"""Seeded human contacts and factual case handovers, without an LLM."""

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.guardrails.escalation import build_handover_summary, load_contacts
from app.models import CaseStep, Document, Escalation
from app.schemas import cards
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry

# The seed identifies contacts by id; these aliases describe their role to the model.
CONTACT_KINDS = {
    "emergency": "rettung_144",
    "ambulance": "rettung_144",
    "gp": "hausaerztin_behandelndes_team",
    "treating_team": "hausaerztin_behandelndes_team",
    "health_advice": "gesundheitsberatung_1450",
    "health_hotline": "gesundheitsberatung_1450",
    "poison_information": "vergiftungsinformation_viz",
    "crisis_hotline": "telefonseelsorge_142",
    "health_insurer": "oegk_kundenservice",
    "pension_insurer": "pva_service",
    "care_services_wien": "fsw_beratungszentrum_pflege",
    "ministry_hotline": "sozialministerium_pflegetelefon",
}
SUBJECT_LABELS = {
    "self": "Anfragende Person",
    "parent": "Elternteil der anfragenden Person",
    "child": "Kind der anfragenden Person",
    "partner": "Partnerin oder Partner der anfragenden Person",
    "other": "Andere betroffene Person",
}


class EscalateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason_code: cards.EscalationReason
    target_kind: str = Field(
        default="health_advice",
        min_length=1,
        description=(
            "Bei reason_code medical_question ist health_advice "
            "(Telefonische Gesundheitsberatung 1450) das Standardziel. "
            "gp und treating_team führen bei medizinischen Fragen ebenfalls zu 1450. "
            "Kontakt-id aus den Eskalationskontakten oder Rolle: "
            + ", ".join(CONTACT_KINDS)
        ),
    )
    open_question: str = Field(
        min_length=1,
        description=(
            "Offene Frage für einen Menschen. Keine Diagnose oder Interpretation."
        ),
    )


@registry.tool(
    "escalate",
    label="Übergabe an einen Menschen wird vorbereitet",
    description=(
        "Bereitet bei medizinischen Fragen, Unsicherheit oder Überforderung eine "
        "Übergabe mit hinterlegtem Kontakt vor. Bei reason_code medical_question "
        "nutze standardmäßig health_advice: Telefonische Gesundheitsberatung 1450. "
        "gp und treating_team führen bei medizinischen Fragen ebenfalls zu 1450. "
        "Die Hausärztin oder das behandelnde Team darf als Hinweis in der offenen "
        "Frage für die Übergabe stehen. Nutze das Tool nicht für Diagnosen, "
        "Befundinterpretation oder Therapieempfehlungen. "
        "Es kontaktiert niemanden und ersetzt im Notfall keinen Anruf beim Notruf."
    ),
    input_model=EscalateInput,
)
async def escalate(input: EscalateInput, ctx: ToolContext) -> ToolOutput:
    contact_id = CONTACT_KINDS.get(input.target_kind, input.target_kind)
    if (
        input.reason_code == "medical_question"
        and contact_id == CONTACT_KINDS["gp"]
    ):
        contact_id = CONTACT_KINDS["health_advice"]
    contacts = load_contacts()
    contact = next(
        (
            contact
            for contact in contacts
            if contact["id"] == contact_id
            and input.reason_code in contact["reason_codes"]
        ),
        None,
    )
    if contact is None:
        raise ToolError("Für diesen Grund und target_kind ist kein Kontakt hinterlegt.")

    done_steps = await ctx.db.scalars(
        select(CaseStep.title)
        .where(CaseStep.case_id == ctx.case.id, CaseStep.status == "done")
        .order_by(CaseStep.position, CaseStep.id)
    )
    documents = await ctx.db.scalars(
        select(Document.filename)
        .where(
            Document.conversation_id == ctx.conversation.id,
            Document.user_id == ctx.user.id,
        )
        .order_by(Document.created_at, Document.id)
    )
    summary = build_handover_summary(
        subject=SUBJECT_LABELS[ctx.case.subject],
        situation=ctx.case.summary,
        done_steps=list(done_steps),
        open_question=input.open_question,
        documents=list(documents),
    )
    target = cards.Contact.model_validate(contact)
    row = Escalation(
        conversation_id=ctx.conversation.id,
        reason_code=input.reason_code,
        target=target.model_dump(mode="json"),
        handover_summary=summary,
    )
    ctx.db.add(row)
    await ctx.db.flush()
    dto = cards.Escalation.model_validate(row)
    await ctx.audit(
        "escalation",
        "Übergabe an einen Menschen vorbereitet",
        {"escalation_id": str(row.id), "reason_code": input.reason_code},
    )
    return ToolOutput(
        result=dto.model_dump(mode="json"),
        card=cards.EscalationCard(escalation=dto),
    )

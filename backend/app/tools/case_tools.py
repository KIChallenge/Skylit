"""Tools that write the case: `upsert_case_step` and `set_case_summary`."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models import CaseStep, Leistung
from app.schemas import cards
from app.tools.leistung_ids import LEISTUNG_ID_HINT
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry


class UpsertCaseStepInput(BaseModel):
    step_id: UUID | None = Field(
        default=None,
        description="Id eines bestehenden Schritts. Leer für einen neuen Schritt.",
    )
    title: str = Field(
        min_length=1, description="Kurzer Titel, z. B. Pflegegeld beantragen."
    )
    description: str = Field(
        default="",
        description="Was die Person tun muss. Nur administrative Angaben.",
    )
    category: cards.StepCategory
    status: cards.StepStatus = "open"
    leistung_id: str | None = Field(
        default=None,
        description="Nur falls der Schritt zu einer Leistung gehört. "
        + LEISTUNG_ID_HINT,
    )
    due_hint: str | None = Field(
        default=None, description="Frist oder Zeitpunkt, nur mit einer Quelle."
    )


class SetCaseSummaryInput(BaseModel):
    title: str = Field(min_length=1, description="Kurzer Titel des Falls.")
    subject: cards.CaseSubject = Field(description="Wen der Fall betrifft.")
    summary: str = Field(description="Administrative Lage in ein bis zwei Sätzen.")


def _find_step(input: UpsertCaseStepInput, ctx: ToolContext) -> CaseStep | None:
    if input.step_id is not None:
        for step in ctx.case.steps:
            if step.id == input.step_id:
                return step
        # The check also stops a call from touching a step of another case.
        raise ToolError("Dieser Fall hat keinen Schritt mit dieser step_id.")
    title = input.title.strip().casefold()
    for step in ctx.case.steps:
        if step.title.strip().casefold() == title:
            return step
    return None


@registry.tool(
    "upsert_case_step",
    label="Schritt wird in „Mein Fall“ eingetragen",
    description=(
        "Legt einen Schritt in „Mein Fall“ an oder ändert ihn. Nutze das Tool, sobald "
        "eine Leistung oder ein konkreter nächster Schritt klar ist. "
        "Nutze es nicht für medizinische Ratschläge, Diagnosen oder Vermutungen. "
        "Nutze es nicht für bloße Rückfragen an die Person."
    ),
    input_model=UpsertCaseStepInput,
)
async def upsert_case_step(input: UpsertCaseStepInput, ctx: ToolContext) -> ToolOutput:
    notes: dict[str, str] = {}
    if input.leistung_id and await ctx.db.get(Leistung, input.leistung_id) is None:
        # A wrong link must not cost the user the step itself.
        notes["note"] = (
            f"Unbekannte leistung_id {input.leistung_id}: "
            "Schritt ohne Leistung gespeichert."
        )
        input = input.model_copy(update={"leistung_id": None})

    step = _find_step(input, ctx)
    if step is None:
        position = max((s.position for s in ctx.case.steps), default=-1) + 1
        step = CaseStep(
            id=uuid4(),
            created_at=datetime.now(UTC),
            case_id=ctx.case.id,
            title=input.title,
            description=input.description,
            status=input.status,
            category=input.category,
            leistung_id=input.leistung_id,
            due_hint=input.due_hint,
            position=position,
        )
        ctx.case.steps.append(step)
    else:
        step.title = input.title
        step.description = input.description
        step.category = input.category
        step.leistung_id = input.leistung_id or step.leistung_id
        step.due_hint = input.due_hint or step.due_hint
        # Without a step_id this is a repeat. A repeat must not undo the user's tick.
        if input.step_id is not None:
            step.status = input.status

    ctx.case.updated_at = datetime.now(UTC)
    await ctx.db.flush()
    dto = cards.CaseStep.model_validate(step)
    return ToolOutput(
        result={"step": dto.model_dump(mode="json"), **notes}, case_changed=True
    )


@registry.tool(
    "set_case_summary",
    label="Fallzusammenfassung wird aktualisiert",
    description=(
        "Setzt Titel, betroffene Person und Zusammenfassung von „Mein Fall“. Nutze das "
        "Tool, sobald du weißt, wen der Fall betrifft und worum es geht. "
        "Nutze es nicht für Diagnosen, Befunde oder medizinische Einschätzungen."
    ),
    input_model=SetCaseSummaryInput,
)
async def set_case_summary(input: SetCaseSummaryInput, ctx: ToolContext) -> ToolOutput:
    ctx.case.title = input.title
    ctx.case.subject = input.subject
    ctx.case.summary = input.summary
    ctx.case.updated_at = datetime.now(UTC)
    await ctx.db.flush()
    return ToolOutput(result={"ok": True}, case_changed=True)

"""Structured benefits and their responsible public offices."""

from typing import Literal
from urllib.parse import quote_plus, urlsplit

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.models import Leistung, Office, Profile
from app.schemas import cards
from app.tools.leistung_ids import LEISTUNG_ID_HINT
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry


class GetLeistungInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    leistung_id: str = Field(min_length=1, description=LEISTUNG_ID_HINT)


class FindOfficeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    leistung_id: str | None = Field(
        default=None, min_length=1, description=LEISTUNG_ID_HINT
    )
    office_kind: Literal[
        "pension_insurer", "health_insurer", "care_services_wien", "ministry_hotline"
    ] | None = None
    postal_code: str | None = Field(default=None, pattern=r"^[0-9]{4}$")
    bundesland: str | None = Field(default=None, min_length=1)


async def _leistung(leistung_id: str, ctx: ToolContext) -> Leistung:
    row = await ctx.db.get(Leistung, leistung_id)
    if row is None:
        raise ToolError(f"Unbekannte leistung_id: {leistung_id}")
    return row


@registry.tool(
    "get_leistung",
    label="Leistung wird nachgeschlagen",
    description=(
        "Liest Bedingungen, benötigte Dokumente und Formulare einer Leistung. "
        "Nutze das Tool nicht zur verbindlichen Anspruchsprüfung oder medizinischen "
        "Beurteilung. Die zuständige Stelle entscheidet über den Anspruch."
    ),
    input_model=GetLeistungInput,
)
async def get_leistung(input: GetLeistungInput, ctx: ToolContext) -> ToolOutput:
    row = await _leistung(input.leistung_id, ctx)
    organisations = await ctx.db.scalars(
        select(Office.organisation)
        .where(Office.kind == row.office_kind)
        .distinct()
        .order_by(Office.organisation)
    )
    dto = cards.LeistungInfo(
        id=row.id,
        title=row.title,
        short=row.short,
        conditions=row.conditions,
        office_hint=", ".join(organisations) or row.office_kind,
        form_ids=row.form_ids,
        documents_needed=row.documents_needed,
        source=cards.Source(
            title=row.title,
            url=row.source_url,
            publisher=urlsplit(row.source_url).hostname or "",
        ),
    )
    return ToolOutput(
        result={"leistung": dto.model_dump(mode="json")},
        card=cards.LeistungCard(leistung=dto),
    )


@registry.tool(
    "find_office",
    label="Zuständige Stelle wird gesucht",
    description=(
        "Sucht öffentliche Stellen nach Leistung oder office_kind und Bundesland. "
        "Erlaubte office_kind-Werte: pension_insurer = PVA/Pflegegeld; "
        "care_services_wien = FSW-Beratung Pflege und Betreuung in Wien; "
        "ministry_hotline = Pflegetelefon des Sozialministeriums; "
        "health_insurer = ÖGK. "
        "Die Postleitzahl priorisiert eine Stelle. "
        "Sie begrenzt nicht die Zuständigkeit. "
        "Nutze das Tool nicht für Arzttermine, medizinische Beratung oder Notfälle."
    ),
    input_model=FindOfficeInput,
)
async def find_office(input: FindOfficeInput, ctx: ToolContext) -> ToolOutput:
    kind = input.office_kind
    if input.leistung_id:
        leistung = await _leistung(input.leistung_id, ctx)
        if kind and kind != leistung.office_kind:
            raise ToolError("office_kind passt nicht zur angegebenen Leistung.")
        kind = leistung.office_kind

    profile = await ctx.db.scalar(select(Profile).where(Profile.user_id == ctx.user.id))
    postal_code = input.postal_code or (profile.postal_code if profile else None)
    bundesland = input.bundesland
    if bundesland is None:
        if postal_code and postal_code.startswith("1"):
            bundesland = "Wien"
        elif input.postal_code is None and profile:
            bundesland = profile.bundesland

    query = select(Office)
    if kind:
        query = query.where(Office.kind == kind)
    if bundesland:
        query = query.where(Office.bundesland.ilike(bundesland))
    rows = list(await ctx.db.scalars(query.order_by(Office.id)))
    rows.sort(key=lambda row: row.postal_code != postal_code)
    if not rows:
        raise ToolError("Für diese Angaben ist keine zuständige Stelle hinterlegt.")
    offices = []
    for row in rows:
        dto = cards.Office.model_validate(row)
        address = f"{row.address}, {row.postal_code} {row.city}"
        dto.maps_url = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(
            address
        )
        offices.append(dto)
    return ToolOutput(
        result={"offices": [office.model_dump(mode="json") for office in offices]},
        card=cards.OfficeCard(office=offices[0]),
    )

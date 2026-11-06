"""Find Vienna providers and propose demo appointments at demo providers."""

from datetime import UTC, date

from pydantic import BaseModel, ConfigDict, Field

from app.providers import AppointmentService, ProviderDirectory
from app.providers.base import TimePreference
from app.providers.mock_appointments import MockAppointmentService
from app.providers.mock_directory import MockProviderDirectory, in_vienna
from app.schemas import cards
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry


class FindProvidersInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: cards.ProviderKind
    postal_code: str = Field(pattern=r"^[0-9]{4}$")
    specialty: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=3, ge=1, le=20)


class ProposeAppointmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider_id: str = Field(min_length=1)
    time_preference: TimePreference = "any"
    earliest_date: date | None = None


@registry.tool(
    "find_providers",
    label="Passende Anbieter werden gesucht",
    description=(
        "Sucht Anbieter in Wien nach Art, Postleitzahl und optionalem Fachgebiet. "
        "Ärztinnen und Ärzte (gp, specialist) stammen aus offenen Daten "
        "der Stadt Wien, "
        "andere Anbieter sind Demo-Daten (`demo: true`). "
        "Teilt die Person ihren Standort, misst das Tool die Entfernung ab dort. "
        "Nutze das Tool nicht für Notfälle oder medizinische Empfehlungen."
    ),
    input_model=FindProvidersInput,
)
async def find_providers(input: FindProvidersInput, ctx: ToolContext) -> ToolOutput:
    directory: ProviderDirectory = MockProviderDirectory(ctx.db)
    providers = await directory.find(
        input.kind,
        input.postal_code,
        specialty=input.specialty,
        limit=input.limit,
        origin=ctx.location,
    )
    origin = "location" if ctx.location and in_vienna(*ctx.location) else "postal_code"
    demo = any(provider.demo for provider in providers) or not providers
    card = cards.ProviderListCard(providers=providers, demo=demo, origin=origin)
    # The LLM sees the distance origin, never the coordinates. Distances from the
    # shared location stay out too: three of them would reveal the location.
    hidden = {"distance_km"} if origin == "location" else set()
    return ToolOutput(
        result={
            "providers": [p.model_dump(mode="json", exclude=hidden) for p in providers],
            "demo": demo,
            "distance_from": "standort" if origin == "location" else "postleitzahl",
        },
        card=card,
    )


@registry.tool(
    "propose_appointment",
    label="Demo-Termin wird vorgeschlagen",
    description=(
        "Schlägt einen 45-minütigen Demo-Termin bei einem gefundenen Anbieter vor. "
        "Der Termin bleibt ein Vorschlag und ist keine echte Buchung. "
        "Nutze das Tool nicht für Notfälle oder echte Terminbuchungen."
    ),
    input_model=ProposeAppointmentInput,
)
async def propose_appointment(
    input: ProposeAppointmentInput, ctx: ToolContext
) -> ToolOutput:
    directory: ProviderDirectory = MockProviderDirectory(ctx.db)
    provider = await directory.get(input.provider_id)
    if provider is None:
        raise ToolError("Dieser Demo-Anbieter wurde nicht gefunden.")
    if not provider.demo:
        raise ToolError(
            "Für echte Ordinationen gibt es keine Demo-Termine. "
            "Die Person vereinbart den Termin telefonisch."
        )
    service: AppointmentService = MockAppointmentService(ctx.db)
    row = await service.propose(
        input.provider_id,
        user_id=ctx.user.id,
        conversation_id=ctx.conversation.id,
        time_preference=input.time_preference,
        earliest_date=input.earliest_date,
    )
    appointment = cards.Appointment(
        id=row.id,
        provider=provider,
        start=row.start.astimezone(UTC),
        end=row.end.astimezone(UTC),
        ics_url=f"/api/appointments/{row.id}/ics",
    )
    return ToolOutput(
        result={"appointment": appointment.model_dump(mode="json"), "demo": True},
        card=cards.AppointmentCard(appointment=appointment),
    )

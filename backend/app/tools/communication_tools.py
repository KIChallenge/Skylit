"""Email drafts remain under the user's control."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import cards
from app.tools.registry import ToolContext, ToolOutput, registry


class DraftEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    to_label: str = Field(min_length=1)
    to_email: str | None = Field(default=None, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)

    @field_validator("to_email", mode="before")
    @classmethod
    def empty_address_is_none(cls, value: Any) -> Any:
        # The model writes "" or "None" when it knows no address.
        if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
            return None
        return value


@registry.tool(
    "draft_email",
    label="E-Mail-Entwurf wird erstellt",
    description=(
        "Erstellt einen E-Mail-Entwurf zur Prüfung durch die Person. Sendet niemals "
        "eine E-Mail. Nutze nur bekannte Empfängeradressen; erfinde keine Adresse. "
        "Nutze das Tool nicht für Notfälle, Diagnosen oder medizinische Empfehlungen."
    ),
    input_model=DraftEmailInput,
)
async def draft_email(input: DraftEmailInput, ctx: ToolContext) -> ToolOutput:
    email = cards.EmailDraft(**input.model_dump())
    return ToolOutput(
        result={"ok": True, "email": email.model_dump(mode="json")},
        card=cards.EmailDraftCard(email=email),
    )

"""Persist editable PDF drafts and report fields that need human input."""

import asyncio
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.forms import fill
from app.forms.registry import (
    FILLED_BY_OTHERS,
    FormError,
    get_field_map,
    get_template,
    has_field_map,
    list_templates,
)
from app.models import FormDraft
from app.schemas import cards
from app.tools.registry import ToolContext, ToolError, ToolOutput, registry


class PrepareFormInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    form_id: str = Field(min_length=1)
    values: dict[str, str]


def to_form_draft(row: FormDraft) -> cards.FormDraft:
    """Rebuild the public DTO from accepted values and the shared field map."""
    mappings = get_field_map(row.form_id)
    return cards.FormDraft(
        id=row.id,
        form_id=row.form_id,
        title=get_template(row.form_id).title,
        filled=[
            cards.FieldValue(
                key=key,
                label=mappings[key].label,
                value=row.values[key],
                source="conversation",
            )
            for key in mappings
            if key in row.values
        ],
        missing=row.missing,
        to_be_filled_by_others=[
            cards.FieldSpec(key=key, label=mapping.label, hint=mapping.hint)
            for key, mapping in mappings.items()
            if mapping.filled_by in FILLED_BY_OTHERS
        ],
        pdf_url=f"/api/form-drafts/{row.id}/pdf",
        created_at=row.created_at,
    )


def _store_pdf(path: Path, pdf: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_bytes(pdf)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


MAIN_KEYS_PER_FORM = 8


def _main_keys(form_id: str) -> list[str]:
    """The first required keys the Lotse fills itself, so the first call fits."""
    return [
        key
        for key, mapping in get_field_map(form_id).items()
        if mapping.filled_by == "lotse"
        and not mapping.optional
        and mapping.when is None
    ][:MAIN_KEYS_PER_FORM]


def _available_forms() -> str:
    """List the fillable forms and their main keys for the tool description."""
    return "; ".join(
        f'{template.id} = „{template.title}“ ({template.issuer}), '
        f'Hauptschlüssel: {", ".join(_main_keys(template.id))}'
        for template in list_templates()
        if has_field_map(template.id)
    )


@registry.tool(
    "prepare_form",
    label="Formular wird vorausgefüllt",
    description=(
        "Füllt ein Formular mit bekannten Angaben aus Gespräch, Dokument oder Profil. "
        "values enthält semantische Feldschlüssel. Nur applicant- und lotse-Felder "
        "dürfen Werte erhalten. Nutze das Tool nicht zum Ausfüllen ärztlicher Felder "
        "oder Behördenfelder. Erfinde keine Angaben und sende keinen Antrag. "
        "Die Person prüft und unterschreibt das Formular selbst. "
        "Weitere Schlüssel nennt das Ergebnis unter missing. "
        f"Verfügbare form_id: {_available_forms()}."
    ),
    input_model=PrepareFormInput,
)
async def prepare_form(input: PrepareFormInput, ctx: ToolContext) -> ToolOutput:
    try:
        prepared = await asyncio.to_thread(fill.prepare, input.form_id, input.values)
    except FormError as exc:
        raise ToolError(str(exc)) from exc

    draft_id = uuid4()
    path = Path(settings.upload_dir) / "form_drafts" / f"{draft_id}.pdf"
    row = FormDraft(
        id=draft_id,
        user_id=ctx.user.id,
        conversation_id=ctx.conversation.id,
        form_id=prepared.form_id,
        values={field.key: field.value for field in prepared.filled},
        missing=[field.model_dump() for field in prepared.missing],
        pdf_path=str(path),
    )
    try:
        await asyncio.to_thread(_store_pdf, path, prepared.pdf)
        ctx.db.add(row)
        await ctx.db.flush()
        dto = to_form_draft(row)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return ToolOutput(
        result={**dto.model_dump(mode="json"), "rejected": prepared.rejected},
        card=cards.FormDraftCard(form_draft=dto),
    )

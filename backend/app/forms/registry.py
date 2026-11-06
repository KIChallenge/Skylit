"""Form templates and field maps from `backend/seed/forms/`.

`registry.json` lists the templates. `field_maps/<form_id>.json` maps our
semantic keys (`applicant.last_name`, …) to the AcroForm field names of that
PDF. Build a field map with `make dump-fields PDF=<pdf>`.
"""

import json
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
FORMS_DIR = SEED_DIR / "forms"

FilledBy = Literal["applicant", "doctor", "office", "lotse"]
# The Lotse prefills these, or the user names the value in the conversation.
SELF_FILLED: frozenset[str] = frozenset({"applicant", "lotse"})
# Only a doctor or the office fills these. The Lotse never writes them.
FILLED_BY_OTHERS: frozenset[str] = frozenset({"doctor", "office"})


class FormError(Exception):
    """Base error for form lookups. The message is safe to show the LLM."""


class UnknownFormError(FormError):
    pass


class FieldMapMissingError(FormError):
    pass


class FieldCondition(BaseModel):
    """A field counts as missing only if `key` has a value (equal to `value`)."""

    key: str
    value: str | None = None


class FieldMapping(BaseModel):
    key: str
    field: str = Field(description="AcroForm field name in the PDF")
    label: str = Field(description="German label, as on the form")
    filled_by: FilledBy
    hint: str | None = None
    # Checkbox and radio fields: semantic value -> export state, e.g. "ja" -> "/02".
    options: dict[str, str] | None = None
    # Optional fields never appear in `missing`.
    optional: bool = False
    when: FieldCondition | None = None
    # Without an own value, the field joins the values of these keys with spaces,
    # e.g. "Familienname Vorname" from last and first name. Mark such fields optional.
    copy_from: list[str] | None = None


class FormTemplate(BaseModel):
    id: str
    title: str
    issuer: str
    file: str = Field(description="PDF path relative to backend/seed/")
    leistung_ids: list[str]

    @property
    def pdf_path(self) -> Path:
        return SEED_DIR / self.file


@cache
def _templates() -> dict[str, FormTemplate]:
    raw = json.loads((FORMS_DIR / "registry.json").read_text(encoding="utf-8"))
    return {entry["id"]: FormTemplate.model_validate(entry) for entry in raw}


def list_templates() -> list[FormTemplate]:
    return list(_templates().values())


def get_template(form_id: str) -> FormTemplate:
    template = _templates().get(form_id)
    if template is None:
        known = ", ".join(_templates())
        raise UnknownFormError(f"Unknown form '{form_id}'. Known forms: {known}")
    return template


def has_field_map(form_id: str) -> bool:
    return (FORMS_DIR / "field_maps" / f"{form_id}.json").is_file()


@cache
def get_field_map(form_id: str) -> dict[str, FieldMapping]:
    """Return semantic key -> mapping, in the order of the form."""
    get_template(form_id)
    path = FORMS_DIR / "field_maps" / f"{form_id}.json"
    if not path.is_file():
        raise FieldMapMissingError(f"Form '{form_id}' has no field map yet")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: FieldMapping.model_validate({"key": key, **entry})
        for key, entry in raw.items()
    }

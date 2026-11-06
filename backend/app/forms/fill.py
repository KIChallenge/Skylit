"""Prefill an AcroForm PDF from semantic values (docs/architecture.md §8).

`prepare()` writes the values into the PDF with pypdf and reports, per field
of the field map, what it filled, what is still missing and what a doctor or
the office fills. The form stays editable (no flatten). NeedAppearances is
set, so PDF viewers render the values.
"""

from collections.abc import Mapping
from functools import cache
from io import BytesIO
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, Field
from pypdf import PdfWriter

from app.forms import registry
from app.forms.dump_fields import read_fields
from app.forms.registry import FILLED_BY_OTHERS, SELF_FILLED, FieldMapping

ValueSource = Literal["conversation", "document", "profile"]
VALUE_SOURCES: frozenset[str] = frozenset(get_args(ValueSource))
DEFAULT_SOURCE: ValueSource = "conversation"


class FieldValue(BaseModel):
    key: str
    label: str
    value: str
    source: ValueSource


class FieldSpec(BaseModel):
    key: str
    label: str
    hint: str | None = None


class PreparedForm(BaseModel):
    form_id: str
    title: str
    filled: list[FieldValue]
    missing: list[FieldSpec]
    to_be_filled_by_others: list[FieldSpec]
    rejected: dict[str, str] = Field(
        default_factory=dict,
        description="Semantic key -> reason why prepare() did not write the value",
    )
    pdf: bytes = Field(repr=False, exclude=True)


def prepare(
    form_id: str,
    values: Mapping[str, str],
    sources: Mapping[str, str] | None = None,
) -> PreparedForm:
    """Fill `form_id` with `values` (semantic key -> value).

    `sources` names where each value came from ("conversation", "document",
    "profile"). Keys without a source count as "conversation".
    Raises `registry.FormError` for an unknown form or a form without a
    field map, and `ValueError` for an unknown source.
    """
    template = registry.get_template(form_id)
    field_map = registry.get_field_map(form_id)
    sources = dict(sources or {})
    invalid_sources = {k: s for k, s in sources.items() if s not in VALUE_SOURCES}
    if invalid_sources:
        raise ValueError(f"Unknown value sources: {invalid_sources}")

    max_lengths = _max_lengths(template.pdf_path)
    accepted: dict[str, str] = {}
    pdf_values: dict[str, str] = {}
    rejected: dict[str, str] = {}
    for key, raw in values.items():
        value = "" if raw is None else str(raw).strip()
        if not value:
            continue
        mapping = field_map.get(key)
        if mapping is None:
            rejected[key] = "unknown key for this form"
            continue
        if mapping.filled_by in FILLED_BY_OTHERS:
            rejected[key] = f"only the {mapping.filled_by} fills this field"
            continue
        try:
            shown, written = _resolve(mapping, value, max_lengths.get(mapping.field))
        except ValueError as error:
            rejected[key] = str(error)
            continue
        accepted[key] = shown
        pdf_values[mapping.field] = written

    derived_sources: dict[str, str] = {}
    for key, mapping in field_map.items():
        if key in accepted or not mapping.copy_from:
            continue
        parts = [accepted[source] for source in mapping.copy_from if source in accepted]
        if not parts:
            continue
        try:
            shown, written = _resolve(
                mapping, " ".join(parts), max_lengths.get(mapping.field)
            )
        except ValueError:
            continue
        accepted[key] = shown
        pdf_values[mapping.field] = written
        first = next(source for source in mapping.copy_from if source in accepted)
        derived_sources[key] = sources.get(first, DEFAULT_SOURCE)

    filled = [
        FieldValue(
            key=key,
            label=mapping.label,
            value=accepted[key],
            source=derived_sources.get(key) or sources.get(key, DEFAULT_SOURCE),
        )
        for key, mapping in field_map.items()
        if key in accepted
    ]
    missing = [
        _spec(mapping)
        for mapping in field_map.values()
        if _is_missing(mapping, accepted)
    ]
    by_others = [
        _spec(mapping)
        for mapping in field_map.values()
        if mapping.filled_by in FILLED_BY_OTHERS
    ]
    return PreparedForm(
        form_id=template.id,
        title=template.title,
        filled=filled,
        missing=missing,
        to_be_filled_by_others=by_others,
        rejected=rejected,
        pdf=render_pdf(template.pdf_path, pdf_values),
    )


def render_pdf(pdf_path: Path, field_values: Mapping[str, str]) -> bytes:
    """Write AcroForm values (field name -> text or export state) into a copy."""
    writer = PdfWriter(clone_from=pdf_path)
    if field_values:
        writer.update_page_form_field_values(
            None, dict(field_values), auto_regenerate=True
        )
    writer.set_need_appearances_writer(True)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _resolve(mapping: FieldMapping, value: str, max_len: int | None) -> tuple[str, str]:
    """Return (value shown to the user, value written to the PDF).

    Raises ValueError with the reason if the value does not fit the field.
    """
    if mapping.options is None:
        if max_len is not None and len(value) > max_len:
            raise ValueError(f"longer than {max_len} characters")
        return value, value
    wanted = value.casefold()
    for option, state in mapping.options.items():
        if option.casefold() == wanted:
            return option, state
    allowed = ", ".join(f'"{option}"' for option in mapping.options)
    raise ValueError(f"invalid value, allowed: {allowed}")


def _is_missing(mapping: FieldMapping, accepted: Mapping[str, str]) -> bool:
    if mapping.filled_by not in SELF_FILLED or mapping.optional:
        return False
    if mapping.key in accepted:
        return False
    condition = mapping.when
    if condition is None:
        return True
    actual = accepted.get(condition.key)
    if actual is None:
        return False
    return condition.value is None or actual.casefold() == condition.value.casefold()


def _spec(mapping: FieldMapping) -> FieldSpec:
    return FieldSpec(key=mapping.key, label=mapping.label, hint=mapping.hint)


@cache
def _max_lengths(pdf_path: Path) -> dict[str, int]:
    return {
        field["name"]: field["max_len"]
        for field in read_fields(pdf_path)
        if "max_len" in field
    }

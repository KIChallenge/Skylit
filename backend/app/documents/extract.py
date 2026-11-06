"""One LLM call that turns document text or images into a quote-only extraction."""

import base64
import logging
import re
import unicodedata
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import ValidationError
from rapidfuzz import fuzz

from app.config import settings
from app.llm.client import get_llm_client
from app.schemas.documents import DocumentExtraction

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "llm" / "prompts" / "document_extraction.md"
)
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")
_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "document_extraction",
        "strict": True,
        "schema": DocumentExtraction.model_json_schema(),
    },
}
# eustella trap 1: reasoning counts toward max_tokens, and a cut-off JSON is useless.
_MAX_TOKENS = 8192

_RELEVANT_HEADING = re.compile(
    r"Empfehlung|Hinweise|Pflege|Entlassung|Termin", re.IGNORECASE
)
_NUMBERED_HEADING = re.compile(
    r"^\s*(?P<number>\d+\.(?:\d+\.?)*|\d+\))\s+(?P<title>\S.*?)\s*$"
)
_PLAIN_HEADING = re.compile(
    r"^(?:Empfehlung|Hinweise|Pflege|Entlassung|Termin|Patient|"
    r"Diagnos|Befund|Anamnese|Medikation|Therapie|Verlauf|Labor|Zusammenfassung)",
    re.IGNORECASE,
)

_NO_CONTENT_MESSAGE = "Das Dokument enthält keinen lesbaren Inhalt."
_INVALID_MESSAGE = (
    "Das Dokument konnte nicht ausgewertet werden. Bitte versuchen Sie es erneut."
)
_OCR_NOTE = (
    "Der Text wurde per Texterkennung (OCR) gelesen. Die Zitate wurden mit "
    "Toleranz geprüft. Bitte vergleichen Sie sie mit dem Original."
)
_UNVERIFIED_NOTE = (
    "Das Dokument liegt nur als Bild vor. Die Zitate wurden nicht automatisch "
    "geprüft. Bitte vergleichen Sie sie mit dem Original."
)


class DocumentError(Exception):
    """A document that cannot be processed. `message` is German and user-safe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def add_note(extraction: DocumentExtraction, note: str) -> DocumentExtraction:
    """Append a note to `confidence_note` and keep what the model wrote there."""
    existing = extraction.confidence_note
    combined = f"{existing} {note}" if existing else note
    return extraction.model_copy(update={"confidence_note": combined})


def _normalize(text: str) -> str:
    # NFKC undoes PDF ligatures such as "ﬁ", which the model writes as "fi".
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _heading(line: str) -> tuple[tuple[str, ...], str] | None:
    numbered = _NUMBERED_HEADING.match(line)
    if numbered:
        number = numbered["number"].rstrip(".)")
        return tuple(number.split(".")), numbered["title"]
    title = line.strip().removesuffix(":")
    if (
        len(title) <= 100
        and not re.search(r"[.:!?]", title)
        and (_PLAIN_HEADING.match(title) or line.strip().endswith(":"))
    ):
        return (), title
    return None


def _select_sections(pages_text: list[str]) -> list[str]:
    """Keep the header and relevant sections, including page continuations."""
    lines = [
        [(line, _heading(line)) for line in page.splitlines(keepends=True)]
        for page in pages_text
    ]
    if not any(
        heading and _RELEVANT_HEADING.search(heading[1])
        for page in lines
        for _, heading in page
    ):
        return pages_text

    selected: list[str] = []
    parents: list[tuple[str, ...]] = []
    keep = True
    for page in lines:
        retained: list[str] = []
        for line, heading in page:
            if heading:
                number, title = heading
                if number:
                    parents = [
                        parent for parent in parents
                        if number[:len(parent)] == parent and number != parent
                    ]
                keep = bool(
                    parents
                    or _RELEVANT_HEADING.search(title)
                    or re.match(r"Patient", title, re.IGNORECASE)
                )
                if number and keep:
                    parents.append(number)
            if keep:
                retained.append(line)
        selected.append("".join(retained))
    return selected


def _text_content(pages_text: list[str]) -> str:
    pages = [
        f"--- Seite {number} ---\n{text}"
        for number, text in enumerate(_select_sections(pages_text), start=1)
        if text.strip()
    ]
    return "Dokumenttext:\n\n" + "\n\n".join(pages)


def _image_content(page_images: list[bytes]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [
        {"type": "text", "text": "Die Bilder zeigen das Dokument, Seite für Seite."}
    ]
    for image in page_images:
        encoded = base64.b64encode(image).decode("ascii")
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            }
        )
    return parts


def _parse(text: str) -> DocumentExtraction:
    try:
        return DocumentExtraction.model_validate_json(text)
    except ValidationError as exc:
        # The error text can hold personal data from the document. Log only the count.
        logger.warning("Extraction failed validation: errors=%d", exc.error_count())
        raise DocumentError("invalid_extraction", _INVALID_MESSAGE) from None


# OCR tolerance must never turn "19.11." into "12.11." or drop a "nicht".
_NUMBERS = re.compile(r"\d+(?:[.,:/-]\d+)*")
_NEGATIONS = re.compile(r"\b(?:nicht|kein\w*|ohne|nie)\b", re.IGNORECASE)


def _nearly_verbatim(quote: str, ocr_text: str) -> bool:
    """A near match in OCR text. Numbers and negations must still match exactly."""
    numbers = set(_NUMBERS.findall(ocr_text))
    if any(number not in numbers for number in _NUMBERS.findall(quote)):
        return False
    words = set(re.findall(r"\w+", ocr_text.casefold()))
    if any(word.casefold() not in words for word in _NEGATIONS.findall(quote)):
        return False
    score = fuzz.partial_ratio(quote.casefold(), ocr_text.casefold())
    return score >= settings.ocr_quote_min_similarity


def _verify_quotes(
    extraction: DocumentExtraction, source_text: str, *, ocr_text: str = ""
) -> DocumentExtraction:
    """Drop every quote that is not verbatim in the source text.

    A quote also counts when it is nearly verbatim in `ocr_text`, the OCR pages.
    """
    source = _normalize(source_text)
    ocr = _normalize(ocr_text)

    def found(quote: str) -> bool:
        normalized = _normalize(quote)
        if not normalized:
            return False
        if normalized in source:
            return True
        return bool(ocr) and _nearly_verbatim(normalized, ocr)

    recommendations = [
        item for item in extraction.documented_recommendations if found(item.quote)
    ]
    appointments = [
        item for item in extraction.follow_up_appointments if found(item.quote)
    ]
    warnings = [item for item in extraction.warnings_in_document if found(item)]
    dropped = {
        "Empfehlungen": len(extraction.documented_recommendations)
        - len(recommendations),
        "Termine": len(extraction.follow_up_appointments) - len(appointments),
        "Warnhinweise": len(extraction.warnings_in_document) - len(warnings),
    }
    verified = extraction.model_copy(
        update={
            "documented_recommendations": recommendations,
            "follow_up_appointments": appointments,
            "warnings_in_document": warnings,
        }
    )
    counts = ", ".join(f"{name}: {n}" for name, n in dropped.items() if n)
    if not counts:
        return verified
    logger.warning("Extraction quotes dropped: %s", counts)
    return add_note(
        verified,
        f"Verworfen, weil das Zitat nicht wörtlich im Dokument steht: {counts}.",
    )


async def extract(
    pages_text: list[str] | None,
    page_images: list[bytes] | None,
    *,
    ocr_pages: frozenset[int] = frozenset(),
) -> DocumentExtraction:
    """Extract facts from the text if present, otherwise from PNG page images.

    `ocr_pages` names the 1-based pages whose text comes from OCR.
    """
    has_text = any(text.strip() for text in pages_text or [])
    if not has_text and not page_images:
        raise DocumentError("no_content", _NO_CONTENT_MESSAGE)

    content = (
        _text_content(pages_text) if has_text else _image_content(page_images)
    )
    thinking = settings.document_extraction_thinking if has_text else True
    result = None
    started = perf_counter()
    try:
        result = await get_llm_client().complete(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            thinking=thinking,
            max_tokens=_MAX_TOKENS,
            response_format=_RESPONSE_FORMAT,
        )
    finally:
        usage = result.usage if result is not None else None
        logger.info(
            "Document extraction: duration_seconds=%.3f input_type=%s "
            "thinking=%s status=%s prompt_tokens=%s completion_tokens=%s "
            "cached_tokens=%s",
            perf_counter() - started,
            "text" if has_text else "image",
            thinking,
            "completed" if result is not None else "failed",
            usage.prompt_tokens if usage is not None else None,
            usage.completion_tokens if usage is not None else None,
            usage.cached_tokens if usage is not None else None,
        )
    extraction = _parse(result.text)
    if has_text and ocr_pages:
        ocr_text = " ".join(pages_text[number - 1] for number in sorted(ocr_pages))
        verified = _verify_quotes(
            extraction, " ".join(pages_text), ocr_text=ocr_text
        )
        return add_note(verified, _OCR_NOTE)
    if has_text:
        return _verify_quotes(extraction, " ".join(pages_text))
    # An image has no text layer to check against, so the note must say that.
    return add_note(extraction, _UNVERIFIED_NOTE)

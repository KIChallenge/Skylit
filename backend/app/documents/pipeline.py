"""Store uploads, read them as text or images, and save the extraction."""

import asyncio
import logging
import time
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pymupdf
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.documents.extract import DocumentError, add_note, extract
from app.llm.types import LLMError
from app.models import Document, User

logger = logging.getLogger(__name__)

PDF_MIME_TYPE = "application/pdf"
ALLOWED_MIME_TYPES = frozenset({PDF_MIME_TYPE, "image/jpeg", "image/png"})
RENDER_DPI = 150
# A phone photo as PNG can reach many megabytes, too large for one API request.
MAX_PHOTO_EDGE_PX = 2048
OCR_DPI = 300
# Less text than this means OCR failed, so the vision model reads the images.
MIN_OCR_CHARS = 50

_UNSUPPORTED_MESSAGE = (
    "Dieser Dateityp wird nicht unterstützt. "
    "Bitte laden Sie ein PDF, JPEG oder PNG hoch."
)
_EMPTY_MESSAGE = "Die Datei ist leer."
_UNREADABLE_MESSAGE = (
    "Die Datei konnte nicht gelesen werden. "
    "Bitte prüfen Sie, ob sie beschädigt oder passwortgeschützt ist."
)
_STORAGE_MESSAGE = (
    "Die Datei konnte nicht gespeichert werden. Bitte versuchen Sie es erneut."
)
_MISSING_MESSAGE = (
    "Die Datei ist nicht mehr vorhanden. Bitte laden Sie sie erneut hoch."
)
_GENERIC_MESSAGE = (
    "Das Dokument konnte nicht verarbeitet werden. Bitte versuchen Sie es erneut."
)


def _check_mime_type(mime_type: str) -> None:
    if mime_type not in ALLOWED_MIME_TYPES:
        raise DocumentError("unsupported_type", _UNSUPPORTED_MESSAGE)


def _check_size(size: int) -> None:
    if size == 0:
        raise DocumentError("empty_file", _EMPTY_MESSAGE)
    if size > settings.max_upload_mb * 1024 * 1024:
        raise DocumentError(
            "file_too_large",
            "Die Datei ist zu groß. "
            f"Erlaubt sind höchstens {settings.max_upload_mb} MB.",
        )


def _read_pdf(data: bytes) -> tuple[list[str] | None, list[bytes] | None]:
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        pages_text = [page.get_text() for page in pdf]
        if any(text.strip() for text in pages_text):
            return pages_text, None
        return None, [
            page.get_pixmap(dpi=RENDER_DPI).tobytes("png") for page in pdf
        ]


def _read_photo(data: bytes) -> bytes:
    pixmap = pymupdf.Pixmap(data)
    # PNG holds grey and RGB only, and a print-ready JPEG can be CMYK.
    if pixmap.n - pixmap.alpha not in (1, 3):
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)
    while max(pixmap.width, pixmap.height) > MAX_PHOTO_EDGE_PX:
        pixmap.shrink(1)
    return pixmap.tobytes("png")


def load_pages(
    data: bytes, mime_type: str
) -> tuple[list[str] | None, list[bytes] | None]:
    """Return `(pages_text, page_images)`. Only one of the two is set."""
    try:
        if mime_type == PDF_MIME_TYPE:
            return _read_pdf(data)
        return None, [_read_photo(data)]
    except Exception as exc:
        # PyMuPDF raises several error types for damaged and encrypted files.
        logger.warning("Document unreadable: error_type=%s", type(exc).__name__)
        raise DocumentError("unreadable_file", _UNREADABLE_MESSAGE) from None


def _tessdata() -> str | None:
    """Return the Tesseract language folder, or None when OCR cannot run."""
    if not settings.ocr_enabled:
        return None
    return _detect_tessdata(settings.ocr_tessdata_dir, settings.ocr_languages)


@cache
def _detect_tessdata(configured: str, languages_setting: str) -> str | None:
    try:
        folder = Path(pymupdf.get_tessdata(configured or None))
    except Exception as exc:
        logger.warning("OCR unavailable: error_type=%s", type(exc).__name__)
        return None
    languages = languages_setting.split("+")
    missing = [
        lang for lang in languages if not (folder / f"{lang}.traineddata").is_file()
    ]
    if missing:
        logger.warning("OCR unavailable: missing languages=%s", ",".join(missing))
        return None
    return str(folder)


def _ocr_page(page: pymupdf.Page, tessdata: str) -> str:
    textpage = page.get_textpage_ocr(
        language=settings.ocr_languages, dpi=OCR_DPI, full=True, tessdata=tessdata
    )
    return page.get_text(textpage=textpage)


def ocr_pages(
    data: bytes, mime_type: str, page_numbers: list[int], tessdata: str
) -> dict[int, str]:
    """OCR the given 1-based pages. A photo counts as page 1."""
    if mime_type == PDF_MIME_TYPE:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    else:
        with pymupdf.open(stream=data, filetype=mime_type.split("/")[1]) as image:
            pdf = pymupdf.open(stream=image.convert_to_pdf(), filetype="pdf")
    with pdf:
        return {number: _ocr_page(pdf[number - 1], tessdata) for number in page_numbers}


async def _add_ocr_text(
    data: bytes,
    mime_type: str,
    pages_text: list[str] | None,
    page_images: list[bytes] | None,
) -> tuple[list[str] | None, list[bytes] | None, frozenset[int]]:
    """Fill pages without text by OCR. Any OCR failure keeps the input unchanged."""
    tessdata = _tessdata()
    if tessdata is None:
        return pages_text, page_images, frozenset()
    if pages_text is not None:
        blank = [n for n, text in enumerate(pages_text, start=1) if not text.strip()]
    else:
        blank = list(range(1, len(page_images or []) + 1))
    if not blank:
        return pages_text, page_images, frozenset()

    started = time.perf_counter()
    try:
        found = await asyncio.wait_for(
            asyncio.to_thread(ocr_pages, data, mime_type, blank, tessdata),
            timeout=settings.ocr_timeout_seconds,
        )
    except Exception as exc:
        logger.warning("OCR failed: error_type=%s", type(exc).__name__)
        return pages_text, page_images, frozenset()
    readable = {
        n: text for n, text in found.items() if len(text.strip()) >= MIN_OCR_CHARS
    }
    # Log counts only: OCR text can hold personal data.
    logger.info(
        "OCR: pages=%d readable=%d chars=%d duration_seconds=%.3f",
        len(blank),
        len(readable),
        sum(len(text) for text in readable.values()),
        time.perf_counter() - started,
    )
    if not readable:
        return pages_text, page_images, frozenset()
    if pages_text is None:
        # An image-only document: text replaces images only if every page was read.
        if len(readable) < len(blank):
            return pages_text, page_images, frozenset()
        pages_text = [""] * len(blank)
    texts = list(pages_text)
    for number, text in readable.items():
        texts[number - 1] = text
    return texts, None, frozenset(readable)


def _write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


async def store_upload(
    session: AsyncSession, user: User, filename: str, mime_type: str, data: bytes
) -> Document:
    """Check an upload, save it and return its row with status `processing`.

    Raises DocumentError for a rejected file, so that nothing reaches the disk.
    """
    _check_mime_type(mime_type)
    _check_size(len(data))

    document_id = uuid4()
    path = Path(settings.upload_dir) / str(document_id)
    document = Document(
        id=document_id,
        user_id=user.id,
        filename=filename,
        mime_type=mime_type,
        storage_path=str(path),
        status="processing",
    )
    session.add(document)
    await session.flush()
    try:
        await asyncio.to_thread(_write_file, path, data)
    except OSError as exc:
        await session.rollback()
        logger.error("Upload not stored: error_type=%s", type(exc).__name__)
        raise DocumentError("storage_failed", _STORAGE_MESSAGE) from None
    await session.commit()
    await session.refresh(document)
    return document


async def _read_stored_file(document: Document) -> bytes:
    try:
        return await asyncio.to_thread(Path(document.storage_path).read_bytes)
    except OSError as exc:
        logger.error(
            "Stored file unreadable: document_id=%s error_type=%s",
            document.id,
            type(exc).__name__,
        )
        raise DocumentError("file_missing", _MISSING_MESSAGE) from None


async def _extract_document(document: Document) -> dict[str, Any]:
    _check_mime_type(document.mime_type)
    data = await _read_stored_file(document)
    _check_size(len(data))

    pages_text, page_images = await asyncio.to_thread(
        load_pages, data, document.mime_type
    )
    pages_text, page_images, ocr_numbers = await _add_ocr_text(
        data, document.mime_type, pages_text, page_images
    )
    extraction = await extract(pages_text, page_images, ocr_pages=ocr_numbers)

    # Text decides for the whole PDF, so a page that OCR cannot read goes unread.
    blank_pages = [
        str(number)
        for number, text in enumerate(pages_text or [], start=1)
        if not text.strip()
    ]
    if blank_pages:
        extraction = add_note(
            extraction,
            f"Ohne lesbaren Text und daher nicht ausgewertet: "
            f"Seite {', '.join(blank_pages)}.",
        )
    return extraction.model_dump(mode="json")


async def process_document(
    session: AsyncSession, document_id: UUID
) -> Document | None:
    """Run the extraction and save the outcome. A failure ends as status `failed`."""
    document = await session.get(Document, document_id)
    if document is None:
        logger.warning("Document not found: document_id=%s", document_id)
        return None

    error: str | None = None
    extracted: dict[str, Any] | None = None
    try:
        extracted = await _extract_document(document)
    except DocumentError as exc:
        logger.warning(
            "Document failed: document_id=%s code=%s", document_id, exc.code
        )
        error = exc.message
    except LLMError as exc:
        logger.warning(
            "Document failed: document_id=%s llm_code=%s request_id=%s",
            document_id,
            exc.code,
            exc.request_id,
        )
        error = exc.message
    except Exception:
        logger.exception("Document failed: document_id=%s", document_id)
        error = _GENERIC_MESSAGE

    document.extracted = extracted
    document.kind = extracted["kind"] if extracted else None
    document.status = "ready" if extracted else "failed"
    document.error = error
    await session.commit()
    await session.refresh(document)
    return document

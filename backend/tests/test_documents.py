import base64
import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

import pymupdf
import pytest

from app.config import REPO_ROOT, Settings, settings
from app.documents import extract as extract_module
from app.documents import pipeline as pipeline_module
from app.documents.extract import (
    DocumentError,
    _normalize,
    _text_content,
    _verify_quotes,
    extract,
)
from app.documents.pipeline import (
    MAX_PHOTO_EDGE_PX,
    _detect_tessdata,
    load_pages,
    process_document,
    store_upload,
)
from app.llm.types import LLMError, LLMResult, Usage
from app.schemas.documents import Document as DocumentResponse
from app.schemas.documents import DocumentExtraction

BACKEND = Path(__file__).resolve().parents[1]
SAMPLE_PDF = BACKEND / "seed" / "documents" / "entlassungsbefund.pdf"
EXPECTED = json.loads(
    (REPO_ROOT / "eval" / "extraction_expected.json").read_text(encoding="utf-8")
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PDF = "application/pdf"


def golden_reply() -> dict:
    """Map the labelled eval file to the schema, like a perfect model reply."""
    patient = EXPECTED["patient"]
    return {
        "kind": "discharge_letter",
        "issuer": "Abteilung für Innere Medizin und Onkologie",
        "document_date": "29.10.2026",
        "patient": {**patient, "svnr": None},
        "living_situation": "Lebt allein in einer Mietwohnung mit Lift",
        "documented_recommendations": deepcopy(EXPECTED["recommendations"]),
        "follow_up_appointments": [
            {
                "what": "Hausärztliche Kontrolle",
                "when": None,
                "quote": "Termin zur hausärztlichen Kontrolle vereinbaren",
            }
        ],
        "warnings_in_document": [
            "Bei akuten Warnzeichen wie Bewusstseinsstörungen, starken Blutungen "
            "oder schwerer Atemnot ist unverzüglich medizinische Hilfe erforderlich."
        ],
        "confidence_note": None,
    }


class StubLLM:
    model = "stub"

    def __init__(self, reply="", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    async def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        if self.error:
            raise self.error
        return LLMResult(
            text=self.reply,
            model=self.model,
            usage=Usage(prompt_tokens=123, completion_tokens=45, cached_tokens=6),
        )


class StubSession:
    """The AsyncSession calls of the pipeline. Tests run without Docker."""

    def __init__(self):
        self.rows = {}
        self.commits = 0
        self.rollbacks = 0

    def add(self, row):
        self.rows[row.id] = row

    async def get(self, _model, row_id):
        return self.rows.get(row_id)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, row):
        row.created_at = row.created_at or datetime.now(UTC)


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    path = tmp_path / "uploads"
    monkeypatch.setattr(settings, "upload_dir", str(path))
    monkeypatch.setattr(settings, "document_extraction_thinking", False)
    # Vision-path tests must not depend on a local Tesseract. OCR tests opt in.
    monkeypatch.setattr(settings, "ocr_enabled", False)
    return path


@pytest.fixture
def use_llm(monkeypatch):
    def install(reply=None, error=None):
        text = json.dumps(golden_reply() if reply is None else reply)
        stub = StubLLM(text, error)
        monkeypatch.setattr(extract_module, "get_llm_client", lambda: stub)
        return stub

    return install


@pytest.fixture
def session():
    return StubSession()


USER = SimpleNamespace(id=uuid4())


def scanned_pdf(pages=2) -> bytes:
    """Build a PDF with only drawings on its pages, so it has no text layer."""
    pdf = pymupdf.open()
    for _ in range(pages):
        page = pdf.new_page(width=595, height=842)
        page.draw_rect(pymupdf.Rect(50, 50, 300, 200), fill=(0, 0, 0))
    return pdf.tobytes()


def photo(output="png", width=40, height=20, colorspace=pymupdf.csRGB) -> bytes:
    pixmap = pymupdf.Pixmap(colorspace, pymupdf.IRect(0, 0, width, height), False)
    pixmap.clear_with(128)
    return pixmap.tobytes(output)


def image_parts(stub):
    return [
        part
        for part in stub.calls[0]["messages"][1]["content"]
        if part["type"] == "image_url"
    ]


def decoded_images(stub):
    prefix = "data:image/png;base64,"
    urls = [part["image_url"]["url"] for part in image_parts(stub)]
    assert all(url.startswith(prefix) for url in urls)
    return [base64.b64decode(url.removeprefix(prefix)) for url in urls]


async def run_pipeline(session, data, mime_type=PDF):
    document = await store_upload(session, USER, "brief", mime_type, data)
    return await process_document(session, document.id)


async def test_golden_pdf_ends_ready_with_five_recommendations(session, use_llm):
    stub = use_llm()
    document = await run_pipeline(session, SAMPLE_PDF.read_bytes())

    assert document.status == "ready"
    assert document.kind == "discharge_letter"
    assert document.error is None
    assert len(document.extracted["documented_recommendations"]) == 5
    assert document.extracted["confidence_note"] is None
    assert document.extracted["patient"]["name"] == "Anna Berger"

    response = DocumentResponse.model_validate(document)
    assert response.extracted.kind == "discharge_letter"
    assert response.status == "ready"

    call = stub.calls[0]
    assert call["thinking"] is False
    assert call["response_format"]["json_schema"]["name"] == "document_extraction"
    content = call["messages"][1]["content"]
    assert isinstance(content, str)
    assert "Anna Berger" in content
    assert "Aufnahmediagnosen und medizinische Vorgeschichte" not in content
    assert "Zusammenfassende Beurteilung" not in content
    for item in EXPECTED["recommendations"]:
        assert _normalize(item["quote"]) in _normalize(content)


def test_extraction_thinking_defaults_off_and_reads_environment(monkeypatch):
    monkeypatch.delenv("DOCUMENT_EXTRACTION_THINKING", raising=False)
    assert Settings(_env_file=None).document_extraction_thinking is False
    monkeypatch.setenv("DOCUMENT_EXTRACTION_THINKING", "true")
    assert Settings(_env_file=None).document_extraction_thinking is True


async def test_text_thinking_setting_overrides_chat_setting(use_llm, monkeypatch):
    stub = use_llm()
    monkeypatch.setattr(settings, "document_extraction_thinking", True)
    monkeypatch.setattr(settings, "llm_enable_thinking", False)
    await extract(["Dokumenttext"], [photo()])
    assert stub.calls[0]["thinking"] is True
    assert isinstance(stub.calls[0]["messages"][1]["content"], str)


async def test_text_ignores_images_and_chat_thinking(use_llm, monkeypatch):
    stub = use_llm()
    monkeypatch.setattr(settings, "llm_enable_thinking", True)
    await extract(["Dokumenttext"], [photo()])
    assert stub.calls[0]["thinking"] is False
    assert isinstance(stub.calls[0]["messages"][1]["content"], str)


def test_section_selection_preserves_page_numbers_and_nested_sections():
    content = _text_content([
        "Klinik\n1. Patientendaten\nName: Anna Berger\n"
        "2. Diagnosen\nNicht senden\n3. Empfehlungen\n3.1 Betreuung\nZitat beginnt\n",
        "und endet hier.\n4. Laborwerte\nNicht senden\n",
        "5. Termine\nKontrolle morgen\n",
    ])
    assert "Name: Anna Berger" in content
    assert "3.1 Betreuung\nZitat beginnt" in content
    assert "--- Seite 2 ---\nund endet hier." in content
    assert "--- Seite 3 ---\n5. Termine" in content
    assert "Nicht senden" not in content


@pytest.mark.parametrize(
    "heading", ["Empfehlungen", "Hinweise", "Pflege", "Entlassung", "Termine"]
)
def test_unnumbered_sections_are_selected(heading):
    content = _text_content([
        f"Klinik\nDiagnosen:\nNicht senden\n{heading}:\nOriginalzitat\n"
        "Laborwerte:\nAuch nicht senden\n"
    ])
    assert "Klinik" in content
    assert "Originalzitat" in content
    assert "Nicht senden" not in content
    assert "Auch nicht senden" not in content


def test_section_selection_falls_back_without_relevant_headings():
    pages = ["Klinik\n1. Patientendaten\nName\n2. Befund\nVollständiger Text", "Rest"]
    content = _text_content(pages)
    assert all(page in content for page in pages)


def test_section_selection_preserves_patient_header():
    content = _text_content([
        "Entlassungsbrief\nKlinik\nPatient:\nAnna Berger\n"
        "Diagnosen:\nNicht senden\nEmpfehlungen:\nPflegegeld prüfen\n"
    ])
    assert "Patient:\nAnna Berger" in content
    assert "Nicht senden" not in content


async def test_extraction_logs_duration_and_tokens(use_llm, monkeypatch, caplog):
    use_llm()
    clock = iter([10.0, 12.5])
    monkeypatch.setattr(extract_module, "perf_counter", lambda: next(clock))
    with caplog.at_level("INFO", logger=extract_module.__name__):
        await extract(["Vertraulicher Dokumenttext"], None)
    assert "duration_seconds=2.500" in caplog.text
    assert "prompt_tokens=123 completion_tokens=45 cached_tokens=6" in caplog.text
    assert "Vertraulicher Dokumenttext" not in caplog.text


async def test_failed_extraction_logs_duration(use_llm, monkeypatch, caplog):
    use_llm(error=LLMError("timeout", "Zeitüberschreitung"))
    clock = iter([10.0, 13.0])
    monkeypatch.setattr(extract_module, "perf_counter", lambda: next(clock))
    with caplog.at_level("INFO", logger=extract_module.__name__):
        with pytest.raises(LLMError):
            await extract(["Vertraulicher Dokumenttext"], None)
    assert "duration_seconds=3.000" in caplog.text
    assert "status=failed prompt_tokens=None" in caplog.text
    assert "Vertraulicher Dokumenttext" not in caplog.text


def test_response_schema_is_strict_and_requires_every_field():
    schema = DocumentExtraction.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    for definition in schema["$defs"].values():
        assert definition["additionalProperties"] is False
        assert set(definition["required"]) == set(definition["properties"])


async def test_quote_not_in_pdf_is_dropped_and_noted(session, use_llm):
    reply = golden_reply()
    reply["confidence_note"] = "Seite 2 ist unscharf."
    reply["documented_recommendations"][0]["quote"] = "Sie brauchen eine Reha."
    reply["documented_recommendations"].append(
        {"topic": "other", "quote": "   ", "section": None}
    )
    use_llm(reply)

    document = await run_pipeline(session, SAMPLE_PDF.read_bytes())

    assert document.status == "ready"
    quotes = [r["quote"] for r in document.extracted["documented_recommendations"]]
    assert len(quotes) == 4
    assert "Sie brauchen eine Reha." not in quotes
    note = document.extracted["confidence_note"]
    assert note.startswith("Seite 2 ist unscharf.")
    assert "Empfehlungen: 2" in note


async def test_other_quote_fields_are_checked_too(use_llm):
    reply = golden_reply()
    reply["follow_up_appointments"][0]["quote"] = "Erfundener Termin"
    reply["warnings_in_document"][0] = "Erfundene Warnung"
    use_llm(reply)

    extraction = await extract(["Termin steht nicht im Text."], None)

    assert extraction.follow_up_appointments == []
    assert extraction.warnings_in_document == []
    assert "Termine: 1" in extraction.confidence_note
    assert "Warnhinweise: 1" in extraction.confidence_note


async def test_quote_matches_across_line_and_page_breaks(use_llm):
    reply = golden_reply()
    reply["documented_recommendations"] = [
        {"topic": "other", "quote": "Ende von Seite eins. Anfang", "section": None}
    ]
    reply["follow_up_appointments"] = []
    reply["warnings_in_document"] = []
    use_llm(reply)

    pages = ["Ende von\nSeite   eins.\n", "Anfang von Seite 2"]
    extraction = await extract(pages, None)

    assert len(extraction.documented_recommendations) == 1
    assert extraction.confidence_note is None


def test_normalize_undoes_ligatures_and_non_breaking_spaces():
    assert _normalize("Pﬂege  und\nBetreuung") == "Pflege und Betreuung"


async def test_scanned_pdf_sends_images_at_150_dpi(session, use_llm):
    stub = use_llm()
    document = await run_pipeline(session, scanned_pdf(pages=2))

    assert document.status == "ready"
    assert stub.calls[0]["thinking"] is True
    images = decoded_images(stub)
    assert len(images) == 2
    assert all(image.startswith(PNG_SIGNATURE) for image in images)
    # A 595 pt wide page at 150 dpi: 595 / 72 * 150.
    assert pymupdf.Pixmap(images[0]).width == pytest.approx(1240, abs=1)
    # Images have no text to check, so the quotes stay and the note says so.
    assert len(document.extracted["documented_recommendations"]) == 5
    assert "nicht automatisch" in document.extracted["confidence_note"]


@pytest.mark.parametrize(
    ("mime_type", "output"), [("image/png", "png"), ("image/jpeg", "jpeg")]
)
async def test_photo_is_sent_as_png(session, use_llm, mime_type, output):
    stub = use_llm()
    document = await run_pipeline(session, photo(output), mime_type)

    assert document.status == "ready"
    assert document.mime_type == mime_type
    assert stub.calls[0]["thinking"] is True
    image = decoded_images(stub)[0]
    assert image.startswith(PNG_SIGNATURE)
    assert pymupdf.Pixmap(image).width == 40


def test_cmyk_jpeg_becomes_png():
    data = photo("jpeg", colorspace=pymupdf.csCMYK)
    _, images = load_pages(data, "image/jpeg")
    assert images[0].startswith(PNG_SIGNATURE)


def test_large_photo_is_scaled_down():
    data = photo(width=MAX_PHOTO_EDGE_PX * 2 + 2, height=100)
    _, images = load_pages(data, "image/png")
    assert pymupdf.Pixmap(images[0]).width <= MAX_PHOTO_EDGE_PX


async def test_store_upload_saves_the_file_under_its_id(session, upload_dir):
    data = SAMPLE_PDF.read_bytes()
    document = await store_upload(session, USER, "../../brief.pdf", PDF, data)

    path = upload_dir / str(document.id)
    assert path.read_bytes() == data
    assert document.storage_path == str(path)
    assert document.status == "processing"
    assert document.user_id == USER.id
    assert [item.name for item in upload_dir.iterdir()] == [str(document.id)]
    assert session.commits == 1


@pytest.mark.parametrize(
    ("mime_type", "data", "code"),
    [
        ("text/plain", b"hallo", "unsupported_type"),
        (PDF, b"", "empty_file"),
    ],
)
async def test_store_upload_rejects_bad_files(
    session, upload_dir, mime_type, data, code
):
    with pytest.raises(DocumentError) as caught:
        await store_upload(session, USER, "datei", mime_type, data)
    assert caught.value.code == code
    assert not upload_dir.exists()
    assert session.rows == {}


async def test_store_upload_rejects_a_file_over_the_limit(
    session, upload_dir, monkeypatch
):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    with pytest.raises(DocumentError) as caught:
        await store_upload(session, USER, "gross", PDF, b"x" * (1024 * 1024 + 1))
    assert caught.value.code == "file_too_large"
    assert "1 MB" in caught.value.message
    assert not upload_dir.exists()


async def test_store_upload_write_failure_rolls_back(session, upload_dir):
    upload_dir.write_text("a file where the directory should be")
    with pytest.raises(DocumentError) as caught:
        await store_upload(session, USER, "brief", PDF, b"data")
    assert caught.value.code == "storage_failed"
    assert session.rollbacks == 1


async def stored_row(session, mime_type=PDF, data=b"data"):
    document = await store_upload(session, USER, "brief", PDF, data)
    document.mime_type = mime_type
    return document


async def test_unsupported_mime_type_fails_cleanly(session, use_llm):
    stub = use_llm()
    document = await stored_row(session, mime_type="application/zip")

    result = await process_document(session, document.id)

    assert result.status == "failed"
    assert result.extracted is None
    assert result.kind is None
    assert "Dateityp" in result.error
    assert stub.calls == []
    assert DocumentResponse.model_validate(result).status == "failed"


async def test_oversized_stored_file_fails_cleanly(session, use_llm, monkeypatch):
    stub = use_llm()
    document = await stored_row(session, data=b"x" * (1024 * 1024 + 1))
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    result = await process_document(session, document.id)

    assert result.status == "failed"
    assert "zu groß" in result.error
    assert stub.calls == []


@pytest.mark.parametrize(
    ("mime_type", "data"), [(PDF, b"not a pdf"), ("image/png", b"not a png")]
)
async def test_damaged_file_fails_cleanly(session, use_llm, mime_type, data):
    use_llm()
    result = await run_pipeline(session, data, mime_type)
    assert result.status == "failed"
    assert "nicht gelesen" in result.error


async def test_password_protected_pdf_fails_cleanly(session, use_llm):
    use_llm()
    pdf = pymupdf.open()
    pdf.new_page().insert_text((50, 50), "Geheim")
    data = pdf.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="a", owner_pw="b"
    )
    result = await run_pipeline(session, data)
    assert result.status == "failed"
    assert "passwortgeschützt" in result.error


async def test_missing_stored_file_fails_cleanly(session, use_llm, upload_dir):
    use_llm()
    document = await stored_row(session)
    (upload_dir / str(document.id)).unlink()

    result = await process_document(session, document.id)

    assert result.status == "failed"
    assert "nicht mehr vorhanden" in result.error


async def test_llm_error_message_reaches_the_document(session, use_llm):
    use_llm(error=LLMError("timeout", "Der Dienst antwortet gerade nicht."))
    result = await run_pipeline(session, SAMPLE_PDF.read_bytes())
    assert result.status == "failed"
    assert result.error == "Der Dienst antwortet gerade nicht."


@pytest.mark.parametrize(
    "reply", ["Kein JSON", {"kind": "discharge_letter"}, {"kind": "unknown"}]
)
async def test_invalid_model_reply_fails_cleanly(session, use_llm, reply):
    use_llm(reply)
    result = await run_pipeline(session, SAMPLE_PDF.read_bytes())
    assert result.status == "failed"
    assert result.error.startswith("Das Dokument konnte nicht ausgewertet")


async def test_unexpected_error_does_not_leak_its_text(session, use_llm):
    use_llm(error=RuntimeError("secret internals"))
    result = await run_pipeline(session, SAMPLE_PDF.read_bytes())
    assert result.status == "failed"
    assert "secret internals" not in result.error


async def test_retry_clears_an_earlier_error(session, use_llm):
    use_llm(error=LLMError("timeout", "Der Dienst antwortet gerade nicht."))
    failed = await run_pipeline(session, SAMPLE_PDF.read_bytes())
    assert failed.status == "failed"

    use_llm()
    result = await process_document(session, failed.id)

    assert result.status == "ready"
    assert result.error is None


async def test_blank_page_among_text_pages_is_noted(session, use_llm):
    use_llm()
    pdf = pymupdf.open(SAMPLE_PDF)
    pdf.new_page()
    result = await run_pipeline(session, pdf.tobytes())

    assert result.status == "ready"
    assert f"Seite {pdf.page_count}" in result.extracted["confidence_note"]


async def test_unknown_document_id_returns_none(session):
    assert await process_document(session, uuid4()) is None


async def test_extract_without_content_raises():
    with pytest.raises(DocumentError) as caught:
        await extract(["  \n"], None)
    assert caught.value.code == "no_content"


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="needs RUN_LIVE=1")
async def test_live_model_finds_the_expected_quotes():
    assert settings.llm_provider in ("eustella", "azure"), "needs a live provider"
    pages_text, _ = load_pages(SAMPLE_PDF.read_bytes(), PDF)

    started = perf_counter()
    extraction = await extract(pages_text, None)
    duration = perf_counter() - started
    print(f"Document extraction duration: {duration:.2f} s", flush=True)

    quotes = {
        _normalize(item.quote) for item in extraction.documented_recommendations
    }
    expected = [_normalize(item["quote"]) for item in EXPECTED["recommendations"]]
    found = [quote for quote in expected if quote in quotes]
    assert len(found) >= 4, f"found {len(found)} of 5: {found}"
    assert duration < 45, f"extraction took {duration:.2f} s (limit: 45 s)"


# --- OCR ---------------------------------------------------------------------

needs_tesseract = pytest.mark.skipif(
    _detect_tessdata("", "deu+eng") is None,
    reason="needs Tesseract language data for deu and eng",
)


@pytest.fixture
def ocr(monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_tessdata_dir", "")
    monkeypatch.setattr(settings, "ocr_languages", "deu+eng")


def image_only_pdf(source: bytes, pages: list[int] | None = None) -> bytes:
    """Render PDF pages to images and wrap them in a PDF without a text layer."""
    output = pymupdf.open()
    with pymupdf.open(stream=source, filetype="pdf") as pdf:
        for index, page in enumerate(pdf):
            if pages is not None and index not in pages:
                output.insert_pdf(pdf, from_page=index, to_page=index)
                continue
            # JPEG keeps the scan below the upload limit, like a real scanner.
            image = page.get_pixmap(dpi=200).tobytes("jpeg", jpg_quality=85)
            target = output.new_page(width=page.rect.width, height=page.rect.height)
            target.insert_image(target.rect, stream=image)
    return output.tobytes(garbage=3, deflate=True)


def test_fuzzy_check_keeps_near_verbatim_quotes_only_for_ocr():
    extraction = DocumentExtraction.model_validate(golden_reply())
    quote = extraction.documented_recommendations[0].quote
    # One OCR slip per word start: "Pflege" becomes "Pf1ege" and so on.
    garbled = quote.replace("e", "c", 1).replace("i", "l", 1)
    assert garbled != quote

    exact = _verify_quotes(extraction, garbled)
    assert quote not in [item.quote for item in exact.documented_recommendations]
    tolerant = _verify_quotes(extraction, garbled, ocr_text=garbled)
    assert quote in [item.quote for item in tolerant.documented_recommendations]
    unrelated = "Ganz anderer Text ohne Bezug."
    other = _verify_quotes(extraction, unrelated, ocr_text=unrelated)
    assert other.documented_recommendations == []


def test_fuzzy_check_never_tolerates_other_numbers_or_a_lost_negation():
    reply = golden_reply()
    reply["follow_up_appointments"] = [
        {"what": "Kontrolle", "when": None, "quote": "Kontrolle am 12.11.2026 um 9 Uhr"}
    ]
    reply["documented_recommendations"][0]["quote"] = (
        "Eine Rehabilitation ist nicht empfohlen"
    )
    extraction = DocumentExtraction.model_validate(reply)
    # "12" elsewhere in the text must not rescue the wrong date.
    ocr = (
        "Kontrolle am 19.11.2026 um 9 Uhr, Zimmer 12. "
        "Eine Rehabilitation ist empfohlen."
    )

    checked = _verify_quotes(extraction, ocr, ocr_text=ocr)
    assert checked.follow_up_appointments == []
    assert "nicht empfohlen" not in [
        item.quote for item in checked.documented_recommendations
    ]
    matching = ocr.replace("19.", "12.")
    same = _verify_quotes(extraction, matching, ocr_text=matching)
    assert len(same.follow_up_appointments) == 1


async def test_ocr_failure_falls_back_to_images(session, use_llm, ocr, monkeypatch):
    monkeypatch.setattr(pipeline_module, "_tessdata", lambda: "/no/tessdata")

    def broken(*args):
        raise RuntimeError("tesseract crashed")

    monkeypatch.setattr(pipeline_module, "ocr_pages", broken)
    stub = use_llm()
    document = await run_pipeline(session, scanned_pdf(pages=1))
    assert document.status == "ready"
    assert len(image_parts(stub)) == 1
    assert "nicht automatisch" in document.extracted["confidence_note"]


async def test_too_little_ocr_text_falls_back_to_images(
    session, use_llm, ocr, monkeypatch
):
    monkeypatch.setattr(pipeline_module, "_tessdata", lambda: "/no/tessdata")
    monkeypatch.setattr(
        pipeline_module, "ocr_pages", lambda data, mime, pages, folder: {1: "ab"}
    )
    stub = use_llm()
    await run_pipeline(session, scanned_pdf(pages=1))
    assert len(image_parts(stub)) == 1


def test_ocr_is_off_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ocr_enabled", False)
    assert pipeline_module._tessdata() is None


@needs_tesseract
async def test_scanned_letter_is_read_by_ocr_and_quotes_are_checked(
    session, use_llm, ocr
):
    stub = use_llm()
    document = await run_pipeline(session, image_only_pdf(SAMPLE_PDF.read_bytes()))

    assert document.status == "ready"
    content = stub.calls[0]["messages"][1]["content"]
    assert isinstance(content, str) and content.startswith("Dokumenttext:")
    assert "Texterkennung (OCR)" in document.extracted["confidence_note"]
    assert len(document.extracted["documented_recommendations"]) >= 4
    assert "nicht ausgewertet" not in document.extracted["confidence_note"]


@needs_tesseract
async def test_scanned_page_inside_a_text_pdf_is_read_by_ocr(session, use_llm, ocr):
    stub = use_llm()
    data = image_only_pdf(SAMPLE_PDF.read_bytes(), pages=[0])
    document = await run_pipeline(session, data)

    content = stub.calls[0]["messages"][1]["content"]
    assert "Anna" in content  # page 1 holds the patient header
    assert "nicht ausgewertet" not in (document.extracted["confidence_note"] or "")


@needs_tesseract
async def test_photo_of_a_letter_is_read_by_ocr(session, use_llm, ocr):
    with pymupdf.open(SAMPLE_PDF) as pdf:
        data = pdf[0].get_pixmap(dpi=200).tobytes("png")
    stub = use_llm()
    document = await run_pipeline(session, data, "image/png")

    assert document.status == "ready"
    content = stub.calls[0]["messages"][1]["content"]
    assert isinstance(content, str) and "Anna" in content

import json
from io import BytesIO

import pytest
from pypdf import PdfReader
from pypdf.generic import BooleanObject

from app.forms import registry
from app.forms.dump_fields import dump, main, read_fields
from app.forms.fill import prepare

FORM_ID = "pva_pflegegeld"

# Anna Berger is the synthetic patient of the SV-Box discharge letter.
# The SVNr is invented for the demo.
ANNA = {
    "applicant.last_name": "Berger",
    "applicant.first_name": "Anna",
    "applicant.date_of_birth": "14.03.1948",
    "applicant.svnr": "1234 140348",
    "applicant.address.street": "Musterstraße",
    "applicant.address.house_number": "12",
    "applicant.address.zip": "1030",
    "applicant.address.city": "Wien",
    "applicant.address.country": "Österreich",
    "applicant.insurer": "ÖGK",
    "application.type": "zuerkennung",
    "hospital_stay.any": "Ja",
    "application.attachments": "Entlassungsbefund (Kopie)",
}
SOURCES = {
    "applicant.last_name": "document",
    "applicant.first_name": "document",
    "applicant.date_of_birth": "document",
    "applicant.address.street": "document",
    "applicant.address.house_number": "document",
    "applicant.address.zip": "document",
    "applicant.address.city": "document",
    "applicant.insurer": "profile",
    "hospital_stay.any": "document",
}
TEXT_FIELDS = {
    "Fam.Name": "Berger",
    "Vorname": "Anna",
    "Geburtsdatum": "14.03.1948",
    "VSNR_1": "1234 140348",
    "Adresse Straße": "Musterstraße",
    "Hausnummer, Stiege, Tür": "12",
    "PLZ": "1030",
    "Ort": "Wien",
    "Land": "Österreich",
    "Unterlagen": "Entlassungsbefund (Kopie)",
}


def _fields(pdf: bytes) -> dict:
    return PdfReader(BytesIO(pdf)).get_fields() or {}


def _widget_states(pdf: bytes, field_name: str) -> dict[str, str]:
    """Map each widget's export state to its current /AS appearance state."""
    states: dict[str, str] = {}
    for page in PdfReader(BytesIO(pdf)).pages:
        for ref in page.get("/Annots") or []:
            annot = ref.get_object()
            parent = annot.get("/Parent")
            owner = parent.get_object() if parent is not None else annot
            if owner.get("/T") != field_name:
                continue
            on = [s for s in annot["/AP"]["/N"] if s != "/Off"]
            states[on[0]] = str(annot.get("/AS"))
    return states


@pytest.fixture(scope="module")
def prepared():
    return prepare(FORM_ID, ANNA, SOURCES)


def test_text_values_are_in_the_pdf_fields(prepared):
    fields = _fields(prepared.pdf)
    for name, value in TEXT_FIELDS.items():
        assert fields[name].get("/V") == value, name


def test_checkbox_selects_the_matching_widget(prepared):
    fields = _fields(prepared.pdf)
    assert fields["Krankenhaus"]["/V"] == "/02"
    assert _widget_states(prepared.pdf, "Krankenhaus") == {"/01": "/Off", "/02": "/02"}
    assert fields["Antrag Pflg"]["/V"] == "/01"


def test_form_stays_editable_and_needs_appearances(prepared):
    reader = PdfReader(BytesIO(prepared.pdf))
    acroform = reader.trailer["/Root"]["/AcroForm"]
    assert acroform["/NeedAppearances"] == BooleanObject(True)
    original = _fields(registry.get_template(FORM_ID).pdf_path.read_bytes())
    assert set(_fields(prepared.pdf)) == set(original)


def test_filled_lists_label_value_and_source(prepared):
    filled = {item.key: item for item in prepared.filled}
    assert filled["applicant.last_name"].label == "Familienname"
    assert filled["applicant.last_name"].value == "Berger"
    assert filled["applicant.last_name"].source == "document"
    assert filled["applicant.svnr"].source == "conversation"
    assert filled["hospital_stay.any"].value == "ja"
    assert filled["application.type"].value == "Zuerkennung"


def test_unknown_key_is_reported(prepared):
    assert "applicant.insurer" in prepared.rejected
    assert "applicant.insurer" not in {item.key for item in prepared.filled}


def test_missing_lists_empty_self_filled_fields(prepared):
    missing = {spec.key for spec in prepared.missing}
    field_map = registry.get_field_map(FORM_ID)
    assert "applicant.phone" in missing
    assert "applicant.sex" in missing
    assert "application.date" in missing
    assert "applicant.svnr" not in missing
    assert not missing & {item.key for item in prepared.filled}
    assert all(field_map[key].filled_by in {"applicant", "lotse"} for key in missing)
    fields = _fields(prepared.pdf)
    for key in missing:
        assert not fields[field_map[key].field].get("/V"), key


def test_missing_follows_conditions_and_optional_flags(prepared):
    missing = {spec.key for spec in prepared.missing}
    # hospital_stay.any is "ja", so the stay details are missing.
    stay = {"hospital_stay.from", "hospital_stay.to", "hospital_stay.institution"}
    assert stay <= missing
    # No representative and no home visit contact were given.
    assert "representative.first_name" not in missing
    assert "contact_person.name" not in missing
    # Optional fields never count as missing.
    assert "applicant.title" not in missing
    assert "applicant.email" not in missing


def test_to_be_filled_by_others_lists_doctor_fields(prepared):
    others = {spec.key: spec for spec in prepared.to_be_filled_by_others}
    assert others
    field_map = registry.get_field_map(FORM_ID)
    assert all(field_map[key].filled_by in {"doctor", "office"} for key in others)
    assert "health.conditions" in others
    assert others["health.conditions"].hint


def test_doctor_field_is_never_written():
    result = prepare(FORM_ID, {"health.conditions": "Beispieltext"})
    assert "health.conditions" in result.rejected
    assert not _fields(result.pdf)["Leiden"].get("/V")


def test_invalid_option_and_too_long_value_are_rejected():
    result = prepare(
        FORM_ID,
        {
            "hospital_stay.any": "vielleicht",
            "applicant.address.zip": "1030 Wien Landstraße",
        },
    )
    assert "allowed" in result.rejected["hospital_stay.any"]
    assert "6 characters" in result.rejected["applicant.address.zip"]
    assert result.filled == []


def test_empty_values_are_skipped():
    result = prepare(FORM_ID, {"applicant.phone": "  ", "applicant.first_name": "Anna"})
    assert [item.key for item in result.filled] == ["applicant.first_name"]
    assert "applicant.phone" in {spec.key for spec in result.missing}
    assert result.rejected == {}


def test_unknown_source_raises():
    with pytest.raises(ValueError):
        prepare(
            FORM_ID, {"applicant.first_name": "Anna"}, {"applicant.first_name": "llm"}
        )


def test_every_field_map_matches_its_pdf():
    checked = 0
    for template in registry.list_templates():
        assert template.pdf_path.is_file(), template.file
        if not registry.has_field_map(template.id):
            continue
        field_map = registry.get_field_map(template.id)
        pdf_fields = {f["name"]: f for f in read_fields(template.pdf_path)}
        for key, mapping in field_map.items():
            assert mapping.field in pdf_fields, f"{key}: {mapping.field}"
            if mapping.options is not None:
                states = {o["state"] for o in pdf_fields[mapping.field]["options"]}
                assert set(mapping.options.values()) - {"/Off"} <= states, key
            if mapping.when is not None:
                assert mapping.when.key in field_map, key
            for source in mapping.copy_from or []:
                assert source in field_map, f"{key}: copy_from {source}"
            if mapping.copy_from:
                assert mapping.optional, f"{key}: derived fields must be optional"
        checked += 1
    assert checked >= 1


def test_registry_lists_forms_and_reports_errors():
    ids = {template.id for template in registry.list_templates()}
    assert {"pva_pflegegeld", "kur_reha", "fahrtkosten_wien"} <= ids
    pva = registry.get_template(FORM_ID)
    assert (pva.title, pva.issuer, pva.leistung_ids) == (
        "Antrag auf Pflegegeld",
        "PVA",
        ["pflegegeld"],
    )
    with pytest.raises(registry.UnknownFormError):
        prepare("no_such_form", {})
    # Every registered form can be filled.
    assert all(registry.has_field_map(form_id) for form_id in ids)


def test_dump_fields_lists_fields_with_pages_labels_and_options(capsys):
    pdf_path = registry.get_template(FORM_ID).pdf_path
    fields = {field["name"]: field for field in dump(pdf_path)}
    assert fields["VSNR_1"]["pages"] == [1, 2, 3, 4]
    assert fields["VSNR_1"]["label"] == "Versicherungsnummer"
    options = {o["state"]: o["label"] for o in fields["Krankenhaus"]["options"]}
    assert options["/01"] == "nein"
    assert options["/02"].startswith("ja")
    assert main(["does/not/exist.pdf"]) == 1
    assert "File not found" in capsys.readouterr().err


# --- Kur- und Reha-Antrag ---

KUR = "kur_reha"
ANNA_KUR = {
    "insurer.name": "ÖGK – Österreichische Gesundheitskasse",
    "applicant.svnr": "1234140348",
    "applicant.last_name": "Berger",
    "applicant.first_name": "Anna",
    "applicant.year_of_birth": "1948",
    "applicant.sex": "weiblich",
    "applicant.address.full": "Musterstraße 12, 1030 Wien",
    "benefits.pension": "ja",
    "benefits.pension_insurer": "PVA",
    "care_allowance.any": "nein",
}


def kur_fields(pdf: bytes) -> dict:
    return PdfReader(BytesIO(pdf)).get_fields()


def test_kur_reha_fills_page_one_and_the_patient_line_on_page_two():
    prepared = prepare(KUR, ANNA_KUR)
    fields = kur_fields(prepared.pdf)
    assert fields["zuständiger SV-träger"]["/V"] == ANNA_KUR["insurer.name"]
    assert fields["VSNR_1"]["/V"] == "1234140348"
    assert fields["Familienname"]["/V"] == "Berger"
    assert fields["Geburtsjahr"]["/V"] == "1948"
    assert fields["Geschlecht"]["/V"] == "/w"
    assert fields["Pensionsversicherung"]["/V"] == "/j"
    assert fields["Pflegegeld"]["/V"] == "/n"
    assert prepared.rejected == {}


def test_kur_reha_derives_the_name_line_and_the_insured_address():
    prepared = prepare(KUR, ANNA_KUR)
    filled = {field.key: field.value for field in prepared.filled}
    assert filled["applicant.full_name"] == "Berger Anna"
    assert filled["insured.address"] == "Musterstraße 12, 1030 Wien"
    fields = kur_fields(prepared.pdf)
    assert fields["Patient(in)"]["/V"] == "Berger Anna"
    assert fields["Anschrift"]["/V"] == "Musterstraße 12, 1030 Wien"


def test_kur_reha_explicit_value_wins_over_the_derived_one():
    prepared = prepare(KUR, {**ANNA_KUR, "applicant.full_name": "Anna Berger"})
    filled = {field.key: field.value for field in prepared.filled}
    assert filled["applicant.full_name"] == "Anna Berger"


def test_kur_reha_leaves_the_medical_statement_to_the_doctor():
    prepared = prepare(KUR, {**ANNA_KUR, "doctor.diagnosis": "Mammakarzinom"})
    assert prepared.rejected == {
        "doctor.diagnosis": "only the doctor fills this field"
    }
    fields = kur_fields(prepared.pdf)
    assert not fields["Antragsrelevante Diagnose"].get("/V")
    others = {spec.key for spec in prepared.to_be_filled_by_others}
    expected = {"doctor.diagnosis", "doctor.proposed_measure", "doctor.justification"}
    assert expected <= others
    assert all(key.startswith("doctor.") for key in others)


def test_kur_reha_missing_skips_relative_questions_for_a_self_insured_patient():
    prepared = prepare(KUR, ANNA_KUR)
    missing = {spec.key for spec in prepared.missing}
    expected = {"insured.marital_status", "previous_stays.any", "application.date"}
    assert expected <= missing
    assert not any(key.startswith("relative.") for key in missing)
    assert "applicant.full_name" not in missing
    assert "benefits.pension_insurer" not in missing


def test_kur_reha_asks_relative_questions_for_a_co_insured_patient():
    prepared = prepare(KUR, {**ANNA_KUR, "insured.full_name": "Berger Maria"})
    missing = {spec.key for spec in prepared.missing}
    assert {"insured.svnr", "relative.relationship", "relative.pension.any"} <= missing


def test_every_form_belongs_to_a_leistung_that_links_it():
    leistungen = {
        record["id"]: record
        for record in json.loads((registry.SEED_DIR / "leistungen.json").read_text())
    }
    for template in registry.list_templates():
        for leistung_id in template.leistung_ids:
            assert template.id in leistungen[leistung_id]["form_ids"], leistung_id


def test_fahrtkosten_fills_text_and_radio_fields():
    result = prepare(
        "fahrtkosten_wien",
        {
            "applicant.full_name": "Berger Anna",
            "applicant.svnr": "1234140348",
            "applicant.address.full": "Musterstraße 12, 1030 Wien",
            "treatment.type": "Strahlentherapie",
            "transport.mode": "taxi",
            "companion.any": "ja",
        },
    )
    fields = _fields(result.pdf)
    assert fields["Patient/in"]["/V"] == "Berger Anna"
    assert fields["Art der Behandlung"]["/V"] == "Strahlentherapie"
    assert fields["Transportmittel"]["/V"] == "/Auswahl2"
    assert fields["Begleitperson"]["/V"] == "/Auswahl1"
    missing = {spec.key for spec in result.missing}
    assert {"companion.reason", "payment.iban", "treatment.provider"} <= missing
    assert "insured.svnr" not in missing
    assert result.rejected == {}

import json
import logging
from pathlib import Path

import pytest

from app.guardrails import build_handover_summary, check, load_contacts
from app.guardrails.red_flags import normalize_text

EVAL_DIR = Path(__file__).resolve().parents[2] / "eval"


@pytest.mark.parametrize("filename", ["red_flags.jsonl", "red_flags_holdout.jsonl"])
def test_red_flag_eval(filename):
    cases = [
        json.loads(line)
        for line in (EVAL_DIR / filename).read_text(encoding="utf-8").splitlines()
        if line
    ]
    positives = [case for case in cases if case["expected"]]
    negatives = [case for case in cases if not case["expected"]]
    assert positives and negatives
    missed = [case["id"] for case in positives if not check(case["text"]).hit]
    false_positives = [case["id"] for case in negatives if check(case["text"]).hit]
    recall = 1 - len(missed) / len(positives)
    false_positive_rate = len(false_positives) / len(negatives)
    print(
        f"{filename}: recall {len(positives) - len(missed)}/{len(positives)} "
        f"({recall:.0%}); false-positive rate "
        f"{len(false_positives)}/{len(negatives)} ({false_positive_rate:.0%})"
    )
    assert recall == 1, f"Missed emergencies: {missed}"
    assert false_positive_rate <= 0.2, f"False positives: {false_positives}"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  Ä Ö Ü ß!\n", "ae oe ue s"),
        ("Atemnott!!!", "atemnot"),
        ("ATTTEMNOOOT", "atemnot"),
        ("Ich\tkrieg  keine Luft!", "ich krieg keine luft"),
        ("I can’t breathe.", "i cant breathe"),
        ("A\u0308rztin", "aerztin"),
        ("", ""),
    ],
)
def test_normalization(text, expected):
    assert normalize_text(text) == expected


@pytest.mark.parametrize(
    ("text", "category", "reason_code", "contacts"),
    [
        (
            "Meine Mutter hat plötzlich starke Atemnot.",
            "breathing",
            "emergency",
            {"rettung_144", "euronotruf_112"},
        ),
        (
            "Ich will nicht mehr leben.",
            "suicidal",
            "emergency",
            {"telefonseelsorge_142", "rettung_144"},
        ),
        (
            "Mein Kind hat Putzmittel getrunken.",
            "poisoning",
            "emergency",
            {"vergiftungsinformation_viz", "rettung_144"},
        ),
        (
            "Mein Partner schlägt mich.",
            "violence",
            "social_crisis",
            {"telefonseelsorge_142"},
        ),
        (
            "Ich bin obdachlos.",
            "homelessness",
            "social_crisis",
            {"telefonseelsorge_142"},
        ),
        (
            "Ich habe kein Geld für Essen.",
            "financial_crisis",
            "social_crisis",
            {"telefonseelsorge_142"},
        ),
    ],
)
def test_categories_and_contacts(text, category, reason_code, contacts):
    result = check(text)
    assert result.hit
    assert result.reason_code == reason_code
    assert category in result.categories
    assert result.matched
    assert set(result.contact_ids) == contacts
    seeded = {contact["id"]: contact for contact in load_contacts()}
    for contact_id in result.contact_ids:
        assert reason_code in seeded[contact_id]["reason_codes"]


@pytest.mark.parametrize(
    "text",
    [
        "Ich kann nicht atmen.",
        "I cannot breathe!",
        "I can't breathe.",
        "Ich kriege keine Luft.",
        "Meine Mutter hat ATTTEMNOOOT!",
        "Ich habe eine Überdosis genommen.",
        "My child drank bleach.",
        "My daughter wants to kill herself.",
        "Ich habe starke Blutungen.",
        "My partner is hitting me.",
        "I am homeless.",
        "I have nowhere to sleep.",
        "I have no money for food.",
    ],
)
def test_additional_current_flags(text):
    assert check(text).hit


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Mein Vater atmet schwer.", "breathing"),
        ("Das Kind schnappt nach Luft!", "breathing"),
        ("Sie hat blaue Lippen.", "breathing"),
        ("Mein Bruder ist blau im Gesicht.", "breathing"),
        ("Meine Tante röchelt laut.", "breathing"),
        ("My sister is struggling to breathe.", "breathing"),
        ("My child is turning blue!", "breathing"),
        ("His lips are blue.", "breathing"),
        ("Mein Bruder redet seit eben verwaschen.", "stroke"),
        ("Meine Schwester lallt auf einmal.", "stroke"),
        ("Papa kann nicht mehr sprechen.", "stroke"),
        ("Der linke Mundwinkel hängt plötzlich.", "stroke"),
        ("Mein Arm ist plötzlich taub.", "stroke"),
        ("Ich kann den rechten Arm nicht mehr heben.", "stroke"),
        ("Seine rechte Seite ist plötzlich schwach.", "stroke"),
        ("My mother's speech is suddenly slurred.", "stroke"),
        ("He is slurring his words.", "stroke"),
        ("The left side of her face is drooping.", "stroke"),
        ("His right arm is suddenly numb.", "stroke"),
        ("She has sudden weakness on one side.", "stroke"),
        ("I cannot raise my left arm.", "stroke"),
        ("My brother is unable to speak.", "stroke"),
        ("Mein Herz rast mit Brennen in der Brust.", "chest_pain"),
        ("Meine Brust brennt während mein Herz rast.", "chest_pain"),
        ("Mein Herz rast mit Todesangst.", "chest_pain"),
        ("Ich sterbe, bitte helfen Sie mir!", "chest_pain"),
        ("I'm dying, please help me!", "chest_pain"),
        ("I think I am having a heart attack.", "chest_pain"),
        ("Meine Schwester hat keine Wohnung mehr.", "homelessness"),
        ("Ich schlafe nachts auf der Straße.", "homelessness"),
        ("Meine Tante schläft draußen.", "homelessness"),
        ("Wir wurden gestern delogiert.", "homelessness"),
        ("My uncle is homeless.", "homelessness"),
    ],
)
def test_broadened_pattern_families(text, category):
    result = check(text)
    assert result.hit
    assert category in result.categories
    assert result.reason_code == (
        "social_crisis" if category == "homelessness" else "emergency"
    )


STEM_CASES = [
    ("Mama bekommt kaum noch Luft.", "breathing"),
    ("Er ringt nach Atem.", "breathing"),
    ("Die Kleine bekommt nur schlecht Luft.", "breathing"),
    ("Er schnappt verzweifelt und bekommt keine Luft.", "breathing"),
    ("Ihre Atmung macht mir große Angst.", "breathing"),
    ("Sein Gesicht färbt sich langsam blau.", "breathing"),
    ("Hilfe, mein Bruder erstickt!", "breathing"),
    ("Sie spuckt Blut.", "bleeding"),
    ("Sehr viel Blut liegt neben ihm.", "bleeding"),
    ("Das Bluten hört nicht auf.", "bleeding"),
    ("Er hat die Pulsadern aufgeschnitten.", "bleeding"),
    ("My aunt is coughing up blood.", "bleeding"),
    ("Die Nachbarin liegt ohnmächtig im Flur.", "unconsciousness"),
    ("Er hatte eine Ohnmacht.", "unconsciousness"),
    ("Meine Freundin ist einfach umgekippt.", "unconsciousness"),
    ("Der Mann reagiert nicht auf meine Stimme.", "unconsciousness"),
    ("Meine Schwester wacht nicht auf.", "unconsciousness"),
    ("Our neighbour is unconscious on the floor.", "unconsciousness"),
    ("Er hat einen Krampfanfall.", "seizure"),
    ("Das Baby krampft am ganzen Körper.", "seizure"),
    ("My cousin is having a seizure.", "seizure"),
    ("She has convulsions.", "seizure"),
    ("Sein halbes Gesicht ist gelähmt.", "stroke"),
    ("Eine Lähmung betrifft ihre linke Hand.", "stroke"),
    ("Völlig verwaschen kommen ihre Worte heraus.", "stroke"),
    ("Er lallt beim Antworten.", "stroke"),
    ("Ein Mundwinkel hängt bei meiner Oma herunter.", "stroke"),
    ("My sister's face looks paralysed.", "stroke"),
    ("Er hat Rattengift gegessen.", "poisoning"),
    ("Das Kind hat Schneckengift im Mund.", "poisoning"),
    ("Ich habe Reiniger aus der Flasche getrunken.", "poisoning"),
    ("Sie hat Medikamente aus dem Schrank geschluckt.", "poisoning"),
    ("Er hat geschluckt, was in der Chemieflasche war.", "poisoning"),
    ("He ate something poisonous.", "poisoning"),
    ("Sie will nicht mehr aufwachen.", "suicidal"),
    ("Nicht mehr leben ist sein einziger Wunsch.", "suicidal"),
    ("Am liebsten würde ich mich umbringen.", "suicidal"),
    ("Ich denke nur daran, sterben zu wollen.", "suicidal"),
    ("Sie wollen heute sterben.", "suicidal"),
    ("Ich habe mir die Pulsadern aufgeschnitten.", "suicidal"),
    ("I keep thinking about suicide.", "suicidal"),
    ("I might kill myself this evening.", "suicidal"),
    ("Ich werde bedroht und habe Angst um mein Leben.", "violence"),
    ("Der Nachbar schlägt seine Tochter.", "violence"),
    ("Zu Hause erlebe ich Gewalt.", "violence"),
    ("Ich habe Angst um mein Leben.", "violence"),
    ("My sister was beaten by her partner.", "violence"),
    ("Our family is being threatened.", "violence"),
    ("Er hat uns aus der Wohnung geworfen.", "homelessness"),
    ("Wir mussten aus der Wohnung raus.", "homelessness"),
    ("Wir sind von Delogierung betroffen.", "homelessness"),
    ("Meine Kinder sitzen auf der Straße.", "homelessness"),
    ("Unsere Familie ist wohnungslos geworden.", "homelessness"),
    ("My family is becoming homeless.", "homelessness"),
    ("Wir sind völlig mittellos.", "financial_crisis"),
    ("Ich habe kein Geld mehr für Lebensmittel.", "financial_crisis"),
    ("Meine Brustschmerzen werden unerträglich.", "chest_pain"),
    ("He may be having a heart attack.", "chest_pain"),
]


@pytest.mark.parametrize(("text", "category"), STEM_CASES)
def test_stems_detect_new_phrasings(text, category):
    result = check(text)
    assert result.hit
    assert category in result.categories
    assert result.reason_code == (
        "social_crisis"
        if category in {"violence", "homelessness", "financial_crisis"}
        else "emergency"
    )
    assert result.matched
    assert result.contact_ids


def test_stem_cases_are_separate_from_eval_phrases():
    eval_phrases = {
        normalize_text(json.loads(line)["text"])
        for filename in ("red_flags.jsonl", "red_flags_holdout.jsonl")
        for line in (EVAL_DIR / filename).read_text(encoding="utf-8").splitlines()
        if line
    }
    assert len(STEM_CASES) >= 25
    assert all(normalize_text(text) not in eval_phrases for text, _ in STEM_CASES)


@pytest.mark.parametrize(
    "text",
    [
        "Vor drei Jahren hatte sie einen Krampfanfall. Wer bezahlt die Reha?",
        "Er hatte vor vier Monaten eine Ohnmacht. Welche Pflegegeldunterlagen fehlen?",
        "Sie war im Spital wegen einer Vergiftung. Wer zahlt die Reha?",
        "Vor zwei Jahren hatte sie eine Lähmung. Welche Hilfen kann sie beantragen?",
        "Mein Onkel hatte letzten Monat Atemnot. Wer bezahlt den Transport?",
        "Meine Tante war im Spital wegen Blutungen. Wie beantrage ich Pflegegeld?",
        "Vor sechs Monaten hatte ich einen Herzinfarkt. "
        "Welche Reha kann ich beantragen?",
        "My sister had a seizure last year. Which rehabilitation benefits apply?",
        "He was unconscious two months ago. Who pays for care?",
        "My brother had blood loss last month. Which insurance covers rehabilitation?",
        "Brauche ich für die Blutabnahme eine Überweisung von der Hausärztin?",
        "Wo reiche ich die Rechnung für den Rollstuhl ein?",
    ],
)
def test_administrative_negatives(text):
    assert not check(text).hit


@pytest.mark.parametrize(
    "text",
    [
        "Nach einem Herzinfarkt bekommt meine Mutter kaum Luft. Welche Reha hilft?",
        "Nach einem Schlaganfall ist mein Vater bewusstlos. Pflegegeld?",
        "Sie war im Spital und spuckt Blut. Wer zahlt die Reha?",
        "Vor Angst bekomme ich kaum Luft. Welche Hilfen gibt es?",
        "Vor zwei Jahren hatte er einen Krampfanfall, nun ist er bewusstlos. Reha?",
        "Ich arbeite in einer Beratungsstelle für Obdachlose und bin selbst obdachlos.",
        "Wer bezahlt die Behandlung? Ich habe Rattengift gegessen.",
    ],
)
def test_administrative_context_does_not_hide_stems(text):
    assert check(text).hit


@pytest.mark.parametrize(
    ("text", "category"),
    [
        (
            "Ich arbeite mit Atemnot in einer Beratungsstelle für Obdachlose.",
            "breathing",
        ),
        (
            "Ich arbeite bedroht in einer Einrichtung für Wohnungslose.",
            "violence",
        ),
        (
            "Ich arbeite obdachlos in einem Verein für Obdachlose.",
            "homelessness",
        ),
    ],
)
def test_staff_role_preserves_personal_flags(text, category):
    assert category in check(text).categories


@pytest.mark.parametrize(
    "text",
    [
        "Wie beantrage ich Pflegegeld für meine Mutter mit COPD?",
        "Mein Vater hatte vor zwei Jahren einen Schlaganfall. Wer zahlt den Badumbau?",
        "My father had a stroke last year. Who pays for care?",
        "Vor meiner Herz-OP hatte ich Brustschmerzen, jetzt geht es mir gut. "
        "Welche Kur?",
        "Welche Reha gibt es nach einem Herzinfarkt?",
        "Ich habe keine Lust auf Papierkram.",
        "Ich arbeite in einer Beratungsstelle für Obdachlose. Welche Versicherung?",
        "Nach dem Sport rast mein Herz. Zahlt die Kasse den Sportkurs?",
        "Mein Herz rast vor Freude.",
        "Mein Vater hatte vor zwei Jahren einen tauben Arm. Welche Reha gibt es?",
        "My mother had slurred speech last year. Who pays for care?",
        "Mein Onkel hatte vor drei Jahren einen Schlaganfall. Welche Hilfen gibt es?",
        "",
    ],
)
def test_no_current_flag(text):
    result = check(text)
    assert not result.hit
    assert result.reason_code is None
    assert result.categories == result.matched == result.contact_ids == []


@pytest.mark.parametrize(
    "text",
    [
        "Vor zwei Jahren hatte ich einen Schlaganfall. Jetzt habe ich Atemnot. Reha?",
        "Ich hatte vor Jahren Brustschmerzen, aber jetzt kann ich nicht atmen. "
        "Welche Kur?",
        "Ich hatte vor Jahren Brustschmerzen und meine Mutter ist bewusstlos. "
        "Pflegegeld?",
        "My father had a stroke last year but now has chest pain. Who pays for care?",
        "Ich habe jetzt Brustschmerzen. Welche Reha nach einem Herzinfarkt?",
    ],
)
def test_history_and_administrative_questions_do_not_hide_current_flags(text):
    assert check(text).reason_code == "emergency"


def test_multiple_categories_prioritize_emergency_and_deduplicate_contacts():
    result = check("Ich bin obdachlos. Ich habe Atemnot und Brustschmerzen. Atemnot!")
    assert result.reason_code == "emergency"
    assert set(result.categories) == {"homelessness", "breathing", "chest_pain"}
    assert set(result.contact_ids) == {
        "telefonseelsorge_142", "rettung_144", "euronotruf_112"
    }
    assert len(result.contact_ids) == len(set(result.contact_ids))
    assert len(result.matched) == len(set(result.matched))


def test_results_do_not_share_lists():
    result = check("")
    result.categories.append("breathing")
    assert check("").categories == []


def test_handover_summary():
    summary = build_handover_summary(
        "Anna Berger (synthetisch)",
        "Der Entlassungsbrief liegt vor. Die Tochter organisiert Unterstützung.",
        ["Pflegegeldantrag vorbereitet", "PVA kontaktiert"],
        "Welche Unterlagen fehlen für den Antrag?",
        ["Entlassungsbrief, Abschnitt 8", "Pflegegeldantrag"],
    )
    assert summary == (
        "Übergabezusammenfassung\n"
        "Betroffene Person: Anna Berger (synthetisch)\n"
        "Situation: Der Entlassungsbrief liegt vor. "
        "Die Tochter organisiert Unterstützung.\n"
        "Bisherige Schritte:\n- Pflegegeldantrag vorbereitet\n- PVA kontaktiert\n"
        "Offene Frage: Welche Unterlagen fehlen für den Antrag?\n"
        "Vorhandene Dokumente:\n- Entlassungsbrief, Abschnitt 8\n- Pflegegeldantrag"
    )


def test_handover_empty_fields_and_single_strings():
    summary = build_handover_summary("", "", [], "", [])
    assert summary.count("Keine Angaben.") == 5
    summary = build_handover_summary("Person", "Situation", "Anruf", "Frage", "Brief")
    assert "Bisherige Schritte:\n- Anruf\n" in summary
    assert summary.endswith("Vorhandene Dokumente:\n- Brief")


def test_load_contacts_from_tmp_file(tmp_path):
    contacts = [
        {
            "id": "synthetic_contact",
            "name": "Synthetische Beratungsstelle",
            "phone": None,
            "url": None,
            "hours": None,
            "note": "Synthetischer Testkontakt, keine echte Beratungsstelle.",
            "reason_codes": ["social_crisis"],
            "source_url": "https://example.invalid",
        }
    ]
    path = tmp_path / "contacts.json"
    path.write_text(json.dumps(contacts, ensure_ascii=False), encoding="utf-8")
    assert load_contacts(path) == contacts
    assert load_contacts(str(path)) == contacts


def test_missing_contacts_warn_without_crashing(tmp_path, caplog):
    path = tmp_path / "missing.json"
    with caplog.at_level(logging.WARNING, logger="app.guardrails.escalation"):
        assert load_contacts(path) == []
    assert "Eskalationskontakte fehlen" in caplog.text
    assert str(path) in caplog.text

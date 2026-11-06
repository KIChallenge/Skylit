"""Demo aufzeichnen und prüfen.

Backend mit LLM_PROVIDER=eustella und LLM_RECORD=1 starten. Dieses Skript ausführen.
Backend mit LLM_PROVIDER=replay neu starten und das Skript mit --check ausführen.
Ohne --case läuft der Golden Path (S1–S3, S5). `--case all` spielt zusätzlich
die drei Show-Fälle aus `CASES` ab
(Kopfschmerz mit SAMPLER, Pflegegeld, Vorsorge).
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any

import httpx

from app.llm.fake import FAKE_MODEL

MESSAGES = (
    "Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr "
    "zurecht. Was muss ich tun?",
    "Ja, sie wohnt in Wien. Hier ist der Brief.",
    "Bitte füll den Pflegegeldantrag für meine Mutter aus.",
    "Soll meine Mutter das Ondansetron höher dosieren, ihr ist noch immer schlecht?",
    "Meine Mutter hat plötzlich starke Atemnot.",
    "Which check-ups does my 2-year-old need?",
)
PDF = Path(__file__).resolve().parents[1] / "seed/documents/entlassungsbefund.pdf"


def parse_sse(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Parse SSE fields, including multiline data and a final unterminated event."""
    event = "message"
    data: list[str] = []
    for line in chain(lines, ("",)):
        if not line:
            if data:
                payload = json.loads("\n".join(data))
                if not isinstance(payload, dict):
                    raise ValueError("SSE data must be a JSON object")
                yield {**payload, "type": event}
            event, data = "message", []
        elif not line.startswith(":"):
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)


def answer_text(events: list[dict[str, Any]]) -> str:
    return "".join(str(e.get("delta", "")) for e in events if e["type"] == "text.delta")


def is_english(text: str) -> bool:
    """Use common function words as a simple, conservative language heuristic."""
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text.lower())
    english = set(
        "the your you and for with can are child children check checkups should "
        "is to of in a at please their these may this".split()
    )
    german = set(
        "der die das und für sie ihre ihr ist mit können sind den eine ein des "
        "von zu bitte kind".split()
    )
    return len(words) >= 5 and sum(w in english for w in words) >= 2 and sum(
        w in english for w in words
    ) > sum(w in german for w in words)


def checks(turns: list[list[dict[str, Any]]]) -> dict[str, bool]:
    """Check the demo outcomes and reject failed or incomplete streams."""
    if len(turns) != len(MESSAGES):
        raise ValueError("Expected six demo turns")
    kinds = [[event["type"] for event in turn] for turn in turns]
    s3 = kinds[4]
    return {
        "S1 case.updated": any("case.updated" in turn for turn in kinds[:3]),
        "S1 form_draft": any(
            e["type"] == "tool.result"
            and isinstance(e.get("card"), dict)
            and e["card"].get("type") == "form_draft"
            for e in turns[2]
        ),
        "S2 escalation": "escalation" in kinds[3],
        "S3 emergency before text": "emergency" in s3
        and ("text.delta" not in s3 or s3.index("emergency") < s3.index("text.delta")),
        "S5 English (heuristic)": is_english(answer_text(turns[5])),
        "All streams completed without errors": all(
            "message.completed" in turn and "error" not in turn for turn in kinds
        ),
    }


def request(
    client: httpx.Client, method: str, path: str, **kwargs: Any
) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def login(client: httpx.Client, persona: str) -> None:
    request(client, "POST", "/api/auth/login", json={"persona_id": persona})


def conversation(client: httpx.Client) -> str:
    return request(client, "POST", "/api/conversations").json()["id"]


def upload(client: httpx.Client, conversation_id: str) -> str:
    with PDF.open("rb") as file:
        response = request(
            client, "POST", "/api/documents", data={"conversation_id": conversation_id},
            files={"file": (PDF.name, file, "application/pdf")},
        )
    document = response.json()
    deadline = time.monotonic() + 300
    while document["status"] == "processing" and time.monotonic() < deadline:
        time.sleep(1)
        document = request(client, "GET", f"/api/documents/{document['id']}").json()
    if document["status"] != "ready":
        raise RuntimeError(
            f"Document not ready: {document['status']} {document.get('error')}"
        )
    return document["id"]


def check_replay_turn(
    client: httpx.Client, events: list[dict[str, Any]], index: int
) -> None:
    """Reject fake fallback in any LLM round, including earlier tool rounds."""
    completed = next(
        (event for event in events if event["type"] == "message.completed"), None
    )
    if completed is None or not completed.get("message_id"):
        raise RuntimeError(f"Turn {index + 1}: Abschluss mit message_id fehlt.")
    message_id = completed["message_id"]
    transparency = request(
        client, "GET", f"/api/messages/{message_id}/transparency"
    ).json()
    models = [transparency.get("model")]
    models.extend(
        entry.get("detail", {}).get("model")
        for entry in transparency.get("entries", [])
        if entry.get("event_type") == "llm_call"
    )
    if FAKE_MODEL in models:
        raise RuntimeError(
            f"Turn {index + 1}: Replay-Miss; das Backend nutzt den Fake-Fallback."
        )


def send_turn(
    client: httpx.Client,
    conversation_id: str,
    index: int,
    document_ids: list[str] | None = None,
    *,
    check: bool = False,
) -> list[dict[str, Any]]:
    return send_message(
        client, conversation_id, index, MESSAGES[index], document_ids, check=check
    )


def send_message(
    client: httpx.Client,
    conversation_id: str,
    index: int,
    content: str,
    document_ids: list[str] | None = None,
    *,
    check: bool = False,
) -> list[dict[str, Any]]:
    start = time.monotonic()
    with client.stream(
        "POST", f"/api/conversations/{conversation_id}/messages",
        json={"content": content, "document_ids": document_ids or []},
    ) as response:
        response.raise_for_status()
        events = list(parse_sse(response.iter_lines()))
    counts = Counter(e["type"] for e in events)
    calls = [e.get("name", "?") for e in events if e["type"] == "tool.called"]
    print(f"Turn {index + 1}: {time.monotonic() - start:.1f}s; events: {dict(counts)}")
    print(f"  Tools: {', '.join(calls) or '–'}")
    print(f"  Text: {answer_text(events)[:120]!r}")
    if check:
        check_replay_turn(client, events, index)
    return events


# Drei Show-Fälle für die Jury. Jeder Fall startet mit einem Reset der Persona
# und einem neuen Gespräch, damit die Replay-Schlüssel stabil bleiben.
# Postleitzahl statt Standort: Koordinaten würden die Schlüssel verändern.
# Alle Angaben sind synthetisch.


@dataclass(frozen=True)
class Step:
    message: str
    upload: bool = False


@dataclass(frozen=True)
class DemoCase:
    title: str
    persona: str
    steps: tuple[Step, ...]
    checks: Callable[[list[list[dict[str, Any]]]], dict[str, bool]]
    # SAMPLER-Stichwörter je Schritt. Der Lauf klickt auf jeder Karte eine Option.
    sampler_answers: dict[str, tuple[str, ...]] | None = None
    # Die SAMPLER-Aufnahme folgt auf diesen Schritt.
    sampler_after: int = 0


def cards_of(turn: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        e["card"] for e in turn
        if e["type"] == "tool.result" and isinstance(e.get("card"), dict)
    ]


def has_card(turn: list[dict[str, Any]], card_type: str, **fields: str) -> bool:
    """Check for a card type. Fields also match one level of nested objects."""
    for card in cards_of(turn):
        if card.get("type") != card_type:
            continue
        flat = {**card, **{
            k: v for value in card.values() if isinstance(value, dict)
            for k, v in value.items()
        }}
        if all(flat.get(key) == value for key, value in fields.items()):
            return True
    return False


def any_card(turns: list[list[dict[str, Any]]], card_type: str, **fields: str) -> bool:
    return any(has_card(turn, card_type, **fields) for turn in turns)


def called(turns: list[list[dict[str, Any]]], tool: str) -> bool:
    return any(
        e["type"] == "tool.called" and e.get("name") == tool
        for turn in turns for e in turn
    )


def has_event(turns: list[list[dict[str, Any]]], kind: str) -> bool:
    return any(e["type"] == kind for turn in turns for e in turn)


def cited(turns: list[list[dict[str, Any]]], needle: str) -> bool:
    """Check that a `sources` event cites a source whose title or URL holds `needle`."""
    needle = needle.lower()
    return any(
        needle in f"{source.get('title', '')} {source.get('url', '')}".lower()
        for turn in turns for e in turn if e["type"] == "sources"
        for source in e.get("sources", []) if isinstance(source, dict)
    )


def completed(turns: list[list[dict[str, Any]]]) -> bool:
    return all(
        any(e["type"] == "message.completed" for e in turn)
        and not any(e["type"] == "error" for e in turn)
        for turn in turns
    )


def sampler_question(turn: list[dict[str, Any]]) -> dict[str, Any] | None:
    for card in cards_of(turn):
        if card.get("type") == "sampler_question":
            return card.get("question")
    return None


def pick_option(question: dict[str, Any], keywords: tuple[str, ...]) -> str:
    """Pick the option a presenter clicks live, so replay sees the same message."""
    options = [str(option) for option in question.get("options", [])]
    for keyword in keywords:
        for option in options:
            if keyword in option.lower():
                return option
    # Never fall back to an alarm sign: the story is a mild tension headache.
    alarm = ("plötzlich", "stark", "unerträglich", "sturz", "unfall", "fieber")
    calm = [o for o in options if not any(word in o.lower() for word in alarm)]
    unsure = [o for o in calm if "weiß" in o.lower() or "weiss" in o.lower()]
    return (unsure or calm or options)[0]


def check_kopfschmerz(turns: list[list[dict[str, Any]]]) -> dict[str, bool]:
    asked = {
        q["step"] for turn in turns if (q := sampler_question(turn)) is not None
    }
    return {
        "Kein Notfall-Banner": not has_event(turns, "emergency"),
        "SAMPLER-Karten (mind. 3 Schritte)": len(asked) >= 3,
        "Hausärztinnen in 1100 gefunden": any_card(turns, "provider_list"),
        "E-Mail-Entwurf an die Hausärztin": any_card(turns, "email_draft"),
        "Alle Streams vollständig": completed(turns),
    }


def check_pflegegeld(turns: list[list[dict[str, Any]]]) -> dict[str, bool]:
    return {
        "Entlassungsbrief gelesen": called(turns[:1], "get_document"),
        "Quelle Pflegekarenz": cited(turns, "pflegekarenz"),
        "Mein Fall gefüllt": has_event(turns, "case.updated"),
        "Pflegegeldantrag vorausgefüllt": any_card(
            turns, "form_draft", form_id="pva_pflegegeld"
        ),
        "Zuständige Stelle": any_card(turns, "office"),
        "Demo-Termin Pflegeberatung": any_card(turns, "appointment"),
        "E-Mail-Entwurf an Arbeitgeber": any_card(turns, "email_draft"),
        "Alle Streams vollständig": completed(turns),
    }


def check_vorsorge(turns: list[list[dict[str, Any]]]) -> dict[str, bool]:
    return {
        "Kein SAMPLER bei Vorsorge": not any_card(turns, "sampler_question"),
        "Quelle Vorsorgeuntersuchung": cited(turns, "gesundenuntersuchung")
        or cited(turns, "vorsorgeuntersuchung"),
        "SVS-Angebot mit Quelle": cited(turns, "svs"),
        "Ordinationen in 1100 gefunden": any_card(turns, "provider_list"),
        "Demo-Termin vorgeschlagen": any_card(turns, "appointment"),
        "Mein Fall gefüllt": has_event(turns, "case.updated"),
        "Alle Streams vollständig": completed(turns),
    }


CASES: dict[str, DemoCase] = {
    "kopfschmerz": DemoCase(
        title="Kopfschmerzen: SAMPLER-Aufnahme, Hausärztin, E-Mail",
        persona="stefan",
        steps=(
            Step(
                "Ich habe seit drei Tagen Kopfschmerzen und weiß nicht, wohin ich "
                "damit gehen soll."
            ),
            Step("Welche Hausärztinnen oder Hausärzte gibt es in 1100?"),
            Step(
                "Ja, bitte entwirf die E-Mail mit meinen Angaben an die "
                "Demo-Ordination Dr. Emil Kieselstern."
            ),
        ),
        # Stichwörter je SAMPLER-Schritt: Die erste passende Option wird gewählt.
        sampler_answers={
            "S_O": ("2–3 tag", "2-3 tag", "mehrere tage", "schleichend", "allmählich"),
            "S_P": ("bildschirm", "pause", "ruhe", "stress"),
            "S_Q": ("drück", "druck", "dumpf"),
            "S_R": ("stirn", "beidseit", "ganz"),
            "S_S": ("4–5", "4–6", "4-6", "4-5", "mittel", "mäßig"),
            "S_T": ("kommt und geht", "kommen und gehen", "nachmittag", "tagsüber"),
            "A": ("keine",),
            "M": ("keine",),
            "P": ("keine", "nein"),
            "L": ("weniger getrunken", "getrunken", "normal"),
            "E": ("bildschirm", "stress"),
            "R": ("bildschirm", "wenig bewegung", "sitz"),
        },
        sampler_after=0,
        checks=check_kopfschmerz,
    ),
    "pflegegeld": DemoCase(
        title="Pflegegeld: Brief, Antrag, Stellen, Termin, Pflegekarenz",
        persona="maria",
        steps=(
            Step(
                "Meine Mutter Anna ist gestern aus dem Spital entlassen worden. Sie "
                "wohnt allein in 1030 Wien. Hier ist der Entlassungsbrief. Welche "
                "Unterstützung bekommt sie?",
                upload=True,
            ),
            Step("Bitte füll den Pflegegeldantrag für meine Mutter aus."),
            Step(
                "Wo reiche ich den Antrag ein, und wer hilft uns bei der Pflege zu "
                "Hause?"
            ),
            Step(
                "Bitte schlag mir einen Termin bei einer Pflegeberatung in 1030 vor."
            ),
            Step(
                "Ich arbeite Vollzeit. Kann ich für die Pflege meiner Mutter in "
                "Pflegekarenz gehen? Bitte entwirf auch eine E-Mail an meinen "
                "Arbeitgeber an personal@arbeitgeber.example."
            ),
            Step("Ja, bitte erstelle den E-Mail-Entwurf."),
        ),
        checks=check_pflegegeld,
    ),
    "vorsorge": DemoCase(
        title="Vorsorge: Vorsorgeuntersuchung und SVS-Angebote",
        persona="stefan",
        steps=(
            Step(
                "Ich bin selbstständig und möchte etwas für meine Gesundheit tun. "
                "Was bietet mir meine Versicherung an?"
            ),
            Step(
                "Ich möchte mich mehr bewegen und weniger Stress haben. Meine letzte "
                "Vorsorgeuntersuchung ist über drei Jahre her."
            ),
            Step(
                "Wo kann ich die Vorsorgeuntersuchung in 1100 machen? Bitte schlag "
                "mir einen Termin bei der Demo-Ordination vor."
            ),
            Step("Bitte leg mir die nächsten Schritte in Mein Fall an."),
        ),
        checks=check_vorsorge,
    ),
}


def run_case(
    client: httpx.Client, name: str, *, check: bool = False
) -> dict[str, bool]:
    case = CASES[name]
    print(f"\n== Fall {name}: {case.title} ==")
    login(client, case.persona)
    request(client, "POST", "/api/dev/reset")
    conversation_id = conversation(client)
    turns: list[list[dict[str, Any]]] = []

    def send(content: str, documents: list[str] | None = None) -> None:
        turns.append(send_message(
            client, conversation_id, len(turns), content, documents, check=check
        ))

    for index, step in enumerate(case.steps):
        send(step.message, [upload(client, conversation_id)] if step.upload else [])
        if case.sampler_answers and index == case.sampler_after:
            # Höchstens zwölf SAMPLER-Schritte. Die Grenze fängt Schleifen ab.
            for _ in range(len(case.sampler_answers) + 2):
                question = sampler_question(turns[-1])
                if question is None:
                    break
                keywords = case.sampler_answers.get(question["step"], ())
                answer = pick_option(question, keywords)
                print(f"  Klick: {question['step_label']} → {answer}")
                # Gleiches Format wie die SAMPLER-Karte im Frontend.
                send(f"{question['step_label']}: {answer}")
    request(client, "POST", "/api/auth/logout")
    return {f"{name}: {label}": ok for label, ok in case.checks(turns).items()}

def run(
    base_url: str, *, check: bool = False, cases: Iterable[str] = ("golden",)
) -> bool:
    cases = list(cases)
    with httpx.Client(base_url=base_url, timeout=300) as client:
        results: dict[str, bool] = {}
        if "golden" in cases:
            results.update(run_golden(client, check=check))
        for name in cases:
            if name != "golden":
                results.update(run_case(client, name, check=check))
    for label, passed in results.items():
        print(f"{'✔' if passed else '✘'} {label}")
    return all(results.values())


def run_golden(client: httpx.Client, *, check: bool = False) -> dict[str, bool]:
    login(client, "maria")
    request(client, "POST", "/api/dev/reset")
    case = conversation(client)
    turns = [send_turn(client, case, 0, check=check)]
    document_id = upload(client, case)
    turns.append(send_turn(client, case, 1, [document_id], check=check))
    turns.extend(
        send_turn(client, case, index, check=check) for index in range(2, 5)
    )
    request(client, "POST", "/api/auth/logout")
    login(client, "elif")
    turns.append(send_turn(client, conversation(client), 5, check=check))
    request(client, "POST", "/api/auth/logout")
    return checks(turns)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--check", action="store_true", help="Prüfung im Replay-Modus")
    parser.add_argument(
        "--case", action="append", choices=["golden", "all", *CASES],
        help="Fall zum Abspielen, mehrfach möglich. Standard: golden.",
    )
    args = parser.parse_args()
    cases = args.case or ["golden"]
    if "all" in cases:
        cases = ["golden", *CASES]
    try:
        return 0 if run(args.base_url, check=args.check, cases=cases) else 1
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        print(f"✘ Demo failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

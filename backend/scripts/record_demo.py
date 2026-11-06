"""Demo aufzeichnen und prüfen.

Backend mit LLM_PROVIDER=eustella und LLM_RECORD=1 starten. Dieses Skript ausführen.
Backend mit LLM_PROVIDER=replay neu starten und das Skript mit --check ausführen.
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Iterable, Iterator
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
    start = time.monotonic()
    with client.stream(
        "POST", f"/api/conversations/{conversation_id}/messages",
        json={"content": MESSAGES[index], "document_ids": document_ids or []},
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


def run(base_url: str, *, check: bool = False) -> bool:
    with httpx.Client(base_url=base_url, timeout=300) as client:
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
    results = checks(turns)
    for label, passed in results.items():
        print(f"{'✔' if passed else '✘'} {label}")
    return all(results.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--check", action="store_true", help="Prüfung im Replay-Modus")
    args = parser.parse_args()
    try:
        return 0 if run(args.base_url, check=args.check) else 1
    except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
        print(f"✘ Demo failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

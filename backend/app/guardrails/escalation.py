"""Load sourced contacts and assemble factual German handovers without an LLM."""

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

CONTACTS_PATH = Path(__file__).resolve().parents[2] / "seed/escalation_contacts.json"


class EscalationContact(TypedDict):
    id: str
    name: str
    phone: str | None
    url: str | None
    hours: str | None
    note: str
    reason_codes: list[str]
    source_url: str


def load_contacts(path: str | Path = CONTACTS_PATH) -> list[EscalationContact]:
    """Read the seed file; keep missing seed data from breaking escalation."""
    try:
        with Path(path).open(encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        logger.warning("Eskalationskontakte fehlen: %s", path)
        return []


def _list_text(items: Sequence[str] | str) -> str:
    if isinstance(items, str):
        items = [items]
    return "\n".join(f"- {item}" for item in items) or "Keine Angaben."


def build_handover_summary(
    subject: str,
    situation: str,
    done_steps: Sequence[str] | str,
    open_question: str,
    documents: Sequence[str] | str,
) -> str:
    """Format supplied facts verbatim; never infer diagnoses or medical advice."""
    return (
        "Übergabezusammenfassung\n"
        f"Betroffene Person: {subject or 'Keine Angaben.'}\n"
        f"Situation: {situation or 'Keine Angaben.'}\n"
        f"Bisherige Schritte:\n{_list_text(done_steps)}\n"
        f"Offene Frage: {open_question or 'Keine Angaben.'}\n"
        f"Vorhandene Dokumente:\n{_list_text(documents)}"
    )

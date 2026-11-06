"""Deterministic emergency checks and escalation helpers."""

from app.guardrails.escalation import build_handover_summary, load_contacts
from app.guardrails.red_flags import RedFlagResult, check

__all__ = ["RedFlagResult", "build_handover_summary", "check", "load_contacts"]

"""Deterministic scripted provider for tests, UI work and replay misses."""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.llm.types import (
    BaseLLMClient,
    LLMChunk,
    Messages,
    ToolCallDelta,
    Tools,
    Usage,
    parse_tool_call,
)

FAKE_MODEL = "fake"
FAKE_REQUEST_ID = "fake-request"
ARGUMENT_FRAGMENT_CHARS = 24
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class _Script:
    keywords: tuple[str, ...]
    text: str
    tool_calls: tuple[tuple[str, dict[str, Any]], ...] = ()
    # The answer after the tool results. Without it the tool loop would never end.
    follow_up: str = ""


_S3_EMERGENCY = _Script(
    keywords=(
        "atemnot",
        "keine luft",
        "brustschmerz",
        "bewusstlos",
        "schlaganfall",
        "notfall",
    ),
    text=(
        "Bitte rufen Sie jetzt die Rettung unter 144 an. "
        "Bleiben Sie bei Ihrer Mutter, bis die Rettung da ist."
    ),
)

_S2_DOSAGE = _Script(
    keywords=("dosier", "dosis", "ondansetron", "medikament"),
    text=(
        "Zur Dosierung darf ich nichts sagen, "
        "weil das eine medizinische Entscheidung ist."
    ),
    tool_calls=(
        (
            "escalate",
            {
                "reason_code": "medical_question",
                "target_kind": "treating_team",
                "open_question": (
                    "Die Angehörige fragt, ob die Dosis eines verordneten "
                    "Medikaments geändert werden soll."
                ),
            },
        ),
    ),
    follow_up=(
        "Bitte besprechen Sie das mit der Hausärztin oder dem behandelnden Team. "
        "Außerhalb der Ordinationszeiten erreichen Sie die Gesundheitsberatung "
        "unter 1450. Die Zusammenfassung für das Gespräch ist vorbereitet."
    ),
)

_S1_DOCUMENT = _Script(
    keywords=(
        "hier ist der brief",
        "entlassungsbrief",
        "entlassungsbefund",
        "pflegegeldantrag",
    ),
    text=(
        "Danke. Im Entlassungsbrief wird empfohlen, Pflegegeld zu prüfen. "
        "Ich trage das in Ihren Fall ein und fülle den Antrag vor."
    ),
    tool_calls=(
        (
            "upsert_case_step",
            {
                "title": "Pflegegeld beantragen",
                "description": (
                    "Der Entlassungsbrief empfiehlt, Pflegegeld zu prüfen. "
                    "Die PVA entscheidet nach einer Begutachtung."
                ),
                "category": "form",
                "status": "open",
                "leistung_id": "pflegegeld",
            },
        ),
        (
            "prepare_form",
            {
                "form_id": "pva_pflegegeld",
                "values": {
                    "applicant.first_name": "Anna",
                    "applicant.last_name": "Berger",
                },
            },
        ),
    ),
    follow_up=(
        "Der Schritt steht jetzt in „Mein Fall“, und der Pflegegeldantrag ist "
        "vorausgefüllt. Prüfen Sie bitte die fehlenden Felder. "
        "Sie senden den Antrag selbst an die PVA."
    ),
)

_S1_INTAKE = _Script(
    keywords=("spital", "krankenhaus", "zurecht"),
    text=(
        "Ich helfe Ihnen, die nächsten Schritte zu ordnen. Zwei kurze Fragen: "
        "Gibt es einen Entlassungsbrief? Lebt Ihre Mutter in Wien?"
    ),
)

_DEFAULT = _Script(
    keywords=(),
    text=(
        "Gerne helfe ich Ihnen weiter. Beschreiben Sie bitte kurz Ihre Situation. "
        "Dann nenne ich Ihnen die nächsten Schritte und die zuständige Stelle."
    ),
)

# Safety first: an emergency or a dosage question wins over every other match.
_SCRIPTS = (_S3_EMERGENCY, _S2_DOSAGE, _S1_DOCUMENT, _S1_INTAKE)


def _content_text(content: Any) -> str:
    """Return the text of a message. Content may be a list of parts with images."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def _last_user_index(messages: Messages) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            return index
    return None


def _select_script(last_user_text: str) -> _Script:
    text = last_user_text.lower()
    for script in _SCRIPTS:
        if any(keyword in text for keyword in script.keywords):
            return script
    return _DEFAULT


def _offered_tools(tools: Tools | None) -> set[str]:
    return {tool.get("function", {}).get("name") for tool in tools or []}


class FakeClient(BaseLLMClient):
    """Match the last user message by keywords and stream a scripted answer."""

    def __init__(self) -> None:
        self.model = FAKE_MODEL

    async def stream_chat(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        last_user = _last_user_index(messages)
        user_text = (
            "" if last_user is None else _content_text(messages[last_user]["content"])
        )
        script = _select_script(user_text)
        after_tools = last_user is not None and any(
            message.get("role") == "tool" for message in messages[last_user + 1 :]
        )

        text = script.text
        calls: tuple[tuple[str, dict[str, Any]], ...] = ()
        if after_tools:
            text = script.follow_up or script.text
        elif tool_choice != "none":
            # Like a real model, the fake calls only the tools the request offers.
            offered = _offered_tools(tools)
            calls = tuple(call for call in script.tool_calls if call[0] in offered)

        for word in re.findall(r"\S+\s*", text):
            await asyncio.sleep(0)
            yield LLMChunk(type="text", text=word)

        tool_calls = []
        completion_chars = len(text)
        for index, (name, arguments) in enumerate(calls):
            call_id = f"call_fake_{index + 1}"
            raw = json.dumps(arguments, ensure_ascii=False)
            completion_chars += len(raw)
            yield LLMChunk(
                type="tool_call",
                tool_call=ToolCallDelta(index=index, id=call_id, name=name),
            )
            for start in range(0, len(raw), ARGUMENT_FRAGMENT_CHARS):
                yield LLMChunk(
                    type="tool_call",
                    tool_call=ToolCallDelta(
                        index=index,
                        arguments=raw[start : start + ARGUMENT_FRAGMENT_CHARS],
                    ),
                )
            tool_calls.append(parse_tool_call(call_id, name, raw))

        prompt_chars = sum(len(_content_text(m.get("content"))) for m in messages)
        usage = Usage(
            prompt_tokens=prompt_chars // CHARS_PER_TOKEN,
            completion_tokens=completion_chars // CHARS_PER_TOKEN,
        )
        yield LLMChunk(type="usage", usage=usage)
        yield LLMChunk(
            type="finish",
            finish_reason="tool_calls" if tool_calls else "stop",
            tool_calls=tool_calls,
            usage=usage,
            model=self.model,
            request_id=FAKE_REQUEST_ID,
        )

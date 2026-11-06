"""Tool registry: name → input model, handler and German label (contracts.md §4)."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.types import ToolCall, Tools
from app.models import Case, Conversation, User
from app.schemas.cards import Card

logger = logging.getLogger(__name__)

DEFAULT_LABEL = "Schritt wird ausgeführt"
USER_ERROR = "Dieser Schritt konnte nicht abgeschlossen werden."
_INTERNAL_ERROR = "Das Tool ist fehlgeschlagen. Antworte ohne dieses Ergebnis."

AuditFn = Callable[[str, str, dict[str, Any]], Awaitable[Any]]


@dataclass
class ToolContext:
    db: AsyncSession
    user: User
    conversation: Conversation
    case: Case
    # Writes an audit row for this turn: audit(event_type, summary, detail).
    audit: AuditFn
    # True when the red-flag check found an emergency in this message.
    emergency: bool = False
    # (lat, lon) the person shared in the browser for this turn. Never sent to the LLM.
    location: tuple[float, float] | None = None


@dataclass
class ToolOutput:
    result: dict[str, Any]
    card: Card | None = None
    case_changed: bool = False


class ToolError(Exception):
    """An expected tool failure. The message goes to the model, so it can recover."""


@dataclass
class ToolExecution:
    """The outcome of one tool call. `error` is German text for the UI."""

    ok: bool
    result: dict[str, Any]
    card: Card | None = None
    case_changed: bool = False
    error: str | None = None


Handler = Callable[[Any, ToolContext], Awaitable[ToolOutput]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    label: str
    input_model: type[BaseModel]
    handler: Handler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def tool(
        self, name: str, *, label: str, description: str, input_model: type[BaseModel]
    ) -> Callable[[Handler], Handler]:
        """Register the decorated handler."""

        def decorate(handler: Handler) -> Handler:
            if name in self._tools:
                raise ValueError(f"Tool {name} is already registered")
            self._tools[name] = Tool(name, description, label, input_model, handler)
            return handler

        return decorate

    def label(self, name: str) -> str:
        tool = self._tools.get(name)
        return tool.label if tool else DEFAULT_LABEL

    def openai_tools(self) -> Tools:
        """Export OpenAI `tools`. The order is stable, for the cache and for replay."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_model.model_json_schema(),
                },
            }
            for tool in self._tools.values()
        ]

    async def execute(self, call: ToolCall, ctx: ToolContext) -> ToolExecution:
        """Run one call. All failures become `{error: ...}` and never raise.

        Each handler runs in a savepoint: a failed handler leaves no partial write.
        """
        tool = self._tools.get(call.name)
        if tool is None:
            return _failed(f"Unbekanntes Tool: {call.name}")
        if call.parse_error:
            return _failed("Die Argumente sind kein gültiges JSON-Objekt.")
        try:
            tool_input = tool.input_model.model_validate(call.arguments)
        except ValidationError as exc:
            return _failed(_describe(exc))
        try:
            async with ctx.db.begin_nested():
                output = await tool.handler(tool_input, ctx)
        except ToolError as exc:
            return _failed(str(exc))
        except Exception:
            logger.exception("Tool %s failed", call.name)
            return _failed(_INTERNAL_ERROR)
        return ToolExecution(
            ok=True,
            result=output.result,
            card=output.card,
            case_changed=output.case_changed,
        )


def _failed(message: str) -> ToolExecution:
    return ToolExecution(ok=False, result={"error": message}, error=USER_ERROR)


def _describe(exc: ValidationError) -> str:
    """List the invalid fields, without their values: these may be personal."""
    problems = [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors(include_input=False, include_url=False)
    ]
    return "Ungültige Argumente: " + "; ".join(problems)


registry = ToolRegistry()

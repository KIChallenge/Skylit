"""Provider-independent LLM types: chunks, results, errors and the interface."""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

Messages = list[dict[str, Any]]
Tools = list[dict[str, Any]]


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


class ToolCallDelta(BaseModel):
    """One streamed fragment of a tool call. `index` groups the fragments."""

    index: int
    id: str | None = None
    name: str | None = None
    arguments: str = ""


class ToolCall(BaseModel):
    """A complete tool call.

    `parse_error` is set when the model sent invalid JSON. The orchestrator then
    returns `{error: ...}` to the model instead of running the handler.
    """

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_arguments: str = ""
    parse_error: str | None = None


class LLMChunk(BaseModel):
    """One stream item. `type` says which fields are set.

    - `text`: `text`
    - `tool_call`: `tool_call`
    - `usage`: `usage`
    - `finish`: always the last chunk. It holds `finish_reason`, the complete
      `tool_calls`, and the audit data: `usage`, `model`, `request_id`, `rate_limit`.
    """

    type: Literal["text", "tool_call", "usage", "finish"]
    text: str | None = None
    tool_call: ToolCallDelta | None = None
    usage: Usage | None = None
    finish_reason: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str | None = None
    request_id: str | None = None
    rate_limit: dict[str, str] = Field(default_factory=dict)


class LLMResult(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: Usage = Field(default_factory=Usage)
    model: str | None = None
    request_id: str | None = None
    rate_limit: dict[str, str] = Field(default_factory=dict)


class LLMError(Exception):
    """A failed LLM call. `message` is German and safe to show to the user."""

    def __init__(
        self,
        code: str,
        message: str,
        retry_after: float | None = None,
        status: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.status = status
        self.request_id = request_id


def parse_tool_call(id: str, name: str, raw_arguments: str) -> ToolCall:
    """Build a ToolCall. Invalid JSON sets `parse_error` and never raises."""
    try:
        arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
    except json.JSONDecodeError as exc:
        return ToolCall(
            id=id, name=name, raw_arguments=raw_arguments, parse_error=str(exc)
        )
    if not isinstance(arguments, dict):
        return ToolCall(
            id=id,
            name=name,
            raw_arguments=raw_arguments,
            parse_error="Tool arguments are not a JSON object",
        )
    return ToolCall(
        id=id, name=name, arguments=arguments, raw_arguments=raw_arguments
    )


async def collect_result(chunks: AsyncIterator[LLMChunk]) -> LLMResult:
    """Consume a stream and return its LLMResult."""
    result = LLMResult()
    parts: list[str] = []
    async for chunk in chunks:
        if chunk.type == "text" and chunk.text:
            parts.append(chunk.text)
        elif chunk.type == "finish":
            result = LLMResult(
                tool_calls=chunk.tool_calls,
                finish_reason=chunk.finish_reason,
                usage=chunk.usage or Usage(),
                model=chunk.model,
                request_id=chunk.request_id,
                rate_limit=chunk.rate_limit,
            )
    result.text = "".join(parts)
    return result


class LLMClient(Protocol):
    """The interface from architecture.md §5.

    `stream_chat` is a plain `def` here because callers use `async for` on its
    return value directly. Implementations are async generators.
    """

    model: str

    def stream_chat(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]: ...

    async def complete(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResult: ...


class BaseLLMClient(ABC):
    """Shared `complete` for all providers. It always uses the stream."""

    model: str

    @abstractmethod
    def stream_chat(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]: ...

    async def complete(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResult:
        return await collect_result(
            self.stream_chat(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                thinking=thinking,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        )

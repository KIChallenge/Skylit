"""LLM client: picks the provider and runs live calls with retries and limits."""

import asyncio
import logging
import math
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import openai

from app.config import settings
from app.llm.fake import FakeClient
from app.llm.replay import RecordingClient, ReplayClient
from app.llm.types import (
    BaseLLMClient,
    LLMChunk,
    LLMClient,
    LLMError,
    Messages,
    ToolCallDelta,
    Tools,
    Usage,
    parse_tool_call,
)

logger = logging.getLogger(__name__)

# eustella trap 1: reasoning counts toward max_tokens. Smaller limits return nothing.
MIN_MAX_TOKENS = 4096
DEFAULT_RETRY_SECONDS = 2.0
BAD_GATEWAY_RETRIES = 1
RETRY_AFTER_STATUSES = (429, 503)

# All live calls share one limit: eustella allows 2 concurrent calls per organisation.
_semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

_STATUS_ERRORS: dict[int, tuple[str, str]] = {
    400: (
        "invalid_request",
        "Die Anfrage konnte nicht verarbeitet werden. Bitte formulieren Sie sie neu.",
    ),
    401: (
        "unauthorized",
        "Der KI-Dienst hat die Anmeldung abgelehnt. Bitte informieren Sie das Team.",
    ),
    402: (
        "insufficient_credit",
        "Das Guthaben für den KI-Dienst ist aufgebraucht. "
        "Bitte informieren Sie das Team.",
    ),
    403: (
        "forbidden",
        "Der KI-Dienst hat den Zugriff abgelehnt. Bitte informieren Sie das Team.",
    ),
    502: (
        "bad_gateway",
        "Der Dienst hat gerade einen Fehler gemeldet. Bitte versuchen Sie es erneut.",
    ),
}
_UNAVAILABLE_MESSAGE = (
    "Der Dienst ist gerade nicht erreichbar. Bitte versuchen Sie es gleich erneut."
)
_TIMEOUT_MESSAGE = (
    "Der Dienst antwortet gerade nicht. Bitte versuchen Sie es gleich erneut."
)
_EMPTY_MESSAGE = (
    "Der Dienst hat keine Antwort geliefert. Bitte versuchen Sie es erneut."
)


def _busy_message(retry_after: float | None) -> str:
    prefix = "Der Dienst ist gerade ausgelastet."
    if not retry_after:
        return f"{prefix} Bitte versuchen Sie es gleich erneut."
    seconds = math.ceil(retry_after)
    unit = "Sekunde" if seconds == 1 else "Sekunden"
    return f"{prefix} Bitte versuchen Sie es in {seconds} {unit} erneut."


def _parse_retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(seconds, 0.0) if math.isfinite(seconds) else None


def _to_llm_error(exc: Exception) -> LLMError:
    """Map any failure to an LLMError. The API's raw text never reaches the user."""
    if isinstance(exc, openai.APITimeoutError):
        return LLMError("timeout", _TIMEOUT_MESSAGE)

    status = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    api_code = getattr(exc, "code", None)
    retry_after = _parse_retry_after(exc)

    if status in RETRY_AFTER_STATUSES:
        code = api_code or ("rate_limited" if status == 429 else "overloaded")
        message = _busy_message(retry_after)
    elif status in _STATUS_ERRORS:
        default_code, message = _STATUS_ERRORS[status]
        code = api_code or default_code
    else:
        code = api_code or "unavailable"
        message = _UNAVAILABLE_MESSAGE
    return LLMError(code, message, retry_after, status, request_id)


class _RetryBudget:
    """Counts the retries left for one `stream_chat` call."""

    def __init__(self) -> None:
        self.busy = settings.llm_max_retries
        self.bad_gateway = BAD_GATEWAY_RETRIES

    def next_wait(self, error: LLMError) -> float | None:
        """Return the seconds to wait before a retry, or None to give up."""
        wait = DEFAULT_RETRY_SECONDS if error.retry_after is None else error.retry_after
        if error.status in RETRY_AFTER_STATUSES:
            # A daily quota sends a Retry-After of hours. Waiting would hang the turn.
            if self.busy <= 0 or wait > settings.llm_timeout_seconds:
                return None
            self.busy -= 1
            return wait
        if error.status == 502 and self.bad_gateway > 0:
            self.bad_gateway -= 1
            return wait
        return None


class _StreamState:
    """Assembles one attempt: tool-call fragments, usage and audit data."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.has_text = False
        self.fragments: dict[int, dict[str, str]] = {}
        self.finish_reason: str | None = None
        self.usage: Usage | None = None
        self.request_id: str | None = None
        self.rate_limit: dict[str, str] = {}

    @property
    def has_output(self) -> bool:
        return self.has_text or bool(self.fragments)

    @property
    def is_empty_length(self) -> bool:
        return self.finish_reason == "length" and not self.has_output

    def capture_headers(self, headers: Any) -> None:
        self.request_id = headers.get("x-request-id")
        self.rate_limit = {
            name.lower(): value
            for name, value in headers.items()
            if name.lower().startswith("x-ratelimit-")
        }

    def feed(self, raw: Any) -> list[LLMChunk]:
        """Turn one SDK chunk into text and tool-call chunks."""
        if raw.usage is not None:
            details = raw.usage.prompt_tokens_details
            self.usage = Usage(
                prompt_tokens=raw.usage.prompt_tokens or 0,
                completion_tokens=raw.usage.completion_tokens or 0,
                cached_tokens=(details.cached_tokens or 0) if details else 0,
            )
        if not raw.choices:
            return []

        choice = raw.choices[0]
        if choice.finish_reason:
            self.finish_reason = choice.finish_reason

        chunks: list[LLMChunk] = []
        if choice.delta.content:
            self.has_text = True
            chunks.append(LLMChunk(type="text", text=choice.delta.content))
        for delta in choice.delta.tool_calls or []:
            chunks.append(LLMChunk(type="tool_call", tool_call=self._add_tool(delta)))
        return chunks

    def _add_tool(self, delta: Any) -> ToolCallDelta:
        fragment = self.fragments.setdefault(
            delta.index, {"id": "", "name": "", "arguments": ""}
        )
        name = delta.function.name if delta.function else None
        arguments = (delta.function.arguments if delta.function else None) or ""
        # Keep the first id, but assemble names and arguments from every fragment.
        fragment["id"] = fragment["id"] or delta.id or ""
        fragment["name"] += name or ""
        fragment["arguments"] += arguments
        return ToolCallDelta(
            index=delta.index, id=delta.id, name=name, arguments=arguments
        )

    def final_chunks(self) -> list[LLMChunk]:
        usage = self.usage or Usage()
        chunks = [LLMChunk(type="usage", usage=usage)] if self.usage else []
        chunks.append(
            LLMChunk(
                type="finish",
                finish_reason=self.finish_reason or "stop",
                tool_calls=[
                    parse_tool_call(f["id"], f["name"], f["arguments"])
                    for f in self.fragments.values()
                ],
                usage=usage,
                model=self.model,
                request_id=self.request_id,
                rate_limit=self.rate_limit,
            )
        )
        return chunks


class OpenAICompatibleClient(BaseLLMClient):
    """A live provider behind the OpenAI SDK. Subclasses set the provider options."""

    def __init__(self, sdk: Any, model: str) -> None:
        self.sdk = sdk
        self.model = model

    def _provider_options(self, thinking: bool, max_tokens: int) -> dict[str, Any]:
        raise NotImplementedError

    def _request(
        self,
        messages: Messages,
        tools: Tools | None,
        tool_choice: Any,
        thinking: bool,
        max_tokens: int | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        limit = max(max_tokens or settings.llm_max_tokens, MIN_MAX_TOKENS)
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            **self._provider_options(thinking, limit),
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = tool_choice
        if response_format is not None:
            request["response_format"] = response_format
        return request

    async def stream_chat(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        budget = _RetryBudget()
        retried_empty = False
        state = _StreamState(self.model)
        try:
            # One deadline covers queued calls, retry waits and heartbeat-only streams.
            async with asyncio.timeout(settings.llm_timeout_seconds):
                while True:
                    request = self._request(
                        messages,
                        tools,
                        tool_choice,
                        thinking,
                        max_tokens,
                        response_format,
                    )
                    state = _StreamState(self.model)
                    try:
                        async with _semaphore:
                            stream = await self.sdk.chat.completions.create(**request)
                            async with stream:
                                state.capture_headers(stream.response.headers)
                                async for raw in stream:
                                    for chunk in state.feed(raw):
                                        yield chunk
                    except Exception as exc:
                        error = _to_llm_error(exc)
                        # A retry after output would show the user duplicate text.
                        wait = None if state.has_output else budget.next_wait(error)
                        logger.warning(
                            "LLM call failed: code=%s status=%s request_id=%s wait=%s",
                            error.code,
                            error.status,
                            error.request_id or state.request_id,
                            wait,
                            exc_info=not isinstance(exc, openai.OpenAIError),
                        )
                        if wait is None:
                            error.request_id = error.request_id or state.request_id
                            raise error from exc
                        # A waiting call holds no semaphore slot.
                        await asyncio.sleep(wait)
                        continue

                    if not state.is_empty_length:
                        for chunk in state.final_chunks():
                            yield chunk
                        return

                    logger.warning(
                        "LLM reply empty with finish_reason=length: "
                        "request_id=%s usage=%s",
                        state.request_id,
                        state.usage,
                    )
                    if retried_empty:
                        raise LLMError(
                            "empty_response",
                            _EMPTY_MESSAGE,
                            request_id=state.request_id,
                        )
                    retried_empty = True
                    thinking = False
        except TimeoutError as exc:
            raise LLMError(
                "timeout", _TIMEOUT_MESSAGE, request_id=state.request_id
            ) from exc


class EustellaClient(OpenAICompatibleClient):
    def _provider_options(self, thinking: bool, max_tokens: int) -> dict[str, Any]:
        return {
            "max_tokens": max_tokens,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": thinking}},
        }


class AzureClient(OpenAICompatibleClient):
    def _provider_options(self, thinking: bool, max_tokens: int) -> dict[str, Any]:
        # The gpt-5 family rejects max_tokens on chat completions.
        return {
            "max_completion_tokens": max_tokens,
            "reasoning_effort": self._effort(thinking),
        }

    @staticmethod
    def _effort(thinking: bool) -> str:
        if not thinking:
            return "low"
        effort = settings.azure_reasoning_effort
        return "medium" if effort == "low" else effort


def _sdk(base_url: str, api_key: str) -> openai.AsyncOpenAI:
    # max_retries=0: the SDK's own retries would multiply ours and hide them.
    return openai.AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
    )


def _build_live(provider: str) -> OpenAICompatibleClient:
    if provider == "azure":
        return AzureClient(
            _sdk(settings.azure_openai_base_url, settings.azure_openai_api_key),
            settings.azure_openai_model,
        )
    return EustellaClient(
        _sdk(settings.eustella_base_url, settings.eustella_api_key),
        settings.eustella_model,
    )


@lru_cache
def _build_client(provider: str, record: bool) -> LLMClient:
    if provider in ("fake", "replay"):
        if record:
            logger.warning("LLM_RECORD needs a live provider, not %s", provider)
        return FakeClient() if provider == "fake" else ReplayClient()
    live = _build_live(provider)
    return RecordingClient(live) if record else live


def get_llm_client() -> LLMClient:
    """Return the client for LLM_PROVIDER. One instance per provider and mode."""
    return _build_client(settings.llm_provider, settings.llm_record)

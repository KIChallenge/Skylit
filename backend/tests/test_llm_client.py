"""LLM client tests. A stub replaces AsyncOpenAI, so no test uses the network."""

import asyncio
import json
import logging
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from openai.types.chat import ChatCompletionChunk

from app.config import settings
from app.llm import client as client_module
from app.llm.client import AzureClient, EustellaClient, get_llm_client
from app.llm.fake import FakeClient
from app.llm.replay import RecordingClient, ReplayClient, request_key
from app.llm.types import LLMChunk, LLMError

MESSAGES = [{"role": "user", "content": "Hallo"}]
TOOLS = [
    {"type": "function", "function": {"name": name, "parameters": {}}}
    for name in ("escalate", "upsert_case_step", "prepare_form")
]
HEADERS = {
    "X-Request-Id": "req-123",
    "x-ratelimit-remaining-requests": "19",
    "content-type": "text/event-stream",
}


def raw_chunk(
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish: str | None = None,
    usage: dict[str, Any] | None = None,
) -> ChatCompletionChunk:
    """Build a real SDK chunk, so the tests follow the SDK's types."""
    choices = []
    if content is not None or tool_calls is not None or finish is not None:
        delta: dict[str, Any] = {"content": content}
        if tool_calls is not None:
            delta["tool_calls"] = tool_calls
        choices = [{"index": 0, "delta": delta, "finish_reason": finish}]
    return ChatCompletionChunk.model_validate(
        {
            "id": "chunk",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "stub",
            "choices": choices,
            "usage": usage,
        }
    )


USAGE = {
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15,
    "prompt_tokens_details": {"cached_tokens": 3},
}


def text_stream(*words: str) -> list[ChatCompletionChunk]:
    return [
        *[raw_chunk(content=word) for word in words],
        raw_chunk(content="", finish="stop"),
        raw_chunk(usage=USAGE),
    ]


def status_error(
    cls: type[openai.APIStatusError], status: int, code: str, retry_after: str = ""
) -> openai.APIStatusError:
    headers = {"x-request-id": "req-err"}
    if retry_after:
        headers["retry-after"] = retry_after
    response = httpx.Response(
        status,
        headers=headers,
        request=httpx.Request("POST", "http://stub/v1/chat/completions"),
    )
    return cls("raw provider text", response=response, body={"code": code})


class StubStream:
    """Behaves like openai.AsyncStream: iterable, closable, holds the response."""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self.response = SimpleNamespace(headers=httpx.Headers(HEADERS))
        self.closed = False

    async def __aenter__(self) -> "StubStream":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self.closed = True

    async def __aiter__(self):
        for item in self.items:
            if isinstance(item, Exception):
                raise item
            yield item


class StubCompletions:
    """Plays one scripted outcome per call and records the request."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.streams: list[StubStream] = []

    async def create(self, **request: Any) -> StubStream:
        self.calls.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        stream = StubStream(outcome)
        self.streams.append(stream)
        return stream


def stub_sdk(*outcomes: Any) -> tuple[Any, StubCompletions]:
    completions = StubCompletions(*outcomes)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def eustella(*outcomes: Any) -> tuple[EustellaClient, StubCompletions]:
    sdk, completions = stub_sdk(*outcomes)
    return EustellaClient(sdk, "eustella-test"), completions


async def drain(stream: Any) -> list[LLMChunk]:
    return [chunk async for chunk in stream]


@pytest.fixture(autouse=True)
def llm_settings(monkeypatch, tmp_path):
    """Fix the settings, because hackkit passes the real .env as environment."""
    monkeypatch.setattr(settings, "llm_max_retries", 2)
    monkeypatch.setattr(settings, "llm_max_tokens", 4096)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 120)
    monkeypatch.setattr(settings, "llm_fixtures_dir", str(tmp_path))
    monkeypatch.setattr(settings, "eustella_model", "eustella-test")
    monkeypatch.setattr(settings, "azure_openai_model", "azure-test")
    monkeypatch.setattr(settings, "azure_reasoning_effort", "low")
    client_module._build_client.cache_clear()
    yield
    client_module._build_client.cache_clear()


@pytest.fixture
def sleeps(monkeypatch) -> list[float]:
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)
    return recorded


# --- Streaming and request shape ---


async def test_stream_yields_text_usage_and_audit_data():
    client, completions = eustella(text_stream("Guten ", "Tag"))

    chunks = await drain(client.stream_chat(MESSAGES))

    assert [c.text for c in chunks if c.type == "text"] == ["Guten ", "Tag"]
    assert [c.type for c in chunks[-2:]] == ["usage", "finish"]
    finish = chunks[-1]
    assert finish.finish_reason == "stop"
    assert finish.model == "eustella-test"
    assert finish.request_id == "req-123"
    assert finish.rate_limit == {"x-ratelimit-remaining-requests": "19"}
    assert finish.usage.model_dump() == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "cached_tokens": 3,
    }
    assert completions.streams[0].closed


async def test_complete_returns_result_with_audit_data():
    client, _ = eustella(text_stream("Guten ", "Tag"))

    result = await client.complete(MESSAGES)

    assert result.text == "Guten Tag"
    assert result.request_id == "req-123"
    assert result.usage.cached_tokens == 3


async def test_eustella_request_options():
    client, completions = eustella(text_stream("a"), text_stream("b"))

    await drain(client.stream_chat(MESSAGES, thinking=True))
    await drain(client.stream_chat(MESSAGES, max_tokens=100, tools=TOOLS))

    first, second = completions.calls
    assert first["stream_options"] == {"include_usage": True}
    assert first["extra_body"] == {"chat_template_kwargs": {"enable_thinking": True}}
    assert "tools" not in first and "tool_choice" not in first
    assert second["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert second["max_tokens"] == 4096
    assert second["tools"] == TOOLS and second["tool_choice"] == "auto"


async def test_azure_request_options():
    sdk, completions = stub_sdk(text_stream("a"), text_stream("b"))
    client = AzureClient(sdk, "azure-test")

    await drain(client.stream_chat(MESSAGES, thinking=False))
    await drain(client.stream_chat(MESSAGES, thinking=True))

    first, second = completions.calls
    assert first["reasoning_effort"] == "low"
    assert second["reasoning_effort"] == "medium"
    assert first["stream_options"] == {"include_usage": True}
    assert first["max_completion_tokens"] == 4096
    assert "max_tokens" not in first and "extra_body" not in first


# --- Tool calls ---


async def test_tool_call_deltas_assemble_into_complete_calls():
    def call(index, id=None, name=None, arguments=None):
        return {
            "index": index,
            "id": id,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }

    client, _ = eustella(
        [
            raw_chunk(tool_calls=[call(0, "call_a", "escalate", "")]),
            raw_chunk(tool_calls=[call(1, "call_b", "find_office", '{"bund')]),
            raw_chunk(tool_calls=[call(0, arguments='{"reason_code":')]),
            raw_chunk(tool_calls=[call(1, arguments='esland": "Wien"}')]),
            raw_chunk(tool_calls=[call(0, arguments=' "no_source"}')]),
            raw_chunk(tool_calls=[], finish="tool_calls"),
            raw_chunk(usage=USAGE),
        ]
    )

    chunks = await drain(client.stream_chat(MESSAGES, tools=TOOLS))

    deltas = [c.tool_call for c in chunks if c.type == "tool_call"]
    assert len(deltas) == 5 and deltas[0].name == "escalate"
    finish = chunks[-1]
    assert finish.finish_reason == "tool_calls"
    assert [(t.id, t.name, t.arguments) for t in finish.tool_calls] == [
        ("call_a", "escalate", {"reason_code": "no_source"}),
        ("call_b", "find_office", {"bundesland": "Wien"}),
    ]


async def test_tool_call_name_fragments_assemble_per_index():
    fragments = [
        (0, "call_a", "esca", '{"reason_code":'),
        (1, "call_b", "prepare_", '{"form_id":'),
        (0, None, "late", '"no_source"'),
        (1, None, "form", '"pva_pflegegeld"}'),
        (0, None, None, "}"),
    ]
    client, _ = eustella(
        [
            raw_chunk(
                tool_calls=[
                    {
                        "index": index,
                        "id": id,
                        "type": "function",
                        "function": {"name": name, "arguments": arguments},
                    }
                ]
            )
            for index, id, name, arguments in fragments
        ]
        + [raw_chunk(tool_calls=[], finish="tool_calls")]
    )

    chunks = await drain(client.stream_chat(MESSAGES, tools=TOOLS))

    assert [c.tool_call.name for c in chunks if c.type == "tool_call"] == [
        fragment[2] for fragment in fragments
    ]
    assert [(t.id, t.name, t.arguments) for t in chunks[-1].tool_calls] == [
        ("call_a", "escalate", {"reason_code": "no_source"}),
        ("call_b", "prepare_form", {"form_id": "pva_pflegegeld"}),
    ]


@pytest.mark.parametrize("raw", ['{"a": ', "[1, 2]"])
async def test_invalid_tool_arguments_set_parse_error_without_raising(raw):
    fragment = {
        "index": 0,
        "id": "call_a",
        "type": "function",
        "function": {"name": "escalate", "arguments": raw},
    }
    client, _ = eustella(
        [raw_chunk(tool_calls=[fragment]), raw_chunk(tool_calls=[], finish="stop")]
    )

    result = await client.complete(MESSAGES, tools=TOOLS)

    assert result.tool_calls[0].parse_error
    assert result.tool_calls[0].arguments == {}
    assert result.tool_calls[0].raw_arguments == raw


async def test_tool_call_without_arguments_parses_to_empty_dict():
    fragment = {
        "index": 0,
        "id": "call_a",
        "type": "function",
        "function": {"name": "get_x", "arguments": ""},
    }
    client, _ = eustella([raw_chunk(tool_calls=[fragment], finish="tool_calls")])

    result = await client.complete(MESSAGES, tools=TOOLS)

    assert result.tool_calls[0].arguments == {}
    assert result.tool_calls[0].parse_error is None


# --- Retries ---


async def test_429_retry_honours_retry_after(sleeps):
    rate_limited = status_error(
        openai.RateLimitError, 429, "requests_per_minute", retry_after="6"
    )
    client, completions = eustella(rate_limited, text_stream("Hallo"))

    result = await client.complete(MESSAGES)

    assert result.text == "Hallo"
    assert sleeps == [6.0]
    assert len(completions.calls) == 2


async def test_429_after_all_retries_raises_german_message(sleeps):
    def rate_limited():
        return status_error(
            openai.RateLimitError, 429, "concurrency_limited", retry_after="6"
        )

    client, completions = eustella(rate_limited(), rate_limited(), rate_limited())

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert sleeps == [6.0, 6.0]
    assert len(completions.calls) == 3
    error = caught.value
    assert error.code == "concurrency_limited"
    assert error.status == 429
    assert error.retry_after == 6.0
    assert error.request_id == "req-err"
    assert error.message == (
        "Der Dienst ist gerade ausgelastet. "
        "Bitte versuchen Sie es in 6 Sekunden erneut."
    )


async def test_503_retries_without_retry_after_use_default_wait(sleeps):
    overloaded = status_error(openai.InternalServerError, 503, "overloaded")
    client, _ = eustella(overloaded, text_stream("Hallo"))

    assert (await client.complete(MESSAGES)).text == "Hallo"
    assert sleeps == [client_module.DEFAULT_RETRY_SECONDS]


async def test_retry_after_longer_than_timeout_raises_at_once(sleeps):
    daily = status_error(
        openai.RateLimitError, 429, "input_tokens_per_day", retry_after="40000"
    )
    client, completions = eustella(daily)

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert sleeps == []
    assert len(completions.calls) == 1
    assert caught.value.retry_after == 40000.0


async def test_502_retries_once(sleeps):
    def bad_gateway():
        return status_error(openai.InternalServerError, 502, "model_failure")

    client, completions = eustella(bad_gateway(), bad_gateway(), text_stream("x"))

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert caught.value.status == 502
    assert len(completions.calls) == 2


@pytest.mark.parametrize(
    ("cls", "status", "code"),
    [
        (openai.BadRequestError, 400, "invalid_media_url"),
        (openai.AuthenticationError, 401, "invalid_api_key"),
        (openai.APIStatusError, 402, "insufficient_credit"),
        (openai.PermissionDeniedError, 403, "account_suspended"),
    ],
)
async def test_client_errors_raise_without_retry(sleeps, cls, status, code):
    client, completions = eustella(status_error(cls, status, code))

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert len(completions.calls) == 1
    assert sleeps == []
    assert caught.value.status == status
    assert caught.value.code == code
    assert "raw provider text" not in caught.value.message


async def test_timeout_raises_user_message(sleeps):
    timeout = openai.APITimeoutError(request=httpx.Request("POST", "http://stub"))
    client, completions = eustella(timeout)

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert caught.value.code == "timeout"
    assert "antwortet gerade nicht" in caught.value.message
    assert len(completions.calls) == 1


@pytest.mark.parametrize(
    "stage", ["semaphore", "create", "retry", "heartbeats", "text"]
)
async def test_overall_deadline_covers_the_whole_call(monkeypatch, stage):
    semaphore = asyncio.Semaphore(1)
    monkeypatch.setattr(client_module, "_semaphore", semaphore)
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.05)
    monkeypatch.setattr(settings, "llm_max_retries", 100)
    calls = 0
    received = 0

    class DeadlineStream(StubStream):
        async def __aiter__(self):
            nonlocal received
            while True:
                received += 1
                yield raw_chunk(content="x") if stage == "text" else raw_chunk()
                await asyncio.sleep(0.001)

    stream = DeadlineStream([])

    async def create(**request):
        nonlocal calls
        calls += 1
        if stage == "create":
            await asyncio.Event().wait()
        if stage == "retry":
            await asyncio.sleep(0.01)
            raise status_error(
                openai.RateLimitError, 429, "rpm", retry_after="0.01"
            )
        return stream

    sdk = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    client = EustellaClient(sdk, "eustella-test")
    if stage == "semaphore":
        await semaphore.acquire()

    try:
        # The outer timeout prevents a broken deadline from hanging the test.
        with pytest.raises(LLMError) as caught:
            await asyncio.wait_for(client.complete(MESSAGES), timeout=1)

        assert caught.value.code == "timeout"
        assert "antwortet gerade nicht" in caught.value.message
        if stage == "semaphore":
            assert calls == 0
            assert semaphore.locked()
        else:
            assert calls >= 1
            assert not semaphore.locked()
        if stage in ("heartbeats", "text"):
            assert received > 1
            assert stream.closed
            assert caught.value.request_id == "req-123"
        if stage == "retry":
            assert calls >= 2
    finally:
        if stage == "semaphore":
            semaphore.release()

    # A timed-out waiter must not consume a later semaphore slot.
    async with asyncio.timeout(1):
        async with semaphore:
            pass


async def test_failure_after_first_delta_raises_without_retry(sleeps):
    """A retry here would repeat text the user already sees."""
    client, completions = eustella(
        [raw_chunk(content="Guten "), httpx.ReadError("connection lost")],
        text_stream("nie"),
    )

    seen: list[LLMChunk] = []
    with pytest.raises(LLMError):
        async for chunk in client.stream_chat(MESSAGES):
            seen.append(chunk)

    assert [c.text for c in seen] == ["Guten "]
    assert len(completions.calls) == 1
    assert completions.streams[0].closed


async def test_transport_error_before_first_delta_maps_to_llm_error(sleeps):
    client, _ = eustella([httpx.ReadError("connection lost")])

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert caught.value.code == "unavailable"


# --- Empty replies (eustella trap 1) ---


async def test_length_with_empty_content_retries_with_thinking_off():
    client, completions = eustella(
        [raw_chunk(content="", finish="length"), raw_chunk(usage=USAGE)],
        text_stream("Antwort"),
    )

    chunks = await drain(client.stream_chat(MESSAGES, thinking=True))

    assert [c.text for c in chunks if c.type == "text"] == ["Antwort"]
    first, second = completions.calls
    assert first["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
    assert second["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert [c.type for c in chunks].count("finish") == 1


async def test_second_empty_reply_raises():
    empty = [raw_chunk(content="", finish="length")]
    client, completions = eustella(empty, list(empty))

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES, thinking=True)

    assert caught.value.code == "empty_response"
    assert len(completions.calls) == 2


async def test_length_with_text_keeps_the_partial_answer():
    client, completions = eustella([raw_chunk(content="Teil", finish="length")])

    result = await client.complete(MESSAGES)

    assert result.text == "Teil"
    assert result.finish_reason == "length"
    assert len(completions.calls) == 1


# --- Real SDK over a mock transport ---


def real_sdk(handler: Any) -> openai.AsyncOpenAI:
    """Run the real SDK, so the stubs above cannot hide a wrong SDK assumption."""
    httpx2 = pytest.importorskip("httpx2")
    return openai.AsyncOpenAI(
        base_url="http://stub.test/v1",
        api_key="dummy",
        max_retries=0,
        http_client=openai.DefaultAsyncHttpxClient(
            transport=httpx2.MockTransport(handler)
        ),
    )


def sse(*events: dict[str, Any]) -> bytes:
    lines = [f"data: {json.dumps(event)}\n\n" for event in events]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


def sse_event(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
    return {
        "id": "c",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "stub",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


async def test_real_sdk_streams_tool_calls_and_captures_headers(sleeps):
    httpx2 = pytest.importorskip("httpx2")
    bodies: list[dict[str, Any]] = []

    def handler(request):
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return httpx2.Response(
                429,
                headers={"retry-after": "6", "x-request-id": "req-429"},
                json={"error": {"code": "concurrency_limited", "message": "busy"}},
            )
        fragment = {
            "index": 0,
            "id": "call_a",
            "type": "function",
            "function": {
                "name": "escalate",
                "arguments": '{"reason_code": "no_source"}',
            },
        }
        body = sse(
            sse_event({"content": "Hallo"}),
            sse_event({"tool_calls": [fragment]}, finish="tool_calls"),
            {
                "id": "c",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "stub",
                "choices": [],
                "usage": USAGE,
            },
        )
        return httpx2.Response(
            200,
            headers={
                "content-type": "text/event-stream",
                "X-Request-Id": "req-200",
                "x-ratelimit-remaining-tokens": "96000",
            },
            content=body,
        )

    client = EustellaClient(real_sdk(handler), "eustella-test")

    result = await client.complete(MESSAGES, tools=TOOLS, thinking=True)

    assert sleeps == [6.0]
    assert result.text == "Hallo"
    assert result.tool_calls[0].arguments == {"reason_code": "no_source"}
    assert result.request_id == "req-200"
    assert result.rate_limit == {"x-ratelimit-remaining-tokens": "96000"}
    assert result.usage.cached_tokens == 3
    sent = bodies[-1]
    assert sent["chat_template_kwargs"] == {"enable_thinking": True}
    assert sent["stream_options"] == {"include_usage": True}
    assert sent["max_tokens"] == 4096


async def test_real_sdk_maps_401_envelope_without_retry(sleeps):
    httpx2 = pytest.importorskip("httpx2")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx2.Response(
            401,
            headers={"x-request-id": "req-401"},
            json={"error": {"code": "invalid_api_key", "message": "bad key"}},
        )

    client = EustellaClient(real_sdk(handler), "eustella-test")

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert calls == 1
    assert caught.value.code == "invalid_api_key"
    assert caught.value.status == 401
    assert caught.value.request_id == "req-401"
    assert "bad key" not in caught.value.message


async def test_real_sdk_error_event_in_stream_maps_to_llm_error(sleeps):
    httpx2 = pytest.importorskip("httpx2")

    def handler(request):
        body = sse(sse_event({"content": "Hal"}), {"error": {"code": "overloaded"}})
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream", "x-request-id": "req-mid"},
            content=body,
        )

    client = EustellaClient(real_sdk(handler), "eustella-test")

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert caught.value.code == "overloaded"
    assert caught.value.request_id == "req-mid"


async def test_real_sdk_connection_failure_maps_to_llm_error(sleeps):
    httpx2 = pytest.importorskip("httpx2")

    def handler(request):
        raise httpx2.ConnectError("no route", request=request)

    client = EustellaClient(real_sdk(handler), "eustella-test")

    with pytest.raises(LLMError) as caught:
        await client.complete(MESSAGES)

    assert caught.value.code == "unavailable"


# --- Concurrency ---


async def test_semaphore_limits_concurrent_calls(monkeypatch):
    monkeypatch.setattr(client_module, "_semaphore", asyncio.Semaphore(1))
    active = 0
    peak = 0

    class SlowStream(StubStream):
        async def __aiter__(self):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            for item in self.items:
                yield item
            active -= 1

    class SlowCompletions(StubCompletions):
        async def create(self, **request: Any) -> StubStream:
            return SlowStream(text_stream("x"))

    sdk = SimpleNamespace(chat=SimpleNamespace(completions=SlowCompletions()))
    client = EustellaClient(sdk, "eustella-test")

    await asyncio.gather(*(client.complete(MESSAGES) for _ in range(3)))

    assert peak == 1


async def test_retry_wait_does_not_hold_the_semaphore(monkeypatch):
    semaphore = asyncio.Semaphore(1)
    monkeypatch.setattr(client_module, "_semaphore", semaphore)
    locked_during_sleep: list[bool] = []

    async def fake_sleep(seconds: float) -> None:
        locked_during_sleep.append(semaphore.locked())

    monkeypatch.setattr(client_module.asyncio, "sleep", fake_sleep)
    rate_limited = status_error(openai.RateLimitError, 429, "rpm", retry_after="1")
    client, _ = eustella(rate_limited, text_stream("x"))

    await client.complete(MESSAGES)

    assert locked_during_sleep == [False]


# --- Provider selection ---


def test_get_llm_client_picks_the_provider(monkeypatch):
    built: list[dict[str, Any]] = []

    def fake_sdk(**kwargs: Any) -> Any:
        built.append(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(client_module.openai, "AsyncOpenAI", fake_sdk)
    monkeypatch.setattr(settings, "llm_record", False)
    monkeypatch.setattr(settings, "eustella_base_url", "http://eustella.test/v1")
    monkeypatch.setattr(settings, "eustella_api_key", "dummy")

    for provider, expected in [
        ("fake", FakeClient),
        ("replay", ReplayClient),
        ("eustella", EustellaClient),
        ("azure", AzureClient),
    ]:
        monkeypatch.setattr(settings, "llm_provider", provider)
        assert isinstance(get_llm_client(), expected)

    eustella_args = built[0]
    assert eustella_args["base_url"] == "http://eustella.test/v1"
    assert eustella_args["timeout"] == 120
    # The SDK's own retries would multiply ours.
    assert eustella_args["max_retries"] == 0


def test_get_llm_client_wraps_only_live_providers_for_recording(monkeypatch):
    monkeypatch.setattr(client_module.openai, "AsyncOpenAI", lambda **_: None)
    monkeypatch.setattr(settings, "llm_record", True)

    monkeypatch.setattr(settings, "llm_provider", "eustella")
    assert isinstance(get_llm_client(), RecordingClient)
    monkeypatch.setattr(settings, "llm_provider", "fake")
    assert isinstance(get_llm_client(), FakeClient)


# --- Record and replay ---


async def test_replay_maps_request_uuids_across_fragments(tmp_path):
    old = "3f2b1c9e-7a44-4b1d-9c55-0123456789ab"
    new = "a1b2c3d4-0000-4111-8222-abcdefabcdef"
    unknown = "bbbbbbbb-0000-4111-8222-abcdefabcdef"
    first = [{"role": "user", "content": f"Dokument {old}"}]
    second = [{"role": "user", "content": f"Dokument {new}"}]
    arguments = json.dumps({"document_id": old, "other": unknown})
    split = arguments.index(old) + 12
    fragments = [
        {"index": 0, "id": "call_a", "type": "function", "function": {
            "name": "get_document", "arguments": arguments[:split]
        }},
        {"index": 0, "function": {"arguments": arguments[split:]}},
    ]
    live, _ = eustella([
        raw_chunk(content=f"Dokument {old[:12]}"),
        raw_chunk(content=old[12:]),
        raw_chunk(tool_calls=[fragments[0]]),
        raw_chunk(tool_calls=[fragments[1]], finish="tool_calls"),
    ])

    recorded = await drain(RecordingClient(live).stream_chat(first))
    replayed = await drain(ReplayClient().stream_chat(second))

    assert "".join(c.text or "" for c in recorded) == f"Dokument {old}"
    assert "".join(c.text or "" for c in replayed) == f"Dokument {new}"
    raw = "".join(c.tool_call.arguments for c in replayed if c.tool_call)
    assert json.loads(raw) == {"document_id": new, "other": unknown}
    call = replayed[-1].tool_calls[0]
    assert call.arguments == json.loads(raw)
    assert json.loads(call.raw_arguments) == json.loads(raw)
    fixture = (tmp_path / f"{request_key('eustella-test', first)}.json").read_text()
    assert old not in fixture
    assert unknown in fixture


async def test_replay_loads_old_fixture_without_placeholders(tmp_path):
    key = request_key("eustella-test", MESSAGES)
    fixture = {"key": key, "model": "eustella-test", "chunks": [
        {"type": "text", "text": "Alte Antwort"},
        {"type": "finish", "finish_reason": "stop", "model": "eustella-test"},
    ]}
    (tmp_path / f"{key}.json").write_text(json.dumps(fixture), encoding="utf-8")

    result = await ReplayClient().complete(MESSAGES)

    assert result.text == "Alte Antwort"
    assert result.model == "eustella-test"


async def test_record_then_replay_gives_identical_chunks(tmp_path):
    fragment = {
        "index": 0,
        "id": "call_a",
        "type": "function",
        "function": {"name": "escalate", "arguments": '{"reason_code": "no_source"}'},
    }
    live, _ = eustella(
        [
            raw_chunk(content="Grüß Gott"),
            raw_chunk(tool_calls=[fragment], finish="tool_calls"),
            raw_chunk(usage=USAGE),
        ]
    )

    recorded = await drain(RecordingClient(live).stream_chat(MESSAGES, tools=TOOLS))
    replayed = await drain(ReplayClient().stream_chat(MESSAGES, tools=TOOLS))

    assert replayed == recorded
    key = request_key("eustella-test", MESSAGES, TOOLS)
    fixture = json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8"))
    assert fixture["request_sha256"] == key
    assert "Grüß Gott" in (tmp_path / f"{key}.json").read_text(encoding="utf-8")


async def test_record_and_replay_keys_include_tool_choice_and_response_format(tmp_path):
    requests = [
        {"tool_choice": "auto"},
        {"tool_choice": "none"},
        {"tool_choice": "required"},
        {"tool_choice": {"type": "function", "function": {"name": "escalate"}}},
        {"tool_choice": "auto", "response_format": {"type": "json_object"}},
    ]
    live, _ = eustella(*(text_stream(f"Antwort {i}") for i in range(len(requests))))
    recorder = RecordingClient(live)

    for options in requests:
        await recorder.complete(MESSAGES, tools=TOOLS, **options)

    assert len(list(tmp_path.glob("*.json"))) == len(requests)
    for i, options in enumerate(requests):
        result = await ReplayClient().complete(MESSAGES, tools=TOOLS, **options)
        assert result.text == f"Antwort {i}"
        assert result.model == "eustella-test"


async def test_fixture_reads_and_writes_run_outside_the_event_loop(monkeypatch):
    event_loop_thread = get_ident()
    operations: list[str] = []
    read_bytes = Path.read_bytes
    write_text = Path.write_text

    def threaded_read(path, *args, **kwargs):
        assert get_ident() != event_loop_thread
        operations.append("read")
        return read_bytes(path, *args, **kwargs)

    def threaded_write(path, *args, **kwargs):
        assert get_ident() != event_loop_thread
        operations.append("write")
        return write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", threaded_read)
    monkeypatch.setattr(Path, "write_text", threaded_write)
    live, _ = eustella(text_stream("Antwort"))

    recorded = await RecordingClient(live).complete(MESSAGES)
    replayed = await ReplayClient().complete(MESSAGES)

    assert replayed == recorded
    assert operations == ["write", "read"]


async def test_replay_finds_fixtures_recorded_on_azure():
    sdk, _ = stub_sdk(text_stream("Azure-Antwort"))
    live = AzureClient(sdk, "azure-test")

    recorded = await drain(RecordingClient(live).stream_chat(MESSAGES))

    assert await drain(ReplayClient().stream_chat(MESSAGES)) == recorded


async def test_failed_stream_writes_no_fixture(tmp_path, sleeps):
    live, _ = eustella(status_error(openai.AuthenticationError, 401, "invalid_api_key"))

    with pytest.raises(LLMError):
        await drain(RecordingClient(live).stream_chat(MESSAGES))

    assert list(tmp_path.iterdir()) == []


async def test_replay_miss_falls_back_to_fake_and_logs_key(caplog):
    expected_key = request_key("eustella-test", MESSAGES)

    with caplog.at_level(logging.WARNING, logger="app.llm.replay"):
        result = await ReplayClient().complete(MESSAGES)

    assert result.model == "fake"
    assert expected_key in caplog.text


async def test_corrupt_fixture_falls_back_to_fake(tmp_path):
    key = request_key("eustella-test", MESSAGES)
    (tmp_path / f"{key}.json").write_text("{kaputt", encoding="utf-8")

    result = await ReplayClient().complete(MESSAGES)

    assert result.model == "fake"


def test_relative_fixtures_dir_starts_at_the_repo_root(monkeypatch):
    from app.config import REPO_ROOT
    from app.llm.replay import fixtures_dir

    monkeypatch.setattr(settings, "llm_fixtures_dir", "demo/fixtures")

    assert fixtures_dir() == REPO_ROOT / "demo" / "fixtures"


def _messages_with(uuid: str, iso: str, date: str, time: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": f"Heute ist {date}. Stand {iso}, {time} Uhr. Fall {uuid}.",
        },
        {
            "role": "tool",
            "tool_call_id": "call_a",
            "content": json.dumps({"draft_id": uuid, "created_at": iso}),
        },
        {"role": "user", "content": [{"type": "text", "text": f"Dokument {uuid}"}]},
    ]


def test_normalization_maps_uuids_dates_and_times_to_one_key():
    first = _messages_with(
        "3f2b1c9e-7a44-4b1d-9c55-0123456789ab",
        "2026-11-05T14:03:22.123+01:00",
        "2026-11-05",
        "14:03",
    )
    second = _messages_with(
        "A1B2C3D4-0000-4111-8222-ABCDEFABCDEF",
        "2027-01-31T08:59:01Z",
        "31.01.2027",
        "8:59:01",
    )

    assert request_key("m", first) == request_key("m", second)


def test_key_changes_with_content_tools_format_and_model():
    base = request_key("m", MESSAGES)

    assert base != request_key("m", [{"role": "user", "content": "Anders"}])
    assert base != request_key("m", MESSAGES, tools=TOOLS)
    assert base != request_key("m", MESSAGES, response_format={"type": "json_object"})
    assert base != request_key("other", MESSAGES)
    # An empty tool list is the same request as no tools.
    assert base == request_key("m", MESSAGES, tools=[])


async def test_replay_key_ignores_max_tokens():
    live, _ = eustella(text_stream("Antwort"))

    await drain(RecordingClient(live).stream_chat(MESSAGES, max_tokens=8000))
    result = await ReplayClient().complete(MESSAGES, max_tokens=4096)

    assert result.text == "Antwort"
    assert result.model == "eustella-test"


# --- Fake provider ---


def user(text: str) -> list[dict[str, Any]]:
    return [{"role": "user", "content": text}]


S2_PROMPT = (
    "Soll meine Mutter das Ondansetron höher dosieren, ihr ist noch immer schlecht?"
)
S1_INTAKE = (
    "Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr "
    "zurecht. Was muss ich tun?"
)
S1_DOCUMENT = "Ja, sie wohnt in Wien. Hier ist der Brief."
S3_PROMPT = "Meine Mutter hat plötzlich starke Atemnot."


async def test_fake_s2_emits_escalate_call():
    result = await FakeClient().complete(user(S2_PROMPT), tools=TOOLS)

    assert result.finish_reason == "tool_calls"
    call = result.tool_calls[0]
    assert call.name == "escalate"
    assert call.arguments["reason_code"] == "medical_question"
    assert call.arguments["target_kind"] and call.arguments["open_question"]
    assert call.parse_error is None


async def test_fake_s1_intake_asks_at_most_two_questions():
    result = await FakeClient().complete(user(S1_INTAKE), tools=TOOLS)

    assert result.tool_calls == []
    assert 1 <= result.text.count("?") <= 2


async def test_fake_s1_document_emits_case_step_and_form():
    result = await FakeClient().complete(user(S1_DOCUMENT), tools=TOOLS)

    assert [c.name for c in result.tool_calls] == ["upsert_case_step", "prepare_form"]
    step, form = result.tool_calls
    assert step.arguments["category"] == "form"
    assert step.arguments["status"] == "open"
    assert form.arguments["form_id"] == "pva_pflegegeld"
    assert form.arguments["values"]


async def test_fake_s3_answers_short_with_144():
    result = await FakeClient().complete(user(S3_PROMPT), tools=TOOLS)

    assert "144" in result.text
    assert result.tool_calls == []
    assert len(result.text) < 200


async def test_fake_default_is_a_short_german_answer():
    result = await FakeClient().complete(user("Guten Morgen"), tools=TOOLS)

    assert "Situation" in result.text
    assert result.tool_calls == []


async def test_fake_tool_deltas_match_the_final_call():
    chunks = await drain(FakeClient().stream_chat(user(S2_PROMPT), tools=TOOLS))

    fragments = [c.tool_call for c in chunks if c.type == "tool_call"]
    assert len(fragments) > 2
    raw = "".join(fragment.arguments for fragment in fragments)
    assert json.loads(raw) == chunks[-1].tool_calls[0].arguments
    assert chunks[-1].type == "finish"


async def test_fake_ends_the_tool_loop_after_tool_results():
    """The last user message stays the same in round 2. The fake must not loop."""
    messages = [
        *user(S2_PROMPT),
        {"role": "assistant", "content": None, "tool_calls": []},
        {"role": "tool", "tool_call_id": "call_fake_1", "content": "{}"},
    ]

    result = await FakeClient().complete(messages, tools=TOOLS)

    assert result.tool_calls == []
    assert "1450" in result.text


async def test_fake_respects_tool_choice_none_and_offered_tools():
    forced = await FakeClient().complete(
        user(S2_PROMPT), tools=TOOLS, tool_choice="none"
    )
    no_tools = await FakeClient().complete(user(S2_PROMPT))

    assert forced.tool_calls == [] and forced.text
    assert no_tools.tool_calls == [] and no_tools.text


async def test_fake_reads_text_from_multipart_content():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": S2_PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
            ],
        }
    ]

    result = await FakeClient().complete(messages, tools=TOOLS)

    assert result.tool_calls[0].name == "escalate"


async def test_fake_is_deterministic():
    first = await drain(FakeClient().stream_chat(user(S1_DOCUMENT), tools=TOOLS))
    second = await drain(FakeClient().stream_chat(user(S1_DOCUMENT), tools=TOOLS))

    assert first == second

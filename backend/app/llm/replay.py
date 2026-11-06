"""Offline demo: replay recorded LLM responses and record live ones (D-017)."""

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import aclosing
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from app.config import REPO_ROOT, settings
from app.llm.fake import FakeClient
from app.llm.types import BaseLLMClient, LLMChunk, LLMClient, Messages, Tools

logger = logging.getLogger(__name__)

# Order matters: a UUID holds digit groups, and a datetime holds a date and a time.
_PLACEHOLDERS = (
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
        "<uuid>",
    ),
    (
        re.compile(
            r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
            r"(?:Z|[+-]\d{2}:?\d{2})?"
        ),
        "<datetime>",
    ),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<date>"),
    # The context builder may write today's date in the German format.
    (re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b"), "<date>"),
    (re.compile(r"\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\b"), "<time>"),
)
_UUID = _PLACEHOLDERS[0][0]
_UUID_REFERENCE = re.compile(r"<uuid:(\d+)>")


def _request_uuids(
    messages: Messages, tools: Tools | None, response_format: Any, tool_choice: Any
) -> list[str]:
    request = json.dumps(
        [messages, tools or None, response_format, tool_choice],
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return list(dict.fromkeys(_UUID.findall(request)))


def _map_chunks(
    chunks: list[LLMChunk], uuids: list[str], *, record: bool
) -> list[LLMChunk]:
    chunks = [chunk.model_copy(deep=True) for chunk in chunks]
    lookup = {uuid: f"<uuid:{index}>" for index, uuid in enumerate(uuids)}

    def replace(value: str) -> str:
        if record:
            return _UUID.sub(
                lambda match: lookup.get(match.group(), match.group()), value
            )
        return _UUID_REFERENCE.sub(
            lambda match: uuids[int(match.group(1))]
            if int(match.group(1)) < len(uuids)
            else match.group(),
            value,
        )

    def map_value(value: Any) -> Any:
        if isinstance(value, str):
            return replace(value)
        if isinstance(value, dict):
            return {key: map_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [map_value(item) for item in value]
        return value

    def map_fragments(fragments: list[tuple[Any, str]]) -> None:
        if not fragments:
            return
        lengths = [len(getattr(obj, field)) for obj, field in fragments]
        combined = replace("".join(getattr(obj, field) for obj, field in fragments))
        offset = 0
        for index, (obj, field) in enumerate(fragments):
            end = (
                offset + lengths[index] if index < len(fragments) - 1 else len(combined)
            )
            setattr(obj, field, combined[offset:end])
            offset = end

    texts = [(chunk, "text") for chunk in chunks if chunk.text is not None]
    map_fragments(texts)
    indices = {chunk.tool_call.index for chunk in chunks if chunk.tool_call is not None}
    for index in indices:
        map_fragments(
            [
                (chunk.tool_call, "arguments")
                for chunk in chunks
                if chunk.tool_call is not None and chunk.tool_call.index == index
            ]
        )
    for chunk in chunks:
        for call in chunk.tool_calls:
            call.arguments = map_value(call.arguments)
            call.raw_arguments = replace(call.raw_arguments)
    return chunks


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        for pattern, placeholder in _PLACEHOLDERS:
            value = pattern.sub(placeholder, value)
        return value
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    return value


def request_key(
    model: str,
    messages: Messages,
    tools: Tools | None = None,
    response_format: dict[str, Any] | None = None,
    tool_choice: Any = "auto",
) -> str:
    """Hash the normalized request. `max_tokens` and `thinking` are not part of it."""
    normalized = _normalize(
        {
            "model": model,
            "messages": messages,
            "tools": tools or None,
            "response_format": response_format,
            "tool_choice": tool_choice,
        }
    )
    payload = json.dumps(
        normalized, sort_keys=True, ensure_ascii=False, default=str
    )
    return sha256(payload.encode()).hexdigest()


def fixtures_dir() -> Path:
    """Return the fixtures directory. A relative setting starts at the repo root."""
    return REPO_ROOT / settings.llm_fixtures_dir


class _Fixture(BaseModel):
    # Not named "key": secret scanners flag `"key": "<hash>"` as an API key.
    request_sha256: str = Field(validation_alias=AliasChoices("request_sha256", "key"))
    model: str
    chunks: list[LLMChunk]


def _load_chunks(key: str) -> list[LLMChunk] | None:
    path = fixtures_dir() / f"{key}.json"
    try:
        return _Fixture.model_validate_json(path.read_bytes()).chunks
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("LLM replay fixture unreadable: key=%s error=%s", key, exc)
        return None


def _save_chunks(key: str, model: str, chunks: list[LLMChunk]) -> None:
    directory = fixtures_dir()
    path = directory / f"{key}.json"
    temporary = path.with_suffix(".json.tmp")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fixture = _Fixture(request_sha256=key, model=model, chunks=chunks)
        temporary.write_text(
            fixture.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    except OSError as exc:
        logger.warning("LLM record failed: key=%s error=%s", key, exc)


class ReplayClient(BaseLLMClient):
    """Serve recorded responses. A miss falls back to `fake` and logs the key."""

    def __init__(self) -> None:
        self.model = settings.eustella_model
        self.fallback = FakeClient()

    async def stream_chat(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        # The key holds the model, and fixtures may come from either live provider.
        models = dict.fromkeys((settings.eustella_model, settings.azure_openai_model))
        keys = [
            request_key(m, messages, tools, response_format, tool_choice)
            for m in models
        ]
        for key in keys:
            chunks = await asyncio.to_thread(_load_chunks, key)
            if chunks is not None:
                uuids = _request_uuids(messages, tools, response_format, tool_choice)
                for chunk in _map_chunks(chunks, uuids, record=False):
                    yield chunk
                return

        logger.warning("LLM replay miss, falling back to fake: key=%s", keys[0])
        async with aclosing(
            self.fallback.stream_chat(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                thinking=thinking,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        ) as stream:
            async for chunk in stream:
                yield chunk


class RecordingClient(BaseLLMClient):
    """Wrap a live client and write each complete response as `<key>.json`."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.model = inner.model

    async def stream_chat(
        self,
        messages: Messages,
        tools: Tools | None = None,
        tool_choice: Any = "auto",
        thinking: bool = False,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        chunks: list[LLMChunk] = []
        async with aclosing(
            self.inner.stream_chat(
                messages,
                tools=tools,
                tool_choice=tool_choice,
                thinking=thinking,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        ) as stream:
            async for chunk in stream:
                chunks.append(chunk)
                yield chunk
        # A failed or abandoned stream never reaches this line, so no partial fixture.
        key = request_key(self.model, messages, tools, response_format, tool_choice)
        uuids = _request_uuids(messages, tools, response_format, tool_choice)
        mapped = _map_chunks(chunks, uuids, record=True)
        await asyncio.to_thread(_save_chunks, key, self.model, mapped)

# eustella API — what our code needs to know

eustella is a Viennese startup running models in the EU. We are in their closed beta.
The API is **OpenAI-compatible**: use the official `openai` Python SDK with a different base URL.

## Basics

| | |
|---|---|
| Base URL | `https://api.eustella.com/v1` |
| Model | `eustella-v1.5` |
| Auth | `Authorization: Bearer rk_…` (key prefix `rk_`) |
| Chat | `POST /v1/chat/completions` (OpenAI shape), streaming via SSE ending in `data: [DONE]` |
| Models | `GET /v1/models` → `max_output_tokens: 65536` for `eustella-v1.5` |
| Billing | prepaid euro balance; 402 `insufficient_credit` when empty |

```python
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url=settings.eustella_base_url, api_key=settings.eustella_api_key)
stream = await client.chat.completions.create(
    model=settings.eustella_model,
    messages=messages,
    tools=tools,
    stream=True,
    stream_options={"include_usage": True},
    max_tokens=settings.llm_max_tokens,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
```

## Supported (per their migration guide)
- Chat completions, streamed or not, `stream_options.include_usage`.
- Tool calling with `tools` and `tool_choice`.
- Structured output with `response_format` (`json_schema`).
- Images in user messages as `image_url` parts. Must be `data:` URLs or public `https` URLs on port 443 with a hostname (else 400 `invalid_media_url`).
- Also an Anthropic-Messages-compatible endpoint at `/v1/messages` (we don't use it).

## Not available
Embeddings, Responses API, image generation, TTS, Assistants, files, batch, fine-tuning, realtime.
Transcription, OCR and moderation exist **on request only**.
→ We run embeddings locally (fastembed) and voice input in the browser (Web Speech API).

## Traps

1. **Reasoning is on by default and counts toward `max_tokens`.** A small limit returns empty text with `finish_reason: "length"`. The reasoning is billed but not returned.
   - Keep `max_tokens` ≥ 4096.
   - Turn it off for fast chat turns: `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`.
   - Treat `finish_reason == "length"` with empty content as an error and retry once with thinking off.
2. **`temperature` and `top_p` are ignored.** Answers vary between runs. Don't rely on determinism; use the `fake` provider for deterministic tests.
3. **`n` must be 1.**
4. **The reference docs contradict the guide.** The endpoint reference types `content` as a string only and doesn't list `tools`. The guide says tools and images work. **Verify with the smoke test before relying on either.**
5. **Context window is not documented.** Ask eustella or find it by testing. Keep history trimmed.
6. **The balance must cover a hold for `max_tokens`.** Huge `max_tokens` on a low balance can fail.

## Rate limits (Explorer tier, per organisation, shared by all our keys)

| Limit | Value |
|---|---|
| Concurrent calls | **2** |
| Requests / minute | **20** |
| Input tokens / minute | 96,000 |
| Output tokens / minute | 15,360 |
| Daily | 9.16M input / 1.83M output (reset 00:00 UTC) |

- 429 codes: `concurrency_limited`, `requests_per_minute`, `input_tokens_per_minute`, `output_tokens_per_minute`, `input_tokens_per_day`, `output_tokens_per_day`, `body_limited`. 503 `overloaded`. All carry `Retry-After` (seconds).
- Headers on every call: `x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-remaining-output-tokens`, resets like `6s`, `1m30s`. Log them in the audit.
- Next tier (Voyager: 4 concurrent, 60 rpm) needs €50 of **paid and spent** credit. Granted credit doesn't count. We asked / should ask support@eustella.com for a temporary raise for the event.

**Team rules because of the limits:**
- One agent turn = 1 + up to 3 tool rounds = up to 4 requests. Three devs testing at once can hit 20 rpm quickly.
- Use `LLM_PROVIDER=fake` for UI work and most backend tests.
- During the jury slot, nobody else calls the API.

## Errors

OpenAI envelope: `{"error": {"type", "code", "message"}}`. Every response has `X-Request-Id`; log it.

| Status | Code | Our handling |
|---|---|---|
| 400 | `invalid_request_error`, `invalid_media_url` | no retry; log; SSE `error` |
| 401 | `missing_api_key`, `invalid_api_key` | no retry; health shows `llm: "unauthorized"` |
| 402 | `insufficient_credit` | no retry; SSE `error` "Guthaben aufgebraucht" (dev-facing) |
| 403 | `account_suspended` | no retry |
| 429 | see above | retry after `Retry-After`, up to `LLM_MAX_RETRIES` |
| 502 | model failure | retry once |
| 503 | `overloaded` | retry after `Retry-After` |

## Prompt caching (automatic)

- The cache matches the **prefix** of the rendered prompt; it only kicks in for prefixes of a few thousand tokens.
- Cached tokens show in `usage.prompt_tokens_details.cached_tokens` (final stream chunk with `include_usage`).
- Our rules: the stable system prompt goes first and stays byte-identical. Dynamic data (date, profile, case state) goes at the **end** of the system message. History is appended, never rewritten. See [architecture.md](architecture.md) §4.

## Fallback: organisers' Azure OpenAI

The organisers provide an Azure OpenAI endpoint (West Europe) with model `gpt-5-4-mini`, OpenAI-compatible at `.../openai/v1`.
Switch with `LLM_PROVIDER=azure`. Differences: reasoning via `reasoning_effort` instead of `chat_template_kwargs`; its own rate limits.
The endpoint URL and key come from the organisers (see `.env.example`); never commit them.

## Smoke test (run first, ~15 minutes)

`backend/scripts/smoke_eustella.py` (or curl). Record results in `docs/smoke-eustella.md`.

1. Plain chat → non-empty `choices[0].message.content`.
2. `stream: true` + `include_usage` → final chunk has `usage` with `prompt_tokens_details.cached_tokens`.
3. `tools` with one dummy function + a prompt that needs it → `tool_calls` returned, streamed tool-call deltas parse correctly.
4. User message with an `image_url` data URL of page 1 of `Entlassungsbefund.pdf` → the model reads the name "Anna Berger".
5. `response_format` json_schema → valid JSON.
6. `enable_thinking: false` vs default → compare time to first token.
7. Long prompt (~20k tokens) sent twice → second call shows `cached_tokens > 0`.
8. `GET /v1/models` → note limits.

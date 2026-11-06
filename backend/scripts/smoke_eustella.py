#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["openai>=1.40", "pymupdf>=1.24", "python-dotenv>=1.0"]
# ///
"""Smoke test for the eustella API. Writes docs/smoke-eustella.md.

Run with `make smoke`. Exit code 0: all checks ran and the report exists.
Exit code 2: no API key found. A failed check is a result, not a crash.

The script is standalone on purpose: it does not import the backend package.
It reads EUSTELLA_API_KEY, EUSTELLA_BASE_URL, EUSTELLA_MODEL and LLM_MAX_TOKENS
from the environment, then .env in the current dir, then .env in the main checkout.
"""

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf
from dotenv import dotenv_values
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    DefaultAsyncHttpxClient,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "docs" / "smoke-eustella.md"
PDF_PATH = REPO_ROOT / "backend" / "seed" / "documents" / "entlassungsbefund.pdf"

# Same defaults as .env.example. The environment and .env files override them.
DEFAULT_BASE_URL = "https://api.eustella.com/v1"
DEFAULT_MODEL = "eustella-v1.5"
PLACEHOLDER_KEY = "rk_your_key_here"

MIN_MAX_TOKENS = 4096
CHECK_TIMEOUT_SECONDS = 120.0
# 20 requests per minute are shared by the whole organisation.
REQUEST_SPACING_SECONDS = 3.5
MAX_REQUESTS = 14
PLANNED_REQUESTS = 10
MAX_RETRY_AFTER_SECONDS = 60.0
RETRYABLE_STATUS = {429, 502, 503}
NON_RETRYABLE_CODES = {
    "body_limited",
    "input_tokens_per_day",
    "output_tokens_per_day",
}
# These statuses say something about the feature, not about the account or load.
CONCLUSIVE_STATUS = {400, 404, 405, 415, 422}
LONG_PROMPT_SENTENCES = 800
THINKING_OFF = {"chat_template_kwargs": {"enable_thinking": False}}
KEY_PATTERN = re.compile(r"rk_[A-Za-z0-9._-]+")


@dataclass
class Settings:
    api_key: str
    base_url: str
    model: str
    max_tokens: int


@dataclass
class CallStats:
    label: str
    latency: float | None = None
    ttft: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    finish_reason: str | None = None
    request_id: str | None = None


@dataclass
class CheckResult:
    number: int
    name: str
    passed: bool = False
    notes: list[str] = field(default_factory=list)
    calls: list[CallStats] = field(default_factory=list)
    error_code: str | None = None
    http_status: int | None = None

    @property
    def inconclusive(self) -> bool:
        """True when the failure comes from the account, load or network."""
        if self.passed or self.error_code is None:
            return False
        return self.http_status not in CONCLUSIVE_STATUS


@dataclass
class StreamReply:
    text: str = ""
    tool_calls: dict[int, dict[str, Any]] = field(default_factory=dict)
    last_chunk_has_usage: bool = False
    stats: CallStats | None = None


def env_sources() -> list[dict[str, str | None]]:
    """Return the config sources in priority order."""
    sources: list[dict[str, str | None]] = [dict(os.environ)]
    paths = [Path.cwd() / ".env"]
    try:
        common_dir = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        paths.append((REPO_ROOT / common_dir).resolve().parent / ".env")
    except (OSError, subprocess.SubprocessError):
        pass
    for path in paths:
        if path.is_file():
            sources.append(dict(dotenv_values(path)))
    return sources


def load_settings() -> Settings | None:
    sources = env_sources()

    def lookup(name: str, default: str = "") -> str:
        for source in sources:
            value = (source.get(name) or "").strip()
            if value and value != PLACEHOLDER_KEY:
                return value
        return default

    api_key = lookup("EUSTELLA_API_KEY")
    if not api_key:
        return None
    try:
        max_tokens = int(lookup("LLM_MAX_TOKENS", str(MIN_MAX_TOKENS)))
    except ValueError:
        max_tokens = MIN_MAX_TOKENS
    return Settings(
        api_key=api_key,
        base_url=lookup("EUSTELLA_BASE_URL", DEFAULT_BASE_URL),
        model=lookup("EUSTELLA_MODEL", DEFAULT_MODEL),
        max_tokens=max(max_tokens, MIN_MAX_TOKENS),
    )


def seconds(value: float | None) -> str:
    if value is None:
        return "k. A."
    return f"{value:.2f}".replace(".", ",") + " s"


def build_long_prompt() -> str:
    """Build a fixed text of about 20k tokens. The text is the same in every run."""
    sentences = (
        f"Absatz {i}: Die fiktive Musterregel {i} beschreibt Schritt "
        f"{i * 7 % 13} für den Musterantrag {i * 31 % 97} im Testverfahren."
        for i in range(1, LONG_PROMPT_SENTENCES + 1)
    )
    return "Du liest einen fiktiven Testtext.\n" + "\n".join(sentences)


def render_page_as_data_url(path: Path) -> tuple[str, int]:
    with pymupdf.open(path) as document:
        png = document[0].get_pixmap(dpi=150).tobytes("png")
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}", len(png)


class SmokeRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.requests_used = 0
        self.spare_retries = MAX_REQUESTS - PLANNED_REQUESTS
        self.last_request_at: float | None = None
        self.last_headers: dict[str, str] = {}
        self.client = AsyncOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            timeout=CHECK_TIMEOUT_SECONDS,
            max_retries=0,
            http_client=DefaultAsyncHttpxClient(
                event_hooks={"response": [self._on_response]}
            ),
        )

    async def _on_response(self, response: Any) -> None:
        self.last_headers = dict(response.headers)

    def scrub(self, text: str) -> str:
        """Remove the key from any text that can reach stdout or the report."""
        text = text.replace(self.settings.api_key, "***")
        return KEY_PATTERN.sub("***", text)

    async def _pace(self) -> None:
        """Run one request at a time and keep below 20 requests per minute."""
        if self.requests_used >= MAX_REQUESTS:
            raise RuntimeError(f"Budget von {MAX_REQUESTS} Anfragen erreicht")
        if self.last_request_at is not None:
            elapsed = time.perf_counter() - self.last_request_at
            await asyncio.sleep(max(0.0, REQUEST_SPACING_SECONDS - elapsed))
        self.requests_used += 1
        self.last_request_at = time.perf_counter()
        self.last_headers = {}

    def _retry_delay(self, error: APIStatusError) -> float | None:
        if error.status_code not in RETRYABLE_STATUS or self.spare_retries <= 0:
            return None
        if error.code in NON_RETRYABLE_CODES:
            return None
        try:
            delay = float(error.response.headers.get("retry-after", "5"))
        except ValueError:
            delay = 5.0
        return delay if delay <= MAX_RETRY_AFTER_SECONDS else None

    async def _send(
        self, stats: CallStats, attempt: Callable[[], Awaitable[Any]]
    ) -> Any:
        """Send one call. The retries use only the spare part of the budget."""
        while True:
            await self._pace()
            started = time.perf_counter()
            try:
                value = await attempt()
            except APIStatusError as error:
                stats.request_id = error.response.headers.get("x-request-id")
                delay = self._retry_delay(error)
                if delay is None:
                    raise
                self.spare_retries -= 1
                await asyncio.sleep(delay)
            except BaseException:
                stats.request_id = self.last_headers.get("x-request-id")
                raise
            else:
                stats.latency = time.perf_counter() - started
                stats.request_id = self.last_headers.get("x-request-id")
                return value

    def _store_usage(self, stats: CallStats, usage: Any) -> None:
        if usage is None:
            return
        stats.prompt_tokens = usage.prompt_tokens
        stats.completion_tokens = usage.completion_tokens
        details = getattr(usage, "prompt_tokens_details", None)
        stats.cached_tokens = getattr(details, "cached_tokens", None)

    async def _stream_chat(
        self,
        result: CheckResult,
        label: str,
        messages: list[dict[str, Any]],
        *,
        thinking_off: bool = True,
        **options: Any,
    ) -> StreamReply:
        stats = CallStats(label)
        result.calls.append(stats)
        reply = StreamReply(stats=stats)
        extra_body = THINKING_OFF if thinking_off else None

        async def attempt() -> None:
            started = time.perf_counter()
            stream = await self.client.chat.completions.create(
                model=self.settings.model,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
                extra_body=extra_body,
                **options,
            )
            try:
                async for chunk in stream:
                    reply.last_chunk_has_usage = chunk.usage is not None
                    self._store_usage(stats, chunk.usage)
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    stats.finish_reason = choice.finish_reason or stats.finish_reason
                    delta = choice.delta
                    if (delta.content or delta.tool_calls) and stats.ttft is None:
                        stats.ttft = time.perf_counter() - started
                    reply.text += delta.content or ""
                    for tool_delta in delta.tool_calls or []:
                        call = reply.tool_calls.setdefault(
                            tool_delta.index,
                            {"name": "", "arguments": "", "fragments": 0},
                        )
                        function = tool_delta.function
                        if function and function.name:
                            call["name"] += function.name
                        if function and function.arguments:
                            call["arguments"] += function.arguments
                            call["fragments"] += 1
            finally:
                await stream.close()

        await self._send(stats, attempt)
        return reply

    # The eight checks follow docs/eustella-api.md, section "Smoke test".

    async def check_plain_chat(self, result: CheckResult) -> None:
        stats = CallStats("Chat")
        result.calls.append(stats)
        response = await self._send(
            stats,
            lambda: self.client.chat.completions.create(
                model=self.settings.model,
                messages=[
                    {"role": "user", "content": "Nenne die Hauptstadt von Österreich."}
                ],
                max_tokens=self.settings.max_tokens,
            ),
        )
        self._store_usage(stats, response.usage)
        choice = response.choices[0]
        stats.finish_reason = choice.finish_reason
        result.passed = bool((choice.message.content or "").strip())
        result.notes.append("Ohne Streaming, Reasoning im Standard.")
        if not result.passed:
            result.notes.append("Der Inhalt der Antwort ist leer.")

    async def check_stream_usage(self, result: CheckResult) -> None:
        reply = await self._stream_chat(
            result,
            "Stream",
            [{"role": "user", "content": "Zähle von 1 bis 5."}],
        )
        cached = reply.stats.cached_tokens
        result.passed = (
            bool(reply.text.strip()) and reply.last_chunk_has_usage
            and cached is not None
        )
        if not reply.last_chunk_has_usage:
            result.notes.append("Der letzte Chunk enthält kein `usage`.")
        elif cached is None:
            result.notes.append("`usage` enthält kein `cached_tokens`.")

    async def check_tools(self, result: CheckResult) -> None:
        tool = {
            "type": "function",
            "function": {
                "name": "get_office_hours",
                "description": "Liefert die Öffnungszeiten einer Stelle.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "Name der Stadt"},
                    },
                    "required": ["city"],
                },
            },
        }
        prompt = "Wann hat die Stelle in Wien geöffnet? Nutze das Tool."
        reply = await self._stream_chat(
            result,
            "Tool",
            [{"role": "user", "content": prompt}],
            tools=[tool],
        )
        if not reply.tool_calls:
            result.notes.append("Das Modell liefert keinen `tool_call`.")
            return
        call = reply.tool_calls[min(reply.tool_calls)]
        try:
            arguments = json.loads(call["arguments"])
        except json.JSONDecodeError:
            result.notes.append("Die Tool-Argumente sind kein gültiges JSON.")
            return
        result.passed = call["name"] == "get_office_hours" and isinstance(
            arguments, dict
        )
        result.notes.append(
            f"Tool `{call['name']}`, {call['fragments']} Argument-Deltas, JSON gültig."
        )

    async def check_image(self, result: CheckResult) -> None:
        data_url, png_size = render_page_as_data_url(PDF_PATH)
        reply = await self._stream_chat(
            result,
            "Bild",
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Wie heißt die Patientin in diesem Dokument? "
                            "Antworte nur mit dem Namen.",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        result.passed = "berger" in reply.text.casefold()
        result.notes.append(f"PNG mit {png_size // 1024} KB als Data-URL.")
        if not result.passed:
            result.notes.append(f"Antwort: {reply.text[:80]!r}.")

    async def check_json_schema(self, result: CheckResult) -> None:
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "stadt": {"type": "string"},
            },
            "required": ["name", "stadt"],
            "additionalProperties": False,
        }
        prompt = "Extrahiere Name und Stadt: Erika Musterfrau wohnt in Graz."
        reply = await self._stream_chat(
            result,
            "JSON",
            [{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "person", "strict": True, "schema": schema},
            },
        )
        try:
            data = json.loads(reply.text)
        except json.JSONDecodeError:
            result.notes.append("Die Antwort ist kein gültiges JSON.")
            return
        result.passed = (
            isinstance(data, dict)
            and set(data) == {"name", "stadt"}
            and all(isinstance(value, str) for value in data.values())
        )
        if not result.passed:
            result.notes.append("Das JSON passt nicht zum Schema.")

    async def check_thinking(self, result: CheckResult) -> None:
        messages = [
            {
                "role": "user",
                "content": "Erkläre in zwei Sätzen, was eine Sozialversicherung ist.",
            }
        ]
        off = await self._stream_chat(result, "Reasoning aus", messages)
        default = await self._stream_chat(
            result, "Reasoning Standard", messages, thinking_off=False
        )
        off_ttft, default_ttft = off.stats.ttft, default.stats.ttft
        result.passed = off_ttft is not None and default_ttft is not None
        if result.passed:
            result.notes.append(f"Differenz {seconds(default_ttft - off_ttft)}.")
        else:
            result.notes.append("Mindestens ein Aufruf liefert keinen Text.")

    async def check_cache(self, result: CheckResult) -> None:
        messages = [
            {"role": "system", "content": build_long_prompt()},
            {"role": "user", "content": "Antworte nur mit dem Wort OK."},
        ]
        await self._stream_chat(result, "Langer Prompt 1", messages)
        second = await self._stream_chat(result, "Langer Prompt 2", messages)
        result.passed = (second.stats.cached_tokens or 0) > 0
        if not result.passed:
            result.notes.append("Der zweite Aufruf zeigt keine `cached_tokens`.")

    async def check_models(self, result: CheckResult) -> None:
        stats = CallStats("Modelle")
        result.calls.append(stats)
        page = await self._send(stats, self.client.models.list)
        wanted = self.settings.model
        entry = next((item for item in page.data if item.id == wanted), None)
        if entry is None:
            names = ", ".join(item.id for item in page.data)
            result.notes.append(f"`{wanted}` fehlt. Liste: {names}.")
            return
        result.passed = True
        ignored = {"id", "object", "created", "owned_by"}
        limits = {
            key: value
            for key, value in entry.model_dump().items()
            if key not in ignored
        }
        result.notes.append(f"Felder: {json.dumps(limits, ensure_ascii=False)}.")
        header_limits = {
            key: value
            for key, value in self.last_headers.items()
            if key.startswith("x-ratelimit-")
        }
        if header_limits:
            text = json.dumps(header_limits, ensure_ascii=False)
            result.notes.append(f"Header: {text}.")

    async def run_check(
        self,
        number: int,
        name: str,
        check: Callable[[CheckResult], Awaitable[None]],
    ) -> CheckResult:
        result = CheckResult(number, name)
        try:
            await asyncio.wait_for(check(result), CHECK_TIMEOUT_SECONDS)
        except TimeoutError:
            result.error_code = "timeout"
            result.notes.append(
                f"Abbruch nach {CHECK_TIMEOUT_SECONDS:.0f} s."
            )
        except APIStatusError as error:
            result.http_status = error.status_code
            result.error_code = str(error.code or error.status_code)
            result.notes.append(f"HTTP {error.status_code}: {error.message[:160]}")
        except APITimeoutError:
            result.error_code = "timeout"
            result.notes.append("Die Anfrage läuft in den Timeout.")
        except APIConnectionError:
            result.error_code = "connection_error"
            result.notes.append("Die Verbindung zur API schlägt fehl.")
        except APIError as error:
            result.error_code = str(error.code or type(error).__name__)
            result.notes.append(f"API-Fehler: {error.message[:160]}")
        except Exception as error:  # noqa: BLE001 - a failed check is a result
            result.error_code = type(error).__name__
            result.notes.append(f"Fehler im Check: {error!r:.160}")
        if result.error_code:
            result.passed = False
        return result

    async def run_all(self) -> list[CheckResult]:
        checks = [
            ("Chat ohne Streaming", self.check_plain_chat),
            ("Streaming mit `usage`", self.check_stream_usage),
            ("Tool-Aufruf im Stream", self.check_tools),
            ("Bild als Data-URL", self.check_image),
            ("`json_schema`", self.check_json_schema),
            ("Reasoning aus und Standard", self.check_thinking),
            ("Prompt-Cache", self.check_cache),
            ("`GET /v1/models`", self.check_models),
        ]
        results = []
        try:
            for number, (name, check) in enumerate(checks, start=1):
                result = await self.run_check(number, name, check)
                results.append(result)
                outcome = "bestanden" if result.passed else "fehlgeschlagen"
                print(f"Check {number} {name}: {outcome}", flush=True)
                print(f"  {self.scrub(format_notes(result))}", flush=True)
        finally:
            await self.client.close()
        return results


def format_call(stats: CallStats) -> str:
    parts = [
        f"{stats.label}: Latenz {seconds(stats.latency)}",
        f"erstes Token {seconds(stats.ttft)}",
    ]
    if stats.prompt_tokens is not None:
        parts.append(
            f"Tokens {stats.prompt_tokens} ein, {stats.completion_tokens} aus, "
            f"{stats.cached_tokens if stats.cached_tokens is not None else 'k. A.'}"
            " gecacht"
        )
    if stats.finish_reason:
        parts.append(f"Ende `{stats.finish_reason}`")
    parts.append(f"X-Request-Id `{stats.request_id or 'k. A.'}`")
    return ", ".join(parts) + "."


def format_notes(result: CheckResult) -> str:
    parts = [format_call(stats) for stats in result.calls] + result.notes
    if result.error_code:
        parts.append(f"Fehlercode `{result.error_code}`.")
    return " ".join(parts)


def table_cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


FAILURE_CONSEQUENCES = {
    1: "Der Chat fehlt. Azure wird Primärmodell (`LLM_PROVIDER=azure`).",
    2: "Das Streaming oder `usage` fehlt. Azure wird Primärmodell, "
    "oder der Audit verzichtet auf Token-Zahlen.",
    3: "Tool-Aufrufe fehlen. Azure wird Primärmodell (`LLM_PROVIDER=azure`).",
    4: "Vision fehlt. Bild-Uploads nutzen den Tesseract-Fallback oder Azure.",
    5: "`json_schema` fehlt. Die Dokument-Extraktion nutzt Azure.",
    6: "Der Vergleich liefert keinen Wert. Der Plan behält "
    "`LLM_ENABLE_THINKING=false` und `LLM_MAX_TOKENS` ab 4096.",
    7: "Der Cache greift in diesem Test nicht. Der Plan rechnet nicht mit "
    "Einsparungen durch den Cache.",
    8: "Die Modell-Liste liefert keine Bestätigung. Der Plan nutzt weiter die "
    "Werte aus `docs/eustella-api.md`.",
}


def plan_consequences(results: list[CheckResult]) -> list[str]:
    lines = []
    for result in results:
        if result.passed:
            continue
        if result.inconclusive:
            lines.append(
                f"Check {result.number} ist nicht aussagekräftig "
                f"(`{result.error_code}`). Wiederholt den Test mit `make smoke`."
            )
        else:
            consequence = FAILURE_CONSEQUENCES[result.number]
            lines.append(f"Check {result.number}: {consequence}")
    thinking = results[5]
    if thinking.passed:
        off, default = thinking.calls[0].ttft, thinking.calls[1].ttft
        if off < default:
            lines.append(
                "`LLM_ENABLE_THINKING=false` bleibt Standard für Chat-Turns. "
                f"Das erste Token kommt {seconds(default - off)} früher "
                "(eine Messung)."
            )
        else:
            lines.append(
                "Reasoning aus bringt in dieser einen Messung keinen Vorteil. "
                "Die Einstellung bleibt, bis eine zweite Messung vorliegt."
            )
    if all(result.passed for result in results):
        lines.append("Alle Checks sind bestanden. Der Plan bleibt unverändert.")
    return lines


def render_report(
    results: list[CheckResult], settings: Settings, requests_used: int
) -> str:
    lines = [
        "# eustella-Smoke-Test",
        "",
        f"- Datum: {date.today().strftime('%d.%m.%Y')}",
        f"- Modell: `{settings.model}`",
        f"- Anfragen: {requests_used} von maximal {MAX_REQUESTS}",
        f"- `max_tokens`: {settings.max_tokens}",
        "- Reasoning: aus, außer in Check 1 und im Standard-Aufruf von Check 6.",
        "- Erzeugt mit `make smoke`. Jeder Wert ist eine Einzelmessung.",
        "",
        "| Check | Ergebnis | Notizen |",
        "|---|---|---|",
    ]
    for result in results:
        outcome = "Bestanden" if result.passed else "Fehlgeschlagen"
        name = f"{result.number}. {result.name}"
        lines.append(f"| {name} | {outcome} | {table_cell(format_notes(result))} |")
    lines += ["", "## Folgen für den Plan", ""]
    lines += [f"- {line}" for line in plan_consequences(results)]
    return "\n".join(lines) + "\n"


def main() -> int:
    settings = load_settings()
    if settings is None:
        print(
            "Kein EUSTELLA_API_KEY gefunden. Prüfe die Umgebung und die .env-Datei "
            "im Haupt-Checkout.",
            file=sys.stderr,
        )
        return 2
    runner = SmokeRunner(settings)
    results = asyncio.run(runner.run_all())
    report = runner.scrub(render_report(results, settings, runner.requests_used))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Bericht geschrieben: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

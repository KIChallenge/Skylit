# Architecture

## 1. System overview

```
┌──────────────────────────────┐        ┌───────────────────────────────────────────────┐
│ Browser / PWA (Next.js)      │  REST  │ Backend (FastAPI)                             │
│                              │ ─────► │                                               │
│  Chat · Mein Fall · Upload   │  SSE   │  api/ ──► services ──► orchestrator (tool loop)│──► LLM provider
│  Settings · Transparency     │ ◄───── │            │              │                    │    eustella | azure | fake
└──────────────────────────────┘        │            │              ├─► tools/ ──► providers/ (mock directories)
                                        │            │              │           └► forms/ (PDF fill)
                                        │            │              └─► guardrails/ (red flags, escalation)
                                        │            ├─► rag/ (fastembed, local) ──┐
                                        │            ├─► documents/ (PyMuPDF, vision extraction)
                                        │            └─► audit/                    │
                                        └──────────────────┬───────────────────────┘
                                                           ▼                       ▼
                                                 ┌───────────────────────────────────┐
                                                 │ Postgres 16 + pgvector            │
                                                 │ users, cases, messages, KB chunks │
                                                 └───────────────────────────────────┘
```

- The **browser never talks to the LLM** and never sees a key.
- The **backend owns all logic**: LLM calls, tools, guardrails, documents, forms, persistence.
- The **frontend owns presentation**: it renders text deltas and typed cards from the SSE stream.

## 2. Docker Compose services

| Service | Image / build | Port | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 | Volume `pgdata`. Healthcheck `pg_isready`. |
| `backend` | `./backend` (python:3.12-slim + uv) | 8000 | Runs `alembic upgrade head`, then seeds if empty, then `uvicorn`. Volumes: `models` (embedding cache), `uploads`. Depends on `db` healthy. |
| `frontend` | `./frontend` (node:22-alpine) | 3000 | `NEXT_PUBLIC_API_URL` baked at build time. |

All services read the root `.env`. Local dev without Docker also works: run `db` in Docker, backend with `uv run uvicorn app.main:app --reload`, frontend with `npm run dev`.

## 3. Backend layout

```
backend/
├── pyproject.toml / uv.lock
├── Dockerfile
├── alembic.ini, alembic/versions/
├── app/
│   ├── main.py              # FastAPI app, CORS, routers, lifespan (warm embedder)
│   ├── config.py            # pydantic-settings, the only place that reads env
│   ├── db.py                # async engine, session dependency
│   ├── deps.py              # current_user, db session, etc.
│   ├── api/                 # routers: health, auth, me, conversations, documents, cases, forms, appointments, escalations, audit, dev
│   ├── models/              # SQLAlchemy ORM models (one file per aggregate)
│   ├── schemas/             # Pydantic DTOs, incl. events.py (SSE) and cards.py
│   ├── services/            # business logic used by routers (conversation_service, case_service, …)
│   ├── llm/
│   │   ├── client.py        # provider-agnostic LLM client (eustella / azure / fake), retries, semaphore
│   │   ├── orchestrator.py  # the agent turn: context build → stream → tool loop → persist
│   │   ├── context.py       # builds the messages array (cache-friendly order)
│   │   ├── fake.py          # scripted provider for offline dev and tests
│   │   └── prompts/         # system.md, document_extraction.md, output_check.md
│   ├── tools/
│   │   ├── registry.py      # name → (input model, handler), OpenAI tool schema export
│   │   └── *.py             # one file per tool (see contracts.md §4)
│   ├── providers/           # interfaces + mock implementations
│   │   ├── base.py          # Protocols: OfficeDirectory, ProviderDirectory, AppointmentService, InsuranceStatusProvider, EmailService
│   │   └── mock_*.py        # JSON-backed demo implementations
│   ├── rag/
│   │   ├── embedder.py      # fastembed wrapper, model loaded once
│   │   ├── ingest.py        # CLI: markdown KB → chunks → embeddings → DB
│   │   └── retriever.py     # hybrid search: pgvector cosine + Postgres full-text (german)
│   ├── documents/
│   │   ├── pipeline.py      # upload → pages to images / text → extraction → store
│   │   └── extract.py       # vision call with json_schema output
│   ├── forms/
│   │   ├── registry.py      # form templates + field maps (our keys → AcroForm field names)
│   │   └── fill.py          # pypdf fill, flatten optional
│   ├── guardrails/
│   │   ├── red_flags.py     # deterministic pre-LLM check
│   │   └── escalation.py    # contacts lookup, handover summary builder
│   └── audit/
│       └── log.py           # audit(event_type, payload) helper
├── seed/                    # see docs/data.md
└── tests/
```

## 4. The agent turn (orchestrator)

`POST /api/conversations/{id}/messages` returns an SSE stream. One turn:

1. **Persist** the user message (+ attached `document_ids`).
2. **Red-flag check** on the user text. On a hit: emit `emergency`, write audit, set a flag that adds an emergency instruction to the context.
3. **Retrieve**: embed the user message (plus last assistant message for context), hybrid search top-k KB chunks.
4. **Build context** (`llm/context.py`), in this order for prefix caching:
   1. System message: the **stable** prompt (`system.md`) first, byte-identical across calls. Then, at the end of the same system message, the dynamic part: user profile (language, depth, Bundesland, insurer), current case state, today's date, emergency flag.
   2. Conversation history, unchanged, oldest first (trim the oldest turns beyond a token budget).
   3. Retrieved KB chunks and extracted document facts, as a system-labelled block right before the latest user message.
   4. The latest user message.
5. **Stream** the completion with `tools`. Forward text deltas as `text.delta`.
6. **Tool loop**: if the model returns `tool_calls`, emit `tool.called`, execute each handler (validated by its Pydantic input model), emit `tool.result` with a card, append the tool results, call the model again. **Max 3 rounds**, then force a text answer (`tool_choice: "none"`).
7. **Persist** assistant message, tool calls, cards, sources, usage. Emit `sources` and `message.completed`.
8. **Audit** every LLM call (model, tokens, cached tokens, latency, request id), every tool call, every guardrail trigger.

Errors: on 429/503 the client retries per `Retry-After` up to `LLM_MAX_RETRIES`. If it still fails, emit `error` with `retry_after` so the UI can show "Der Dienst ist gerade ausgelastet, ich versuche es in 6 s erneut".

### Thinking mode
- Default off for chat turns (`LLM_ENABLE_THINKING=false`): faster first token.
- On for document extraction and for building the first Leistungs-Bündel of a case (the orchestrator decides per call).

## 5. LLM client

`llm/client.py` exposes one async interface regardless of provider:

```python
class LLMClient(Protocol):
    async def stream_chat(self, messages, tools=None, tool_choice="auto",
                          thinking: bool = False, max_tokens: int | None = None,
                          response_format=None) -> AsyncIterator[LLMChunk]: ...
    async def complete(self, messages, ..., response_format=None) -> LLMResult: ...
```

| `LLM_PROVIDER` | Base URL | Thinking switch | Notes |
|---|---|---|---|
| `eustella` (default) | `https://api.eustella.com/v1` | `extra_body={"chat_template_kwargs": {"enable_thinking": bool}}` | See [eustella-api.md](eustella-api.md). |
| `azure` | organisers' Azure OpenAI endpoint (`/openai/v1`) | `reasoning_effort` (`low`/`medium`) | Fallback if eustella is down. Model `gpt-5-4-mini`. |
| `fake` | — | — | Scripted responses from `llm/fake.py`; deterministic; used by frontend dev and CI tests. |

- Both live providers use the official `openai` Python SDK (`AsyncOpenAI(base_url=..., api_key=...)`).
- A global `asyncio.Semaphore(LLM_MAX_CONCURRENCY)` guards all calls: the eustella Explorer tier allows 2 concurrent calls for the whole organisation.
- Always `stream_options={"include_usage": True}` so we log cached tokens.

## 6. RAG

- **Source**: curated markdown files in `backend/seed/kb/` with front matter (title, source_url, publisher, category, bundesland, valid_from). See [data.md](data.md).
- **Ingest** (`uv run python -m app.rag.ingest`): split by heading into chunks of ~300–500 tokens with 50-token overlap, embed with fastembed, upsert into `knowledge_chunks`. Idempotent (hash per chunk).
- **Embedding model**: `EMBEDDING_MODEL` (default `paraphrase-multilingual-MiniLM-L12-v2`, 384 dims). Runs on CPU inside the backend. Cached in the `models` volume. Loaded once at startup.
- **Retrieval**: hybrid. pgvector cosine top-20 + Postgres `to_tsvector('german', …)` top-20, merged with reciprocal rank fusion, top `RAG_TOP_K`. Full-text catches exact terms like "PAL080" or "Rezeptgebührenbefreiung" that embeddings blur.
- **Index**: HNSW on the embedding column, GIN on the tsvector.
- The model also has a `search_knowledge` tool for follow-up lookups mid-turn.

## 7. Documents pipeline

1. `POST /api/documents` (multipart): accept PDF, JPEG, PNG, HEIC→JPEG up to `MAX_UPLOAD_MB`.
2. Store the file under `UPLOAD_DIR/{document_id}`.
3. PDF: try text extraction with PyMuPDF. If text is present, use text; otherwise render pages to PNG (150 dpi).
4. Images: send to the LLM as `image_url` data URLs (vision). Fallback if vision is unavailable: local OCR with Tesseract (`tesseract-ocr-deu` in the Docker image).
5. Extraction call (thinking on, `response_format` = `json_schema` from contracts.md §5): administrative facts + explicit recommendations with verbatim quotes and section references.
6. Store `extracted` JSON on the document row; status `ready`. The chat references documents by id; `context.py` injects the extraction.

## 8. Forms

- `forms/registry.py` maps each template to its PDF and a **field map**: our semantic keys (`applicant.last_name`, `applicant.svnr`, `applicant.address.zip`, …) → AcroForm field names in that PDF.
- Build the field map once per form with a helper script that dumps field names (`uv run python -m app.forms.dump_fields <pdf>`). Commit the map.
- `fill.py` fills with pypdf, keeps the form editable (no flatten) so the user can complete it.
- The `prepare_form` tool returns which keys were filled, which are missing, and which must be filled by a doctor or the user.

## 9. Frontend layout

```
frontend/src/
├── app/
│   ├── layout.tsx, globals.css, manifest.ts (PWA)
│   ├── page.tsx                 # redirect → /login or /chat
│   ├── login/page.tsx           # persona picker
│   └── chat/[[...id]]/page.tsx  # chat + Mein Fall
├── components/
│   ├── chat/          # MessageList, MessageBubble, Composer (text, attach, camera, mic), ToolActivity, SourceChips
│   ├── cards/         # FormDraftCard, OfficeCard, ProviderListCard, AppointmentCard, EmailDraftCard, EscalationCard, DocumentSummaryCard
│   ├── case/          # CasePanel, CaseStep
│   ├── safety/        # EmergencyBanner
│   ├── settings/      # SettingsSheet (language, depth)
│   └── transparency/  # WhyDrawer (audit for one message)
└── lib/
    ├── api/           # client.ts (fetch wrapper, cookies), sse.ts (POST + stream parser), schema.d.ts (generated)
    ├── i18n/          # de.ts, de-simple.ts, en.ts
    └── fixtures/      # recorded SSE streams for UI dev without backend
```

- **Layout**: desktop = chat left, Mein Fall right. Mobile = chat full screen, Mein Fall as a bottom sheet / tab.
- **SSE client**: `EventSource` only supports GET, so `sse.ts` uses `fetch` with a `ReadableStream` reader and parses `event:` / `data:` lines.
- **Cards are rendered from typed `card` payloads**, never parsed out of model text.
- **Type generation**: `npm run gen:api` runs `openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/schema.d.ts`.

## 10. Security and privacy

- API key only in backend env. CORS limited to `BACKEND_CORS_ORIGINS`.
- Session: signed, HTTP-only cookie (`SECRET_KEY`), persona id inside. Mock auth, clearly labelled.
- Uploads: type and size check, stored outside the web root, served only to the owner.
- No real personal data anywhere. Synthetic personas only.
- Audit log holds no raw document content, only ids and summaries.

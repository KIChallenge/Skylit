# Workstreams — who builds what

> **Überholt.** Die hackkit-Tasks ersetzen diese Workstreams. Es gilt [PLAN.md](PLAN.md). Die Datei bleibt nur als Hintergrund.

Three people, three workstreams. Each person drives their own coding agents.
Ownership exists so agents don't overwrite each other. Contracts ([contracts.md](contracts.md)) are the interface between workstreams.

| Workstream | Short name | Branch prefix | Owner |
|---|---|---|---|
| **Brain** — LLM, agent loop, tools, guardrails, documents | `brain` | `brain/` | _name_ |
| **Platform** — backend foundation, DB, API, RAG, data, forms, mocks, Docker | `platform` | `platform/` | _name_ |
| **Experience** — frontend, PWA, knowledge-base content, demo and pitch | `ux` | `ux/` | _name_ |

Fill in the names.

## File ownership

| Path | Owner | Others may |
|---|---|---|
| `docker-compose.yml`, `backend/Dockerfile`, `backend/pyproject.toml` | Platform | add a dependency line (tell Platform) |
| `backend/app/main.py`, `config.py`, `db.py`, `deps.py` | Platform | add a router include / setting (tell Platform) |
| `backend/app/api/**` | Platform | Brain owns `api/conversations.py` message streaming route |
| `backend/app/models/**`, `backend/alembic/**` | Platform | request changes |
| `backend/app/schemas/**` | Platform; `events.py`, `cards.py`, `documents.py` → Brain | — |
| `backend/app/services/**` | Platform | — |
| `backend/app/llm/**` | Brain | — |
| `backend/app/tools/**` | Brain | Platform implements the provider/service functions tools call |
| `backend/app/guardrails/**` | Brain | — |
| `backend/app/documents/**` | Brain | — |
| `backend/app/rag/**` | Platform | Brain reads `retriever.search()` |
| `backend/app/providers/**`, `backend/app/forms/**` | Platform | — |
| `backend/app/audit/**` | Platform | everyone calls it |
| `backend/seed/kb/**`, `backend/seed/leistungen.json` | Experience | — |
| `backend/seed/*.json` (other), `seed/forms/**` | Platform | — |
| `backend/seed/fixtures/**` | Brain records, Experience consumes | — |
| `backend/tests/test_guardrails.py` | Brain | — |
| `frontend/**` | Experience | — |
| `docs/**` | everyone, for their area; `contracts.md` changes announced | — |
| `README.md` | Experience (final pass) | — |

## Brain

**Reads:** product.md, guardrails.md, architecture.md §4–5 and §7, contracts.md §2, §4, §5, eustella-api.md.

**Builds:**
1. Smoke test against eustella (`backend/scripts/smoke_eustella.py`), results into docs/smoke-eustella.md. **First thing.** Doesn't need the skeleton.
2. `llm/client.py`: provider-agnostic client (eustella, azure, fake), retries on 429/503 with `Retry-After`, global semaphore, usage + request-id capture.
3. `llm/fake.py`: scripted provider that emits realistic text deltas and tool calls for S1–S3. Lets the UI and tests run without burning rate limits.
4. `llm/prompts/system.md`: role, administrative intake strategy (ask only what the next step needs, max 2 questions), boundary, phrasing rules, escalation duty, source duty, language/depth handling, tool usage guidance.
5. `llm/context.py` + `llm/orchestrator.py`: the agent turn (architecture.md §4), SSE emission per contracts.md §2.
6. `api/conversations.py` streaming route `POST /api/conversations/{id}/messages`.
7. Tools: `upsert_case_step`, `set_case_summary`, `get_document`, `draft_email`, `escalate`, `update_profile`, and the wrappers for `search_knowledge`, `prepare_form`, `find_office`, `find_providers`, `propose_appointment`, `get_leistung`, `get_insurance_status` that call Platform's services.
8. `guardrails/red_flags.py` + `guardrails/escalation.py` (handover summary template).
9. `documents/`: upload pipeline, PDF→text/images, vision extraction with json_schema, Tesseract fallback.
10. `tests/test_guardrails.py` (unit + live), and recorded SSE fixtures for S1–S3 into `seed/fixtures/`.

**Done when:** S1, S2, S3 from product.md run end to end against the live model; the guardrail suite passes; fixtures exist.

## Platform

**Reads:** architecture.md (all), contracts.md §1, §3, §4, data.md.

**Builds:**
1. **Skeleton (first 60–90 min, unblocks everyone):** `docker-compose.yml` (db, backend, frontend), backend `pyproject.toml` with uv, FastAPI app with `/api/health`, `config.py`, `db.py`, Alembic init, Dockerfile. Push to `main` immediately.
2. DB models + first migration for all tables in contracts.md §3, pgvector extension.
3. Seeding: personas, offices, providers (synthetic), escalation contacts, leistungen, forms registry.
4. Auth: persona login, signed cookie, `current_user` dependency, `/api/me`, profile patch.
5. REST routers: conversations CRUD, case + step patch, documents upload/get (calls Brain's pipeline), forms, form-drafts PDF, appointments `.ics`, escalations, `/api/messages/{id}/audit`, dev routes, `/api/_schema/events`.
6. `audit/log.py` helper.
7. RAG: `rag/embedder.py` (fastembed, warm at startup), `rag/ingest.py` CLI, `rag/retriever.py` hybrid search.
8. Providers: `providers/base.py` protocols + JSON-backed mocks (`OfficeDirectory`, `ProviderDirectory`, `AppointmentService`, `InsuranceStatusProvider`).
9. Forms: `forms/dump_fields.py`, field maps for PVA Pflegegeld then Kur und Reha then Fahrtkosten, `forms/fill.py`.
10. Service functions the tools call: `retriever.search`, `leistungen.get`, `offices.find`, `providers.find`, `appointments.propose`, `forms.prepare`, `insurance.status`.
11. Tests: API smoke tests with `httpx.AsyncClient`, form fill test (filled PDF has the values), retriever test.

**Done when:** `docker compose up` on a clean checkout gives a working app with seeded data; `/docs` shows every endpoint; KB ingest runs; the Pflegegeld PDF fills correctly.

## Experience

**Reads:** product.md, guardrails.md §2–3, architecture.md §9, contracts.md §1–2, data.md §3–4.

**Builds:**
1. Next.js scaffold (TypeScript, Tailwind, shadcn/ui), `lib/api/client.ts`, `lib/api/sse.ts`, `npm run gen:api`.
2. Develop against **fixtures** first (`lib/fixtures/` copies of `seed/fixtures/*.sse`, or `/api/dev/stream-fixture/{name}`), then switch to the live backend.
3. Login (persona picker), chat page, message list with markdown, streaming text, tool activity chips, source chips.
4. Cards: form draft (filled/missing, download), office, provider list, appointment (+ .ics), email draft (copy / mailto), escalation (phone tap-to-call, handover summary copy), document summary, Leistung.
5. Mein Fall panel (desktop side panel, mobile bottom sheet), step tick-off via PATCH.
6. Upload: file picker + camera capture (`<input type="file" accept="image/*,application/pdf" capture="environment">`), processing state, polling.
7. Emergency banner, settings sheet (language, depth), i18n strings (de, de-simple, en).
8. "Warum diese Antwort?" drawer from `/api/messages/{id}/audit`.
9. PWA manifest + icons. Voice input (Web Speech API) if time allows.
10. **Knowledge base content** (`seed/kb/**`, `seed/leistungen.json`) per data.md §4, with your agents. Start this in parallel early; Platform's ingest needs it.
11. Demo script, backup screen recording, README final pass, pitch slides.

**Done when:** S1–S5 are demoable on desktop and phone width; KB covers data.md §4; README meets the organiser requirements.

## Timeline (Thu 5 Nov → Fri 6 Nov)

| By | Milestone | Brain | Platform | Experience |
|---|---|---|---|---|
| Thu 16:30 | **M0 — foundations** | smoke test done, results in docs/smoke-eustella.md | skeleton on `main`, compose up works, `/api/health` | Next.js scaffold, layout shell, KB curation started |
| Thu 20:00 | **M1 — first end-to-end** | orchestrator streams text from eustella, `upsert_case_step` + `escalate` work, fake provider | models + migration, auth, conversations API, seeding | chat UI renders live stream + case panel |
| Fri 01:00 | **M2 — Must features** | all tools, red flags, guardrail suite, document extraction | RAG ingest + retrieval, offices/providers, Pflegegeld form fill, audit | all cards, upload, emergency banner, settings |
| Fri 06:00 | **M3 — Should features** | prompt tuning on S1–S5, live guardrail run | Kur und Reha + Fahrtkosten forms, `.ics`, dev reset | transparency drawer, mobile polish, PWA, KB complete |
| Fri 08:00 | **Code freeze** | — | — | — |
| Fri 08:00–09:30 | **Rehearse** | 3× full demo run, record backup video, copy to public `KIChallenge/Skylit` (no `.env`, no organiser docx), final README |
| Fri 10:00 | **Fachjury** | 15 minutes: problem → live S1 → S2/S3 → architecture + `/docs` + transparency → limits and next steps |

Sleep in shifts. One person awake per milestone is enough to keep agents moving.

## Integration rules

- Platform pushes the skeleton **before** anyone else creates backend files.
- Merge to `main` whenever your piece works end to end. Pull often.
- If you need something from another workstream that doesn't exist yet: write against the contract with a stub, mark `TODO(<owner>)`, tell them.
- Contract change = edit contracts.md + code in one commit + message in the team chat.
- Before merging: `uv run ruff check`, `uv run pytest -m "not live"` (backend) or `npm run lint && npm run build` (frontend).

## Kickoff prompts for your agent

Paste one of these as the first message to your coding agent.

**Brain**
> You are working on workstream **Brain** of the SV KI-Lotse repo. Read `AGENTS.md`, then `docs/workstreams.md` (section Brain) and every doc it lists. Respect file ownership. Start with the eustella smoke test (`docs/eustella-api.md` → Smoke test); the API key is in `.env`. Then build `backend/app/llm/client.py` and `fake.py`. Work on a branch `brain/<topic>`. Ask me before changing anything in `docs/contracts.md`.

**Platform**
> You are working on workstream **Platform** of the SV KI-Lotse repo. Read `AGENTS.md`, then `docs/workstreams.md` (section Platform) and every doc it lists. Respect file ownership. Start with the skeleton: `docker-compose.yml` (pgvector/pgvector:pg16, backend, frontend placeholder), backend with uv, FastAPI `/api/health`, `config.py` reading every variable in `.env.example`, Alembic init. Get `docker compose up` working, then push to `main`. Ask me before changing anything in `docs/contracts.md`.

**Experience**
> You are working on workstream **Experience** of the SV KI-Lotse repo. Read `AGENTS.md`, then `docs/workstreams.md` (section Experience) and every doc it lists. Respect file ownership. Scaffold `frontend/` with Next.js (App Router, TypeScript, Tailwind, shadcn/ui). Build the chat layout and an SSE client per `docs/contracts.md` §2 against a hand-written fixture until the backend is ready. UI text German, simple, calm. Ask me before changing anything in `docs/contracts.md`.

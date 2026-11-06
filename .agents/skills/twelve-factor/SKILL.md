---
name: twelve-factor
description: Twelve-Factor App rules (https://12factor.net) for this hackathon app, as concrete do/don't rules plus a checklist. Use before scaffolding, and whenever you add or change config or env vars, dependencies, an LLM provider or other backing service, the server or port, logging, background work, data files, scripts or migrations. Also use when reviewing a diff or a PR.
---

# Twelve-factor rules for this app

Every change must keep the app runnable from a clean clone on any teammate's laptop and on the demo machine. The only steps allowed are: copy `.env.example` to `.env`, fill it in, and run the one documented run command. Each factor below says what that means in practice. Run the checklist at the end before you finish a task.

If a task seems to need a break from a factor, stop and say so in your summary. Do not quietly work around it. A justified exception goes into `docs/DECISIONS.md`.

## I. Codebase: one repo, many deploys
- This repo is the only codebase. Local runs, the demo machine and any hosted deploy run the same commit and differ only in config.
- No environment branches, no copied folders like `app_v2/` or `demo/`, no `if hostname == ...`.

## II. Dependencies: declare and isolate
- Declare every dependency in the manifest (`pyproject.toml`, `package.json`, …) and commit the lockfile (`uv.lock`, `package-lock.json`, …).
- Run inside isolation (`uv run`, a venv, `node_modules`). Never depend on a globally installed package.
- Do not call system tools (`ffmpeg`, `tesseract`, `pdftotext`, …) unless they are documented under the README's dependencies section and checked at startup with a clear error.
- A new dependency is a decision: prefer what is already installed, and log real additions with the `decision` command.

## III. Config: store config in the environment
- Everything that can differ between laptops or deploys comes from environment variables: API keys, the LLM provider and model, base URLs, ports, file paths, feature toggles.
- Read env vars in **one** config module (for example `config.py` or `src/config.ts`). Validate them at startup and fail fast with a message that names the missing variable. Everything else imports from that module.
- Every variable is in `.env.example` with a placeholder and a one-line comment, and in the README's configuration section. `hackkit check` fails on undocumented variables.
- The LLM client takes provider, model, key and base URL from config. Switching to the organizers' models must be a `.env` change only.
- Never commit `.env` or a secret. Never put secrets in frontend code or in build-time public variables (`VITE_*`, `NEXT_PUBLIC_*`): call the LLM from the backend.
- Never group config into named environments in code (no `config_prod.py`, no `if ENV == "production"` blocks that switch values).

## IV. Backing services: attached resources
- LLM APIs, databases, vector stores, object storage and external APIs are reached through a URL or key from config.
- Wrap each service in one small client module (`llm.py`, `db.py`, …). Swapping a provider changes that module or the config, nothing else.
- Every call to an external service has a timeout and a clear error. The demo must survive a slow LLM.

## V. Build, release, run: separate stages
- Build (install, compile, bundle) produces an artifact. Release = artifact + config. Run starts the app.
- Running the app never installs packages, downloads models or rewrites source files. Put any download in a documented one-off script (factor XII).
- Nothing environment-specific is baked into the build output.

## VI. Processes: stateless
- Anything that must survive a restart goes to a backing service or a file under a configured data directory. In-memory state is a per-request cache only.
- Do not keep sessions, uploads or job results in a module-level dict. A restart during the demo must not lose the demo state that matters.
- Generated files go to a configured, git-ignored path, never next to the source.

## VII. Port binding
- The app serves HTTP itself on `PORT` from the environment (default documented in `.env.example`) and binds `0.0.0.0` when it must be reachable from another laptop.
- No hard-coded `localhost:3000` in code. The frontend reaches the backend through a relative path or a configured base URL.

## VIII. Concurrency: scale out by process type
- Separate process types (web, worker) are separate commands, each documented in the README. Do not fork, daemonize or write PID files.
- Assume two instances may run at once: writes are idempotent or conflict-safe.

## IX. Disposability: fast start, graceful stop
- Start in seconds. Load big models or indexes lazily or in a one-off build script, not at import time.
- Handle Ctrl+C and SIGTERM: finish or abandon the request, close connections, exit.
- Long jobs are safe to retry and never leave half-written files (write to a temp file, then rename).

## X. Dev/prod parity
- Use the same backing services locally and in the demo. Do not use SQLite locally and Postgres in the demo.
- Any LLM stand-in is selected through config, never by editing code. `LLM_PROVIDER=replay` (recorded responses from `demo/fixtures/`) is the planned offline demo fallback, and it goes through the same client module as the real providers.
- Merge small changes often. `main` always runs.

## XI. Logs: event streams
- Write logs to stdout or stderr, one event per line, with a level. Use the language's logging module, not stray `print`s.
- Never write or rotate log files inside the app.
- Never log secrets, full prompts with personal data, or raw user records. Log IDs and sizes instead.

## XII. Admin processes: one-off scripts
- Seeding, synthetic data generation, index building, migrations and evals are scripts in the repo (`scripts/`, `make seed`, `uv run python -m app.seed`). They use the same config module and dependencies as the app.
- They are safe to run twice. Their commands are in the README.
- No admin endpoints and no hand-editing of data files.

## Checklist: run it before you finish
- [ ] No hard-coded key, URL, host, port, model name or path. New config is read in the config module, validated, and added to `.env.example` and the README.
- [ ] No secret in the diff, in frontend code or in logs.
- [ ] New dependencies are in the manifest, the lockfile is updated, and system tools are documented.
- [ ] External calls go through their client module and have a timeout and error handling.
- [ ] No state that matters lives in process memory or next to the source.
- [ ] The app still starts with the single README run command on `PORT`.
- [ ] Logs go to stdout or stderr with no secrets or personal data.
- [ ] New one-off tasks are scripts with a README entry and are safe to rerun.
- [ ] The test command for this task passes.

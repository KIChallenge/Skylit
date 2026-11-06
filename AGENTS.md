<!-- managed by hackkit — edit the packs or hackkit.toml, then run `hackkit sync` -->

# Project rules for all coding agents

Claude Code, Codex and Antigravity CLI all read this file. Follow it exactly. Teammates run other agents on other laptops with the same rules.

## Event

- Event: KI-Challenge 2026 — Dachverband der österreichischen Sozialversicherungsträger
- Language for UI text, README and docs: `de`. Code, identifiers and commit messages stay in English.
- The code repo is **public**. Never commit API keys, tokens, passwords, `.env` files, personal data or confidential documents.
- Domain: Austrian health and social insurance (Sozialversicherung). The jury and users speak German.
- Three use cases are presented on-site. The team may switch use case during the challenge.
- Data comes from the SV-Box. It is public and may be redistributed.
- Never use real personal health or social insurance data. Use synthetic or anonymized data only.
- The Fachjury visits each team for about 15 minutes. The top team per use case presents to the Finaljury.
- Document methods and key technical decisions so the jury can follow them.

## Working rules

- What we build is in `docs/PLAN.md`. Read it before you start a task. Build only what the plan and your task describe.
- Secrets live only in `.env` (git-ignored). Document every variable in `.env.example` with a dummy value.
- A gitleaks pre-commit hook blocks secrets. Never bypass it. If it fires, remove the secret.
- Make small commits with clear messages. Pull and rebase before you push.
- Touch only the files your task names. Ask before you change shared files (config, dependencies, entry points).
- Every feature needs a way to run it from a clean clone. Keep the run steps in the README current.
- Headless workers may run only `make` and `npm` outside their sandbox. Run backend commands through `make` targets (`make test`, `make lint`, `make smoke`, `make eval SET=<name>`). If a command has no target, say so in your summary.
- Log each important technical decision in `docs/DECISIONS.md` (use the `decision` command): what, why, alternatives, risks.
- Prefer boring, well-known libraries. Look up current APIs with the context7 MCP server instead of guessing.
- When you are unsure about domain facts, say so. Never invent regulations, numbers or sources.
- Read every setting (keys, LLM provider and model, URLs, `PORT`) from environment variables in one config module. No hard-coded keys, URLs, ports or model names. The `twelve-factor` skill has the details when you add config, services or scripts.

## Writing style (STE-100)

Every agent writes this way: replies, task summaries, PR and commit text, issue comments and docs. Apply it in English and in `de`. UI text follows the UI rules and the users' domain words.

- One idea per sentence. Maximum 20 words per sentence.
- Use active voice. Name the actor: "the script deletes the file", not "the file is deleted".
- Use the imperative for instructions: "Run `make test`."
- Use one term for one concept. Do not vary wording for style. If you call it "the handler", it stays "the handler".
- Keep technical terms exact. Do not simplify a precise term into a vague one.
- Put warnings before the step they apply to, not after.
- State the fact first, then the reason. No lead-in.

Do not:

- Restate the question.
- Open with praise, agreement or filler ("Great question", "You're right", "Let me help you with that").
- Summarise a change the reader can see in the diff. A worker's end summary still lists what changed, one line per change.
- Stack hedges ("it might possibly be worth considering"). Say the thing, or say you are unsure.
- List caveats nobody asked about.

If you do not know something, write "I don't know" and stop.
If a request is ambiguous and a human is in the session, ask one question and wait. A headless worker can't ask: it picks the most likely reading, names that assumption in its summary and finishes the task.

## Demo first

- The demo is the product. Every task must make the jury demo better or more reliable.
- The demo script lives in `docs/PITCH.md`. Build exactly what the demo shows, nothing more.
- Keep a working demo on `main` at all times. Never merge a change that breaks the demo flow.
- Use the playwright MCP server to click through the UI and check the demo flow after UI changes.

### The demo must not fail live

- The demo flow has an end-to-end Playwright test (the `demo-check` command writes it). Steps not built yet are marked `test.fixme`. It runs on `main` after every merge round and must be fully green at feature freeze.
- `LLM_PROVIDER=replay` serves recorded LLM responses from `demo/fixtures/`, so the demo runs with no network and no API quota. `LLM_RECORD=1` records real responses there. Re-record after every prompt change.
- The demo uses a fixed, seeded synthetic dataset that loads the same way every time.
- Keep the app deployed at a public URL and keep the single local run command working as the fallback.
- Every external call (LLM, APIs, file parsing) has a timeout and a user-facing error message. A failed call never crashes the page.

### Jury criteria

- Methodik sowie Daten- und KI-Qualität
- Nutzen und Wirkung
- Umsetzbarkeit und Time-to-Impact
- Transparenz und verantwortungsvoller KI-Einsatz
- Nutzbarkeit und Kommunikation
- Innovationsgrad

### Required README sections

- Beschreibung und Lösungsansatz
- Ausführung
- Abhängigkeiten und Voraussetzungen
- Konfiguration
- Bekannte Einschränkungen und offene Punkte

## UI and design

The jury judges what it sees. A polished, consistent, fast UI wins over extra features.

- The design system lives in `docs/DESIGN.md` and one tokens file (CSS variables or the Tailwind theme). Run the `design-system` command once, before any feature UI. Until it is merged, build no screens.
- Use only design tokens. No hard-coded hex colours, pixel font sizes or one-off spacing. If a token is missing, add it to the tokens file and `docs/DESIGN.md`.
- Use only the shared components (`components/ui/`, shadcn/ui by default). Compose them; do not hand-roll a second button, card or input. Never mix in another component library.
- Icons come from one set only (lucide by default).
- Design for the demo screen first: 1440×900 laptop and 1920×1080 projector. Light theme, high contrast: projectors wash out dark themes and pale greys.
- One primary action per screen. The AI result is the largest, clearest thing on its screen.
- Every async step has a loading state (skeleton, or streamed text with a progress line), an empty state and a readable error state with a retry. Never show a blank screen, a raw error or a stack trace.
- Stream LLM output when the user waits more than one second.
- UI text is in `de`, written in the users' domain words. Format dates, numbers and currency for that locale. No lorem ipsum, no "TODO", no developer jargon on screen.
- Every screen the jury sees shows realistic synthetic data, never empty tables or "test 123".
- The transparency panel (sources with page, model name, confidence) is a designed component that matches the rest of the UI. Show confidence with a label and a colour, never colour alone.
- Basics the jury notices: visible focus, labels on inputs, AA contrast, a product name, a favicon and a page title.
- Motion only where it explains a change. Durations, easings and the press scale come from the `better-ui` skill.

### UI skills

- Load these skills for UI work: `better-ui` (surfaces, icons, motion), `better-typography`, `better-layout`, `better-colors` and `better-accessibility`.
- `animate` adds Framer Motion patterns and examples. `hackkit setup` installs it per laptop, so it may be missing: then follow `better-ui` alone.
- Where `animate` and `better-ui` give different values, `better-ui` wins. Examples: press scale `0.96`, exits with `ease-out`.
- Animations use `framer-motion`. Workers can't install packages, so the design-system task adds it.
- After any UI change, open the page with the playwright MCP server, take a screenshot at 1440×900, compare it with `docs/DESIGN.md` and fix what is off before you finish.

## Responsible AI

- Use only synthetic or properly anonymized data. Never paste real personal data into prompts, code, tests or docs.
- Pseudonymize names, IDs and free text before they reach an LLM when the input could contain personal data.
- Every AI output in the UI shows: the sources used (with links or document and page), the model name, and a confidence or uncertainty hint.
- A human confirms every AI decision that affects a person. Show that step in the UI.
- State the EU AI Act risk class of the use case and why, in the README and the pitch.
- Measure quality: keep a small labelled eval set and record results in `docs/EVAL.md` (use the `eval` command).
- Record known failure modes in the README limitations section.

## Team pool

Work is split into tasks in the ops repo `John2206/ki-challenge-26-ops`. Each laptop runs `hackkit worker`. A human approves every task before their laptop runs it.

- If you run as a worker on a task: change only the files the task names, do not commit or push (hackkit does that), and end with a short summary of what you changed and how you tested it.
- If you run as the manager: follow the manager instructions you were started with.
- Never start work that belongs to another open task. Check `hackkit task list` first.

Team and the agents each member runs on their own laptop:
- Jonathan Löscher: claude, codex, agy — skills: integration, backend
- Gjergj Brestovci: claude, agy — skills: frontend, demo
- Fabian Górski: claude, agy — skills: research, data, pitch

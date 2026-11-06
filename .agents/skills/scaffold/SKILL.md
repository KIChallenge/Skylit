---
name: scaffold
description: Scaffold the app for the chosen use case and stack
---

Scaffold the project for: (the text the user gave after the command, or their request in the message)

1. Propose the smallest stack that can demo this use case in a browser within the time limit, and that can look polished fast. Default unless the use case clearly needs something else: Next.js + TypeScript + Tailwind + shadcn/ui, deployed on Vercel; Python only for data and eval scripts. State it in 3 lines and wait for a yes.
2. Create the folder layout, dependency file with a lockfile, one runnable entry point and a health-check or hello page.
3. Add an LLM client module that reads the provider and key from environment variables, so we can switch to the organizers' models by changing `.env` only. It supports `LLM_PROVIDER=replay` (serve recorded responses from `demo/fixtures/`, keyed by a hash of the request) and `LLM_RECORD=1` (record real responses there). Every call has a timeout.
4. Add one command that runs the app from a clean clone (`make run`, `npm run dev` or equivalent), serving on `PORT` from the environment, and a fast smoke test (the app builds and the health page answers). Put both in the README run section, and tell the human to set the smoke test as `test_command` in `hackkit.toml`.
5. Deploy a first version to a public URL and put the URL in the README.
6. Log the stack choice with the `decision` command.
Do not build features yet. Next step: the `design-system` command.

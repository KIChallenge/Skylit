---
description: Write and run an end-to-end Playwright test of the exact jury demo flow
---

Write or update the demo check. Extra instructions: $ARGUMENTS

1. Read the live-demo steps in `docs/PITCH.md`. The test follows them exactly: same inputs, same clicks, same order.
2. Write it as a Playwright test (for example `e2e/demo.spec.ts`) that runs against the local app with `LLM_PROVIDER=replay`, so it is fast and stable. If fixtures are missing, record them once with `LLM_RECORD=1` and a real provider. `playwright.config` reads `PORT` (default 3000) for `webServer.port` and `use.baseURL`, and sets `reuseExistingServer: !process.env.CI`. hackkit runs tests with `CI=true` and a free `PORT`, so a test never hits a dev server running other code.
3. Assert what the jury must see at each step: the key result, the sources, no error state, no console errors.
4. Save a screenshot of each step to `e2e/screenshots/` at 1920×1080. They double as backup slides.
5. Add one command for it (for example `npm run demo:check`) and put it in the README run section. Do not make it the repo's `test_command`: until the whole demo exists it fails, and every task would fail with it.
6. Mark each step whose feature is not built yet with `test.fixme`, so the check passes on what exists. Remove the `fixme` when the feature lands.
7. Run it until it passes. Report the result and any step that was flaky.

import { defineConfig, devices } from "@playwright/test";

import { loadRootEnv } from "./scripts/root-env.mjs";

// CI and hackkit set PORT in the shell. Locally, FRONTEND_PORT comes from the repo-root .env.
// Read PORT before loading .env: the .env PORT belongs to the backend.
const shellPort = process.env.PORT;
loadRootEnv(["FRONTEND_PORT", "NEXT_PUBLIC_API_URL", "PLAYWRIGHT_CHANNEL"]);
const port = shellPort ?? process.env.FRONTEND_PORT;
if (!port) {
  throw new Error("Set PORT or FRONTEND_PORT so Playwright knows where the frontend runs.");
}
const baseURL = `http://localhost:${port}`;
const demoViewport = { width: 1440, height: 900 };
// Optional, local only: PLAYWRIGHT_CHANNEL=chrome uses the installed Google Chrome instead of
// the bundled Chromium. CI ignores it and always uses the browser from `npx playwright install`.
// .env.example documents this optional test-runner setting.
const localChannel = process.env.CI ? undefined : process.env.PLAYWRIGHT_CHANNEL?.trim() || undefined;

export default defineConfig({
  testDir: "./e2e",
  // The demo flow shares one seeded backend. Run it in order.
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    locale: "de-AT",
    timezoneId: "Europe/Vienna",
    viewport: demoViewport,
    // The person declined location sharing before, so the location dialog does not cover the chat.
    storageState: {
      cookies: [],
      origins: [{ origin: baseURL, localStorage: [{ name: "lotse.location.choice", value: "dismissed" }] }],
    },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: demoViewport,
        ...(localChannel ? { channel: localChannel } : {}),
      },
    },
  ],
  // Reuses a running frontend (make run or npm run dev). Otherwise builds and starts one.
  // The backend must already run, for example with make run and LLM_PROVIDER=replay.
  webServer: {
    command: "npm run build && npm run start",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: { PORT: port },
  },
});

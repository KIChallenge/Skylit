/**
 * Shared data and helpers for the jury demo check.
 *
 * Every input string comes verbatim from docs/PITCH.md §3. Change the pitch first, then this file.
 * Selectors follow the components' roles and accessible names, never CSS classes.
 */
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { expect, type APIRequestContext, type Page } from "@playwright/test";

import { repoRoot } from "../../scripts/root-env.mjs";

export const SCREENSHOT_DIR = resolve(repoRoot, "frontend/e2e/screenshots");

/** The projector resolution from docs/PITCH.md. Screenshots double as backup slides. */
export const PROJECTOR_VIEWPORT = { width: 1920, height: 1080 } as const;

export const PRODUCT_NAME = "SV KI-Lotse";

/** Persona IDs from backend/seed/personas.json. Display names from the same file. */
export const PERSONAS = {
  maria: { id: "maria", name: "Maria Berger" },
  elif: { id: "elif", name: "Elif Yılmaz" },
} as const;

/** The seed PDF the presenter uploads in S1 step 4. */
export const SEED_DISCHARGE_LETTER = resolve(
  repoRoot,
  "backend/seed/documents/entlassungsbefund.pdf",
);

/** Exact pitch inputs, in demo order (docs/PITCH.md §3). */
export const PITCH = {
  s1: {
    opening:
      "Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr zurecht. Was muss ich tun?",
    followUpWithLetter: "Ja, sie wohnt in Wien. Hier ist der Brief.",
    formRequest: "Bitte füll den Pflegegeldantrag für meine Mutter aus.",
  },
  s2: {
    medicalQuestion: "Soll meine Mutter das Ondansetron höher dosieren, ihr ist noch immer schlecht?",
  },
  s3: {
    emergency: "Meine Mutter hat plötzlich starke Atemnot.",
  },
  s5: {
    englishQuestion: "Which check-ups does my 2-year-old need?",
  },
} as const;

/** Sections the discharge letter cites (docs/PITCH.md S1 step 5). */
export const EXPECTED_QUOTE_SECTIONS = ["Abschnitt 7", "Abschnitt 8"] as const;

/** Model name the transparency panel must show (docs/PITCH.md S1 step 9). */
export const EXPECTED_MODEL = "eustella-v1.5";

/** Backend origin. playwright.config.ts loads NEXT_PUBLIC_API_URL from the repo-root .env. */
export function apiUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!value) {
    throw new Error("Set NEXT_PUBLIC_API_URL so the demo check can reach the backend.");
  }
  return value.replace(/\/+$/, "");
}

/**
 * Fails fast unless the backend serves recorded LLM responses.
 * The demo check never calls a live LLM and never needs an API key.
 */
export async function expectReplayBackend(request: APIRequestContext): Promise<void> {
  const response = await request.get(`${apiUrl()}/api/health`, { timeout: 5_000 });
  expect(response.ok(), "Backend /api/health antwortet nicht. Läuft make run?").toBe(true);
  const body = (await response.json()) as { llm_provider?: string };
  expect(body.llm_provider, "Starten Sie das Backend mit LLM_PROVIDER=replay.").toBe("replay");
}

/**
 * Wipes one persona's conversations, cases, documents and forms (POST /api/dev/reset).
 * Uses the browser context's request client, so the session cookie lands in the same jar.
 * Logs out afterwards: the demo then starts on /login like the presenter does.
 */
export async function resetPersona(request: APIRequestContext, personaId: string): Promise<void> {
  const api = apiUrl();
  const login = await request.post(`${api}/api/auth/login`, { data: { persona_id: personaId } });
  expect(login.ok(), `Login als ${personaId} für den Reset fehlgeschlagen.`).toBe(true);
  const reset = await request.post(`${api}/api/dev/reset`);
  expect(reset.status(), "POST /api/dev/reset braucht APP_ENV=development oder demo.").toBe(204);
  const logout = await request.post(`${api}/api/auth/logout`);
  expect(logout.status()).toBe(204);
}

/**
 * Collects console errors, uncaught page errors and failed same-app requests.
 * Call `expectClean()` at the end of every step. It also clears the list for the next step.
 */
export function watchBrowserErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  return {
    expectClean(step: string) {
      const found = errors.splice(0);
      expect(found, `Browserfehler in Schritt „${step}“`).toEqual([]);
    },
  };
}

/** Saves one full-viewport PNG per active demo step, e.g. `s1-05-zitate.png`. */
export async function saveStepScreenshot(page: Page, name: string): Promise<void> {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({ path: resolve(SCREENSHOT_DIR, `${name}.png`), animations: "disabled" });
}

/** Shared locators for the real demo components. */
export function ui(page: Page) {
  return {
    personaCard: (name: string) => page.getByRole("button", { name: `Als ${name} anmelden` }),
    composer: () => page.getByRole("textbox", { name: "Ihre Nachricht an den Lotsen" }),
    send: () => page.getByRole("button", { name: "Senden" }),
    attach: () => page.getByRole("button", { name: "Dokument anhängen" }),
    progress: () => page.getByRole("status"),
    casePanel: () => page.getByRole("complementary", { name: "Mein Fall" }),
    caseSteps: () =>
      page.getByRole("complementary", { name: "Mein Fall" })
        .getByRole("list", { name: "Ihre nächsten Schritte" }).locator(":scope > li"),
    documentCard: () => page.getByRole("region", { name: "Aus Ihrem Dokument" }),
    formCard: () => page.getByRole("region", { name: /Antrag auf Pflegegeld/ }),
    downloadPdf: () => page.getByRole("button", { name: "PDF herunterladen" }),
    whyButton: () => page.getByRole("button", { name: "Warum diese Antwort?" }).last(),
    transparencyDrawer: () => page.getByRole("dialog", { name: "Warum diese Antwort?" }),
    escalationCard: () => page.getByRole("region", { name: "Medizinische Frage", exact: true }),
    copySummary: () => page.getByRole("button", { name: /Zusammenfassung kopieren|Kopiert/ }),
    emergencyBanner: () => page.getByRole("alert").filter({ hasText: "Notfall" }),
    personaMenu: () => page.getByRole("button", { name: /^Persona-Menü: / }),
    logout: () => page.getByRole("menuitem", { name: "Abmelden" }),
  };
}

/** Types one pitch input and sends it with the "Senden" button, as the presenter does. */
export async function sendMessage(page: Page, text: string): Promise<void> {
  const { composer, send } = ui(page);
  await expect(composer()).toBeVisible();
  await composer().fill(text);
  await send().click();
  await expect(page.getByText(text, { exact: true }).last()).toBeVisible();
}

/**
 * Waits until the streamed answer is complete. "Senden" shows "Lotse antwortet…" and is
 * aria-disabled while the Lotse answers (docs/DESIGN.md §8). Other role="status" live regions
 * stay in the DOM, so this check does not count them.
 */
export async function waitForAnswer(page: Page): Promise<void> {
  await expect(page.getByRole("button", { name: "Lotse antwortet…" })).toHaveCount(0, {
    timeout: 45_000,
  });
  await expect(ui(page).send()).toHaveAttribute("aria-disabled", "false");
}

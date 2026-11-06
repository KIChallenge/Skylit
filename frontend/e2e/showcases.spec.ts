/**
 * Show cases K, P, V from docs/PITCH.md ("Show-Fälle"), clicked through the UI like the presenter.
 *
 * Prerequisites: backend with LLM_PROVIDER=replay and the recorded fixtures in demo/fixtures/
 * (backend/scripts/record_demo.py --case all). The check never calls a live LLM.
 * After each case it reads the transparency of every answer: a replay miss shows the fake model.
 */
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  SEED_DISCHARGE_LETTER,
  apiUrl,
  expectReplayBackend,
  resetPersona,
  saveStepScreenshot,
  sendMessage,
  ui,
  waitForAnswer,
} from "./support/demo";

const STEFAN = { id: "stefan", name: "Stefan Gruber" };
const MARIA = { id: "maria", name: "Maria Berger" };

/** Exact inputs from docs/PITCH.md. Replay hits only on the same text. */
const SHOW = {
  kopfschmerz: {
    opening: "Ich habe seit drei Tagen Kopfschmerzen und weiß nicht, wohin ich damit gehen soll.",
    samplerClicks: [
      "Vor 2–3 Tagen", "Stetig", "4–5: spürbar", "Keine bekannt", "Keine Medikamente", "Keine relevant",
    ],
    doctors: "Welche Hausärztinnen oder Hausärzte gibt es in 1100?",
    email: "Ja, bitte entwirf die E-Mail mit meinen Angaben an die Demo-Ordination Dr. Emil Kieselstern.",
  },
  pflegegeld: [
    "Meine Mutter Anna ist gestern aus dem Spital entlassen worden. Sie wohnt allein in 1030 Wien. "
      + "Hier ist der Entlassungsbrief. Welche Unterstützung bekommt sie?",
    "Bitte füll den Pflegegeldantrag für meine Mutter aus.",
    "Wo reiche ich den Antrag ein, und wer hilft uns bei der Pflege zu Hause?",
    "Bitte schlag mir einen Termin bei einer Pflegeberatung in 1030 vor.",
    "Ich arbeite Vollzeit. Kann ich für die Pflege meiner Mutter in Pflegekarenz gehen? "
      + "Bitte entwirf auch eine E-Mail an meinen Arbeitgeber an personal@arbeitgeber.example.",
    "Ja, bitte erstelle den E-Mail-Entwurf.",
  ],
  vorsorge: [
    "Ich bin selbstständig und möchte etwas für meine Gesundheit tun. Was bietet mir meine Versicherung an?",
    "Ich möchte mich mehr bewegen und weniger Stress haben. Meine letzte Vorsorgeuntersuchung ist über drei Jahre her.",
    "Wo kann ich die Vorsorgeuntersuchung in 1100 machen? Bitte schlag mir einen Termin bei der Demo-Ordination vor.",
    "Bitte leg mir die nächsten Schritte in Mein Fall an.",
  ],
} as const;

async function login(page: Page, name: string): Promise<void> {
  await page.goto("/login");
  await ui(page).personaCard(name).click();
  await expect(page).toHaveURL(/\/chat\//);
  // Decline the location: shared coordinates change the replay keys.
  const notNow = page.getByRole("button", { name: "Nicht jetzt" });
  await notNow.click({ timeout: 10_000 }).catch(() => undefined);
  await expect(ui(page).send()).toHaveAttribute("aria-disabled", "false");
}

async function say(page: Page, text: string): Promise<void> {
  await sendMessage(page, text);
  await waitForAnswer(page);
}

/** Fails when any answer of the open conversation came from the fake fallback. */
async function expectNoReplayMiss(page: Page): Promise<void> {
  const conversationId = new URL(page.url()).pathname.split("/").pop();
  const conversation = await page.request.get(`${apiUrl()}/api/conversations/${conversationId}`);
  expect(conversation.ok()).toBe(true);
  const { messages } = (await conversation.json()) as { messages: { id: string; role: string }[] };
  const answers = messages.filter(message => message.role === "assistant");
  expect(answers.length).toBeGreaterThan(0);
  for (const answer of answers) {
    const response = await page.request.get(`${apiUrl()}/api/messages/${answer.id}/transparency`);
    expect(response.ok()).toBe(true);
    const body = (await response.json()) as {
      model?: string | null;
      entries?: { event_type: string; detail?: { model?: string } }[];
    };
    const models = [body.model, ...(body.entries ?? [])
      .filter(entry => entry.event_type === "llm_call")
      .map(entry => entry.detail?.model)];
    expect(models, `Replay-Miss bei Antwort ${answer.id}`).not.toContain("fake");
  }
}

test.describe.serial("Show-Fälle aus der Aufnahme", () => {
  let context: BrowserContext;
  let page: Page;

  test.beforeAll(async ({ browser }, testInfo) => {
    // No geolocation permission: shared coordinates change the replay keys.
    context = await browser.newContext({ ...testInfo.project.use, acceptDownloads: true });
    await expectReplayBackend(context.request);
    page = await context.newPage();
  });

  test.afterAll(async () => {
    await context?.close();
  });

  test("K Kopfschmerz: SAMPLER-Karten, Hausärzte, E-Mail-Entwurf", async () => {
    test.setTimeout(180_000);
    await resetPersona(context.request, STEFAN.id);
    await login(page, STEFAN.name);
    await say(page, SHOW.kopfschmerz.opening);
    for (const option of SHOW.kopfschmerz.samplerClicks) {
      const answerButton = page.getByRole("button", { name: "Antworten" });
      await expect(answerButton).toHaveCount(1);
      const card = page.locator("form").filter({ has: answerButton });
      await card.getByText(option, { exact: true }).click();
      await answerButton.click();
      await waitForAnswer(page);
    }
    await expect(page.getByRole("button", { name: "Antworten" })).toHaveCount(0);
    await expect(ui(page).emergencyBanner()).toHaveCount(0);
    await expect(page.getByText("1450").last()).toBeVisible();
    await say(page, SHOW.kopfschmerz.doctors);
    await say(page, SHOW.kopfschmerz.email);
    await saveStepScreenshot(page, "show-k-email");
    await expectNoReplayMiss(page);
  });

  test("P Pflegegeld: Brief, Antrag, Stellen, Termin, Pflegekarenz, E-Mail", async () => {
    test.setTimeout(240_000);
    await resetPersona(context.request, MARIA.id);
    await login(page, MARIA.name);
    const { composer, attach, send, caseSteps } = ui(page);
    await composer().fill(SHOW.pflegegeld[0]);
    const chooserPromise = page.waitForEvent("filechooser");
    await attach().click();
    await (await chooserPromise).setFiles(SEED_DISCHARGE_LETTER);
    await send().click();
    await waitForAnswer(page);
    await expect(caseSteps().first()).toBeVisible();
    for (const text of SHOW.pflegegeld.slice(1)) await say(page, text);
    await expect(ui(page).formCard()).toBeVisible();
    await saveStepScreenshot(page, "show-p-email");
    await expectNoReplayMiss(page);
  });

  test("V Vorsorge: SVS-Angebote, Demo-Termin, Mein Fall", async () => {
    test.setTimeout(180_000);
    await resetPersona(context.request, STEFAN.id);
    await login(page, STEFAN.name);
    for (const text of SHOW.vorsorge) await say(page, text);
    await expect(page.getByRole("button", { name: "Antworten" })).toHaveCount(0);
    await expect(ui(page).caseSteps().first()).toBeVisible();
    await saveStepScreenshot(page, "show-v-fall");
    await expectNoReplayMiss(page);
  });
});

/**
 * Jury demo check: docs/PITCH.md §3, S1 → S2 → S3, same inputs, same clicks, same order.
 *
 * Prerequisites (the check never calls a live LLM and needs no API key):
 *   - Backend runs with LLM_PROVIDER=replay and APP_ENV=development or demo (make run).
 *   - Recorded fixtures for every pitch input exist in demo/fixtures/.
 *
 * The steps share one browser page and one conversation, like the live demo.
 * Run steps in demo order. Each step depends on the previous step's state.
 */
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import {
  EXPECTED_MODEL,
  EXPECTED_QUOTE_SECTIONS,
  PERSONAS,
  PITCH,
  PROJECTOR_VIEWPORT,
  SEED_DISCHARGE_LETTER,
  expectReplayBackend,
  resetPersona,
  saveStepScreenshot,
  sendMessage,
  ui,
  waitForAnswer,
  watchBrowserErrors,
} from "./support/demo";

test.describe.serial("Live-Demo mit Maria Berger (S1–S3)", () => {
  let context: BrowserContext;
  let page: Page;
  let browserErrors: ReturnType<typeof watchBrowserErrors>;

  // Start with a fresh browser context and reset Maria's demo data.
  test.beforeAll(async ({ browser }, testInfo) => {
    const projectUse = testInfo.project.use;
    context = await browser.newContext({
      baseURL: projectUse.baseURL,
      locale: projectUse.locale,
      timezoneId: projectUse.timezoneId,
      viewport: PROJECTOR_VIEWPORT,
      permissions: ["clipboard-read", "clipboard-write"],
      acceptDownloads: true,
    });
    await expectReplayBackend(context.request);
    await resetPersona(context.request, PERSONAS.maria.id);
    page = await context.newPage();
    browserErrors = watchBrowserErrors(page);
  });

  test.afterAll(async () => {
    await context?.close();
  });

  // ---------------------------------------------------------------- S1 — Golden Path

  test("S1.1 Persona Maria Berger wählen, „Mein Fall“ ist leer", async () => {
    const { personaCard, composer, casePanel } = ui(page);
    await page.goto("/login");
    await expect(page).toHaveTitle(/Anmelden – SV KI-Lotse/);
    await personaCard(PERSONAS.maria.name).click();
    await expect(page).toHaveURL(/\/chat\//);
    await expect(composer()).toBeVisible();
    await expect(ui(page).send()).toHaveAttribute("aria-disabled", "false");
    await expect(casePanel().getByText(/Noch keine Schritte/)).toBeVisible();
    await saveStepScreenshot(page, "s1-01-login-maria");
    browserErrors.expectClean("S1.1");
  });

  test("S1.2–3 Anfangsfrage: Antwort streamt mit höchstens zwei Rückfragen", async () => {
    await sendMessage(page, PITCH.s1.opening);
    await waitForAnswer(page);
    const answer = page.getByRole("article", { name: "Antwort des Lotsen", exact: true }).last();
    await expect(answer).toContainText("Entlassungsbrief");
    // The model asks for the place of residence: "in Wien?" or "in welchem Bundesland?".
    await expect(answer).toContainText(/Wien|Bundesland/);
    await expect(ui(page).whyButton()).toBeVisible();
    await saveStepScreenshot(page, "s1-03-rueckfragen");
    browserErrors.expectClean("S1.2–3");
  });

  test("S1.4–5 Brief hochladen: Zitate mit Abschnitt erscheinen", async () => {
    const { composer, attach, send, documentCard } = ui(page);
    await composer().fill(PITCH.s1.followUpWithLetter);
    const chooserPromise = page.waitForEvent("filechooser");
    await attach().click();
    const chooser = await chooserPromise;
    await chooser.setFiles(SEED_DISCHARGE_LETTER);
    await expect(page.getByRole("group", { name: "Anhang: entlassungsbefund.pdf", exact: true })
      .getByText("entlassungsbefund.pdf", { exact: true })).toBeVisible();
    await send().click();
    await expect(page.getByRole("status").filter({ hasText: "Dokument wird gelesen…" })).toBeVisible();
    await waitForAnswer(page);

    const card = documentCard();
    await expect(card).toBeVisible();
    await expect(card.getByText("Wörtlich zitiert. Der Lotse bewertet keine Befunde.")).toBeVisible();
    for (const section of EXPECTED_QUOTE_SECTIONS) {
      await expect(card.locator("figcaption").filter({ hasText: section }).first()).toBeVisible();
    }
    await expect(card.getByText(/Rehabilitation/).first()).toBeVisible();
    await expect(card.getByText(/Pflegegeld/).first()).toBeVisible();
    await expect(card.getByText(/Hauskrankenpflege/).first()).toBeVisible();
    await expect(card.getByText(/Rezeptgebühr/).first()).toBeVisible();
    await saveStepScreenshot(page, "s1-05-zitate");
    browserErrors.expectClean("S1.4–5");
  });

  test("S1.6 „Mein Fall“ füllt sich mit 5–6 Schritten", async () => {
    const steps = ui(page).caseSteps();
    await expect(steps.nth(4)).toBeVisible();
    expect(await steps.count()).toBeGreaterThanOrEqual(5);
    expect(await steps.count()).toBeLessThanOrEqual(6);
    await saveStepScreenshot(page, "s1-06-mein-fall");
    browserErrors.expectClean("S1.6");
  });

  test("S1.7 Pflegegeldantrag ausfüllen und PDF herunterladen", async () => {
    await sendMessage(page, PITCH.s1.formRequest);
    await waitForAnswer(page);
    const card = ui(page).formCard();
    await expect(card).toBeVisible();
    await expect(card.getByText("Von Ihnen zu prüfen").first()).toBeVisible();
    await expect(card.getByRole("heading", { name: /^Ausgefüllt \(\d+\)$/ })).toBeVisible();
    await expect(card.getByRole("heading", { name: /^Fehlt noch \(\d+\)$/ })).toBeVisible();
    await expect(card.getByRole("heading", { name: /^Füllen andere aus \(\d+\)$/ })).toBeVisible();
    await saveStepScreenshot(page, "s1-07-formular");

    const downloadPromise = page.waitForEvent("download");
    await card.getByRole("button", { name: "PDF herunterladen" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.pdf$/i);
    expect(await download.failure()).toBeNull();
    browserErrors.expectClean("S1.7");
  });

  test("S1.8 Stellen: PVA", async () => {
    await expect(page.getByRole("region", { name: /PVA|Pensionsversicherung/ }).first()).toBeVisible();
    await saveStepScreenshot(page, "s1-08-stellen");
    browserErrors.expectClean("S1.8");
  });

  test("S1.8 Stellen: FSW-Beratungszentrum Pflege und Betreuung", async () => {
    await expect(
      page.getByRole("region", { name: /Beratungszentrum Pflege und Betreuung/ }).first(),
    ).toBeVisible();
  });

  test("S1.9 Transparenz: Quellen, Tool-Aufrufe, Modell und Sicherheit", async () => {
    await ui(page).whyButton().click();
    const drawer = ui(page).transparencyDrawer();
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("link").first()).toBeVisible();
    await expect(drawer.getByText(EXPECTED_MODEL)).toBeVisible();
    // Confidence always shows a label, never colour alone.
    for (const name of ["Sicherheit", "Quellen", "Schritte des Lotsen", "Modell"]) {
      await expect(drawer.getByRole("heading", { name, exact: true })).toBeVisible();
    }
    await expect(drawer.getByText(/^Sicherheit: (hoch|mittel|niedrig)$/)).toBeVisible();
    await expect(drawer.getByText(/Diese Antwort hat eine KI erstellt/)).toBeVisible();
    await saveStepScreenshot(page, "s1-09-transparenz");
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    browserErrors.expectClean("S1.9");
  });

  // ---------------------------------------------------------------- S2 — Medizinische Grenze

  test("S2.1–2 Medizinische Frage: Ablehnung und Eskalation mit 1450", async () => {
    await sendMessage(page, PITCH.s2.medicalQuestion);
    await waitForAnswer(page);
    // AnswerFooter loads the badge through a separate transparency request after streaming.
    await expect(page.getByText("Medizinische Frage – an Fachleute übergeben", { exact: true }).last())
      .toBeVisible({ timeout: 45_000 });
    const card = ui(page).escalationCard();
    await expect(card).toBeVisible();
    await expect(card.getByText(/Hausärzt|onkologisch/).first()).toBeVisible();
    await expect(card.getByText(/1450/).first()).toBeVisible();
    await expect(card.getByText("Zum Vorlesen am Telefon")).toBeVisible();
    await saveStepScreenshot(page, "s2-02-medizinische-grenze");
    browserErrors.expectClean("S2.1–2");
  });

  test("S2.3 Zusammenfassung kopieren", async () => {
    const copy = ui(page).escalationCard().getByRole("button", { name: "Zusammenfassung kopieren" });
    await copy.click();
    await expect(ui(page).escalationCard().getByRole("button", { name: "Kopiert" })).toBeVisible();
    const clipboard = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboard.trim().length).toBeGreaterThan(0);
    await saveStepScreenshot(page, "s2-03-kopiert");
    browserErrors.expectClean("S2.3");
  });

  // ---------------------------------------------------------------- S3 — Notfall

  test("S3 Notfall-Banner mit 144 erscheint vor jedem KI-Text", async () => {
    // The observer records whether answer text exists when the banner appears.
    // Match stored answers and the streaming answer, which use different accessible names.
    await page.evaluate(() => {
      const answers = () => document.querySelectorAll('article[aria-label$="Antwort des Lotsen"]');
      const baseline = answers().length;
      const state = { bannerSeen: false, textBeforeBanner: false };
      (window as unknown as { __emergencyOrder: typeof state }).__emergencyOrder = state;
      const observer = new MutationObserver(() => {
        if (state.bannerSeen) return;
        const banner = Array.from(document.querySelectorAll('[role="alert"]')).some((node) =>
          node.textContent?.includes("Notfall"),
        );
        const list = answers();
        const newText = list.length > baseline && (list[list.length - 1].textContent ?? "").trim() !== "";
        state.textBeforeBanner ||= newText;
        if (banner) {
          state.bannerSeen = true;
          observer.disconnect();
        }
      });
      observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    });

    await sendMessage(page, PITCH.s3.emergency);
    const banner = ui(page).emergencyBanner();
    await expect(banner).toBeVisible();
    await expect(banner.getByText("Bitte holen Sie sofort Hilfe")).toBeVisible();
    await expect(banner.getByRole("link", { name: /144/ })).toHaveAttribute("href", /^tel:144/);

    const order = await page.evaluate(
      () => (window as unknown as { __emergencyOrder: { bannerSeen: boolean; textBeforeBanner: boolean } })
        .__emergencyOrder,
    );
    expect(order.bannerSeen).toBe(true);
    expect(order.textBeforeBanner, "Der Notfall-Banner muss vor dem KI-Text stehen.").toBe(false);
    // In the DOM the banner precedes <main> (docs/DESIGN.md §10).
    const bannerBeforeMain = await banner.evaluate((node) => {
      const main = document.querySelector("main");
      return !!main && !!(node.compareDocumentPosition(main) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(bannerBeforeMain).toBe(true);

    await saveStepScreenshot(page, "s3-notfall");
    await waitForAnswer(page);
    await expect(banner).toBeVisible();
    browserErrors.expectClean("S3");
  });
});

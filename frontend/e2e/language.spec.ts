/**
 * Optional demo step S5 (docs/PITCH.md §3): only shown when time is left.
 * Runs in its own browser context with Elif's data reset, so it never depends on S1–S3.
 */
import { expect, test } from "@playwright/test";

import {
  PERSONAS,
  PITCH,
  PROJECTOR_VIEWPORT,
  expectReplayBackend,
  resetPersona,
  saveStepScreenshot,
  sendMessage,
  ui,
  waitForAnswer,
  watchBrowserErrors,
} from "./support/demo";

test.use({ viewport: PROJECTOR_VIEWPORT });

test("S5 (optional) Elif Yılmaz fragt auf Englisch, der Lotse antwortet auf Englisch", async ({
  page,
  context,
}) => {
  // The pitch starts S5 with "Abmelden" after S3. This test starts on /login after a reset,
  // so S5 stays independent of the S1–S3 conversation.
  await expectReplayBackend(context.request);
  await resetPersona(context.request, PERSONAS.elif.id);
  const browserErrors = watchBrowserErrors(page);

  await page.goto("/login");
  await ui(page).personaCard(PERSONAS.elif.name).click();
  await expect(page).toHaveURL(/\/chat\//);

  await sendMessage(page, PITCH.s5.englishQuestion);
  await waitForAnswer(page);
  await expect(page.getByText(/Eltern-Kind-Pass|mother-child|parent-child/i).last()).toBeVisible();
  await expect(page.getByText(/vaccinat|immuni[sz]ation|Kinderimpfprogramm/i).last()).toBeVisible();
  await saveStepScreenshot(page, "s5-englisch");
  browserErrors.expectClean("S5");
});

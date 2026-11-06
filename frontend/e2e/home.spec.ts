import { expect, test } from "@playwright/test";

import {
  PRODUCT_NAME,
  PROJECTOR_VIEWPORT,
  saveStepScreenshot,
  watchBrowserErrors,
} from "./support/demo";

// "/" redirects to /login without a session; its session check logs an expected 401.
// The login page shows the product name and the AI notice (docs/DESIGN.md §8). It needs no LLM.
test.use({ viewport: PROJECTOR_VIEWPORT });

test("Startseite lädt mit Produktname und KI-Hinweis, ohne Browserfehler", async ({ page }) => {
  const browser = watchBrowserErrors(page);

  const response = await page.goto("/login");
  expect(response?.ok(), "Die Startseite antwortet nicht mit 2xx.").toBe(true);

  await expect(page).toHaveTitle(new RegExp(PRODUCT_NAME));
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "SV KI-Lotse – Startseite" })).toBeVisible();
  // AI notice (EU AI Act Art. 50): the user must see that a KI answers.
  await expect(page.getByText(/(ist eine KI|hat eine KI erstellt|nutzen einen KI-Assistenten)/).first()).toBeVisible();
  // No raw error or Next.js error overlay on screen.
  await expect(page.getByText(/Application error|Unhandled Runtime Error/)).toHaveCount(0);

  await saveStepScreenshot(page, "00-startseite");
  browser.expectClean("Startseite");
});

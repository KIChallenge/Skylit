import { expect, test, type Locator, type Page } from "@playwright/test";

const shell = (page: Page) => page.locator('section[aria-labelledby="shell"]');

async function expectFocusInside(dialog: Locator) {
  await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
}

async function expectNoOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}

// No backend, persona login or feature previews are needed for these shared components.
for (const width of [1440, 1920]) {
  test(`Gemeinsame Grundlage bei ${width} Pixeln`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 1440 ? 900 : 1080 });
    for (const path of ["/", "/styleguide"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expectNoOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(path === "/" ? "home.png" : "styleguide.png") });
    }
    const preview = shell(page);
    await preview.scrollIntoViewIfNeeded();
    await expect(preview.getByRole("navigation", { name: "Gespräche" })).toBeVisible();
    await expect(preview.getByRole("complementary", { name: "Mein Fall" })).toBeVisible();
    await expect(preview.getByRole("button", { name: "Gespräche anzeigen" })).toBeHidden();
    await expect(preview.getByRole("button", { name: "Mein Fall · 2 offen" })).toBeHidden();
    await preview.screenshot({ path: testInfo.outputPath("shell.png") });
  });
}

for (const width of [320, 390, 768]) {
  test(`Mobile Sheets halten und restaurieren den Fokus bei ${width} Pixeln`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/styleguide");
    await expectNoOverflow(page);
    const preview = shell(page);
    await preview.scrollIntoViewIfNeeded();
    const skip = preview.getByRole("link", { name: "Zum Gespräch" });
    await skip.focus();
    await page.keyboard.press("Enter");
    await expect(preview.getByRole("main")).toBeFocused();

    const navTrigger = preview.getByRole("button", { name: "Gespräche anzeigen" });
    await expect(navTrigger).toHaveAttribute("aria-expanded", "false");
    await navTrigger.focus();
    await page.keyboard.press("Tab");
    await expect(preview.getByRole("link", { name: "SV KI-Lotse – Startseite" })).toBeFocused();
    await page.keyboard.press("Tab");
    // The badge reads „KI“ below 640 px and „KI-Assistent“ above.
    await expect(preview.getByRole("button", { name: /^KI(-Assistent)?$/ })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(preview.getByRole("button", { name: "Dunkles Design einschalten" })).toBeFocused();
    await page.keyboard.press("Tab");
    const caseTrigger = preview.getByRole("button", { name: "Mein Fall · 2 offen" });
    await expect(caseTrigger).toBeFocused();

    // Radix owns focus restoration. Exercise the real triggers and both close paths.
    await navTrigger.focus();
    await page.keyboard.press("Enter");
    const navigation = page.getByRole("dialog", { name: "Gespräche", exact: true });
    const newConversation = navigation.getByRole("button", { name: "Neues Gespräch" });
    await expect(newConversation).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(navigation.getByRole("link", { name: /Pflege für Mutter/ })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(navigation.getByRole("link", { name: /Reha nach Hüft-OP/ })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(navigation.getByRole("button", { name: "Schließen" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(newConversation).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(navigation.getByRole("button", { name: "Schließen" })).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath("navigation.png") });
    await page.keyboard.press("Escape");
    await expect(navigation).toBeHidden();
    await expect(navTrigger).toBeFocused();
    await expect(navTrigger).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("Space");
    await navigation.getByRole("button", { name: "Schließen" }).click();
    await expect(navTrigger).toBeFocused();

    await caseTrigger.focus();
    await page.keyboard.press("Enter");
    const caseSheet = page.getByRole("dialog", { name: "Mein Fall", exact: true });
    await expect(caseSheet.getByText("Pflegegeld bei der PVA beantragen")).toBeVisible();
    await expect(caseSheet.getByRole("button", { name: "Schließen" })).toBeFocused();
    for (const key of ["Tab", "Shift+Tab"]) {
      await page.keyboard.press(key);
      await expectFocusInside(caseSheet);
    }
    await page.screenshot({ path: testInfo.outputPath("case.png") });
    await page.keyboard.press("Escape");
    await expect(caseSheet).toBeHidden();
    await expect(caseTrigger).toBeFocused();
    await expect(caseTrigger).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("Space");
    await caseSheet.getByRole("button", { name: "Schließen" }).click();
    await expect(caseTrigger).toBeFocused();
    await expectNoOverflow(page);
  });
}

test("Tablet zeigt Mein Fall neben dem Gespräch und Gespräche im Sheet", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.goto("/styleguide");
  const preview = shell(page);
  await preview.scrollIntoViewIfNeeded();
  await expect(preview.getByRole("complementary", { name: "Mein Fall" })).toBeVisible();
  await expect(preview.getByRole("button", { name: "Mein Fall · 2 offen" })).toBeHidden();
  await expect(preview.getByRole("navigation", { name: "Gespräche" })).toBeHidden();
  const trigger = preview.getByRole("button", { name: "Gespräche anzeigen" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "Gespräche", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await expectNoOverflow(page);
});

test("Fortschritt nennt den angezeigten Wert", async ({ page }) => {
  await page.goto("/styleguide");
  const progress = shell(page).getByRole("progressbar");
  await expect(progress).toHaveAttribute("aria-valuenow", "33");
  await expect(progress).toHaveAttribute("aria-valuemin", "0");
  await expect(progress).toHaveAttribute("aria-valuemax", "100");
});

test("Reduzierte Bewegung verhindert Slide, Zoom, Pulse und Spin", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/styleguide");
  await expect(page.locator('[data-slot="skeleton"]').first()).toHaveCSS("animation-name", "none");
  await expect(page.locator('[data-slot="progress-indicator"]')).toHaveCSS("transition-duration", "0s");

  // Probe the generated loading-icon utility without introducing a demo-only control.
  const spinAnimation = await page.evaluate(() => {
    const icon = document.createElement("span");
    icon.className = "motion-safe:animate-spin";
    document.body.append(icon);
    const name = getComputedStyle(icon).animationName;
    icon.remove();
    return name;
  });
  expect(spinAnimation).toBe("none");

  async function expectOpacityOnly(target: Locator) {
    const movement = await target.evaluate((element) => element.getAnimations({ subtree: true }).flatMap((animation) => {
      const effect = animation.effect;
      if (!(effect instanceof KeyframeEffect)) return [];
      return effect.getKeyframes().filter((frame) => {
        const transform = frame.transform as string | undefined;
        return (transform && transform !== "none" && !new DOMMatrixReadOnly(transform).isIdentity)
          || (frame.translate && !["none", "0px", "0px 0px"].includes(String(frame.translate)))
          || (frame.scale && !["none", "1", "1 1"].includes(String(frame.scale)))
          || (frame.rotate && !["none", "0deg"].includes(String(frame.rotate)))
          || (frame.filter && frame.filter !== "none" && frame.filter !== "blur(0px)");
      });
    }));
    expect(movement).toEqual([]);
  }

  await shell(page).getByRole("button", { name: "Gespräche anzeigen" }).click();
  await expectOpacityOnly(page.getByRole("dialog", { name: "Gespräche", exact: true }));
  await page.keyboard.press("Escape");
  await shell(page).getByRole("button", { name: "Mein Fall · 2 offen" }).click();
  await expectOpacityOnly(page.getByRole("dialog", { name: "Mein Fall", exact: true }));
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Maria Berger" }).click();
  await expectOpacityOnly(page.getByRole("menu"));
  await page.keyboard.press("Escape");
  const badge = shell(page).getByRole("button", { name: "KI", exact: true });
  await badge.focus();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await expectOpacityOnly(page.getByRole("tooltip"));
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Schritte erneut einblenden" }).click();
  await expectOpacityOnly(page.locator('section[aria-labelledby="bewegung"]'));
  // Framer Motion can update inline styles without a Web Animations API animation.
  const inlineMovement = await page.locator('section[aria-labelledby="bewegung"]').evaluate(async (section) => {
    const movement: string[] = [];
    const start = performance.now();
    while (performance.now() - start < 600) {
      for (const element of section.querySelectorAll("[style]")) {
        const style = getComputedStyle(element);
        if (style.transform !== "none" && !new DOMMatrixReadOnly(style.transform).isIdentity) {
          movement.push(style.transform);
        }
        if (style.filter !== "none" && style.filter !== "blur(0px)") {
          movement.push(style.filter);
        }
      }
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    }
    return movement;
  });
  expect(inlineMovement).toEqual([]);
});

import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { THEME_INIT_SCRIPT, THEME_STORAGE_KEY, ThemeToggle } from "./theme-toggle";

// Node 26 ships its own global localStorage, which hides the jsdom one. Use a fresh store.
beforeEach(() => {
  const items = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, String(value)),
    removeItem: (key: string) => void items.delete(key),
    clear: () => items.clear(),
  });
});

afterEach(() => {
  cleanup();
  delete document.documentElement.dataset.theme;
  vi.unstubAllGlobals();
});

describe("theme toggle", () => {
  it("starts light, switches to dark and back, and remembers the choice", async () => {
    render(<ThemeToggle />);
    const toLight = () => screen.findByRole("button", { name: "Helles Design einschalten" });
    const button = screen.getByRole("button", { name: "Dunkles Design einschalten" });
    expect(button).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(button);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(await toLight()).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(await toLight());
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("applies a saved dark theme before the first paint", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    new Function(THEME_INIT_SCRIPT)();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

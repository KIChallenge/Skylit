"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

export type Theme = "light" | "dark";

/** localStorage key. The inline script in the root layout reads it before the first paint. */
export const THEME_STORAGE_KEY = "lotse-theme";

/** Runs in <head> before hydration: applies the saved theme, so dark mode never flashes light. */
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="dark")document.documentElement.dataset.theme="dark"}catch(e){}`;

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  // Suppress every colour transition for one frame, so the swap does not smear.
  root.classList.add("theme-switching");
  if (theme === "dark") root.dataset.theme = "dark";
  else delete root.dataset.theme;
  void root.offsetHeight;
  requestAnimationFrame(() => root.classList.remove("theme-switching"));
  try { localStorage.setItem(THEME_STORAGE_KEY, theme); } catch { /* private mode: keep it for this page only */ }
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

const currentTheme = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

/** Light is the default for the projector. The choice is remembered per browser. */
export function ThemeToggle() {
  // The server does not know the saved theme; the button shows the light state until hydration.
  const theme = useSyncExternalStore(subscribe, currentTheme, () => "light" as Theme);
  const dark = theme === "dark";
  return (
    <Button type="button" variant="ghost" size="icon" aria-pressed={dark}
      aria-label={dark ? "Helles Design einschalten" : "Dunkles Design einschalten"}
      onClick={() => applyTheme(dark ? "light" : "dark")}>
      {dark ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}

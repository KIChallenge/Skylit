"use client";

import { useEffect, useRef, useState } from "react";

import type { TypeRequest } from "@/features/chat";

import { SCRIPTS, SCRIPT_SHORTCUTS, nextMessage, pickSamplerOption, scriptFor, type ScriptId } from "./scripts";

const STORAGE_KEY = "lotse-demo-script";
const CLICK_DELAY_MS = 450;

export type OpenSamplerQuestion = { step: string; options: readonly string[] };

export type AutopilotInput = {
  enabled: boolean;
  personaId: string;
  /** Contents of the user messages in this conversation, oldest first. */
  sent: readonly string[];
  /** True while a turn streams or an upload is read: the shortcut then does nothing. */
  busy: boolean;
  /** The SAMPLER question that waits for an answer, if any. */
  openQuestion: OpenSamplerQuestion | null;
};

function readSelection(): ScriptId | null {
  try {
    const value = window.sessionStorage.getItem(STORAGE_KEY);
    return value && Object.values(SCRIPT_SHORTCUTS).includes(value as ScriptId) ? (value as ScriptId) : null;
  } catch {
    return null;
  }
}

function storeSelection(id: ScriptId) {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Without storage the selection lasts until the next page load.
  }
}

/** Click the option like a person: the real input, so the card's own logic runs. */
function clickOption(option: string): () => void {
  const inputs = Array.from(document.querySelectorAll<HTMLInputElement>("input[type=radio], input[type=checkbox]"));
  const input = inputs.reverse().find((element) => element.value === option && !element.disabled);
  if (!input) return () => {};
  const timer = window.setTimeout(() => {
    if (!input.checked) input.click();
    input.form?.querySelector<HTMLButtonElement>("button[type=submit]")?.focus();
  }, CLICK_DELAY_MS);
  return () => window.clearTimeout(timer);
}

/**
 * Presenter autopilot. Ctrl+Shift+Space (or Ctrl+Shift+ArrowRight) runs the next script step:
 * it types the next prompt into the composer or clicks the scripted SAMPLER option. The
 * presenter still sends with Enter. Ctrl+Shift+1…5 selects a script. Nothing shows on screen.
 */
export function useAutopilot({ enabled, personaId, sent, busy, openQuestion }: AutopilotInput): TypeRequest | null {
  const [request, setRequest] = useState<TypeRequest | null>(null);
  const latest = useRef({ personaId, sent, busy, openQuestion });
  // The key handler reads the newest conversation state without re-subscribing.
  useEffect(() => {
    latest.current = { personaId, sent, busy, openQuestion };
  });
  const selection = useRef<ScriptId | null>(null);
  const counter = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    selection.current = readSelection();
    let cancelClick = () => {};

    function onKeyDown(event: KeyboardEvent) {
      if (!event.ctrlKey || !event.shiftKey || event.altKey || event.metaKey) return;
      const selected = SCRIPT_SHORTCUTS[event.code];
      if (selected) {
        event.preventDefault();
        selection.current = selected;
        storeSelection(selected);
        return;
      }
      if (event.code !== "Space" && event.code !== "ArrowRight") return;
      event.preventDefault();
      const { personaId: persona, sent: contents, busy: working, openQuestion: question } = latest.current;
      if (working) return;
      const script = scriptFor(selection.current, persona);
      if (!script) return;
      if (question) {
        // Only the headache story was recorded with SAMPLER; its keywords serve every script.
        const keywords = (script.sampler ?? SCRIPTS.kopfschmerz.sampler)?.[question.step];
        const option = pickSamplerOption(question.options, keywords);
        cancelClick();
        if (option) cancelClick = clickOption(option);
        return;
      }
      const message = nextMessage(script, contents);
      if (!message) return;
      counter.current += 1;
      setRequest({ id: counter.current, text: message.text });
    }

    // Capture: the composer's own key handling must not see the shortcut first.
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.removeEventListener("keydown", onKeyDown, true);
      cancelClick();
    };
  }, [enabled]);

  return enabled ? request : null;
}

"use client";

import { Send } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** A text to type into the draft, character by character. A new `id` starts a new run. */
export type TypeRequest = { id: number; text: string };

export type ComposerProps = {
  sending: boolean;
  onSend: (content: string) => void;
  attachment?: ReactNode;
  /** Presenter autopilot: types this text like a person. Any real keystroke takes over. */
  typeRequest?: TypeRequest | null;
};

/** A new typing pace for the next word: some words come in a quick burst, some slowly. */
export function nextPace(random: () => number = Math.random): number {
  return 0.45 + random() * 1.35;
}

/**
 * Delay before the next character, like a person: jitter per key, a pace that changes per
 * word, longer after punctuation and now and then a short pause to think.
 */
export function typingDelay(previous: string, random: () => number = Math.random, pace = 1): number {
  let delay = (22 + random() * 48) * pace;
  if (/[.,!?;:]/.test(previous)) delay += 140 + random() * 260;
  else if (previous === " ") delay += random() < 0.12 ? 180 + random() * 420 : 15 + random() * 40;
  return delay;
}

/** Local draft only. The parent owns the request and its sending lifecycle. */
export function Composer({ sending, onSend, attachment, typeRequest }: ComposerProps) {
  const id = useId();
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);
  const submitted = useRef(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  // Stops a running type animation. `full` writes the rest of the text at once.
  const stopTyping = useRef<((full: boolean) => void) | null>(null);

  useEffect(() => {
    if (!sending) submitted.current = false;
  }, [sending]);

  useEffect(() => {
    if (!typeRequest) return;
    const { text } = typeRequest;
    let index = 0;
    let timer: number | undefined;
    const stop = (full: boolean) => {
      window.clearTimeout(timer);
      stopTyping.current = null;
      if (full) setDraft(text);
    };
    let pace = nextPace();
    const step = () => {
      if (index === 0) setInvalid(false);
      index += 1;
      // The first character replaces any old draft.
      setDraft(text.slice(0, index));
      if (text[index - 1] === " ") pace = nextPace();
      if (index < text.length) timer = window.setTimeout(step, typingDelay(text[index - 1], Math.random, pace));
      else stopTyping.current = null;
    };
    textarea.current?.focus();
    stopTyping.current = stop;
    timer = window.setTimeout(step, 250);
    return () => stop(false);
  }, [typeRequest]);

  function send() {
    if (sending || submitted.current) return;
    const content = draft.trim();
    if (!content || draft.length > 4000) {
      setInvalid(true);
      textarea.current?.focus();
      return;
    }
    submitted.current = true;
    try {
      onSend(content);
      setDraft("");
      setInvalid(false);
    } catch (error) {
      submitted.current = false;
      throw error;
    }
  }

  return (
    <form
      aria-label="Nachricht verfassen"
      className="shrink-0 px-4 pt-2 pb-4 sm:px-8 sm:pb-6"
      onSubmit={(event) => { event.preventDefault(); send(); }}
    >
      <div className="mx-auto flex max-w-answer flex-col gap-2">
        <Label htmlFor={id} className="sr-only">Ihre Nachricht an den Lotsen</Label>
        <div className="glass rounded-xl shadow-card transition-[box-shadow,border-color] duration-150 ease-out focus-within:shadow-overlay focus-within:ring-2 focus-within:ring-ring has-[textarea[aria-invalid=true]]:ring-2 has-[textarea[aria-invalid=true]]:ring-caution-solid">
          <Textarea
            ref={textarea}
            id={id}
            name="message"
            rows={2}
            maxLength={4000}
            value={draft}
            aria-invalid={invalid || undefined}
            aria-describedby={`${id}-hint${draft.length >= 3500 ? ` ${id}-count` : ""}${invalid ? ` ${id}-error` : ""}`}
            placeholder="Beschreiben Sie Ihre Lage…"
            className="min-h-16 max-h-48 resize-none border-0 bg-transparent px-5 pt-4 pb-1 text-answer shadow-none focus-visible:ring-0 dark:bg-transparent"
            onChange={(event) => { setDraft(event.target.value); setInvalid(false); }}
            onKeyDown={(event) => {
              const typing = stopTyping.current;
              if (typing) {
                // Enter finishes the text without sending, Escape discards it, any other key
                // keeps what is typed so far and lets the person continue by hand.
                if (event.key === "Enter") { event.preventDefault(); typing(true); return; }
                if (event.key === "Escape") { event.preventDefault(); typing(false); setDraft(""); return; }
                if (!["Shift", "Control", "Alt", "Meta"].includes(event.key)) typing(false);
              }
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                send();
              }
            }}
          />
          <div className="flex flex-wrap items-end justify-between gap-2 px-3 pb-3">
            <div className="min-w-0">{attachment}</div>
            <Button type="submit" aria-disabled={sending} className="shrink-0 rounded-lg">
              <Send aria-hidden />{sending ? "Lotse antwortet…" : "Senden"}
            </Button>
          </div>
        </div>
        {invalid ? <p id={`${id}-error`} className="text-label text-caution-text">Geben Sie eine Nachricht mit höchstens 4000 Zeichen ein.</p> : null}
        <p id={`${id}-hint`} className="sr-only">Enter sendet · Umschalt+Enter fügt eine neue Zeile ein.</p>
        {draft.length >= 3500 ? <span id={`${id}-count`} className="text-caption tabular text-text-secondary">{draft.length}/4000 Zeichen</span> : null}
        <p className="text-center text-caption text-text-secondary">KI-Antworten können Fehler enthalten. Die zuständige Stelle entscheidet.</p>
      </div>
    </form>
  );
}

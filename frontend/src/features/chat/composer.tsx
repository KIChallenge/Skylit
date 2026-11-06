"use client";

import { Send } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export type ComposerProps = {
  sending: boolean;
  onSend: (content: string) => void;
  attachment?: ReactNode;
};

/** Local draft only. The parent owns the request and its sending lifecycle. */
export function Composer({ sending, onSend, attachment }: ComposerProps) {
  const id = useId();
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);
  const submitted = useRef(false);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!sending) submitted.current = false;
  }, [sending]);

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

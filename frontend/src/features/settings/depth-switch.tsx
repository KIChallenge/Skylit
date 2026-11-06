"use client";

import { useId, useState } from "react";
import { toast } from "sonner";

import { api, type AnswerDepth, type ApiClient } from "@/lib/api";
import { cn } from "@/lib/utils";

const OPTIONS: { value: AnswerDepth; label: string; hint: string }[] = [
  { value: "short", label: "Kurz", hint: "Höchstens fünf kurze Sätze" },
  { value: "detailed", label: "Ausführlich", hint: "Mit Voraussetzungen und Ablauf" },
];

export type DepthSwitchProps = {
  initial: AnswerDepth;
  client?: Pick<ApiClient, "updateProfile">;
};

/** Answer length for the next answers. Saves at once and reverts when saving fails. */
export function DepthSwitch({ initial, client = api }: DepthSwitchProps) {
  const [depth, setDepth] = useState<AnswerDepth>(initial);
  const [saving, setSaving] = useState(false);
  const name = useId();

  async function choose(next: AnswerDepth) {
    if (next === depth || saving) return;
    const previous = depth;
    setDepth(next);
    setSaving(true);
    try {
      const me = await client.updateProfile({ depth: next });
      setDepth(me.profile.depth);
    } catch {
      setDepth(previous);
      toast.error("Die Einstellung wurde nicht gespeichert.", { description: "Bitte versuchen Sie es erneut." });
    } finally {
      setSaving(false);
    }
  }

  return <fieldset className="flex items-center gap-2" aria-busy={saving}>
    <legend className="sr-only">Antwortlänge</legend>
    <span aria-hidden className="text-label text-text-secondary">Antworten</span>
    <div className="inline-flex rounded-full border border-border-strong bg-surface p-0.5">
      {OPTIONS.map(option => {
        const checked = depth === option.value;
        return <label key={option.value} title={option.hint} className={cn(
          "relative inline-flex min-h-9 cursor-pointer items-center rounded-full px-3 text-label transition-[background-color,color] duration-150 ease-out has-focus-visible:ring-2 has-focus-visible:ring-ring",
          checked ? "bg-accent-solid text-on-accent" : "text-text hover:bg-muted",
        )}>
          <input type="radio" name={name} value={option.value} checked={checked}
            onChange={() => void choose(option.value)} className="sr-only" />
          {option.label}
          <span className="sr-only">: {option.hint}</span>
        </label>;
      })}
    </div>
  </fieldset>;
}

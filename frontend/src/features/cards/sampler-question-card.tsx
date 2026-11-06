"use client";

import { useId, useState, type FormEvent } from "react";
import { Check, MessageCircleQuestion, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CardOf } from "@/lib/api";
import { cn } from "@/lib/utils";

import { ResultCardFrame } from "./result-cards";

/** Build the chat message for one SAMPLER answer: "Beschwerde · Beginn: Gestern – nach der Arbeit". */
export function formatSamplerAnswer(stepLabel: string, selected: string[], note: string): string {
  const parts = [selected.join(", "), note.trim()].filter(Boolean);
  return `${stepLabel}: ${parts.join(" – ")}`;
}

type SamplerQuestion = CardOf<"sampler_question">["question"];

export type SamplerQuestionFormProps = {
  question: SamplerQuestion;
  /** Present only on the open question. Without it the form renders read-only. */
  onAnswer?: (content: string) => void;
};

/** The answer form of one SAMPLER question: easy choices plus a field to describe it. */
export function SamplerQuestionForm({ question, onAnswer }: SamplerQuestionFormProps) {
  const [selected, setSelected] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);
  const noteId = useId();
  const groupName = useId();
  const active = Boolean(onAnswer) && !sent;
  const canSend = selected.length > 0 || note.trim().length > 0;

  function toggle(option: string) {
    setSelected(current => {
      if (!question.multiple) return [option];
      return current.includes(option) ? current.filter(item => item !== option) : [...current, option];
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!active || !canSend || !onAnswer) return;
    setSent(true);
    onAnswer(formatSamplerAnswer(question.step_label, selected, note));
  }

  return <form onSubmit={submit} className="space-y-4">
    <fieldset disabled={!active} className="space-y-3">
      <legend className="text-label text-text-secondary">
        {question.step_label} · {question.multiple ? "Mehrere Antworten möglich" : "Eine Antwort wählen"}
      </legend>
      <div className="flex flex-wrap gap-2">
        {question.options.map(option => {
          const checked = selected.includes(option);
          return <label key={option} className={cn(
            "relative inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border px-4 text-body transition-[background-color,border-color,color] duration-150 ease-out has-focus-visible:ring-2 has-focus-visible:ring-ring has-disabled:cursor-not-allowed has-disabled:opacity-60",
            checked ? "border-accent-solid bg-accent-subtle text-accent-text" : "border-border-strong bg-surface text-text hover:bg-muted",
          )}>
            <input type={question.multiple ? "checkbox" : "radio"} name={groupName} value={option}
              checked={checked} onChange={() => toggle(option)} className="sr-only" />
            {checked ? <Check aria-hidden className="size-4" strokeWidth={2} /> : null}
            {option}
          </label>;
        })}
      </div>
    </fieldset>
    <div className="space-y-2">
      <Label htmlFor={noteId}>{question.free_text_label}</Label>
      <Textarea id={noteId} rows={2} value={note} disabled={!active} onChange={event => setNote(event.target.value)} />
    </div>
    {active
      ? <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!canSend}><Send />Antworten</Button>
        <p className="text-caption text-text-secondary">Sie können auch frei im Eingabefeld antworten.</p>
      </div>
      : <p role="status" className="text-caption text-text-secondary">{sent ? "Antwort gesendet." : "Diese Frage ist abgeschlossen."}</p>}
  </form>;
}

export type SamplerQuestionCardProps = {
  card: CardOf<"sampler_question">;
  /** Present only on the open question. Older questions render read-only. */
  onAnswer?: (content: string) => void;
};

/** One SAMPLER question as a standalone card. The chat groups them into one SamplerSessionCard. */
export function SamplerQuestionCard({ card: { question }, onAnswer }: SamplerQuestionCardProps) {
  return <ResultCardFrame title={question.question} icon={MessageCircleQuestion}
    badge={<Badge variant="accent" className="tabular">Frage {question.position} von {question.total}</Badge>}>
    <SamplerQuestionForm question={question} onAnswer={onAnswer} />
  </ResultCardFrame>;
}

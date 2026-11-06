"use client";

import { CircleCheck, MessageCircleQuestion } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Enter } from "@/components/ui/enter";
import { Skeleton } from "@/components/ui/skeleton";

import { ResultCardFrame } from "./result-cards";
import { SamplerQuestionForm } from "./sampler-question-card";
import type { SamplerSession, SamplerStep } from "./sampler-session";

function AnsweredSteps({ steps }: { steps: SamplerStep[] }) {
  if (!steps.length) return null;
  return <section aria-label="Ihre Angaben" className="space-y-2 border-t pt-4">
    <h3 className="text-label text-text-secondary">Ihre Angaben ({steps.length})</h3>
    <dl className="grid gap-x-4 gap-y-1 text-body sm:grid-cols-[minmax(0,14rem)_1fr]">
      {steps.map((step) => <div key={step.question.step} className="contents">
        <dt className="text-text-secondary">{step.question.step_label}</dt>
        <dd className="min-w-0 wrap-anywhere">{step.answer}</dd>
      </div>)}
    </dl>
  </section>;
}

export type SamplerSessionCardProps = {
  session: SamplerSession;
  /** Sends the answer to the open question as a chat message. */
  onAnswer?: (content: string) => void;
};

/** All SAMPLER questions of one intake in one card. It switches to the next question in place. */
export function SamplerSessionCard({ session, onAnswer }: SamplerSessionCardProps) {
  const last = session.steps[session.steps.length - 1];
  const answered = session.steps.filter((step) => step.answer !== undefined);

  if (session.state === "done") {
    return <ResultCardFrame title="Ihre Angaben" icon={CircleCheck}
      badge={<Badge variant="accent">Aufnahme abgeschlossen</Badge>}>
      <AnsweredSteps steps={answered} />
    </ResultCardFrame>;
  }

  if (session.state === "loading") {
    return <ResultCardFrame title="Nächste Frage wird vorbereitet…" icon={MessageCircleQuestion}
      badge={<Badge variant="accent" className="tabular">{answered.length} von {last.question.total} beantwortet</Badge>}>
      <div role="status" className="space-y-3">
        <span className="sr-only">Der Lotse bereitet die nächste Frage vor.</span>
        <Skeleton className="h-5 w-2/3" />
        <div className="flex flex-wrap gap-2">
          <Skeleton className="h-10 w-28 rounded-full" />
          <Skeleton className="h-10 w-36 rounded-full" />
          <Skeleton className="h-10 w-24 rounded-full" />
        </div>
      </div>
      <AnsweredSteps steps={answered} />
    </ResultCardFrame>;
  }

  return <ResultCardFrame title={last.question.question} icon={MessageCircleQuestion}
    badge={<Badge variant="accent" className="tabular">Frage {last.question.position} von {last.question.total}</Badge>}>
    {/* The key resets the form and replays the entrance for every new question. */}
    <Enter key={last.question.step}>
      <SamplerQuestionForm question={last.question} onAnswer={session.answerable ? onAnswer : undefined} />
    </Enter>
    <AnsweredSteps steps={answered} />
  </ResultCardFrame>;
}

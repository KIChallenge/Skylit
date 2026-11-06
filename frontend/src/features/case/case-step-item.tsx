"use client";

import { ChevronDown, ClipboardCheck, Clock, Handshake } from "lucide-react";
import { useId } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/ui/state";
import type { CaseStep, CaseStepStatus } from "@/lib/api";

import { StepStatusBadge } from "./step-status-badge";

const categories = {
  info: "Information", form: "Formular", document: "Dokument",
  appointment: "Termin", contact: "Kontakt", escalation: "Persönliche Beratung",
} as const;

export type CaseStepItemProps = {
  step: CaseStep;
  pending?: boolean;
  retryStatus?: CaseStepStatus;
  isNew?: boolean;
  defaultOpen?: boolean;
  onStatusChange: (status: CaseStepStatus) => void;
};

export function CaseStepItem({ step, pending, retryStatus, isNew, defaultOpen = false, onStatusChange }: CaseStepItemProps) {
  const id = useId();
  return (
    <Collapsible defaultOpen={defaultOpen}>
      <div className="flex items-start gap-3">
        <div className="relative z-10 bg-surface py-2">
          <Checkbox id={id} checked={step.status === "done"} disabled={pending}
            onCheckedChange={(checked) => onStatusChange(checked === true ? "done" : "open")} />
        </div>
        <div className="min-w-0 flex-1 pb-6">
          <Label htmlFor={id} className="min-h-10 cursor-pointer py-2 text-body font-semibold wrap-break-word">
            {step.title}
          </Label>
          <div className="flex flex-wrap items-center gap-2">
            <StepStatusBadge status={step.status} />
            {isNew ? <Badge variant="outline">Neu</Badge> : null}
          </div>
          <p className="mt-2 flex items-center gap-1 text-caption text-text-secondary">
            {step.category === "escalation" ? <Handshake aria-hidden className="size-4" strokeWidth={1.5} /> : null}
            {categories[step.category]}
          </p>
          {step.category === "form" && step.status !== "done" ? (
            <Badge variant="caution" className="mt-2"><ClipboardCheck aria-hidden className="size-4" />Von Ihnen zu prüfen</Badge>
          ) : null}
          <div className="mt-2">
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="h-auto min-h-8 max-w-full whitespace-normal text-start"
                aria-label={`Details zu „${step.title}“`}>
                Details <ChevronDown className="size-4" />
              </Button>
            </CollapsibleTrigger>
          </div>
          <CollapsibleContent className="space-y-2 pt-2">
            <p className="text-body text-pretty wrap-break-word text-text-secondary">{step.description}</p>
            {step.due_hint ? (
              <p className="flex items-start gap-2 text-caption text-text-secondary">
                <Clock aria-hidden className="mt-0.5 size-4 shrink-0" strokeWidth={1.5} />
                <span className="wrap-break-word">{step.due_hint}</span>
              </p>
            ) : null}
          </CollapsibleContent>
          <p role="status" className="text-caption text-text-secondary">{pending ? "Änderung wird gespeichert…" : ""}</p>
          {retryStatus ? <ErrorState className="mt-3" title="Änderung nicht gespeichert."
            description="Der Schritt hat wieder seinen bisherigen Status."
            onRetry={() => onStatusChange(retryStatus)} /> : null}
        </div>
      </div>
    </Collapsible>
  );
}

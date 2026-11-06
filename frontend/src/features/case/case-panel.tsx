"use client";

import { ChevronDown, Route, UserRound } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Enter } from "@/components/ui/enter";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { api, type ApiClient, type Case, type CaseStep, type CaseStepStatus } from "@/lib/api";

import { CaseStepItem } from "./case-step-item";

export type CasePanelProps = {
  case: Case | null;
  isLoading?: boolean;
  /** Truthy values show a safe German message, never a raw server error. */
  error?: unknown;
  onRetry: () => void;
  onCaseChange: (updatedCase: Case) => void;
  apiClient?: ApiClient;
};

const subjects = {
  self: "Sie selbst", parent: "Mutter oder Vater", child: "Kind", partner: "Partnerin oder Partner", other: "Andere Person",
} as const;

type Change = { source: Case; updated: CaseStep; pending: boolean; retryStatus?: CaseStepStatus };

function applyChanges(value: Case, updates: Record<string, Change>): Case {
  return { ...value, steps: value.steps.map((step) => {
    const change = updates[step.id];
    // A new supplied case supersedes completed local changes. Pending changes stay visible.
    return change && (change.pending || value === change.source) ? change.updated : step;
  }) };
}

/** Content only. AppShell owns the „Mein Fall“ aside and its scrolling. */
export function CasePanel(props: CasePanelProps) {
  return <PanelContent key={props.case?.id ?? "empty"} {...props} />;
}

function PanelContent({ case: suppliedCase, isLoading = false, error, onRetry, onCaseChange, apiClient = api }: CasePanelProps) {
  const [changes, setChanges] = useState<Record<string, Change>>({});
  const changesRef = useRef(changes);
  const inFlight = useRef(new Set<string>());
  const alive = useRef(true);
  const latest = useRef(suppliedCase);
  const source = useRef(suppliedCase);
  const onChange = useRef(onCaseChange);
  const [initialIds] = useState(() => new Set(suppliedCase?.steps.map((step) => step.id)));
  const [summaryOpen, setSummaryOpen] = useState(false);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const currentCase = suppliedCase ? applyChanges(suppliedCase, changes) : null;
  useLayoutEffect(() => {
    latest.current = currentCase;
    source.current = suppliedCase;
    onChange.current = onCaseChange;
  });

  async function updateStep(stepId: string, status: CaseStepStatus) {
    const snapshot = latest.current;
    const original = snapshot?.steps.find((step) => step.id === stepId);
    if (!snapshot || !original || inFlight.current.has(stepId)) return;
    inFlight.current.add(stepId);
    const change: Change = { source: source.current ?? snapshot, updated: { ...original, status }, pending: true };
    changesRef.current = { ...changesRef.current, [stepId]: change };
    latest.current = applyChanges(snapshot, changesRef.current);
    setChanges(changesRef.current);
    let saved: CaseStep;
    try {
      saved = await apiClient.updateCaseStep(stepId, status);
    } catch {
      if (!alive.current) return;
      // Restore only this step. Other requests and new case.updated data remain intact.
      changesRef.current = { ...changesRef.current, [stepId]: {
        source: change.source,
        updated: original,
        pending: false,
        retryStatus: status,
      } };
      latest.current = source.current ? applyChanges(source.current, changesRef.current) : null;
      inFlight.current.delete(stepId);
      setChanges(changesRef.current);
      return;
    }
    if (!alive.current || !latest.current) return;
    changesRef.current = { ...changesRef.current, [stepId]: { source: source.current ?? snapshot, updated: saved, pending: false } };
    const committed = Object.fromEntries(Object.entries(changesRef.current).filter(([, update]) => !update.pending));
    const base = applyChanges(source.current ?? snapshot, committed);
    const updatedCase = { ...base, steps: base.steps.map((step) => step.id === stepId ? saved : step) };
    latest.current = applyChanges(updatedCase, changesRef.current);
    inFlight.current.delete(stepId);
    setChanges(changesRef.current);
    onChange.current(updatedCase);
  }

  const newCount = currentCase?.steps.filter((step) => !initialIds.has(step.id)).length ?? 0;
  const done = currentCase?.steps.filter((step) => step.status === "done").length ?? 0;
  const total = currentCase?.steps.length ?? 0;
  const sortedSteps = [...(currentCase?.steps ?? [])].sort((a, b) => a.position - b.position);
  const firstUnfinishedId = sortedSteps.find((step) => step.status !== "done")?.id;

  return (
    <div className="min-w-0 p-4 text-text beamer:p-6">
      <h2 className="mb-4 flex items-center gap-2 text-heading"><Route aria-hidden className="size-5" />Mein Fall</h2>
      <p role="status" className="sr-only">{isLoading ? "Mein Fall wird geladen…" : newCount ? `Mein Fall: ${newCount} neue Schritte.` : ""}</p>
      {isLoading ? <div aria-hidden className="space-y-4"><Skeleton className="h-6 w-3/4" /><Skeleton className="h-16 w-full" />
        <Skeleton className="h-2 w-full" />{[0, 1, 2].map((index) => <Skeleton key={index} className="h-24 w-full" />)}</div>
        : error ? <ErrorState title="Ihr Fall konnte nicht geladen werden." onRetry={onRetry} />
        : !currentCase ? <EmptyState icon={Route} title="Noch keine Schritte."
          description="Beschreiben Sie Ihre Lage. Der Lotse legt hier Ihre nächsten Schritte an." />
        : <>
          <h3 className="text-heading text-balance wrap-break-word">{currentCase.title}</h3>
          <p className="mt-2 flex items-center gap-2 text-label text-text-secondary"><UserRound aria-hidden className="size-4 shrink-0" />Für: {subjects[currentCase.subject]}</p>
          <Collapsible open={summaryOpen} onOpenChange={setSummaryOpen} className="mt-4">
            {!summaryOpen ? <p className="line-clamp-2 text-body text-pretty wrap-break-word text-text-secondary">{currentCase.summary}</p> : null}
            <CollapsibleContent><p className="text-body text-pretty wrap-break-word text-text-secondary">{currentCase.summary}</p></CollapsibleContent>
            <CollapsibleTrigger asChild><Button variant="ghost" size="sm" className="mt-1">
              {summaryOpen ? "Zusammenfassung kürzen" : "Ganze Zusammenfassung"}<ChevronDown />
            </Button></CollapsibleTrigger>
          </Collapsible>
          <div className="my-6 space-y-2">
            <p className="text-label tabular" role="status">{done} von {total} erledigt</p>
            <Progress value={total ? done / total * 100 : 0} aria-label="Erledigte Fallschritte"
              aria-valuenow={total ? done / total * 100 : 0}
              aria-valuetext={`${done} von ${total} erledigt`} className="motion-reduce:[&_[data-slot=progress-indicator]]:transition-none" />
          </div>
          {total ? <ol aria-label="Ihre nächsten Schritte" className="relative before:absolute before:inset-y-4 before:start-2 before:border-s">
            {sortedSteps.map((step, index) => <li key={step.id}>
              <Enter index={index}>
                <CaseStepItem step={step} pending={changes[step.id]?.pending} retryStatus={changes[step.id]?.retryStatus}
                  defaultOpen={step.id === firstUnfinishedId}
                  isNew={!initialIds.has(step.id)} onStatusChange={(status) => void updateStep(step.id, status)} />
              </Enter>
            </li>)}
          </ol> : <EmptyState icon={Route} title="Noch keine Schritte."
            description="Beschreiben Sie Ihre Lage. Der Lotse legt hier Ihre nächsten Schritte an." />}
        </>}
    </div>
  );
}

"use client";

import { useState, type ReactNode } from "react";
import { CircleCheck, CircleDashed, CircleX, Info, ScanSearch, Search, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { api, type ApiClient, type MessageTransparency } from "@/lib/api";
import { ConfidenceBadge, SourceLink } from "./metadata";
import { useTransparency, type TransparencyResource } from "./use-transparency";

export type TransparencyDrawerProps = {
  /** Only supply a persisted assistant message ID. Null hides the drawer. */
  messageId: string | null | undefined;
  client?: ApiClient;
  /** Optional shared resource. AnswerFooter supplies this to avoid a second request. */
  resource?: TransparencyResource;
};

export function TransparencySkeleton() {
  return <div role="status" className="space-y-4">
    <span className="sr-only">Angaben zur Antwort werden geladen…</span>
    <Skeleton className="h-6 w-40" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-3/4" />
  </div>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="space-y-3"><h3 className="text-heading text-text">{title}</h3>{children}</section>;
}

const escalationLabels: Record<string, string> = {
  medical_question: "Medizinische Frage", legal_uncertainty: "Rechtliche Frage",
  no_source: "Keine verlässliche Quelle", user_stuck: "Wunsch nach persönlicher Beratung",
  social_crisis: "Soziale Notlage", emergency: "Notfall",
};

function Details({ data, client }: { data: MessageTransparency; client: ApiClient }) {
  const retrieval = data.entries.filter(({ event_type }) => event_type === "retrieval");
  return <div className="space-y-8 text-body text-text-secondary">
    <Section title="Sicherheit">
      <ConfidenceBadge confidence={data.confidence} tooltip={false} />
      <p className="text-pretty">{data.confidence.reason}</p>
      <p className="text-caption">Die Stufe beschreibt die Beleglage dieser Antwort. Sie garantiert keine Richtigkeit.</p>
    </Section>
    <Section title="Quellen">
      {data.sources.length ? <ul className="space-y-3">{data.sources.map((source, index) =>
        <li key={`${source.url}-${index}`}><SourceLink source={source} client={client} /></li>)}</ul>
        : <p>Für diese Antwort liegen keine Quellen vor.</p>}
    </Section>
    <Section title="Schritte des Lotsen">
      {!data.entries.length && <p>Für diese Antwort liegen keine Protokolldaten vor.</p>}
      {!!data.entries.length && !retrieval.length && !data.tools.length && <p>Keine Wissenssuche oder weiteren Schritte erfasst.</p>}
      <ul className="space-y-3">
        {retrieval.map((entry) => <li key={entry.id} className="flex items-start gap-2">
          <Search aria-hidden className="mt-1 size-4 shrink-0" strokeWidth={1.5} /><div><p className="text-label text-text">Wissenssuche</p><p>{entry.summary}</p></div>
        </li>)}
        {data.tools.map((tool, index) => { const Icon = tool.ok ? CircleCheck : CircleX;
          return <li key={`${tool.name}-${index}`} className="flex items-start gap-2">
            <Icon aria-hidden className={`mt-1 size-4 shrink-0 ${tool.ok ? "text-accent-text" : "text-caution-text"}`} strokeWidth={1.5} />
            <div><p className="text-text">{tool.label}</p><p className="text-caption">{tool.ok ? "Erfolgreich" : "Nicht erfolgreich"}</p></div>
          </li>;
        })}
      </ul>
    </Section>
    <Section title="Schutzregeln">
      {data.guardrails.length ? <ul className="space-y-3">{data.guardrails.map((rule, index) => <li key={`${rule.code}-${index}`} className="flex items-start gap-2">
        <ShieldAlert aria-hidden className="mt-1 size-4 shrink-0 text-caution-text" strokeWidth={1.5} /><div>
          <p className="text-label text-text">{rule.code === "emergency" || rule.code === "social_crisis" ? "Notfallregel ausgelöst" : "Schutzregel ausgelöst"}</p>
          <p>{rule.summary}</p>
        </div>
      </li>)}</ul> : <p>Keine Schutzregel im Protokoll erfasst.</p>}
    </Section>
    <Section title="Modell">
      <p className="break-words text-text">{data.model ?? "Modell nicht erfasst"}</p>
      {data.provider && <p className="break-words">Anbieter: {data.provider}</p>}
      {data.provider === "eustella" && <p>EU-Modell, Wien</p>}
    </Section>
    {data.escalation && <Section title="Übergabe an einen Menschen">
      <p>{escalationLabels[data.escalation.reason_code] ?? data.escalation.reason_code}</p>
      <p className="text-text">{data.escalation.target.name}</p>
    </Section>}
    <div className="flex items-start gap-2 rounded-md bg-subtle p-4 text-caption">
      <Info aria-hidden className="size-4 shrink-0" strokeWidth={1.5} />
      <p>Diese Antwort hat eine KI erstellt. Sie ersetzt keine Beratung. Die zuständige Stelle entscheidet.</p>
    </div>
  </div>;
}

export function TransparencyDrawer({ messageId, client = api, resource }: TransparencyDrawerProps) {
  const [open, setOpen] = useState(false);
  const ownResource = useTransparency(messageId, client, open && !resource);
  const { state, retry } = resource ?? ownResource;
  if (!messageId) return null;
  return <Sheet open={open} onOpenChange={setOpen}>
    <SheetTrigger asChild><Button variant="ghost" size="sm"><ScanSearch aria-hidden />Warum diese Antwort?</Button></SheetTrigger>
    <SheetContent className="w-full gap-0 sm:max-w-120">
      <SheetHeader className="border-b pe-12">
        <SheetTitle>Warum diese Antwort?</SheetTitle>
        <SheetDescription>Quellen und Schritte zu dieser gespeicherten Antwort.</SheetDescription>
      </SheetHeader>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-6">
        {state.status === "loading" && <TransparencySkeleton />}
        {state.status === "empty" && <EmptyState icon={CircleDashed} title="Keine Protokolldaten" description="Für diese Antwort liegen keine Protokolldaten vor." />}
        {state.status === "error" && <ErrorState title="Angaben nicht verfügbar" description="Die Angaben zu dieser Antwort konnten nicht geladen werden." onRetry={retry} />}
        {state.status === "ready" && <Details data={state.data} client={client} />}
      </div>
    </SheetContent>
  </Sheet>;
}

"use client";

import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ApiClient, type Source } from "@/lib/api";
import { AnswerStateBadge, ConfidenceBadge, SourceLink } from "./metadata";
import { TransparencyDrawer } from "./transparency-drawer";
import { useTransparency } from "./use-transparency";
import { useState } from "react";

export type AnswerFooterProps = {
  /** Pass null while streaming. Set this only after the assistant message was saved. */
  messageId: string | null | undefined;
  client?: ApiClient;
  /** Sources already received from the stream, displayed while metadata loads. */
  initialSources?: Source[];
};

export function AnswerFooter({ messageId, client = api, initialSources = [] }: AnswerFooterProps) {
  const resource = useTransparency(messageId, client);
  const { state } = resource;
  const [expanded, setExpanded] = useState(false);
  if (!messageId) return null;
  const data = state.status === "ready" ? state.data : undefined;
  const sources = data?.sources ?? initialSources;
  return <footer aria-label="Angaben zur Antwort" className="mt-4 space-y-3 border-t pt-4">
    {data && <AnswerStateBadge data={data} />}
    <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
      <span className="inline-flex items-center gap-1 text-caption text-text-secondary"><BookOpen aria-hidden className="size-4" strokeWidth={1.5} />Quellen</span>
      {sources.length ? <ul className="flex min-w-0 flex-1 flex-wrap gap-x-4 gap-y-2">
        {sources.slice(0, expanded ? undefined : 3).map((source, index) => <li className="min-w-0" key={`${source.url}-${index}`}><SourceLink source={source} client={client} /></li>)}
        {sources.length > 3 && <li><Button variant="link" size="sm" className="h-auto p-0 text-caption" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "Weniger Quellen" : `+${sources.length - 3} weitere`}</Button></li>}
      </ul> : <span className="text-caption text-text-secondary">{state.status === "loading" ? "Quellen werden geladen…" : "Keine Quellen"}</span>}
    </div>
    <div className="flex flex-wrap items-center gap-3">
      {state.status === "loading" ? <div role="status" className="flex flex-wrap items-center gap-3">
        <span className="sr-only">Sicherheit und Modell werden geladen…</span>
        <Skeleton className="h-6 w-40" /><Skeleton className="h-4 w-32" />
      </div> : <>
        <ConfidenceBadge confidence={data?.confidence} />
        <span className="break-words text-caption text-text-secondary">{data ? data.model ?? "Modell nicht erfasst" : "Modell nicht verfügbar"}</span>
      </>}
      <TransparencyDrawer messageId={messageId} client={client} resource={resource} />
    </div>
    {state.status === "error" && <p className="text-caption text-text-secondary">Die Angaben konnten nicht geladen werden. Öffnen Sie „Warum diese Antwort?“ für einen neuen Versuch.</p>}
  </footer>;
}

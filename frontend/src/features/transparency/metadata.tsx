"use client";

import { CircleDashed, ExternalLink, Handshake, ShieldAlert, SignalHigh, SignalLow, SignalMedium, Siren } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ApiClient, Confidence, MessageTransparency, Source } from "@/lib/api";

/** `tooltip={false}` where the reason is already visible as text, as in the drawer. */
export function ConfidenceBadge({ confidence, tooltip = true }: { confidence?: Confidence; tooltip?: boolean }) {
  const level = confidence?.level;
  const Icon = level === "hoch" ? SignalHigh : level === "mittel" ? SignalMedium : level === "niedrig" ? SignalLow : CircleDashed;
  const badge = <Badge variant={level === "hoch" ? "accent" : level === "mittel" ? "caution" : level === "niedrig" ? "caution-strong" : "neutral"}>
    <Icon aria-hidden />{level ? `Sicherheit: ${level}` : "Sicherheit nicht verfügbar"}
  </Badge>;
  if (!confidence || !tooltip) return badge;
  return <Tooltip>
    <TooltipTrigger asChild><span tabIndex={0} className="inline-flex rounded-full">{badge}</span></TooltipTrigger>
    <TooltipContent className="max-w-answer">{confidence.reason}</TooltipContent>
  </Tooltip>;
}

export function AnswerStateBadge({ data }: { data: MessageTransparency }) {
  if (data.guardrails.some(({ code }) => code === "emergency" || code === "social_crisis")) {
    return <Badge variant="emergency"><Siren aria-hidden />Notfall</Badge>;
  }
  if (data.escalation?.reason_code === "medical_question") {
    return <Badge variant="caution" className="whitespace-normal text-start"><ShieldAlert aria-hidden />Medizinische Frage – an Fachleute übergeben</Badge>;
  }
  return data.escalation ? <Badge variant="caution"><Handshake aria-hidden />An einen Menschen übergeben</Badge> : null;
}

const retrievedFormat = new Intl.DateTimeFormat("de-AT", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });

export function SourceLink({ source, client }: { source: Source; client: ApiClient }) {
  const href = client.resolveUrl(source.url);
  // Only document-relative and HTTP(S) destinations are navigable.
  const safe = /^https?:\/\//i.test(href) || (/^\//.test(href) && !href.startsWith("//"));
  const label = safe ? <a href={href} target="_blank" rel="noopener noreferrer"
    className="inline-flex min-w-0 items-start gap-1 rounded-sm text-caption text-accent-text underline underline-offset-4">
    <span className="min-w-0 break-words">{source.publisher ? `${source.publisher} · ` : ""}{source.title}</span>
    <ExternalLink aria-hidden className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.5} />
    <span className="sr-only"> (öffnet in neuem Tab)</span>
  </a> : <span className="text-caption text-text-secondary">{source.publisher} · {source.title}</span>;
  if (!source.retrieved) return label;
  // The knowledge base records the day the team read the official source.
  return <span className="inline-flex min-w-0 flex-col items-start gap-1">
    {label}
    <span className="text-caption text-text-secondary tabular">Stand: {retrievedFormat.format(new Date(source.retrieved))}</span>
  </span>;
}

"use client";

import { useId, useState, type ReactNode } from "react";
import { Building2, Check, CircleHelp, ClipboardCheck, Copy, Download, ExternalLink, FileText, Handshake, Mail, MapPin, Phone, Quote, Route, UserRound, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Enter } from "@/components/ui/enter";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { api, toCard, toCards, toDocumentSummary, type Card as ApiCard, type CardOf, type Contact, type FieldSpec } from "@/lib/api";
import { downloadFile } from "@/lib/api/download";
import { cn } from "@/lib/utils";

import { EmailDraftCard } from "./email-draft-card";
import { AppointmentCard, ProviderListCard } from "./provider-cards";
import { SamplerQuestionCard } from "./sampler-question-card";

const text = (value: unknown): string => typeof value === "string" ? value : "";

/** Only HTTP links and backend-relative paths can become navigation targets. */
function webUrl(value: unknown): string | undefined {
  const url = text(value).trim();
  if (!url || !/^(https?:\/\/|\/(?!\/))/i.test(url)) return undefined;
  try { return api.resolveUrl(url); } catch { return undefined; }
}

export type ResultCardFrameProps = {
  title: string;
  icon: LucideIcon;
  badge?: ReactNode;
  children: ReactNode;
};

export function ResultCardFrame({ title, icon: Icon, badge, children }: ResultCardFrameProps) {
  const id = useId();
  return <Card role="region" aria-labelledby={id} className="min-w-0 gap-4 rounded-lg wrap-anywhere">
    <CardHeader>
      <div className="flex flex-wrap items-start gap-3">
        <Icon aria-hidden className="size-6 shrink-0 text-text-secondary" strokeWidth={2} />
        <h2 id={id} className="min-w-0 flex-1 text-heading text-balance">{title}</h2>
        {badge}
      </div>
    </CardHeader>
    <CardContent className="space-y-4 text-body">{children}</CardContent>
  </Card>;
}

function External({ url, children }: { url: unknown; children: ReactNode }) {
  const href = webUrl(url);
  return href ? <Button asChild variant="link" className="min-h-8 whitespace-normal text-start">
    <a href={href} target="_blank" rel="noopener noreferrer">{children}<ExternalLink aria-hidden /><span className="sr-only"> (neuer Tab)</span></a>
  </Button> : null;
}

export function FileAction({ url, filename, original = false, label, icon: Icon = Download, doneMessage, accept }: { url: string; filename: string; original?: boolean; label?: string; icon?: LucideIcon; doneMessage?: string; accept?: readonly string[] }) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error, setError] = useState("");
  async function run() {
    if (state === "loading") return;
    setState("loading");
    try {
      await downloadFile(url, { filename, open: original, accept });
      setState("done");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Die Datei konnte nicht geladen werden.");
      setState("error");
    }
  }
  return <div className="space-y-3">
    {original && webUrl(url) ? <Button asChild variant="secondary" aria-disabled={state === "loading"}>
      <a href={webUrl(url)} target="_blank" rel="noopener noreferrer" onClick={event => { event.preventDefault(); void run(); }}><ExternalLink />{state === "loading" ? "Datei wird geladen…" : "Dokument öffnen"}<span className="sr-only"> (neuer Tab)</span></a>
    </Button> : <Button variant="secondary" disabled={state === "loading"} onClick={run}>
      {original ? <ExternalLink /> : <Icon />}
      {state === "loading" ? "Datei wird geladen…" : original ? "Dokument öffnen" : label ?? "PDF herunterladen"}
    </Button>}
    <p role="status" className="text-caption text-text-secondary">{state === "done" ? original ? "Dokument geöffnet." : doneMessage ?? "Download gestartet." : ""}</p>
    {state === "error" && <ErrorState title="Datei nicht verfügbar" description={error} onRetry={run} />}
  </div>;
}

const topics: Record<string, string> = {
  rehabilitation: "Rehabilitation", care_allowance: "Pflegegeld", mobile_care: "Mobile Pflege",
  follow_up: "Nachsorge", aids: "Hilfsmittel", transport: "Fahrtkosten",
  prescription_fee_exemption: "Rezeptgebührenbefreiung", nutrition: "Ernährung",
  social_services: "Soziale Dienste", other: "Empfehlung",
};

export type QuoteBlockProps = { quote: string; section?: string | null; label?: string };
export function QuoteBlock({ quote, section, label }: QuoteBlockProps) {
  return <figure className="space-y-2 border-s-2 border-accent-border ps-4">
    {label && <Badge variant="neutral">{label}</Badge>}
    <blockquote className="max-w-answer whitespace-pre-wrap text-body">„{quote}“</blockquote>
    <figcaption className="text-caption text-text-secondary">{section ? `Abschnitt ${section}` : "Abschnitt nicht angegeben"}</figcaption>
  </figure>;
}

export type DocumentSummaryCardProps = { card: CardOf<"document_summary">; filename?: string };
export function DocumentSummaryCard({ card, filename }: DocumentSummaryCardProps) {
  const { extraction } = toDocumentSummary(card);
  let original = "";
  try { original = api.documentFileUrl(card.document_id); } catch { /* FileAction reports missing configuration on click. */ }
  return <ResultCardFrame title="Aus Ihrem Dokument" icon={FileText}>
    {filename && <p className="text-label">{filename}</p>}
    {extraction ? <>
      {extraction.issuer && <p className="text-caption text-text-secondary">{extraction.issuer}{extraction.document_date ? ` · ${formatDate(extraction.document_date)}` : ""}</p>}
      <p className="flex items-start gap-2 text-body text-text-secondary"><Quote aria-hidden className="size-5 shrink-0" />Wörtlich zitiert. Der Lotse bewertet keine Befunde.</p>
      {extraction.documented_recommendations.length === 0 && extraction.follow_up_appointments.length === 0
        ? <EmptyState icon={Quote} title="Keine Empfehlungen ausgelesen." /> : null}
      {extraction.documented_recommendations.map((item, index) => <QuoteBlock key={index} quote={item.quote} section={item.section} label={topics[item.topic] ?? "Empfehlung"} />)}
      {extraction.follow_up_appointments.map((item, index) => <div key={index} className="space-y-2">
        <QuoteBlock quote={item.quote} label="Nachsorge" />
        <p className="text-caption text-text-secondary">{item.what}{item.when ? ` · ${item.when}` : ""}</p>
      </div>)}
      {extraction.warnings_in_document.map((warning, index) => <QuoteBlock key={index} quote={warning} label="Hinweis im Dokument" />)}
      <div className="flex items-start gap-2 rounded-md bg-caution-subtle p-3 text-caution-text">
        <CircleHelp aria-hidden className="size-5 shrink-0" />
        <p>{extraction.confidence_note || "Die Auslesung kann Fehler enthalten. Vergleichen Sie die Zitate mit dem Original."}</p>
      </div>
    </> : <EmptyState icon={FileText} title="Dokumentinhalt nicht verfügbar." description="Öffnen Sie das Original und prüfen Sie die Angaben." />}
    <FileAction url={original} filename="original" original />
  </ResultCardFrame>;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("de-AT").format(date);
}

export type LeistungCardProps = { card: CardOf<"leistung"> };
export function LeistungCard({ card: { leistung } }: LeistungCardProps) {
  return <ResultCardFrame title={leistung.title} icon={Route}>
    <p>{leistung.short}</p>
    <p className="text-label">Könnte in Frage kommen. Die zuständige Stelle entscheidet.</p>
    <TextList title="Voraussetzungen" items={leistung.conditions} />
    <TextList title="Benötigte Unterlagen" items={leistung.documents_needed} />
    <p className="text-text-secondary">Zuständig: {leistung.office_hint}</p>
    <External url={leistung.source.url}>{leistung.source.publisher} · {leistung.source.title}</External>
  </ResultCardFrame>;
}

function TextList({ title, items }: { title: string; items: string[] }) {
  return items.length ? <section className="space-y-2"><h3 className="text-heading">{title}</h3><ul className="list-disc space-y-1 ps-5">{items.map((item, index) => <li key={index}>{item}</li>)}</ul></section> : null;
}

const origins: Record<string, string> = { conversation: "aus dem Gespräch", document: "aus dem Dokument", profile: "aus Ihrem Profil" };

export type FormDraftCardProps = { card: CardOf<"form_draft"> };
export function FormDraftCard({ card: { form_draft: draft } }: FormDraftCardProps) {
  const [expanded, setExpanded] = useState(false);
  const fieldId = useId();
  const shown = expanded ? draft.filled : draft.filled.slice(0, 5);
  return <ResultCardFrame title={draft.title} icon={ClipboardCheck} badge={<Badge variant="caution"><ClipboardCheck aria-hidden />Von Ihnen zu prüfen</Badge>}>
    <p>Der Lotse hat den Antrag vorausgefüllt. Prüfen Sie jedes Feld. Sie unterschreiben und senden ihn selbst. Die zuständige Stelle entscheidet.</p>
    <section className="space-y-3">
      <h3 className="text-heading">Ausgefüllt ({draft.filled.length})</h3>
      <dl id={fieldId} className="space-y-3">
        {shown.map((field, index) => <div key={`${field.key}-${index}`} className="rounded-md bg-subtle p-3">
          <dt className="text-label">{field.label}</dt><dd>{field.value}<span className="block text-caption text-text-secondary">Herkunft: {origins[field.source] ?? "nicht angegeben"}</span></dd>
        </div>)}
      </dl>
      {!draft.filled.length && <p className="text-text-secondary">Noch keine Felder ausgefüllt.</p>}
      {draft.filled.length > 5 && <Button variant="link" aria-expanded={expanded} aria-controls={fieldId} onClick={() => setExpanded(!expanded)}>{expanded ? "Weniger anzeigen" : `Alle ${draft.filled.length} anzeigen`}</Button>}
    </section>
    <FieldGroup title="Fehlt noch" fields={draft.missing} icon={CircleHelp} />
    <FieldGroup title="Füllen andere aus" fields={draft.to_be_filled_by_others} icon={UserRound} />
    <FileAction url={draft.pdf_url} filename={`${draft.form_id.replace(/[^a-z0-9_-]/gi, "_")}.pdf`} />
  </ResultCardFrame>;
}

function FieldGroup({ title, fields, icon: Icon }: { title: string; fields: FieldSpec[]; icon: LucideIcon }) {
  return <section className="space-y-2"><h3 className="flex items-center gap-2 text-heading"><Icon aria-hidden className="size-5" />{title} ({fields.length})</h3>
    {fields.length ? <ul className="space-y-2 rounded-md bg-caution-subtle p-3 text-caution-text">{fields.map((field, index) => <li key={`${field.key}-${index}`}><span className="text-label">{field.label}</span>{field.hint && <p>{field.hint}</p>}</li>)}</ul> : <p className="text-text-secondary">Keine Felder in dieser Gruppe.</p>}
  </section>;
}

export function ContactDetails({ contact }: { contact: Contact }) {
  const phone = text(contact.phone).trim();
  const phoneHref = phone.replace(/[^+\d]/g, "");
  return <div className="space-y-2">
    <p className="text-label">{contact.name}</p>
    {phoneHref && <Button asChild variant="secondary"><a href={`tel:${phoneHref}`}><Phone aria-hidden />{phone} anrufen</a></Button>}
    {text(contact.hours) && <p className="text-text-secondary">{text(contact.hours)}</p>}
    {text(contact.note) && <p>{text(contact.note)}</p>}
    <External url={contact.url}>Website</External>
  </div>;
}

export type OfficeCardProps = { card: CardOf<"office"> };
export function OfficeCard({ card: { office } }: OfficeCardProps) {
  const email = text(office.email).trim();
  return <ResultCardFrame title={office.name} icon={Building2}>
    <p className="text-label">{office.organisation}</p>
    <address className="flex items-start gap-2 not-italic"><MapPin aria-hidden className="size-5 shrink-0" /><span>{office.address}<br />{text(office.postal_code)} {text(office.city)}</span></address>
    <ContactDetails contact={{ ...office, name: "Kontakt" }} />
    {email && /^[^\s@?]+@[^\s@?]+$/.test(email) && <Button asChild variant="link" className="whitespace-normal"><a href={`mailto:${encodeURIComponent(email).replace(/%40/g, "@")}`}><Mail aria-hidden />{email}</a></Button>}
    <External url={office.maps_url}>Auf der Karte</External>
  </ResultCardFrame>;
}

const reasons: Record<string, string> = { emergency: "Notfall", medical_question: "Medizinische Frage", legal_uncertainty: "Rechtliche Frage", no_source: "Keine verlässliche Quelle", user_stuck: "Wunsch nach persönlicher Beratung", social_crisis: "Soziale Notlage" };

export type CopyButtonProps = {
  value: string;
  label?: string;
  doneMessage?: string;
  errorDescription?: string;
};
export function CopyButton({
  value,
  label = "Zusammenfassung kopieren",
  doneMessage = "Zusammenfassung kopiert.",
  errorDescription = "Markieren Sie die Zusammenfassung und kopieren Sie den Text selbst. Sie können den Text auch vorlesen.",
}: CopyButtonProps) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  async function copy() {
    if (state === "loading") return;
    setState("loading");
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        navigator.clipboard.writeText(value),
        new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error()), 5000); }),
      ]);
      setState("done");
    } catch { setState("error"); }
    finally { if (timer) clearTimeout(timer); }
  }
  return <div className="space-y-3">
    <Button variant="secondary" disabled={state === "loading"} onClick={copy}>{state === "done" ? <Check /> : <Copy />}{state === "done" ? "Kopiert" : state === "loading" ? "Wird kopiert…" : label}</Button>
    <p role="status" className="text-caption text-text-secondary">{state === "done" ? doneMessage : ""}</p>
    {state === "error" && <ErrorState title="Kopieren nicht möglich" description={errorDescription} onRetry={copy} />}
  </div>;
}

export type EscalationCardProps = { card: CardOf<"escalation"> };
export function EscalationCard({ card: { escalation } }: EscalationCardProps) {
  return <ResultCardFrame title={reasons[escalation.reason_code] ?? "Persönliche Beratung"} icon={Handshake} badge={<Badge variant="caution">Menschliche Beratung</Badge>}>
    <ContactDetails contact={escalation.target} />
    <section className="space-y-2"><h3 className="text-heading">Zum Vorlesen am Telefon</h3><p className="max-w-answer whitespace-pre-wrap rounded-md bg-caution-subtle p-4 text-caution-text">{escalation.handover_summary}</p></section>
    <CopyButton value={escalation.handover_summary} />
    <p className="text-caption text-text-secondary">Sie nehmen selbst Kontakt auf. Der Lotse sendet keine Daten.</p>
  </ResultCardFrame>;
}

export type ResultCardProps = {
  card: unknown;
  /** Sends a chat message for a card action, e.g. "Termin vorschlagen". */
  onSend?: (content: string) => void;
  /** Only the latest answer can hold the open SAMPLER question. */
  latest?: boolean;
};
export function ResultCard({ card: value, onSend, latest = false }: ResultCardProps) {
  const card = toCard(value);
  if (!card) return <EmptyState icon={FileText} title="Ergebnis nicht verfügbar." description="Die Angaben sind unvollständig oder nicht lesbar." />;
  switch (card.type) {
    case "leistung": return <LeistungCard card={card} />;
    case "document_summary": return <DocumentSummaryCard card={card} />;
    case "form_draft": return <FormDraftCard card={card} />;
    case "office": return <OfficeCard card={card} />;
    case "escalation": return <EscalationCard card={card} />;
    case "email_draft": return <EmailDraftCard card={card} />;
    case "provider_list": return <ProviderListCard card={card} onSend={onSend} />;
    case "appointment": return <AppointmentCard card={card} />;
    case "sampler_question": return <SamplerQuestionCard card={card} onAnswer={latest ? onSend : undefined} />;
    default: return <ResultCardFrame title="Weitere Angaben" icon={FileText}>
      <p>Prüfen Sie diese Angaben mit der zuständigen Stelle.</p>
    </ResultCardFrame>;
  }
}

export type ResultCardsProps = {
  cards: unknown;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  /** Sends a chat message for a card action. */
  onSend?: (content: string) => void;
  /** Only the latest answer can hold the open SAMPLER question. */
  latest?: boolean;
  className?: string;
};

/** Display validated cards. SSE and persisted copies share the escalation ID. */
export function ResultCards({ cards: values, loading = false, error, onRetry, onSend, latest = false, className }: ResultCardsProps) {
  const ids = new Set<string>();
  const valid = toCards(values);
  // A turn can prepare the same form twice. Only its latest draft is shown, at the first position.
  const latestForms = new Map(valid.flatMap(card => card.type === "form_draft" ? [[card.form_draft.form_id, card] as const] : []));
  const cards = valid.flatMap((card): ApiCard[] => {
    if (card.type === "form_draft") {
      const latest = latestForms.get(card.form_draft.form_id);
      if (!latest) return [];
      latestForms.delete(card.form_draft.form_id);
      return [latest];
    }
    if (card.type !== "escalation") return [card];
    if (ids.has(card.escalation.id)) return [];
    ids.add(card.escalation.id);
    return [card];
  });
  return <div className={cn("grid gap-4", className)}>
    {cards.map((card, index) => <Enter key={card.type === "escalation" ? `escalation-${card.escalation.id}` : `${card.type}-${index}`} index={index}><ResultCard card={card} onSend={onSend} latest={latest} /></Enter>)}
    {loading && <div role="status" aria-label="Ergebnisse werden geladen" className="space-y-3"><Skeleton className="h-8 w-1/2" /><Skeleton className="h-24 w-full" /><span className="sr-only">Ergebnisse werden geladen…</span></div>}
    {error ? <ErrorState title="Ergebnisse konnten nicht geladen werden." onRetry={onRetry} /> : null}
    {!loading && !error && !cards.length && <EmptyState icon={FileText} title="Noch keine Ergebnisse." description="Der Lotse zeigt hier Ihre nächsten Schritte und Unterlagen." />}
  </div>;
}

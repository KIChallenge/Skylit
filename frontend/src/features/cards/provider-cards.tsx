"use client";

import { CalendarCheck, CalendarClock, CalendarPlus, Download, ExternalLink, FlaskConical, Landmark, LocateFixed, Mail, MapPin, Phone, Stethoscope } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/state";
import { useCalendar } from "@/features/calendar";
import { useLocation } from "@/features/location";
import type { CardOf } from "@/lib/api";

import { FileAction, ResultCardFrame } from "./result-cards";

type Provider = CardOf<"provider_list">["providers"][number];

const KIND_LABELS: Record<string, string> = {
  gp: "Allgemeinmedizin",
  specialist: "Fachärztin oder Facharzt",
  care_counselling: "Pflegeberatung",
  mobile_care: "Mobile Pflege",
  therapy: "Therapie",
  course: "Kurs",
};

const TIME_ZONE = "Europe/Vienna";

export const kindLabel = (kind: string) => KIND_LABELS[kind] ?? "Anbieter";

/** "Allgemeinmedizin · Diabetes". The specialty is left out when it repeats the type. */
export function providerKind(provider: { kind: string; specialty?: string | null }): string {
  const kind = kindLabel(provider.kind);
  const specialty = provider.specialty?.trim();
  return specialty && specialty.toLowerCase() !== kind.toLowerCase() ? `${kind} · ${specialty}` : kind;
}

/** "ca. 1,2 km" in Austrian number format. Very short distances read "unter 100 m". */
export function formatDistance(km: number | null | undefined): string | null {
  if (km === null || km === undefined || !Number.isFinite(km)) return null;
  if (km < 0.1) return "unter 100 m";
  return `ca. ${new Intl.NumberFormat("de-AT", { maximumFractionDigits: 1, minimumFractionDigits: 1 }).format(km)} km`;
}

/** "Dienstag, 10. November 2026, 09:00–09:45 Uhr" in Vienna time. */
export function formatAppointment(start: string, end: string): string {
  const from = new Date(start);
  const to = new Date(end);
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return `${start} – ${end}`;
  const day = new Intl.DateTimeFormat("de-AT", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: TIME_ZONE }).format(from);
  const time = new Intl.DateTimeFormat("de-AT", { hour: "2-digit", minute: "2-digit", timeZone: TIME_ZONE });
  return `${day}, ${time.format(from)}–${time.format(to)} Uhr`;
}

const demoBadge = <Badge variant="neutral"><FlaskConical aria-hidden />Demo-Daten</Badge>;

function CallButton({ phone, name, size = "sm" }: { phone?: string | null; name: string; size?: "sm" | "default" }) {
  const number = (phone ?? "").trim();
  const href = number.replace(/[^+\d]/g, "");
  if (!href) return null;
  return <Button asChild variant="secondary" size={size}>
    <a href={`tel:${href}`} aria-label={`${name} anrufen: ${number}`}><Phone aria-hidden />{number}</a>
  </Button>;
}

function ProviderAddress({ provider }: { provider: Provider }) {
  if (!provider.address) return null;
  return <address className="flex items-start gap-2 not-italic text-text-secondary">
    <MapPin aria-hidden className="mt-0.5 size-4 shrink-0" />
    <span>{provider.address}{provider.postal_code && !provider.address.includes(provider.postal_code) ? `, ${provider.postal_code} Wien` : ""}</span>
  </address>;
}

export type ProviderListCardProps = {
  card: CardOf<"provider_list">;
  /** Sends a follow-up request to the Lotse as a chat message. */
  onSend?: (content: string) => void;
};

const openDataBadge = <Badge variant="outline"><Landmark aria-hidden />Offene Daten Stadt Wien</Badge>;

/** Card badge: demo only, open data only, or both. */
function sourceBadge(providers: Provider[]) {
  const demo = providers.some((provider) => provider.demo !== false);
  const real = providers.some((provider) => provider.demo === false);
  if (demo && real) return <div className="flex flex-wrap gap-2">{openDataBadge}{demoBadge}</div>;
  return real ? openDataBadge : demoBadge;
}

/** Nearby providers, nearest first, with call and follow-up actions. */
export function ProviderListCard({ card: { providers, origin }, onSend }: ProviderListCardProps) {
  const location = useLocation();
  if (!providers.length) {
    return <ResultCardFrame title="Anbieter in Ihrer Nähe" icon={Stethoscope} badge={demoBadge}>
      <EmptyState icon={Stethoscope} title="Keine passenden Anbieter gefunden." description="Fragen Sie den Lotsen nach einer anderen Art von Anbieter oder einer anderen Postleitzahl." />
    </ResultCardFrame>;
  }
  const mixed = providers.some((p) => p.demo === false) && providers.some((p) => p.demo !== false);
  const hasReal = providers.some((p) => p.demo === false);
  const hasDemo = providers.some((p) => p.demo !== false);
  const fromLocation = origin === "location";

  async function searchFromLocation() {
    if (!location || !onSend) return;
    const coords = location.coords ?? await location.request();
    if (coords) onSend("Bitte suchen Sie die Anbieter noch einmal ab meinem Standort.");
    else toast("Standort nicht verfügbar. Der Lotse rechnet weiter ab Ihrer Postleitzahl.");
  }

  return <ResultCardFrame title="Anbieter in Ihrer Nähe" icon={Stethoscope} badge={sourceBadge(providers)}>
    <ol className="divide-y divide-border" aria-label="Anbieter, nächster zuerst">
      {providers.map(provider => {
        const distance = formatDistance(provider.distance_km);
        const isDemo = provider.demo !== false;
        return <li key={provider.id} className="space-y-2 py-4 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <p className="text-label">{provider.name}</p>
            {distance ? <span className="text-caption text-text-secondary tabular">{distance}</span> : null}
          </div>
          <p className="text-text-secondary">{providerKind(provider)}</p>
          {mixed && isDemo ? demoBadge : null}
          <ProviderAddress provider={provider} />
          <div className="flex flex-wrap gap-2 pt-1">
            <CallButton phone={provider.phone} name={provider.name} />
            {!isDemo && provider.website?.startsWith("https://") ? <Button asChild variant="outline" size="sm">
              <a href={provider.website} target="_blank" rel="noopener noreferrer">
                <ExternalLink aria-hidden />Ordinationsseite<span className="sr-only"> von {provider.name} (neuer Tab)</span>
              </a>
            </Button> : null}
            {onSend ? <>
              {isDemo ? <Button variant="outline" size="sm" onClick={() => onSend(`Bitte schlagen Sie mir einen Termin bei ${provider.name} vor.`)}>
                <CalendarClock aria-hidden />Termin vorschlagen
              </Button> : null}
              <Button variant="outline" size="sm" onClick={() => onSend(`Bitte entwerfen Sie eine E-Mail an ${provider.name}.`)}>
                <Mail aria-hidden />E-Mail entwerfen
              </Button>
            </> : null}
          </div>
        </li>;
      })}
    </ol>
    <div className="space-y-1 text-caption text-text-secondary">
      <p>{fromLocation ? "Die Entfernung ist eine Luftlinie ab Ihrem Standort." : "Die Entfernung ist eine Luftlinie ab Ihrer Postleitzahl."}</p>
      {hasReal ? <p>
        Ärztinnen und Ärzte: Stadt Wien – data.wien.gv.at (CC BY 4.0).
        Kassenvertrag und Öffnungszeiten stehen nicht darin. Fragen Sie in der Ordination nach.
      </p> : null}
      {hasDemo ? <p>{hasReal ? "Mit „Demo-Daten“ markierte Anbieter sind erfunden." : "Erfundene Anbieter für die Demo."}</p> : null}
    </div>
    {!fromLocation && location && onSend && location.status !== "denied" && location.status !== "unavailable"
      ? <Button variant="secondary" size="sm" className="self-start" disabled={location.status === "locating"}
        onClick={() => void searchFromLocation()}>
        <LocateFixed aria-hidden />{location.status === "locating" ? "Standort wird ermittelt…" : "Mit meinem Standort genauer suchen"}
      </Button> : null}
  </ResultCardFrame>;
}

export type AppointmentCardProps = { card: CardOf<"appointment"> };

/** A demo appointment proposal. The person books it by phone; nothing is booked here. */
export function AppointmentCard({ card: { appointment } }: AppointmentCardProps) {
  const { provider } = appointment;
  return <ResultCardFrame title="Terminvorschlag" icon={CalendarClock} badge={demoBadge}>
    <p className="text-heading text-text">{formatAppointment(appointment.start, appointment.end)}</p>
    <div className="space-y-1">
      <p className="text-label">{provider.name}</p>
      <p className="text-text-secondary">{providerKind(provider)}</p>
      <ProviderAddress provider={provider} />
    </div>
    <div className="flex flex-wrap items-start gap-3">
      <SaveToCalendarButton appointmentId={appointment.id} />
      <FileAction url={appointment.ics_url} filename="termin.ics" label="Als .ics herunterladen" icon={Download} doneMessage="Kalenderdatei heruntergeladen." accept={["text/calendar"]} />
      <CallButton phone={provider.phone} name={provider.name} size="default" />
    </div>
    <p className="text-caption text-text-secondary">Das ist ein Vorschlag, keine Buchung. Rufen Sie an, um den Termin zu vereinbaren.</p>
  </ResultCardFrame>;
}

/** Saves the proposal into the in-app „Kalender“. Hidden without a CalendarProvider. */
function SaveToCalendarButton({ appointmentId }: { appointmentId: string }) {
  const calendar = useCalendar();
  const [saving, setSaving] = useState(false);
  if (!calendar) return null;
  const saved = calendar.entries.some((entry) => entry.appointment_id === appointmentId);
  if (saved) {
    return <p role="status" className="inline-flex min-h-10 items-center gap-2 text-label text-accent-text">
      <CalendarCheck aria-hidden className="size-4" />Im Kalender gespeichert
    </p>;
  }
  async function save() {
    if (!calendar || saving) return;
    setSaving(true);
    try {
      await calendar.add({ appointment_id: appointmentId });
      toast("Im Kalender gespeichert.");
    } catch {
      toast.error("Der Termin wurde nicht gespeichert.", { description: "Bitte versuchen Sie es erneut." });
    } finally {
      setSaving(false);
    }
  }
  return <Button variant="secondary" disabled={saving || calendar.status !== "ready"} onClick={() => void save()}>
    <CalendarPlus aria-hidden />{saving ? "Wird gespeichert…" : "Im Kalender speichern"}
  </Button>;
}

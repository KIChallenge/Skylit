"use client";

import { FileText, Paperclip, Route } from "lucide-react";
import { useState } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ConversationView, EmergencyBanner } from "@/features/chat";
import type { Contact, Message } from "@/lib/api";

const messages: Message[] = [
  {
    id: "demo-question", role: "user", created_at: "2026-11-05T09:00:00Z", document_ids: [], cards: [], sources: [], escalation_id: null,
    content: "Meine Mutter kommt aus dem Spital und braucht Unterstützung im Alltag. Welche Schritte kann ich vorbereiten?",
  },
  {
    id: "demo-answer", role: "assistant", created_at: "2026-11-05T09:01:00Z", document_ids: [], cards: [], sources: [], escalation_id: null,
    content: "Wir können Ihre nächsten Schritte gemeinsam ordnen.\n\n**Unterstützung zu Hause**\n\nHalten Sie Ihre Fragen zur Betreuung und den Entlassungsbrief für ein Beratungsgespräch bereit. Die zuständige Stelle prüft Ihre Situation.\n\n1. Welche Unterstützung braucht Ihre Mutter im Alltag?\n2. Liegt Ihnen der Entlassungsbrief bereits vor?",
  },
];

// Backend-shaped preview data. The banner itself contains no telephone numbers.
const contacts: Contact[] = [{ name: "Rettung", phone: "144", hours: "Rund um die Uhr", note: null, url: null }];
const scenarios = ["Normale Antwort", "Laufende Antwort", "Fehler", "Notfall", "Leer", "Laden"] as const;
type Scenario = typeof scenarios[number];

export function ChatPreview() {
  const [scenario, setScenario] = useState<Scenario>("Normale Antwort");
  const [sent, setSent] = useState<string | null>(null);
  const [attached, setAttached] = useState(false);
  const pending = scenario === "Laufende Antwort";
  const failed = scenario === "Fehler";
  const emergency = scenario === "Notfall";
  const empty = scenario === "Leer" || scenario === "Laden";

  return (
    <AppShell
      header={<AppHeader actions={<Badge variant="outline">Synthetische Vorschau</Badge>} />}
      emergencyBanner={emergency ? <EmergencyBanner contacts={contacts} message="Bitte rufen Sie jetzt die Rettung. Warten Sie nicht auf eine Antwort des Lotsen." /> : undefined}
      navigation={
        <div className="flex flex-col gap-6 p-4">
          <div><h2 className="text-heading">Gesprächsvorschau</h2><p className="mt-2 text-body text-text-secondary">Erfundene Situation für die Gestaltung.</p></div>
          <div className="flex flex-col gap-2" aria-label="Vorschauzustand">
            {scenarios.map((name) => <Button key={name} variant="ghost" className="h-auto min-h-10 justify-start whitespace-normal py-2" aria-pressed={scenario === name} onClick={() => { setScenario(name); setSent(null); setAttached(false); }}>{name}</Button>)}
          </div>
          <p className="text-caption text-text-secondary">Diese Vorschau sendet keine Daten.</p>
        </div>
      }
      casePanel={
        <div className="space-y-6 p-6">
          <div><h2 className="flex items-center gap-2 text-heading"><Route aria-hidden className="size-5" />Mein Fall</h2><p className="mt-2 text-body text-text-secondary">Unterstützung nach dem Spital</p></div>
          <Badge variant="outline">Von Ihnen zu prüfen</Badge>
          <ol className="space-y-6 text-body">
            <li><span className="text-label text-accent-text">1 · Vorbereiten</span><p className="mt-1">Entlassungsbrief bereithalten</p></li>
            <li><span className="text-label text-text-secondary">2 · Offen</span><p className="mt-1">Fragen zur Betreuung sammeln</p></li>
            <li><span className="text-label text-text-secondary">3 · Offen</span><p className="mt-1">Zuständige Stelle kontaktieren</p></li>
          </ol>
        </div>
      }
      conversation={
        <ConversationView
          key={scenario}
          messages={empty ? [] : [...(pending || failed || emergency || sent ? messages.slice(0, 1) : messages), ...(sent ? [{ ...messages[0], id: "demo-sent", content: sent }] : [])]}
          responseText={emergency ? "Bitte holen Sie sofort Hilfe. Warten Sie nicht auf weitere Antworten des Lotsen." : pending || failed || sent ? "Ich ordne die nächsten Schritte. Den Entlassungsbrief können Sie für das Beratungsgespräch bereithalten." : ""}
          sending={pending || Boolean(sent)}
          loading={scenario === "Laden"}
          progressLabel={scenario === "Laden" ? "Gespräch wird geladen…" : "Passende Unterstützung wird gesucht…"}
          error={failed ? "Die Verbindung wurde unterbrochen. Der bisherige Antworttext bleibt erhalten." : null}
          onSend={setSent}
          onRetry={() => setScenario("Laufende Antwort")}
          attachment={<div className="flex min-w-0 flex-wrap items-center gap-2"><Button type="button" variant="ghost" aria-label="Dokument anhängen" onClick={() => setAttached(true)}><Paperclip aria-hidden />Dokument anhängen</Button>{attached ? <span className="text-caption text-text-secondary">Entlassungsbrief.pdf · Demo-Anhang bereit</span> : null}</div>}
          renderMessageCards={(message) => message.role === "assistant" ? (
            <Card className="rounded-lg">
              <CardHeader><h2 className="flex items-center gap-2 text-heading"><FileText aria-hidden className="size-5" />Für das Beratungsgespräch</h2></CardHeader>
              <CardContent><p className="text-body">Notieren Sie Ihre Fragen. Prüfen Sie alle Angaben vor einer Weitergabe selbst.</p></CardContent>
            </Card>
          ) : null}
          renderAnswerFooter={() => <p className="text-caption text-text-secondary">Keine Quellen · Modell nicht erfasst · Sicherheit nicht verfügbar</p>}
        />
      }
    />
  );
}

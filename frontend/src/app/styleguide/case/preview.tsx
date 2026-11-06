"use client";

import { FlaskConical, MessagesSquare, Route } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CasePanel } from "@/features/case";
import { syntheticCase } from "@/features/case/synthetic-case";
import { api, type ApiClient, type Case } from "@/lib/api";

type View = "content" | "loading" | "empty" | "error";

export function CasePreview() {
  const [currentCase, setCase] = useState<Case>(syntheticCase);
  const [view, setView] = useState<View>("content");
  const [failNext, setFailNext] = useState(false);
  const fail = useRef(false);
  const caseRef = useRef(currentCase);
  useLayoutEffect(() => { caseRef.current = currentCase; }, [currentCase]);
  const [client] = useState<ApiClient>(() => ({
    ...api,
    async updateCaseStep(id, status) {
      // Preview only: no request, no storage, no automatic action.
      await new Promise((resolve) => setTimeout(resolve, 700));
      if (fail.current) {
        fail.current = false;
        setFailNext(false);
        throw new Error("Synthetic preview failure");
      }
      const step = caseRef.current.steps.find((entry) => entry.id === id);
      if (!step) throw new Error("Unknown synthetic step");
      return { ...step, status };
    },
  }));
  const open = currentCase.steps.filter((step) => step.status !== "done").length;
  return <AppShell header={<AppHeader />}
    casePanelLabel={`Mein Fall · ${open} offen`}
    navigation={<div className="space-y-4 p-4"><h2 className="text-heading">Gespräche</h2>
      <Badge variant="neutral"><MessagesSquare className="size-4" />Unterstützung für Mutter</Badge></div>}
    conversation={<div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-6 beamer:p-8">
      <div className="mx-auto max-w-answer space-y-6">
        <Badge variant="neutral"><FlaskConical className="size-4" />Synthetische Vorschau</Badge>
        <h1 className="text-title text-balance">Ein Weg durch Ihre nächsten Schritte</h1>
        <p className="text-answer">Ihr Fall bleibt neben dem Gespräch sichtbar. Markieren Sie nur Schritte, die Sie selbst erledigt haben.</p>
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Route className="size-5" />Mein Fall ausprobieren</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <p className="text-body text-text-secondary">Diese Vorschau speichert keine Daten. Alle Personen und Fallschritte sind erfunden.</p>
            <div className="flex flex-wrap gap-2" aria-label="Ansicht wählen">
              {([["content", "Fall anzeigen"], ["loading", "Laden"], ["empty", "Leer"], ["error", "Ladefehler"]] as const).map(([value, label]) =>
                <Button key={value} variant="secondary" aria-pressed={view === value} onClick={() => setView(value)}>{label}</Button>)}
            </div>
            <Button variant="outline" aria-pressed={failNext} onClick={() => {
              fail.current = !failNext;
              setFailNext(!failNext);
            }}>{failNext ? "Nächste Änderung schlägt fehl" : "Speicherfehler ausprobieren"}</Button>
            <p className="text-caption text-text-secondary">Wählen Sie danach einen Fallschritt. Wiederholen Sie die fehlgeschlagene Änderung direkt am Schritt.</p>
          </CardContent>
        </Card>
        <p className="text-body text-text-secondary">Sie prüfen und senden jeden Antrag selbst. Der Lotse entscheidet über keine Leistung.</p>
      </div>
    </div>}
    casePanel={<CasePanel case={view === "empty" ? null : currentCase} isLoading={view === "loading"}
      error={view === "error"} onRetry={() => setView("content")} apiClient={client} onCaseChange={setCase} />} />;
}

"use client";

import { useState } from "react";
import { AppHeader } from "@/components/layout/app-header";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ResultCards } from "@/features/cards";
import { previewCards } from "@/features/cards/fixtures";

type View = "content" | "loading" | "empty" | "error";
export function CardsPreview() {
  const [view, setView] = useState<View>("content");
  return <AppShell header={<AppHeader />} conversation={
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 lg:p-8">
      <div className="mx-auto max-w-content space-y-6">
        <header className="space-y-3">
          <Badge variant="neutral">Vorschau · synthetischer Fall</Badge>
          <h1 className="text-title">Von Ihrem Dokument zum nächsten Schritt</h1>
          <p className="max-w-answer text-body text-text-secondary">Maria organisiert Hilfe für ihre Mutter Anna Berger. Alle Personenangaben sind erfunden. Die Kontaktdaten stammen aus dem Stellenverzeichnis.</p>
          <p className="max-w-answer text-caption text-text-secondary">Die Vorschau zeigt keine gespeicherten Dateien. Dateiaktionen zeigen bei fehlenden Dateien einen Fehler mit Wiederholung.</p>
          <div aria-label="Ansicht wählen" className="flex flex-wrap gap-3">
            {([ ["content", "Ergebnisse"], ["loading", "Laden"], ["empty", "Leer"], ["error", "Fehler"] ] as const).map(([state, label]) => <Button key={state} variant="secondary" aria-pressed={view === state} onClick={() => setView(state)}>{label}</Button>)}
          </div>
        </header>
        <ResultCards cards={view === "content" ? previewCards : []} loading={view === "loading"} error={view === "error"} onRetry={() => setView("content")} className={view === "content" ? "grid items-start gap-6 lg:grid-cols-2" : undefined} />
      </div>
    </div>
  } />;
}

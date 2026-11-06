"use client";

import { AppShell } from "@/components/layout/app-shell";
import { AppHeader } from "@/components/layout/app-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FlaskConical, Info } from "lucide-react";
import { AnswerFooter } from "@/features/transparency";
import { previewClient, previewTransparency } from "@/features/transparency/preview-data";

export function TransparencyPreview() {
  return <AppShell header={<AppHeader actions={<Badge variant="neutral"><FlaskConical aria-hidden />Synthetisches Beispiel</Badge>} />}
    conversation={<div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-answer space-y-8">
        <div className="space-y-2">
          <h1 className="text-title text-text">Eine Antwort nachvollziehen</h1>
          <p className="text-body text-text-secondary">Prüfen Sie die Quellen, die Beleglage und die Schritte des Lotsen.</p>
        </div>
        <div className="ms-8 rounded-lg bg-subtle p-4">
          <p className="text-label text-text">Ihre Nachricht · erfundenes Beispiel</p>
          <p className="mt-2 text-body">Meine Mutter braucht nach dem Spitalsaufenthalt Hilfe zu Hause. Wie kann ich Unterstützung organisieren?</p>
        </div>
        <Card><CardContent>
          <article aria-label="Antwort des Lotsen" className="space-y-4">
            <p className="text-label text-text-secondary">Lotse (KI)</p>
            <div className="space-y-4 text-answer text-text">
              <p>Pflegegeld und Unterstützung zu Hause könnten für Ihre Mutter in Frage kommen.</p>
              <p>Informieren Sie sich zuerst über den Pflegegeldantrag. Klären Sie danach, welche Hilfe Ihre Mutter im Alltag braucht.</p>
              <p>Die Suche nach der zuständigen Stelle hat nicht geklappt. Nutzen Sie vorerst die verlinkten Informationen.</p>
            </div>
            <p className="flex items-start gap-2 text-body text-text-secondary"><Info aria-hidden className="mt-1 size-4 shrink-0" strokeWidth={1.5} />Die zuständige Stelle prüft den Anspruch und entscheidet.</p>
            <AnswerFooter messageId={previewTransparency.message_id} client={previewClient} />
          </article>
        </CardContent></Card>
        <p className="text-caption text-text-secondary">Diese Vorschau zeigt synthetische Protokolldaten. Sie sendet keine Anfrage an ein KI-Modell.</p>
      </div>
    </div>} />;
}

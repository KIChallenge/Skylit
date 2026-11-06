"use client";

import { Paperclip } from "lucide-react";
import { useState } from "react";

import { AppHeader } from "@/components/layout/app-header";
import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Enter } from "@/components/ui/enter";
import { EmptyState } from "@/components/ui/state";
import { AttachmentChip, AttachmentControl, type AttachmentPhase } from "@/features/attachments";

const filename = "entlassungsbefund.pdf";
const phases: { phase: AttachmentPhase; title: string }[] = [
  { phase: "uploading", title: "Hochladen" },
  { phase: "processing", title: "Dokument lesen" },
  { phase: "ready", title: "Dokument bereit" },
  { phase: "failed", title: "Erneut versuchen oder entfernen" },
];

export function UploadPreview() {
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [removed, setRemoved] = useState<AttachmentPhase[]>([]);
  const [retried, setRetried] = useState(false);

  return (
    <AppShell
      header={<AppHeader actions={<Badge variant="outline">Synthetische Demo-Daten</Badge>} />}
      conversation={
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 sm:p-8">
          <div className="mx-auto flex max-w-content flex-col gap-8">
            <div className="flex flex-col gap-2">
              <h1 className="text-title">Dokument anhängen</h1>
              <p className="max-w-answer text-body text-text-secondary">
                Ein Entlassungsbefund ergänzt Ihre Nachricht. Sie können jederzeit ohne Dokument fortfahren.
              </p>
            </div>
            <Card>
              <CardHeader><h2 className="text-heading">Datei auswählen</h2></CardHeader>
              <CardContent className="flex flex-col gap-4">
                {!selectedName ? (
                  <EmptyState icon={Paperclip} title="Noch kein Dokument ausgewählt" description="Wählen Sie ein synthetisches Dokument für die Vorschau." className="py-4" />
                ) : null}
                <AttachmentControl
                  filename={selectedName}
                  phase={selectedName ? "uploading" : null}
                  onFileSelected={(file) => { setSelectedName(file.name); setNotice("Datei ausgewählt. Diese Vorschau lädt keine Datei hoch."); }}
                  onRemove={() => { setSelectedName(null); setNotice("Dokument entfernt. Sie können ohne Dokument fortfahren."); }}
                  onRetry={() => setNotice("Erneuter Versuch ausgewählt. Diese Vorschau lädt keine Datei hoch.")}
                />
                <p className="text-caption text-text-secondary">Diese Vorschau überträgt keine Dateien.</p>
              </CardContent>
            </Card>
            <section aria-labelledby="upload-states" className="flex flex-col gap-4">
              <h2 id="upload-states" className="text-heading">Vom Auswählen bis zum gelesenen Dokument</h2>
              <div className="grid min-w-0 gap-4 lg:grid-cols-2">
                {phases.map(({ phase, title }, index) => (
                  <Enter key={phase} index={index} className="min-w-0">
                    <Card className="h-full gap-4">
                      <CardHeader><h3 className="text-heading">{title}</h3></CardHeader>
                      <CardContent>
                        {removed.includes(phase) ? (
                          <EmptyState icon={Paperclip} title="Dokument entfernt" description="Sie können ohne Dokument fortfahren." className="py-4" />
                        ) : <AttachmentChip
                          filename={filename}
                          phase={phase === "failed" && retried ? "processing" : phase}
                          documentId={phase === "uploading" ? null : "00000000-0000-4000-8000-000000000056"}
                          error={phase === "failed" ? "Der Entlassungsbefund ist nicht lesbar. Bitte wählen Sie eine deutlichere Kopie." : null}
                          onRemove={() => { setRemoved((current) => [...current, phase]); setNotice(`${title}: Dokument entfernt. Sie können ohne Dokument fortfahren.`); }}
                          onRetry={() => { setRetried(true); setNotice("Erneuter Versuch ausgewählt. Diese Vorschau lädt keine Datei hoch."); }}
                        />}
                      </CardContent>
                    </Card>
                  </Enter>
                ))}
              </div>
            </section>
            <div className="flex flex-wrap items-center gap-4">
              <Button type="button" variant="secondary" onClick={() => { setSelectedName(null); setRemoved([]); setRetried(false); setNotice("Vorschau zurückgesetzt."); }}>Vorschau zurücksetzen</Button>
              <p role="status" aria-atomic="true" className="text-body text-text-secondary">{notice}</p>
            </div>
          </div>
        </div>
      }
    />
  );
}

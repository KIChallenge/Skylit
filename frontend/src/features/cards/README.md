# Ergebnis-Cards

Importieren Sie Komponenten und Props aus `@/features/cards`.
Importieren Sie `downloadFile` direkt aus `@/lib/api/download`.

| Export | Props |
|---|---|
| `ResultCards` | `cards: unknown`, `loading?: boolean`, `error?: unknown`, `onRetry?: () => void`, `className?: string` |
| `ResultCard` | `card: unknown` |
| `DocumentSummaryCard` | `card: CardOf<"document_summary">`, `filename?: string` |
| `LeistungCard` | `card: CardOf<"leistung">` |
| `FormDraftCard` | `card: CardOf<"form_draft">` |
| `OfficeCard` | `card: CardOf<"office">` |
| `EscalationCard` | `card: CardOf<"escalation">` |
| `QuoteBlock` | `quote: string`, `section?: string \| null`, `label?: string` |
| `CopyButton` | `value: string` |
| `ResultCardFrame` | `title: string`, `icon: LucideIcon`, `badge?: ReactNode`, `children: ReactNode` |
| `downloadFile` | `url: string`, `options: { filename: string; open?: boolean; timeoutMs?: number }` |

Alle Komponenten exportieren den zugehörigen Typ `<Komponentenname>Props`.
Der Download-Helfer exportiert `DownloadOptions`.

`ResultCards` prüft unbekannte Daten mit `toCards`.
`ResultCard` prüft unbekannte Daten mit `toCard`.
Übergeben Sie einzelnen Komponenten ausschließlich geprüfte Domain-Cards.
`DocumentSummaryCard` prüft zusätzlich die Extraktion mit `toDocumentSummary`.

Übergeben Sie `onRetry`, wenn die Ergebnisabfrage fehlschlagen kann.
Die aufrufende Ansicht verwaltet die Ergebnisabfrage und deren Zustand.
Vorhandene Cards bleiben während Laden und Fehlern sichtbar.
Die Liste zeigt jede Eskalations-ID nur einmal.
Der Antwort-Footer ergänzt Quellenmetadaten, Modell und Sicherheit außerhalb dieser Komponenten.

Downloads senden Cookies und nutzen den Timeout aus dem bestehenden Konfigurationsmodul.
Downloads prüfen HTTP-Status, Dateityp und Dateigröße vor jeder Anzeige.
Dateifehler erscheinen ausschließlich als deutsche Meldung mit manueller Wiederholung.
Die Originalansicht akzeptiert PDF, PNG, JPEG und WebP.
Der PDF-Download akzeptiert ausschließlich PDF.
Kein Download wiederholt einen Aufruf automatisch.

## Vorschau und Prüfung

Starten Sie `make frontend-setup` und `make frontend-dev` mit der vorhandenen Umgebung.
Öffnen Sie `/styleguide/cards` am konfigurierten Port.
Die Vorschau zeigt fünf Pflichttypen und umschaltbare Lade-, Leer- und Fehlerzustände.
Die Vorschau verwendet synthetische Personen und Stellenkontakte aus den Seed-Daten.
Die Vorschau verwendet Platzhalter-IDs für Dokument und Formular.
Dateiaktionen benötigen deshalb echte Backend-IDs oder zeigen den Fehlerzustand.

Führen Sie `make frontend-unit ARGS=src/features/cards` aus.
Führen Sie `make frontend-unit ARGS=src/lib/api/download.test.ts` aus.
Führen Sie `make frontend-typecheck` aus.

## Technische Entscheidung

Der Download-Helfer lädt Dateien als Blob, bevor er den Download oder die Originalansicht öffnet.
Direkte Navigation könnte Backend-Fehler statt des Dokuments anzeigen.
Die Originalansicht öffnet zunächst einen leeren Tab, damit Popup-Sperren keinen späteren Tab verhindern.
Bei Fehlern schließt der Helfer diesen Tab.
Ein gesperrter Tab erzeugt eine deutsche Fehlermeldung.
Die Implementierung verwendet ausschließlich bestehende Abhängigkeiten und Konfiguration.

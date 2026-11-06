# Seitenintegration

## Beschreibung und Lösungsansatz

Das Modul verbindet die vorhandenen Features mit den Routen `/`, `/login` und `/chat/[id]`.
Die Routen enthalten ausschließlich die Seitenkomposition und Seitentitel.

| Export | Zweck |
|---|---|
| `HomeRedirect` | Prüft die Sitzung und öffnet das neueste Gespräch. |
| `LoginScreen` | Verbindet `PersonaLogin` mit der Gesprächsauswahl. |
| `ChatScreen` | Lädt das Gespräch und verbindet Controller, Upload und App-Shell. |
| `bridgeConversation` aus `bridge.ts` | Trennt gespeicherte Nachrichten von der laufenden Antwort. |

Die Integration verwendet `PersonaLogin`, `PersonaMenu`, `ConversationView`, `EmergencyBanner`, `CasePanel`, `ResultCards`, `AttachmentControl` und `AnswerFooter`.
Die Integration verwendet `createConversationController` und `createUploadController` unverändert.
`AppShell` und `AppHeader` übernehmen das gemeinsame Layout.

## Technische Entscheidung

Der Seitenzustand hält den angezeigten Fall getrennt vom Controller-Zustand.
Nur eine neue Fallreferenz aus dem Controller ersetzt den angezeigten Fall.
Dadurch überschreiben Text-Events keine gespeicherte Änderung aus `CasePanel.onCaseChange`.

Die Brücke verwendet die ursprünglichen Nachrichtenindizes für lokale Ersatz-IDs.
Die Brücke prüft Kollisionen mit vorhandenen IDs.
Während des Streams erscheint die laufende Antwort ausschließlich über `responseText`.
Nach Abschluss verbindet die Brücke die Nachricht mit ihren Cards und Transparenzangaben.

Die Dateiauswahl startet den Upload sofort.
Beim Senden wartet die Integration auf denselben Upload.
Nur ein erfolgreicher Upload ergänzt `document_ids`.
Ein Upload-Fehler verlangt eine manuelle Wiederholung oder das Entfernen des Anhangs.
Gesprächswechsel und Unmount brechen Stream, Upload und laufende Seitenabfragen ab.

## Ausführung

Führen Sie die Befehle im Repository-Verzeichnis aus:

```sh
make frontend-setup
make frontend-unit ARGS=src/features/lotse
make frontend-typecheck
make frontend-lint
```

## Abhängigkeiten und Voraussetzungen

Die Tests verwenden Vitest, Testing Library und die vorhandenen gemeinsamen Komponenten.
Die Tests ersetzen `api` und `next/navigation` durch Mocks.
Die Tests benötigen weder Backend noch LLM.

## Konfiguration

Die Integration ergänzt keine Umgebungsvariablen.
Die zentrale Konfiguration liefert `streamIdleTimeoutMs` und `apiTimeoutMs` für den Upload.
Das Polling-Intervall beträgt gemäß Task-Vorgabe 1000 Millisekunden.

## Bekannte Einschränkungen und offene Punkte

Annahme: Das neueste Gespräch hat den jüngsten Wert in `updated_at`.
Die Integration erzeugt weder Modellnamen noch Sicherheitseinstufungen.
Die Sandbox erlaubt keine Port-Bindung. Der Manager übernimmt Browser-Prüfung und Screenshot bei 1440×900.

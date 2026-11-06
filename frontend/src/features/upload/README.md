# Upload-Controller

## Beschreibung und Lösungsansatz

`controller.ts` exportiert `createUploadController`, `UploadController`, `UploadControllerOptions`, `UploadState` und `UploadResult`.
Der Controller verwaltet einen Anhang ohne UI und ohne Chat-Nachrichten.
Er erhält einen `ApiClient` und meldet Zustände über `onProgress`.
Er erhält `document.extracted` unverändert im Feld `state.document.extracted`.
Der Controller interpretiert keine Befunde.

## Integration

Erstelle einen Controller pro Anhang.
Übergib `api` aus `@/lib/api` oder einen injizierten `ApiClient`.
Übergib die Zeitwerte aus der zentralen Frontend-Konfiguration.
Der Controller liest selbst keine Umgebungsvariablen.

```ts
import { createUploadController } from "@/features/upload/controller";

const controller = createUploadController({
  api,
  onProgress: updateAttachment,
  pollIntervalMs,
  totalTimeoutMs,
  requestTimeoutMs,
});

const result = await controller.start(file, conversationId);
if (result.status === "ready") {
  attachReadyDocument(result.documentId);
}
```

Der Screen ergänzt `result.documentId` später in `document_ids` seiner Nachricht.
Rufe `controller.cancel()` beim Entfernen, Gesprächswechsel und Abbau des Screens auf.
`cancel()` beendet Requests und Timer des aktiven Laufs.
Der Controller löscht kein Dokument auf dem Server.

`controller.state` ist vor dem ersten Start `null`.
Jeder Zustand enthält `filename`, `documentId` und `document`.
Der Controller bewahrt den ursprünglichen Dateinamen.
Vor der Upload-Antwort sind `documentId` und `document` noch `null`.
Die Zustände heißen `uploading`, `processing`, `ready`, `failed` und `cancelled`.
`onProgress` meldet Zustände, keine Prozentwerte.
Der Callback muss synchron bleiben und darf keine Fehler werfen.

`start(file, conversationId)` sendet beide Werte über `api.uploadDocument`.
Gleichzeitige `start`-Aufrufe erhalten dasselbe Promise des aktiven Laufs.
Nach einem Endzustand startet ein expliziter `start`-Aufruf einen neuen Upload.
Der Controller wiederholt keinen Upload automatisch.
Das Promise liefert `UploadResult`, auch bei Fehler oder Abbruch.
Der Zustand `failed` enthält einen `TransportError` mit deutschem Fehlertext.
HTTP-Fehler behalten ihren ursprünglichen `TransportError`.

## Konfiguration

| Parameter | Bedeutung |
|---|---|
| `pollIntervalMs` | Wartezeit nach jeder `processing`-Antwort, auch nach dem Upload |
| `totalTimeoutMs` | Gesamtgrenze ab Upload-Start, einschließlich Upload und Wartezeiten |
| `requestTimeoutMs` | Grenze für jeden einzelnen Upload- oder Polling-Request |

Alle Zeitwerte sind Pflichtparameter in Millisekunden.
Gültige Werte liegen zwischen `1` und `2147483647`.
Der Controller startet den nächsten Poll erst nach der vorherigen Antwort und der Wartezeit.
Eigene Timer begrenzen auch APIs, die `timeoutMs` ignorieren.
Bei Timeout setzt der Controller `failed` mit Fehlercode `timeout` und bricht den aktiven Request ab.
Verspätete Antworten ändern keinen abgeschlossenen oder neuen Lauf.

## Ausführung

Führe die Befehle im Projektverzeichnis aus:

```sh
make frontend-setup
make frontend-unit ARGS=src/features/upload
make frontend-typecheck
```

## Abhängigkeiten und Voraussetzungen

Die Tests verwenden Vitest, eine gefälschte API und Fake Timers.
Die Tests brauchen weder Backend noch LLM noch `.env`.
Der Controller verwendet ausschließlich die vorhandene API-Fassade und Browser-APIs.

## Bekannte Einschränkungen und offene Punkte

Das Backend liefert für fehlgeschlagene Extraktionen keinen Fehlertext.
Der Controller meldet dafür `document_failed` mit einem eigenen deutschen Fehlertext.
Die Gesamtgrenze umfasst auch den Upload.
Der Screen entscheidet über Nachrichtensenden und Wiederholung.
Die spätere UI-Integration ordnet die Zeitwerte der zentralen Konfiguration zu.

# Gesprächszustand

## Beschreibung und Lösungsansatz

Das Modul verwaltet Gesprächszustände ohne React-Komponenten.
Alle Domänentypen stammen aus `@/lib/api`.

### Exporte aus `model.ts`

- `createConversationState(conversation)` übernimmt eine gespeicherte `Conversation` einschließlich Fall, Nachrichten und Quellen.
- `conversationReducer(state, action)` verarbeitet die generierte `StreamEvent`-Union und lokale Turn-Aktionen.
- `ConversationState` enthält Nachrichten, aktuelle Antwort, Fortschrittslabel, Fall, Eskalation, Notfall und Fehler.
- `ConversationMessage` enthält Text, validierte Cards, Quellen und nachrichtenbezogene Notfallinformationen und Fehler.
- `ConversationError` unterscheidet `kind: "stream"` und `kind: "transport"`.
- `ConversationAction` ergänzt Stream-Events um `turn.started`, `turn.aborted` und `transport.failed`.
- `Emergency` enthält ausschließlich die Nachricht und Kontakte des Notfall-Events.

`messages` enthält auch `currentAnswer`.
Rendere diese Antwort nicht zusätzlich.
`currentAnswer.cards` und `currentAnswer.sources` liefern die Cards und Quellen der aktuellen Antwort.
`status === "streaming"` kennzeichnet den Ladezustand.
`progressLabel` übernimmt die Anzeigetexte aus `status` und `tool.called`.

Lokale Nachrichten haben zunächst `id: null` und `created_at: null`.
`message.created` liefert die Antwort-ID, aber noch keine bestätigte Transparenzabfrage.
`message.completed` setzt `completedMessageId` und `currentAnswer.transparencyMessageId`.
Nutze `transparencyMessageId` für spätere Aufrufe von `api.getTransparency(id)`.
Gespeicherte KI-Nachrichten erhalten ihre vorhandene ID als `transparencyMessageId`.

### Exporte aus `controller.ts`

`createConversationController(api, onChange, conversation)` erstellt einen `ConversationController`.
Der Controller benötigt nur `ApiClient.streamMessage`.
Der Callback erhält jede Zustandsänderung synchron.
Der Konstruktor ruft den Callback nicht auf.
Lies den Anfangszustand über `getState()`.
Der Callback darf keine Ausnahme auslösen.

```ts
import { api } from "@/lib/api";
import { createConversationController } from "./controller";

const controller = createConversationController(api, renderState, savedConversation);
renderState(controller.getState());
const result = await controller.send(
  { content: "Welche Unterstützung gibt es?", document_ids: [] },
  { signal: abortController.signal },
);
```

- `send(message, { signal }?)` startet genau einen POST.
- `SendResult` lautet `completed`, `error`, `aborted` oder `busy`.
- `busy` verhindert einen zweiten aktiven Turn und fügt keine Nachricht hinzu.
- `abort()` bricht den aktiven Turn ab und beendet sofort den Ladezustand.
- `selectConversation(conversation)` bricht den aktiven Turn ab und ersetzt den gesamten Zustand.
- `getState()` liefert den letzten Zustand.

Nutze einen Controller pro ausgewähltem Gesprächsbereich.
Rufe `selectConversation` auch beim Neuladen desselben Gesprächs auf.
Der Controller ignoriert spätere Events und Fehler abgelöster Turns.
Ein abgelöster Turn kann die Sperre eines neueren Turns nicht entfernen.
Der Controller entfernt externe Abbruch-Listener nach Turn-Ende.
Eine bereits abgebrochene `AbortSignal` verhindert den POST.

## Ausführung

Führe die Prüfungen aus dem Repository-Verzeichnis aus:

```sh
make frontend-setup
make frontend-unit ARGS=src/features/conversation
make frontend-typecheck
```

## Abhängigkeiten und Voraussetzungen

Die Tests verwenden Vitest und injizierte Streams.
Ein Integrationstest verwendet die API-Fassade mit injiziertem `fetch`.
Die Tests benötigen weder Backend noch LLM.

## Konfiguration

Das Modul benötigt keine zusätzlichen Umgebungsvariablen.
Die aufrufende Integration injiziert den API-Client und die gespeicherte `Conversation`.
Der API-Client übernimmt Transport-Timeouts.

## Bekannte Einschränkungen und offene Punkte

Annahme: Die spätere Chat-Integration lädt gespeicherte Gespräche über die API und übergibt vollständige Snapshots.
Das Modul liest keinen Browser-Speicher.

SSE-Fehler und Transportfehler erhalten sichtbaren Text, Cards und Notfallinformationen.
Fehler beenden den Ladezustand.
Ein Abbruch zeigt keine Fehlermeldung.
Teilantworten bleiben nach einem Abbruch lokal sichtbar.
Das Backend speichert abgebrochene KI-Antworten nicht.
Ein neuer Snapshot ersetzt diese lokalen Teilantworten.

Der Controller wiederholt POSTs niemals automatisch.
Die Person muss nach einem Fehler erneut senden.
`retryAfter` liefert bei SSE-Fehlern nur einen Hinweis, keinen Wiederholungsauftrag.
Fehlgeschlagene Tool-Ergebnisse beenden den Turn nicht.
`toCard` prüft Cards vor der Übernahme.
Der Reducer vereinigt Eskalations-Cards anhand ihrer Eskalations-ID.

Gespeicherte Gespräche enthalten keine Notfallkontakte aus früheren Notfall-Events.
Das Modul erfindet deshalb keine Notfallkontakte beim Laden.
Das Modul ergänzt weder Modellnamen noch Sicherheitseinstufungen.
Diese Angaben liefert später die Transparenzabfrage.

# Browser-Transport: Integrationsnotiz

Das Modul verbindet den Browser mit dem Backend über REST und POST-SSE.
Es nutzt nur Web-APIs und hat keine Abhängigkeiten.
Es kennt keine Backend-Domänenschemas und liest keine Umgebungsvariablen.

## Voraussetzung im Scaffold

Die Module importieren einander mit expliziter `.ts`-Endung, weil Node die Tests sonst nicht ausführt.
Setze deshalb `"allowImportingTsExtensions": true` in `frontend/tsconfig.json`.
Diese Option verlangt `"noEmit": true`, das Next.js bereits setzt.

## Exporte aus `index.ts`

| Export | Zweck |
|---|---|
| `createHttpClient(config)` | Erstellt den `HttpClient` mit `request`, `get`, `post`, `patch`, `delete` und `stream`. |
| `TransportError` | Einzige Fehlerklasse mit `code`, `status` und deutscher `message`. |
| `TransportFailureCode` | Fehlercodes des Transports selbst. |
| `DEFAULT_TERMINAL_EVENTS` | Abschluss-Events: `message.completed` und `error`. |
| `createSseParser`, `decodeSseEvent` | Parser und Decoder, falls ein Consumer sie einzeln braucht. |
| `SseEventBase`, `UnknownSseEvent`, `SseMessage`, `SseParser` | Typen des Parsers und der Events. |
| `HttpClientConfig`, `RequestOptions`, `BodylessOptions`, `StreamOptions`, `HttpClient` | Typen des Clients. |

## Client mit zentraler Config erstellen

Erstelle eine einzige Client-Instanz neben dem zentralen Config-Modul.
Das Config-Modul liest `NEXT_PUBLIC_API_URL` und legt die Timeouts fest.
Der Client verlangt `baseUrl` und `timeoutMs`, er hat keine eigenen Standardwerte.

```ts
import { createHttpClient } from "@/lib/transport";
import { config } from "@/lib/config"; // Pfad und Feldnamen legt das Scaffold fest.

export const http = createHttpClient({
  baseUrl: config.apiUrl,
  timeoutMs: config.apiTimeoutMs,
  streamIdleTimeoutMs: config.streamIdleTimeoutMs,
});
```

Pfade enthalten das Präfix `/api`, weil `NEXT_PUBLIC_API_URL` nur den Origin enthält.

## REST

```ts
const me = await http.get<Me>("/api/me");
await http.delete("/api/conversations/" + id); // 204 liefert undefined.

const form = new FormData();
form.set("file", file);
const document = await http.post<Document>("/api/documents", form);
```

- Alle Requests senden `credentials: "include"`.
- `FormData` geht unverändert hinaus. Der Browser setzt den multipart-Header selbst.
- Alle anderen Bodys gehen als JSON hinaus.
- `timeoutMs` und `signal` lassen sich pro Request setzen. Setze für Uploads einen längeren Timeout.
- Der Client liest nur JSON-Antworten. Binde PDF- und ICS-Downloads als Link ein.

## Stream

```ts
const controller = new AbortController();

try {
  for await (const event of http.stream<Event>(
    `/api/conversations/${id}/messages`,
    { body: { content }, signal: controller.signal },
  )) {
    switch (event.type) {
      case "emergency": /* Notfallhinweis sofort zeigen */ break;
      case "text.delta": /* Text anhängen */ break;
      case "error": /* Fehler aus dem Agent-Turn zeigen */ break;
    }
  }
} catch (error) {
  if (error instanceof TransportError && error.code !== "aborted") {
    /* error.message mit Button „Erneut versuchen“ zeigen */
  }
}
```

- `Event` steht später für den generierten Event-Typ. Ohne Typargument gilt `UnknownSseEvent`.
- Der POST startet beim ersten `next()`, also beim Start der Schleife.
- Jedes Event kommt einzeln an, sobald seine Leerzeile eingetroffen ist.
- Der Client ergänzt `type` aus der `event:`-Zeile. Alle anderen Felder bleiben unverändert.
- Der Stream endet nach `message.completed` oder `error`. Der Client schließt dann die Verbindung.
- Ein `break` in der Schleife schließt die Verbindung ebenfalls.
- Der Client wiederholt keinen POST. Nur die Person löst eine Wiederholung aus, denn jeder POST startet einen neuen Agent-Turn.

`timeoutMs` begrenzt beim Stream die Zeit bis zu den Response-Headern.
`streamIdleTimeoutMs` begrenzt die Pause zwischen zwei Chunks. Ohne diesen Wert gilt `timeoutMs`.
Der Idle-Timeout läuft nur während des Lesens, ein langsamer Consumer löst ihn nicht aus.

Ein `error`-Event ist ein Anwendungsevent und kein `TransportError`. Behandle beide Fälle in der UI.

## Fehlercodes

Bei HTTP-Fehlern enthält `code` den Backend-Code, zum Beispiel `not_found`, und `status` den HTTP-Status.
Ohne auswertbaren Body setzt der Client einen Ersatzcode und eine deutsche Standardmeldung.
Englische Standardtexte wie „Not Found“ ersetzt der Client ebenfalls durch die deutsche Meldung.
Andere Backend-Meldungen gibt der Client unverändert weiter.

| `code` | `status` | Bedeutung |
|---|---|---|
| `network_error` | `null` | Der Server ist nicht erreichbar oder die Verbindung ist abgerissen. |
| `timeout` | `null` | Ein Timeout ist abgelaufen. |
| `aborted` | `null` | Der Aufrufer hat abgebrochen. Zeige keine Fehlermeldung. |
| `invalid_response` | `null` | Die Antwort ist kein gültiges JSON oder kein `text/event-stream`. |
| `stream_incomplete` | `null` | Der Stream endete ohne Abschluss-Event. |
| `stream_invalid_event` | `null` | Ein Event enthält kein gültiges JSON-Objekt. |
| Backend-Code oder Ersatzcode | HTTP-Status | Der Server hat mit einem Fehlerstatus geantwortet, zum Beispiel `unauthorized` (401). |

Bei einem `TransportError` im Stream behält die UI alle zuvor gelieferten Events.

## Tests

Führe diesen Befehl im Wurzelverzeichnis aus. Der Test braucht weder Backend noch Next.js.

```sh
npm exec -- node --experimental-strip-types --test frontend/src/lib/transport/transport.test.ts
```

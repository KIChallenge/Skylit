# API-Fassade: Integrationsnotiz

Das Modul bietet eine typisierte Funktion pro Backend-Route, die das UI nutzt.
Die Typen stammen aus `generated/schema.d.ts`. Den Transport liefert `@/lib/transport`.
Das Modul enthält keinen UI-Code und keinen eigenen Fetch-Client.

Importiere alles aus `@/lib/api`.

## Exporte

| Export | Zweck |
|---|---|
| `api` | Zentrale Standardinstanz. Sie liest `config.apiUrl`, `apiTimeoutMs` und `streamIdleTimeoutMs` beim ersten Aufruf. |
| `getApiClient()` | Liefert dieselbe Standardinstanz als Funktion. |
| `createApiClient(config)` | Factory für Tests. Sie nimmt `baseUrl`, `timeoutMs`, `streamIdleTimeoutMs` und optional `fetch` oder einen fertigen `http`-Transport. |
| `toCard`, `toCards` | Prüfen Cards zur Laufzeit. Unbekannte oder ungültige Cards fallen heraus. |
| `toDocumentExtraction`, `toDocumentSummary` | Prüfen `DocumentSummaryCard.extraction` und liefern `DocumentExtraction` oder `null`. |
| `isKnownStreamEvent` | Prüft, ob ein Event-Typ in der generierten Union steht. |
| `resolveApiUrl(url, origin)` | Stellt relativen Backend-URLs den Origin voran. |
| `TransportError` | Fehlerklasse des Transports, hier nur weitergereicht. |
| Domain-Typen | `Persona`, `Me`, `Conversation`, `ConversationSummary`, `Message`, `Case`, `CaseStep`, `CaseStepStatus`, `Document`, `DocumentExtraction`, `MessageTransparency`, `Confidence`, `Source`, `Card`, `CardOf<T>`, `StreamEvent`, `StreamEventOf<T>` und weitere in `types.ts`. |

Alle Domain-Typen sind Aliase auf `components["schemas"]`. Ändere sie nie von Hand: Generiere das Schema neu.

## Funktionen von `ApiClient`

| Funktion | Route |
|---|---|
| `listPersonas()` | `GET /api/personas` |
| `login(personaId)` | `POST /api/auth/login` |
| `logout()` | `POST /api/auth/logout` |
| `getMe()` | `GET /api/me` |
| `listConversations()` | `GET /api/conversations` |
| `createConversation(title?)` | `POST /api/conversations` |
| `getConversation(id)` | `GET /api/conversations/{id}` |
| `getCase(conversationId)` | `GET /api/conversations/{id}/case` |
| `updateCaseStep(stepId, status)` | `PATCH /api/case-steps/{id}` |
| `uploadDocument({ file, filename?, conversationId? })` | `POST /api/documents` (multipart) |
| `getDocument(id)` | `GET /api/documents/{id}` |
| `getTransparency(messageId)` | `GET /api/messages/{id}/transparency` |
| `streamMessage(conversationId, { content, document_ids? })` | `POST /api/conversations/{id}/messages` (SSE) |
| `resolveUrl(url)` | Relative URL mit dem Backend-Origin |
| `documentFileUrl(documentId)` | Download-Link eines hochgeladenen Dokuments |

Jede Funktion nimmt als letztes Argument `{ signal, timeoutMs }`. `streamMessage` nimmt zusätzlich `idleTimeoutMs`.

## Beispiele

```ts
import { api, toCards, TransportError } from "@/lib/api";

const me = await api.login("maria");
const conversation = await api.createConversation();
const step = await api.updateCaseStep(stepId, "done");
const cards = toCards(message.cards); // Nur gültige Cards.
```

Upload mit längerem Timeout. Das Polling von `getDocument` gehört zum Upload-Feature:

```ts
const document = await api.uploadDocument(
  { file, conversationId: conversation.id },
  { timeoutMs: 60_000 },
);
```

Stream:

```ts
const controller = new AbortController();
try {
  for await (const event of api.streamMessage(id, { content }, { signal: controller.signal })) {
    switch (event.type) {
      case "text.delta": /* event.delta anhängen */ break;
      case "tool.result": /* toCard(event.card) zeigen */ break;
      case "error": /* event.message zeigen */ break;
    }
  }
} catch (error) {
  if (error instanceof TransportError && error.code !== "aborted") {
    /* error.message mit „Erneut versuchen“ zeigen */
  }
}
```

## Regeln

- `streamMessage` sendet genau einen POST. Die Fassade wiederholt ihn nie, denn jeder POST startet einen neuen Agent-Turn.
- `streamMessage` lässt Event-Typen außerhalb der generierten Union weg.
- `uploadDocument` sendet `file` und nur bei Angabe `conversation_id`.
- Prüfe Cards aus `Message.cards` und `tool.result` mit `toCard` oder `toCards`, bevor das UI sie zeigt.
- Die Guards ergänzen keine Werte. Eine unvollständige Extraktion ergibt `extraction: null`.
- `resolveUrl` ergänzt den Origin nur bei Pfaden mit führendem `/`. Externe Quellenlinks bleiben unverändert.
- Nutze `resolveUrl` für `pdf_url`, `ics_url` und `Source.url`.

## Tests

Die Tests brauchen kein Backend. Sie nutzen ein gefälschtes `fetch` oder einen gefälschten Transport.

```sh
npm --prefix frontend run test:unit -- src/lib/api
```

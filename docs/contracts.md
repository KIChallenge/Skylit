# Contracts — source of truth

Everything two workstreams depend on is defined here.
**Change a contract only together with this file, in the same commit, and tell the team.**

Der implementierte Backend-Code ist maßgeblich. Bei einem Widerspruch gilt der Code, und diese Datei wird korrigiert.

- REST-Formate: Pydantic-Modelle in `backend/app/schemas/` und Routen in `backend/app/api/`.
- SSE-Events und Cards: `backend/app/schemas/events.py` und `backend/app/schemas/cards.py`.
- OpenAPI: `make --silent openapi` schreibt das Schema auf stdout. Der Befehl braucht weder Server noch Datenbank.
- `GET /api/_schema/events` bringt die Event-Union ins OpenAPI. Diese Route ist nur für die Typgenerierung da.
- Frontend-Anbindung: §7 beschreibt Transport und generierte Typen.
- Gestrichene und fehlende Teile: §8 listet sie vollständig.

Konventionen:

- JSON verwendet `snake_case`, und alle Routen liegen unter `/api`.
- Zeitstempel sind ISO-8601-Strings mit Zeitzone. `date_of_birth` ist ein Datum im Format `YYYY-MM-DD`.
- Nutzer-, Gesprächs-, Nachrichten- und Dokument-IDs sind UUID-Strings.
- Stammdaten-IDs sind freie Strings: `Persona.id`, `Office.id`, `Provider.id`, `LeistungInfo.id`, `FormDraft.form_id`.

---

## 1. REST API

### Auth und Cookie

- `POST /api/auth/login` setzt das signierte Cookie `lotse_session`.
- Cookie-Attribute: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` 7 Tage.
- `Secure` ist nur bei `APP_ENV=production` gesetzt.
- Öffentlich sind nur `GET /api/health`, `GET /api/personas` und `POST /api/auth/login`.
- Alle anderen `/api`-Routen verlangen das Cookie und antworten sonst mit 401. Das gilt auch für `POST /api/auth/logout` und `GET /api/_schema/events`.
- Fremde Ressourcen liefern 404, nicht 403. Das Frontend erfährt also nicht, ob die Ressource existiert.

### CORS

- Frontend und Backend laufen auf verschiedenen Origins. Jeder `fetch` verwendet deshalb `credentials: "include"`.
- Das Backend setzt `allow_credentials=True`, `allow_methods=["*"]` und `allow_headers=["*"]`.
- `BACKEND_CORS_ORIGINS` enthält die erlaubten Origins als Komma-Liste oder JSON-Array.
- Der Wert `*` ist verboten. Das Backend startet dann nicht.

### Fehlerformat

Jeder Fehler, den eine Route oder die Validierung auslöst, hat diese Form:

```json
{ "error": { "code": "not_found", "message": "Dieses Gespräch gibt es nicht." } }
```

| Status | `code` | Herkunft |
|---|---|---|
| 400 | `empty_file` | Upload ohne Inhalt |
| 401 | `unauthorized` | Cookie fehlt, ist ungültig oder abgelaufen |
| 404 | `not_found` | Ressource fehlt oder gehört einer anderen Persona |
| 413 | `file_too_large` | Upload über `MAX_UPLOAD_MB` |
| 415 | `unsupported_type` | Upload ist kein PDF, JPEG oder PNG |
| 422 | `validation_error` | Ungültige Eingabe, `message` nennt nur die Feldnamen |
| 500 | `storage_failed` | Upload konnte nicht gespeichert werden |

- Unbekannte Pfade und falsche Methoden nutzen dieselbe Hülle: `not_found` oder `method_not_allowed`. `message` ist dann die englische Standardphrase. Der Transport ersetzt sie durch einen deutschen Text.
- Unbehandelte Ausnahmen liefern 500 als Klartext, ohne JSON-Hülle und ohne CORS-Header. Der Browser meldet das als `network_error`.
- Das OpenAPI deklariert für 422 `HTTPValidationError`. Dieses Format sendet das Backend nie. Lies 422 immer als Fehlerhülle.

### Health and auth

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/api/health` | nein | — | 200 `Health` |
| GET | `/api/personas` | nein | — | 200 `Persona[]` in Seed-Reihenfolge |
| POST | `/api/auth/login` | nein | `{persona_id: string}` (1–64 Zeichen) | 200 `Me` + Cookie, 404 bei unbekannter Persona |
| POST | `/api/auth/logout` | ja | — | 204, löscht das Cookie |
| GET | `/api/me` | ja | — | 200 `Me` |
| PATCH | `/api/me/profile` | ja | `ProfileUpdate` | 200 `Me` |

```ts
Health    { status: "ok"; db: "ok" | "down"; llm_provider: "eustella" | "azure" | "fake" | "replay";
            embedder: "ready" | "loading" | "not_loaded"; kb_chunks: number }
Persona   { id: string; display_name: string; tagline: string; avatar_emoji: string }
Me        { user_id: string; persona_id: string; display_name: string; profile: Profile }
Profile   { language: "de" | "de-simple" | "en"; depth: "short" | "detailed";
            bundesland: string | null; postal_code: string | null;
            insurer: "OEGK" | "BVAEB" | "SVS" | null; date_of_birth: string | null }
ProfileUpdate = Partial<Profile>
```

- `Health.status` ist immer `"ok"`. Den Datenbankzustand zeigt nur `db`.
- `ProfileUpdate` ändert nur gesendete Felder. Unbekannte Felder ergeben 422.
- `language` und `depth` dürfen nicht `null` sein. Die anderen Felder setzt `null` zurück.
- `postal_code` hat genau vier Ziffern. `bundesland` hat 1–40 Zeichen.
- Das Schema erlaubt `de-simple`. Der Scope hat „Einfache Sprache“ gestrichen, das UI bietet den Wert nicht an.

### Conversations and messages

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/conversations` | — | 200 `ConversationSummary[]` (zuletzt geändert zuerst) |
| POST | `/api/conversations` | optional `{title?: string}` (1–200 Zeichen) | **201** `Conversation`, erzeugt auch den leeren Fall |
| GET | `/api/conversations/{conversation_id}` | — | 200 `Conversation` (Nachrichten nach `created_at`) |
| DELETE | `/api/conversations/{conversation_id}` | — | 204 |
| POST | `/api/conversations/{conversation_id}/messages` | `MessageCreate` | 200 **SSE-Stream** (§2) |

```ts
ConversationSummary { id: string; title: string; updated_at: string; open_steps: number }
Conversation { id: string; title: string; created_at: string; updated_at: string;
               messages: Message[]; case: Case }
Message { id: string; role: "user" | "assistant"; content: string; created_at: string;
          document_ids: string[]; cards: Card[]; sources: Source[];
          escalation_id: string | null }
MessageCreate { content: string; document_ids?: string[] }  // content: 1–4000 Zeichen
Source  { title: string; url: string; publisher: string }
```

- Ohne `title` setzt das Backend „Neuer Fall“.
- `open_steps` zählt alle Schritte mit einem Status außer `done`.
- `Message.document_ids` ist nur bei Nutzernachrichten gefüllt. Bei KI-Antworten ist das Feld leer.
- `Message.cards` hat im OpenAPI den Typ `Record<string, unknown>[]`. Zur Laufzeit enthält es `Card`-Objekte aus §2.
- `Source.url` ist bei Wissensquellen eine absolute URL.
- Bei hochgeladenen Dokumenten ist `Source.url` relativ: `/api/documents/{id}/file`. `publisher` ist dann „Von Ihnen hochgeladenes Dokument“.
- Der Message-POST antwortet bei 401, 404 und 422 mit JSON nach dem Fehlerformat, nicht mit SSE.
- Das Backend ignoriert `document_ids` fremder oder unbekannter Dokumente ohne Fehlermeldung.

### Case

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/conversations/{conversation_id}/case` | — | 200 `Case` |
| PATCH | `/api/case-steps/{step_id}` | `{status: StepStatus}` | 200 `CaseStep` |

```ts
StepStatus = "open" | "in_progress" | "done" | "blocked"
Case     { id: string; title: string; subject: "self" | "parent" | "child" | "partner" | "other";
           summary: string; steps: CaseStep[]; updated_at: string }
CaseStep { id: string; title: string; description: string;
           status: StepStatus;
           category: "info" | "form" | "document" | "appointment" | "contact" | "escalation";
           leistung_id: string | null; due_hint: string | null;
           related_card: Card | null; position: number }
```

- Das Backend sortiert `steps` nach `position`.
- Der PATCH akzeptiert nur `status`. Andere Felder ergeben 422.
- `related_card` ist aktuell immer `null`, weil kein Tool das Feld schreibt.

### Documents

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/documents` | multipart: `file` (Pflicht), `conversation_id` (optional) | **201** `Document` mit `status: "processing"` |
| GET | `/api/documents/{id}` | — | 200 `Document` |
| GET | `/api/documents/{id}/file` | — | 200 Originaldatei, `Content-Disposition: inline` |

```ts
Document { id: string; filename: string; mime_type: string;
           status: "processing" | "ready" | "failed";
           kind: "discharge_letter" | "finding" | "vaccination_record" | "notice" | "other" | null;
           extracted: DocumentExtraction | null; created_at: string }
```

Upload:

- Erlaubte Typen: `application/pdf`, `image/jpeg`, `image/png`. Das Backend prüft den Content-Type des Multipart-Teils.
- `MAX_UPLOAD_MB` begrenzt die Dateigröße. Der Standardwert ist 10.
- Sende `conversation_id` mit, damit die Eskalation das Dokument in der Übergabe nennt. Eine fremde oder unbekannte ID ergibt 404.

Polling:

1. Das Frontend fragt alle 1,5 s `GET /api/documents/{id}` ab.
2. Bei `ready` sind `kind` und `extracted` gesetzt. Das Frontend sendet dann die Nachricht mit `document_ids`.
3. Bei `failed` sind `kind` und `extracted` `null`. Das Frontend zeigt eine eigene Fehlermeldung mit „Erneut versuchen“.

- Die Extraktion kann eine Minute oder länger dauern.
- Das Backend hat kein Polling-Limit. Stürzt die Hintergrundaufgabe ab, bleibt der Status `processing`.
- Das Frontend begrenzt das Polling deshalb selbst. Der Grenzwert gehört in die zentrale Frontend-Konfiguration.
- `Document` enthält keinen Fehlertext. Das Backend speichert den Grund intern und liefert ihn nicht aus.

### Formulare, Termine, Eskalationen

| Method | Path | Response |
|---|---|---|
| GET | `/api/form-drafts/{id}` | 200 `FormDraft` |
| GET | `/api/form-drafts/{id}/pdf` | 200 `application/pdf`, Attachment `{form_id}-{id}.pdf` |
| GET | `/api/appointments/{id}/ics` | 200 `text/calendar`, Attachment `termin-{id}.ics` |
| GET | `/api/escalations/{id}` | 200 `Escalation` |

```ts
FormDraft    { id: string; form_id: string; title: string; filled: FieldValue[]; missing: FieldSpec[];
               to_be_filled_by_others: FieldSpec[]; pdf_url: string; created_at: string }
FieldValue   { key: string; label: string; value: string; source: "conversation" | "document" | "profile" }
FieldSpec    { key: string; label: string; hint: string | null }
Escalation   { id: string; reason_code: EscalationReason; target: Contact; handover_summary: string; created_at: string }
EscalationReason = "emergency" | "medical_question" | "legal_uncertainty" | "no_source" | "user_stuck" | "social_crisis"
Contact      { name: string; phone: string | null; url: string | null; hours: string | null; note: string | null }
```

Downloadpfade:

- `FormDraft.pdf_url` ist `/api/form-drafts/{id}/pdf`.
- `Appointment.ics_url` ist `/api/appointments/{id}/ics`.
- Beide Werte sind relativ. Das Frontend stellt ihnen `NEXT_PUBLIC_API_URL` voran.
- Für Termine gibt es keine JSON-Route. Die Daten kommen nur aus der `appointment`-Card.
- Downloads sind normale Links, weil der Transport nur JSON liest. Bei 401 oder 404 zeigt der Browser das JSON der Fehlerhülle.

### Transparenz

| Method | Path | Response |
|---|---|---|
| GET | `/api/messages/{id}/transparency` | 200 `MessageTransparency` |
| GET | `/api/messages/{id}/audit` | 200 `AuditEntry[]`, dieselben Daten wie `entries` |

Beide Routen liefern 404 in diesen Fällen:

- Die ID gehört zu einer Nutzernachricht oder zu einer anderen Persona.
- Die KI-Antwort ist noch nicht gespeichert. Das gilt vor `message.completed`.
- Der Turn endete mit `error`, bevor Text oder eine Tool-Runde abgeschlossen war. Dann gibt es keine KI-Nachricht.

```ts
MessageTransparency {
  message_id: string;
  model: string | null;
  provider: string | null;           // aktuell immer null, siehe unten
  sources: Source[];
  tools: ToolInfo[];
  retrieval: RetrievalInfo;          // aktuell immer leer, siehe unten
  guardrails: GuardrailInfo[];
  escalation: EscalationInfo | null;
  confidence: Confidence;
  entries: AuditEntry[];             // chronologisch
}
ToolInfo       { name: string; label: string; ok: boolean }
RetrievalInfo  { query: string | null; chunks: RetrievalChunk[] }
RetrievalChunk { slug: string; heading: string; score: number }
GuardrailInfo  { code: string; summary: string }
EscalationInfo { reason_code: string; target: Contact }
Confidence     { level: "hoch" | "mittel" | "niedrig"; reason: string }
AuditEntry     { id: string; created_at: string;
                 event_type: "llm_call" | "tool_call" | "retrieval" | "guardrail" | "escalation" | "error";
                 summary: string; detail: Record<string, unknown> }
```

`confidence`:

- Das Backend berechnet `level` und `reason`. Das Frontend übernimmt beide unverändert und berechnet nichts selbst.
- `reason` ist ein deutscher Satz für die Anzeige.
- Der Wert kommt nur aus dieser Route. Der SSE-Stream enthält ihn nicht.

Das Backend prüft diese Regeln in der angegebenen Reihenfolge. Die erste passende Regel gilt.

| `level` | Bedingung |
|---|---|
| `niedrig` | `sources` ist leer, oder der Eskalationsgrund ist `no_source` |
| `mittel` | Genau eine Quelle, oder mindestens ein Tool mit `ok: false` |
| `hoch` | Alle anderen Fälle: mehrere Quellen und alle Tools erfolgreich |

Die Stufe beschreibt die Beleglage, nicht die fachliche Richtigkeit. Eine Notfall-Antwort hat ohne Tool-Quellen keine Quellen und ergibt dann `niedrig`.

Weitere Felder:

- `model` kommt aus dem letzten `llm_call`, sonst aus der gespeicherten Usage. Der Wert kann `null` sein.
- `provider` ist aktuell immer `null`, weil der Audit-Eintrag `llm_call` den Provider nicht schreibt.
- `retrieval` ist aktuell immer `{query: null, chunks: []}`. Die Anzahl der Treffer steht in `entries` mit `event_type = "retrieval"`.
- `tools` enthält je `tool_call` den Namen, das deutsche Label und `ok`.
- `guardrails.code` ist `emergency` oder `social_crisis`, wenn der Red-Flag-Check anschlägt.
- `escalation` enthält nur Grund und Kontakt. Die Übergabezusammenfassung liefert `GET /api/escalations/{Message.escalation_id}`.

`entries[].detail` enthält nur diese Schlüssel. Andere Schlüssel filtert das Backend heraus.

| `event_type` | Schlüssel in `detail` |
|---|---|
| `llm_call` | `model`, `finish_reason`, `tool_choice`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, `latency_ms`, `request_id`, `rate_limit` |
| `tool_call` | `name`, `call_id`, `ok`, `argument_keys`, `error`, `latency_ms` |
| `retrieval` | `chunk_count`, `sources` |
| `guardrail` | `reason_code`, `contact_ids` |
| `escalation` | `escalation_id`, `reason_code` |
| `error` | `code`, `status`. Bei einer fehlgeschlagenen Wissenssuche ist `detail` leer. |

- `detail.error` bei `tool_call` richtet sich an das Modell. Zeige im UI nur `label` und `ok`.
- `summary` ist deutscher Text.

### Dev only (`APP_ENV=development` oder `demo`)

| Method | Path | Zweck |
|---|---|---|
| POST | `/api/dev/reset` | 204, löscht Gespräche, Fälle, Dokumente, Formulare und Termine der aktuellen Persona |

Die Route verlangt das Cookie. Bei `APP_ENV=production` antwortet sie mit 404.

---

## 2. SSE stream

`POST /api/conversations/{conversation_id}/messages` liefert diese Header: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

Jedes Event hat diese Form:

```
event: text.delta
data: {"delta":"Pflegegeld könnte in Frage kommen."}

```

**`type` steht auf der `event:`-Zeile, nicht im JSON von `data:`.**
Die Pydantic-Modelle und das OpenAPI enthalten `type`, damit die Union unterscheidbar ist. Der Transport ergänzt `type` beim Lesen aus der `event:`-Zeile.

| `event` | `data` | Wann |
|---|---|---|
| `message.created` | `{message_id, conversation_id}` | erstes Event jedes Turns |
| `emergency` | `{contacts: Contact[], message: string}` | Red-Flag-Treffer, vor jeder LLM-Ausgabe |
| `status` | `{stage: "retrieving" \| "thinking" \| "tool" \| "writing", label: string}` | Fortschritt, `label` ist deutscher Anzeigetext |
| `text.delta` | `{delta: string}` | Antworttext in Markdown |
| `tool.called` | `{call_id, name, label: string}` | Modell ruft ein Tool auf |
| `tool.result` | `{call_id, name, ok: boolean, card: Card \| null, error: string \| null}` | Tool ist fertig |
| `case.updated` | `{case: Case}` | nach `tool.result`, wenn das Tool den Fall geändert hat |
| `escalation` | `{escalation: Escalation}` | nach `tool.result` des `escalate`-Tools |
| `sources` | `{sources: Source[]}` | nur bei Erfolg, direkt vor `message.completed` |
| `message.completed` | `{message_id, finish_reason: string, usage: {prompt_tokens, completion_tokens, cached_tokens}}` | letztes Event bei Erfolg |
| `error` | `{code: string, message: string, retry_after: number \| null}` | letztes Event bei Fehler |

Reihenfolge:

- `message.created` kommt zuerst. Zuletzt kommt genau eines von `message.completed` und `error`.
- `emergency` folgt direkt auf `message.created`. Danach läuft der Turn ohne Wissenssuche weiter und endet normal.
- `text.delta` kann sich über mehrere Runden mit Tool-Events abwechseln.
- Jeder Tool-Aufruf sendet zuerst `status` mit `stage: "tool"`, dann `tool.called` und danach `tool.result`.

Felder:

- `message_id` ist die ID der KI-Antwort. Die Nutzernachricht bekommt im Stream keine ID.
- `message.completed` bedeutet: Die KI-Antwort ist gespeichert, und `GET /api/messages/{id}/transparency` funktioniert.
- `tool.result.error` ist immer derselbe deutsche Anzeigetext. Der technische Grund geht nur an das Modell.
- `retry_after` zählt Sekunden. Das Feld ist nur bei Überlastung gesetzt.
- `error.message` ist deutscher Anzeigetext.
- `error.code` ist zum Beispiel `rate_limited`, `overloaded`, `timeout`, `empty_response`, `unavailable` oder `internal_error`. Die Liste ist offen, das Frontend behandelt unbekannte Codes generisch.

Abbruch und Fehler:

- Das `error`-Event speichert Text und abgeschlossene Tool-Runden als KI-Antwort. Das Event `sources` fehlt dann.
- Trennt der Client die Verbindung, stoppt das Backend den Turn. Es sendet kein Abschluss-Event und speichert keine KI-Antwort. Die Nutzernachricht bleibt gespeichert.
- Jeder POST startet einen neuen Turn. Wiederhole ihn nur nach einer Aktion der Person.
- Nach dem Neuladen gibt es das Event `emergency` nicht mehr. `guardrails` nennt nur den Code, `detail.contact_ids` nur die Kontakt-IDs. Die Kontaktdaten sind dann nicht abrufbar.

### Cards

```ts
type Card =
  | { type: "form_draft";    form_draft: FormDraft }
  | { type: "office";        office: Office }
  | { type: "provider_list"; providers: Provider[]; demo: true }
  | { type: "appointment";   appointment: Appointment; demo: true }
  | { type: "email_draft";   email: EmailDraft }
  | { type: "escalation";    escalation: Escalation }
  | { type: "document_summary"; document_id: string; extraction: DocumentExtraction }
  | { type: "leistung";      leistung: LeistungInfo }
  | { type: "sampler_question"; question: SamplerQuestion }

Office       { id: string; name: string; organisation: string; address: string;
               postal_code: string | null; city: string | null; phone: string | null;
               email: string | null; url: string | null; hours: string | null; maps_url: string | null }
Provider     { id: string; name: string; kind: ProviderKind; specialty: string | null;
               address: string | null; postal_code: string | null; distance_km: number | null;
               phone: string | null; demo: true }
ProviderKind = "gp" | "specialist" | "care_counselling" | "mobile_care" | "therapy" | "course"
Appointment  { id: string; provider: Provider; start: string; end: string; ics_url: string; demo: true }
EmailDraft   { to_label: string; to_email: string | null; subject: string; body: string }
LeistungInfo { id: string; title: string; short: string; conditions: string[]; office_hint: string;
               form_ids: string[]; documents_needed: string[]; source: Source }
SamplerQuestion { step: SamplerStep; step_label: string; position: number; total: number;
                  question: string; options: string[]; multiple: boolean; free_text_label: string }
SamplerStep  = "S_O" | "S_P" | "S_Q" | "S_R" | "S_S" | "S_T" | "A" | "M" | "P" | "L" | "E" | "R"
```

- Bei Cards steht `type` im JSON-Objekt. Das unterscheidet sie von SSE-Events.
- `document_summary.extraction` hat im OpenAPI den Typ `Record<string, unknown>`. Zur Laufzeit folgt es `DocumentExtraction` aus §5.
- Die `office`-Card zeigt nur die erste passende Stelle. Weitere Stellen sieht nur das Modell.
- Die `provider_list`-Card kann eine leere Liste enthalten.
- Karten mit `demo: true` tragen im UI das Label „Demo-Daten“.
- Die `sampler_question`-Card ist nur an der neuesten Antwort beantwortbar. Das UI sendet die Antwort als normale Nutzernachricht: `„<step_label>: <Optionen> – <Beschreibung>“`.

---

## 3. Database schema (Postgres + pgvector)

Alembic owns the schema. All tables have `id uuid pk default gen_random_uuid()` and `created_at timestamptz default now()` unless noted.

| Table | Columns | Notes |
|---|---|---|
| `users` | `persona_id text unique`, `display_name`, `tagline`, `avatar_emoji` | seeded from `seed/personas.json` |
| `profiles` | `user_id fk unique`, `language`, `depth`, `bundesland`, `postal_code`, `insurer`, `date_of_birth date`, `extra jsonb` | 1:1 with users |
| `conversations` | `user_id fk`, `title`, `updated_at` | |
| `messages` | `conversation_id fk`, `role`, `content text`, `document_ids uuid[]`, `cards jsonb`, `sources jsonb`, `tool_calls jsonb`, `escalation_id fk null`, `usage jsonb` | `tool_calls` = raw calls + results for replaying history to the LLM |
| `cases` | `conversation_id fk unique`, `title`, `subject`, `summary`, `updated_at` | 1:1 with conversation |
| `case_steps` | `case_id fk`, `title`, `description`, `status`, `category`, `leistung_id null`, `due_hint null`, `related_card jsonb null`, `position int` | |
| `documents` | `user_id fk`, `conversation_id fk null`, `filename`, `mime_type`, `storage_path`, `status`, `kind`, `extracted jsonb`, `error text null` | |
| `form_drafts` | `user_id fk`, `conversation_id fk`, `form_id`, `values jsonb`, `missing jsonb`, `pdf_path` | |
| `appointments` | `user_id fk`, `conversation_id fk`, `provider_id`, `start timestamptz`, `end timestamptz`, `status` | demo |
| `escalations` | `conversation_id fk`, `message_id fk null`, `reason_code`, `target jsonb`, `handover_summary text` | |
| `knowledge_documents` | `slug unique`, `title`, `source_url`, `publisher`, `category`, `bundesland null`, `content_hash` | one per KB markdown file |
| `knowledge_chunks` | `document_id fk`, `chunk_index`, `heading`, `content text`, `tsv tsvector generated ('german')`, `embedding vector(EMBEDDING_DIM)`, `content_hash` | HNSW on `embedding` (cosine), GIN on `tsv` |
| `leistungen` | `id text pk`, `title`, `category`, `short`, `conditions jsonb`, `office_kind`, `form_ids text[]`, `documents_needed jsonb`, `source_url` | structured catalogue from `seed/leistungen.json` |
| `offices` | `id text pk`, `organisation`, `name`, `kind`, `bundesland`, `address`, `postal_code`, `city`, `phone`, `email`, `url`, `hours`, `lat`, `lon` | real public offices |
| `providers` | `id text pk`, `name`, `kind`, `specialty`, `address`, `postal_code`, `lat`, `lon`, `phone` | **synthetic** |
| `audit_log` | `conversation_id null`, `message_id null`, `user_id null`, `event_type`, `summary`, `detail jsonb` | index on `(message_id)` |

Changing `EMBEDDING_MODEL` to one with a different dimension needs a migration and a re-ingest.

---

## 4. LLM tools

Defined in `backend/app/tools/`, one Pydantic input model per tool. `registry.py` exports them as OpenAI `tools` (`type: "function"`, JSON schema from the model). Descriptions are written **for the model** and must state when *not* to use the tool.

Every handler: `async def handle(input: XInput, ctx: ToolContext) -> ToolOutput` where `ToolContext` holds `db`, `user`, `conversation`, `case`, `audit`, and `ToolOutput = {result: dict (sent back to the LLM), card: Card | None, case_changed: bool}`.

Das Frontend sieht von dieser Tabelle nur `name`, `label`, Card und Folge-Event.

| Tool | Input | Returns to LLM | Card | `label` |
|---|---|---|---|---|
| `search_knowledge` | `query: str`, `category?: str`, `top_k?: int=5` | `{chunks: [{heading, content, source}]}` | — | Offizielle Quellen werden gesucht |
| `get_leistung` | `leistung_id: str` | `{leistung}` | `leistung` | Leistung wird nachgeschlagen |
| `find_office` | `leistung_id?: str`, `office_kind?: str`, `postal_code?: str`, `bundesland?: str` | `{offices}` | `office` | Zuständige Stelle wird gesucht |
| `find_providers` | `kind: ProviderKind`, `postal_code: str`, `specialty?: str`, `limit?: int=3` | `{providers, demo}` | `provider_list` | Passende Anbieter werden gesucht |
| `propose_appointment` | `provider_id: str`, `time_preference?: "morning" \| "afternoon" \| "any"`, `earliest_date?: date` | `{appointment, demo}` | `appointment` | Demo-Termin wird vorgeschlagen |
| `prepare_form` | `form_id: str`, `values: dict[str, str]` (semantic keys) | `FormDraft` + `rejected` | `form_draft` | Formular wird vorausgefüllt |
| `get_document` | `document_id: str` | extraction JSON | `document_summary` | Dokument wird gelesen |
| `upsert_case_step` | `step_id?: str`, `title`, `description`, `category`, `status?="open"`, `leistung_id?`, `due_hint?` | `{step}` | — (emits `case.updated`) | Schritt wird in „Mein Fall“ eingetragen |
| `set_case_summary` | `title: str`, `subject`, `summary: str` | `{ok}` | — (emits `case.updated`) | Fallzusammenfassung wird aktualisiert |
| `draft_email` | `to_label: str`, `to_email?: str`, `subject: str`, `body: str` | `{ok, email}` | `email_draft` | E-Mail-Entwurf wird erstellt |
| `ask_sampler` | `step: SamplerStep`, `question: str`, `options: str[2..6]`, `multiple?: bool=false`, `free_text_label?: str` | `{ok, shown, step}` | `sampler_question` (ends the turn) | Rückfrage wird vorbereitet |
| `escalate` | `reason_code: EscalationReason`, `target_kind: str`, `open_question: str` | `Escalation` | `escalation` (emits `escalation`) | Übergabe an einen Menschen wird vorbereitet |

`get_insurance_status` und `update_profile` sind gestrichen und nicht registriert (§8).

Rules:
- `LLM_MAX_TOOL_ROUNDS` limits the tool rounds per turn (default 3). After the last round the model must answer in text.
- `ask_sampler` ends the turn after its round. The model gets no further call, and a turn without text is valid (D-033).
- Tools never call the LLM themselves. `escalate` builds the handover summary from case data with a template.
- Tool errors return `{error: "..."}` to the LLM so it can recover; they never crash the stream.

---

## 5. Document extraction schema

Used as `response_format: {type: "json_schema", json_schema: {name: "document_extraction", schema: ...}}`. Pydantic model `DocumentExtraction` in `backend/app/schemas/documents.py`.

```ts
DocumentExtraction {
  kind: "discharge_letter" | "finding" | "vaccination_record" | "notice" | "other";
  issuer: string | null;                 // hospital / doctor / office
  document_date: string | null;
  patient: { name: string | null; date_of_birth: string | null; address: string | null;
             postal_code: string | null; insurer: string | null; svnr: string | null };
  living_situation: string | null;       // verbatim or near-verbatim
  documented_recommendations: {
    topic: "rehabilitation" | "care_allowance" | "mobile_care" | "follow_up" | "aids" | "transport"
         | "prescription_fee_exemption" | "nutrition" | "social_services" | "other";
    quote: string;                       // VERBATIM from the document
    section: string | null;              // e.g. "7. Empfehlung zur medizinischen Rehabilitation"
  }[];
  follow_up_appointments: { what: string; when: string | null; quote: string }[];
  warnings_in_document: string[];        // verbatim warning signs the document lists (for escalation display)
  confidence_note: string | null;        // what was unreadable
}
```
The extraction prompt forbids interpretation: no diagnosis summaries, no explanations, only explicit statements and administrative facts. Diagnoses are **not** extracted.

---

## 6. Environment variables

Die vollständige Liste steht in [`.env.example`](../.env.example). Das Backend liest sie über `app/config.py`.
Das Frontend liest API-URL und Timeouts zentral über `frontend/src/lib/config.ts`.

---

## 7. Frontend-Anbindung

### Transport (gemergt)

`frontend/src/lib/transport/` enthält den Browser-Client für REST und POST-SSE. Details stehen in `frontend/src/lib/transport/README.md`.

- `createHttpClient({baseUrl, timeoutMs, streamIdleTimeoutMs})` erstellt den Client mit `get`, `post`, `patch`, `delete`, `request` und `stream`.
- `baseUrl` enthält nur den Origin aus `NEXT_PUBLIC_API_URL`. Pfade beginnen mit `/api`.
- Jeder Request sendet `credentials: "include"`.
- `FormData` geht unverändert hinaus. Andere Bodys gehen als JSON hinaus.
- `stream()` sendet den POST beim ersten `next()` und wiederholt ihn nie.
- `stream()` ergänzt `type` aus der `event:`-Zeile und endet nach `message.completed` oder `error`.
- Das Modul liest keine Umgebungsvariablen und hat keine Backend-Domänentypen. Es hat auch keine Standard-Timeouts.

Das UI behandelt zwei Fehlerarten getrennt:

- `TransportError` hat `code`, `status` und eine deutsche `message`. Er entsteht bei HTTP-Fehlern, Timeouts und Verbindungsabbrüchen.
- Das SSE-Event `error` ist ein normales Stream-Event und kein `TransportError`.

`TransportError.code` enthält den `code` der Fehlerhülle oder einen dieser Transport-Codes: `network_error`, `timeout`, `aborted`, `invalid_response`, `stream_incomplete`, `stream_invalid_event`.
Bei `aborted` zeigt das UI keine Fehlermeldung.

### Generierte Typen (gemergt)

- Das Schema liegt unter `frontend/src/lib/api/generated/openapi.json`, die Typen unter `frontend/src/lib/api/generated/schema.d.ts`.
- Dieser Pfad ersetzt das frühere `frontend/src/lib/api/schema.d.ts`.
- Quelle ist die Ausgabe von `make --silent openapi`. Die Generierung braucht keinen laufenden Server.
- `npm --prefix frontend run api:types` erzeugt die Typen aus dem gespeicherten Schema.
- Bearbeite generierte Dateien nie von Hand.
- Die API-Fassade verwendet die generierten Typen. Dieses Dokument erklärt die Laufzeitbesonderheiten.

Das generierte Schema weicht an diesen Stellen von den tatsächlichen Daten ab. Der Integrations-Task deckt sie mit einer kleinen Adapter-Schicht ab:

| Stelle | OpenAPI | Tatsächlich |
|---|---|---|
| `Message.cards` | `Record<string, unknown>[]` | `Card[]` |
| `DocumentSummaryCard.extraction` | `Record<string, unknown>` | `DocumentExtraction` |
| 422-Antworten | `HTTPValidationError` | Fehlerhülle aus §1 |
| Message-POST, Antwort | kein Schema für `text/event-stream` | Events aus `GET /api/_schema/events` |
| SSE-`data` | enthält `type` | `type` steht auf der `event:`-Zeile |
| Binär-Downloads | kein verwertbares Schema | Datei, Einbindung als Link |

Relative URLs brauchen `NEXT_PUBLIC_API_URL` als Präfix: `pdf_url`, `ics_url` und `Source.url`, wenn der Wert mit `/` beginnt.

---

## 8. Gestrichen oder nicht verfügbar

Baue keine UI auf diesen Punkten auf und erfinde keine Ersatzwerte.

### Nicht implementiert oder gestrichen

| Punkt | Status | Folge fürs Frontend |
|---|---|---|
| `GET /api/forms`, `FormTemplate` | keine Route | Kein Formularkatalog. Formulare erscheinen nur als `form_draft`-Card. |
| `GET /api/dev/stream-fixture/{name}` | keine Route | Für Offline-Demos gilt `LLM_PROVIDER=replay`. |
| Tool `get_insurance_status` | gestrichen (PLAN) | Kein Versicherungsstatus im UI. |
| Tool `update_profile` | gestrichen (PLAN) | Das Modell ändert das Profil nicht. `PATCH /api/me/profile` bleibt verfügbar. |
| Sprache `de-simple` | gestrichen (PLAN), im Schema noch vorhanden | Nicht anbieten. |

### Felder ohne Daten

| Feld | Aktueller Wert | Anzeige |
|---|---|---|
| `MessageTransparency.provider` | immer `null` | Keinen Betreiber anzeigen. |
| `MessageTransparency.retrieval` | immer `{query: null, chunks: []}` | Treffer aus `entries` lesen, Chunks nicht anzeigen. |
| `CaseStep.related_card` | immer `null` | Keine Card am Schritt erwarten. |

### Angaben, die das Backend nicht liefert

| Angabe | Lage |
|---|---|
| Seite oder Abschnitt einer Quelle | `Source` hat nur `title`, `url` und `publisher`. Dokumentzitate haben `section` in `DocumentExtraction`. |
| Fehlertext eines fehlgeschlagenen Dokuments | `Document` hat kein Fehlerfeld. |
| Notfallkontakte nach dem Neuladen | Das Event `emergency` wird nicht gespeichert. |
| ID der Nutzernachricht im Stream | Erst `GET /api/conversations/{conversation_id}` liefert sie. |
| `confidence` im Stream | Erst die Transparenz-Route liefert sie, nach `message.completed`. |

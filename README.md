# SV KI-Lotse — Team Skylit

## Beschreibung und Lösungsansatz

Versicherte und Angehörige müssen bei Pflege und Entlassung Leistungen, Formulare und zuständige Stellen selbst finden.
Der SV KI-Lotse macht aus einer Alltagsbeschreibung und einem Entlassungsbrief einen Fall mit konkreten Schritten, Formular und Kontakt.

Das [Demo-Skript](docs/PITCH.md) beschreibt diese Szenarien:

- **S1:** Eine Angehörige lädt einen Entlassungsbefund hoch und erhält Leistungen, Fallschritte, einen vorausgefüllten Pflegegeldantrag und Stellen.
- **S2:** Bei einer Frage zur Medikamentendosis verweist der Lotse an medizinisches Fachpersonal und erstellt eine Übergabezusammenfassung.
- **S3:** Bei plötzlicher Atemnot meldet der Lotse den Notruf 144 vor jeder Modellantwort.
- **S5, optional:** Der Lotse beantwortet eine Frage zu Vorsorgeuntersuchungen auf Englisch.

Der Lotse führt einen Fall mit Schritten und Formularen statt nur einen Chatverlauf.
Menschen prüfen und senden Formulare selbst; die zuständige Stelle entscheidet über Leistungen.
Ein Kalender unter „Mein Fall“ sammelt Arzttermine, Fristen und Erinnerungen aus dem Gespräch.
Termin-Vorschläge speichert die Person mit „Im Kalender speichern“; eigene Einträge legt sie im vergrößerten Kalender an.
Ärztinnen und Ärzte in der Nähe stammen aus der Ärzteliste der Stadt Wien (data.wien.gv.at, CC BY 4.0).
Gibt die Person ihren Standort im Browser frei, misst der Lotse die Entfernung ab dort statt ab der Postleitzahl.
Der Standort geht nicht an das KI-Modell und wird nicht gespeichert.
Quellen, Modell, Tool-Aufrufe und Sicherheit machen Antworten nachvollziehbar.
Das Frontend unter `frontend/` deckt den ganzen Demo-Ablauf ab:

- **Login** mit drei synthetischen Demo-Personas.
- **Lotse-Screen** mit Gesprächsliste, gestreamten Antworten, Dokument-Upload und „Mein Fall“ mit Kalender.
- **Ergebnis-Cards** für Zitate aus Dokumenten, vorausgefüllte Formulare, Stellen, Ärztinnen und Ärzte, Terminvorschläge, E-Mail-Entwürfe und Übergaben. Bei Beschwerden fragt die SAMPLER-Aufnahme Schritt für Schritt mit Auswahlantworten.
- **Transparenz-Panel** „Warum diese Antwort?“ mit Quellen, Werkzeugen, Modell und Sicherheit.
- **Notfall-Banner** mit 144 und 112 vor jedem KI-Text.
- Umschalter für die Antwortlänge und für helles oder dunkles Design.

Die Architektur umfasst vier Bausteine:

```text
[Next.js-Oberfläche] → [FastAPI: Agent und Tools]
                                         ↙         ↘
                         [eustella-LLM, EU]   [Postgres + pgvector]
```

Das Modell `eustella-v1.5` läuft in der EU.
Lokale Embeddings und deutsche Volltextsuche bilden ein hybrides RAG mit Reciprocal Rank Fusion.
Tools suchen Wissen und Stellen, bearbeiten Fallschritte, bereiten Formulare vor und eskalieren.
Ein regelbasierter Red-Flag-Check prüft Eingaben vor dem Modell.
Die Wissensbasis nutzt offizielle Quellen; die Demo verwendet synthetische Daten und öffentliche SV-Box-Dokumente.
Details stehen in [Produkt](docs/product.md), [Architektur](docs/architecture.md) und [Guardrails](docs/guardrails.md).

Die [Entscheidung D-014](docs/DECISIONS.md) ordnet den Lotsen als begrenztes Risiko mit Transparenzpflichten nach Art. 50 ein.
Der Lotse entscheidet keine Ansprüche und hat keine medizinische Funktion.
Eine automatische Anspruchsprüfung fiele laut D-014 unter Anhang III Nr. 5(a) und wäre Hochrisiko.
Diese Einordnung ist die Lesart des Teams und muss noch geprüft werden.

## Ausführung

Klonen Sie das Repository und wechseln Sie in dessen Verzeichnis.
Kopieren Sie die Vorlage. Sie startet die Offline-Demo mit `LLM_PROVIDER=replay`.
Ohne Eintrag in `.env` verwendet Compose ebenfalls `replay`.
Replay braucht keinen LLM-Schlüssel und spielt Aufzeichnungen aus `demo/fixtures/` ab.

```bash
cp .env.example .env
make run
```

Für den Live-Betrieb setzen Sie `LLM_PROVIDER=eustella` und Ihren Schlüssel unter `EUSTELLA_API_KEY` in `.env`.
Verwenden Sie ausschließlich synthetische Daten.
Compose startet PostgreSQL, das Backend und das Frontend.
Compose lädt die Demo-Daten nur in eine leere Datenbank.
Nach einer Änderung an `backend/seed/*.json` führen Sie bei laufendem Compose `make seed-reset` aus.
Achtung: `make seed-reset` löscht alle Demo-Gespräche.
Das Frontend startet erst, wenn das Backend gesund ist.
Öffnen Sie die App unter http://localhost:3000.
Das Backend ist unter http://localhost:8000 erreichbar.
Die API-Dokumentation steht unter http://localhost:8000/docs.

Achtung: Öffnen Sie die App über `localhost`, nicht über `127.0.0.1`.
Sonst sendet der Browser das Sitzungs-Cookie nicht an das Backend.

### Frontend lokal entwickeln

Starten Sie zuerst das Backend, zum Beispiel mit `make run`.
Installieren Sie die Abhängigkeiten und starten Sie den Entwicklungsserver:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Der Entwicklungsserver liest `NEXT_PUBLIC_API_URL` aus der `.env` im Wurzelverzeichnis.
Er übernimmt nur diesen Schlüssel; Backend-Schlüssel erreichen das Frontend nicht.
Der Server lauscht auf `PORT` aus der Shell, ohne Angabe auf Port 3000.
Wenn Compose das Frontend schon auf Port 3000 betreibt, wählen Sie einen freien Port.
Tragen Sie dann den Ursprung in `BACKEND_CORS_ORIGINS` ein und starten Sie das Backend neu:

```bash
PORT=3100 npm --prefix frontend run dev
```

Führen Sie die Frontend-Prüfungen aus:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:unit
npm --prefix frontend run test:transport
```

`test:unit` startet Vitest und läuft auch ohne Tests erfolgreich.
`test:transport` prüft den Transport unter `frontend/src/lib/transport/` mit `node:test`.
Vitest lässt diese Tests aus.

Headless-Worker nutzen `make frontend-setup` für die Installation und `make frontend-check` für Lint, Typprüfung und Build.
hackkit führt `make frontend-setup` vor neuen Tasks aus. Starten Sie laufende Worker nach einer Konfigurationsänderung neu.
Weitere Ziele: `frontend-unit`, `frontend-dev` und `frontend-browser`. Browser-Argumente übergeben Sie mit `ARGS`.

Der Demo-Check startet Playwright gegen das Frontend.
Er nutzt ein laufendes Frontend oder baut und startet selbst eines.
Das Backend muss laufen, für die Demo mit `LLM_PROVIDER=replay`.
Installieren Sie Chromium einmalig:

```bash
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run demo:check
```

Playwright nimmt `PORT` aus der Shell, sonst `FRONTEND_PORT` aus `.env`.
Die Tests liegen unter `frontend/e2e/`.
Mit `PLAYWRIGHT_CHANNEL=chrome` verwendet Playwright lokal den installierten Chrome. CI verwendet weiterhin das gebündelte Chromium.
Die Variable kann in `.env` oder in der Shell stehen.

### API-Typen erzeugen

Das Frontend nutzt Typen aus dem OpenAPI-Schema des Backends.
Dazu gehören die SSE-Ereignisse über `GET /api/_schema/events`.
Starten Sie das Backend und erzeugen Sie Schema und Typen:

```bash
make run
npm --prefix frontend run api:generate
```

Der Befehl lädt `${NEXT_PUBLIC_API_URL}/openapi.json`.
Er schreibt `frontend/src/lib/api/generated/openapi.json` und `schema.d.ts`.
Für eine andere Quelle führen Sie beide Schritte einzeln aus:

```bash
npm --prefix frontend run api:schema -- --url http://localhost:8000/openapi.json
npm --prefix frontend run api:types
```

Ohne laufendes Backend exportiert `make openapi` das Schema ohne Datenbank:

```bash
make -s openapi > frontend/src/lib/api/generated/openapi.json
npm --prefix frontend run api:types
```

Committen Sie beide Dateien nach jeder Änderung an den Backend-Schemas.
Bearbeiten Sie die erzeugten Dateien nicht von Hand.

Führen Sie die Backend-Tests aus:

```bash
make test
```

Führen Sie alle Evaluationssets aus:

```bash
make eval-all
```

Die Evaluation benötigt eine vorbereitete Datenbank und einen konfigurierten LLM-Provider.
Einzelne Voraussetzungen und Ergebnisse stehen in [docs/EVAL.md](docs/EVAL.md).

Für eine Aufzeichnung starten Sie das Backend mit `LLM_PROVIDER=eustella` und `LLM_RECORD=1`.
Das Backend benötigt einen gültigen Schlüssel und Schreibzugriff auf das Fixture-Verzeichnis.
Compose bindet dieses Verzeichnis nur lesend ein.
Starten Sie für die Prüfung das Backend mit `LLM_PROVIDER=replay`.
Führen Sie den jeweiligen Befehl gegen das laufende Backend aus:

```bash
make record-demo
make check-demo
```

## Abhängigkeiten und Voraussetzungen

- Docker mit Compose ab Version 2.24 und GNU Make für den Start.
- Python 3.12 und uv für lokale Entwicklung, Tests und Evaluation.
- FastAPI, SQLAlchemy, asyncpg und PostgreSQL mit pgvector für Backend und Datenbank.
- OpenAI SDK, fastembed, PyMuPDF und pypdf für Modellzugriff, Embeddings, Dokumente und Formulare.
- Tesseract mit den Sprachdaten `deu` und `eng` für die Texterkennung. Das Backend-Image enthält beides.
  Für lokale Tests installieren Sie unter Debian oder Ubuntu `tesseract-ocr`, `tesseract-ocr-deu` und `tesseract-ocr-eng`.
- rapidfuzz für die tolerante Zitatprüfung bei OCR-Text.
- pytest und ruff für Tests und statische Prüfungen.

Die Abhängigkeiten stehen in `backend/pyproject.toml`; `backend/uv.lock` fixiert die Versionen.

Für das Frontend gilt:

- Node.js ab 22.12 und npm für lokale Entwicklung und Prüfungen. Compose braucht beides nicht.
- Next.js (App Router), React, TypeScript und Tailwind CSS für die Oberfläche.
- Grundlagen für shadcn/ui (Radix UI, class-variance-authority, clsx, tailwind-merge), lucide-react, framer-motion und react-markdown.
- Vitest mit Testing Library für Unit-Tests, Playwright für den Demo-Check.
- openapi-typescript für die API-Typen.

Die Abhängigkeiten stehen in `frontend/package.json`; `frontend/package-lock.json` fixiert die Versionen.
Die App lädt zur Laufzeit keine Schriften aus dem Netz und läuft mit `LLM_PROVIDER=replay` offline.

## Konfiguration

Die Tabelle zeigt die Werte aus `.env.example`.
Ersetzen Sie Platzhalter für Schlüssel und Passwörter vor einem Einsatz.
Umgebungsvariablen haben Vorrang vor `.env`.

| Variable | Bedeutung | Vorgabe in `.env.example` |
|---|---|---|
| `APP_ENV` | Betriebsmodus | `development` |
| `LOG_LEVEL` | Protokollstufe | `INFO` |
| `SECRET_KEY` | Signatur der Sitzungs-Cookies | `change-me` |
| `LLM_PROVIDER` | Anbieter: `eustella`, `azure`, `fake` oder `replay` | `replay` |
| `LLM_RECORD` | Live-Antworten aufzeichnen | `false` |
| `LLM_FIXTURES_DIR` | Verzeichnis der Aufzeichnungen | `demo/fixtures` |
| `EUSTELLA_API_KEY` | eustella-Schlüssel | `rk_your_key_here` |
| `EUSTELLA_BASE_URL` | eustella-API-Adresse | `https://api.eustella.com/v1` |
| `EUSTELLA_MODEL` | eustella-Modell | `eustella-v1.5` |
| `LLM_MAX_TOKENS` | Maximale Antwortlänge in Tokens | `4096` |
| `LLM_ENABLE_THINKING` | Denkmodus für Chat-Turns | `false` |
| `DOCUMENT_EXTRACTION_THINKING` | Denkmodus für Textextraktion | `false` |
| `LLM_TIMEOUT_SECONDS` | Zeitlimit für Modellaufrufe in Sekunden | `120` |
| `LLM_MAX_RETRIES` | Wiederholungen bei 429 oder 503 | `2` |
| `LLM_MAX_CONCURRENCY` | Maximale parallele Modellaufrufe | `2` |
| `LLM_MAX_TOOL_ROUNDS` | Maximale Tool-Runden pro Turn | `3` |
| `AZURE_OPENAI_BASE_URL` | Azure-API-Adresse | `https://your-endpoint.services.ai.azure.com/openai/v1` |
| `AZURE_OPENAI_API_KEY` | Azure-Schlüssel | `your_azure_key_here` |
| `AZURE_OPENAI_MODEL` | Azure-Modell | `gpt-5-4-mini` |
| `AZURE_REASONING_EFFORT` | Azure-Reasoning-Stufe | `low` |
| `GUARDRAIL_OUTPUT_CHECK` | Zusätzliche Modellprüfung der Ausgabe | `false` |
| `EMBEDDING_MODEL` | Lokales Embedding-Modell | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `EMBEDDING_DIM` | Dimension der Embeddings | `384` |
| `EMBEDDING_CACHE_DIR` | Cache-Verzeichnis für das Embedding-Modell | `/models` |
| `RAG_TOP_K` | Anzahl der Suchtreffer | `5` |
| `POSTGRES_USER` | PostgreSQL-Benutzer | `lotse` |
| `POSTGRES_PASSWORD` | PostgreSQL-Passwort | `change-me` |
| `POSTGRES_DB` | PostgreSQL-Datenbank | `lotse` |
| `POSTGRES_HOST` | PostgreSQL-Host | `db` |
| `POSTGRES_PORT` | PostgreSQL-Port | `5432` |
| `DATABASE_URL` | Async-Datenbankverbindung | `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}` |
| `BACKEND_PORT` | Backend-Port für Compose | `8000` |
| `PORT` | Port-Vorrang beim nativen Backend-Start | `8000` |
| `BACKEND_CORS_ORIGINS` | Erlaubte Browser-Ursprünge, muss den Frontend-Ursprung enthalten | `http://localhost:3000` |
| `UPLOAD_DIR` | Verzeichnis für Uploads | `/data/uploads` |
| `MAX_UPLOAD_MB` | Maximale Upload-Größe in MB | `10` |
| `OCR_ENABLED` | Lokale Texterkennung für Scans und Fotos | `true` |
| `OCR_LANGUAGES` | Tesseract-Sprachen, mit `+` verbunden | `deu+eng` |
| `OCR_TESSDATA_DIR` | Tesseract-Sprachordner, leer für automatische Suche | leer |
| `OCR_TIMEOUT_SECONDS` | Zeitlimit für die Texterkennung in Sekunden | `60` |
| `OCR_QUOTE_MIN_SIMILARITY` | Mindestähnlichkeit (0–100) für Zitate aus OCR-Text | `90` |
| `FRONTEND_PORT` | Frontend-Port für Compose und Playwright | `3000` |
| `NEXT_PUBLIC_API_URL` | Backend-Adresse, wie der Browser sie aufruft | `http://localhost:8000` |
| `NEXT_PUBLIC_API_TIMEOUT_MS` | Timeout pro REST-Anfrage und bis zu den Stream-Headern in ms | `15000` |
| `NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS` | Längste Pause zwischen zwei SSE-Chunks in ms, über `LLM_TIMEOUT_SECONDS` | `130000` |
| `PLAYWRIGHT_CHANNEL` | Optionaler lokaler Browser für Playwright, zum Beispiel `chrome` | leer |
| `RUN_LIVE` | `1` führt Dokumenttests gegen das Live-Modell aus | leer |
| `RUN_SLOW` | `1` führt langsame RAG-Tests aus | leer |

Compose setzt im Backend `PORT` auf `BACKEND_PORT` und verwendet `/app/demo/fixtures` für Aufzeichnungen.
Ohne `BACKEND_CORS_ORIGINS` erlaubt Compose den Ursprung `http://localhost:${FRONTEND_PORT}`.
Im Frontend-Container setzt Compose `PORT` auf `FRONTEND_PORT`.
Das Frontend liest alle Einstellungen in `frontend/src/lib/config.ts`.

Achtung: Jeder Wert mit dem Präfix `NEXT_PUBLIC_` landet im Browser. Tragen Sie dort nie Schlüssel ein.
Next.js schreibt alle `NEXT_PUBLIC_*`-Werte beim Build fest in das Frontend.
Ohne Angabe gelten für die beiden Timeouts die Standardwerte aus `frontend/src/lib/config.ts`.
Nach einer Änderung bauen Sie das Frontend neu; `make run` baut bei jedem Start neu.
Das Frontend nutzt `PORT` nur aus der Shell. Den Wert `PORT` aus `.env` liest nur das Backend.

## Bekannte Einschränkungen und offene Punkte

- Versicherungsstatus, Termine, nichtärztliche Anbieter und E-Mail sind Mocks mit der Kennzeichnung „Demo-Daten“.
- Die SV-Datenabfrage ist simuliert (D-041). `MockSvDataService` liest synthetische SV-Nummern aus `backend/seed/sv_register.json`. Eine echte Schnittstelle steht uns nicht zur Verfügung. Ein Echtbetrieb braucht eine Rechtsgrundlage und die Einwilligung der Person. Nach dem Update legt `make seed-reset` die Profile neu an.
- Stellen und Formulare decken zunächst Wien ab.
- Die Ärzteliste der Stadt Wien nennt keinen Kassenvertrag und keine Öffnungszeiten. Viele Einträge haben keine Telefonnummer. `cd backend && uv run python -m scripts.fetch_vienna_doctors` lädt die Liste neu.
- Die Standortabfrage braucht HTTPS oder `localhost`. Ohne Freigabe rechnet der Lotse ab dem Mittelpunkt des Bezirks.
- Der Lotse trägt keine Kalendertermine selbst ein; die Person speichert sie. Die Demo-Termine liegen relativ zum Seed-Tag. Nach einigen Tagen legt `make seed-reset` sie neu an.
- Der Lotse füllt drei Formulare vor: Pflegegeld (PVA), Kur und Reha sowie Fahrtkostenzuschuss (ÖGK). Ein Mensch muss die Feldzuordnungen noch prüfen.
- eustella ist eine Closed Beta mit zwei parallelen Aufrufen und 20 Anfragen pro Minute.
- Der Red-Flag-Check nutzt Schlüsselwörter und kann Fehlalarme auslösen.
- Bei Live-Läufen begann eine Ablehnung selten auf Englisch.
- Das Modell kann `prepare_form` zweimal aufrufen.
- Die Dokument-Extraktion dauerte in einer Messung rund 10 Sekunden.
- Bei Scans und Fotos liest Tesseract den Text, im Container rund 2 Sekunden pro Seite.
  Die Zitatprüfung toleriert dann kleine Erkennungsfehler und kann ein fast wörtliches Zitat zulassen.
  Liefert die Texterkennung zu wenig Text, liest das Vision-Modell die Bilder. Diese Zitate prüft niemand automatisch.
- Die Suche findet zu englischen Fragen deutsche Quellen nur über Embeddings. Die deutsche Volltextsuche greift dort nicht.
- Die letzten dokumentierten Retrieval- und Guardrail-Läufe verfehlten ihre Ziele; Details stehen in [docs/EVAL.md](docs/EVAL.md).
- D-013 streicht S4, PWA, Spracheingabe, Einfache Sprache, das FSW-Formular und den Erstattungskodex. Das Fahrtkostenformular kam später doch dazu.
- Der Plan streicht auch die Ausgabeprüfung durch einen zweiten LLM-Aufruf.
- Das helle Design ist für den Beamer gedacht. Das dunkle Design vor einer Vorführung auf dem Beamer prüfen.
- Die Backend-Adresse steht nach dem Build fest im Frontend-Bundle. Eine Änderung braucht einen neuen Build.

Weitere Details stehen im [Plan](docs/PLAN.md), in den [Entscheidungen](docs/DECISIONS.md) und im [eustella-Smoke-Test](docs/smoke-eustella.md).

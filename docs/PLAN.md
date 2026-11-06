# Produktplan — SV KI-Lotse

Jeder Agent liest diese Datei vor jedem Task. Sie fasst den Plan zusammen und verweist auf die Detaildokumente.
Bei einem Widerspruch gilt diese Datei vor den Detaildokumenten.

| Detail | Datei |
|---|---|
| Produkt, Personas, Szenarien S1–S5 | [product.md](product.md) |
| Medizinische Grenze, Eskalation, Guardrail-Tests | [guardrails.md](guardrails.md) |
| Systemaufbau, Agent-Turn, RAG, Dokumente, Formulare | [architecture.md](architecture.md) |
| REST, SSE-Events, Cards, DB-Schema, Tools, Extraktionsschema | [contracts.md](contracts.md) |
| Datenquellen, Seed-Dateien, KB-Format | [data.md](data.md) |
| eustella-API, Limits, Fallen | [eustella-api.md](eustella-api.md) |
| Demo-Skript | [PITCH.md](PITCH.md) |
| Designsystem | [DESIGN.md](DESIGN.md) |
| Entscheidungen | [DECISIONS.md](DECISIONS.md) |
| Eval-Ergebnisse | [EVAL.md](EVAL.md) |

`workstreams.md` ist überholt. Die hackkit-Tasks ersetzen die Workstreams. Jeder Task nennt seine Dateien.

## Use Case

Use Case 1 „SV KI-Lotse“ (`KI-Challenge_UseCase.yaml` → `uc1`). Ein Navigator durch das österreichische Sozialversicherungssystem. Die Veranstalter fordern ausdrücklich „kein klassischer Chatbot“.

## Problem und Nutzer

- **Wer:** Versicherte und pflegende Angehörige. Beispiel: Maria Berger (52) organisiert Hilfe für ihre Mutter nach dem Spitalsaufenthalt.
- **Situation:** Mehrere Themen treffen gleichzeitig ein: Entlassung, Pflegebedarf, Reha, Kosten. Die Person kennt weder Leistung noch Stelle noch Formular.
- **Kosten heute:** Viele Anrufe, falsche Stellen, unvollständige Anträge, Wochen bis zur ersten Leistung. Konkrete Zahlen mit Quelle liefert Task T8. Wir erfinden keine Zahlen.

## Wertversprechen

Der Lotse macht aus einer Alltagsbeschreibung einen Fall mit konkreten Schritten: passende Leistungen, vorausgefülltes Formular, zuständige Stelle und einen Menschen, wenn die KI aufhören muss.

## Demo-Ablauf

Das Klick-für-Klick-Skript steht in [PITCH.md](PITCH.md). Kurzfassung:
1. S1: Maria meldet sich an, beschreibt die Lage, lädt den Entlassungsbefund hoch. Der Lotse zitiert die Empfehlungen, füllt „Mein Fall“, füllt den PVA-Pflegegeldantrag vor und zeigt die zuständigen Stellen.
2. S2: Maria fragt nach der Dosis eines Medikaments. Der Lotse lehnt ab und eskaliert mit Übergabezusammenfassung.
3. S3: „Meine Mutter hat plötzlich starke Atemnot.“ Der Notfall-Banner mit 144 erscheint vor jeder LLM-Ausgabe.
4. „Warum diese Antwort?“ zeigt Quellen, Tool-Aufrufe, Modell und Sicherheit.
5. Optional S5: Elif schreibt Englisch, der Lotse antwortet Englisch.

## Features

Scope-Entscheidung D-013: Variante A.

| Feature | Priorität | Demo-Schritt |
|---|---|---|
| Persona-Login (Maria, Stefan, Elif) | must | S1.1 |
| Chat mit gestreamter Antwort und Fortschrittszeile | must | S1.1 |
| Administrative Rückfragen (max. 2 pro Antwort) | must | S1.2 |
| Dokument-Upload (PDF, Foto) mit Extraktion und wörtlichen Zitaten | must | S1.3 |
| Leistungs-Bündel als Leistungs-Cards | must | S1.4 |
| Mein Fall (Schritte, abhaken, bleibt gespeichert) | must | S1.5 |
| PVA-Pflegegeldantrag vorausfüllen, PDF-Download, fehlende Felder markiert | must | S1.6 |
| Zuständige Stelle (Office-Card, echte öffentliche Stellen Wien) | must | S1.7 |
| Quellen an jeder Antwort | must | S1.4 |
| „Warum diese Antwort?“-Panel (Quellen, Tools, Modell, Sicherheit) | must | S1.8 |
| Eskalation mit Übergabezusammenfassung (`escalate`-Tool, Card) | must | S2 |
| Deterministischer Red-Flag-Check vor dem LLM, Notfall-Banner | must | S3 |
| KI-Hinweis (Art. 50 AI Act) und menschliche Bestätigung im UI | must | alle |
| Replay-Modus für die Offline-Demo | must | alle |
| Sprache Englisch (S5) | should | S5 |
| Pflegeberatungstermin (Demo-Daten) mit `.ics`-Download | should | S1.7 |
| Kur-und-Reha-Antrag vorausfüllen | should | S1.6 |
| E-Mail-Entwurf (`draft_email`) | should | S1.7 |
| Einstellungen Tiefe kurz/ausführlich | should | — |
| S4 Gesundheitsförderung (Stefan) | cut | — |
| Einfache Sprache | cut | — |
| PWA, Offline-Shell, Spracheingabe | cut | — |
| Fahrtkostenzuschuss-Formular vorausfüllen (D-038) | should | S1.6 |
| FSW-Förderantrag | cut | — |
| Erstattungskodex-Abfrage | cut | — |
| Output-Check per zweitem LLM-Call | cut | — |

Mobile Ansicht: Das Layout darf auf Handybreite nicht brechen. Wir polieren nur 1440×900 und 1920×1080.

## Daten

- **SV-Box (öffentlich, darf ins Repo):** Der Manager kopiert die genutzten Dateien nach `backend/seed/`:
  - `backend/seed/documents/entlassungsbefund.pdf` (Golden Path, Anna Berger)
  - `backend/seed/documents/impfpass.pdf`, `roentgen_befund.pdf` (Guardrail-Tests)
  - `backend/seed/forms/pdf/pva_pflegegeld.pdf` (`PAL080_0125_Mpfl_052026.pdf`)
  - `backend/seed/forms/pdf/kur_reha.pdf` (`Antrag Kur und Reha.pdf`)
  - `backend/seed/sources/serviceratgeber_2026.pdf` (KB-Quelle)
- **Wissensbasis:** ca. 25 Markdown-Dateien in `backend/seed/kb/<kategorie>/`, Format nach [data.md](data.md) §3. Kategorien `pflege`, `reha`, `kosten`, `organisation`, `kind`. Jede Datei hat eine offizielle `source_url`. Ein Mensch prüft Beträge, Stunden und Fristen.
- **Strukturiert:** `leistungen.json` (ca. 12 Leistungen), `offices.json` (echte öffentliche Stellen Wien), `escalation_contacts.json` (Hotlines, jede Nummer mit Quelle).
- **Synthetisch:** `personas.json` (3 Personas, [data.md](data.md) §5), `providers.json` (erfundene Ärztinnen und Dienste, `demo: true`), Terminslots (generiert).
- **Keine echten Personendaten.** Anna Berger ist die synthetische Patientin der SV-Box.

## KI-Ansatz

- **Modell:** `eustella-v1.5` (EU, Wien) über die OpenAI-kompatible API. Fallback: Azure OpenAI der Veranstalter (`gpt-5-4-mini`). Umschalten nur über `LLM_PROVIDER` in `.env`.
- **Provider im LLM-Client** (`backend/app/llm/client.py`):
  - `eustella`, `azure`: Live-Modelle.
  - `fake`: geskriptete Antworten für Unit-Tests und UI-Entwicklung.
  - `replay`: spielt aufgezeichnete LLM-Antworten aus `demo/fixtures/` ab. Der Schlüssel ist ein Hash der normalisierten Anfrage (UUIDs, Datum und Uhrzeit ersetzt). Bei einem Treffer-Fehler fällt der Client auf `fake` zurück und loggt eine Warnung.
  - `LLM_RECORD=1`: zeichnet echte Antworten nach `demo/fixtures/` auf. Nach jeder Prompt-Änderung neu aufzeichnen.
- **Agent-Turn:** Red-Flag-Check → Retrieval → Kontext → gestreamte Antwort mit Tools → max. 3 Tool-Runden. Details: [architecture.md](architecture.md) §4.
- **Tools:** [contracts.md](contracts.md) §4. `get_insurance_status` und `update_profile` sind cut.
- **Simulierte SV-Datenabfrage (D-041):** `MockSvDataService` neben den Mocks für Ärzteverzeichnis und Termine (D-010). Der Seed füllt Bundesland, PLZ, Versicherungsträger und Geburtsdatum aus der synthetischen SV-Nummer. Das Benutzermenü zeigt die Daten als „Demo-Daten“. Kein LLM-Tool: `get_insurance_status` bleibt cut, SV-Nummer, Name und Adresse gehen nicht an das Modell.
- **Retrieval:** lokale Embeddings (fastembed, `paraphrase-multilingual-MiniLM-L12-v2`) plus deutsche Volltextsuche in Postgres, gemischt mit Reciprocal Rank Fusion.
- **Dokumente:** PyMuPDF-Text, sonst Seitenbild an das Vision-Modell. Extraktion mit `json_schema` ([contracts.md](contracts.md) §5). Nur wörtliche Zitate, keine Diagnosen.
- **Prompts:** `backend/app/llm/prompts/system.md`, `document_extraction.md`. Jede Prompt-Version steht in `docs/EVAL.md`.
- **Timeouts:** Jeder externe Aufruf hat einen Timeout (`LLM_TIMEOUT_SECONDS`). Fehler erscheinen als lesbare deutsche Meldung mit „Erneut versuchen“.

## Qualität

Eval-Sets in `eval/`, Ergebnisse in `docs/EVAL.md` (Entscheidung D-015).

| Set | Datei | Umfang | Metrik | Ziel |
|---|---|---|---|---|
| Red-Flag-Check | `eval/red_flags.jsonl` | 20 positiv, 20 negativ | Recall, Falsch-positiv-Rate | 100 %, ≤ 10 % |
| Guardrails live | `eval/guardrails.jsonl` | 12 Prompts aus [guardrails.md](guardrails.md) §5 | korrekt behandelt | ≥ 11/12, alle Notfälle korrekt |
| Dokument-Extraktion | `eval/extraction_expected.json` | Entlassungsbefund, 5 Empfehlungen | gefunden, Zitat wörtlich im PDF | 5/5, 100 % |
| Retrieval | `eval/retrieval.jsonl` | 20 Fragen mit erwarteter KB-Datei | Treffer in Top 5 | ≥ 85 % |

`uv run python -m eval.run --set <name>` führt ein Set aus und schreibt eine Zeile in `docs/EVAL.md`.

## Verantwortungsvoller KI-Einsatz

- **AI-Act-Risikoklasse:** begrenztes Risiko, Transparenzpflichten nach Art. 50 (D-014). Begründung: Der Lotse entscheidet nicht über Ansprüche und hat keine medizinische Funktion. Grenze: Eine automatische Anspruchsprüfung fiele unter Anhang III Nr. 5(a) und wäre Hochrisiko. Wir prüfen diese Einordnung in der Fragestunde.
- **Transparenz:** Jede Antwort zeigt Quellen (Titel, Herausgeber, Link oder Dokument und Abschnitt), Modellname und einen Sicherheitshinweis mit Label und Farbe. Das UI kennzeichnet den Lotsen als KI.
- **Mensch entscheidet:** Der Lotse sagt „könnte in Frage kommen, die Stelle entscheidet“. Die Nutzerin prüft und sendet jedes Formular und jede E-Mail selbst. Das UI zeigt den Schritt „Von Ihnen zu prüfen“.
- **Medizinische Grenze und Eskalation:** [guardrails.md](guardrails.md). Nicht verhandelbar.
- **Datenschutz:** nur synthetische Personas und SV-Box-Daten. Das Audit-Log speichert keine Dokumentinhalte. Embeddings laufen lokal. Das LLM läuft in der EU.
- **Grenzen:** Mocks für SV-Datenabfrage, Versicherungsstatus, Ärzteverzeichnis und Termine (Label „Demo-Daten“). Nur Wien. eustella ist eine Closed Beta.

## Architektur und Stack

```
Browser (Next.js) ──REST/SSE──► Backend (FastAPI) ──► LLM (eustella | azure | fake | replay)
                                     │
                                     ├─► Tools, Guardrails, Formulare (pypdf), Dokumente (PyMuPDF)
                                     └─► Postgres 16 + pgvector (Daten, KB-Chunks, Audit)
```

- **Backend:** Python 3.12, uv, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, pydantic-settings, openai SDK, fastembed, pgvector, PyMuPDF, pypdf, pytest, ruff.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, shadcn/ui, lucide-react, framer-motion, react-markdown, openapi-typescript, Playwright.
- **Konfiguration:** Alle Einstellungen in `.env`, dokumentiert in `.env.example`. Das Backend liest sie nur in `backend/app/config.py`. Neue Variablen: `LLM_RECORD`, `LLM_FIXTURES_DIR=demo/fixtures`.
- **Ausführen:** `make run` = `docker compose up --build`. App auf `http://localhost:3000`, API-Doku auf `http://localhost:8000/docs`.
- **Betrieb:** keine öffentliche URL (D-016). Die Demo läuft auf Jonathans Laptop. Fallback: zweiter Laptop mit `make run` und `LLM_PROVIDER=replay`, plus Backup-Video.
- **Worktrees:** `.env` liegt nur im Haupt-Checkout. Tests laufen ohne `.env` mit `LLM_PROVIDER=fake`. Skripte, die einen Key brauchen, suchen `.env` im Haupt-Checkout (`git rev-parse --git-common-dir`, dann eine Ebene höher).

## Screens

| Screen | Route | Inhalt |
|---|---|---|
| Login | `/login` | Produktname, KI-Hinweis, drei Persona-Karten mit Kurzbeschreibung. |
| Lotse | `/chat/[id]` | Links Chat (Nachrichten, Cards, Quellen-Chips, Eingabe mit Upload). Rechts „Mein Fall“ (Fallzusammenfassung, Schritte mit Status). Oben Notfall-Banner bei Red Flag. |
| Warum diese Antwort? | Drawer im Lotse-Screen | Quellen, Tool-Aufrufe, Modell, Sicherheit, Eskalationsgrund. |
| Styleguide | `/styleguide` | Tokens und Komponenten (nur intern). |

Primäraktion im Lotse-Screen: Nachricht senden. Das KI-Ergebnis (Antwort und Cards) ist das größte Element.

## Risiken und offene Fragen

| Risiko | Gegenmaßnahme |
|---|---|
| eustella fällt aus oder limitiert (2 parallel, 20 rpm) | Azure-Fallback, Replay-Modus, Retries, nur `fake` in Tests |
| Tools, Vision oder `json_schema` funktionieren bei eustella nicht | Smoke-Test T3 zuerst. Sonst Azure als Primärmodell. |
| Replay-Hash trifft nicht, weil der Kontext dynamische Werte hat | Normalisierung von UUIDs und Datum. Demo-Check läuft mit `replay`. |
| Scope zu groß für 19 h | Scope A, harte Cuts oben |
| Falsche Fakten in der KB | Quelle je Datei, Mensch prüft Zahlen, „Offene Punkte“ je Datei |

Fragen für die Fragestunde (17:00):
1. Stimmen Sie der Einordnung „begrenztes Risiko, Art. 50“ zu?
2. Ist ein externes EU-LLM (eustella) erlaubt, oder soll es der Azure-Endpunkt sein? Gibt es höhere Limits?
3. Ist der Entlassungsbefund vollständig synthetisch? Dürfen wir ihn auf dem Beamer zeigen?
4. Ist Pflegegeld über die PVA ein guter Golden Path aus Ihrer Sicht?
5. Gibt es Zahlen zu Anrufaufkommen oder Bearbeitungszeit bei Pflegegeld und Reha?
6. Genügt eine Demo vom Laptop, oder erwartet die Jury eine URL?
7. Was muss bis wann im öffentlichen Abgabe-Repo liegen?

## Meilensteine

| Bis | Meilenstein | Inhalt |
|---|---|---|
| Do 16:30 | M0 Fundament | Backend-Scaffold auf `main`, Smoke-Test-Ergebnis, KB-Arbeit läuft |
| Do 17:00 | Fragestunde | Fragen oben |
| Do 20:00 | M1 Vertical Slice | Backend: Login → SSE-Stream von eustella → ein Schritt in „Mein Fall“, geprüft per API-Test. Frontend nach Freigabe. |
| Fr 01:00 | M2 Must | S1, S2, S3 komplett, Transparenz-Panel, Eval-Sets laufen, Demo-Check grün für gebaute Schritte |
| Fr 06:00 | M3 Should | S5, `.ics`, Kur-und-Reha, `ui-polish`, Replay-Fixtures aufgezeichnet |
| Fr 08:00 | Feature Freeze | README, DECISIONS, `hackkit check`, Demo-Check mit `LLM_PROVIDER=replay` |
| Fr 09:00 | Probe | zweimal 15 Minuten, Backup-Video |
| Fr 10:00 | Fachjury | |

## Arbeitsaufteilung

Headless-Worker führen Befehle nur über `make`-Ziele aus (AGENTS.md). Runde 1 startet sofort. Runde 2 startet nach dem Merge von T1. Frontend-Tasks warten auf die Freigabe durch Jonathan (D-018). „P“ = parallel zu den anderen Tasks der Runde.

| Task | Agent | Dateien | Test | Runde |
|---|---|---|---|---|
| T1 Backend-Scaffold, Compose (nur `db` und `backend`), `make run` | codex | `docker-compose.yml`, `Makefile`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `backend/alembic.ini`, `backend/alembic/**`, `backend/app/{__init__,main,config,db}.py`, `backend/app/api/{__init__,health}.py`, `backend/tests/{conftest,test_health}.py`, `.env.example` | `cd backend && uv run pytest -q` | 1 P |
| T3 eustella-Smoke-Test | agy | `backend/scripts/smoke_eustella.py`, `docs/smoke-eustella.md` | `uv run backend/scripts/smoke_eustella.py` | 1 P |
| T4 KB Pflege und Reha | agy | `backend/seed/kb/pflege/**`, `backend/seed/kb/reha/**` | Front-Matter-Check (Task-Body) | 1 P |
| T5 KB Kosten, Organisation, Kind | agy | `backend/seed/kb/kosten/**`, `backend/seed/kb/organisation/**`, `backend/seed/kb/kind/**` | Front-Matter-Check | 1 P |
| T6 Leistungen, Stellen, Notfallkontakte | agy | `backend/seed/leistungen.json`, `backend/seed/offices.json`, `backend/seed/escalation_contacts.json` | JSON-Check | 1 P |
| T7 Eval-Sets Red Flags, Guardrails, Extraktion | claude | `eval/red_flags.jsonl`, `eval/guardrails.jsonl`, `eval/extraction_expected.json` | JSONL-Check | 1 P |
| T8 Problemzahlen mit Quellen | agy | `docs/research/problemzahlen.md` | Datei hat ≥ 3 Zahlen mit URL | 1 P |
| T10 DB-Modelle, Migration, Seeding, Test-DB-Fixture | codex | `backend/app/models/**`, `backend/alembic/versions/**`, `backend/app/seed.py`, `backend/seed/{personas,providers}.json`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/tests/conftest.py`, `backend/tests/test_models.py` | `cd backend && uv run pytest -q tests/test_models.py` | 2 P |
| T15 Persona-Login, `/api/me` | codex | `backend/app/api/auth.py`, `backend/app/deps.py`, `backend/app/schemas/auth.py`, `backend/tests/test_auth.py` | `cd backend && uv run pytest -q tests/test_auth.py` | 2 (nach T10) |
| T11 LLM-Client mit fake, replay, record | claude | `backend/app/llm/{__init__,client,fake,replay}.py`, `backend/tests/test_llm_client.py`, `demo/fixtures/.gitkeep` | `cd backend && uv run pytest -q tests/test_llm_client.py` | 2 P |
| T12 Red-Flag-Check und Eskalationskontakte | agy | `backend/app/guardrails/**`, `backend/tests/test_red_flags.py` | `cd backend && uv run pytest -q tests/test_red_flags.py` | 2 P |
| T13 Pflegegeld-Formular füllen | claude | `backend/app/forms/**`, `backend/seed/forms/{registry.json,field_maps/**}`, `backend/tests/test_forms.py` | `cd backend && uv run pytest -q tests/test_forms.py` | 2 P |

Frontend (gesperrt bis zur Freigabe): T2 Frontend-Scaffold (claude, `frontend/**`), T9 Designsystem und App-Shell (claude), T14 Demo-Check-Gerüst (agy), Chat-Screen und „Mein Fall“ (claude), Cards (claude), Transparenz-Panel (claude).

Runde 3 (läuft): T11b LLM-Client-Härtung (codex), T15 Persona-Login (claude), T16 Orchestrator-Kern (claude), T17 RAG (claude), T18 Dokument-Pipeline (claude), T20 Retrieval-Eval-Set (claude). Danach: Konversations- und Fall-API mit SSE-Route, restliche Tools (Leistung, Stelle, Formular, Wissenssuche, Dokument, Eskalation), Dokument-Upload-Route, Audit-API, Eval-Runner.

agy ist seit D-019 nicht mehr im Einsatz. Nur claude und codex bekommen Tasks.

## Frontend-Freigabe und aktuelle Runden

Jonathan hat das Frontend am 05.11.2026 freigegeben. Diese Runden ersetzen die frühere Frontend-Sperre und Arbeitsaufteilung.
Mehrere Claude-Worker pro Laptop arbeiten über hackkit. Drei Laptops begrenzen nicht die Anzahl gleichzeitiger Tasks.
Codex übernimmt das Management. agy bekommt keine Tasks.
Die Skizzen bestimmen Navigation und Antwortzustände. Claude bestimmt die visuelle Gestaltung mit den UI-Skills.
Persona-Login bleibt. ID Austria gehört nicht zum Scope. Ein einfacher Kalender unter „Mein Fall“ ist seit D-039 Teil des Umfangs.

1. Sofort parallel: Fabian erstellt Scaffold und Startintegration (#40). Jonathan implementiert unabhängigen REST-/SSE-Transport (#41).
   Gjergj definiert die Designrichtung und Demo-Interaktionen in docs/DESIGN.md (#42).
   Der Transport liegt exklusiv unter frontend/src/lib/transport/. Er braucht weder Scaffold noch generierte Typen zum Testen.
2. Nach dem Scaffold-Merge: Gjergj implementiert Designsystem und App-Shell. Ein freier Claude erstellt das Playwright-Demo-Gerüst.
   Ein weiterer Claude verbindet den Transport mit generierten API-Typen. Die Tasks bekommen getrennte Dateibereiche.
3. Nach dem Designsystem-Merge: Gjergj erstellt Login und Chat. Jonathan erstellt „Mein Fall“. Fabian erstellt die Cards.
4. Weitere kleine Tasks ergänzen Upload, Transparenz und Seitenintegration. Jeder Task dauert 15–40 Minuten.
5. Nach jeder UI-Mergerunde folgt ein ui-polish-Task. Der Manager prüft den Demo-Check auf aktuellem main.

Nach dem Designsystem-Merge können Login, Chat, Mein Fall, Cards, Upload, Transparenz und Demo-Tests getrennte Tasks bilden.
Der Manager vergibt alle unabhängigen Tasks gleichzeitig. Nur echte Abhängigkeiten und gemeinsame Dateien begrenzen die Parallelität.

Aktueller Stand: Transport und Designentwurf sind gemergt. Der Manager integriert den reparierten Scaffold aus Task #44.
Danach starten Designsystem, typisierte API-Anbindung und Demo-Check parallel. Feature-Screens warten nur auf den Designsystem-Merge.
Während das Designsystem entsteht, können reine Gesprächs- und Upload-Controller ohne UI-Code parallel starten.
Diese Controller verwenden die gemergte API-Fassade. Sie ändern weder Seiten noch gemeinsame UI-Komponenten.

### Aktuelle Frontend-Runde nach PR #34

Gjergjs Umsetzung ist das gemeinsame Designsystem. PR #34 ersetzt die erste Umsetzung aus PR #33.
API-Fassade und Demo-Check sind gemergt. Feature-UI ist freigegeben.
Tasks #49 bis #57 können parallel laufen. Jeder Task besitzt getrennte Dateien.
Seit D-031 laufen #49 bis #57 parallel mit Codex auf Jonathans Laptop. Claude prüft und merged.

| Task | Ergebnis |
|---|---|
| #49 | Gesprächs-Controller ohne UI |
| #50 | Upload-Controller ohne UI |
| #51 | Gemeinsame UI-Prüfung und Tastatur-Regressionsprüfung |
| #52 | Persona-Login und Persona-Menü |
| #53 | Gesprächsansicht, Eingabe und Notfall-Banner |
| #54 | Mein Fall |
| #55 | Ergebnis-Cards |
| #56 | Anhang-Auswahl und Upload-Zustände |
| #57 | Antwort-Metadaten und Transparenz-Panel |

Feature-Tasks liefern eigene Styleguide-Vorschauen. Ein folgender Task verbindet ihre Exporte mit den echten Seiten.
Der Seiten-Task verbindet auch die Controller. Kein Feature-Task kopiert die Logik eines anderen Tasks.

Jeder Task nennt getrennte Dateibereiche und einen schnellen Test. Nur ein Task besitzt gemeinsame Konfigurationsdateien.
Feature-Tasks starten erst nach dem Designsystem-Merge. Ungebaute Demo-Schritte bleiben test.fixme.
S1, S2 und S3 haben Vorrang. S5 und Terminkarten bleiben optional.

### Offen nach der Runde „E-Mail-Entwurf“ (2026-11-06)

Gebaut: E-Mail-Entwurf-Card (bearbeitbar, „In E-Mail-Programm öffnen“, „Text kopieren“) und die E-Mail an die nächste Hausärztin, auch mit den SAMPLER-Angaben.
Noch offen, für eine spätere Runde:

| Punkt | Stand heute |
|---|---|
| Anbieter-Card „Anbieter in Ihrer Nähe“ | Gebaut (2026-11-06): nächster zuerst, Entfernung, Anruf, „Termin vorschlagen“ und „E-Mail entwerfen“ als Chat-Nachricht. |
| Termin-Card mit „Zum Kalender hinzufügen“ | Gebaut (2026-11-06): Datum und Uhrzeit in Wiener Zeit, `.ics`-Download, Anruf, Hinweis „keine Buchung“. |
| E-Mail-Adressen der Demo-Anbieter | Die 12 Demo-Anbieter haben keine Adresse. Die Person trägt sie im Entwurf selbst ein (Entscheidung Gjergj, 2026-11-06). |
| Umschalter Antwortlänge „Kurz | Ausführlich“ | Gebaut (2026-11-06): im Kopf des Gesprächs, speichert sofort über `PATCH /api/me/profile`, gilt ab der nächsten Antwort. |
| Kur- und Reha-Antrag vorausfüllen | Gebaut (2026-11-06): Feldkarte `kur_reha.json`. Seite 1 füllen Lotse und Person, die ärztliche Stellungnahme auf Seite 2 bleibt der Ärztin. |
| Echter E-Mail-Versand | Bewusst nicht gebaut. Die Person sendet selbst über ihr E-Mail-Programm (D-034). |

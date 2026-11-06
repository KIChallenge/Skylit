# Code-Wegweiser für den SV KI-Lotsen

Dieser Wegweiser beschreibt den vorhandenen Backend-Code.
Pfade beziehen sich auf das Repository.

## Überblick

```text
Browser
  │ POST Nachricht / SSE
  ▼
api/messages.py ──► llm/orchestrator.py ──► guardrails/red_flags.py
                           │
                           ├──► rag/retriever.py ──► Postgres / KB
                           ├──► llm/context.py ──► llm/client.py / replay.py
                           ├──► tools/ ──► forms/, providers/, documents/
                           └──► audit/ und Postgres
  ▲                        │
  └──── SSE-Events ◄───────┘
```

`main.py` registriert die API-Router und startet die Anwendung.
`config.py:Settings` liest die Einstellungen.
`db.py` stellt Datenbanksitzungen bereit.
`models/` beschreibt Datenbanktabellen.
`schemas/` beschreibt API-Daten, Cards und SSE-Events.
Docker Compose startet Postgres mit pgvector und das Backend.
`backend/scripts/start.sh` führt Migrationen, Seed und KB-Import aus.
Bei einem Importfehler startet das Skript den Server trotzdem.

## Ein Chat-Turn Schritt für Schritt

1. `api/messages.py:post_message` prüft die Anmeldung und den Besitz der Conversation.
2. `api/messages.py:_turn_events` öffnet eine eigene Datenbanksitzung für den Stream.
3. `llm/orchestrator.py:run_turn` startet `llm/orchestrator.py:_run`.
4. `_run` lädt Verlauf, angehängte Dokumente und Profil.
5. `_run` speichert die Nutzernachricht und sendet `message.created`.
6. `guardrails/red_flags.py:check` prüft den Nachrichtentext.
7. Bei einem Treffer sendet `_run` `emergency` vor der Modellantwort und überspringt die Suche.
8. Sonst ruft `_run` über `_retrieve` die Suche `rag/retriever.py:search` auf.
9. `llm/context.py:build_messages` erstellt den Modellkontext aus Fall, Verlauf, Dokumenten und Suchergebnissen.
10. `llm/orchestrator.py:_tool_loop` streamt Modelltext und führt bei Bedarf Tools aus.
11. `_run_tool` sendet Tool-Events und gegebenenfalls `case.updated` oder `escalation`.
12. `_persist_assistant` speichert die Antwort und ihre Metadaten.
13. `_run` sendet `sources` und abschließend `message.completed`.
14. `api/messages.py:_turn_events` wandelt Events mit `schemas/events.py:to_sse` in SSE um.

Bei Fehlern sendet `run_turn` abschließend ein `error`-Event.
Bei einem Verbindungsabbruch beendet `_turn_events` den Stream.

## API und Datenmodell

`api/auth.py:login` setzt das Session-Cookie für eine Persona.
`deps.py:current_user` löst die angemeldete Person auf.
`api/conversations.py` verwaltet Conversations und Fallschritte.
`api/documents.py:upload_document` nimmt Dokumente an und startet ihre Verarbeitung im Hintergrund.
`api/form_drafts.py` liefert Formularentwürfe und PDFs.
`api/appointments.py:download_appointment` liefert eine Kalenderdatei.
`api/audit.py:read_transparency` liefert Transparenzdaten zu einer Nachricht.
Die API liest und schreibt Daten über SQLAlchemy-Modelle und Sitzungen.
`tests/test_auth.py`, `test_conversations.py`, `test_messages.py` und `test_audit_api.py` prüfen diese Wege.
`tests/test_documents_api.py`, `test_appointments.py` und `test_health.py` prüfen weitere Endpunkte.
`tests/test_models.py` prüft Modelle.
Alle Testpfade in diesem Dokument liegen unter `backend/tests/`.

## LLM und Kontext

`llm/client.py:get_llm_client` wählt den konfigurierten Client.
Der Client unterstützt Eustella, Azure, Fake und Replay.
`llm/context.py:build_messages` liest den Systemprompt, das Profil und den bisherigen Fall.
Die Funktion fügt Verlauf, Dokumentextraktionen und Suchergebnisse hinzu.
`llm/orchestrator.py:_tool_loop` verarbeitet Modell- und Tool-Runden.
Der Orchestrator schreibt Nachrichten, Quellen, Tool-Ergebnisse und Audit-Einträge.
`llm/prompts/system.md` enthält die Verhaltensregeln für das Modell.
`tests/test_llm_client.py`, `test_orchestrator.py` und `test_system_prompt.py` prüfen diese Komponenten.

## Tools

`tools/registry.py:ToolRegistry` registriert und validiert Tool-Aufrufe.
`tools/knowledge_tools.py:search_knowledge` sucht in der Wissensbasis.
`tools/leistung_tools.py` liest Leistungen und zuständige Stellen.
`tools/document_tools.py:get_document` liest eine Dokumentextraktion.
`tools/case_tools.py` schreibt Fallschritte und Fallzusammenfassungen.
`tools/form_tools.py:prepare_form` erstellt einen Formularentwurf und speichert das PDF.
`tools/appointment_tools.py` sucht Demo-Anbieter und erstellt Demo-Termine.
`tools/communication_tools.py:draft_email` erzeugt einen E-Mail-Entwurf.
`tools/escalation_tools.py:escalate` erstellt eine Eskalation mit Übergabezusammenfassung.
Tools liefern Ergebnisse an das Modell und teilweise Cards an die Oberfläche.
`tests/test_tools.py`, `test_forms.py` und `test_appointments.py` prüfen Tool-Verhalten.

## Guardrails

`guardrails/red_flags.py:check` prüft Text deterministisch auf Notfallmuster.
`guardrails/escalation.py:load_contacts` liest die Kontaktdatei.
`guardrails/escalation.py:build_handover_summary` erstellt die Übergabe aus Falldaten.
Das Eskalations-Tool schreibt die Eskalation in die Datenbank.
`tests/test_red_flags.py`, `test_tools.py` und `test_orchestrator.py` prüfen diese Wege.

## Wissensbasis und Retrieval

`rag/ingest.py:ingest` liest Markdown-Dateien aus `backend/seed/kb/`.
Die Funktion zerlegt Texte und schreibt Dokumente und Chunks mit Embeddings in Postgres.
`rag/embedder.py:FastEmbedder` erzeugt lokale Embeddings.
`rag/retriever.py:search` kombiniert Vektorsuche und deutsche Volltextsuche.
`rag/retriever.py:reciprocal_rank_fusion` verbindet die Ranglisten.
Die Suche liefert Chunks und Quellen für den Modellkontext.
`tests/test_rag.py` prüft Import und Suche.

## Dokumente

`documents/pipeline.py:store_upload` prüft und speichert Uploads.
`documents/pipeline.py:process_document` liest die Datei und speichert Status und Extraktion.
`documents/pipeline.py:load_pages` gewinnt PDF-Text oder Seitenbilder.
`documents/pipeline.py:_add_ocr_text` liest Seiten ohne Text mit Tesseract (über PyMuPDF).
Bei Fehler, Zeitüberschreitung oder zu wenig Text bleiben die Seitenbilder für das Vision-Modell.
`documents/extract.py:extract` sendet Text oder Bilder mit dem Extraktionsprompt an den LLM-Client.
`documents/extract.py:_verify_quotes` prüft Zitate gegen vorhandenen Dokumenttext.
Die Funktion entfernt nicht gefundene Zitate und ergänzt einen Hinweis.
Bei OCR-Text gilt ein Zitat auch bei hoher Ähnlichkeit als gefunden (rapidfuzz, `OCR_QUOTE_MIN_SIMILARITY`).
Bei Bildern ohne Textschicht ergänzt `extract` einen Hinweis zur fehlenden Prüfung.
`tests/test_documents.py` und `test_documents_api.py` prüfen die Verarbeitung.

## Formulare

`forms/registry.py:get_template` liest die Formularregistrierung.
`forms/registry.py:get_field_map` liest die Zuordnung semantischer Felder zu PDF-Feldern.
`forms/fill.py:prepare` unterscheidet ausgefüllte, fehlende und fremd auszufüllende Felder.
`forms/fill.py:render_pdf` schreibt die Werte in ein PDF.
`forms/dump_fields.py:dump` liest PDF-Felder für die Erstellung einer Feldzuordnung.
`tests/test_forms.py` prüft Registrierung, Vorbereitung und PDF-Ausgabe.

## Anbieter und Termine

`providers/base.py` definiert Schnittstellen für Anbieter und Termine.
`providers/mock_directory.py:MockProviderDirectory` sucht Anbieter in den Demo-Daten.
`providers/mock_appointments.py:available_slots` erzeugt freie Demo-Termine.
Das Termin-Tool speichert gewählte Termine in Postgres.
`api/appointments.py:calendar_content` erstellt den Inhalt der Kalenderdatei.
`tests/test_appointments.py` und `test_tools.py` prüfen diese Wege.

## Audit

`audit/log.py:audit` schreibt Audit-Einträge in die Datenbank.
`audit/log.py:_scrub` entfernt sensible Detailfelder aus den protokollierten Daten.
`api/audit.py:read_audit` und `read_transparency` lesen Daten für berechtigte Nutzer.
`tests/test_audit_api.py` und `test_orchestrator.py` prüfen Audit und Transparenz.

## Seed, Evaluation und Skripte

`seed.py:seed` liest Personas, Anbieter, Leistungen und Stellen aus JSON-Dateien.
Die Funktion schreibt diese Datensätze in Postgres und überspringt vorhandene Personas beim normalen Start.
`eval/run.py:run_selected` führt ausgewählte Evaluationssets aus.
`eval/run.py:append_result` ergänzt Ergebnisse in `docs/EVAL.md`, sofern das Schreiben aktiviert ist.
`backend/scripts/record_demo.py:run` spielt den Demo-Ablauf über die API durch.
`backend/scripts/smoke_eustella.py` prüft den Live-Anbieter und erstellt einen Bericht.
`tests/test_eval_runner.py` und `test_record_demo.py` prüfen diese Abläufe.

## Sicherheitsnetze

Der Red-Flag-Check läuft vor Retrieval und Modellaufruf.
Ein Treffer sendet zuerst das Notfall-Event mit Kontakten.
Das Tool `escalate` erstellt eine Übergabe an eine Kontaktstelle.
Der Systemprompt verbietet medizinische Beratung und verweist auf menschliche Fachpersonen.
Die Extraktion prüft Zitate nur, wenn Dokumenttext vorliegt.
Replay liest aufgezeichnete Antworten aus `demo/fixtures/`.
Bei fehlender Fixture protokolliert Replay eine Warnung und nutzt den Fake-Client.
`llm/client.py` begrenzt Live-Aufrufe durch `LLM_TIMEOUT_SECONDS`.
Der Orchestrator sendet bei Fehlern ein lesbares `error`-Event.
Ein Tool-Fehler liefert ein Fehlerergebnis an das Modell.

## Daten

`backend/seed/personas.json` enthält synthetische Personas.
`backend/seed/providers.json` enthält erfundene Anbieter mit Demo-Markierung.
Die Termin-Slots erzeugt der Mock-Dienst als Demo-Daten.
`backend/seed/leistungen.json` und `offices.json` enthalten den Leistungskatalog und Stellen.
`backend/seed/escalation_contacts.json` enthält Eskalationskontakte.
`backend/seed/documents/` enthält SV-Box-Dokumente für die Demo.
Die Patientin Anna Berger ist synthetisch.
`backend/seed/forms/` enthält PDF-Vorlagen, Registrierung und Feldzuordnung.
`backend/seed/sources/` enthält den Serviceratgeber als Quelle.
`backend/seed/kb/` enthält Markdown-Wissen mit Quellenangaben.
`demo/fixtures/` enthält aufgezeichnete LLM-Antworten für Replay.
`eval/` enthält Testfälle für Red Flags, Extraktion, Retrieval und Guardrails.

## Befehle

| Ziel | Wirkung |
|---|---|
| `make run` | Startet Docker Compose und baut Images. |
| `make test` | Führt die Backend-Tests aus. |
| `make test-one T=tests/test_forms.py` | Führt die angegebene Testdatei aus. |
| `make lint` | Prüft Backend und Evaluation mit Ruff. |
| `make smoke` | Führt den Eustella-Smoke-Test aus. |
| `make eval SET=red_flags` | Führt das gewählte Evaluationsset aus. `ARGS` ergänzt Optionen. |
| `make eval-all` | Führt alle Evaluationssets aus. `ARGS` ergänzt Optionen. |
| `make ingest` | Importiert die Wissensbasis in die Datenbank. |
| `make seed-reset` | Lädt Personas, Leistungen und Stellen im laufenden Compose neu und löscht Demo-Gespräche. |
| `make dump-fields PDF=seed/forms/pdf/pva_pflegegeld.pdf` | Gibt PDF-Felder und erkannte Beschriftungen aus. |
| `make record-demo` | Führt den Demo-Ablauf gegen das laufende Backend aus. |
| `make check-demo` | Prüft den Demo-Ablauf gegen das laufende Backend. |

Für Aufzeichnungen benötigt `record-demo` den passenden Live-Provider und `LLM_RECORD=1`.

## Wo ändere ich was?

| Ich will … | Datei |
|---|---|
| den Chat-Ablauf ändern | `backend/app/llm/orchestrator.py` |
| den Systemprompt ändern | `backend/app/llm/prompts/system.md` |
| den Extraktionsprompt ändern | `backend/app/llm/prompts/document_extraction.md` |
| ein Tool ändern | `backend/app/tools/` |
| Notfallmuster ändern | `backend/app/guardrails/red_flags.py` |
| Eskalationskontakte ändern | `backend/seed/escalation_contacts.json` |
| die Wissensbasis ändern | `backend/seed/kb/` |
| die Suche ändern | `backend/app/rag/retriever.py` |
| Formularfelder zuordnen | `backend/seed/forms/field_maps/` |
| Demo-Personas ändern | `backend/seed/personas.json` |
| API-Events ändern | `backend/app/schemas/events.py` |
| Einstellungen ändern | `backend/app/config.py` und `.env.example` |
| Evaluationen ändern | `eval/run.py` und die Sets unter `eval/` |

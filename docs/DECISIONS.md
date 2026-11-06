# Technische Entscheidungen

Die Veranstalter verlangen, dass „die eingesetzten Methoden und wesentlichen technischen Entscheidungen nachvollziehbar dokumentiert werden“.
Jeder Eintrag: Entscheidung, Warum, Alternativen, Risiken. Neueste unten.
Diese Datei ersetzt `docs/decisions.md` (D-001 bis D-012 übernommen).

---

**D-001 — Use Case 1 (SV KI-Lotse)** · 2026-11-05 · angenommen
- Entscheidung: Wir bauen Use Case 1 (`KI-Challenge_UseCase.yaml` → `uc1`).
- Warum: klarster Nutzen, live demonstrierbar, passt zu den Skills im Team.
- Alternativen: uc2 HealthPolicy Simulator, uc3 StatAgent.

**D-002 — LLM: eustella-v1.5** · 2026-11-05 · angenommen
- Entscheidung: Primärmodell `eustella-v1.5` über die OpenAI-kompatible API.
- Warum: EU-gehostet, Wiener Start-up, Teil unseres USP. OpenAI-Kompatibilität hält Wechselkosten nahe null.
- Alternativen: Azure OpenAI der Veranstalter.
- Risiken: Closed Beta, Explorer-Limits (2 parallel, 20 rpm). Gegenmaßnahmen: providerunabhängiger Client, `fake`, `replay`, Azure-Fallback, Retries. Tools, Vision und `json_schema` prüft der Smoke-Test.

**D-003 — Fallback-LLM: Azure OpenAI der Veranstalter** · 2026-11-05 · angenommen
- Entscheidung: `LLM_PROVIDER=azure` schaltet auf `gpt-5-4-mini` (West Europe).
- Warum: schützt die Live-Demo vor einem Beta-Ausfall, ebenfalls in der EU.

**D-004 — FastAPI-Backend und Next.js-Frontend** · 2026-11-05 · angenommen
- Entscheidung: FastAPI enthält die ganze Logik. Next.js ist reine Oberfläche.
- Warum: technische Jury. Eigene API mit OpenAPI, typisierte Verträge, Migrationen. Python bringt PyMuPDF, pypdf und fastembed.
- Alternativen: nur Next.js (Vorgabe des `scaffold`-Skills).
- Risiken: zwei Services → Verträge in `contracts.md`, generierte TS-Typen, Docker Compose.

**D-005 — Postgres mit pgvector** · 2026-11-05 · angenommen
- Entscheidung: eine Postgres-Datenbank für App-Daten, KB-Chunks und Vektoren.
- Warum: ein System, hybride Suche (Vektor plus deutsche Volltextsuche) in SQL.

**D-006 — Lokale Embeddings mit fastembed** · 2026-11-05 · angenommen
- Entscheidung: Embeddings laufen auf der CPU im Backend (`paraphrase-multilingual-MiniLM-L12-v2`, 384 Dimensionen).
- Warum: eustella hat keinen Embeddings-Endpunkt. Suchanfragen verlassen unseren Rechner nicht.

**D-007 — Eigenes SSE-Event-Protokoll** · 2026-11-05 · angenommen
- Entscheidung: eigene typisierte SSE-Events (`contracts.md` §2).
- Warum: volle Kontrolle über Cards, Fall-Updates, Eskalation und Notfall. Keine Kopplung an ein Frontend-SDK.

**D-008 — Keine klinische Anamnese (OPQRST, SAMPLER)** · 2026-11-05 · ersetzt durch D-033
- Entscheidung: nur administrative Rückfragen. Symptome dienen nur dem Red-Flag-Check.
- Warum: Klinische Anamnese ist Triage und widerspricht der medizinischen Grenze des Use Case.

**D-009 — Eskalation als eigenes Feature** · 2026-11-05 · angenommen
- Entscheidung: fester Red-Flag-Check vor dem LLM, `escalate`-Tool, Eskalations-Card mit Übergabezusammenfassung, Audit.
- Warum: USP und Jurykriterium „verantwortungsvoller Umgang mit Unsicherheiten“.

**D-010 — Mocks hinter Schnittstellen der echten Systeme** · 2026-11-05 · angenommen
- Entscheidung: Versicherungsstatus, Ärzteverzeichnis, Termine und E-Mail sind Mocks hinter Protocols mit den Namen der echten Systeme. Das UI zeigt „Demo-Daten“.
- Warum: keine echten Daten erlaubt. Der Weg zur Produktion ist eine Klasse pro Anbindung.

**D-011 — Keine PWA** · 2026-11-05 · geändert durch D-013
- Entscheidung: Die PWA ist gestrichen. Das Frontend ist eine normale Web-App mit Kamera-Upload über `<input capture>`.
- Warum: Scope A.

**D-012 — Entwicklung privat, Abgabe öffentlich** · 2026-11-05 · angenommen
- Entscheidung: Entwicklung in `John2206/ki-challenge-26` (privat). Vor der Jury kopieren wir den Stand nach `KIChallenge/Skylit` (öffentlich).
- Warum: Andere Teams können das öffentliche Repo während des Events lesen.
- Risiken: Die Kopie darf weder `.env` noch die Veranstalter-Dokumente enthalten (`KI Challenge Teilnahmeinformationen.pdf`, `Use Case 1 Versicherten-Chatbot V2.docx`).

**D-013 — Scope A** · 2026-11-05 · angenommen
- Entscheidung: Must: S1, S2, S3, Transparenz-Panel, Pflegegeldantrag, Mein Fall. Should: S5 (Englisch), `.ics`-Termin, Kur-und-Reha-Antrag. Cut: S4, PWA, Spracheingabe, Einfache Sprache, FSW- und Fahrtkostenformular, Erstattungskodex.
- Warum: 19 Stunden für drei Personen. Jeder Task braucht Review. Die Demo zählt mehr als die Feature-Zahl.
- Alternativen: S1–S5 mit zwei Formularen. Voller Scope aus `product.md`.
- Risiken: S4 fehlt als Gesundheitsförderungs-Beispiel. S5 zeigt dafür einen zweiten Nutzertyp.

**D-014 — AI-Act-Einordnung: begrenztes Risiko** · 2026-11-05 · angenommen, in der Fragestunde zu prüfen
- Entscheidung: Wir nennen „begrenztes Risiko, Transparenzpflichten nach Art. 50“.
- Warum: Der Lotse entscheidet nicht über Ansprüche und hat keine medizinische Funktion. Das UI kennzeichnet ihn als KI.
- Alternativen: „potenziell Hochrisiko“ wegen Betrieb durch einen SV-Träger. Keine Einordnung bis zur Antwort der Veranstalter.
- Risiken: Eine automatische Anspruchsprüfung fiele unter Anhang III Nr. 5(a). Diese Grenze nennen wir offen. Die Einordnung ist unsere Lesart, keine Rechtsauskunft.

**D-015 — Eval mit vier Sets** · 2026-11-05 · angenommen
- Entscheidung: Red-Flag-Check (40 Phrasen), Guardrails live (12 Prompts), Dokument-Extraktion (5 Empfehlungen), Retrieval (20 Fragen). Ziele in `PLAN.md` → Qualität.
- Warum: Jurykriterium „Daten- und KI-Qualität“ braucht gemessene Zahlen.
- Alternativen: ohne Retrieval-Eval. Nur Guardrail-Suite.

**D-016 — Keine öffentliche URL, Demo vom Laptop** · 2026-11-05 · angenommen
- Entscheidung: Die App läuft nur lokal mit `make run`. Die Demo läuft auf Jonathans Laptop.
- Warum: kein Deploy-Aufwand, keine Cold Starts, kein öffentlich erreichbarer API-Key-Verbrauch.
- Alternativen: VPS mit Docker Compose. Railway oder Render. Laptop mit Tunnel.
- Risiken: weicht von der AGENTS.md-Regel „public URL“ ab. Ausfall des Laptops → zweiter Laptop mit `LLM_PROVIDER=replay`, dann Backup-Video.

**D-017 — Replay-Provider für die Offline-Demo** · 2026-11-05 · angenommen
- Entscheidung: Der LLM-Client hat die Provider `eustella`, `azure`, `fake` und `replay`. `replay` liest Antworten aus `demo/fixtures/`, Schlüssel ist ein Hash der normalisierten Anfrage. `LLM_RECORD=1` zeichnet auf. `fake` bleibt für Unit-Tests.
- Warum: Die Demo muss ohne Netz und ohne Quota laufen (AGENTS.md).
- Alternativen: Replay auf SSE-Ebene pro Szenario. Einfacher, testet aber den Backend-Pfad nicht.
- Risiken: Dynamische Werte (UUIDs, Datum) im Kontext ändern den Hash. Gegenmaßnahme: Normalisierung vor dem Hash, Rückfall auf `fake` mit Warnung.

**D-018 — Frontend erst nach Freigabe** · 2026-11-05 · angenommen
- Entscheidung: Kein Frontend-Task (Scaffold, Designsystem, Demo-Check) startet, bevor Jonathan ihn freigibt.
- Warum: Entscheidung des Teams. Zuerst stehen Backend, Daten und Eval.
- Risiken: Die Jury bewertet das UI. Wenig Zeit für Designsystem und `ui-polish` gefährdet „Nutzbarkeit und Kommunikation“.

**D-019 — Nur claude und codex als Worker** · 2026-11-05 · angenommen
- Entscheidung: Das Team setzt agy nicht mehr ein. Tasks gehen nur an claude und codex.
- Warum: Headless-agy verweigerte jeden Shell-Befehl und hatte keinen Webzugriff. Es schrieb KB-Dateien aus dem Gedächtnis mit toten Quell-URLs.
- Risiken: weniger parallele Worker. Quellenprüfung im Web macht der Manager.

---

## Smoke-Test-Ergebnisse

Alle 8 Checks bestanden (Tools, Vision, `json_schema`, Prompt-Cache). Details: `docs/smoke-eustella.md`.

## D-020 — Frontend mit drei Claude-Workern — 2026-11-05
- **Decision:** Jonathan gibt das Frontend frei. Drei Claude-Worker arbeiten über hackkit. Codex übernimmt das Management.
- **Why:** Das Backend steht. Das Team konzentriert die verbleibende Zeit auf die Jury-Demo.
- **Alternatives:** agy bleibt ausgeschlossen. ID Austria und ein vollständiger Kalender erweitern den Demo-Scope nicht.
- **Risks / limits:** Gemeinsame Dateien brauchen eindeutige Task-Zuständigkeit. Das Designsystem muss vor Feature-Screens auf main stehen.

## D-021 — Reproduzierbare Frontend-Installation — 2026-11-05
- **Decision:** Das Frontend nutzt eine Lockdatei und Playwright 1.64.0 als feste Version.
- **Why:** Der bisherige Versionsbereich löste eine Version mit fehlendem playwright-core auf. Der Manager hat die Installation geprüft.
- **Alternatives:** Der offene Versionsbereich scheiterte. Playwright 1.56.0 unterstützt das lokale Ubuntu nicht beim Browser-Download.
- **Risks / limits:** Updates brauchen erneute Installations- und Browserprüfungen. Die lokale Sichtprüfung nutzte den installierten Chrome.

## D-022 — Frontend-Befehle für Headless-Worker — 2026-11-05
- **Decision:** hackkit führt vor jedem Worker make frontend-setup aus. Agenten nutzen die Frontend-Make-Ziele.
- **Why:** Die automatische Erkennung übersieht verschachtelte Lockdateien. Die Claude-Freigabe erlaubt make, aber nicht npm --prefix.
- **Alternatives:** Wiederholte Tasks scheitern unverändert. Breitere Agent-Berechtigungen sind nicht erforderlich.
- **Risks / limits:** Laufende Worker-Prozesse müssen die neue Konfiguration laden. npm ci braucht beim ersten Lauf Netzwerkzugriff.

## D-023 — Designsystem „Klare Route“ mit gesperrter Standardpalette — 2026-11-05
- **Decision:** Eine Tokens-Datei (`frontend/src/app/globals.css`) setzt OKLCH-Rollen und eine eigene Schriftskala. Tailwinds Standardfarben und -schriftgrößen sind abgeschaltet.
- **Why:** Feature-Worker können so keine Einzelwerte wie `text-neutral-600` oder `text-sm` einschleusen. Der Build erzeugt dafür keine Klasse.
- **Alternatives:** Standardpalette behalten und per Review prüfen. Das scheitert bei drei parallelen Workern.
- **Risks / limits:** Neue shadcn-Komponenten aus der Registry nutzen teils Standardklassen. Ein Worker muss sie auf Tokens umschreiben.

## D-024 — Systemschrift statt Atkinson Hyperlegible Next — 2026-11-05
- **Decision:** Die App nutzt vorerst die Systemschrift über `--font-sans`.
- **Why:** Die Schriftdatei liegt nicht im Repo. Workers haben keinen Netzzugriff. Schriften aus dem Netz sind verboten.
- **Alternatives:** Atkinson später über `next/font/local` einbinden. Die Umstellung betrifft nur `--font-sans`.
- **Risks / limits:** Die Schrift sieht je Betriebssystem anders aus. Die Demo läuft auf Jonathans Laptop, daher zählt nur dessen Systemschrift.

## D-025 — `tailwind-merge` kennt die eigenen Tokens — 2026-11-05
- **Decision:** `cn()` nutzt `extendTailwindMerge` mit den Schriftklassen, Radien und Schatten aus der Tokens-Datei.
- **Why:** Ohne diese Angabe hält `tailwind-merge` `text-body` für eine Farbe. Es verwarf dann `text-on-emergency` am Notruf-Button.
- **Alternatives:** Klassen ohne `cn()` zusammensetzen. Das bricht `className`-Überschreibungen der shadcn-Komponenten.
- **Risks / limits:** Neue Schrift-, Radius- oder Schatten-Tokens müssen auch in `frontend/src/lib/utils.ts` stehen.

## D-026 — AppShell als reines Slot-Layout — 2026-11-05
- **Decision:** `AppShell` nimmt Kopfbereich, Navigation, Gespräch, Mein Fall und Notfall-Banner als `ReactNode`. Unter 1440 px wird die Navigation zum Sheet, unter 1024 px auch Mein Fall.
- **Why:** Login-, Chat- und Fall-Tasks laufen parallel. Die Shell darf keine Feature-Imports oder API-Calls haben.
- **Alternatives:** Ein Layout pro Route. Das dupliziert Breakpoint-Logik und Spaltenbreiten.
- **Risks / limits:** Ein Sheet rendert den Slot neu. Zustand in Navigation oder Mein Fall gehört darum in die Feature-Ebene, nicht in den Slot.

## D-027 — Designsystem „Klare Route“ mit Systemschrift — 2026-11-05
- **Decision:** Gjergj gibt die Richtung „Klare Route“ frei. Alle Werte stehen in `frontend/src/app/globals.css` als OKLCH-Tokens. Die App nutzt vorerst die Systemschrift.
- **Why:** Die Demo läuft offline und auf dem Beamer. Ein Token-File verhindert Einzelwerte. Systemschrift braucht keine Schriftdatei und kein Netz.
- **Alternatives:** Atkinson Hyperlegible Next als lokale Datei. Sie fehlt noch im Repo. Inter oder Geist über `next/font/google` brauchen Netz beim Build.
- **Risks / limits:** Die Systemschrift sieht je nach Betriebssystem anders aus. Die Demo-Laptops zeigen darum leicht verschiedene Laufweiten.

## D-028 — shadcn/ui-Namen auf semantische Tokens abgebildet — 2026-11-05
- **Decision:** `primary`, `muted`, `border` und weitere shadcn/ui-Namen zeigen auf die semantischen Tokens. Button und Badge haben die Varianten aus DESIGN.md. Rot gibt es nur als Variante `emergency`.
- **Why:** Generierte Komponenten folgen dem Design ohne eigene Farben. Rot bleibt dem Notfall vorbehalten.
- **Alternatives:** Eigene Komponenten ohne shadcn/ui. Das widerspricht AGENTS.md und kostet Zeit.
- **Risks / limits:** `npx shadcn add` erzeugt neue Dateien mit Standardklassen. Jede neue Komponente braucht eine kurze Token-Prüfung.

## D-029 — tailwind-merge kennt die eigene Typo-Skala — 2026-11-05
- **Decision:** `cn()` nutzt `extendTailwindMerge` mit den Größen `display` bis `caption`.
- **Why:** Ohne diese Angabe hält tailwind-merge `text-label` für eine Farbe. Es löscht dann `text-primary-foreground`, und Button-Text wird dunkel auf Grün.
- **Alternatives:** Standard-Tailwind-Größen wie `text-sm`. Sie passen nicht zu den Rollen in DESIGN.md.
- **Risks / limits:** Neue Größen-Tokens müssen auch in `frontend/src/lib/utils.ts` stehen.

## D-030 — Gjergjs Designsystem ersetzt die erste Umsetzung — 2026-11-05
- **Decision:** PR #34 ersetzt die gemeinsame UI aus PR #33. Die API-Fassade und Demo-Tests bleiben erhalten.
- **Why:** Jonathan beauftragt den Merge von Gjergjs freigegebener Umsetzung. Ein gemeinsames System verhindert widersprüchliche Komponenten.
- **Alternatives:** Beide Systeme gleichzeitig behalten. Das erzeugt unvereinbare Tokens und Komponenten-Varianten.
- **Risks / limits:** Neue Feature-Tasks müssen die Exporte aus PR #34 nutzen. Die Integration bewahrt reduzierte Bewegung und die Entscheidungshistorie.

## D-031 — Codex übernimmt die Frontend-Feature-Tasks — 2026-11-05
- **Decision:** Tasks #49 bis #57 laufen mit Codex auf Jonathans Laptop. Claude prüft, merged und baut nur kleine Integrationsfixes.
- **Why:** Das Claude-Kontingent im Team ist fast verbraucht. Jonathan hat noch zwei Codex-Resets.
- **Alternatives:** Claude-Worker auf allen Laptops. Das Kontingent reicht nicht bis zur Abgabe.
- **Risks / limits:** Codex lädt die UI-Skills nicht automatisch. Die Task-Bodies verweisen deshalb auf `.agents/skills/better-*/SKILL.md`. Claude prüft die Gestaltung im Review.

## D-032 — Medizinische Grenze gelockert: Anlaufstelle statt Pauschal-Eskalation — 2026-11-05
- **Decision:** Der Lotse prüft zuerst Lebensgefahr. Allgemeine Gesundheitsfragen beantwortet er mit der passenden Anlaufstelle und allgemeinen Hinweisen mit Quelle. `escalate(medical_question)` gilt nur noch für Diagnose, Befunddeutung, Medikament, Dosis oder Therapie im Einzelfall. Er antwortet in der Sprache der Nachricht, die Profilsprache ist der Fallback.
- **Why:** Der Lotse eskalierte jede Gesundheitsfrage an 1450 und gab keine brauchbare Antwort. Das macht das Produkt für Nutzerinnen wertlos.
- **Alternatives:** Pauschal-Eskalation behalten (bisher). Klinische Anamnese nach SAMPLER: offen, das Team liefert die eigene Fassung nach (D-008 bleibt bis dahin gültig).
- **Risks / limits:** Die Empfehlung einer Anlaufstelle ist eine leichte Form der Einordnung. Keine Diagnose, keine Symptombewertung. Die Replay-Fixtures müssen nach dieser Prompt-Änderung neu aufgezeichnet werden. Der Live-Guardrail-Eval muss erneut laufen.

## D-033 — SAMPLER-Aufnahme als zweiter Schritt — 2026-11-06
- **Decision:** Schildert eine Person eine gesundheitliche Beschwerde ohne Notfall, fragt der Lotse nach SAMPLER (S mit OPQRST, dann A, M, P, L, E, R). Jede Frage kommt einzeln über das Tool `ask_sampler` als Karte mit 2–6 Antwortoptionen und einem Beschreibungsfeld. Die Karte beendet den Turn. Nach R folgen Zusammenfassung und Anlaufstelle. Ersetzt D-008.
- **Why:** Die Nutzerin soll schnell und ohne unnötige Angaben zur passenden Anlaufstelle kommen. Auswahlantworten sind leichter als freie Texte. SAMPLER ist das in Österreich übliche Aufnahmeschema, vom Team vorgegeben.
- **Alternatives:** Keine Anamnese (D-008). Eine feste Fragenliste im Backend: zuverlässiger, aber ohne zur Beschwerde passende Optionen.
- **Risks / limits:** Klinische Anamnese ist eine Form der Triage. Die Use-Case-Vorgabe der Veranstalter verlangt eine strikte medizinische Grenze; die Jury kann das kritisch sehen. Der Lotse stellt weiter keine Diagnose. Das Modell überspringt manchmal einen Schritt oder fragt einen schon beantworteten. Bis zu 12 Fragen sind lang. Replay-Fixtures und Live-Guardrail-Eval müssen neu laufen.

## D-034 — E-Mail-Entwurf: Person sendet selbst über ihr E-Mail-Programm — 2026-11-06
- **Decision:** Der Lotse erstellt mit `draft_email` nur einen Entwurf. Die Card zeigt Empfängername, ein leeres Adressfeld, Betreff und Text zum Bearbeiten. „In E-Mail-Programm öffnen“ erzeugt einen `mailto:`-Link, „Text kopieren“ kopiert Betreff und Text. Für „nächste Hausärztin“ nutzt der Lotse `find_providers` mit der PLZ aus dem Profil. Nach einer SAMPLER-Aufnahme bietet er eine E-Mail mit den Angaben an.
- **Why:** Die Person entscheidet und sendet jede E-Mail selbst (Mensch entscheidet). Kein Mailserver und keine Zugangsdaten nötig.
- **Alternatives:** Echter Versand über SMTP: braucht Konfiguration und echte Adressen, widerspricht „Mensch sendet“. Nur Kopieren: ein Schritt mehr für die Person. Demo-Adressen für die Anbieter: verworfen, die Person trägt die Adresse ein.
- **Risks / limits:** Ein `mailto:`-Link braucht ein eingerichtetes E-Mail-Programm. Sehr lange Texte kann ein Programm kürzen; dann hilft „Text kopieren“. Gesundheitsangaben stehen im Klartext in der E-Mail, die Person sendet sie bewusst selbst.

## D-035 — Antwortlänge sichtbar im Gespräch, SAMPLER im Notfall gesperrt — 2026-11-06
- **Decision:** Der Umschalter „Antworten: Kurz | Ausführlich“ steht im Kopf des Gesprächs, nicht im Persona-Menü. Er speichert sofort über `PATCH /api/me/profile` und setzt bei einem Fehler zurück. Zusätzlich lehnt das Backend `ask_sampler` in einem Turn ab, in dem der Red-Flag-Check einen Notfall erkannt hat.
- **Why:** Die Einstellung soll ohne Suchen auffindbar sein. Im Notfall gilt „Lebensgefahr zuerst“; das Modell hatte trotz Notfall-Banner eine SAMPLER-Frage gestellt. Eine harte Sperre im Backend ist zuverlässiger als eine Prompt-Regel.
- **Alternatives:** Eintrag im Persona-Menü: versteckt. Das Tool im Notfall aus der Tool-Liste nehmen: ändert die Anfrage und damit die Replay-Schlüssel.
- **Risks / limits:** Eine geänderte Antwortlänge ändert die Anfrage. Steht eine Demo-Persona auf „Ausführlich“, passen die Replay-Aufnahmen nicht; `POST /api/dev/reset` setzt die Persona zurück.

## D-036 — Kur- und Reha-Antrag: Feldkarte, abgeleitete Felder, Formulare in der Tool-Beschreibung — 2026-11-06
- **Decision:** `kur_reha.json` bildet Seite 1 des DVSV-Antrags ab (Patient*in, Versicherte*r, Leistungsbezüge, frühere Aufenthalte). Die ärztliche Stellungnahme auf Seite 2 steht als 12 Arztgruppen unter „Füllen andere aus“; nur die Patientenzeile (Name, Geburtsjahr, Geschlecht) füllt der Lotse. Neu: `copy_from` leitet ein Feld aus anderen ab, etwa „Familienname Vorname“ aus Nach- und Vorname. Die `prepare_form`-Beschreibung nennt alle Formulare mit ihren Hauptschlüsseln, erzeugt aus der Registry. Ein Turn mit Card, aber ohne Text, gilt als vollständig. Die FSW-Pflegeberatung kommt nur noch bei Pflege-Leistungen dazu.
- **Why:** Ohne Formular-ID riet das Modell `pva_pflegegeld`. Ohne Schlüssel verbrauchte es alle Tool-Runden und lieferte ein leeres Formular. Die Patientenzeile auf Seite 2 sollte das Modell nicht doppelt angeben müssen. FSW passt nicht zu einem Reha-Antrag.
- **Alternatives:** Formular-ID nur im Golden Path des Prompts: deckt nur Pflegegeld ab. Alle Schlüssel in der Beschreibung: zu lang für jede Anfrage. Mehr Tool-Runden: kostet Zeit und behebt das Raten nicht.
- **Risks / limits:** Die Tool-Beschreibung ist Teil jeder Anfrage; neue Formulare oder Schlüssel erfordern eine neue Replay-Aufnahme. Der Versicherungsträger erscheint als Kürzel („OEGK“), wenn das Modell den Profilwert übernimmt.

## D-037 — Optik „Atmosphäre“ mit hellem und dunklem Design — 2026-11-06
- **Decision:** Neue Optik nach Referenz-Stimmung: weicher Radialverlauf, Glas-Panels, mehr Luft, große Eingabebox, zentrierter Login. Zwei Designs über dieselben Tokens; hell ist Standard, dunkel per Umschalter im Kopf, gespeichert im Browser. Der Notfall-Banner wird beim Notfall-Event in einem eigenen Commit gerendert.
- **Why:** Gjergj wünscht eine modernere, atmosphärische Oberfläche und beide Designs. Mit `backdrop-filter` wurde das Rendern langsamer; Notfall-Event und erster Text kamen dann im selben React-Commit an, und der Demo-Check S3 schlug fehl.
- **Alternatives:** Nur dunkel wie die Referenz: widerspricht der Beamer-Regel in `AGENTS.md`. Nur hell: ohne den gewünschten dunklen Modus. Glas ohne Blur: wirkt flach.
- **Risks / limits:** `AGENTS.md` nennt noch „Light theme“; das helle Design bleibt deshalb Standard für die Demo. Dunkles Design auf dem Beamer vorher prüfen. Logo, Wortmarke und Maskottchen der Referenz sind bewusst nicht übernommen.

## D-038 — Fahrtkostenformular vorausfüllen — 2026-11-06 03:40
- **Decision:** Der Lotse füllt zusätzlich den ÖGK-Antrag auf Zuschuss zu Fahrtkosten vor. Das hebt D-013 für dieses Formular auf. Den Kur-und-Reha-Antrag regelt D-036.
- **Why:** Der Entlassungsbrief nennt Fahrtkosten zur Bestrahlung. Das Formular hat nur 13 Felder und hängt an der Leistung `fahrtkostenzuschuss`.
- **Alternatives:** D-013 beibehalten. FSW-Förderantrag: 122 Felder, zu viel Aufwand für die Demo.
- **Risks / limits:** Neue Leistungsdaten ändern den Modellkontext, darum Replay-Fixtures neu aufnehmen. Ein Mensch prüft die Feldzuordnung. Eine bestehende Datenbank braucht `make seed-reset`.

## D-039 — Kalender unter „Mein Fall“ — 2026-11-06
- **Decision:** Ein Kalender steht unten in der Spalte „Mein Fall“, gleich breit. Verkleinert zeigt er die nächsten drei Termine. Vergrößert füllt er die Spalte mit Monatsansicht, allen Terminen und einem Formular. Einträge haben drei Arten: Termin, Frist, Erinnerung. Die Termin-Card speichert einen Vorschlag mit „Im Kalender speichern“; die `.ics`-Datei bleibt als zweite Aktion. Neue Tabelle `calendar_entries`, Routen `GET/POST /api/calendar-entries` und `DELETE /api/calendar-entries/{id}`, nur für die eigene Person. Der Seed legt pro Persona drei bis vier Demo-Termine relativ zum Seed-Tag an.
- **Why:** Fabian wünscht Arzttermine und Fristen aus dem Gespräch an einem Ort. Das hebt für diesen Umfang „kein vollständiger Kalender“ aus PLAN.md auf. Termine im Backend überstehen einen Neustart und gelten für alle Gespräche einer Person.
- **Alternatives:** Nur `localStorage`: nach jedem Browserwechsel leer, keine Demo-Daten. Ein LLM-Tool, das Termine selbst einträgt: ändert die Tool-Liste und damit alle Replay-Aufnahmen. Eigenes Dialogfenster statt vergrößerter Spalte: verdeckt das Gespräch.
- **Risks / limits:** Der Lotse trägt noch keine Termine selbst ein; die Person speichert sie. Demo-Termine liegen relativ zum Seed-Tag und rücken mit der Zeit in die Vergangenheit; `make seed-reset` legt sie neu an. Das Formular rechnet in Wiener Zeit.

## D-040 — Ärzteliste der Stadt Wien statisch laden, Standort aus dem Browser — 2026-11-06
- **Decision:** Die Ärzte-Standorte der Stadt Wien (WFS-Layer `ogdwien:ARZTOGD`, data.wien.gv.at, CC BY 4.0) liegen als statische Datei `backend/seed/vienna_doctors.json` im Repo. `scripts/fetch_vienna_doctors.py` erzeugt sie neu. Der Seed lädt sie bei jedem Start per Upsert in `providers` (`source = "wien_ogd"`, Art `gp` oder `specialist`). Erfundene Anbieter behalten `source = "demo"`. `find_providers` sucht das Fachgebiet als Teilstring. `propose_appointment` lehnt echte Ordinationen ab. Der Browser fragt nach einem Erklär-Dialog um den Standort. Die Koordinaten (auf etwa 100 m gerundet) gehen pro Nachricht an das Backend und dort nur an `find_providers`.
- **Why:** Die Demo-Anbieter decken keine Fachärzte ab. Eine statische Datei hält die Demo offline und wiederholbar. Der Standort ist genauer als der Bezirksmittelpunkt der Postleitzahl.
- **Alternatives:** WFS bei jeder Suche abfragen: braucht Netz, ein Radiusfilter (`DWITHIN`) lieferte keine Treffer. Standort im Profil speichern: mehr personenbezogene Daten als nötig. Nur der Browser-Dialog ohne eigenen Hinweis: erklärt nicht, wofür der Lotse den Standort braucht.
- **Risks / limits:** Die Daten nennen keinen Kassenvertrag und keine Öffnungszeiten; 43 % der Einträge haben keine Telefonnummer. Echte Namen erscheinen im Chat; ein Demo-Termin bei echten Ordinationen ist gesperrt. Prompt und Tool-Beschreibung haben sich geändert: Replay-Aufnahmen neu aufnehmen. Bei einer Suche ab dem Standort bekommt das Modell keine Entfernungen, denn drei Entfernungen verraten den Standort. Die gespeicherte Card enthält diese Entfernungen; daraus lässt sich der Standort grob schätzen. Der Standort braucht HTTPS oder `localhost`. Die CC-BY-Lizenz steht auf der Wien-Seite zu Ärzten; der Katalogeintrag des Layers ist nicht geprüft.

## D-041 — Eine simulierte SV-Datenabfrage füllt die Persona-Profile — 2026-11-06
- **Decision:** Jede Demo-Persona hat eine synthetische SV-Nummer. Beim Seed liefert `MockSvDataService` (Protocol `SvDataService`, D-010) die Daten aus `backend/seed/sv_register.json`. Der Seed übernimmt daraus Bundesland, PLZ, Versicherungsträger und Geburtsdatum und speichert die ganze Antwort in `profiles.sv_record` (Migration `0005`). Das Benutzermenü zeigt „Meine Daten“ mit „Demo-Daten“ und „Quelle: simulierte SV-Datenabfrage“.
- **Why:** Personalisierung aus der SV-Nummer zeigt den Nutzen ohne Formularausfüllen. Eine echte Schnittstelle steht uns nicht zur Verfügung. Eine spätere Anbindung braucht nur eine neue Klasse.
- **Alternatives:** Profile weiter von Hand in `personas.json` (kein Bezug zur SV). Ein Ablauf „Konto anlegen“ mit Live-Abfrage: gestrichen, die Personas bleiben der Login.
- **Risks / limits:** Die Prompt-Zeilen bleiben byte-gleich, sonst verfehlt der Replay-Hash alle Fixtures; ein Test sichert das. Die SV-Nummer, Name und Adresse gehen nie an das LLM. Synthetische Nummern bestehen die Prüfziffer und können echt wirken; `sv_register.json` und `docs/data.md` kennzeichnen sie. Ein Echtbetrieb braucht eine Rechtsgrundlage und die Einwilligung der Person.

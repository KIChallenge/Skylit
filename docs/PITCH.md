# Demo-Skript und Pitch — SV KI-Lotse

Fachjury: 15 Minuten. Der Plan: 11 Minuten Pitch und Demo, 4 Minuten Fragen.
Die Demo läuft auf Jonathans Laptop, 1920×1080 am Beamer. Fallback: zweiter Laptop mit `LLM_PROVIDER=replay`, dann Backup-Video.

## 1. Problem (30 s)

„Maria Berger, 52, berufstätig. Ihre Mutter Anna, 78, kommt nach einer Krebsbehandlung aus dem Spital und lebt allein. Maria hält einen Entlassungsbrief mit acht Abschnitten in der Hand. Darin stehen Reha, Pflegegeld, mobile Pflege, Rezeptgebührenbefreiung und Fahrtkosten. Wer ist zuständig? Welches Formular? Was zuerst?“

Zahlen mit Quelle: aus `docs/research/problemzahlen.md` (Task T8). Ohne Quelle nennen wir keine Zahl.

## 2. Lösung in einem Satz

„Der SV KI-Lotse macht aus einer Alltagsbeschreibung und einem Entlassungsbrief einen Fall mit konkreten Schritten: Leistungen, vorausgefülltes Formular, zuständige Stelle und ein Mensch, wenn die KI aufhören muss.“

## 3. Live-Demo (5 min)

Vorbereitung: `POST /api/dev/reset` für Maria. Browser auf `http://localhost:3000/login`. Datei `backend/seed/documents/entlassungsbefund.pdf` liegt auf dem Desktop.

### S1 — Golden Path (3 min)
1. Klick auf die Persona-Karte **Maria Berger**. Der Lotse-Screen öffnet sich, „Mein Fall“ ist leer.
2. Eingabe: „Meine Mutter ist gerade aus dem Spital gekommen und kommt allein nicht mehr zurecht. Was muss ich tun?“
3. Der Lotse streamt die Antwort und stellt höchstens zwei Fragen: Gibt es einen Entlassungsbrief? Lebt Ihre Mutter in Wien?
4. Eingabe: „Ja, sie wohnt in Wien. Hier ist der Brief.“ Klick auf das Büroklammer-Symbol, `entlassungsbefund.pdf` wählen, senden.
5. Die Fortschrittszeile zeigt „Dokument wird gelesen…“. Die Dokument-Card zeigt die Empfehlungen als wörtliche Zitate mit Abschnitt:
   - Abschnitt 7: Prüfung einer stationären onkologischen Rehabilitation
   - Abschnitt 8: Pflegegeld prüfen
   - Abschnitte 6.3 und 8: mobile Hauskrankenpflege, soziale Dienste Wien
   - Abschnitt 8: Rezeptgebührenbefreiung, Fahrtkosten zur Bestrahlung
6. „Mein Fall“ füllt sich mit 5–6 Schritten. Sprechtext: „Das ist kein Chatverlauf. Das ist ein Fall, den Maria morgen fortsetzt.“
7. Eingabe: „Bitte füll den Pflegegeldantrag für meine Mutter aus.“ Die Formular-Card zeigt ausgefüllte Felder, fehlende Felder und Felder für Ärztin oder Antragstellerin. Klick auf **PDF herunterladen**, PDF kurz zeigen.
8. Die Office-Cards zeigen die PVA (Pflegegeld) und das FSW-Beratungszentrum Pflege und Betreuung.
9. Klick auf **Warum diese Antwort?**. Das Panel zeigt Quellen mit Link, die Tool-Aufrufe, das Modell `eustella-v1.5` und die Sicherheit mit Label.

### S2 — Medizinische Grenze (1 min)
1. Eingabe: „Soll meine Mutter das Ondansetron höher dosieren, ihr ist noch immer schlecht?“
2. Der Lotse lehnt in einem Satz ab und begründet. Die Eskalations-Card zeigt Hausärztin oder onkologisches Team, außerhalb der Ordinationszeiten 1450.
3. Klick auf **Zusammenfassung kopieren**. Sprechtext: „Maria fängt am Telefon nicht bei null an.“

### S3 — Notfall (30 s)
1. Eingabe: „Meine Mutter hat plötzlich starke Atemnot.“
2. Der Notfall-Banner mit **144** erscheint sofort, vor jeder KI-Antwort. Sprechtext: „Das prüft eine feste Regel vor dem Modell. Diese Prüfung kann das Modell nicht übergehen.“

### S5 — Sprache (30 s, nur wenn Zeit bleibt)
1. Abmelden, Persona **Elif Yılmaz** wählen.
2. Eingabe: „Which check-ups does my 2-year-old need?“ Der Lotse antwortet auf Englisch mit Eltern-Kind-Pass und Kinderimpfprogramm.

## 4. So funktioniert es (2 min)

Vier Kästen: Next.js-Oberfläche → FastAPI-Backend mit Agent und Tools → LLM `eustella-v1.5` (EU, Wien) → Postgres mit pgvector.
- Das Modell ruft Tools auf: Wissenssuche, Leistung, Stelle, Formular, Fallschritt, Eskalation.
- Die Wissensbasis besteht aus offiziellen Quellen (oesterreich.gv.at, PVA, ÖGK, FSW). Die Embeddings laufen lokal.
- Der Lotse liest den Entlassungsbrief aus, interpretiert ihn aber nicht: nur wörtliche Zitate.
- Qualität: Folie mit den Eval-Zahlen aus `docs/EVAL.md` (Red Flags, Guardrails, Extraktion, Retrieval).
- Kurz `http://localhost:8000/docs` zeigen: echte API, Mocks hinter Schnittstellen mit den Namen der echten Systeme.

## 5. Verantwortungsvoller KI-Einsatz (2 min)

- AI Act: begrenztes Risiko, Art. 50. Der Lotse entscheidet keinen Anspruch und berät nicht medizinisch.
- Quellen, Modell und Sicherheit an jeder Antwort.
- Der Mensch entscheidet: Die Stelle entscheidet über die Leistung, Maria sendet das Formular selbst.
- Eskalation als Feature: sechs Gründe, feste Notfallregel, Übergabezusammenfassung.
- Datenschutz: nur synthetische Daten, EU-Modell, lokale Embeddings, kein Dokumentinhalt im Audit-Log.
- Grenzen: nur Wien, Demo-Daten für Termine und Ärzte, eustella ist Beta.

## 6. Wirkung und nächste Schritte (1 min)

- Time-to-Impact: Die Mocks heißen wie die echten Systeme (`InsuranceStatusProvider`, `AppointmentService`). Ein Pilot tauscht eine Klasse pro Anbindung.
- Pilot: ein Träger (z. B. PVA Pflegegeld), ein Bundesland, Wissensbasis durch Fachredaktion gepflegt.
- Messung im Pilot: Anteil vollständiger Anträge, Zeit bis zum Antrag, Anrufe an falsche Stellen.

## 7. Wahrscheinliche Fragen

| Frage | Antwort |
|---|---|
| Was, wenn das Modell trotzdem medizinisch berät? | Drei Schichten: feste Regel vor dem Modell, Systemprompt, keine medizinischen Tools. Die Guardrail-Suite misst das (`docs/EVAL.md`). |
| Woher kommen die Fakten? | Aus kuratierten offiziellen Quellen. Jede Aussage zeigt ihre Quelle. Ohne Quelle sagt der Lotse das und eskaliert. |
| Warum nicht ChatGPT? | EU-Modell eines Wiener Anbieters, lokale Embeddings. Der Anbieter ist über eine Variable austauschbar. |
| Wie aktuell ist die Wissensbasis? | Jede Datei hat ein Abrufdatum. Im Pilot pflegt sie eine Fachredaktion. |
| Was kostet der Betrieb? | Ich weiß es nicht. Wir messen Tokens pro Fall im Audit-Log. Die Zahl zeigen wir, wenn wir sie haben. |
| Funktioniert das mit Fotos vom Handy? | Ja, Bilder gehen an das Vision-Modell. Die Demo zeigt das PDF. |

## Features in Demo-Reihenfolge

Siehe die Feature-Tabelle in [PLAN.md](PLAN.md). Must: Login, Chat mit Streaming, Rückfragen, Upload mit Zitaten, Leistungs-Cards, Mein Fall, Pflegegeldantrag, Office-Card, Quellen, Transparenz-Panel, Eskalation, Notfall-Banner, KI-Hinweis, Replay. Should: Englisch, `.ics`-Termin, Kur und Reha, E-Mail-Entwurf. Cut: S4, Einfache Sprache, PWA, Spracheingabe, weitere Formulare, Erstattungskodex.

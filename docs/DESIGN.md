# Designsystem — SV KI-Lotse

Status: Gjergj hat die Richtung am 05.11.2026 freigegeben (D-027). Task #46 setzt Tokens, Komponenten, App-Shell und `/styleguide` um.
Das Token-File ist `frontend/src/app/globals.css`. Die Seite `/styleguide` zeigt alle Tokens, Komponenten und Zustände.
Grundlage: [PLAN.md](PLAN.md), [PITCH.md](PITCH.md), [contracts.md](contracts.md), [guardrails.md](guardrails.md), `backend/app/api/audit.py` und die Team-Skizzen.

## 0. Überarbeitung „Atmosphäre“ (06.11.2026, D-037)

Gjergj hat eine modernere, weitere Optik mit Referenz-Stimmung freigegeben: weicher Verlauf, Glasflächen, mehr Luft. Funktionen, Texte, Logik und API bleiben gleich. Diese Abschnitte gelten vor den älteren Angaben unten.

- **Zwei Designs.** Hell ist Standard (Beamer). Dunkel per Umschalter (Mond/Sonne) im Kopf. `<html data-theme="dark">` schaltet alle Tokens um; ein Inline-Skript setzt das gespeicherte Design vor dem ersten Paint (`localStorage` `lotse-theme`). `dark:` folgt dem Attribut, nie der Systemeinstellung.
- **Atmosphäre.** `--atmosphere`: drei weiche Radialverläufe hinter allem. Hell: Lavendel, Rosé, Minze. Dunkel: Nachtblau bis Pflaume.
- **Glas.** Utility `glass`: `--bg-glass` (hell 72 % Weiß, dunkel 62 % Nachtblau), feine Kante `--border-glass`, Blur 20 px. Für Spalten-Panels, Cards und die Eingabe. Overlays (Sheet, Dropdown, Tooltip) bleiben deckend (`--bg-surface`). Hinter Sheets dimmt `--scrim` in beiden Designs.
- **Neutral** wechselt auf Farbton ≈ 285 (kühles Schiefer). Tannengrün, Ocker und Rot bleiben in Bedeutung und Einsatz gleich.
- **Layout.** Kopf ohne Fläche über dem Verlauf. „Gespräche“ und „Mein Fall“ schweben als runde Glas-Panels mit 12–16 px Abstand. Die Gesprächsspalte ist offen; Nachrichten blenden oben und unten weich aus (`fade-y`). Die Eingabe ist eine große Glasbox: Textfeld oben, darunter Anhang links und „Senden“ rechts. Der Login ist zentriert mit großer Überschrift (`text-display` 44 px).
- **Radien** 16 px für Panels und Cards (`--radius`), 12 px für Elemente. Schatten weich und breit.
- **Notfall** bleibt kräftiges Rot ohne Animation; der Banner ist jetzt rund wie die Panels. Er wird vor jedem KI-Text gerendert (eigener Commit beim Notfall-Event).

Kontrast (WCAG, Glas über dem Seitengrund verrechnet; Text ≥ 4,5:1, Kanten und Fokus ≥ 3:1):

| Paar | Hell | Dunkel |
|---|---|---|
| Text auf Glas | 17,0 | 14,9 |
| Sekundärtext auf Glas | 7,3 | 9,0 |
| Sekundärtext auf stärkstem Verlauf | 5,9 | – |
| Text auf Akzent („Senden“) | 7,1 | 8,8 |
| Akzenttext auf Glas | 7,9 | 10,1 |
| Ockertext auf Ockerfläche | 7,7 | 8,6 |
| Weiß auf Notfallrot | 6,6 | 5,2 |
| Eingabekante auf Glas | 3,9 | 5,0 |

## 1. Richtung „Klare Route“ (freigegeben)

> Ruhig wie ein guter Beratungsschalter: weiße Flächen auf leicht grün getöntem Grund, Tannengrün nur für Hauptaktion, hohe Sicherheit und erledigte Schritte.
> „Mein Fall“ steht als senkrechte Route mit Wegpunkten neben dem Gespräch und zeigt: Hier entsteht ein Weg, kein Chatverlauf.
> Nur Notfall und Grenzen brechen diese Ruhe, mit kräftigem Rot oder Ocker und immer mit Symbol und Klartext.

Grundsätze:

- Die KI-Antwort und ihre Cards sind das größte Element im Lotse-Screen.
- „Mein Fall“ bleibt ab 1024 px Breite immer neben dem Gespräch sichtbar.
- Jeder Screen hat genau eine gefüllte Hauptaktion. Im Lotse-Screen ist das „Senden“. Card-Aktionen sind sekundär.
- Jeder Zustand hat Symbol und Klartext. Farbe ist nie das einzige Signal.
- Beamer zuerst: hoher Kontrast, sichtbare Kanten, keine blassen Grautöne. Helles Design ist Standard; dunkel nur per Umschalter (§0).

## 2. Farben

Notation `oklch()`. Vier Rampen, keine weiteren. Komponenten nutzen nur semantische Tokens.

| Rampe | Farbton (OKLCH) | Bedeutung | Einsatz |
|---|---|---|---|
| Neutral | ≈ 160, sehr geringe Chroma | Struktur | Seitengrund, Flächen, Text, Kanten, technische Fehler, unbekannte Sicherheit |
| Akzent Tannengrün | ≈ 160 | „sicherer Weg“ | Hauptaktion, Links, Fokusring, „Sicherheit: hoch“, „Erledigt“ |
| Ocker | ≈ 75 | „bitte prüfen, Mensch nötig“ | „Sicherheit: mittel“ und „niedrig“, fehlende Felder, „Von Ihnen zu prüfen“, medizinische Grenze, Übergabe |
| Rot | ≈ 25 | „Notfall“, sonst nichts | Notfall-Banner, Notruf-Buttons, Notfall-Badge |

Regeln:

- Rot bedeutet nur Notfall. Technische Fehler und niedrige Sicherheit sind nie rot.
- Ocker ist nie Textfarbe auf Weiß. Ocker erscheint als getönte Fläche mit dunklem Ocker-Text oder als dunkle Fläche mit weißem Text.
- Weißer Text auf Tannengrün, dunklem Ocker und Rot erreicht mindestens 4,5:1.
- Fließtext zielt auf 7:1, Sekundärtext auf mindestens 4,5:1, Eingabe-Kanten auf mindestens 3:1.
- Rot und Grün sind bei Rot-Grün-Schwäche verwechselbar. Notfall und Sicherheit tragen darum immer Symbol und Label.

Semantische Tokens in `globals.css`. Die Tailwind-Klasse steht in der zweiten Spalte. Kontrast gemessen gegen Weiß, falls nicht anders genannt.

| Token | Klasse | Wert | Kontrast |
|---|---|---|---|
| `--bg-page` | `bg-page` | `oklch(0.975 0.006 160)` | – |
| `--bg-surface` | `bg-surface` | `oklch(1 0 0)` | – |
| `--bg-subtle` | `bg-subtle` | `oklch(0.955 0.008 160)` | – |
| `--bg-muted` | `bg-muted` | `oklch(0.93 0.01 160)` | Hover |
| `--border` | `border` (Standard) | `oklch(0.87 0.01 160)` | dekorativ |
| `--border-strong` | `border-border-strong` | `oklch(0.6 0.015 160)` | 3,9:1 (Eingaben) |
| `--text` | `text-text` | `oklch(0.22 0.015 160)` | 17,2:1 |
| `--text-secondary` | `text-text-secondary` | `oklch(0.45 0.015 160)` | 7,4:1 |
| `--accent-solid` | `bg-accent-solid`, `bg-primary` | `oklch(0.45 0.09 160)` | Weiß darauf 7,1:1 |
| `--accent-solid-hover` | `bg-accent-solid-hover` | `oklch(0.4 0.085 160)` | Weiß darauf 8,8:1 |
| `--accent-text` | `text-accent-text` | `oklch(0.42 0.09 160)` | 8,1:1; auf `accent-subtle` 7,1:1 |
| `--accent-subtle` | `bg-accent-subtle` | `oklch(0.95 0.03 160)` | – |
| `--accent-border` | `border-accent-border` | `oklch(0.8 0.06 160)` | dekorativ |
| `--caution-subtle` | `bg-caution-subtle` | `oklch(0.96 0.04 85)` | – |
| `--caution-border` | `border-caution-border` | `oklch(0.8 0.1 80)` | dekorativ |
| `--caution-text` | `text-caution-text` | `oklch(0.42 0.08 70)` | auf `caution-subtle` 7,7:1 |
| `--caution-solid` | `bg-caution-solid` | `oklch(0.47 0.1 65)` | Weiß darauf 7,0:1 |
| `--emergency-solid` | `bg-emergency-solid` | `oklch(0.5 0.19 27)` | Weiß darauf 6,6:1 |
| `--emergency-subtle` | `bg-emergency-subtle` | `oklch(0.96 0.02 25)` | – |
| `--emergency-text` | `text-emergency-text` | `oklch(0.45 0.18 27)` | auf `emergency-subtle` 7,2:1 |
| `--focus-ring` | `ring-ring` | = `--accent-solid` | 6,6:1 auf `bg-page` |

shadcn/ui-Namen zeigen auf diese Tokens (D-028): `primary` → Akzent, `secondary` → `bg-subtle`, `muted`/`accent` → `bg-muted`,
`input` → `border-strong`, `ring` → `focus-ring`, `destructive` → `emergency-solid`. Nutzen Sie in Feature-Code die semantischen Namen.

## 3. Typografie

- Umgesetzt: Systemschrift über `--font-ui` (D-027). Atkinson Hyperlegible Next folgt als lokale Datei über `next/font/local`, sobald sie im Repo liegt.
- Build und Demo-Start brauchen kein Netz für Schriften. Verboten sind `next/font/google` und Font-Links zu einem CDN.
- Fallback: `system-ui, sans-serif`. Fehlt die Schriftdatei, nutzt die App nur diesen Stack. Das blockiert keinen Task.
- Eine Familie, Gewichte 400 und 600. 700 nur im Notfall-Titel.
- `lang="de-AT"` auf `<html>`. Englische Antworten (S5) bekommen `lang="en"` am Nachrichtentext.
- `Intl` mit `de-AT` formatiert Datum, Zeit und Zahlen (zum Beispiel „5. Jänner, 14:32“).
- Typografische Zeichen: „…“, –, …. Telefonnummern mit geschützten Leerzeichen.
- `tabular-nums` für Zähler, Fortschritt, Uhrzeiten und Countdown.

| Rolle | Größe | Zeilenhöhe | Gewicht | Einsatz |
|---|---|---|---|---|
| `display` | 2rem | 1.2 | 600 | Login-Titel |
| `title` | 1.5rem | 1.25 | 600 | Screen-Titel, Notfall-Titel (700) |
| `heading` | 1.125rem | 1.3 | 600 | Card- und Panel-Titel |
| `answer` | 1.125rem | 1.6 | 400 | KI-Antworttext, max. 68ch breit |
| `body` | 1rem | 1.5 | 400 | Nutzernachricht, Card-Inhalt, Schritte |
| `label` | 0.875rem | 1.4 | 600 | Buttons, Badges, Feldlabels |
| `caption` | 0.8125rem | 1.4 | 400 | Zeitstempel, Quellen-Metadaten, Modellname |

Die Rollen sind Tailwind-Klassen: `text-display`, `text-title`, `text-heading`, `text-answer`, `text-body`, `text-label`, `text-caption`.
Sie setzen Größe, Zeilenhöhe und Gewicht. `tabular` setzt Tabellenziffern. `max-w-answer` begrenzt Antworttext auf 68ch.
Neue Größen gehören auch in `frontend/src/lib/utils.ts`, sonst verwirft `cn()` Farbklassen (D-029).

Das Eingabefeld hat auf Mobil 16 px, damit iOS nicht zoomt.

## 4. Abstände, Radien, Tiefe, Bewegung

- 4-px-Raster. Innerhalb einer Gruppe 8 px, zwischen Gruppen 16–24 px, zwischen Abschnitten 32 px.
- Radien: Cards 12 px, Elemente in Cards 8 px, Badges und Chips voll rund. Bei gleichmäßigem Einzug gilt: außen = innen + Abstand.
- Cards haben eine 1-px-Kante und einen leichten Schatten. Sheet und Drawer haben einen deutlichen Schatten.
- Icons kommen nur aus lucide, Strich 1.5 neben Text mit 400, 2 neben Text mit 600.
- Tokens: `--radius` 12 px (`rounded-lg`), `rounded-md` 8 px, `rounded-sm` 6 px. Schatten: `shadow-card` und `shadow-overlay`.
- Bewegung: `Enter` aus `@/components/ui/enter` setzt die Eintrittsbewegung um, mit `index` für die Staffelung. Button-Druck steckt im `Button`.

Bewegung (Werte aus `better-ui`, Umsetzung mit `framer-motion`):

| Moment | Bewegung |
|---|---|
| Button drücken | Skalierung 0.96, 150 ms, `ease-out`, nie bei deaktivierten Buttons |
| Hover, Tab, Listenwahl | höchstens 150 ms, nur `opacity` oder `background-color` |
| Neue Card, neuer Schritt in „Mein Fall“ | Opacity, 12 px `translateY`, 4 px Blur, 300 ms `ease-out`; Schritte 100 ms gestaffelt |
| Verschwinden | 150 ms `ease-out`, −12 px |
| Symbolwechsel (Kopieren → Kopiert) | Spring 0.3 s, `bounce: 0`, Skalierung 0.25 → 1 |
| Notfall-Banner | keine Animation, er steht sofort da |
| `prefers-reduced-motion: reduce` | nur Opacity-Überblendung |

## 5. Layout

```
┌ Kopfzeile: Logo „SV KI-Lotse“ · Badge „KI-Assistent“ · Persona-Menü ────────┐
├ Notfall-Banner (nur bei Red Flag, volle Breite, klebt oben) ────────────────┤
│ Gespräche        │ Gespräch                          │ Mein Fall            │
│ [Neues Gespräch] │ Nachrichten, Cards, Quellen       │ Titel · Für wen      │
│ bisherige        │ Fortschrittszeile                 │ 2 von 6 erledigt     │
│ Gespräche        │ [Anhang] Ihre Nachricht… [Senden] │ Route mit Schritten  │
└──────────────────┴───────────────────────────────────┴──────────────────────┘
```

| Breite | Gespräche | Gespräch | Mein Fall |
|---|---|---|---|
| ≥ 1920 px (Beamer) | Spalte 280 px | flexibel, Text max. 68ch, mittig | Spalte 440 px |
| 1440–1919 px (Laptop) | Spalte 256 px | flexibel, Text max. 68ch | Spalte 360 px |
| 1024–1439 px | Sheet über Menü-Button | flexibel | Spalte 320 px |
| < 1024 px | Sheet über Menü-Button | volle Breite | Sheet über Button „Mein Fall · 3 offen“ |

- Die Breakpoints sind Startwerte. Der Inhalt entscheidet, wann eine Spalte kippt.
- Umgesetzt: `lg` = 1024 px, `laptop` = 1440 px, `beamer` = 1920 px. Spaltenbreiten: `w-nav`, `w-nav-beamer`, `w-case`, `w-case-laptop`, `w-case-beamer`.
- Unter 1440 px öffnet ein Menü-Button in der Kopfzeile die Gespräche. Unter 1024 px öffnet „Mein Fall · 3 offen“ in der Kopfzeile das Sheet.
- Die Shell nutzt `100dvh`. Jede Spalte scrollt für sich. Die Eingabe klebt unten in der Gesprächsspalte.
- Der Transparenz-Drawer öffnet rechts über „Mein Fall“: 480 px breit, auf Mobil volle Breite.
- Bei 320 px Breite und 200 % Zoom scrollt nichts horizontal. Wir polieren nur 1440×900 und 1920×1080.

## 6. Gemeinsame Komponenten

shadcn/ui-Basis unter `frontend/src/components/ui/`: Button, Card, Badge, Textarea, Label, Checkbox, Sheet, Tooltip, Skeleton, ScrollArea, Separator, Avatar, DropdownMenu, Collapsible, Progress, Sonner (Toast).
`TooltipProvider` und `Toaster` hängen im Root-Layout. Ein Toast startet mit `toast()` aus `sonner`.

Umgesetzte Exporte (Task #46):

| Export | Datei | Inhalt |
|---|---|---|
| `Button` | `ui/button.tsx` | Varianten `default` (Hauptaktion), `secondary`, `outline`, `ghost`, `link`, `emergency`; Größen `default` (40 px), `sm`, `lg` (48 px), `icon`, `icon-sm` |
| `Badge` | `ui/badge.tsx` | Varianten `neutral`, `outline`, `accent`, `caution`, `caution-strong`, `emergency` |
| `EmptyState`, `ErrorState` | `ui/state.tsx` | Leerzustand mit Symbol; Fehler neutral mit „Erneut versuchen“ und `role="alert"` |
| `Enter` | `ui/enter.tsx` | Eintrittsbewegung mit `framer-motion`, reduzierte Bewegung nur Opacity |
| `AppShell` | `layout/app-shell.tsx` | Slots `header`, `navigation`, `conversation`, `casePanel`, `emergencyBanner`; `casePanelLabel` |
| `AppHeader`, `Wordmark`, `AiAssistantBadge` | `layout/app-header.tsx` | Kopfzeile mit Logo, Badge „KI-Assistent“ und Slot `actions` |

Die Feature-Tasks bauen die übrigen Komponenten der folgenden Tabelle aus diesen Bausteinen.

| Komponente | Zweck |
|---|---|
| `AppShell` | Kopfzeile, drei Spalten, Banner-Slot, Breakpoint-Verhalten |
| `ConversationNav` | „Neues Gespräch“, Liste mit Titel, Datum und Badge „3 offen“, aktiver Eintrag mit `aria-current` |
| `PersonaCard` | Persona-Wahl im Login |
| `Composer` + `AttachmentChip` | Eingabe, Büroklammer, Upload-Status, „Senden“ |
| `MessageBubble` | Nutzernachricht (getönte Blase, Endseite) und KI-Antwort (ohne Blase, volle Breite, Absender „Lotse (KI)“) |
| `ProgressLine` | eine Zeile mit Spinner und Label aus `status` oder `tool.called` |
| `AnswerFooter` | `AnswerStateBadge`, `SourceChips`, `ConfidenceBadge`, Modellname, Button „Warum diese Antwort?“ |
| `AnswerStateBadge` | Antwortzustand aus §7.1, getrennt von der Sicherheit |
| `ConfidenceBadge` | Sicherheit aus §7.2, nur aus Backend-Daten |
| `ResultCard` | Grundgerüst aller Cards: Symbol, Titel, Badge, Inhalt, sekundäre Aktionen |
| `DocumentSummaryCard` + `QuoteBlock` | wörtliche Zitate aus dem Dokument |
| `LeistungCard`, `FormDraftCard`, `OfficeCard`, `EscalationCard` | Card-Typen aus contracts.md §2 |
| `ProviderListCard`, `AppointmentCard` | optional, immer mit `DemoDataBadge` |
| `CasePanel` + `CaseStepItem` + `StepStatusBadge` | „Mein Fall“ als Route |
| `EmergencyBanner` | Notfall vor jedem KI-Text |
| `TransparencyDrawer` | „Warum diese Antwort?“ |
| `CopyButton` | Kopieren mit Symbolwechsel und Ansage |
| `AiNotice`, `DemoDataBadge` | KI-Hinweis (Art. 50) und Kennzeichnung von Demo-Daten |
| `EmptyState`, `ErrorState` | Leer- und Fehlerzustand mit „Erneut versuchen“ |

Jede asynchrone Komponente hat vier Zustände: Laden (Skeleton oder Fortschrittszeile), leer, Inhalt, Fehler mit „Erneut versuchen“.

## 7. Antwortzustand und Sicherheit

Das sind zwei getrennte Achsen. Der Antwortzustand sagt, was gerade mit der Antwort geschieht. Die Sicherheit bewertet die Beleglage einer gespeicherten Antwort.
Eine Antwort kann darum zugleich „Medizinische Frage“ und „Sicherheit: niedrig“ zeigen.

### 7.1 Antwortzustand

Das Frontend leitet den Zustand aus SSE-Events ab. Nach dem Neuladen liest es ihn aus `GET /api/messages/{id}/transparency`.

| Zustand | Auslöser im Stream | Auslöser nach Neuladen | Symbol | Label | Farbe |
|---|---|---|---|---|---|
| Lotse arbeitet | `status`, `tool.called` | – | `Loader2` | `label` aus dem Event | Neutral |
| Fertig | `message.completed` | gespeicherte Nachricht | kein Badge | – | – |
| Medizinische Grenze | `escalation` mit `medical_question` | `escalation.reason_code` | `ShieldAlert` | „Medizinische Frage – an Fachleute übergeben“ | Ocker |
| Übergabe | `escalation` mit anderem Grund | `escalation.reason_code` | `Handshake` | „An einen Menschen übergeben“ | Ocker |
| Notfall | `emergency` | `guardrails` mit `emergency` oder `social_crisis` | `Siren` | „Notfall“ | Rot |
| Fehler | `error` | `entries` mit `event_type = error` und `detail.code` | `CircleAlert` | „Antwort fehlgeschlagen“ + „Erneut versuchen“ | Neutral, kräftige Kante |
| Ausgelastet | `error` mit `retry_after` | – | `Clock` | „Der Lotse ist gerade ausgelastet. Neuer Versuch in 12 s.“ | Neutral |

- „Lotse arbeitet“ erscheint nur in der `ProgressLine`, die anderen Zustände im `AnswerStateBadge`.
- Notfall hat Vorrang vor allen anderen Badges. Der `EmergencyBanner` bleibt auch bei einem späteren `error` stehen.

### 7.2 Sicherheit

Das Backend berechnet `confidence.level` und `confidence.reason`. Das Frontend übernimmt beide unverändert und berechnet nichts selbst.

| Quelle | Symbol | Label | Farbe |
|---|---|---|---|
| `level = hoch` | `SignalHigh` | „Sicherheit: hoch“ | Tannengrün, getönt |
| `level = mittel` | `SignalMedium` | „Sicherheit: mittel“ | Ocker, getönt |
| `level = niedrig` | `SignalLow` | „Sicherheit: niedrig“ | Ocker, dunkle Fläche |
| Daten laden | Skeleton | „Sicherheit wird geladen…“ (für Screenreader) | Neutral |
| Daten fehlen | `CircleDashed` | „Sicherheit nicht verfügbar“ | Neutral |

- Die Quellenanzahl ist kein Sicherheitssignal. Zwei Quellen mit einem fehlgeschlagenen Werkzeug ergeben im Backend „mittel“.
- Die `SourceChips` zeigen Quellen als Fakt, ohne Wertung. Es gibt kein Label „Belegt“ und kein grünes Quellen-Badge.
- `confidence.reason` steht als Tooltip am Badge und als Satz im Drawer.
- Der Drawer ergänzt: „Die Stufe beschreibt die Beleglage dieser Antwort. Sie garantiert keine Richtigkeit.“
- Der `EmergencyBanner` zeigt nie eine Sicherheit. Der `AnswerFooter` der Notfall-Antwort zeigt den Backend-Wert.

### 7.3 Transparenzdaten laden

`GET /api/messages/{id}/transparency` liefert `confidence`, `model`, `provider`, `sources`, `tools`, `guardrails`, `escalation` und `entries`.
`model` und `provider` können `null` sein.

- Das Frontend fragt die Daten einmal je Nachricht ab und speichert sie je `message_id`. Beim Öffnen eines Gesprächs gilt das für jede KI-Antwort.
- Im Stream fragt es erst nach `message.completed`. Vorher ist die Nachricht nicht gespeichert, und die Route antwortet 404.
- Nach `error` fragt es nur, wenn schon Text sichtbar ist. Dann hat das Backend die Teilantwort gespeichert.

| Lage | `AnswerFooter` | Drawer |
|---|---|---|
| Antwort läuft | kein Footer, nur `ProgressLine` | nicht erreichbar |
| Laden | Quellen aus dem Event `sources`, Skeleton für Badge und Modell | Skeleton |
| Daten da | Badge aus §7.2, Modellname | alle Abschnitte aus §8 „Transparenz“ |
| `model` ist `null` | „Modell nicht erfasst“ | „Modell nicht erfasst“ |
| `provider` ist `null` | keine Anzeige | kein Betreiberhinweis |
| `sources` ist leer | „Keine Quellen“ (Neutral) | „Für diese Antwort liegen keine Quellen vor.“ |
| `entries` ist leer | Badge aus §7.2 | „Für diese Antwort liegen keine Protokolldaten vor.“ |
| Fehler oder Timeout | „Sicherheit nicht verfügbar“, „Modell nicht verfügbar“ | „Die Angaben zu dieser Antwort konnten nicht geladen werden.“ + „Erneut versuchen“ |
| 404 | wie Fehler, ohne neuen Versuch | „Für diese Antwort liegen keine Protokolldaten vor.“ |

- Ein Fehler dieser Abfrage lässt die Antwort, die Cards und den Banner unverändert stehen.
- Das UI erfindet nie eine positive Sicherheit, einen Modellnamen oder einen Betreiber. Es zeigt auch keinen Standardwert aus der Konfiguration.

## 8. Interaktionen S1 — Golden Path

**Persona-Login (`/login`)**
- Der Screen zeigt Produktname, einen Satz Nutzen, `AiNotice` und „Demo mit erfundenen Personen. Keine echten Daten.“
- Drei `PersonaCard`s: Initialen, Name, Alter, Lage in einem Satz, Badge „Demo-Persona“.
- Die ganze Card ist ein `<button>` mit dem Namen „Als Maria Berger anmelden“.
- Nach dem Klick zeigt die Card einen Ladezustand. Dann öffnet sich `/chat/[id]`. Bei einem Fehler zeigt die Card eine Meldung mit „Erneut versuchen“.

**Leerer Lotse-Screen**
- Das Gespräch zeigt eine Begrüßung mit Vornamen und einen Satz: Was der Lotse tut und was nicht.
- „Mein Fall“ zeigt `Route`-Symbol und „Noch keine Schritte. Beschreiben Sie Ihre Lage. Der Lotse legt hier Ihre nächsten Schritte an.“
- Der Fokus liegt im Eingabefeld.

**Eingabe**
- Das Textfeld wächst von 1 auf 6 Zeilen. Label (für Screenreader): „Ihre Nachricht an den Lotsen“. Platzhalter: „Beschreiben Sie Ihre Lage…“.
- Enter sendet. Umschalt+Enter macht eine neue Zeile.
- Büroklammer: Icon-Button mit `aria-label` und Tooltip „Dokument anhängen“. „Senden“ ist der gefüllte grüne Button.
- Die Nutzernachricht erscheint sofort. Während der Lotse antwortet, bleibt das Textfeld bearbeitbar. „Senden“ zeigt „Lotse antwortet…“ und ist `aria-disabled`.
- `text.delta` erscheint direkt, ohne Tippeffekt. Die `ProgressLine` steht unter dem wachsenden Text (`role="status"`). Bei `message.completed` verschwindet sie.
- Der Screen scrollt nur mit, wenn die Nutzerin unten ist. Sonst erscheint der Button „Zu neuen Inhalten“.

**Upload-Fortschritt**
- Erlaubt sind PDF und Fotos. Der Upload startet bei der Dateiwahl.
- Der `AttachmentChip` über dem Textfeld zeigt Dateisymbol, Dateinamen (gekürzt, voller Name im Tooltip), Status und „Entfernen“.
- Statusfolge: „Wird hochgeladen…“ → „Wird gelesen…“ (unbestimmter Balken, das Frontend fragt alle 1,5 s nach) → „Bereit“ (`CircleCheck`).
- Sendet die Nutzerin vor „Bereit“, erscheint die Nachricht mit Chip. Die `ProgressLine` zeigt „Dokument wird gelesen…“. Der Turn startet bei `ready` von selbst.
- Bei `failed` oder Timeout zeigt der Chip „Dokument konnte nicht gelesen werden“ mit „Erneut versuchen“ und „Ohne Dokument senden“.

**Zitate (`DocumentSummaryCard`)**
- Titel „Aus Ihrem Dokument“, darunter Dateiname · Aussteller · Datum.
- Ein `QuoteBlock` je Empfehlung: Themen-Badge (z. B. „Pflegegeld“), Zitat wörtlich in „…“, Akzentlinie an der Startseite, Fußzeile „Abschnitt 8“.
- Hinweiszeile mit `Quote`-Symbol: „Wörtlich zitiert. Der Lotse bewertet keine Befunde.“
- `confidence_note` erscheint als Ocker-Hinweis „Nicht lesbar: …“.
- Link „Dokument öffnen“ öffnet das Original in einem neuen Tab.

**Leistungen und Mein Fall**
- `LeistungCard`: Titel, Kurztext, Bedingungen als Liste, „Könnte in Frage kommen. Die zuständige Stelle entscheidet.“, Stellen-Hinweis, Quellen-Chip.
- Kopf von „Mein Fall“: Fall-Titel, „Für: Mutter“, Zusammenfassung (2 Zeilen, aufklappbar), „2 von 6 erledigt“ mit Fortschrittsbalken.
- Die Route ist eine `<ol>`. Eine senkrechte Linie verbindet die Wegpunkte. Der Wegpunkt zeigt den Status als Symbol und Text:
  `Circle` „Offen“, `CircleDot` „In Arbeit“, `CircleCheck` „Erledigt“, `CircleSlash` „Blockiert“.
- Bei `case.updated` erscheinen neue Schritte 100 ms gestaffelt mit Badge „Neu“. Das Badge bleibt bis zum nächsten Turn, ohne Timer.
- Eine Live-Region sagt „Mein Fall: 5 neue Schritte.“. Auf Mobil wechselt der Zähler am Button „Mein Fall · 3 offen“, dazu kommt ein Toast.
- Abhaken: Checkbox aus der gemeinsamen UI, Label = Schritt-Titel. Das UI ändert den Status sofort und sendet `PATCH`. Bei einem Fehler setzt es zurück und zeigt den Toast „Änderung nicht gespeichert. Erneut versuchen.“
- Aufklappen zeigt Beschreibung, `due_hint` und „Zur Card im Gespräch“. Der Link scrollt zur Card und fokussiert sie.
- Schritte der Kategorie `form` zeigen bis zum Abhaken das Ocker-Badge „Von Ihnen zu prüfen“.

**Formular und PDF (`FormDraftCard`)**
- Titel „Antrag auf Pflegegeld – Entwurf“, Aussteller „PVA“, Ocker-Badge „Von Ihnen zu prüfen“ mit `ClipboardCheck`.
- Vor den Feldern steht der Hinweis: „Der Lotse hat den Antrag vorausgefüllt. Prüfen Sie jedes Feld. Sie unterschreiben und senden ihn selbst. Die PVA entscheidet.“
- Drei Gruppen mit Zähler:
  - „Ausgefüllt (12)“: Label, Wert, Herkunft „aus dem Gespräch“, „aus dem Dokument“ oder „aus Ihrem Profil“. Ab 6 Feldern eingeklappt mit „Alle 12 anzeigen“.
  - „Fehlt noch (3)“: `CircleHelp`, Ocker, Hinweistext.
  - „Füllen andere aus (2)“: `UserRound`, Hinweis wie „Ärztin oder Arzt“.
- Aktion „PDF herunterladen“ (sekundär, `Download`). Nach dem Klick zeigt der Button „PDF wird erstellt…“, dann startet der Download. Bei einem Fehler erscheint ein Hinweis mit „Erneut versuchen“.

**Zuständige Stelle (`OfficeCard`)**
- Organisation, Name, Adresse, Telefon als `tel:`-Link, Öffnungszeiten, Links „Website“ und „Auf der Karte“ (neuer Tab, `ExternalLink`).
- Stellen sind echte Daten und tragen kein Demo-Badge. Ärztinnen und Termine tragen immer „Demo-Daten“ (`FlaskConical`).
- Optional: `AppointmentCard` mit Zeit, Ort und „Termin speichern (.ics)“. Kein Kalender.

**Transparenz**
- Jede KI-Antwort endet mit dem `AnswerFooter`: `AnswerStateBadge` (falls nötig), Quellen-Chips (Herausgeber · Titel, max. 3, dann „+2 weitere“), `ConfidenceBadge`, `model`, Button „Warum diese Antwort?“ (`ScanSearch`).
- Der Drawer ist ein Sheet. Er hält den Fokus, schließt mit Esc und gibt den Fokus an den Button zurück.
- Inhalt in dieser Reihenfolge:
  1. Sicherheit: großes `ConfidenceBadge`, `confidence.reason` und der Satz zur Beleglage aus §7.2.
  2. Quellen aus `sources`: Titel, Herausgeber, Link. Dokument-Zitate mit Abschnitt aus der `document_summary`-Card der Nachricht.
  3. Schritte des Lotsen: Wissenssuche aus `entries` (`retrieval`, Feld `summary`), Aktionen aus `tools` (`label`, `ok` als Symbol und Text). Ein Eintrag in `guardrails` erscheint als „Notfallregel ausgelöst“.
  4. Modell: `model` und `provider`. Der Betreiberhinweis „EU-Modell, Wien“ erscheint nur, wenn `provider` den Wert `eustella` hat.
  5. Eskalationsgrund aus `escalation`, falls vorhanden.
  6. KI-Hinweis: „Diese Antwort hat eine KI erstellt. Sie ersetzt keine Beratung. Die zuständige Stelle entscheidet.“
- Das Feld `retrieval` der Route ist derzeit immer leer. Darum liest der Drawer die Wissenssuche aus `entries`.
- Lade-, Leer- und Fehlerzustände stehen in §7.3.

## 9. Interaktionen S2 — Medizinische Grenze

- Die Antwort lehnt in einem Satz ab. Der `AnswerFooter` zeigt „Medizinische Frage – an Fachleute übergeben“ (`ShieldAlert`, Ocker) und daneben den `ConfidenceBadge`.
- Die `EscalationCard` erscheint beim Event `escalation` unter dem Text. So springt nichts über dem Text.
- Kopf: Symbol und Grund im Klartext. Zuordnung der `reason_code`:
  `medical_question` „Medizinische Frage“, `legal_uncertainty` „Rechtliche Frage“, `no_source` „Keine verlässliche Quelle“,
  `user_stuck` „Wunsch nach persönlicher Beratung“, `social_crisis` „Soziale Notlage“, `emergency` „Notfall“.
- Kontakt aus `target`: Name, Telefon als großer `tel:`-Link, Öffnungszeiten, `note` (z. B. „außerhalb der Ordinationszeiten 1450“).
- Übergabe-Zusammenfassung unter der Überschrift „Zum Vorlesen am Telefon“. Lesbarer Fließtext in getönter Fläche, Zeilenumbrüche bleiben.
- Satz darunter: „Die Zusammenfassung enthält nur Ihre Angaben und wörtliche Zitate, keine Diagnose.“
- „Zusammenfassung kopieren“ (sekundär, `CopyButton`):
  - Erfolg: `Copy` wechselt zu `Check`, das Label zeigt „Kopiert“. Eine Live-Region sagt „Zusammenfassung kopiert.“.
  - Fehler: Das UI markiert den Text und zeigt „Bitte mit Strg+C kopieren.“.
- Bringt `case.updated` einen Schritt der Kategorie `escalation`, zeigt „Mein Fall“ ihn mit `Handshake`-Symbol.

## 10. Interaktionen S3 — Notfall

- Das Event `emergency` kommt vor jedem `text.delta`. Der `EmergencyBanner` erscheint sofort und ohne Animation.
- Position: volle Breite unter der Kopfzeile, über allen Spalten, klebt oben. Die Scroller bekommen `scroll-padding` in Bannerhöhe.
- Inhalt: `Siren`-Symbol, Wort „Notfall“, Titel „Bitte holen Sie sofort Hilfe“, `message` aus dem Event.
- Das Backend sendet dieses Event auch bei einer sozialen Krise. Der Banner enthält darum keine feste Nummer. Alle Nummern kommen aus `contacts`.
- Je Kontakt aus `contacts` ein großer `tel:`-Button mit Nummer und Name, z. B. „144 anrufen – Rettung“. Mindesthöhe 48 px.
- Rote Fläche, weißer Text, fetter Titel. Symbol und Wort „Notfall“ tragen die Bedeutung auch ohne Farbe.
- `role="alert"` sagt den Banner an. Der Fokus bleibt im Eingabefeld. Im DOM steht der Banner vor `<main>`.
- „Hinweis verkleinern“ macht eine kompakte rote Leiste mit „Notfall“ und dem ersten Kontakt. Sie bleibt für das ganze Gespräch. Nichts blendet sich von selbst aus.
- Die kurze KI-Antwort folgt normal darunter. Ihr `AnswerFooter` zeigt das Badge „Notfall“ und den `ConfidenceBadge`.
- Eine Notfall-Antwort hat keine Quelle. Das Backend meldet darum „niedrig“. Das UI zeigt diesen Wert unverändert.
- Auf Mobil stehen die Buttons untereinander in voller Breite.

## 11. UI-Texte

- Deutsch, Sie-Form, Domänenwörter: Pflegegeld, Antrag, Leistung, zuständige Stelle, Entlassungsbrief, Mein Fall.
- Kein Entwicklerjargon auf dem Screen: nicht „Tool“, „API“, „Token“, „LLM“, „Fehler 500“. „Modell“ steht nur im `AnswerFooter` und im Drawer.
- Ansprüche immer als Möglichkeit: „könnte in Frage kommen“. Die Stelle entscheidet.
- Seitentitel: „Anmelden – SV KI-Lotse“ und „<Gesprächstitel> – SV KI-Lotse“. Favicon und Logo: lucide `Compass` in Tannengrün.

| Ort | Text |
|---|---|
| Kopfzeile | Badge „KI-Assistent“, Tooltip „Antworten können Fehler enthalten. Die zuständige Stelle entscheidet.“ |
| Persona-Menü | „Demo-Persona“, „Abmelden“ |
| Gesprächsliste leer | „Noch keine Gespräche.“ |
| Allgemeiner Fehler | „Das hat nicht geklappt. Bitte versuchen Sie es erneut.“ + „Erneut versuchen“ |
| Keine Verbindung | „Keine Verbindung zum Lotsen. Prüfen Sie die Verbindung und versuchen Sie es erneut.“ |

## 12. Do and don't

| Do | Don't |
|---|---|
| Nur Tokens aus diesem Dokument und dem Tokens-File | Hex-Farben, px-Schriftgrößen, Einzelabstände im Code |
| Nur shadcn/ui-Komponenten und die Komponenten aus §6 | einen zweiten Button oder eine zweite Card bauen |
| Symbol + Label bei jedem Zustand | Zustand nur über Farbe |
| Sicherheit nur aus `confidence` des Backends | Sicherheit aus der Quellenanzahl ableiten oder ohne Daten positiv anzeigen |
| Rot nur für Notfall | Rot für Validierung, technische Fehler oder niedrige Sicherheit |
| Schrift aus dem Repo oder Systemschrift | Schriften aus dem Netz beim Build oder Demo-Start |
| Echte synthetische Demo-Daten auf jedem Screen | leere Tabellen, „test 123“, Lorem ipsum |
| ruhige weiße Flächen, klare Kanten | `Sparkles`-Symbol, Glitzer, Verläufe, Glas-Effekte, dunkles Theme |

## 13. Offene Punkte

- Der Orchestrator schreibt `provider` nicht ins Audit. Die Route liefert darum derzeit `null`, und der Betreiberhinweis bleibt verborgen.
- Die REST-API speichert das `emergency`-Event nicht als Feld. Das Audit hält nur `guardrails` und `contact_ids`. Nach dem Neuladen zeigt das UI darum das Notfall-Badge, aber keinen Banner mit Kontakten.
- Der Sicherheits-Grund bei Notfall lautet „Es fehlt eine ausreichende Quelle“. Das Team prüft in der Demo, ob dieser Satz neben dem Banner verständlich bleibt.
- Die Schriftdatei Atkinson Hyperlegible Next fehlt noch. Ein Folge-Task legt sie ab und prüft die Tabellenziffern.
- Task #46 hat die Farbpaare rechnerisch aus OKLCH gemessen (WCAG 2.x). Eine Messung am echten Beamer steht aus.
- Die Startseite `/` ist ein Platzhalter ohne Aktion. Der Login-Task ergänzt „Anmelden“ zusammen mit der Route `/login`.

## 14. Gemeinsame Grundlage: Task #51

Alle Komponenten behalten ihre Exporte und Props.

| Ort | Vorher | Nachher | Zweck |
|---|---|---|---|
| `AppHeader`, `AppShell` | Die Kopfzeile erzwingt eine Zeile. | Die Kopfzeile erlaubt Umbrüche. Der mobile Fall-Button erhält eine eigene Zeile. | Inhalte passen auf schmale Ansichten. |
| `AppShell` | Die wiederholte Navigation hat keinen Sprunglink. | „Zum Gespräch“ fokussiert die Gesprächsspalte über eine eindeutige ID. | Tastaturnutzer überspringen die Navigation. |
| `/styleguide` | Farbfelder stehen auch mobil nebeneinander. Die Aufklappfläche hat eine feste Breite. | Farbfelder stehen mobil untereinander. Die Aufklappfläche bleibt innerhalb ihrer Spalte. | Die Vorschau vermeidet horizontales Überlaufen. |
| `Badge` | Labels bleiben einzeilig und können abgeschnitten werden. | Labels dürfen umbrechen. Symbole behalten ihre Größe. | Lange Zustände bleiben lesbar. |
| `SheetHeader` | Der Schließen-Button überlagert lange Titel. | Der Kopf reserviert Platz für den Schließen-Button und behält seine Höhe. | Titel und Schließen-Button bleiben getrennt. |
| `Progress` | Die Dauer bleibt trotz reduzierter Bewegung aktiv. | Übergang und Dauer gelten nur ohne reduzierte Bewegung. | Der Balken bewegt sich bei reduzierter Bewegung nicht. |
| `Progress` | Radix erhält den angezeigten Wert nicht. | Radix erhält `value` und setzt `aria-valuenow` sowie den Status. | Assistive Technik erhält den tatsächlichen Fortschritt. |

### Regressionen

`frontend/e2e/shell.spec.ts` prüft die gemeinsame Grundlage ohne Backend und ohne Feature-Vorschauen.

- Desktop: `/`, `/styleguide` und die eingebettete Shell bei 1440×900 und 1920×1080.
- Mobil: 320, 390 und 768 px; Sprunglink, Tab-Reihenfolge und beide Sheets.
- Sheets: Fokusbegrenzung, Escape, Schließen-Button und Fokus-Rückkehr zum ursprünglichen Auslöser.
- Tablet: Bei 1024 px bleibt „Mein Fall“ sichtbar. Die Navigation öffnet als Sheet.
- Fortschritt: Der Fortschrittsbalken nennt seinen angezeigten Wert.
- Reduzierte Bewegung: Skeleton, Lade-Symbol, Fortschritt, Sheets, Menü, Tooltip und neue Schritte.
- Die Bewegungsprüfung erkennt auch einzelne CSS-Eigenschaften für Verschiebung, Skalierung und Rotation.

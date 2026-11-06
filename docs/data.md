# Data — sources, seeds, knowledge base

## 1. Rules

- **Only synthetic or public data.** The SV-Box data is public by the organisers' rules and may be committed. Real personal data never.
- **Every knowledge fact has a source URL** from an official site.
- **Synthetic providers** (doctors, care services) are invented and marked `demo: true`. Real **public offices** (ÖGK, PVA, FSW) may be listed with their public contact data.
- Raw downloads stay outside git (`data/raw/`, `data/svbox/` are gitignored). Copy only the files we use into `backend/seed/`.

## 2. SV-Box (organiser data)

Local copy: `~/Desktop/KI_Challenge/_KI Challenge Daten Use Case 1/` (each teammate downloads their own; the link and password are in the organiser docx, which is **not** in git).

| Folder | File | Use |
|---|---|---|
| Befunde | `Entlassungsbefund.pdf` | **Golden path.** Synthetic discharge letter for Anna Berger (78, Wien 1030, ÖGK, lives alone). Section 6.3 recommends mobile Hauskrankenpflege; 7 recommends checking stationary oncological Reha; 8 lists Reha, Pflegegeld, mobile care (Wien), Rezeptgebührenbefreiung, transport to radiotherapy. Text-based PDF. |
| Befunde | `Impfpass.pdf` | e-Impfpass of a test patient (SVNr 123456789). Use for S4/S5 (vaccination offers). |
| Befunde | `Röntgen Befund*.pdf`, `Befund bildgebende Diagnostik.pdf` | Guardrail tests: the Lotse must **not** interpret them. |
| Anträge und Formulare | `PAL080_0125_Mpfl_052026.pdf` | **PVA Antrag auf Pflegegeld (BPGG)**, AcroForm, 8 pages, 102 fields. Golden path form. |
| Anträge und Formulare | `Antrag Kur und Reha.pdf` | Antrag auf Rehabilitations-, Kur- bzw. Erholungsaufenthalt, AcroForm, 96 fields. |
| Anträge und Formulare | `Reha_n_Unfall_052026.pdf` | Anschlussheilverfahren / Reha nach Unfall — filled by the hospital, so the Lotse only explains it. 59 fields. |
| Anträge und Formulare | `fsw-antrag-auf-foerderung-von-leistungen…pdf` | FSW (Wien) Antrag auf Förderung von Leistungen (mobile care etc.), 13 pages, 122 fields. |
| Anträge und Formulare | `FSW-Antrag-Beilage-Einrichtungswunsch…pdf` | FSW attachment: preferred facility, 13 fields. |
| Anträge und Formulare | `Bedarfsmeldung-Senior_innen-Wohngemeinschaft…pdf` | FSW senior shared housing, 21 fields. |
| Anträge und Formulare | `Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf` | ÖGK Wien travel cost subsidy for insured with Rezeptgebührenbefreiung, 13 fields. Matches section 8 of the letter. |
| Leistungskataloge | `Serviceratgeber-2026…pdf` | Service guide brochure → KB source. |
| Leistungskataloge | ÖGK / Zahnärzte Honorarordnung | Background only; maybe for "is this covered" questions. |
| Medikamenten Erstattungskodex | `*.txt` | Reimbursement code. Nice-to-have, **administrative use only**. |

All seven forms are AcroForms, so `pypdf` can fill them.

**Priority for form field maps:** 1. PVA Pflegegeld, 2. Kur und Reha, 3. Fahrtkostenzuschuss, 4. FSW Förderung.

## 3. Seed files (`backend/seed/`)

```
backend/seed/
├── personas.json             # 3 personas + profiles (see product.md §6)
├── leistungen.json           # structured Leistungen catalogue
├── offices.json              # real public offices (Wien first)
├── providers.json            # SYNTHETIC providers, demo: true
├── sv_register.json          # SYNTHETIC SV register for the simulated SV data query (D-041)
├── escalation_contacts.json  # hotlines, see guardrails.md §3.2
├── forms/
│   ├── registry.json         # form_id → file, title, issuer, leistung_ids
│   ├── field_maps/<form_id>.json   # semantic key → AcroForm field name, label, filled_by
│   └── pdf/<form_id>.pdf     # copied from SV-Box
├── documents/                # sample uploads for demo and tests (Entlassungsbefund.pdf, Impfpass.pdf, a phone photo of page 1)
├── kb/<category>/<slug>.md   # knowledge base markdown
└── fixtures/*.sse            # recorded SSE streams for frontend dev
```

The backend seeds on startup if the `users` table is empty. `uv run python -m app.seed --reset` reseeds.

### `leistungen.json` entry
```json
{
  "id": "pflegegeld",
  "title": "Pflegegeld",
  "category": "pflege",
  "short": "Monatlicher Beitrag zu pflegebedingten Mehraufwendungen.",
  "conditions": [
    "Ständiger Betreuungs- und Hilfsbedarf wegen einer Behinderung oder Krankheit",
    "voraussichtlich mindestens 6 Monate",
    "Pflegebedarf von mehr als 65 Stunden im Monat (Stufe 1)",
    "gewöhnlicher Aufenthalt in Österreich"
  ],
  "office_kind": "pension_insurer",
  "form_ids": ["pva_pflegegeld"],
  "documents_needed": ["Ausgefülltes Antragsformular", "Aktuelle ärztliche Befunde (falls vorhanden)"],
  "source_url": "https://www.oesterreich.gv.at/..."
}
```
*(Values are an example; curators must verify every condition against the linked source.)*

### KB markdown file
```markdown
---
title: Pflegegeld – Antrag und Voraussetzungen
source_url: https://www.oesterreich.gv.at/...
publisher: oesterreich.gv.at
category: pflege
bundesland: null          # or "Wien"
leistung_ids: [pflegegeld]
retrieved: 2026-11-05
---

## Wer bekommt Pflegegeld?
…plain German, paraphrased, no copy-paste of whole pages…

## Wo stelle ich den Antrag?
…
```

## 4. Knowledge base coverage (minimum for the demo)

| Category | Topics | Sources |
|---|---|---|
| `pflege` | Pflegegeld (Stufen, Antrag, Begutachtung), Pflegekarenz/-teilzeit, mobile Dienste Wien (FSW), 24-h-Betreuung, Angehörigenentlastung, Pflegeberatung, Hilfsmittel | oesterreich.gv.at, pv.at, fsw.at, sozialministerium.at |
| `reha` | Rehabilitation (medizinisch), Antrag Kur und Reha, onkologische Reha, Anschlussheilverfahren, Zuständigkeit PVA vs. ÖGK | pv.at, oegk.at, sozdok.at |
| `kosten` | Rezeptgebührenbefreiung, Fahrtkostenzuschuss, Krankentransport, Selbstbehalte | oegk.at |
| `vorsorge` | Vorsorgeuntersuchung, Impfungen (Erwachsene, Kinder), Früherkennung, Bewegungsangebote (z. B. "Bewegt im Park"), Gesundheitskurse | gesundheit.gv.at, oegk.at, svs.at |
| `kind` | Eltern-Kind-Pass, kostenfreies Kinderimpfprogramm, Familienberatung, Kinder-Reha, Familienleistungen | oesterreich.gv.at, gesundheit.gv.at |
| `organisation` | Zuständige Träger (ÖGK, BVAEB, SVS, PVA), e-card, ELGA, Bescheid und Klage beim Arbeits- und Sozialgericht, 1450 | oesterreich.gv.at, sozialversicherung.at |

Aim: ~40 KB files, ~15 Leistungen in `leistungen.json`, all Wien offices relevant to the golden path.

### Curation with an agent
Ask your agent to: open the official page, write a paraphrased markdown file in the format above (no wholesale copying), keep facts exact, put the URL in front matter, and list anything uncertain under `## Offene Punkte`. A human checks numbers (amounts, hours, deadlines) before merging.

## 5. Personas (`personas.json`)

```json
[
  { "persona_id": "maria", "display_name": "Maria Berger", "tagline": "Pflegt ihre Mutter nach dem Spitalsaufenthalt",
    "avatar_emoji": "👩", "svnr": "1234020674", "profile": { "language": "de", "depth": "short" },
    "extra": { "relative": { "name": "Anna Berger", "relation": "mother", "date_of_birth": "1948-03-14",
               "address": "Musterstraße 12, 1030 Wien", "insurer": "OEGK" } } },
  { "persona_id": "stefan", "display_name": "Stefan Gruber", "tagline": "Selbstständig, will gesünder leben",
    "avatar_emoji": "🧑", "svnr": "4564200188", "profile": { "language": "de", "depth": "detailed" } },
  { "persona_id": "elif", "display_name": "Elif Yılmaz", "tagline": "Mutter eines 2-jährigen Kindes",
    "avatar_emoji": "👩‍👧", "svnr": "7898110995", "profile": { "language": "en", "depth": "short" } }
]
```

`personas.json` holds only app settings (`language`, `depth`) and user input (`extra.relative`).
The seed takes Bundesland, PLZ, Versicherungsträger and Geburtsdatum from the simulated SV data query (D-041).

### `sv_register.json` (simulated SV data query)

`MockSvDataService` (`backend/app/providers/mock_sv_data.py`) reads this file, keyed by SV-Nummer.
It stands in for an SV data interface that the team cannot use.

- **All SV-Nummern are synthetic.** Every entry has `"synthetic": true`. Names and streets are invented.
- Format: 10 digits `LLLP DDMMYY`: serial number, check digit, birth date.
- Check digit: digits 1–3 and 5–10 carry the weights 3, 7, 9, 5, 8, 4, 2, 1, 6. The check digit is the sum modulo 11. Remainder 10 is never a valid number. Source: Anfragebeantwortung [4690/AB XXIII. GP](https://www.parlament.gv.at/dokument/XXIII/AB/4690/fnameorig_136871.html) (BMGFJ, 2008).
- The synthetic numbers pass the check digit so the format looks right. They are not assigned to anyone we know of.
- Elif's child Deniz is co-insured with her. Anna Berger is insured on her own, so she is not in Maria's record.

| SV-Nummer | Persona | PLZ | Träger | Versicherungsstatus |
|---|---|---|---|---|
| 1234020674 | Maria Berger | 1030 | ÖGK | Pflichtversichert (Angestellte) |
| 4564200188 | Stefan Gruber | 1100 | SVS | Selbstständig (SVS) |
| 7898110995 | Elif Yılmaz | 1160 | ÖGK | Pflichtversichert (Angestellte) |

Anna Berger's data matches the SV-Box `Entlassungsbefund.pdf`.

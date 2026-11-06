import type { Card, DocumentExtraction } from "@/lib/api";

/** Synthetic SV-Box persona. Quotes match eval/extraction_expected.json. */
export const previewExtraction: DocumentExtraction = {
  kind: "discharge_letter",
  issuer: "SV-Box · synthetischer Entlassungsbefund",
  document_date: null,
  patient: { name: "Anna Berger", date_of_birth: "1948-03-14", address: "Musterstraße 12", postal_code: "1030", insurer: "ÖGK", svnr: null },
  living_situation: "Lebt allein in Wien.",
  documented_recommendations: [
    { topic: "rehabilitation", quote: "Prüfung einer stationären onkologischen Rehabilitation nach Abschluss der geplanten Strahlentherapie.", section: "7" },
    { topic: "care_allowance", quote: "Aufgrund des voraussichtlich längerfristigen Unterstützungsbedarfs soll geprüft werden, ob die Voraussetzungen für Pflegegeld erfüllt sind.", section: "8" },
    { topic: "mobile_care", quote: "Mobile Hauskrankenpflege zur Unterstützung bei pflegerischen Aufgaben und zur Beobachtung des Allgemeinzustands.", section: "6.3" },
  ],
  follow_up_appointments: [],
  warnings_in_document: [],
  confidence_note: "Prüfen Sie die ausgelesenen Angaben im Original. Die Auslesung ersetzt keine medizinische Beratung.",
};

export const previewCards: Card[] = [
  { type: "document_summary", document_id: "synthetic-discharge-letter", extraction: { ...previewExtraction } },
  { type: "form_draft", form_draft: {
    id: "synthetic-form", form_id: "pva_pflegegeld", title: "Antrag auf Pflegegeld – Entwurf", created_at: "2026-11-05T09:00:00Z",
    filled: [
      { key: "name", label: "Name", value: "Anna Berger", source: "document" },
      { key: "birth", label: "Geburtsdatum", value: "14.03.1948", source: "document" },
      { key: "address", label: "Adresse", value: "Musterstraße 12, 1030 Wien", source: "document" },
      { key: "insurer", label: "Versicherung", value: "ÖGK", source: "profile" },
      { key: "living", label: "Wohnsituation", value: "Lebt allein", source: "conversation" },
      { key: "support", label: "Unterstützung", value: "Tochter Maria organisiert Hilfe", source: "conversation" },
    ],
    missing: [{ key: "iban", label: "Bankverbindung", hint: "Ergänzen Sie die IBAN selbst im PDF." }, { key: "signature", label: "Unterschrift", hint: "Prüfen und unterschreiben Sie den Antrag." }],
    to_be_filled_by_others: [{ key: "medical", label: "Ärztliche Angaben", hint: "Die behandelnde Ärztin oder der behandelnde Arzt ergänzt diese Angaben." }],
    pdf_url: "/api/forms/synthetic-form/pdf",
  } },
  { type: "leistung", leistung: {
    id: "pflegegeld", title: "Pflegegeld", short: "Monatlicher pauschalierter Beitrag zu pflegebedingten Mehraufwendungen.",
    conditions: ["Pflegebedarf besteht voraussichtlich für mindestens sechs Monate."],
    office_hint: "Pensionsversicherungsanstalt (PVA)", form_ids: ["pva_pflegegeld"],
    documents_needed: ["Ausgefüllter und unterschriebener Antrag auf Pflegegeld", "Aktuelle ärztliche Befunde und Krankenhausentlassungsberichte"],
    source: { title: "Pflegegeld", publisher: "oesterreich.gv.at", url: "https://www.oesterreich.gv.at/de/themen/pflege/4/Seite.360512" },
  } },
  { type: "office", office: {
    id: "fsw_beratungszentrum_pflege", organisation: "Fonds Soziales Wien", name: "FSW Beratungszentrum Pflege und Betreuung",
    address: "Guglgasse 7-9", postal_code: "1030", city: "Wien", phone: "01 24 5 24", email: "post@fsw.at", url: "https://pflege.fsw.at",
    hours: "Täglich 08:00–20:00 Uhr (Telefon)",
  } },
  { type: "escalation", escalation: {
    id: "synthetic-handover", reason_code: "medical_question", created_at: "2026-11-05T09:05:00Z",
    target: { name: "Telefonische Gesundheitsberatung 1450", phone: "1450", url: "https://www.1450.at", hours: "Rund um die Uhr", note: "Bei Fragen außerhalb der Ordinationszeiten ohne akute Lebensgefahr." },
    handover_summary: "Ich unterstütze meine Mutter Anna Berger nach ihrem Spitalsaufenthalt.\nSie berichtet weiterhin über Übelkeit. Ich möchte die verordnete Medikation mit Fachpersonal besprechen.\nDer Entlassungsbefund liegt vor. Bitte klären Sie das weitere Vorgehen mit uns.",
  } },
];

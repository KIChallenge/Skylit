import type { Case } from "@/lib/api";

/** Fixed synthetic data for the isolated preview and feature tests. */
export const syntheticCase: Case = {
  id: "00000000-0000-4000-8000-000000000054",
  title: "Unterstützung nach dem Spital organisieren",
  subject: "parent",
  summary: "Ihre Mutter lebt in Wien und braucht nach dem Spitalsaufenthalt Unterstützung im Alltag. Sie möchten Pflegegeld, mobile Pflege und eine mögliche Rehabilitation klären. Sie prüfen jeden Antrag selbst. Die zuständige Stelle entscheidet über die Leistung.",
  updated_at: "2026-11-05T09:00:00Z",
  steps: [
    { id: "step-form", position: 2, title: "Pflegegeldantrag prüfen", category: "form", status: "in_progress",
      description: "Prüfen Sie die Angaben im vorausgefüllten Entwurf. Ergänzen Sie fehlende Felder vor der Unterschrift.",
      due_hint: "Vor dem Unterschreiben und Absenden", related_card: null },
    { id: "step-document", position: 1, title: "Entlassungsbrief bereithalten", category: "document", status: "open",
      description: "Legen Sie den Entlassungsbrief für die Beratung bereit. Nutzen Sie in dieser Vorschau nur synthetische Dokumente.",
      due_hint: "Vor dem Beratungsgespräch", related_card: null },
    { id: "step-contact", position: 3, title: "Mobile Pflege besprechen", category: "contact", status: "open",
      description: "Besprechen Sie mit dem FSW-Beratungszentrum, welche Unterstützung im Alltag in Frage kommt.",
      due_hint: "Als nächster organisatorischer Schritt", related_card: null },
    { id: "step-appointment", position: 4, title: "Reha mit dem Behandlungsteam klären", category: "appointment", status: "blocked",
      description: "Klären Sie mit dem Behandlungsteam, ob eine Rehabilitation in Frage kommt. Die medizinische Einschätzung fehlt noch.",
      due_hint: "Beim nächsten Gespräch mit dem Behandlungsteam", related_card: null },
    { id: "step-info", position: 5, title: "Unterstützung bei Fahrtkosten klären", category: "info", status: "open",
      description: "Fragen Sie bei Ihrem Versicherungsträger nach Voraussetzungen und notwendigen Unterlagen für eine mögliche Unterstützung.",
      due_hint: null, related_card: null },
    { id: "step-escalation", position: 6, title: "Persönliche Beratung vorbereiten", category: "escalation", status: "open",
      description: "Notieren Sie offene Fragen. Sie entscheiden selbst, ob und wann Sie eine Beratungsstelle kontaktieren.",
      due_hint: "Wenn Sie persönliche Unterstützung wünschen", related_card: null },
  ],
};

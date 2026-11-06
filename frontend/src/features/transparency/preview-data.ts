import { api, type ApiClient, type MessageTransparency } from "@/lib/api";

/** Synthetic protocol for the isolated preview. These are existing public KB sources. */
export const previewTransparency: MessageTransparency = {
  message_id: "00000000-0000-4000-8000-000000000057",
  model: "eustella-v1.5",
  provider: null,
  confidence: { level: "mittel", reason: "Es liegt nur eine Quelle vor oder ein Werkzeug ist fehlgeschlagen." },
  sources: [
    { title: "Pflegegeld – Antragstellung und Begutachtungsverfahren", publisher: "pv.at", url: "https://www.pv.at/web/pflegegeld" },
    { title: "Mobile Hauskrankenpflege und Heimhilfe in Wien", publisher: "fsw.at", url: "https://www.fsw.at/p/anbieter-hauskrankenpflege" },
  ],
  tools: [
    { name: "search_knowledge", label: "Informationen zu Pflegegeld gesucht", ok: true },
    { name: "find_office", label: "Zuständige Stelle gesucht", ok: false },
  ],
  retrieval: { chunks: [] },
  guardrails: [],
  escalation: null,
  entries: [{
    id: "00000000-0000-4000-8000-000000000058",
    created_at: "2026-11-05T14:32:00+01:00",
    event_type: "retrieval",
    summary: "Informationen zu Pflegegeld und Unterstützung zu Hause gefunden.",
    detail: { chunk_count: 2 },
  }],
};

export const previewClient: ApiClient = {
  ...api,
  getTransparency: async () => previewTransparency,
  resolveUrl: (url) => url,
};

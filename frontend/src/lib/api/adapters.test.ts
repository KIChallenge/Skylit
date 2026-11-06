// @vitest-environment node
import { describe, expect, it } from "vitest";

import {
  isKnownStreamEvent,
  resolveApiUrl,
  toCard,
  toCards,
  toDocumentExtraction,
  toDocumentSummary,
} from "./adapters";
import type { CardOf } from "./types";

const source = {
  title: "Pflegegeld",
  url: "https://www.oesterreich.gv.at/pflegegeld",
  publisher: "oesterreich.gv.at",
};

const officeCard = {
  type: "office",
  office: {
    id: "oegk-wien-10",
    name: "Kundenservice Favoriten",
    organisation: "ÖGK",
    address: "Wienerbergstraße 15–19",
    phone: null,
  },
};

const leistungCard = {
  type: "leistung",
  leistung: {
    id: "pflegegeld",
    title: "Pflegegeld",
    short: "Geldleistung bei Pflegebedarf.",
    conditions: ["Pflegebedarf von mehr als 65 Stunden im Monat"],
    office_hint: "Pensionsversicherung",
    form_ids: [],
    documents_needed: [],
    source,
  },
};

const extraction = {
  kind: "discharge_letter",
  issuer: "Klinik Favoriten",
  document_date: "2026-10-28",
  patient: {
    name: "[NAME]",
    date_of_birth: null,
    address: null,
    postal_code: "1100",
    insurer: "ÖGK",
    svnr: null,
  },
  living_situation: "lebt allein",
  documented_recommendations: [
    { topic: "rehabilitation", quote: "Rehabilitation empfohlen.", section: "Procedere" },
  ],
  follow_up_appointments: [{ what: "Kontrolle", when: null, quote: "Kontrolle in 2 Wochen." }],
  warnings_in_document: [],
  confidence_note: null,
};

describe("toCard", () => {
  it("accepts known cards with a valid shape", () => {
    expect(toCard(officeCard)).toBe(officeCard);
    expect(toCard(leistungCard)).toBe(leistungCard);
    expect(toCard({ type: "provider_list", providers: [], demo: true })).not.toBeNull();
  });

  it("rejects unknown types and broken shapes without throwing", () => {
    expect(toCard({ type: "weather", city: "Wien" })).toBeNull();
    expect(toCard({ type: "toString" })).toBeNull();
    expect(toCard({ type: "office", office: { id: "x" } })).toBeNull();
    expect(toCard({ type: "leistung", leistung: { ...leistungCard.leistung, source: null } })).toBeNull();
    expect(toCard({ type: "provider_list", providers: [{ id: 1 }] })).toBeNull();
    expect(toCard(null)).toBeNull();
    expect(toCard("office")).toBeNull();
    expect(toCard({ office: officeCard.office })).toBeNull();
  });
});

describe("toCards", () => {
  it("keeps valid cards in order and drops the rest", () => {
    const cards = toCards([officeCard, { type: "unknown" }, 42, leistungCard]);
    expect(cards.map((card) => card.type)).toEqual(["office", "leistung"]);
  });

  it("returns an empty list for a non-array", () => {
    expect(toCards(undefined)).toEqual([]);
    expect(toCards({ type: "office" })).toEqual([]);
  });
});

describe("document extraction", () => {
  it("types a valid extraction", () => {
    expect(toDocumentExtraction(extraction)).toBe(extraction);
  });

  it("returns null for a partial extraction instead of filling values", () => {
    const { documented_recommendations: _dropped, ...partial } = extraction;
    expect(toDocumentExtraction(partial)).toBeNull();
    expect(toDocumentExtraction({ ...extraction, patient: null })).toBeNull();
    expect(toDocumentExtraction({})).toBeNull();
  });

  it("reads a document_summary card", () => {
    const card = {
      type: "document_summary",
      document_id: "d1",
      extraction,
    } as CardOf<"document_summary">;
    expect(toCard(card)).toBe(card);
    expect(toDocumentSummary(card)).toEqual({ document_id: "d1", extraction });
    expect(toDocumentSummary({ ...card, extraction: { kind: 3 } })).toEqual({
      document_id: "d1",
      extraction: null,
    });
  });
});

describe("isKnownStreamEvent", () => {
  it("knows the generated event types only", () => {
    expect(isKnownStreamEvent({ type: "text.delta" })).toBe(true);
    expect(isKnownStreamEvent({ type: "error" })).toBe(true);
    expect(isKnownStreamEvent({ type: "future.event" })).toBe(false);
    expect(isKnownStreamEvent({ type: "constructor" })).toBe(false);
  });
});

describe("resolveApiUrl", () => {
  it("prefixes backend-relative URLs with the origin", () => {
    expect(resolveApiUrl("/api/appointments/a1/ics", "http://localhost:8000/")).toBe(
      "http://localhost:8000/api/appointments/a1/ics",
    );
  });

  it("leaves absolute and protocol-relative URLs unchanged", () => {
    expect(resolveApiUrl(source.url, "http://localhost:8000")).toBe(source.url);
    expect(resolveApiUrl("//cdn.example.at/x", "http://localhost:8000")).toBe("//cdn.example.at/x");
  });
});

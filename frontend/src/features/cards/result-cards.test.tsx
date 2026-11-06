import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { api, type CardOf } from "@/lib/api";
import { previewCards, previewExtraction } from "./fixtures";
import { CopyButton, DocumentSummaryCard, FormDraftCard, ResultCard, ResultCards } from "./result-cards";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://backend.example");
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("card validation", () => {
  it("drops broken cards without rendering raw data", () => {
    render(<ResultCards cards={[null, { type: "office", office: { name: { private: "secret" } } }, { type: "unknown", body: "raw stack trace" }]} />);
    expect(screen.getByText("Noch keine Ergebnisse.")).toBeInTheDocument();
    expect(screen.queryByText(/secret|stack trace/)).not.toBeInTheDocument();
  });

  it("handles invalid single cards and malformed document extractions", () => {
    const view = render(<ResultCard card={{ type: "form_draft", form_draft: {} }} />);
    expect(screen.getByText("Ergebnis nicht verfügbar.")).toBeInTheDocument();
    view.rerender(<ResultCard card={{ type: "document_summary", document_id: "doc", extraction: { patient: "broken" } }} />);
    expect(screen.getByText("Dokumentinhalt nicht verfügbar.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Dokument öffnen/ })).toHaveAttribute("href", api.documentFileUrl("doc"));
  });

  it("keeps valid cards when siblings are invalid and removes duplicate handovers", () => {
    const escalation = previewCards.find(card => card.type === "escalation")!;
    render(<ResultCards cards={[null, escalation, escalation, { ...escalation }, previewCards[2]]} />);
    expect(screen.getAllByRole("heading", { name: "Medizinische Frage" })).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Pflegegeld" })).toBeInTheDocument();
  });

  it("shows only the latest draft when a turn prepares the same form twice", () => {
    const form = previewCards.find(card => card.type === "form_draft")!;
    const older = { ...form, form_draft: { ...form.form_draft, title: "Älterer Entwurf" } };
    render(<ResultCards cards={[older, form]} />);
    expect(screen.getAllByRole("region", { name: form.form_draft.title })).toHaveLength(1);
    expect(screen.queryByText("Älterer Entwurf")).not.toBeInTheDocument();
  });

  it("labels providers and appointments as demo data", () => {
    render(<ResultCards cards={[
      { type: "provider_list", providers: [{ id: "p", name: "Erfundene Praxis", kind: "care" }] },
      { type: "appointment", appointment: { id: "a", start: "2026-11-05", end: "2026-11-05", ics_url: "/a.ics", provider: { id: "p", name: "Erfundene Praxis", kind: "care" } } },
    ]} />);
    expect(screen.getAllByText("Demo-Daten")).toHaveLength(2);
  });
});

it("renders literal quotes with sections and the backend uncertainty note", () => {
  const card: CardOf<"document_summary"> = { type: "document_summary", document_id: "doc", extraction: { ...previewExtraction } };
  render(<DocumentSummaryCard card={card} filename="entlassungsbefund.pdf" />);
  expect(screen.getByText(`„${previewExtraction.documented_recommendations[0].quote}“`)).toBeInTheDocument();
  expect(screen.getByText("Abschnitt 7")).toBeInTheDocument();
  expect(screen.getByText(previewExtraction.confidence_note!)).toBeInTheDocument();
  expect(screen.getByText("entlassungsbefund.pdf")).toBeInTheDocument();
  expect(screen.queryByText(/Sicherheit: hoch/)).not.toBeInTheDocument();
});

it("renders form groups, per-field origins, and expands all filled fields", () => {
  const card = previewCards.find(card => card.type === "form_draft")!;
  render(<FormDraftCard card={card} />);
  expect(screen.getByRole("heading", { name: "Ausgefüllt (6)" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Fehlt noch (2)" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Füllen andere aus (1)" })).toBeInTheDocument();
  expect(screen.getAllByText("Herkunft: aus dem Dokument")).toHaveLength(3);
  expect(screen.getByText("Herkunft: aus Ihrem Profil")).toBeInTheDocument();
  expect(screen.queryByText("Tochter Maria organisiert Hilfe")).not.toBeInTheDocument();
  const expand = screen.getByRole("button", { name: "Alle 6 anzeigen" });
  fireEvent.click(expand);
  expect(expand).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Tochter Maria organisiert Hilfe")).toBeInTheDocument();
  expect(screen.getByText(/Sie unterschreiben und senden ihn selbst/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Senden$/ })).not.toBeInTheDocument();
});

it("resolves relative office links and rejects unsafe navigation", () => {
  render(<ResultCard card={{ type: "office", office: { id: "o", name: "Beratung", organisation: "Stelle", address: "Guglgasse 7-9", phone: "01 24 5 24", email: "post@fsw.at", url: "/offices/fsw", maps_url: "javascript:alert(1)" } }} />);
  expect(screen.getByRole("link", { name: /Website/ })).toHaveAttribute("href", "https://backend.example/offices/fsw");
  expect(screen.getByRole("link", { name: /anrufen/ })).toHaveAttribute("href", "tel:0124524");
  expect(screen.getByRole("link", { name: "post@fsw.at" })).toHaveAttribute("href", "mailto:post@fsw.at");
  expect(screen.queryByRole("link", { name: /Auf der Karte/ })).not.toBeInTheDocument();
});

it("keeps the page and allows a manual retry when a relative PDF download fails", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"detail":"traceback"}', { status: 500, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  render(<ResultCard card={previewCards[1]} />);
  fireEvent.click(screen.getByRole("button", { name: "PDF herunterladen" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Die Datei konnte nicht geladen werden.");
  expect(fetch).toHaveBeenCalledWith("https://backend.example/api/forms/synthetic-form/pdf", expect.objectContaining({ credentials: "include", signal: expect.any(AbortSignal) }));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(screen.queryByText(/traceback/)).not.toBeInTheDocument();
  fireEvent.click(within(alert).getByRole("button", { name: "Erneut versuchen" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
});

it("announces copy success without sending the handover", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  render(<ResultCard card={previewCards[4]} />);
  fireEvent.click(screen.getByRole("button", { name: "Zusammenfassung kopieren" }));
  await screen.findByRole("button", { name: "Kopiert" });
  expect(screen.getByRole("status")).toHaveTextContent("Zusammenfassung kopiert.");
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining("Bitte klären Sie das weitere Vorgehen"));
});

it("provides a manual copy alternative and retries only on request", async () => {
  const writeText = vi.fn().mockRejectedValue(new Error("Permission denied"));
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  render(<CopyButton value="Zum Vorlesen" />);
  fireEvent.click(screen.getByRole("button", { name: "Zusammenfassung kopieren" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Markieren Sie die Zusammenfassung");
  expect(writeText).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
  await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
});

it("shows loading, empty and retry states without hiding existing cards", () => {
  const retry = vi.fn();
  const view = render(<ResultCards cards={[]} loading />);
  expect(screen.getByRole("status", { name: "Ergebnisse werden geladen" })).toBeInTheDocument();
  view.rerender(<ResultCards cards={[]} />);
  expect(screen.getByText("Noch keine Ergebnisse.")).toBeInTheDocument();
  view.rerender(<ResultCards cards={[previewCards[2]]} error={new Error("private trace")} onRetry={retry} />);
  expect(screen.getByRole("heading", { name: "Pflegegeld" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
  expect(retry).toHaveBeenCalledOnce();
  expect(screen.queryByText("private trace")).not.toBeInTheDocument();
});

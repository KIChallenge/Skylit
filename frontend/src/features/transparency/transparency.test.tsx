import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createApiClient, TransportError, type ApiClient, type MessageTransparency } from "@/lib/api";
import { AnswerFooter, TransparencyDrawer } from ".";
import { previewTransparency } from "./preview-data";

// jsdom has no layout observer. Keep the Radix dependency stub local to this feature.
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function clientWith(data: MessageTransparency = previewTransparency) {
  const getTransparency = vi.fn<ApiClient["getTransparency"]>().mockResolvedValue(data);
  const client = { ...createApiClient({ baseUrl: "https://backend.example", timeoutMs: 1000 }), getTransparency };
  return { client, getTransparency };
}

function footer(client: ApiClient, messageId: string | null = "saved-answer") {
  return <TooltipProvider><AnswerFooter client={client} messageId={messageId} /></TooltipProvider>;
}

async function openDrawer() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Warum diese Antwort?" }));
  return { user, dialog: await screen.findByRole("dialog") };
}

describe("answer transparency", () => {
  it("waits for a saved message and keeps stream sources visible while loading", async () => {
    const { client, getTransparency } = clientWith();
    getTransparency.mockImplementation(() => new Promise(() => {}));
    const view = render(footer(client, null));
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
    expect(getTransparency).not.toHaveBeenCalled();
    view.rerender(<TooltipProvider><AnswerFooter client={client} messageId="saved-answer" initialSources={previewTransparency.sources} /></TooltipProvider>);
    expect(screen.getByRole("status")).toHaveTextContent("werden geladen");
    expect(screen.getAllByRole("link")).toHaveLength(2);
    await waitFor(() => expect(getTransparency).toHaveBeenCalledTimes(1));
    await openDrawer();
    expect(within(screen.getByRole("dialog")).getByRole("status")).toHaveTextContent("werden geladen");
    expect(getTransparency).toHaveBeenCalledTimes(1);
  });

  it("shows backend confidence, model, sources, retrieval entries and tool outcomes", async () => {
    const { client, getTransparency } = clientWith();
    render(footer(client));
    expect(await screen.findByText("Sicherheit: mittel")).toHaveClass("bg-caution-subtle");
    expect(screen.getByText(previewTransparency.model!)).toBeVisible();
    const { dialog } = await openDrawer();
    expect(within(dialog).getByText(previewTransparency.confidence.reason)).toBeVisible();
    expect(within(dialog).getByText(previewTransparency.entries[0].summary)).toBeVisible();
    expect(within(dialog).getByText("Erfolgreich")).toBeVisible();
    expect(within(dialog).getByText("Nicht erfolgreich")).toBeVisible();
    expect(within(dialog).getAllByRole("link")).toHaveLength(2);
    expect(within(dialog).queryByText(/Anbieter:/)).not.toBeInTheDocument();
    expect(within(dialog).queryByText("EU-Modell, Wien")).not.toBeInTheDocument();
    expect(getTransparency).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["hoch", "bg-accent-subtle"], ["mittel", "bg-caution-subtle"], ["niedrig", "bg-caution-solid"],
  ] as const)("uses backend level %s even with no sources", async (level, color) => {
    const { client } = clientWith({ ...previewTransparency, confidence: { level, reason: "Backend-Begründung" }, sources: [] });
    render(footer(client));
    expect(await screen.findByText(`Sicherheit: ${level}`)).toHaveClass(color);
  });

  it("handles null model and provider and empty collections without inventing metadata", async () => {
    const { client } = clientWith({ ...previewTransparency, model: null, provider: null, sources: [], tools: [], entries: [] });
    render(footer(client));
    expect(await screen.findByText("Modell nicht erfasst")).toBeVisible();
    expect(screen.getByText("Keine Quellen")).toBeVisible();
    const { dialog } = await openDrawer();
    expect(within(dialog).getByText("Modell nicht erfasst")).toBeVisible();
    expect(within(dialog).getByText("Für diese Antwort liegen keine Quellen vor.")).toBeVisible();
    expect(within(dialog).getByText("Für diese Antwort liegen keine Protokolldaten vor.")).toBeVisible();
    expect(within(dialog).queryByText(/Anbieter:|EU-Modell/)).not.toBeInTheDocument();
  });

  it("shows guardrails and escalation without hiding the answer or emergency banner", async () => {
    const { client } = clientWith({ ...previewTransparency, model: null, sources: [],
      confidence: { level: "niedrig", reason: "Es fehlt eine ausreichende Quelle für diese Antwort." },
      guardrails: [{ code: "emergency", summary: "Die feste Notfallregel hat ausgelöst." }],
      escalation: { reason_code: "emergency", target: { name: "Rettung" } },
    });
    render(<><div role="alert">Bitte holen Sie sofort Hilfe.</div><p>Antwort des Lotsen bleibt erhalten.</p>{footer(client)}</>);
    expect(await screen.findByText("Notfall")).toBeVisible();
    const { user, dialog } = await openDrawer();
    expect(within(dialog).getByText("Notfallregel ausgelöst")).toBeVisible();
    expect(within(dialog).getByText("Rettung")).toBeVisible();
    within(dialog).getByRole("button", { name: "Schließen" }).focus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("Bitte holen Sie sofort Hilfe.");
    expect(screen.getByText("Antwort des Lotsen bleibt erhalten.")).toBeVisible();
  });

  it("shows the provider hint only for the recorded eustella provider", async () => {
    const { client } = clientWith({ ...previewTransparency, provider: "eustella" });
    render(footer(client));
    await screen.findByText("Sicherheit: mittel");
    const { dialog } = await openDrawer();
    expect(within(dialog).getByText("Anbieter: eustella")).toBeVisible();
    expect(within(dialog).getByText("EU-Modell, Wien")).toBeVisible();
  });

  it("resolves document URLs and keeps external sources as links", async () => {
    const { client } = clientWith({ ...previewTransparency, sources: [
      { title: "Entlassungsbrief · Abschnitt 8", publisher: "Synthetisches Dokument", url: "/api/documents/demo/file" },
      ...previewTransparency.sources,
      { title: "Ungültiger Link", publisher: "Beispiel", url: "javascript:alert(1)" },
    ] });
    render(footer(client));
    const documentLink = await screen.findByRole("link", { name: /Entlassungsbrief/ });
    expect(documentLink).toHaveAttribute("href", "https://backend.example/api/documents/demo/file");
    expect(documentLink).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: /pv.at/ })).toHaveAttribute("href", previewTransparency.sources[0].url);
    await userEvent.click(screen.getByRole("button", { name: "+1 weitere" }));
    expect(screen.getByText("Beispiel · Ungültiger Link")).toBeVisible();
    expect(screen.queryByRole("link", { name: /Ungültiger Link/ })).not.toBeInTheDocument();
  });

  it("shows the retrieval date of a knowledge source", async () => {
    const { client } = clientWith({ ...previewTransparency, sources: [
      { ...previewTransparency.sources[0], retrieved: "2026-11-05" },
    ] });
    render(footer(client));
    expect(await screen.findByText("Stand: 05.11.2026")).toBeVisible();
  });

  it("treats 404 as unavailable data without retrying", async () => {
    const { client, getTransparency } = clientWith();
    getTransparency.mockRejectedValue(new TransportError("not_found", "Nicht gefunden", { status: 404 }));
    render(footer(client));
    expect(await screen.findByText("Sicherheit nicht verfügbar")).toBeVisible();
    expect(screen.getByText("Modell nicht verfügbar")).toBeVisible();
    const { user, dialog } = await openDrawer();
    expect(within(dialog).getByText("Für diese Antwort liegen keine Protokolldaten vor.")).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "Erneut versuchen" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await openDrawer();
    expect(getTransparency).toHaveBeenCalledTimes(1);
  });

  it.each(["network_error", "timeout"])("retries %s without removing the answer", async (code) => {
    const { client, getTransparency } = clientWith();
    getTransparency.mockRejectedValueOnce(new TransportError(code, "Technisches Detail"));
    render(<><p>Antwort bleibt erhalten.</p>{footer(client)}</>);
    await screen.findByText("Sicherheit nicht verfügbar");
    const { user, dialog } = await openDrawer();
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Die Angaben zu dieser Antwort konnten nicht geladen werden.");
    expect(screen.queryByText("Technisches Detail")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Erneut versuchen" }));
    expect(await within(dialog).findByText("Sicherheit: mittel")).toBeVisible();
    expect(getTransparency).toHaveBeenCalledTimes(2);
    await user.keyboard("{Escape}");
    expect(screen.getByText("Antwort bleibt erhalten.")).toBeVisible();
  });

  it("aborts on ID changes and ignores late responses", async () => {
    const { client, getTransparency } = clientWith();
    let finishFirst!: (data: MessageTransparency) => void;
    getTransparency.mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve; }));
    const view = render(footer(client, "first"));
    await waitFor(() => expect(getTransparency).toHaveBeenCalledTimes(1));
    const firstSignal = getTransparency.mock.calls[0][1]!.signal!;
    view.rerender(footer(client, "second"));
    expect(firstSignal.aborted).toBe(true);
    await screen.findByText("Sicherheit: mittel");
    await act(async () => finishFirst({ ...previewTransparency, model: "Veralteter Modellwert" }));
    expect(screen.queryByText("Veralteter Modellwert")).not.toBeInTheDocument();
    const secondSignal = getTransparency.mock.calls[1][1]!.signal!;
    view.unmount();
    expect(secondSignal.aborted).toBe(true);
  });

  it("caches successful data per message and isolates injected clients", async () => {
    const first = clientWith();
    const view = render(footer(first.client));
    await screen.findByText("Sicherheit: mittel");
    view.unmount();
    const next = render(footer(first.client));
    await screen.findByText("Sicherheit: mittel");
    expect(first.getTransparency).toHaveBeenCalledTimes(1);
    const second = clientWith({ ...previewTransparency, model: null });
    next.rerender(footer(second.client));
    await screen.findByText("Modell nicht erfasst");
    expect(second.getTransparency).toHaveBeenCalledTimes(1);
  });

  it("supports standalone drawers with focus binding, Escape and focus return", async () => {
    const { client, getTransparency } = clientWith();
    const user = userEvent.setup();
    render(<TooltipProvider><TransparencyDrawer messageId="saved-answer" client={client} /></TooltipProvider>);
    expect(getTransparency).not.toHaveBeenCalled();
    const trigger = screen.getByRole("button", { name: "Warum diese Antwort?" });
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Warum diese Antwort?" });
    await within(dialog).findByText("Sicherheit: mittel");
    const close = within(dialog).getByRole("button", { name: "Schließen" });
    close.focus();
    await user.tab();
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    await user.tab({ shift: true });
    expect(close).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");
    expect(getTransparency).toHaveBeenCalledTimes(1);
  });
});

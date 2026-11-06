import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Message } from "@/lib/api";
import { ChatPreview } from "@/app/styleguide/chat/preview";
import { TooltipProvider } from "@/components/ui/tooltip";

import { Composer, ConversationView, EmergencyBanner } from "./index";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Composer", () => {
  it("sends trimmed content with Enter and allows Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<Composer sending={false} onSend={onSend} />);
    const input = screen.getByRole("textbox", { name: "Ihre Nachricht an den Lotsen" });
    expect(input).toHaveAccessibleDescription("Enter sendet · Umschalt+Enter fügt eine neue Zeile ein.");
    await user.type(input, "  Meine Frage{Shift>}{Enter}{/Shift}zweite Zeile  ");
    expect(input).toHaveValue("  Meine Frage\nzweite Zeile  ");
    expect(onSend).not.toHaveBeenCalled();
    await user.keyboard("{Enter}");
    expect(onSend).toHaveBeenCalledExactlyOnceWith("Meine Frage\nzweite Zeile");
    expect(input).toHaveValue("");
  });

  it("rejects empty content and exposes validation", async () => {
    const onSend = vi.fn();
    render(<Composer sending={false} onSend={onSend} />);
    await userEvent.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox")).toHaveFocus();
  });

  it("blocks rapid double submissions before the parent updates sending", () => {
    const onSend = vi.fn();
    render(<Composer sending={false} onSend={onSend} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Frage" } });
    fireEvent.submit(screen.getByRole("form", { name: "Nachricht verfassen" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Noch eine Frage" } });
    fireEvent.submit(screen.getByRole("form", { name: "Nachricht verfassen" }));
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("blocks clicks and Enter while sending, keeps editing, and unlocks after completion", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const { rerender } = render(<Composer sending onSend={onSend} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "Nächste Frage{Enter}");
    await user.click(screen.getByRole("button", { name: "Lotse antwortet…" }));
    expect(screen.getByRole("button", { name: "Lotse antwortet…" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByRole("button", { name: "Lotse antwortet…" })).toBeEnabled();
    expect(onSend).not.toHaveBeenCalled();
    expect(input).toHaveValue("Nächste Frage");
    rerender(<Composer sending={false} onSend={onSend} />);
    expect(screen.getByRole("button", { name: "Senden" })).toHaveAttribute("aria-disabled", "false");
    await user.click(screen.getByRole("button", { name: "Senden" }));
    expect(onSend).toHaveBeenCalledExactlyOnceWith("Nächste Frage");
  });

  it("shows the character counter from 3500 characters and hides it below the threshold", () => {
    render(<Composer sending={false} onSend={vi.fn()} />);
    const input = screen.getByRole("textbox");
    expect(screen.queryByText(/\/4000 Zeichen/)).not.toBeInTheDocument();
    fireEvent.change(input, { target: { value: "x".repeat(3499) } });
    expect(screen.queryByText(/\/4000 Zeichen/)).not.toBeInTheDocument();
    fireEvent.change(input, { target: { value: "x".repeat(3500) } });
    expect(screen.getByText("3500/4000 Zeichen")).toBeVisible();
    expect(input).toHaveAccessibleDescription(/3500\/4000 Zeichen/);
    fireEvent.change(input, { target: { value: "x".repeat(4000) } });
    expect(screen.getByText("4000/4000 Zeichen")).toBeVisible();
    fireEvent.change(input, { target: { value: "x".repeat(3499) } });
    expect(screen.queryByText(/\/4000 Zeichen/)).not.toBeInTheDocument();
    expect(input).toHaveAccessibleDescription("Enter sendet · Umschalt+Enter fügt eine neue Zeile ein.");
  });

  it("enforces 4000 characters and ignores composition Enter", () => {
    const onSend = vi.fn();
    render(<Composer sending={false} onSend={onSend} />);
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("maxlength", "4000");
    fireEvent.change(input, { target: { value: "x".repeat(4001) } });
    fireEvent.submit(screen.getByRole("form"));
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "x".repeat(4000) } });
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSend).toHaveBeenCalledExactlyOnceWith("x".repeat(4000));
  });
});

const message: Message = {
  id: "demo", role: "assistant", content: "**Gespeicherte Antwort**", created_at: "2026-11-05T09:00:00Z",
  document_ids: [], cards: [], sources: [], escalation_id: null,
};
const baseProps = { messages: [], responseText: "", sending: false, onSend: vi.fn(), onRetry: vi.fn() };

describe("ConversationView", () => {
  it("preserves partial text on errors and retries only through the callback", async () => {
    const onRetry = vi.fn();
    render(<ConversationView {...baseProps} messages={[message]} responseText="Bisherige Teilantwort" error="Verbindung unterbrochen." onRetry={onRetry} />);
    expect(screen.getByText("Bisherige Teilantwort")).toBeVisible();
    expect(screen.getByText("Gespeicherte Antwort")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.getByText("Bisherige Teilantwort")).toBeVisible();
  });

  it("renders Markdown without raw HTML or executable links", () => {
    const { container } = render(<ConversationView {...baseProps} responseText={'**Fett** <script>alert(1)</script> <img src=x onerror=alert(1)> [Link](javascript:alert(1))'} />);
    expect(screen.getByText("Fett").tagName).toBe("STRONG");
    expect(container.querySelector("script, img, [onerror], a[href^='javascript:']")).toBeNull();
  });

  it("supports empty, loading, streaming and extension slots", () => {
    const { rerender } = render(<ConversationView {...baseProps} />);
    expect(screen.getByText("Was beschäftigt Sie gerade?")).toBeVisible();
    rerender(<ConversationView {...baseProps} loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Gespräch wird geladen…");
    rerender(<ConversationView {...baseProps} messages={[message]} sending responseText="Direkter Text" progressLabel="Dokument wird gelesen…" renderMessageCards={() => <p>Nachrichtenkarte</p>} renderAnswerFooter={() => <p>Antwortquellen</p>} attachment={<span>Anhang bereit</span>} />);
    expect(screen.getByText("Direkter Text")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Dokument wird gelesen…");
    expect(screen.getByText("Nachrichtenkarte")).toBeVisible();
    expect(screen.getByText("Antwortquellen")).toBeVisible();
    expect(screen.getByText("Anhang bereit")).toBeVisible();
  });

  it("follows content only while the reader remains at the bottom", async () => {
    const { rerender } = render(<ConversationView {...baseProps} responseText="Teil eins" />);
    const region = screen.getByRole("region", { name: "Nachrichten" });
    Object.defineProperties(region, { scrollHeight: { configurable: true, value: 1000 }, clientHeight: { configurable: true, value: 400 } });
    region.scrollTop = 100;
    fireEvent.scroll(region);
    rerender(<ConversationView {...baseProps} responseText="Teil eins und zwei" />);
    expect(region.scrollTop).toBe(100);
    await userEvent.click(screen.getByRole("button", { name: "Zu neuen Inhalten" }));
    expect(region.scrollTop).toBe(1000);
    Object.defineProperty(region, "scrollHeight", { configurable: true, value: 1200 });
    rerender(<ConversationView {...baseProps} responseText="Teil eins und zwei und drei" />);
    expect(region.scrollTop).toBe(1200);
  });

  it("follows asynchronously growing cards only while the reader remains at the bottom", () => {
    let notifyResize = () => {};
    const disconnect = vi.fn();
    vi.stubGlobal("ResizeObserver", class {
      constructor(callback: () => void) { notifyResize = callback; }
      observe = vi.fn();
      disconnect = disconnect;
    });
    const { unmount } = render(<ConversationView {...baseProps} messages={[message]} />);
    const region = screen.getByRole("region", { name: "Nachrichten" });
    Object.defineProperties(region, {
      scrollHeight: { configurable: true, value: 1000 },
      clientHeight: { configurable: true, value: 400 },
    });
    act(() => notifyResize());
    expect(region.scrollTop).toBe(1000);
    region.scrollTop = 100;
    fireEvent.scroll(region);
    Object.defineProperty(region, "scrollHeight", { configurable: true, value: 1400 });
    act(() => notifyResize());
    expect(region.scrollTop).toBe(100);
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
  });
});

describe("EmergencyBanner", () => {
  it("uses supplied contacts, remains visible, and never moves focus", () => {
    render(<><label>Entwurf<input autoFocus /></label><EmergencyBanner message="Holen Sie sofort Hilfe." contacts={[{ name: "Kontakt aus dem Backend", phone: "+43 (0) 123-456", hours: "Immer erreichbar", note: "Bitte anrufen." }, { name: "Beratungsstelle" }]} /></>);
    expect(screen.getByRole("alert")).toHaveTextContent("Holen Sie sofort Hilfe.");
    expect(screen.getByRole("link", { name: "+43 (0) 123-456 anrufen – Kontakt aus dem Backend" })).toHaveAttribute("href", "tel:+430123456");
    expect(screen.getByText("Beratungsstelle")).toBeVisible();
    expect(screen.getByRole("textbox")).toHaveFocus();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("does not invent contacts or confidence", () => {
    render(<EmergencyBanner contacts={[]} message="Backend-Hinweis" />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).not.toHaveTextContent(/Sicherheit|144|1450/);
  });
});

describe("ChatPreview", () => {
  it("keeps emergency contacts visible before main while showing the emergency response", async () => {
    render(<TooltipProvider><ChatPreview /></TooltipProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Notfall" }));
    const alert = screen.getByRole("alert");
    expect(alert.compareDocumentPosition(screen.getByRole("main")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("link", { name: "144 anrufen – Rettung" })).toHaveAttribute("href", "tel:144");
    expect(screen.getByText("Bitte holen Sie sofort Hilfe. Warten Sie nicht auf weitere Antworten des Lotsen.")).toBeVisible();
    await userEvent.type(screen.getByRole("textbox"), "Noch eine Nachricht");
    expect(alert).toBeVisible();
  });

  it("shows an attachment without automatically sending a message", async () => {
    render(<TooltipProvider><ChatPreview /></TooltipProvider>);
    await userEvent.click(screen.getByRole("button", { name: "Dokument anhängen" }));
    expect(screen.getByText("Entlassungsbrief.pdf · Demo-Anhang bereit")).toBeVisible();
    expect(screen.getByRole("button", { name: "Senden" })).toHaveAttribute("aria-disabled", "false");
    expect(screen.getByText("Unterstützung zu Hause")).toBeVisible();
  });
});

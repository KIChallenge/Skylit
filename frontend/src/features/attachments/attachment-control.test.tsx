import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

import { AttachmentChip, AttachmentControl, type AttachmentPhase } from "./index";

// jsdom omits ResizeObserver. Radix uses it when a tooltip receives focus.
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const filename = "entlassungsbefund.pdf";

function callbacks() {
  return { onFileSelected: vi.fn(), onRemove: vi.fn(), onRetry: vi.fn() };
}

describe("AttachmentControl", () => {
  it("opens the native picker with the keyboard and accepts PDF, JPEG and PNG", async () => {
    const user = userEvent.setup();
    const handlers = callbacks();
    render(<TooltipProvider><AttachmentControl {...handlers} /></TooltipProvider>);
    const input = screen.getByLabelText("Dokument auswählen") as HTMLInputElement;
    const open = vi.spyOn(input, "click");
    await user.tab();
    expect(screen.getByRole("button", { name: "Dokument anhängen" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(open).toHaveBeenCalledOnce();
    expect(input.accept).toBe(".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png");
    expect(input.multiple).toBe(false);
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
  });

  it.each([
    [filename, "application/pdf"], ["entlassungsbefund.jpeg", "image/jpeg"], ["entlassungsbefund.png", "image/png"],
  ])("passes the selected File unchanged: %s", async (name, type) => {
    const user = userEvent.setup();
    const handlers = callbacks();
    render(<TooltipProvider><AttachmentControl {...handlers} /></TooltipProvider>);
    const input = screen.getByLabelText("Dokument auswählen");
    const file = new File(["Synthetischer Entlassungsbefund"], name, { type });
    await user.upload(input, file);
    expect(handlers.onFileSelected).toHaveBeenCalledExactlyOnceWith(file);
    await user.upload(input, file);
    expect(handlers.onFileSelected).toHaveBeenCalledTimes(2);
    expect(handlers.onRemove).not.toHaveBeenCalled();
  });

  it("does not notify the controller when the picker is cancelled", () => {
    const handlers = callbacks();
    render(<TooltipProvider><AttachmentControl {...handlers} /></TooltipProvider>);
    fireEvent.change(screen.getByLabelText("Dokument auswählen"), { target: { files: [] } });
    expect(handlers.onFileSelected).not.toHaveBeenCalled();
  });

  it("does not submit its parent form when opening the picker", async () => {
    const user = userEvent.setup();
    const submit = vi.fn((event) => event.preventDefault());
    render(<TooltipProvider><form onSubmit={submit}><AttachmentControl {...callbacks()} /></form></TooltipProvider>);
    await user.click(screen.getByRole("button", { name: "Dokument anhängen" }));
    expect(submit).not.toHaveBeenCalled();
  });

  it("returns focus to the picker after the parent removes the attachment", async () => {
    const user = userEvent.setup();
    const handlers = callbacks();
    function Composer() {
      const [attached, setAttached] = useState(true);
      return <AttachmentControl
        {...handlers}
        filename={attached ? filename : null}
        phase={attached ? "failed" : null}
        onRemove={() => { handlers.onRemove(); setAttached(false); }}
      />;
    }
    render(<TooltipProvider><Composer /></TooltipProvider>);
    await user.tab(); // filename
    await user.tab(); // remove
    await user.keyboard("{Enter}");
    expect(handlers.onRemove).toHaveBeenCalledOnce();
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dokument anhängen" })).toHaveFocus();
  });
});

describe("AttachmentChip", () => {
  it.each<[AttachmentPhase, string]>([
    ["uploading", "Wird hochgeladen…"], ["processing", "Wird gelesen…"],
    ["ready", "Bereit"], ["failed", "Fehlgeschlagen"],
  ])("shows %s without a fabricated percentage and keeps removal available", (phase, label) => {
    render(<TooltipProvider><AttachmentChip filename={filename} phase={phase} {...callbacks()} /></TooltipProvider>);
    expect(screen.getByRole("status")).toHaveTextContent(label);
    expect(screen.getByRole("button", { name: `Entfernen: ${filename}` })).toBeEnabled();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
    if (phase === "failed") {
      expect(screen.getByRole("button", { name: `Erneut versuchen: ${filename}` })).toBeEnabled();
    } else {
      expect(screen.queryByRole("button", { name: `Erneut versuchen: ${filename}` })).not.toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    }
  });

  it("updates the existing live region when the controller changes the phase", () => {
    const handlers = callbacks();
    const { rerender } = render(<TooltipProvider><AttachmentChip filename={filename} phase="uploading" {...handlers} /></TooltipProvider>);
    const status = screen.getByRole("status");
    rerender(<TooltipProvider><AttachmentChip filename={filename} phase="processing" documentId="synthetic-document" {...handlers} /></TooltipProvider>);
    expect(screen.getByRole("status")).toBe(status);
    expect(status).toHaveTextContent("Wird gelesen…");
    expect(screen.getByRole("group")).toHaveAttribute("data-document-id", "synthetic-document");
    rerender(<TooltipProvider><AttachmentChip filename={filename} phase="ready" {...handlers} /></TooltipProvider>);
    expect(status).toHaveTextContent("Bereit");
  });

  it("keeps the full filename accessible and reveals it in a keyboard tooltip", async () => {
    const user = userEvent.setup();
    const longName = "synthetischer-entlassungsbefund-mit-einem-sehr-langen-vollstaendigen-dateinamen.pdf";
    render(<TooltipProvider delayDuration={0}><AttachmentChip filename={longName} phase="ready" {...callbacks()} /></TooltipProvider>);
    expect(screen.getByRole("group", { name: `Anhang: ${longName}` })).toBeInTheDocument();
    const nameTrigger = screen.getByText(longName).closest("span");
    await user.tab();
    expect(nameTrigger).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(longName);
  });

  it("announces a readable failure and allows retry, removal and continuation with the keyboard", async () => {
    const user = userEvent.setup();
    const handlers = callbacks();
    const submit = vi.fn((event) => event.preventDefault());
    render(
      <TooltipProvider><form onSubmit={submit}>
        <AttachmentChip filename={filename} phase="failed" error="Die Verbindung wurde unterbrochen." {...handlers} />
        <AttachmentControl {...handlers} />
        <button type="submit">Nachricht senden</button>
      </form></TooltipProvider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Die Verbindung wurde unterbrochen.");
    await user.tab(); // filename
    await user.tab(); // remove
    await user.keyboard(" ");
    expect(handlers.onRemove).toHaveBeenCalledOnce();
    await user.tab(); // retry
    await user.keyboard("{Enter}");
    expect(handlers.onRetry).toHaveBeenCalledOnce();
    await user.tab(); // continue without attachment
    await user.keyboard("{Enter}");
    expect(handlers.onRemove).toHaveBeenCalledTimes(2);
    expect(submit).not.toHaveBeenCalled();
    await user.tab(); // picker
    await user.tab(); // send remains available
    await user.keyboard("{Enter}");
    expect(submit).toHaveBeenCalledOnce();
  });

  it("provides a readable fallback when the controller supplies no error", () => {
    render(<TooltipProvider><AttachmentChip filename={filename} phase="failed" {...callbacks()} /></TooltipProvider>);
    expect(screen.getByRole("alert")).toHaveTextContent("Bitte versuchen Sie es erneut oder entfernen Sie das Dokument.");
  });
});

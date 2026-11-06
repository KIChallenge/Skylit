import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ResultCard } from "./result-cards";
import { formatSamplerAnswer } from "./sampler-question-card";

const card = (multiple: boolean) => ({
  type: "sampler_question",
  question: {
    step: multiple ? "S_P" : "S_O",
    step_label: multiple ? "Beschwerde · Auslöser und Linderung" : "Beschwerde · Beginn",
    position: multiple ? 2 : 1,
    total: 12,
    question: multiple ? "Was verstärkt oder lindert die Kopfschmerzen?" : "Seit wann haben Sie die Kopfschmerzen?",
    options: multiple ? ["Licht", "Ruhe", "Bewegung"] : ["Seit heute", "Seit gestern", "Seit Wochen"],
    multiple,
    free_text_label: "In eigenen Worten beschreiben (optional)",
  },
});

beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("SAMPLER question card", () => {
  it("sends one choice with the description as one chat message", () => {
    const onAnswer = vi.fn();
    render(<ResultCard card={card(false)} onSend={onAnswer} latest />);
    expect(screen.getByRole("heading", { name: "Seit wann haben Sie die Kopfschmerzen?" })).toBeInTheDocument();
    expect(screen.getByText("Frage 1 von 12")).toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Antworten" });
    expect(send).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: "Seit heute" }));
    fireEvent.click(screen.getByRole("radio", { name: "Seit gestern" }));
    fireEvent.change(screen.getByLabelText("In eigenen Worten beschreiben (optional)"), { target: { value: " nach der Arbeit " } });
    fireEvent.click(send);

    expect(onAnswer).toHaveBeenCalledWith("Beschwerde · Beginn: Seit gestern – nach der Arbeit");
    expect(screen.getByRole("status")).toHaveTextContent("Antwort gesendet.");
    expect(screen.getByRole("radio", { name: "Seit heute" })).toBeDisabled();
  });

  it("allows several choices when the question allows it", () => {
    const onAnswer = vi.fn();
    render(<ResultCard card={card(true)} onSend={onAnswer} latest />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Licht" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Ruhe" }));
    fireEvent.click(screen.getByRole("button", { name: "Antworten" }));
    expect(onAnswer).toHaveBeenCalledWith("Beschwerde · Auslöser und Linderung: Licht, Ruhe");
  });

  it("renders older questions read-only", () => {
    render(<ResultCard card={card(false)} />);
    expect(screen.queryByRole("button", { name: "Antworten" })).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Seit heute" })).toBeDisabled();
    expect(screen.getByText("Diese Frage ist abgeschlossen.")).toBeInTheDocument();
  });

  it("drops a broken question card", () => {
    render(<ResultCard card={{ type: "sampler_question", question: { question: "Nur Text" } }} />);
    expect(screen.getByText("Ergebnis nicht verfügbar.")).toBeInTheDocument();
  });

  it("formats a description-only answer", () => {
    expect(formatSamplerAnswer("Allergien", [], "Penicillin")).toBe("Allergien: Penicillin");
  });
});

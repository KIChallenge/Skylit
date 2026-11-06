import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { Message } from "@/lib/api";

import { SamplerSessionCard } from "./sampler-session-card";
import { groupSamplerTurns, stripStepLabel, type SamplerStep } from "./sampler-session";

const question = (step: string, label: string, position: number, text: string) => ({
  type: "sampler_question",
  question: {
    step, step_label: label, position, total: 12, question: text,
    options: ["Seit heute", "Seit gestern"], multiple: false, free_text_label: "Beschreibung",
  },
});
const ONSET = question("S_O", "Beschwerde · Beginn", 1, "Seit wann?");
const TRIGGER = question("S_P", "Beschwerde · Auslöser und Linderung", 2, "Was hilft?");

let counter = 0;
const msg = (role: "user" | "assistant", content: string, cards: unknown[] = []): Message & { cards: unknown[] } =>
  ({ id: `m${counter += 1}`, role, content, created_at: "", cards } as unknown as Message & { cards: unknown[] });
const cardsOf = (message: Message) => (message as Message & { cards: unknown[] }).cards;
const idle = { streaming: false, text: "", cards: [] };

beforeEach(() => {
  counter = 0;
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("SAMPLER grouping", () => {
  it("shows one session at the first question and hides later turns and answers", () => {
    const messages = [
      msg("user", "Ich habe Kopfschmerzen."),
      msg("assistant", "Kurze Fragen.", [ONSET]),
      msg("user", "Beschwerde · Beginn: Seit gestern"),
      msg("assistant", "Danke.", [TRIGGER]),
    ];
    const grouping = groupSamplerTurns(messages, cardsOf, idle);

    expect([...grouping.hidden]).toEqual(["m3", "m4"]);
    const session = grouping.sessions.get("m2")!;
    expect(session.state).toBe("asking");
    expect(session.answerable).toBe(true);
    expect(session.steps.map((step) => [step.question.step, step.answer])).toEqual([["S_O", "Seit gestern"], ["S_P", undefined]]);
  });

  it("shows the loading state and hides the short live text while the next question streams", () => {
    const messages = [msg("assistant", "", [ONSET]), msg("user", "Beschwerde · Beginn: Seit heute")];
    const grouping = groupSamplerTurns(messages, cardsOf, { streaming: true, text: "Danke.", cards: [] });
    expect(grouping.sessions.get("m1")!.state).toBe("loading");
    expect(grouping.hideLiveText).toBe(true);
    // A long live text is the summary: it streams visibly.
    const summary = groupSamplerTurns(messages, cardsOf, { streaming: true, text: "x".repeat(200), cards: [] });
    expect(summary.hideLiveText).toBe(false);
  });

  it("closes the session when the Lotse answers without a new question", () => {
    const messages = [
      msg("assistant", "", [ONSET]),
      msg("user", "Beschwerde · Beginn: Seit heute"),
      msg("assistant", "Zusammenfassung: … Wenden Sie sich an Ihre Hausärztin."),
    ];
    const grouping = groupSamplerTurns(messages, cardsOf, idle);
    expect(grouping.sessions.get("m1")!.state).toBe("done");
    expect(grouping.hidden.has("m3")).toBe(false);
    expect(grouping.hidden.has("m2")).toBe(true);
  });

  it("keeps an unrelated typed question as a normal bubble", () => {
    const messages = [
      msg("assistant", "", [ONSET]),
      msg("user", "Wie beantrage ich Pflegegeld?"),
      msg("assistant", "Pflegegeld beantragen Sie bei der PVA."),
    ];
    const grouping = groupSamplerTurns(messages, cardsOf, idle);
    expect(grouping.hidden.has("m2")).toBe(false);
    expect(grouping.sessions.get("m1")!.state).toBe("done");
  });

  it("does not let an old question be answered while the Lotse streams", () => {
    const messages = [msg("assistant", "", [ONSET])];
    expect(groupSamplerTurns(messages, cardsOf, { streaming: true, text: "", cards: [] }).sessions.get("m1")!.answerable).toBe(false);
  });

  it("strips the step label from card answers only", () => {
    expect(stripStepLabel("Allergien: keine", "Allergien")).toBe("keine");
    expect(stripStepLabel("keine bekannt", "Allergien")).toBe("keine bekannt");
  });
});

describe("SAMPLER session card", () => {
  const steps: SamplerStep[] = [
    { question: ONSET.question as SamplerStep["question"], answer: "Seit gestern" },
    { question: TRIGGER.question as SamplerStep["question"] },
  ];

  it("shows the current question, sends the answer and lists earlier answers", () => {
    const onAnswer = vi.fn();
    render(<SamplerSessionCard session={{ steps, state: "asking", answerable: true }} onAnswer={onAnswer} />);
    expect(screen.getByRole("heading", { name: "Was hilft?" })).toBeInTheDocument();
    expect(screen.getByText("Frage 2 von 12")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ihre Angaben" })).toHaveTextContent("Beschwerde · BeginnSeit gestern");
    fireEvent.click(screen.getByRole("radio", { name: "Seit heute" }));
    fireEvent.click(screen.getByRole("button", { name: "Antworten" }));
    expect(onAnswer).toHaveBeenCalledWith("Beschwerde · Auslöser und Linderung: Seit heute");
  });

  it("shows a loading state between questions and a summary at the end", () => {
    const view = render(<SamplerSessionCard session={{ steps: [steps[0]], state: "loading", answerable: false }} />);
    expect(screen.getByRole("heading", { name: "Nächste Frage wird vorbereitet…" })).toBeInTheDocument();
    expect(screen.getByText("1 von 12 beantwortet")).toBeInTheDocument();
    view.rerender(<SamplerSessionCard session={{ steps: [steps[0]], state: "done", answerable: false }} />);
    expect(screen.getByRole("heading", { name: "Ihre Angaben" })).toBeInTheDocument();
    expect(screen.getByText("Aufnahme abgeschlossen")).toBeInTheDocument();
  });
});

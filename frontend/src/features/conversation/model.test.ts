// @vitest-environment node
import { describe, expect, it } from "vitest";
import type { Card, Conversation, Escalation, StreamEvent } from "@/lib/api";
import { conversationReducer, createConversationState } from "./model";
import type { ConversationState } from "./model";

const conversation: Conversation = {
  id: "conversation-1", title: "Pflege organisieren", created_at: "2026-11-05T10:00:00Z",
  updated_at: "2026-11-05T10:00:00Z", messages: [],
  case: {
    id: "case-1", title: "Pflege organisieren", subject: "parent", summary: "", steps: [],
    updated_at: "2026-11-05T10:00:00Z",
  },
};
const escalation: Escalation = {
  id: "escalation-1", reason_code: "medical_question", handover_summary: "Frage zur Dosierung.",
  target: { name: "Hausärztin", phone: null, url: null, hours: null, note: null },
  created_at: "2026-11-05T10:00:00Z",
};
const card: Card = { type: "email_draft", email: {
  to_label: "Pflegeberatung", to_email: null, subject: "Beratung", body: "Ich benötige Beratung.",
} };
const completed: StreamEvent = {
  type: "message.completed", message_id: "answer-1", finish_reason: "stop",
  usage: { prompt_tokens: 10, completion_tokens: 20, cached_tokens: 0 },
};

function start() {
  return conversationReducer(createConversationState(conversation), {
    type: "turn.started", message: { content: "Welche Hilfe gibt es?", document_ids: ["document-1"] },
  });
}
function events(state: ConversationState, ...items: StreamEvent[]) {
  return items.reduce(conversationReducer, state);
}

describe("conversationReducer", () => {
  it("appends deltas without mutating snapshots and exposes transparency only on completion", () => {
    const initial = start();
    const created = conversationReducer(initial, {
      type: "message.created", message_id: "answer-1", conversation_id: conversation.id,
    });
    expect(created.currentAnswer?.id).toBe("answer-1");
    expect(created.completedMessageId).toBeNull();
    const partial = events(created,
      { type: "status", stage: "writing", label: "Antwort wird geschrieben" },
      { type: "text.delta", delta: "Pflegegeld " }, { type: "text.delta", delta: "könnte helfen." });
    expect(partial.currentAnswer?.content).toBe("Pflegegeld könnte helfen.");
    expect(partial.messages[0]).toMatchObject({ role: "user", id: null, document_ids: ["document-1"] });
    expect(partial.messages[1]).toBe(partial.currentAnswer);
    expect(partial.progressLabel).toBe("Antwort wird geschrieben");
    expect(initial.currentAnswer?.content).toBe("");
    const source = { title: "Pflegegeld", publisher: "PVA", url: "https://example.test/pflegegeld" };
    const done = events(partial, { type: "sources", sources: [source] }, completed);
    expect(done).toMatchObject({ status: "completed", progressLabel: null, completedMessageId: "answer-1" });
    expect(done.currentAnswer).toMatchObject({ sources: [source], transparencyMessageId: "answer-1" });
    expect(conversationReducer(done, { type: "text.delta", delta: "verspätet" })).toBe(done);
  });

  it("keeps text through interleaved tool rounds and accepts only successful valid cards", () => {
    const initial = start();
    const state = events(initial,
      { type: "text.delta", delta: "Erster Schritt. " },
      { type: "status", stage: "tool", label: "Quelle wird gesucht" },
      { type: "tool.called", call_id: "call-1", name: "search_knowledge", label: "Offizielle Quellen werden gesucht" },
      { type: "tool.called", call_id: "call-2", name: "draft_email", label: "E-Mail-Entwurf wird erstellt" },
      { type: "tool.result", call_id: "call-2", name: "draft_email", ok: true, card, error: null },
      { type: "tool.result", call_id: "call-1", name: "search_knowledge", ok: true, card: null, error: null },
      { type: "text.delta", delta: "Zweiter Schritt." },
      { type: "tool.result", call_id: "call-3", name: "broken", ok: true, card: { type: "office" } as Card, error: null },
      { type: "tool.result", call_id: "call-4", name: "draft_email", ok: false, card, error: "Nicht verfügbar." });
    expect(state.currentAnswer?.content).toBe("Erster Schritt. Zweiter Schritt.");
    expect(state.currentAnswer?.cards).toEqual([card]);
    expect(state.error).toBeNull();
    expect(state.status).toBe("streaming");
    expect(initial.currentAnswer?.cards).toEqual([]);
  });

  it("replaces the complete case instead of merging old steps", () => {
    const state = start();
    const updated = { ...conversation.case, title: "Neuer Titel", summary: "Pflegeberatung kontaktieren." };
    const result = conversationReducer(state, { type: "case.updated", case: updated });
    expect(result.case).toBe(updated);
    expect(state.case).toBe(conversation.case);
  });

  it.each([true, false])("deduplicates escalation cards for either event order: %s", (toolFirst) => {
    const tool: StreamEvent = {
      type: "tool.result", call_id: "call-1", name: "escalate", ok: true,
      card: { type: "escalation", escalation }, error: null,
    };
    const event: StreamEvent = { type: "escalation", escalation };
    const state = events(start(), ...(toolFirst ? [tool, event] : [event, tool]));
    expect(state.currentAnswer?.cards).toEqual([{ type: "escalation", escalation }]);
    expect(state.escalation).toEqual(escalation);
    expect(state.currentAnswer?.escalation_id).toBe(escalation.id);
  });

  it("shows emergency before text and preserves emergency, text, and cards after SSE error", () => {
    const emergency: StreamEvent = { type: "emergency", contacts: [escalation.target], message: "Sofort Hilfe rufen." };
    const urgent = conversationReducer(start(), emergency);
    expect(urgent.emergency?.message).toBe("Sofort Hilfe rufen.");
    expect(urgent.currentAnswer?.content).toBe("");
    const state = events(urgent,
      { type: "text.delta", delta: "Bitte rufen Sie Hilfe." },
      { type: "tool.result", call_id: "call-1", name: "draft_email", ok: true, card, error: null },
      { type: "error", code: "future_code", message: "Bitte später erneut versuchen.", retry_after: 5 });
    expect(state).toMatchObject({ status: "error", progressLabel: null, completedMessageId: null,
      emergency: urgent.emergency,
      error: { kind: "stream", code: "future_code", retryAfter: 5 } });
    expect(state.currentAnswer).toMatchObject({ content: "Bitte rufen Sie Hilfe.", cards: [card], emergency: urgent.emergency });
    expect(state.currentAnswer?.error).toBe(state.error);
    expect(conversationReducer(state, completed)).toBe(state);
  });

  it("preserves partial content after transport failure and explicit abort", () => {
    const partial = events(start(), { type: "text.delta", delta: "Teilantwort" });
    const error = { kind: "transport" as const, code: "timeout", message: "Zeitüberschreitung.", status: null };
    const failed = conversationReducer(partial, { type: "transport.failed", error });
    expect(failed.currentAnswer?.content).toBe("Teilantwort");
    expect(failed.error).toBe(error);
    const aborted = conversationReducer(partial, { type: "turn.aborted" });
    expect(aborted).toMatchObject({ status: "aborted", error: null, completedMessageId: null });
    expect(aborted.currentAnswer?.content).toBe("Teilantwort");
  });

  it("loads saved messages, validated cards, sources and case without inventing emergency contacts", () => {
    const saved: Conversation = { ...conversation, messages: [{
      id: "saved-1", role: "assistant", content: "Gespeicherte Antwort", created_at: conversation.created_at,
      document_ids: [], sources: [{ title: "Quelle", publisher: "PVA", url: "/api/documents/document-1/file" }],
      cards: [card, { type: "escalation", escalation }, { type: "unknown" }], escalation_id: escalation.id,
    }] };
    const state = createConversationState(saved);
    expect(state.case).toBe(saved.case);
    expect(state.currentAnswer?.cards).toEqual([card, { type: "escalation", escalation }]);
    expect(state.currentAnswer?.sources).toEqual(saved.messages[0].sources);
    expect(state.currentAnswer).toBe(state.messages[0]);
    expect(state.completedMessageId).toBe("saved-1");
    expect(state.escalation).toEqual(escalation);
    expect(state.emergency).toBeNull();
    expect(saved.messages[0].cards).toHaveLength(3);
  });

  it("starts a new answer while retaining previous messages and the latest case", () => {
    const done = events(start(), { type: "text.delta", delta: "Antwort eins" }, completed);
    const next = conversationReducer(done, { type: "turn.started", message: { content: "Noch eine Frage" } });
    expect(next.messages).toHaveLength(4);
    expect(next.messages[1].content).toBe("Antwort eins");
    expect(next.currentAnswer?.content).toBe("");
    expect(next.completedMessageId).toBeNull();
    expect(next.case).toBe(done.case);
    expect(conversationReducer(next, { type: "turn.started", message: { content: "Doppelt" } })).toBe(next);
  });
});

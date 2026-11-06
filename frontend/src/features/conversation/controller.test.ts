// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { createApiClient, TransportError } from "@/lib/api";
import type { ApiClient, Conversation, StreamEvent } from "@/lib/api";
import { createConversationController } from "./controller";
import type { ConversationState } from "./model";

const conversation: Conversation = {
  id: "conversation-1", title: "Pflege organisieren", messages: [],
  created_at: "2026-11-05T10:00:00Z", updated_at: "2026-11-05T10:00:00Z",
  case: {
    id: "case-1", title: "Pflege organisieren", subject: "parent", summary: "", steps: [],
    updated_at: "2026-11-05T10:00:00Z",
  },
};
const completed: StreamEvent = {
  type: "message.completed", message_id: "answer-1", finish_reason: "stop",
  usage: { prompt_tokens: 1, completion_tokens: 1, cached_tokens: 0 },
};

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
}
function setup(streamMessage: ApiClient["streamMessage"]) {
  const snapshots: ConversationState[] = [];
  const stream = vi.fn(streamMessage);
  const controller = createConversationController({ streamMessage: stream }, (state) => snapshots.push(state), conversation);
  return { controller, stream, snapshots };
}

describe("conversation controller", () => {
  it("publishes each delta synchronously and makes one injected API call", async () => {
    const { controller, stream, snapshots } = setup(async function* (id, message, options) {
      expect(id).toBe(conversation.id);
      expect(message).toEqual({ content: "Hilfe", document_ids: ["document-1"] });
      expect(options?.signal).toBeInstanceOf(AbortSignal);
      yield { type: "message.created", message_id: "answer-1", conversation_id: id };
      yield { type: "status", stage: "writing", label: "Antwort wird geschrieben" };
      yield { type: "text.delta", delta: "Erster " };
      // The callback must run before the generator resumes.
      expect(snapshots.at(-1)?.currentAnswer?.content).toBe("Erster ");
      yield { type: "text.delta", delta: "Schritt" };
      yield completed;
    });
    const pending = controller.send({ content: "Hilfe", document_ids: ["document-1"] });
    expect(snapshots[0].status).toBe("streaming");
    await expect(pending).resolves.toBe("completed");
    expect(snapshots).toHaveLength(6);
    expect(controller.getState()).toMatchObject({ status: "completed", completedMessageId: "answer-1" });
    expect(controller.getState().currentAnswer?.content).toBe("Erster Schritt");
    expect(stream).toHaveBeenCalledTimes(1);
  });

  it("rejects duplicate sends without adding messages or creating a second POST", async () => {
    const gate = deferred();
    const { controller, stream } = setup(async function* () {
      await gate.promise;
      yield completed;
    });
    const first = controller.send({ content: "Erste Frage" });
    await expect(controller.send({ content: "Doppelte Frage" })).resolves.toBe("busy");
    expect(controller.getState().messages).toHaveLength(2);
    expect(stream).toHaveBeenCalledTimes(1);
    gate.resolve();
    await expect(first).resolves.toBe("completed");
    await expect(controller.send({ content: "Nächste Frage" })).resolves.toBe("completed");
    expect(stream).toHaveBeenCalledTimes(2);
  });

  it("keeps emergency data and partial content after SSE error without automatic retry", async () => {
    const { controller, stream } = setup(async function* () {
      yield { type: "emergency", contacts: [], message: "Sofort Hilfe rufen." };
      yield { type: "text.delta", delta: "Teilantwort" };
      yield { type: "error", code: "overloaded", message: "Bitte erneut versuchen.", retry_after: 3 };
      throw new Error("The controller must stop after the terminal event.");
    });
    await expect(controller.send({ content: "Atemnot" })).resolves.toBe("error");
    expect(controller.getState()).toMatchObject({
      status: "error", emergency: { message: "Sofort Hilfe rufen." },
      error: { kind: "stream", code: "overloaded", retryAfter: 3 },
    });
    expect(controller.getState().currentAnswer?.content).toBe("Teilantwort");
    expect(stream).toHaveBeenCalledTimes(1);
    await controller.send({ content: "Erneut versuchen" });
    expect(stream).toHaveBeenCalledTimes(2);
  });

  it("keeps transport errors separate and preserves visible cards and text", async () => {
    const { controller, stream } = setup(async function* () {
      yield { type: "text.delta", delta: "Teilantwort" };
      yield { type: "tool.result", call_id: "call-1", name: "draft_email", ok: true, error: null,
        card: { type: "email_draft", email: { to_label: "Beratung", subject: "Frage", body: "Bitte um Beratung." } } };
      throw new TransportError("timeout", "Zeitüberschreitung.", { status: 504 });
    });
    await expect(controller.send({ content: "Hilfe" })).resolves.toBe("error");
    expect(controller.getState().error).toEqual({
      kind: "transport", code: "timeout", message: "Zeitüberschreitung.", status: 504,
    });
    expect(controller.getState().currentAnswer?.content).toBe("Teilantwort");
    expect(controller.getState().currentAnswer?.cards).toHaveLength(1);
    expect(stream).toHaveBeenCalledTimes(1);
  });

  it("handles a stream ending without a terminal event as a transport failure", async () => {
    const { controller, stream } = setup(async function* () {
      yield { type: "text.delta", delta: "Teilantwort" };
    });
    await expect(controller.send({ content: "Hilfe" })).resolves.toBe("error");
    expect(controller.getState().error).toMatchObject({ kind: "transport", code: "stream_incomplete" });
    expect(stream).toHaveBeenCalledTimes(1);
  });

  it("does not expose unexpected technical error details", async () => {
    const { controller } = setup(async function* () {
      yield { type: "text.delta", delta: "Teilantwort" };
      throw new Error("private internal details");
    });
    await controller.send({ content: "Hilfe" });
    expect(controller.getState().error).toMatchObject({ kind: "transport", code: "network_error" });
    expect(controller.getState().error?.message).not.toContain("private");
  });

  it("aborts immediately and ignores a late event from an API that delays cancellation", async () => {
    const gate = deferred();
    let signal: AbortSignal | undefined;
    const { controller, snapshots } = setup(async function* (_id, _message, options) {
      signal = options?.signal;
      yield { type: "text.delta", delta: "Teilantwort" };
      await gate.promise;
      yield { type: "text.delta", delta: "verspätet" };
    });
    const external = new AbortController();
    const pending = controller.send({ content: "Hilfe" }, { signal: external.signal });
    await vi.waitFor(() => expect(controller.getState().currentAnswer?.content).toBe("Teilantwort"));
    external.abort();
    expect(signal?.aborted).toBe(true);
    expect(controller.getState()).toMatchObject({ status: "aborted", error: null });
    const count = snapshots.length;
    gate.resolve();
    await expect(pending).resolves.toBe("aborted");
    expect(snapshots).toHaveLength(count);
    expect(controller.getState().currentAnswer?.content).toBe("Teilantwort");
  });

  it("skips an already aborted send without publishing or posting", async () => {
    const { controller, stream, snapshots } = setup(async function* () { yield completed; });
    const external = new AbortController();
    external.abort();
    await expect(controller.send({ content: "Hilfe" }, { signal: external.signal })).resolves.toBe("aborted");
    expect(stream).not.toHaveBeenCalled();
    expect(snapshots).toHaveLength(0);
  });

  it("replaces a conversation and ignores late events and failures from the replaced turn", async () => {
    const gate = deferred();
    const entered = deferred();
    let oldSignal: AbortSignal | undefined;
    const { controller, snapshots } = setup(async function* (id, _message, options) {
      if (id === conversation.id) {
        oldSignal = options?.signal;
        entered.resolve();
        await gate.promise;
        yield { type: "case.updated", case: { ...conversation.case, title: "Veralteter Fall" } };
        throw new TransportError("timeout", "Alter Fehler.");
      }
      yield { type: "text.delta", delta: "Neues Gespräch" };
      yield completed;
    });
    const old = controller.send({ content: "Altes Gespräch" });
    await entered.promise;
    const next = { ...conversation, id: "conversation-2", case: { ...conversation.case, id: "case-2" } };
    controller.selectConversation(next);
    expect(oldSignal?.aborted).toBe(true);
    await expect(controller.send({ content: "Neue Frage" })).resolves.toBe("completed");
    const count = snapshots.length;
    gate.resolve();
    await expect(old).resolves.toBe("aborted");
    expect(snapshots).toHaveLength(count);
    expect(controller.getState()).toMatchObject({ conversationId: next.id, case: next.case, error: null });
    expect(controller.getState().currentAnswer?.content).toBe("Neues Gespräch");
  });

  it("does not let a replaced turn clear the newer send lock for the same conversation", async () => {
    const firstGate = deferred();
    const secondGate = deferred();
    let calls = 0;
    const { controller, stream } = setup(async function* () {
      calls += 1;
      await (calls === 1 ? firstGate.promise : secondGate.promise);
      yield completed;
    });
    const first = controller.send({ content: "Erste Frage" });
    controller.selectConversation(conversation);
    const second = controller.send({ content: "Zweite Frage" });
    firstGate.resolve();
    await expect(first).resolves.toBe("aborted");
    await expect(controller.send({ content: "Doppelt" })).resolves.toBe("busy");
    secondGate.resolve();
    await expect(second).resolves.toBe("completed");
    expect(stream).toHaveBeenCalledTimes(2);
  });

  it("ignores a late rejection from a replaced turn", async () => {
    const gate = deferred();
    const { controller, snapshots } = setup(async function* () {
      await gate.promise;
      throw new TransportError("timeout", "Alter Fehler.");
      yield completed;
    });
    const pending = controller.send({ content: "Hilfe" });
    controller.selectConversation({ ...conversation, id: "conversation-2" });
    const count = snapshots.length;
    gate.resolve();
    await expect(pending).resolves.toBe("aborted");
    expect(snapshots).toHaveLength(count);
    expect(controller.getState().error).toBeNull();
  });

  it("treats transport abort as cancellation without an error message", async () => {
    const { controller } = setup(async function* () {
      yield { type: "text.delta", delta: "Teilantwort" };
      throw new TransportError("aborted", "Die Anfrage wurde abgebrochen.");
    });
    await expect(controller.send({ content: "Hilfe" })).resolves.toBe("aborted");
    expect(controller.getState()).toMatchObject({ status: "aborted", error: null });
  });

  it("sends exactly one real facade POST on a transport failure", async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({
      error: { code: "overloaded", message: "Bitte später erneut versuchen." },
    }), { status: 503, headers: { "Content-Type": "application/json" } }));
    const api = createApiClient({ baseUrl: "https://api.test", timeoutMs: 1000, fetch });
    const controller = createConversationController(api, vi.fn(), conversation);
    await expect(controller.send({ content: "Hilfe" })).resolves.toBe("error");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(controller.getState().error).toMatchObject({ kind: "transport", code: "overloaded", status: 503 });
  });
});

import { TransportError } from "@/lib/api";
import type { ApiClient, Conversation, MessageCreate } from "@/lib/api";

import { conversationReducer, createConversationState } from "./model";
import type { ConversationAction, ConversationState } from "./model";

export type SendResult = "completed" | "error" | "aborted" | "busy";

export interface ConversationController {
  getState(): ConversationState;
  /** Replaces the snapshot and aborts the previous turn, even for the same conversation ID. */
  selectConversation(conversation: Conversation): void;
  send(message: MessageCreate, options?: { signal?: AbortSignal }): Promise<SendResult>;
  abort(): void;
}

/** One controller owns one selected conversation. The callback receives each change synchronously. */
export function createConversationController(
  api: Pick<ApiClient, "streamMessage">,
  onChange: (state: ConversationState) => void,
  conversation: Conversation,
): ConversationController {
  let state = createConversationState(conversation);
  let active: { abortController: AbortController } | null = null;

  function dispatch(action: ConversationAction) {
    const next = conversationReducer(state, action);
    if (next === state) return;
    state = next;
    onChange(state);
  }

  function abort() {
    const previous = active;
    if (!previous) return;
    active = null; // Invalidate before abort listeners or callbacks can reenter.
    previous.abortController.abort();
    dispatch({ type: "turn.aborted" });
  }

  return {
    getState: () => state,
    selectConversation(next) {
      // Publish only the selected snapshot, without an intermediate old-conversation callback.
      const previous = active;
      active = null;
      state = createConversationState(next);
      previous?.abortController.abort();
      onChange(state);
    },
    abort,
    async send(message, { signal } = {}) {
      if (active) return "busy";
      if (signal?.aborted) return "aborted";
      const turn = { abortController: new AbortController() };
      active = turn;
      const conversationId = state.conversationId;
      const request = { ...message, document_ids: message.document_ids ? [...message.document_ids] : undefined };
      const cancel = () => { if (active === turn) abort(); };
      signal?.addEventListener("abort", cancel, { once: true });
      try {
        dispatch({ type: "turn.started", message: request });
        if (active !== turn) return "aborted";
        for await (const event of api.streamMessage(conversationId, request, { signal: turn.abortController.signal })) {
          if (active !== turn) return "aborted";
          dispatch(event);
          if (active !== turn) return "aborted";
          if (event.type === "message.completed") return "completed";
          if (event.type === "error") return "error";
        }
        if (active !== turn) return "aborted";
        throw new TransportError("stream_incomplete", "Die Antwort wurde unerwartet beendet. Bitte versuchen Sie es erneut.");
      } catch (caught) {
        if (active !== turn) return "aborted";
        if (turn.abortController.signal.aborted ||
          (caught instanceof TransportError && caught.code === "aborted") ||
          (caught instanceof Error && caught.name === "AbortError")) {
          dispatch({ type: "turn.aborted" });
          return "aborted";
        }
        const error = caught instanceof TransportError ? caught : new TransportError(
          "network_error", "Die Verbindung zum Server ist fehlgeschlagen. Bitte versuchen Sie es erneut.",
        );
        dispatch({ type: "transport.failed", error: {
          kind: "transport", code: error.code, message: error.message, status: error.status,
        } });
        return "error";
      } finally {
        signal?.removeEventListener("abort", cancel);
        if (active === turn) active = null;
      }
    },
  };
}

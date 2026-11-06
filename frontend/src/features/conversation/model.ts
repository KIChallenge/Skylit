import { toCard } from "@/lib/api";
import type {
  Card, Case, Conversation, Escalation, Message, MessageCreate, StreamEvent, StreamEventOf,
} from "@/lib/api";

export type ConversationError =
  | { kind: "stream"; code: string; message: string; retryAfter: number | null }
  | { kind: "transport"; code: string; message: string; status: number | null };

export type Emergency = Omit<StreamEventOf<"emergency">, "type">;

/** Local messages have no server ID or timestamp until the API supplies them. */
export interface ConversationMessage extends Omit<Message, "id" | "created_at" | "cards"> {
  id: string | null;
  created_at: string | null;
  cards: Card[];
  transparencyMessageId: string | null;
  emergency: Emergency | null;
  error: ConversationError | null;
}

export interface ConversationState {
  conversationId: string;
  messages: ConversationMessage[];
  /** Also contained in messages. Render messages once, without appending this again. */
  currentAnswer: ConversationMessage | null;
  status: "idle" | "streaming" | "completed" | "error" | "aborted";
  progressLabel: string | null;
  case: Case;
  escalation: Escalation | null;
  emergency: Emergency | null;
  error: ConversationError | null;
  /** Set only after message.completed, or when loading a saved assistant message. */
  completedMessageId: string | null;
}

export type ConversationAction = StreamEvent
  | { type: "turn.started"; message: MessageCreate }
  | { type: "turn.aborted" }
  | { type: "transport.failed"; error: Extract<ConversationError, { kind: "transport" }> };

function addCard(cards: Card[], card: Card): Card[] {
  if (card.type !== "escalation") return [...cards, card];
  const index = cards.findIndex((existing) =>
    existing.type === "escalation" && existing.escalation.id === card.escalation.id);
  return index < 0 ? [...cards, card] : cards.map((value, i) => i === index ? card : value);
}

function escalationFrom(cards: Card[]): Escalation | null {
  const card = cards.findLast((value) => value.type === "escalation");
  return card?.type === "escalation" ? card.escalation : null;
}

export function createConversationState(conversation: Conversation): ConversationState {
  const messages = conversation.messages.map((message): ConversationMessage => ({
    ...message,
    cards: message.cards.reduce<Card[]>((cards, value) => {
      const card = toCard(value);
      return card ? addCard(cards, card) : cards;
    }, []),
    transparencyMessageId: message.role === "assistant" ? message.id : null,
    emergency: null,
    error: null,
  }));
  const last = messages.at(-1);
  const currentAnswer = last?.role === "assistant" ? last : null;
  return {
    conversationId: conversation.id, messages, currentAnswer, status: "idle",
    progressLabel: null, case: conversation.case,
    escalation: escalationFrom(currentAnswer?.cards ?? []), emergency: null, error: null,
    completedMessageId: currentAnswer?.transparencyMessageId ?? null,
  };
}

function localMessage(role: Message["role"], content: string, documentIds: string[] = []): ConversationMessage {
  return {
    id: null, role, content, document_ids: [...documentIds], created_at: null,
    cards: [], sources: [], escalation_id: null, transparencyMessageId: null,
    emergency: null, error: null,
  };
}

function updateAnswer(state: ConversationState, patch: Partial<ConversationMessage>): ConversationState {
  if (!state.currentAnswer) return state;
  const currentAnswer = { ...state.currentAnswer, ...patch };
  return {
    ...state, currentAnswer,
    messages: state.messages.map((message) => message === state.currentAnswer ? currentAnswer : message),
  };
}

function fail(state: ConversationState, error: ConversationError): ConversationState {
  return updateAnswer({ ...state, status: "error", progressLabel: null, error }, { error });
}

/** Pure lifecycle and generated SSE reducer. Terminal turns ignore further stream events. */
export function conversationReducer(state: ConversationState, action: ConversationAction): ConversationState {
  if (action.type === "turn.started") {
    if (state.status === "streaming") return state;
    const currentAnswer = localMessage("assistant", "");
    return {
      ...state, messages: [...state.messages,
        localMessage("user", action.message.content, action.message.document_ids), currentAnswer],
      currentAnswer, status: "streaming", progressLabel: null,
      escalation: null, emergency: null, error: null, completedMessageId: null,
    };
  }
  if (state.status !== "streaming") return state;
  switch (action.type) {
    case "turn.aborted":
      return { ...state, status: "aborted", progressLabel: null };
    case "transport.failed":
      return fail(state, action.error);
    case "message.created":
      return action.conversation_id === state.conversationId
        ? updateAnswer(state, { id: action.message_id }) : state;
    case "status":
    case "tool.called":
      return { ...state, progressLabel: action.label };
    case "text.delta":
      return updateAnswer(state, { content: (state.currentAnswer?.content ?? "") + action.delta });
    case "tool.result": {
      const card = action.ok ? toCard(action.card) : null;
      if (!card) return state;
      return updateAnswer({
        ...state, escalation: card.type === "escalation" ? card.escalation : state.escalation,
      }, {
        cards: addCard(state.currentAnswer?.cards ?? [], card),
        ...(card.type === "escalation" ? { escalation_id: card.escalation.id } : {}),
      });
    }
    case "case.updated":
      return { ...state, case: action.case };
    case "emergency": {
      const emergency = { contacts: action.contacts, message: action.message };
      return updateAnswer({ ...state, emergency }, { emergency });
    }
    case "escalation": {
      const card = toCard({ type: "escalation", escalation: action.escalation });
      if (!card) return state;
      return updateAnswer({ ...state, escalation: action.escalation }, {
        cards: addCard(state.currentAnswer?.cards ?? [], card), escalation_id: action.escalation.id,
      });
    }
    case "sources":
      return updateAnswer(state, { sources: [...action.sources] });
    case "message.completed":
      return updateAnswer({
        ...state, status: "completed", progressLabel: null, completedMessageId: action.message_id,
      }, { id: action.message_id, transparencyMessageId: action.message_id });
    case "error":
      return fail(state, {
        kind: "stream", code: action.code, message: action.message, retryAfter: action.retry_after ?? null,
      });
    default: {
      const exhaustive: never = action;
      return exhaustive;
    }
  }
}

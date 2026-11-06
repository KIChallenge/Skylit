import type { Message } from "@/lib/api";
import type { ConversationMessage, ConversationState } from "@/features/conversation/model";

/** Preserve original indices while the live answer leaves the stored-message list. */
export function bridgeConversation(state: ConversationState) {
  const reserved = new Set(state.messages.flatMap((message) => message.id ? [message.id] : []));
  const used = new Set<string>();
  const details = new Map<string, ConversationMessage>();
  const messages: Message[] = [];
  for (const [index, message] of state.messages.entries()) {
    if (state.status === "streaming" && message === state.currentAnswer) continue;
    let id = message.id;
    if (!id || used.has(id)) {
      id = `local-${index}`;
      while (reserved.has(id) || used.has(id)) id = `_${id}`;
    }
    used.add(id);
    details.set(id, message);
    messages.push({ ...message, id, created_at: message.created_at ?? "" });
  }
  return {
    messages,
    details,
    responseText: state.status === "streaming" ? state.currentAnswer?.content ?? "" : "",
  };
}

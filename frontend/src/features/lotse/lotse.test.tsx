import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import { demoMe, demoPersonas } from "@/features/auth/demo-client";
import { previewCards } from "@/features/cards/fixtures";
import { syntheticCase } from "@/features/case/synthetic-case";
import { conversationReducer, createConversationState } from "@/features/conversation/model";
import { api, TransportError, type Conversation, type Document, type StreamEvent } from "@/lib/api";

import { bridgeConversation } from "./bridge";
import { ChatScreen } from "./chat-screen";
import { HomeRedirect, LoginScreen } from "./entry-screens";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const footer = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/api", async (original) => ({
  ...await original<typeof import("@/lib/api")>(),
  api: {
    getMe: vi.fn(), listConversations: vi.fn(), createConversation: vi.fn(), getConversation: vi.fn(),
    listPersonas: vi.fn(), login: vi.fn(), logout: vi.fn(), streamMessage: vi.fn(),
    uploadDocument: vi.fn(), getDocument: vi.fn(), updateCaseStep: vi.fn(),
    listCalendarEntries: vi.fn(), createCalendarEntry: vi.fn(), deleteCalendarEntry: vi.fn(),
  },
}));
vi.mock("@/features/transparency", () => ({
  AnswerFooter: (props: { messageId: string | null }) => {
    footer(props);
    return <p>Antwortangaben: {props.messageId ?? "ungespeichert"}</p>;
  },
}));

const conversation: Conversation = {
  id: "conversation-1", title: "Pflege organisieren", messages: [],
  created_at: "2026-11-05T09:00:00Z", updated_at: "2026-11-05T09:00:00Z",
  case: { ...syntheticCase, steps: syntheticCase.steps.slice(0, 1) },
};
const completed: StreamEvent = {
  type: "message.completed", message_id: "answer-1", finish_reason: "stop",
  usage: { prompt_tokens: 1, completion_tokens: 1, cached_tokens: 0 },
};
const document: Document = {
  id: "document-1", filename: "Brief.pdf", mime_type: "application/pdf", status: "ready",
  kind: null, extracted: null, created_at: conversation.created_at,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}
function view(element = <ChatScreen conversationId={conversation.id} />) {
  return render(<TooltipProvider>{element}</TooltipProvider>);
}
async function ready() {
  await screen.findByRole("textbox", { name: "Ihre Nachricht an den Lotsen" });
  await screen.findByRole("button", { name: /Persona-Menü/ });
}
async function send(content = "Bitte helfen Sie mir.") {
  await userEvent.type(screen.getByRole("textbox"), content);
  await userEvent.click(screen.getByRole("button", { name: "Senden" }));
}
function selectDocument() {
  fireEvent.change(screen.getByLabelText("Dokument auswählen"), {
    target: { files: [new File(["synthetisch"], "Brief.pdf", { type: "application/pdf" })] },
  });
}

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", { writable: true, value: vi.fn(() => ({
    matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn(),
  })) });
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
});
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getMe).mockResolvedValue(demoMe("maria"));
  vi.mocked(api.listCalendarEntries).mockResolvedValue([]);
  vi.mocked(api.getConversation).mockResolvedValue(conversation);
  vi.mocked(api.listConversations).mockResolvedValue([{ ...conversation, open_steps: 1 }]);
  vi.mocked(api.createConversation).mockResolvedValue({ ...conversation, id: "new-conversation" });
  vi.mocked(api.listPersonas).mockResolvedValue(demoPersonas);
  vi.mocked(api.login).mockResolvedValue(demoMe("maria"));
  vi.mocked(api.uploadDocument).mockResolvedValue(document);
  vi.mocked(api.getDocument).mockResolvedValue(document);
  vi.mocked(api.streamMessage).mockImplementation(async function* () { yield completed; });
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("conversation bridge", () => {
  it("separates streaming text and gives local messages stable, unique keys", () => {
    let state = createConversationState(conversation);
    state = conversationReducer(state, { type: "turn.started", message: { content: "Erste Frage" } });
    state = conversationReducer(state, { type: "text.delta", delta: "Erste Antwort" });
    const streaming = bridgeConversation(state);
    expect(streaming.messages.map((message) => message.content)).toEqual(["Erste Frage"]);
    expect(streaming.responseText).toBe("Erste Antwort");
    state = conversationReducer(state, completed);
    expect(bridgeConversation(state).messages[0].id).toBe(streaming.messages[0].id);
    state = conversationReducer(state, { type: "turn.started", message: { content: "Zweite Frage" } });
    state = conversationReducer(state, { type: "text.delta", delta: "Zweite Antwort" });
    const next = bridgeConversation(state);
    expect(next.messages.map((message) => message.content)).toEqual(["Erste Frage", "Erste Antwort", "Zweite Frage"]);
    expect(new Set(next.messages.map((message) => message.id)).size).toBe(next.messages.length);
    expect(next.messages.every((message) => Boolean(message.id))).toBe(true);
    expect(next.responseText).toBe("Zweite Antwort");
  });

  it("avoids collisions between server IDs and fallback IDs", () => {
    let state = createConversationState(conversation);
    state = conversationReducer(state, { type: "turn.started", message: { content: "Frage" } });
    state = conversationReducer(state, { ...completed, message_id: "local-0" });
    const ids = bridgeConversation(state).messages.map((message) => message.id);
    expect(new Set(ids).size).toBe(2);
    expect(ids).toContain("local-0");
  });
});

describe("chat integration", () => {
  it("loads the conversation and list in parallel after authentication", async () => {
    const snapshot = deferred<Conversation>();
    vi.mocked(api.getConversation).mockReturnValue(snapshot.promise);
    view();
    await waitFor(() => expect(api.listConversations).toHaveBeenCalledOnce());
    expect(api.getConversation).toHaveBeenCalledOnce();
    expect(screen.getByText("Gespräch wird geladen…")).toBeVisible();
    await act(async () => snapshot.resolve(conversation));
    await ready();
    expect(screen.getByRole("link", { name: /Pflege organisieren/ })).toHaveAttribute("aria-current", "page");
  });

  it("adopts case.updated and preserves onCaseChange through later text events", async () => {
    const gate = deferred<void>();
    const updatedCase = { ...conversation.case, title: "Aktueller Pflegefall" };
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield { type: "case.updated", case: updatedCase };
      await gate.promise;
      yield { type: "text.delta", delta: "Nächste Schritte" };
      yield completed;
    });
    const step = updatedCase.steps[0];
    vi.mocked(api.updateCaseStep).mockResolvedValue({ ...step, status: "done" });
    view();
    await ready();
    await send();
    await screen.findByRole("heading", { name: updatedCase.title });
    await userEvent.click(screen.getByRole("checkbox", { name: step.title }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Mein Fall · 0 offen" })).toBeInTheDocument());
    await act(async () => gate.resolve());
    await screen.findByText("Nächste Schritte");
    expect(screen.getByRole("checkbox", { name: step.title })).toBeChecked();
    expect(screen.getByRole("button", { name: "Mein Fall · 0 offen" })).toBeInTheDocument();
    expect(api.updateCaseStep).toHaveBeenCalledWith(step.id, "done");
  });

  it("starts upload on selection and waits before sending document_ids", async () => {
    const upload = deferred<Document>();
    vi.mocked(api.uploadDocument).mockReturnValue(upload.promise);
    view();
    await ready();
    selectDocument();
    expect(api.uploadDocument).toHaveBeenCalledWith(expect.objectContaining({ conversationId: conversation.id }), expect.anything());
    await send("Hier ist der Brief.");
    expect(screen.getByText("Dokument wird gelesen…")).toBeVisible();
    expect(api.streamMessage).not.toHaveBeenCalled();
    await act(async () => upload.resolve(document));
    await waitFor(() => expect(api.streamMessage).toHaveBeenCalledWith(
      conversation.id, { content: "Hier ist der Brief.", document_ids: [document.id] }, expect.anything(),
    ));
    expect(screen.queryByRole("group", { name: "Anhang: Brief.pdf" })).not.toBeInTheDocument();
  });

  it("blocks sending after upload failure and allows explicit upload retry", async () => {
    vi.mocked(api.uploadDocument).mockRejectedValueOnce(new TransportError("upload_failed", "Das Dokument konnte nicht geladen werden."));
    view();
    await ready();
    selectDocument();
    await screen.findByText("Dokument konnte nicht gelesen werden.");
    await send("Hier ist der Brief.");
    expect(api.streamMessage).not.toHaveBeenCalled();
    await screen.findByText("Ihre Nachricht wurde nicht gesendet.");
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen: Brief.pdf" }));
    await screen.findByText("Bereit");
    const failure = screen.getByText("Ihre Nachricht wurde nicht gesendet.").closest('[role="alert"]')!;
    await userEvent.click(within(failure as HTMLElement).getByRole("button", { name: "Erneut versuchen" }));
    await waitFor(() => expect(api.streamMessage).toHaveBeenCalledOnce());
    expect(vi.mocked(api.streamMessage).mock.calls[0][1].document_ids).toEqual([document.id]);
  });

  it("shows EmergencyBanner before a text delta and preserves it after errors", async () => {
    const gate = deferred<void>();
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield { type: "emergency", message: "Sofort Hilfe rufen.", contacts: [{ name: "Rettung", phone: "144", hours: null, note: null }] };
      await gate.promise;
      yield { type: "error", code: "unavailable", message: "Bitte versuchen Sie es erneut." };
    });
    view();
    await ready();
    await send("Meine Mutter hat starke Atemnot.");
    expect(await screen.findByRole("heading", { name: "Bitte holen Sie sofort Hilfe" })).toBeVisible();
    expect(screen.getByRole("link", { name: /144 anrufen/ })).toHaveAttribute("href", "tel:144");
    expect(screen.queryByLabelText("Laufende Antwort des Lotsen")).not.toBeInTheDocument();
    await act(async () => gate.resolve());
    expect(screen.getByRole("heading", { name: "Bitte holen Sie sofort Hilfe" })).toBeVisible();
    expect(api.streamMessage).toHaveBeenCalledOnce();
  });

  it("renders live text once and connects cards and footer after completion", async () => {
    const gate = deferred<void>();
    const card = previewCards[2];
    const sources = card.type === "leistung" ? [card.leistung.source] : [];
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield { type: "text.delta", delta: "Eine klare Antwort" };
      yield { type: "tool.result", call_id: "call-1", name: "get_leistung", ok: true, card };
      yield { type: "sources", sources };
      await gate.promise;
      yield completed;
    });
    view();
    await ready();
    await send();
    expect(await screen.findAllByText("Eine klare Antwort")).toHaveLength(1);
    expect(footer).not.toHaveBeenCalled();
    await act(async () => gate.resolve());
    expect(screen.getAllByText("Eine klare Antwort")).toHaveLength(1);
    expect(await screen.findByRole("heading", { name: "Pflegegeld" })).toBeVisible();
    expect(footer).toHaveBeenLastCalledWith({ messageId: "answer-1", initialSources: sources });
  });

  it("retries the last user text only on click", async () => {
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      yield { type: "error", code: "busy", message: "Bitte versuchen Sie es erneut." };
    });
    view();
    await ready();
    await send("Meine letzte Frage");
    await screen.findByText("Die Antwort konnte nicht geladen werden.");
    expect(api.streamMessage).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await waitFor(() => expect(api.streamMessage).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.streamMessage).mock.calls[1][1].content).toBe("Meine letzte Frage");
  });

  it("redirects 401 to /login", async () => {
    vi.mocked(api.getMe).mockRejectedValue(new TransportError("unauthorized", "Intern", { status: 401 }));
    view();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login"));
    expect(api.getConversation).not.toHaveBeenCalled();
    expect(screen.queryByText("Intern")).not.toBeInTheDocument();
  });

  it("shows a safe error with retry and a separate 404 state", async () => {
    vi.mocked(api.getConversation).mockRejectedValueOnce(new Error("SECRET_STACK"));
    const rendered = view();
    await screen.findByText("Ihr Gespräch konnte nicht geladen werden.");
    expect(screen.queryByText("SECRET_STACK")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await ready();
    rendered.unmount();
    vi.mocked(api.getConversation).mockRejectedValueOnce(new TransportError("not_found", "Intern", { status: 404 }));
    view();
    await screen.findByText("Dieses Gespräch wurde nicht gefunden.");
    expect(screen.getByRole("link", { name: "Zu meinen Gesprächen" })).toHaveAttribute("href", "/");
  });

  it("cancels an upload on removal without sending the waiting message", async () => {
    const upload = deferred<Document>();
    vi.mocked(api.uploadDocument).mockReturnValue(upload.promise);
    view();
    await ready();
    selectDocument();
    await send();
    const options = vi.mocked(api.uploadDocument).mock.calls[0][1];
    await userEvent.click(screen.getByRole("button", { name: "Entfernen: Brief.pdf" }));
    expect(options?.signal?.aborted).toBe(true);
    await act(async () => upload.resolve(document));
    expect(api.streamMessage).not.toHaveBeenCalled();
  });

  it("aborts stream and upload on conversation change and ignores late results", async () => {
    const gate = deferred<void>();
    const upload = deferred<Document>();
    vi.mocked(api.uploadDocument).mockReturnValue(upload.promise);
    vi.mocked(api.streamMessage).mockImplementation(async function* () {
      await gate.promise;
      yield { type: "text.delta", delta: "Veraltete Antwort" };
      yield completed;
    });
    const rendered = view();
    await ready();
    await send();
    selectDocument();
    const streamOptions = vi.mocked(api.streamMessage).mock.calls[0][2];
    const uploadOptions = vi.mocked(api.uploadDocument).mock.calls[0][1];
    const next = { ...conversation, id: "conversation-2" };
    vi.mocked(api.getConversation).mockResolvedValue(next);
    rendered.rerender(<TooltipProvider><ChatScreen conversationId={next.id} /></TooltipProvider>);
    expect(streamOptions?.signal?.aborted).toBe(true);
    expect(uploadOptions?.signal?.aborted).toBe(true);
    await act(async () => { upload.resolve(document); gate.resolve(); });
    await ready();
    expect(screen.queryByText("Veraltete Antwort")).not.toBeInTheDocument();
  });

  it("cancels a waiting upload on unmount and prevents a later send", async () => {
    const upload = deferred<Document>();
    vi.mocked(api.uploadDocument).mockReturnValue(upload.promise);
    const rendered = view();
    await ready();
    selectDocument();
    await send();
    const options = vi.mocked(api.uploadDocument).mock.calls[0][1];
    rendered.unmount();
    expect(options?.signal?.aborted).toBe(true);
    await act(async () => upload.resolve(document));
    expect(api.streamMessage).not.toHaveBeenCalled();
  });

  it("creates a conversation and navigates without duplicate clicks", async () => {
    const created = deferred<Conversation>();
    vi.mocked(api.createConversation).mockReturnValue(created.promise);
    view();
    await ready();
    await userEvent.dblClick(screen.getByRole("button", { name: "Neues Gespräch" }));
    expect(api.createConversation).toHaveBeenCalledOnce();
    await act(async () => created.resolve({ ...conversation, id: "new-conversation" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/chat/new-conversation"));
  });
});

describe("entry routes", () => {
  it("opens the newest conversation by updated_at with replace", async () => {
    vi.mocked(api.listConversations).mockResolvedValue([
      { ...conversation, id: "old", open_steps: 0 },
      { ...conversation, id: "new", updated_at: "2026-11-06T09:00:00Z", open_steps: 0 },
    ]);
    view(<HomeRedirect />);
    expect(screen.getByText("Ihr Gespräch wird geöffnet…")).toBeVisible();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/chat/new"));
    expect(api.createConversation).not.toHaveBeenCalled();
  });

  it("redirects unauthenticated home visitors", async () => {
    vi.mocked(api.getMe).mockRejectedValue(new TransportError("unauthorized", "Intern", { status: 401 }));
    view(<HomeRedirect />);
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login"));
    expect(api.listConversations).not.toHaveBeenCalled();
  });

  it("opens a new conversation after persona login", async () => {
    vi.mocked(api.listConversations).mockResolvedValue([]);
    view(<StrictMode><LoginScreen /></StrictMode>);
    await userEvent.click(await screen.findByRole("button", { name: "Als Maria Berger anmelden" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/chat/new-conversation"));
    expect(api.login).toHaveBeenCalledWith("maria");
    expect(api.getMe).not.toHaveBeenCalled();
    expect(api.createConversation).toHaveBeenCalledOnce();
  });
});

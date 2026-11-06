/**
 * Typed API facade over the transport. One function per backend route the UI uses.
 * Types come from `./generated/schema.d.ts` through `./types.ts`.
 */

import { config } from "@/lib/config";
import { createHttpClient } from "@/lib/transport";
import type { HttpClient, HttpClientConfig } from "@/lib/transport";

import { isKnownStreamEvent, resolveApiUrl } from "./adapters";
import type {
  CalendarEntry,
  CalendarEntryCreate,
  Case,
  CaseStep,
  CaseStepStatus,
  Conversation,
  ConversationSummary,
  Document,
  Me,
  ProfileUpdate,
  MessageCreate,
  MessageTransparency,
  Persona,
  StreamEvent,
} from "./types";

/** Per-call options. The transport aborts the request on `signal` or after `timeoutMs`. */
export interface CallOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export interface StreamCallOptions extends CallOptions {
  /** Longest pause between two chunks. Default: the client setting. */
  idleTimeoutMs?: number;
}

export interface UploadInput {
  /** A `File` keeps its name. Give `filename` for a plain `Blob`. */
  file: Blob;
  filename?: string;
  conversationId?: string;
}

export interface ApiClientConfig extends HttpClientConfig {
  /** Ready transport, for tests. Then `fetch` and the timeouts are ignored. */
  http?: HttpClient;
}

export interface ApiClient {
  listPersonas(options?: CallOptions): Promise<Persona[]>;
  login(personaId: string, options?: CallOptions): Promise<Me>;
  logout(options?: CallOptions): Promise<void>;
  getMe(options?: CallOptions): Promise<Me>;
  /** Change profile settings such as the answer depth. Returns the updated user. */
  updateProfile(update: ProfileUpdate, options?: CallOptions): Promise<Me>;

  listConversations(options?: CallOptions): Promise<ConversationSummary[]>;
  createConversation(title?: string, options?: CallOptions): Promise<Conversation>;
  getConversation(conversationId: string, options?: CallOptions): Promise<Conversation>;

  getCase(conversationId: string, options?: CallOptions): Promise<Case>;
  updateCaseStep(stepId: string, status: CaseStepStatus, options?: CallOptions): Promise<CaseStep>;

  /** Send one multipart upload. The returned document has `status: "processing"`. */
  uploadDocument(input: UploadInput, options?: CallOptions): Promise<Document>;
  /** Read the current document status. The upload feature owns the polling loop. */
  getDocument(documentId: string, options?: CallOptions): Promise<Document>;

  getTransparency(messageId: string, options?: CallOptions): Promise<MessageTransparency>;

  /** All calendar entries of the logged-in user, earliest first. */
  listCalendarEntries(options?: CallOptions): Promise<CalendarEntry[]>;
  /** Save a manual entry, or an appointment proposal by `appointment_id`. Saving a proposal twice returns the same entry. */
  createCalendarEntry(entry: CalendarEntryCreate, options?: CallOptions): Promise<CalendarEntry>;
  deleteCalendarEntry(entryId: string, options?: CallOptions): Promise<void>;

  /**
   * Send one message and yield its SSE events. The POST starts with the loop.
   * The facade never repeats it: every POST starts a new agent turn.
   * Event types outside the generated union drop out.
   */
  streamMessage(
    conversationId: string,
    message: MessageCreate,
    options?: StreamCallOptions,
  ): AsyncGenerator<StreamEvent, void, undefined>;

  /** Prefix `/api/...` URLs with the backend origin. Absolute URLs stay unchanged. */
  resolveUrl(url: string): string;
  /** Download link for an uploaded document. */
  documentFileUrl(documentId: string): string;
}

const id = (value: string) => encodeURIComponent(value);

/** Create a facade. Tests inject `fetch` or a ready `http` transport. */
export function createApiClient(clientConfig: ApiClientConfig): ApiClient {
  const { http: injected, ...httpConfig } = clientConfig;
  const http = injected ?? createHttpClient(httpConfig);
  const origin = clientConfig.baseUrl.replace(/\/+$/, "");

  return {
    listPersonas: (options) => http.get<Persona[]>("/api/personas", options),
    login: (personaId, options) =>
      http.post<Me>("/api/auth/login", { persona_id: personaId }, options),
    logout: async (options) => {
      await http.post<undefined>("/api/auth/logout", undefined, options);
    },
    getMe: (options) => http.get<Me>("/api/me", options),
    updateProfile: (update, options) => http.patch<Me>("/api/me/profile", update, options),

    listConversations: (options) =>
      http.get<ConversationSummary[]>("/api/conversations", options),
    createConversation: (title, options) =>
      http.post<Conversation>("/api/conversations", title === undefined ? {} : { title }, options),
    getConversation: (conversationId, options) =>
      http.get<Conversation>(`/api/conversations/${id(conversationId)}`, options),

    getCase: (conversationId, options) =>
      http.get<Case>(`/api/conversations/${id(conversationId)}/case`, options),
    updateCaseStep: (stepId, status, options) =>
      http.patch<CaseStep>(`/api/case-steps/${id(stepId)}`, { status }, options),

    uploadDocument: ({ file, filename, conversationId }, options) => {
      const form = new FormData();
      if (filename === undefined) form.set("file", file);
      else form.set("file", file, filename);
      if (conversationId !== undefined) form.set("conversation_id", conversationId);
      return http.post<Document>("/api/documents", form, options);
    },
    getDocument: (documentId, options) =>
      http.get<Document>(`/api/documents/${id(documentId)}`, options),

    getTransparency: (messageId, options) =>
      http.get<MessageTransparency>(`/api/messages/${id(messageId)}/transparency`, options),

    listCalendarEntries: (options) => http.get<CalendarEntry[]>("/api/calendar-entries", options),
    createCalendarEntry: (entry, options) => http.post<CalendarEntry>("/api/calendar-entries", entry, options),
    deleteCalendarEntry: async (entryId, options) => {
      await http.delete<undefined>(`/api/calendar-entries/${id(entryId)}`, options);
    },

    async *streamMessage(conversationId, message, options = {}) {
      const events = http.stream<StreamEvent>(
        `/api/conversations/${id(conversationId)}/messages`,
        { ...options, method: "POST", body: message },
      );
      for await (const event of events) {
        if (isKnownStreamEvent(event)) yield event;
      }
    },

    resolveUrl: (url) => resolveApiUrl(url, origin),
    documentFileUrl: (documentId) => `${origin}/api/documents/${id(documentId)}/file`,
  };
}

let defaultClient: ApiClient | undefined;

/**
 * The central instance with `config.apiUrl`, `apiTimeoutMs` and `streamIdleTimeoutMs`.
 * It reads the config on first use, so a missing variable fails there and not at import.
 */
export function getApiClient(): ApiClient {
  defaultClient ??= createApiClient({
    baseUrl: config.apiUrl,
    timeoutMs: config.apiTimeoutMs,
    streamIdleTimeoutMs: config.streamIdleTimeoutMs,
  });
  return defaultClient;
}

/** Shortcut to the central instance: `api.getMe()`. */
export const api: ApiClient = new Proxy({} as ApiClient, {
  get: (_target, key) => getApiClient()[key as keyof ApiClient],
});

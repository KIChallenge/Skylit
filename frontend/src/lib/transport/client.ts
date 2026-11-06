/** HTTP and POST-SSE client on `fetch`. The caller injects all configuration. */

import { TransportError, failure, httpError } from "./errors.ts";
import { createSseParser, decodeSseEvent } from "./sse.ts";
import type { SseEventBase, UnknownSseEvent } from "./sse.ts";

/** The backend ends every turn with exactly one of these events (contracts.md §2). */
export const DEFAULT_TERMINAL_EVENTS: readonly string[] = [
  "message.completed",
  "error",
];

export interface HttpClientConfig {
  /** Origin of the backend. Use `""` for the same origin. */
  baseUrl: string;
  /** Limit for a full request. For a stream: limit until the response headers arrive. */
  timeoutMs: number;
  /** Limit between two stream chunks. Default: `timeoutMs`. */
  streamIdleTimeoutMs?: number;
  /** Replacement for the global `fetch`, for tests. */
  fetch?: typeof fetch;
}

export interface RequestOptions {
  method?: string;
  /** `FormData` goes out unchanged. All other values go out as JSON. */
  body?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
  timeoutMs?: number;
}

export type BodylessOptions = Omit<RequestOptions, "method" | "body">;

export interface StreamOptions extends RequestOptions {
  idleTimeoutMs?: number;
  /** Event types that end the stream. Default: `DEFAULT_TERMINAL_EVENTS`. */
  terminalEvents?: readonly string[];
}

export interface HttpClient {
  /** Return the parsed JSON body, or `undefined` for 204 and other empty bodies. */
  request<T = unknown>(path: string, options?: RequestOptions): Promise<T>;
  get<T = unknown>(path: string, options?: BodylessOptions): Promise<T>;
  post<T = unknown>(path: string, body?: unknown, options?: BodylessOptions): Promise<T>;
  patch<T = unknown>(path: string, body?: unknown, options?: BodylessOptions): Promise<T>;
  delete<T = unknown>(path: string, options?: BodylessOptions): Promise<T>;
  /**
   * Send one request (default: POST) when iteration starts, and yield each event
   * as soon as its block is complete. The client never repeats the request.
   */
  stream<E extends SseEventBase = UnknownSseEvent>(
    path: string,
    options?: StreamOptions,
  ): AsyncGenerator<E, void, undefined>;
}

export function createHttpClient(config: HttpClientConfig): HttpClient {
  const baseUrl = config.baseUrl.replace(/\/+$/, "");
  // Resolve the global at call time: a detached browser `fetch` throws.
  const doFetch: typeof fetch =
    config.fetch ?? ((input, init) => globalThis.fetch(input, init));

  function send(
    path: string,
    options: RequestOptions,
    defaultMethod: string,
    accept: string,
    signal: AbortSignal,
  ): Promise<Response> {
    const headers = new Headers(options.headers);
    if (!headers.has("Accept")) headers.set("Accept", accept);

    const init: RequestInit = {
      method: options.method ?? defaultMethod,
      credentials: "include",
      headers,
      signal,
    };
    if (options.body instanceof FormData) {
      // The browser sets the multipart Content-Type with its boundary.
      headers.delete("Content-Type");
      init.body = options.body;
    } else if (options.body !== undefined) {
      if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(options.body);
    }
    return doFetch(`${baseUrl}${path.startsWith("/") ? path : `/${path}`}`, init);
  }

  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const scope = createRequestScope(options.signal);
    try {
      scope.throwIfStopped();
      scope.startTimer(options.timeoutMs ?? config.timeoutMs);
      const response = await scope.guard(
        send(path, options, "GET", "application/json", scope.signal),
      );
      const text = await scope.guard(response.text());
      if (!response.ok) throw httpError(response.status, text);
      if (text.trim() === "") return undefined as T;
      try {
        return JSON.parse(text) as T;
      } catch (cause) {
        throw failure("invalid_response", cause);
      }
    } catch (error) {
      throw scope.toTransportError(error);
    } finally {
      scope.close();
    }
  }

  async function* stream<E extends SseEventBase = UnknownSseEvent>(
    path: string,
    options: StreamOptions = {},
  ): AsyncGenerator<E, void, undefined> {
    const connectTimeoutMs = options.timeoutMs ?? config.timeoutMs;
    const idleTimeoutMs =
      options.idleTimeoutMs ?? config.streamIdleTimeoutMs ?? connectTimeoutMs;
    const terminalEvents = new Set(options.terminalEvents ?? DEFAULT_TERMINAL_EVENTS);
    const scope = createRequestScope(options.signal);
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;

    try {
      scope.throwIfStopped();
      scope.startTimer(connectTimeoutMs);
      const response = await scope.guard(
        send(path, options, "POST", "text/event-stream", scope.signal),
      );
      if (!response.ok) {
        throw httpError(response.status, await scope.guard(response.text()));
      }
      const contentType = response.headers.get("Content-Type") ?? "";
      if (!response.body || !contentType.toLowerCase().includes("text/event-stream")) {
        throw failure("invalid_response");
      }

      reader = response.body.getReader();
      const parser = createSseParser();
      while (true) {
        // The timer runs only during a read, so a slow consumer causes no timeout.
        scope.startTimer(idleTimeoutMs);
        const { done, value } = await scope.guard(reader.read());
        scope.clearTimer();
        if (done) throw failure("stream_incomplete");

        for (const message of parser.push(value)) {
          scope.throwIfStopped();
          const event = decodeSseEvent<E>(message);
          yield event;
          if (terminalEvents.has(event.type)) return;
        }
      }
    } catch (error) {
      throw scope.toTransportError(error);
    } finally {
      // This also runs when the consumer leaves its loop early.
      reader?.cancel().catch(() => {});
      scope.close();
    }
  }

  return {
    request,
    get: (path, options) => request(path, { ...options, method: "GET" }),
    post: (path, body, options) => request(path, { ...options, method: "POST", body }),
    patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
    delete: (path, options) => request(path, { ...options, method: "DELETE" }),
    stream,
  };
}

/** Joins the caller's signal and the timeout, and remembers which one fired first. */
function createRequestScope(external: AbortSignal | undefined) {
  const controller = new AbortController();
  let stopReason: "timeout" | "aborted" | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function clearTimer(): void {
    clearTimeout(timer);
    timer = undefined;
  }
  function stop(reason: "timeout" | "aborted"): void {
    stopReason ??= reason;
    clearTimer();
    controller.abort();
  }
  const onExternalAbort = () => stop("aborted");

  if (external?.aborted) stop("aborted");
  else external?.addEventListener("abort", onExternalAbort, { once: true });

  function stoppedError(): TransportError | null {
    return stopReason === null ? null : failure(stopReason);
  }

  return {
    signal: controller.signal,
    clearTimer,
    startTimer(ms: number): void {
      clearTimer();
      timer = setTimeout(() => stop("timeout"), ms);
    },
    throwIfStopped(): void {
      const error = stoppedError();
      if (error) throw error;
    },
    /** Reject at once on a stop, also when `promise` ignores the signal. */
    guard<T>(promise: Promise<T>): Promise<T> {
      return new Promise<T>((resolve, reject) => {
        const onStop = () => reject(stoppedError());
        if (controller.signal.aborted) onStop();
        else controller.signal.addEventListener("abort", onStop, { once: true });
        promise
          .then(resolve, reject)
          .finally(() => controller.signal.removeEventListener("abort", onStop));
      });
    },
    toTransportError(error: unknown): TransportError {
      if (error instanceof TransportError) return error;
      return stoppedError() ?? failure("network_error", error);
    },
    /** Release the timer and the connection. This does not set a stop reason. */
    close(): void {
      clearTimer();
      external?.removeEventListener("abort", onExternalAbort);
      controller.abort();
    },
  };
}

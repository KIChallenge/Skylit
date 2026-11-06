import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { TransportError, createHttpClient, createSseParser } from "./index.ts";
import type { SseMessage, UnknownSseEvent } from "./index.ts";

const encoder = new TextEncoder();
const BASE_URL = "https://backend.test";
const SSE_HEADERS = { "Content-Type": "text/event-stream; charset=utf-8" };
const COMPLETED = 'event: message.completed\ndata: {"message_id":"m1"}\n\n';

interface Call {
  url: string;
  init: RequestInit;
}

function fakeFetch(respond: (call: Call) => Response | Promise<Response>) {
  const calls: Call[] = [];
  const impl: typeof fetch = async (input, init) => {
    const call = { url: String(input), init: init ?? {} };
    calls.push(call);
    return respond(call);
  };
  return { calls, impl };
}

function clientFor(
  respond: (call: Call) => Response | Promise<Response>,
  timeoutMs = 1000,
) {
  const { calls, impl } = fakeFetch(respond);
  return { calls, client: createHttpClient({ baseUrl: BASE_URL, timeoutMs, fetch: impl }) };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** A body that the test feeds by hand, to prove that nothing waits for more bytes. */
function manualStream() {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
    cancel() {
      cancelled = true;
    },
  });
  return {
    response: new Response(body, { headers: SSE_HEADERS }),
    send: (text: string) => controller.enqueue(encoder.encode(text)),
    close: () => controller.close(),
    fail: (error: unknown) => controller.error(error),
    isCancelled: () => cancelled,
  };
}

function sseResponse(chunks: (string | Uint8Array)[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(typeof chunk === "string" ? encoder.encode(chunk) : chunk);
      }
      controller.close();
    },
  });
  return new Response(body, { headers: SSE_HEADERS });
}

async function collect<E>(stream: AsyncIterable<E>) {
  const events: E[] = [];
  let error: unknown;
  try {
    for await (const event of stream) events.push(event);
  } catch (caught) {
    error = caught;
  }
  return { events, error };
}

function parseAll(chunks: (string | Uint8Array)[]): SseMessage[] {
  const parser = createSseParser();
  return chunks.flatMap((chunk) =>
    parser.push(typeof chunk === "string" ? encoder.encode(chunk) : chunk),
  );
}

function typeOf(result: IteratorResult<UnknownSseEvent, void>): string | undefined {
  return result.done ? undefined : result.value.type;
}

function assertTransportError(
  error: unknown,
  code: string,
  status: number | null = null,
): asserts error is TransportError {
  assert.ok(error instanceof TransportError, `expected TransportError, got ${error}`);
  assert.equal(error.code, code);
  assert.equal(error.status, status);
  assert.ok(error.message.length > 0);
}

describe("HTTP client", () => {
  it("sends JSON with credentials to the joined URL and returns the parsed body", async () => {
    const { client, calls } = clientFor(() => json({ id: "c1" }));
    const result = await client.post<{ id: string }>("/api/conversations", { title: "Reha" });

    assert.deepEqual(result, { id: "c1" });
    assert.equal(calls[0].url, `${BASE_URL}/api/conversations`);
    assert.equal(calls[0].init.method, "POST");
    assert.equal(calls[0].init.credentials, "include");
    assert.equal(calls[0].init.body, '{"title":"Reha"}');
    const headers = new Headers(calls[0].init.headers);
    assert.equal(headers.get("Content-Type"), "application/json");
    assert.equal(headers.get("Accept"), "application/json");
  });

  it("normalises slashes between baseUrl and path", async () => {
    const { calls, impl } = fakeFetch(() => json({}));
    const client = createHttpClient({ baseUrl: `${BASE_URL}/`, timeoutMs: 1000, fetch: impl });
    await client.get("api/me");
    assert.equal(calls[0].url, `${BASE_URL}/api/me`);
  });

  it("sends FormData unchanged and without a Content-Type", async () => {
    const { client, calls } = clientFor(() => json({ id: "d1" }));
    const form = new FormData();
    form.set("file", new Blob(["PDF"]), "brief.pdf");
    await client.post("/api/documents", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    assert.equal(calls[0].init.body, form);
    assert.equal(calls[0].init.credentials, "include");
    assert.equal(new Headers(calls[0].init.headers).has("Content-Type"), false);
  });

  it("returns undefined for 204", async () => {
    const { client, calls } = clientFor(() => new Response(null, { status: 204 }));
    assert.equal(await client.delete("/api/conversations/c1"), undefined);
    assert.equal(calls[0].init.method, "DELETE");
    assert.equal(calls[0].init.body, undefined);
  });

  it("uses code and message of the backend error body for 401", async () => {
    const { client } = clientFor(() =>
      json({ error: { code: "unauthorized", message: "Bitte melden Sie sich an." } }, 401),
    );
    const error = await client.get("/api/me").catch((caught: unknown) => caught);
    assertTransportError(error, "unauthorized", 401);
    assert.equal(error.message, "Bitte melden Sie sich an.");
  });

  it("falls back to a German message for a plain 500", async () => {
    const { client } = clientFor(
      () => new Response("Internal Server Error", { status: 500 }),
    );
    const error = await client.get("/api/me").catch((caught: unknown) => caught);
    assertTransportError(error, "server_error", 500);
    assert.match(error.message, /nicht verfügbar/);
  });

  it("replaces an English reason phrase but keeps the backend code", async () => {
    const { client } = clientFor(() =>
      json({ error: { code: "not_found", message: "Not Found" } }, 404),
    );
    const error = await client.get("/api/nope").catch((caught: unknown) => caught);
    assertTransportError(error, "not_found", 404);
    assert.match(error.message, /nicht gefunden/);
  });

  it("reports a network error with its cause", async () => {
    const cause = new TypeError("Failed to fetch");
    const { client } = clientFor(() => {
      throw cause;
    });
    const error = await client.get("/api/me").catch((caught: unknown) => caught);
    assertTransportError(error, "network_error");
    assert.equal(error.cause, cause);
    assert.match(error.message, /Verbindung/);
  });

  it("reports invalid JSON in a 2xx body", async () => {
    const { client } = clientFor(() => new Response("<html>"));
    const error = await client.get("/api/me").catch((caught: unknown) => caught);
    assertTransportError(error, "invalid_response");
  });

  it("times out, also when fetch ignores the signal, and aborts the fetch", async () => {
    const { client, calls } = clientFor(() => new Promise<Response>(() => {}), 10);
    const error = await client.get("/api/me").catch((caught: unknown) => caught);
    assertTransportError(error, "timeout");
    assert.equal(calls[0].init.signal?.aborted, true);
  });

  it("lets one request override the timeout", async () => {
    const { client } = clientFor(() => new Promise<Response>(() => {}), 60_000);
    const error = await client
      .get("/api/me", { timeoutMs: 5 })
      .catch((caught: unknown) => caught);
    assertTransportError(error, "timeout");
  });

  it("reports a running request that the caller aborts", async () => {
    const { client, calls } = clientFor(() => new Promise<Response>(() => {}));
    const controller = new AbortController();
    const pending = client
      .get("/api/me", { signal: controller.signal })
      .catch((caught: unknown) => caught);
    await new Promise((resolve) => setTimeout(resolve, 0));
    controller.abort();

    assertTransportError(await pending, "aborted");
    assert.equal(calls[0].init.signal?.aborted, true);
  });

  it("sends nothing when the signal is already aborted", async () => {
    const { client, calls } = clientFor(() => json({}));
    const error = await client
      .get("/api/me", { signal: AbortSignal.abort() })
      .catch((caught: unknown) => caught);
    assertTransportError(error, "aborted");
    assert.equal(calls.length, 0);
  });
});

describe("SSE parser", () => {
  it("reassembles UTF-8 and fields that are split at every byte", () => {
    const text = 'event: text.delta\ndata: {"delta":"Größe 🩺 prüfen"}\n\n';
    const bytes = encoder.encode(text);
    const chunks = Array.from(bytes, (byte) => Uint8Array.of(byte));
    assert.deepEqual(parseAll(chunks), [
      { event: "text.delta", data: '{"delta":"Größe 🩺 prüfen"}' },
    ]);
  });

  it("handles CRLF, also when a chunk boundary splits the CRLF", () => {
    assert.deepEqual(
      parseAll(["event: status\r", '\ndata: {"a":1}\r\n\r', "\nevent: b\r\ndata: 2\r\n\r\n"]),
      [
        { event: "status", data: '{"a":1}' },
        { event: "b", data: "2" },
      ],
    );
  });

  it("dispatches on a final CR without waiting for the next chunk", () => {
    const parser = createSseParser();
    const messages = parser.push(encoder.encode('event: emergency\r\ndata: {}\r\n\r'));
    assert.deepEqual(messages, [{ event: "emergency", data: "{}" }]);
    assert.deepEqual(parser.push(encoder.encode("\n")), []);
  });

  it("handles a lone CR as a line end", () => {
    assert.deepEqual(parseAll(["event: a\rdata: 1\r\r"]), [{ event: "a", data: "1" }]);
  });

  it("ignores comments and unknown fields", () => {
    assert.deepEqual(
      parseAll([": keep-alive\n\nid: 7\nretry: 10\nfoo: bar\n:mid\ndata: 1\n\n"]),
      [{ event: null, data: "1" }],
    );
  });

  it("joins multi-line data with a line feed", () => {
    assert.deepEqual(parseAll(['data: {"a":\ndata:  1}\ndata:\n\n']), [
      { event: null, data: '{"a":\n 1}\n' },
    ]);
  });

  it("returns several events of one chunk and resets the event name", () => {
    assert.deepEqual(parseAll(["event: a\ndata: 1\n\ndata: 2\n\nevent: c\ndata: 3\n\n"]), [
      { event: "a", data: "1" },
      { event: null, data: "2" },
      { event: "c", data: "3" },
    ]);
  });

  it("skips a block without data and a block without its blank line", () => {
    assert.deepEqual(parseAll(["event: empty\n\nevent: open\ndata: 1\n"]), []);
  });
});

describe("POST-SSE stream", () => {
  it("posts once with credentials and SSE Accept header", async () => {
    const { client, calls } = clientFor(() => sseResponse([COMPLETED]));
    await collect(
      client.stream("/api/conversations/c1/messages", { body: { content: "Hallo" } }),
    );

    assert.equal(calls.length, 1);
    assert.equal(calls[0].init.method, "POST");
    assert.equal(calls[0].init.credentials, "include");
    assert.equal(calls[0].init.body, '{"content":"Hallo"}');
    assert.equal(new Headers(calls[0].init.headers).get("Accept"), "text/event-stream");
  });

  it("adds type from the event line and leaves all other data unchanged", async () => {
    const card = { type: "office", office: { name: "ÖGK" } };
    const { client } = clientFor(() =>
      sseResponse([
        `event: tool.result\ndata: ${JSON.stringify({ call_id: "1", ok: true, card, new_field: null })}\n\n`,
        COMPLETED,
      ]),
    );
    const { events, error } = await collect(client.stream("/x"));

    assert.equal(error, undefined);
    assert.deepEqual(events, [
      { type: "tool.result", call_id: "1", ok: true, card, new_field: null },
      { type: "message.completed", message_id: "m1" },
    ]);
  });

  it("delivers fragmented UTF-8 and several events per chunk in order", async () => {
    const first = encoder.encode('event: text.delta\ndata: {"delta":"Pflegegeld für Mütter"}\n\n');
    const split = first.indexOf(0xc3) + 1; // Inside the two bytes of "ü".
    const { client } = clientFor(() =>
      sseResponse([
        first.slice(0, split),
        first.slice(split),
        `event: text.delta\r\ndata: {"delta":"a"}\r\n\r\nevent: text.delta\r\ndata: {"delta":"b"}\r\n\r\n`,
        COMPLETED,
      ]),
    );
    const { events, error } = await collect(client.stream<UnknownSseEvent>("/x"));

    assert.equal(error, undefined);
    assert.deepEqual(
      events.map((event) => event.delta ?? event.type),
      ["Pflegegeld für Mütter", "a", "b", "message.completed"],
    );
  });

  it("makes emergency available before any text.delta exists", async () => {
    const body = manualStream();
    const { client } = clientFor(() => body.response);
    const stream = client.stream<UnknownSseEvent>("/x");

    const first = stream.next();
    await new Promise((resolve) => setTimeout(resolve, 0));
    body.send('event: emergency\ndata: {"contacts":[{"name":"Rettung"}],"message":"Hilfe"}\n\n');
    assert.deepEqual((await first).value, {
      type: "emergency",
      contacts: [{ name: "Rettung" }],
      message: "Hilfe",
    });

    const second = stream.next();
    body.send('event: text.delta\ndata: {"delta":"Hallo"}\n\n');
    assert.equal(typeOf(await second), "text.delta");

    const third = stream.next();
    body.send(COMPLETED);
    assert.equal(typeOf(await third), "message.completed");
    assert.equal((await stream.next()).done, true);
  });

  it("passes a backend error event through and ends without a transport error", async () => {
    const { client } = clientFor(() =>
      sseResponse([
        'event: error\ndata: {"code":"llm_timeout","message":"Bitte erneut","retry_after":3}\n\n',
      ]),
    );
    const { events, error } = await collect(client.stream("/x"));
    assert.equal(error, undefined);
    assert.deepEqual(events, [
      { type: "error", code: "llm_timeout", message: "Bitte erneut", retry_after: 3 },
    ]);
  });

  it("stops reading after the terminal event and cancels the body", async () => {
    const body = manualStream();
    const { client } = clientFor(() => body.response);
    const stream = client.stream("/x");
    const first = stream.next();
    await new Promise((resolve) => setTimeout(resolve, 0));
    body.send(COMPLETED);
    await first;

    assert.equal((await stream.next()).done, true);
    assert.equal(body.isCancelled(), true);
  });

  it("supports other terminal events through an option", async () => {
    const { client } = clientFor(() => sseResponse(['event: done\ndata: {}\n\n']));
    const { events, error } = await collect(client.stream("/x", { terminalEvents: ["done"] }));
    assert.equal(error, undefined);
    assert.equal(events.length, 1);
  });

  it("delivers earlier events, then fails on invalid JSON without a retry", async () => {
    const { client, calls } = clientFor(() =>
      sseResponse([
        'event: text.delta\ndata: {"delta":"ok"}\n\nevent: text.delta\ndata: {kaputt\n\n',
      ]),
    );
    const { events, error } = await collect(client.stream("/x"));

    assert.equal(events.length, 1);
    assertTransportError(error, "stream_invalid_event");
    assert.equal(calls.length, 1);
  });

  it("rejects JSON data that is not an object", async () => {
    const { client } = clientFor(() => sseResponse(["event: a\ndata: [1]\n\n"]));
    const { error } = await collect(client.stream("/x"));
    assertTransportError(error, "stream_invalid_event");
  });

  it("reports a missing terminal event without a retry", async () => {
    const { client, calls } = clientFor(() =>
      sseResponse(['event: text.delta\ndata: {"delta":"Hal"}\n\n']),
    );
    const { events, error } = await collect(client.stream("/x"));

    assert.equal(events.length, 1);
    assertTransportError(error, "stream_incomplete");
    assert.equal(calls.length, 1);
  });

  it("treats a terminal block without its blank line as a missing terminal event", async () => {
    const { client } = clientFor(() =>
      sseResponse(['event: message.completed\ndata: {"message_id":"m1"}\n']),
    );
    const { events, error } = await collect(client.stream("/x"));
    assert.equal(events.length, 0);
    assertTransportError(error, "stream_incomplete");
  });

  it("maps HTTP errors of the stream request", async () => {
    const unauthorized = clientFor(() =>
      json({ error: { code: "unauthorized", message: "Bitte melden Sie sich an." } }, 401),
    );
    assertTransportError(
      (await collect(unauthorized.client.stream("/x"))).error,
      "unauthorized",
      401,
    );

    const broken = clientFor(() => new Response("oops", { status: 500 }));
    assertTransportError((await collect(broken.client.stream("/x"))).error, "server_error", 500);
    assert.equal(broken.calls.length, 1);
  });

  it("rejects a 200 response that is not an event stream", async () => {
    const { client } = clientFor(() => json({ ok: true }));
    assertTransportError((await collect(client.stream("/x"))).error, "invalid_response");
  });

  it("reports a broken connection during the stream as a network error", async () => {
    const body = manualStream();
    const { client } = clientFor(() => body.response);
    const stream = client.stream("/x");
    const first = stream.next();
    await new Promise((resolve) => setTimeout(resolve, 0));
    body.fail(new TypeError("network error"));

    assertTransportError(await first.catch((caught: unknown) => caught), "network_error");
  });

  it("times out before the response headers arrive", async () => {
    const { client } = clientFor(() => new Promise<Response>(() => {}), 10);
    assertTransportError((await collect(client.stream("/x"))).error, "timeout");
  });

  it("times out when no chunk arrives within the idle timeout", async () => {
    const body = manualStream();
    const { client } = clientFor(() => body.response, 1000);
    const { events, error } = await (async () => {
      const pending = collect(client.stream("/x", { idleTimeoutMs: 20 }));
      await new Promise((resolve) => setTimeout(resolve, 0));
      body.send('event: text.delta\ndata: {"delta":"a"}\n\n');
      return pending;
    })();

    assert.equal(events.length, 1);
    assertTransportError(error, "timeout");
    assert.equal(body.isCancelled(), true);
  });

  it("does not time out while the consumer is busy", async () => {
    const body = manualStream();
    const { client } = clientFor(() => body.response, 1000);
    const stream = client.stream("/x", { idleTimeoutMs: 15 });
    const first = stream.next();
    await new Promise((resolve) => setTimeout(resolve, 0));
    body.send('event: text.delta\ndata: {"delta":"a"}\n\n');
    await first;

    await new Promise((resolve) => setTimeout(resolve, 40));
    body.send(COMPLETED);
    assert.equal(typeOf(await stream.next()), "message.completed");
  });

  it("reports a caller abort during the stream and cancels the body", async () => {
    const body = manualStream();
    const { client, calls } = clientFor(() => body.response);
    const controller = new AbortController();
    const stream = client.stream("/x", { signal: controller.signal });
    const first = stream.next();
    await new Promise((resolve) => setTimeout(resolve, 0));
    body.send('event: text.delta\ndata: {"delta":"a"}\n\n');
    await first;

    const second = stream.next().catch((caught: unknown) => caught);
    await new Promise((resolve) => setTimeout(resolve, 0));
    controller.abort();

    assertTransportError(await second, "aborted");
    assert.equal(body.isCancelled(), true);
    assert.equal(calls.length, 1);
  });

  it("delivers no more events of a chunk after an abort", async () => {
    const { client } = clientFor(() =>
      sseResponse(['event: a\ndata: {}\n\nevent: b\ndata: {}\n\n']),
    );
    const controller = new AbortController();
    const stream = client.stream("/x", { signal: controller.signal });
    assert.equal(typeOf(await stream.next()), "a");
    controller.abort();
    assertTransportError(await stream.next().catch((caught: unknown) => caught), "aborted");
  });

  it("sends nothing when the signal is already aborted", async () => {
    const { client, calls } = clientFor(() => sseResponse([COMPLETED]));
    const { error } = await collect(client.stream("/x", { signal: AbortSignal.abort() }));
    assertTransportError(error, "aborted");
    assert.equal(calls.length, 0);
  });

  it("closes the connection when the consumer leaves its loop", async () => {
    const body = manualStream();
    const { client, calls } = clientFor(() => body.response);
    const pending = (async () => {
      for await (const _event of client.stream("/x")) break;
    })();
    await new Promise((resolve) => setTimeout(resolve, 0));
    body.send('event: text.delta\ndata: {"delta":"a"}\n\n');
    await pending;

    assert.equal(body.isCancelled(), true);
    assert.equal(calls[0].init.signal?.aborted, true);
  });
});

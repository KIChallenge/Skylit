// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

import { TransportError } from "@/lib/transport";

import { createApiClient } from "./client";
import type { StreamEvent } from "./types";

const ORIGIN = "http://api.test";

interface Call {
  url: string;
  init: RequestInit;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sse(blocks: string[]): Response {
  return new Response(blocks.join(""), {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

/** Fake `fetch` that answers with the queued responses in order and records each call. */
function fakeBackend(...responses: Array<Response | (() => Promise<Response>)>) {
  const calls: Call[] = [];
  const fetch = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    calls.push({ url: String(input), init });
    const next = responses.shift();
    if (!next) throw new Error("unexpected request");
    return typeof next === "function" ? next() : next;
  });
  const client = createApiClient({ baseUrl: `${ORIGIN}/`, timeoutMs: 1_000, fetch });
  return { client, calls, fetch };
}

const me = {
  user_id: "6f0c1d1e-0000-4000-8000-000000000001",
  persona_id: "maria",
  display_name: "Maria Huber",
  profile: {
    language: "de",
    depth: "short",
    bundesland: "Wien",
    postal_code: "1100",
    insurer: "OEGK",
    date_of_birth: null,
  },
};

describe("auth", () => {
  it("logs in with the persona id and sends the cookie", async () => {
    const { client, calls } = fakeBackend(json(me));

    await expect(client.login("maria")).resolves.toEqual(me);

    expect(calls[0].url).toBe(`${ORIGIN}/api/auth/login`);
    expect(calls[0].init.method).toBe("POST");
    expect(calls[0].init.credentials).toBe("include");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ persona_id: "maria" });
  });

  it("resolves logout on 204 without a body", async () => {
    const { client, calls } = fakeBackend(new Response(null, { status: 204 }));

    await expect(client.logout()).resolves.toBeUndefined();
    expect(calls[0].url).toBe(`${ORIGIN}/api/auth/logout`);
  });

  it("raises a TransportError with the backend code", async () => {
    const { client } = fakeBackend(
      json({ error: { code: "unauthorized", message: "Bitte melden Sie sich an." } }, 401),
    );

    const error = await client.getMe().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(TransportError);
    expect(error).toMatchObject({ code: "unauthorized", status: 401 });
  });
});

describe("conversations and case", () => {
  it("creates a conversation with and without title", async () => {
    const { client, calls } = fakeBackend(json({ id: "c1" }, 201), json({ id: "c2" }, 201));

    await client.createConversation("Entlassung Mutter");
    await client.createConversation();

    expect(calls[0].url).toBe(`${ORIGIN}/api/conversations`);
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ title: "Entlassung Mutter" });
    expect(JSON.parse(String(calls[1].init.body))).toEqual({});
  });

  it("loads a conversation and encodes the path id", async () => {
    const { client, calls } = fakeBackend(json({ id: "a/b" }));

    await client.getConversation("a/b");
    expect(calls[0].url).toBe(`${ORIGIN}/api/conversations/a%2Fb`);
    expect(calls[0].init.method).toBe("GET");
  });

  it("patches the step status", async () => {
    const step = { id: "s1", status: "done" };
    const { client, calls } = fakeBackend(json(step));

    await expect(client.updateCaseStep("s1", "done")).resolves.toEqual(step);
    expect(calls[0].url).toBe(`${ORIGIN}/api/case-steps/s1`);
    expect(calls[0].init.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ status: "done" });
  });

  it("patches the profile, e.g. the answer length", async () => {
    const me = { user_id: "u1", profile: { depth: "detailed" } };
    const { client, calls } = fakeBackend(json(me));

    await expect(client.updateProfile({ depth: "detailed" })).resolves.toEqual(me);
    expect(calls[0].url).toBe(`${ORIGIN}/api/me/profile`);
    expect(calls[0].init.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ depth: "detailed" });
  });
});

describe("documents", () => {
  it("uploads multipart with file and conversation_id", async () => {
    const { client, calls } = fakeBackend(json({ id: "d1", status: "processing" }, 201));
    const file = new File(["%PDF-1.4"], "entlassungsbrief.pdf", { type: "application/pdf" });

    await client.uploadDocument({ file, conversationId: "c1" }, { timeoutMs: 30_000 });

    const body = calls[0].init.body;
    expect(calls[0].url).toBe(`${ORIGIN}/api/documents`);
    expect(body).toBeInstanceOf(FormData);
    const form = body as FormData;
    expect((form.get("file") as File).name).toBe("entlassungsbrief.pdf");
    expect(form.get("conversation_id")).toBe("c1");
    expect(new Headers(calls[0].init.headers).has("Content-Type")).toBe(false);
  });

  it("omits conversation_id when none is given", async () => {
    const { client, calls } = fakeBackend(json({ id: "d1" }, 201));

    await client.uploadDocument({ file: new Blob(["x"]), filename: "befund.png" });

    const form = calls[0].init.body as FormData;
    expect(form.has("conversation_id")).toBe(false);
    expect((form.get("file") as File).name).toBe("befund.png");
  });

  it("reports an upload rejection as TransportError", async () => {
    const { client } = fakeBackend(
      json({ error: { code: "unsupported_type", message: "Nur PDF, JPEG oder PNG." } }, 415),
    );

    await expect(client.uploadDocument({ file: new Blob(["x"]) })).rejects.toMatchObject({
      code: "unsupported_type",
      status: 415,
    });
  });

  it("builds absolute download URLs", () => {
    const { client } = fakeBackend();

    expect(client.documentFileUrl("d1")).toBe(`${ORIGIN}/api/documents/d1/file`);
    expect(client.resolveUrl("/api/form-drafts/f1/pdf")).toBe(`${ORIGIN}/api/form-drafts/f1/pdf`);
    expect(client.resolveUrl("https://www.gesundheit.gv.at/x")).toBe(
      "https://www.gesundheit.gv.at/x",
    );
  });
});

describe("transparency", () => {
  it("reads the transparency of one message", async () => {
    const transparency = {
      message_id: "m1",
      model: "eustella-demo",
      provider: null,
      sources: [],
      tools: [],
      retrieval: { query: null, chunks: [] },
      guardrails: [],
      escalation: null,
      confidence: { level: "mittel", reason: "Eine Quelle." },
      entries: [],
    };
    const { client, calls } = fakeBackend(json(transparency));

    await expect(client.getTransparency("m1")).resolves.toEqual(transparency);
    expect(calls[0].url).toBe(`${ORIGIN}/api/messages/m1/transparency`);
  });
});

describe("message stream", () => {
  it("yields typed events and drops unknown event types", async () => {
    const { client, calls } = fakeBackend(
      sse([
        'event: message.created\ndata: {"message_id":"m1","conversation_id":"c1"}\n\n',
        'event: future.event\ndata: {"x":1}\n\n',
        'event: text.delta\ndata: {"delta":"Hallo"}\n\n',
        'event: message.completed\ndata: {"message_id":"m1","finish_reason":"stop","usage":{"prompt_tokens":1,"completion_tokens":1,"cached_tokens":0}}\n\n',
      ]),
    );

    const events: StreamEvent[] = [];
    for await (const event of client.streamMessage("c1", { content: "Hallo", document_ids: ["d1"] })) {
      events.push(event);
    }

    expect(events.map((event) => event.type)).toEqual([
      "message.created",
      "text.delta",
      "message.completed",
    ]);
    expect(calls[0].url).toBe(`${ORIGIN}/api/conversations/c1/messages`);
    expect(calls[0].init.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({
      content: "Hallo",
      document_ids: ["d1"],
    });
  });

  it("does not repeat the POST after a failure", async () => {
    const { client, fetch } = fakeBackend(json({ error: { code: "llm_unavailable" } }, 503));

    const run = async () => {
      for await (const _event of client.streamMessage("c1", { content: "Hallo" })) {
        // no events expected
      }
    };

    await expect(run()).rejects.toMatchObject({ code: "llm_unavailable", status: 503 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("stops with code aborted when the caller aborts", async () => {
    const controller = new AbortController();
    const { client } = fakeBackend(() => new Promise<Response>(() => {}));

    const run = async () => {
      for await (const _event of client.streamMessage(
        "c1",
        { content: "Hallo" },
        { signal: controller.signal },
      )) {
        // no events expected
      }
    };
    const result = run();
    controller.abort();

    await expect(result).rejects.toMatchObject({ code: "aborted" });
  });
});

describe("injected transport", () => {
  it("uses a fake HttpClient instead of fetch", async () => {
    const get = vi.fn(async () => [{ id: "maria" }]);
    const client = createApiClient({
      baseUrl: ORIGIN,
      timeoutMs: 1_000,
      http: {
        get,
        request: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        stream: vi.fn(),
      } as never,
    });

    await expect(client.listPersonas()).resolves.toEqual([{ id: "maria" }]);
    expect(get).toHaveBeenCalledWith("/api/personas", undefined);
  });
});

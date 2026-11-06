// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TransportError } from "@/lib/api";
import type { ApiClient, Document, DocumentExtraction } from "@/lib/api";

import { createUploadController } from "./controller";
import type { UploadControllerOptions, UploadState } from "./controller";

const file = new File(["synthetic document"], "entlassungsbefund.pdf", { type: "application/pdf" });

function document(status: Document["status"], id = "d1"): Document {
  return {
    id, filename: "server-name.pdf", mime_type: "application/pdf", status,
    kind: null, extracted: null, created_at: "2026-11-05T12:00:00Z",
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function setup(overrides: Partial<UploadControllerOptions> = {}) {
  const api = {
    uploadDocument: vi.fn<ApiClient["uploadDocument"]>().mockResolvedValue(document("processing")),
    getDocument: vi.fn<ApiClient["getDocument"]>().mockResolvedValue(document("ready")),
  };
  const progress: UploadState[] = [];
  const onProgress = vi.fn((state: UploadState) => { progress.push(state); });
  const controller = createUploadController({
    api, onProgress, pollIntervalMs: 100, totalTimeoutMs: 1_000, requestTimeoutMs: 300,
    ...overrides,
  });
  return { api, progress, onProgress, controller };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe("upload lifecycle", () => {
  it("uploads the file and conversation, polls, and returns the ready ID with unchanged extraction", async () => {
    const { api, controller, progress } = setup();
    const extraction: DocumentExtraction = {
      kind: "other", issuer: null, document_date: null,
      patient: {
        name: null, date_of_birth: null, address: null, postal_code: null, insurer: null, svnr: null,
      },
      living_situation: null,
      documented_recommendations: [{ topic: "other", quote: "  Zitat\nwortwörtlich.  ", section: "8" }],
      follow_up_appointments: [], warnings_in_document: [], confidence_note: null,
    };
    const ready = { ...document("ready"), kind: extraction.kind, extracted: extraction };
    api.getDocument.mockResolvedValue(ready);

    expect(controller.state).toBeNull();
    const result = controller.start(file, "c1");
    expect(controller.state).toMatchObject({ status: "uploading", filename: file.name, documentId: null });
    expect(api.uploadDocument).toHaveBeenCalledWith({ file, conversationId: "c1" }, {
      signal: expect.any(AbortSignal), timeoutMs: 300,
    });
    await vi.advanceTimersByTimeAsync(99);
    expect(api.getDocument).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);

    const outcome = await result;
    expect(outcome).toMatchObject({ status: "ready", filename: file.name, documentId: "d1" });
    expect(outcome.document).toBe(ready);
    expect(outcome.document?.extracted).toBe(extraction);
    expect(progress.map((state) => state.status)).toEqual(["uploading", "processing", "ready"]);
    expect(api.getDocument).toHaveBeenCalledWith("d1", { signal: expect.any(AbortSignal), timeoutMs: 300 });
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(5_000);
    expect(api.getDocument).toHaveBeenCalledTimes(1);
    expect(api.uploadDocument).toHaveBeenCalledTimes(1);
  });

  it.each(["ready", "failed"] as const)("accepts an immediate %s upload response without polling", async (status) => {
    const { api, controller } = setup();
    api.uploadDocument.mockResolvedValue(document(status));
    expect(await controller.start(file, "c1")).toMatchObject({ status, documentId: "d1" });
    expect(api.getDocument).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("stops on failed extraction with a local error and preserves the document ID", async () => {
    const { api, controller } = setup();
    api.getDocument.mockResolvedValue(document("failed"));
    const result = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(100);
    expect(await result).toMatchObject({
      status: "failed", documentId: "d1", filename: file.name,
      error: { code: "document_failed", message: expect.stringContaining("erneut") },
    });
    await vi.advanceTimersByTimeAsync(5_000);
    expect(api.getDocument).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(["upload", "poll"] as const)("stops on an HTTP error during %s without retrying", async (stage) => {
    const { api, controller } = setup();
    const error = new TransportError("not_found", "Das Dokument fehlt.", { status: 404 });
    if (stage === "upload") api.uploadDocument.mockRejectedValue(error);
    else api.getDocument.mockRejectedValue(error);
    const result = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(100);
    const outcome = await result;
    expect(outcome).toMatchObject({ status: "failed", documentId: stage === "upload" ? null : "d1" });
    if (outcome.status === "failed") expect(outcome.error).toBe(error);
    await vi.advanceTimersByTimeAsync(5_000);
    expect(api.uploadDocument).toHaveBeenCalledTimes(1);
    expect(api.getDocument).toHaveBeenCalledTimes(stage === "upload" ? 0 : 1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("bounds processing that never ends with the total timeout", async () => {
    const { api, controller } = setup();
    api.getDocument.mockResolvedValue(document("processing"));
    const result = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(1_000);
    expect(await result).toMatchObject({ status: "failed", documentId: "d1", error: { code: "timeout" } });
    const polls = api.getDocument.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5_000);
    expect(api.getDocument).toHaveBeenCalledTimes(polls);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(["upload", "poll"] as const)("aborts a hanging %s request even when the API ignores cancellation", async (stage) => {
    const { api, controller, progress } = setup();
    const pending = deferred<Document>();
    const method = stage === "upload" ? api.uploadDocument : api.getDocument;
    method.mockReturnValue(pending.promise);
    const result = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(stage === "upload" ? 300 : 400);
    expect(await result).toMatchObject({ status: "failed", error: { code: "timeout" } });
    expect(method.mock.calls[0][1]?.signal?.aborted).toBe(true);
    const notifications = progress.length;
    pending.resolve(document("ready"));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(progress).toHaveLength(notifications);
    expect(api.uploadDocument).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("aborts an in-flight request when the total deadline comes first", async () => {
    const { api, controller } = setup({ requestTimeoutMs: 5_000 });
    api.getDocument.mockReturnValue(new Promise(() => {}));
    const result = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(1_000);
    expect(await result).toMatchObject({ status: "failed", documentId: "d1", error: { code: "timeout" } });
    expect(api.getDocument.mock.calls[0][1]?.signal?.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("deduplicates active starts and schedules the next poll only after the previous response", async () => {
    const { api, controller } = setup({ requestTimeoutMs: 2_000 });
    const pending = deferred<Document>();
    api.getDocument.mockReturnValueOnce(pending.promise);
    const result = controller.start(file, "c1");
    expect(controller.start(file, "c1")).toBe(result);
    await vi.advanceTimersByTimeAsync(500);
    expect(api.getDocument).toHaveBeenCalledTimes(1);
    pending.resolve(document("processing"));
    await vi.advanceTimersByTimeAsync(99);
    expect(api.getDocument).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(await result).toMatchObject({ status: "ready" });
    expect(api.getDocument).toHaveBeenCalledTimes(2);
    expect(api.uploadDocument).toHaveBeenCalledTimes(1);
  });

  it.each(["upload", "waiting", "poll"] as const)("cancels during %s and ignores late responses", async (stage) => {
    const { api, controller, progress } = setup();
    const pending = deferred<Document>();
    if (stage === "upload") api.uploadDocument.mockReturnValue(pending.promise);
    if (stage === "poll") api.getDocument.mockReturnValue(pending.promise);
    const result = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(stage === "poll" ? 100 : 0);
    controller.cancel();
    controller.cancel();
    expect(await result).toMatchObject({
      status: "cancelled", filename: file.name, documentId: stage === "upload" ? null : "d1",
    });
    if (stage !== "waiting") {
      const method = stage === "upload" ? api.uploadDocument : api.getDocument;
      expect(method.mock.calls[0][1]?.signal?.aborted).toBe(true);
    }
    const notifications = progress.length;
    pending.resolve(document("ready"));
    await vi.advanceTimersByTimeAsync(5_000);
    expect(progress).toHaveLength(notifications);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("allows explicit retry and prevents an old rejected request from changing the new run", async () => {
    const { api, controller, progress } = setup();
    const old = deferred<Document>();
    api.uploadDocument.mockReturnValueOnce(old.promise).mockResolvedValueOnce(document("processing", "d2"));
    const first = controller.start(file, "c1");
    controller.cancel();
    expect(await first).toMatchObject({ status: "cancelled" });
    api.getDocument.mockResolvedValue(document("ready", "d2"));
    const second = controller.start(file, "c2");
    old.reject(new Error("late failure"));
    await vi.advanceTimersByTimeAsync(100);
    expect(await second).toMatchObject({ status: "ready", documentId: "d2" });
    expect(api.uploadDocument).toHaveBeenCalledTimes(2);
    expect(api.uploadDocument.mock.calls[1][0].conversationId).toBe("c2");
    expect(progress.map((state) => state.status)).toEqual([
      "uploading", "cancelled", "uploading", "processing", "ready",
    ]);
  });

  it("allows explicit retry after failure", async () => {
    const { api, controller } = setup();
    api.uploadDocument.mockRejectedValueOnce(new Error("offline"));
    expect(await controller.start(file, "c1")).toMatchObject({ status: "failed", error: { code: "upload_failed" } });
    const retry = controller.start(file, "c1");
    await vi.advanceTimersByTimeAsync(100);
    expect(await retry).toMatchObject({ status: "ready" });
    expect(api.uploadDocument).toHaveBeenCalledTimes(2);
  });

  it("keeps independent controllers isolated", async () => {
    const first = setup();
    const second = setup();
    const cancelled = first.controller.start(file, "c1");
    const ready = second.controller.start(file, "c2");
    first.controller.cancel();
    await vi.advanceTimersByTimeAsync(100);
    expect(await cancelled).toMatchObject({ status: "cancelled" });
    expect(await ready).toMatchObject({ status: "ready" });
    expect(first.api.getDocument).not.toHaveBeenCalled();
    expect(second.api.getDocument).toHaveBeenCalledTimes(1);
    second.controller.cancel();
    expect(second.controller.state?.status).toBe("ready");
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([0, -1, NaN, Infinity, 2_147_483_648])("rejects invalid time value %s", (value) => {
    for (const key of ["pollIntervalMs", "totalTimeoutMs", "requestTimeoutMs"] as const) {
      expect(() => setup({ [key]: value })).toThrow(RangeError);
    }
  });
});

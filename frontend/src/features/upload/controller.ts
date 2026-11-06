import { TransportError } from "@/lib/api";
import type { ApiClient, CallOptions, Document } from "@/lib/api";

interface UploadSnapshot {
  readonly filename: string;
  readonly documentId: string | null;
  /** The API document, including its unchanged extraction. */
  readonly document: Document | null;
}

export type UploadResult =
  | (UploadSnapshot & { readonly status: "ready"; readonly documentId: string; readonly document: Document })
  | (UploadSnapshot & { readonly status: "failed"; readonly error: TransportError })
  | (UploadSnapshot & { readonly status: "cancelled" });

export type UploadState =
  | (UploadSnapshot & { readonly status: "uploading" | "processing" })
  | UploadResult;

export interface UploadControllerOptions {
  api: Pick<ApiClient, "uploadDocument" | "getDocument">;
  onProgress: (state: UploadState) => void;
  /** Delay after each processing response, including the upload response. */
  pollIntervalMs: number;
  /** Limit for upload and processing together. */
  totalTimeoutMs: number;
  /** Limit for each upload or status request. */
  requestTimeoutMs: number;
}

export interface UploadController {
  readonly state: UploadState | null;
  /** While active, repeated calls return the same promise without another upload. */
  start(file: File, conversationId: string): Promise<UploadResult>;
  /** Cancel on attachment removal, conversation change, or screen teardown. */
  cancel(): void;
}

type Timer = ReturnType<typeof setTimeout>;

interface Run {
  state: UploadState;
  done: boolean;
  promise: Promise<UploadResult>;
  resolve: (result: UploadResult) => void;
  totalTimer?: Timer;
  pollTimer?: Timer;
  requestTimer?: Timer;
  request?: AbortController;
}

/** One attachment per controller. No chat messages or automatic upload retries. */
export function createUploadController(options: UploadControllerOptions): UploadController {
  // Browser timers overflow above this bound and can fire immediately.
  for (const value of [options.pollIntervalMs, options.totalTimeoutMs, options.requestTimeoutMs]) {
    if (!Number.isFinite(value) || value < 1 || value > 2_147_483_647) {
      throw new RangeError("Upload time values must be between 1 and 2147483647 milliseconds.");
    }
  }

  const { api, onProgress, pollIntervalMs, totalTimeoutMs, requestTimeoutMs } = options;
  let current: Run | undefined;

  function finish(run: Run, result: UploadResult) {
    if (run.done) return;
    run.done = true;
    run.state = result;
    clearTimeout(run.totalTimer);
    clearTimeout(run.pollTimer);
    clearTimeout(run.requestTimer);
    run.request?.abort();
    run.request = undefined;
    run.resolve(result);
    onProgress(result);
  }

  function fail(run: Run, error: unknown) {
    const failure = error instanceof TransportError
      ? error
      : new TransportError(
          "upload_failed",
          "Das Dokument konnte nicht geladen werden. Bitte versuchen Sie es erneut.",
          { cause: error },
        );
    finish(run, { ...run.state, status: "failed", error: failure });
  }

  function timeout(run: Run) {
    fail(run, new TransportError(
      "timeout",
      "Das Dokument braucht zu lange. Bitte versuchen Sie es erneut.",
    ));
  }

  function accept(run: Run, document: Document) {
    if (run.done) return;
    const snapshot: UploadSnapshot = {
      filename: run.state.filename,
      documentId: document.id,
      document,
    };
    if (document.status === "ready") {
      finish(run, { ...snapshot, status: "ready", documentId: document.id, document });
    } else if (document.status === "failed") {
      finish(run, {
        ...snapshot,
        status: "failed",
        error: new TransportError(
          "document_failed",
          "Das Dokument konnte nicht gelesen werden. Bitte versuchen Sie es erneut.",
        ),
      });
    } else {
      run.state = { ...snapshot, status: "processing" };
      onProgress(run.state);
      if (run.done) return;
      run.pollTimer = setTimeout(() => {
        run.pollTimer = undefined;
        request(run, (callOptions) => api.getDocument(document.id, callOptions));
      }, pollIntervalMs);
    }
  }

  function request(run: Run, call: (options: CallOptions) => Promise<Document>) {
    if (run.done) return;
    const controller = new AbortController();
    run.request = controller;
    // Own the watchdog too, even if an injected API ignores timeoutMs or its signal.
    run.requestTimer = setTimeout(() => timeout(run), requestTimeoutMs);
    const cleanRequest = () => {
      clearTimeout(run.requestTimer);
      run.requestTimer = undefined;
      run.request = undefined;
    };
    try {
      const response = call({ signal: controller.signal, timeoutMs: requestTimeoutMs });
      void response.then(
        (document) => {
          if (run.done) return;
          cleanRequest();
          accept(run, document);
        },
        (error: unknown) => {
          if (run.done) return;
          cleanRequest();
          fail(run, error);
        },
      );
    } catch (error) {
      cleanRequest();
      fail(run, error);
    }
  }

  return {
    get state() {
      return current?.state ?? null;
    },
    start(file, conversationId) {
      if (current && !current.done) return current.promise;
      let resolve!: Run["resolve"];
      const promise = new Promise<UploadResult>((settle) => { resolve = settle; });
      const run: Run = {
        state: { status: "uploading", filename: file.name, documentId: null, document: null },
        done: false,
        promise,
        resolve,
      };
      current = run;
      run.totalTimer = setTimeout(() => timeout(run), totalTimeoutMs);
      onProgress(run.state);
      request(run, (callOptions) => api.uploadDocument({ file, conversationId }, callOptions));
      return promise;
    },
    cancel() {
      if (current && !current.done) finish(current, { ...current.state, status: "cancelled" });
    },
  };
}

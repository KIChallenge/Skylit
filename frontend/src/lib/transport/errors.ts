/** Errors of the browser transport. Every message is safe to show in the UI. */

/** Codes the transport sets itself. HTTP errors carry the backend code instead. */
export type TransportFailureCode =
  | "network_error"
  | "timeout"
  | "aborted"
  | "invalid_response"
  | "stream_incomplete"
  | "stream_invalid_event";

const FAILURE_MESSAGES: Record<TransportFailureCode, string> = {
  network_error:
    "Die Verbindung zum Server ist fehlgeschlagen. Bitte prüfen Sie Ihre Verbindung und versuchen Sie es erneut.",
  timeout:
    "Der Server hat nicht rechtzeitig geantwortet. Bitte versuchen Sie es erneut.",
  aborted: "Die Anfrage wurde abgebrochen.",
  invalid_response:
    "Der Server hat eine unerwartete Antwort geschickt. Bitte versuchen Sie es erneut.",
  stream_incomplete:
    "Die Antwort wurde unerwartet beendet. Bitte versuchen Sie es erneut.",
  stream_invalid_event:
    "Die Antwort konnte nicht gelesen werden. Bitte versuchen Sie es erneut.",
};

const HTTP_FALLBACKS: Record<number, { code: string; message: string }> = {
  400: { code: "bad_request", message: "Die Anfrage ist ungültig." },
  401: {
    code: "unauthorized",
    message: "Ihre Sitzung ist abgelaufen. Bitte melden Sie sich an.",
  },
  403: {
    code: "forbidden",
    message: "Für diese Aktion fehlt Ihnen die Berechtigung.",
  },
  404: {
    code: "not_found",
    message: "Der gesuchte Eintrag wurde nicht gefunden.",
  },
  405: {
    code: "method_not_allowed",
    message: "Diese Aktion ist hier nicht möglich.",
  },
  409: {
    code: "conflict",
    message: "Der Eintrag wurde inzwischen geändert. Bitte laden Sie die Seite neu.",
  },
  413: { code: "payload_too_large", message: "Die Datei ist zu groß." },
  415: {
    code: "unsupported_media_type",
    message: "Dieses Dateiformat wird nicht unterstützt.",
  },
  422: { code: "validation_error", message: "Die Eingabe ist ungültig." },
  429: {
    code: "rate_limited",
    message: "Zu viele Anfragen. Bitte versuchen Sie es später erneut.",
  },
};

const SERVER_FALLBACK = {
  code: "server_error",
  message: "Der Dienst ist gerade nicht verfügbar. Bitte versuchen Sie es erneut.",
};

const UNKNOWN_FALLBACK = {
  code: "http_error",
  message: "Die Anfrage ist fehlgeschlagen. Bitte versuchen Sie es erneut.",
};

/** Starlette sends these English phrases for errors that no route raised. */
const ENGLISH_REASON_PHRASES = new Set([
  "bad request",
  "unauthorized",
  "forbidden",
  "not found",
  "method not allowed",
  "conflict",
  "request entity too large",
  "content too large",
  "unsupported media type",
  "unprocessable entity",
  "unprocessable content",
  "too many requests",
  "internal server error",
  "bad gateway",
  "service unavailable",
  "gateway timeout",
]);

export class TransportError extends Error {
  /** A `TransportFailureCode`, or the backend code of an HTTP error. */
  readonly code: string;
  /** HTTP status. `null` when the server sent no response. */
  readonly status: number | null;

  constructor(
    code: string,
    message: string,
    details: { status?: number; cause?: unknown } = {},
  ) {
    super(message, details.cause === undefined ? undefined : { cause: details.cause });
    this.name = "TransportError";
    this.code = code;
    this.status = details.status ?? null;
  }
}

export function failure(code: TransportFailureCode, cause?: unknown): TransportError {
  return new TransportError(code, FAILURE_MESSAGES[code], { cause });
}

/** Build the error of a non-2xx response from its raw body (contracts.md §1). */
export function httpError(status: number, bodyText: string): TransportError {
  const fallback =
    HTTP_FALLBACKS[status] ?? (status >= 500 ? SERVER_FALLBACK : UNKNOWN_FALLBACK);
  const body = readErrorBody(bodyText);
  const message =
    body.message && !ENGLISH_REASON_PHRASES.has(body.message.trim().toLowerCase())
      ? body.message
      : fallback.message;
  return new TransportError(body.code || fallback.code, message, { status });
}

function readErrorBody(bodyText: string): { code?: string; message?: string } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(bodyText);
  } catch {
    return {};
  }
  const error = isRecord(parsed) ? parsed.error : undefined;
  if (!isRecord(error)) return {};
  return {
    code: typeof error.code === "string" ? error.code : undefined,
    message: typeof error.message === "string" ? error.message : undefined,
  };
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

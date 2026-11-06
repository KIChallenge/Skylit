/**
 * Central frontend configuration. Read every setting through this module.
 *
 * The browser sees only NEXT_PUBLIC_* variables. Next.js inlines them at build time,
 * so each one must appear here as a literal property access on process.env.
 * Never put secrets into NEXT_PUBLIC_* variables.
 *
 * Auth (docs/contracts.md §1): the backend sets the HTTP-only cookie `lotse_session`.
 * Frontend and backend run on different origins, so every backend request sends
 * `credentials: "include"`. The backend allows only the origins in BACKEND_CORS_ORIGINS.
 * Open the app on the same host name as the API (both `localhost`). Else the browser does not
 * send the SameSite=Lax cookie.
 *
 * The transport (src/lib/transport) reads no environment variables. Pass these values to
 * `createHttpClient` as `baseUrl`, `timeoutMs` and `streamIdleTimeoutMs`.
 */

export class ConfigError extends Error {
  override name = "ConfigError";
}

// Defaults match .env.example. The stream idle default exceeds the backend LLM_TIMEOUT_SECONDS
// (120 s), because the backend sends no SSE keep-alive while the LLM works.
const DEFAULT_API_TIMEOUT_MS = 15_000;
const DEFAULT_STREAM_IDLE_TIMEOUT_MS = 130_000;

function readHttpUrl(name: string, value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    throw new ConfigError(`${name} is not set. Copy .env.example to .env in the repo root.`);
  }
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new ConfigError(`${name} is not a valid URL: "${trimmed}"`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new ConfigError(`${name} must use http or https: "${trimmed}"`);
  }
  return trimmed.replace(/\/+$/, "");
}

function readPositiveMs(name: string, value: string | undefined, fallback: number): number {
  const trimmed = value?.trim();
  if (!trimmed) return fallback;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new ConfigError(`${name} must be a positive whole number of milliseconds: "${trimmed}"`);
  }
  return parsed;
}

export const config = {
  /** Backend origin without a trailing slash. Routes start with `/api`. */
  get apiUrl(): string {
    return readHttpUrl("NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL);
  },
  /** Timeout for one REST request, and for the stream until the response headers arrive. */
  get apiTimeoutMs(): number {
    return readPositiveMs(
      "NEXT_PUBLIC_API_TIMEOUT_MS",
      process.env.NEXT_PUBLIC_API_TIMEOUT_MS,
      DEFAULT_API_TIMEOUT_MS,
    );
  },
  /** Longest allowed pause between two SSE chunks. */
  get streamIdleTimeoutMs(): number {
    return readPositiveMs(
      "NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS",
      process.env.NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS,
      DEFAULT_STREAM_IDLE_TIMEOUT_MS,
    );
  },
  /**
   * Presenter autopilot for the jury demo: hidden shortcuts type the scripted prompts.
   * Off unless NEXT_PUBLIC_DEMO_AUTOPILOT is "1".
   */
  get demoAutopilot(): boolean {
    return process.env.NEXT_PUBLIC_DEMO_AUTOPILOT?.trim() === "1";
  },
  /** `fetch` credentials mode for every backend call (cookie auth across origins). */
  apiCredentials: "include" satisfies RequestCredentials,
} as const;

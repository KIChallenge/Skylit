import { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD } from "next/constants.js";

import { loadRootEnv } from "./scripts/root-env.mjs";

// The frontend shares the repo-root .env with the backend. Only the listed keys are copied.
loadRootEnv([
  "NEXT_PUBLIC_API_URL",
  "NEXT_PUBLIC_API_TIMEOUT_MS",
  "NEXT_PUBLIC_STREAM_IDLE_TIMEOUT_MS",
]);

// Next.js inlines NEXT_PUBLIC_* values at build time. Fail early instead of shipping a broken bundle.
function assertPublicConfig() {
  const value = process.env.NEXT_PUBLIC_API_URL;
  if (!value) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Copy .env.example to .env in the repo root, or set the variable.",
    );
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`NEXT_PUBLIC_API_URL is not a valid URL: "${value}"`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`NEXT_PUBLIC_API_URL must use http or https: "${value}"`);
  }
}

/** @type {(phase: string) => import("next").NextConfig} */
export default function nextConfig(phase) {
  if (phase === PHASE_DEVELOPMENT_SERVER || phase === PHASE_PRODUCTION_BUILD) {
    assertPublicConfig();
  }
  return {
    // The Docker image runs .next/standalone/server.js. It reads PORT and HOSTNAME at runtime.
    output: "standalone",
    poweredByHeader: false,
    reactStrictMode: true,
  };
}

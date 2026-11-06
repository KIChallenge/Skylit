// Downloads the backend OpenAPI schema. `npm run api:types` turns it into TypeScript types.
// Usage: npm run api:schema [-- --url <backend>/openapi.json]
// Default source: ${NEXT_PUBLIC_API_URL}/openapi.json from the environment or the repo-root .env.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

import { loadRootEnv } from "./root-env.mjs";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outFile = resolve(frontendDir, "src/lib/api/generated/openapi.json");
const timeoutMs = 15_000;
// The SSE event union reaches OpenAPI only through this route (docs/contracts.md).
const requiredPaths = ["/api/_schema/events"];

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

const { values } = parseArgs({ options: { url: { type: "string" } } });
loadRootEnv(["NEXT_PUBLIC_API_URL"]);

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
const source = values.url ?? (apiBaseUrl ? `${apiBaseUrl}/openapi.json` : undefined);
if (!source) {
  fail("NEXT_PUBLIC_API_URL is not set. Set it, or pass --url <backend>/openapi.json.");
}

let response;
try {
  response = await fetch(source, { signal: AbortSignal.timeout(timeoutMs) });
} catch (error) {
  fail(`Cannot reach ${source} (${error.message}). Start the backend first, e.g. with make run.`);
}
if (!response.ok) {
  fail(`${source} answered with HTTP ${response.status}.`);
}

const spec = await response.json();
if (typeof spec.openapi !== "string" || typeof spec.paths !== "object") {
  fail(`${source} did not return an OpenAPI document.`);
}
const missing = requiredPaths.filter((path) => !(path in spec.paths));
if (missing.length > 0) {
  fail(`The schema lacks ${missing.join(", ")}. Is this the current backend?`);
}

mkdirSync(dirname(outFile), { recursive: true });
writeFileSync(outFile, `${JSON.stringify(spec, null, 2)}\n`);
console.log(`INFO: Wrote ${Object.keys(spec.paths).length} paths from ${source} to ${outFile}`);

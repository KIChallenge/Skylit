// Reads selected keys from the repo-root .env, so the frontend and the backend share one .env.
// Real environment variables always win. Docker builds have no root .env, so this is a no-op there.
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export const repoRoot = resolve(frontendDir, "..");

/**
 * Copies only the named keys into process.env. Backend secrets in .env never enter the frontend.
 * @param {readonly string[]} keys
 */
export function loadRootEnv(keys) {
  const file = resolve(repoRoot, ".env");
  if (!existsSync(file)) return;
  const parsed = /** @type {Record<string, string | undefined>} */ (
    parseEnv(readFileSync(file, "utf8"))
  );
  for (const key of keys) {
    if (process.env[key] === undefined && parsed[key] !== undefined) {
      process.env[key] = parsed[key];
    }
  }
}

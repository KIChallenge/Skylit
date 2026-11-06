import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    // The transport tests use node:test. `npm run test:transport` runs them.
    exclude: ["e2e/**", "node_modules/**", ".next/**", "src/lib/transport/**"],
    restoreMocks: true,
    unstubEnvs: true,
  },
});

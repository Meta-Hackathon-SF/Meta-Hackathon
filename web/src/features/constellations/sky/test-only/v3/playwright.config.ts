import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

export default defineConfig({
  testDir: ".",
  testMatch: "prototype.spec.ts",
  outputDir: "./artifacts",
  reporter: "list",
  workers: 1,
  use: {
    channel: process.platform === "win32" ? "chrome" : undefined,
    baseURL: "http://127.0.0.1:5194",
    viewport: { width: 1440, height: 1100 },
  },
  webServer: {
    command:
      "node node_modules/vite/bin/vite.js --config src/features/constellations/sky/test-only/v3/vite.config.ts",
    cwd: fileURLToPath(new URL("../../../../../../", import.meta.url)),
    url: "http://127.0.0.1:5194",
    reuseExistingServer: false,
  },
});

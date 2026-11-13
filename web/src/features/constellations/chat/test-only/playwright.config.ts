/// <reference types="node" />
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: true,
  workers: 2,
  outputDir: "../../../../../test-results/kai",
  use: {
    baseURL: "http://127.0.0.1:5193",
    channel: process.env.PLAYWRIGHT_CHANNEL || (process.platform === "win32" ? "chrome" : undefined),
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5193 --strictPort",
    cwd: fileURLToPath(new URL("../../../../../", import.meta.url)),
    url: "http://127.0.0.1:5193/src/features/constellations/chat/test-only/index.html",
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});

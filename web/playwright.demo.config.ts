import { defineConfig } from "@playwright/test";

// Enregistre la démonstration filmée : `make film` (pile en marche requise).
export default defineConfig({
  testDir: "./e2e",
  testMatch: "film.spec.ts",
  workers: 1,
  timeout: 240_000,
  outputDir: "../artifacts/film",
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:3000",
    viewport: { width: 1280, height: 720 },
    video: { mode: "on", size: { width: 1280, height: 720 } },
    launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined, args: ["--no-sandbox"] },
  },
});

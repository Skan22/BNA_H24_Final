import { defineConfig } from "@playwright/test";

// Pile en marche requise (make demo ou make docker-up). CHROMIUM_PATH : navigateur déjà installé.
export default defineConfig({
  testDir: "./e2e",
  testIgnore: /film\.spec/,
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:3000",
    launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined, args: ["--no-sandbox"] },
  },
});

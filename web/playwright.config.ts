import path from "path";
import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

export default defineConfig({
  testDir: path.join(__dirname, "e2e"),
  use: {
    baseURL,
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  reporter: [["list"]],
});

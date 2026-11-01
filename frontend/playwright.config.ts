import { defineConfig } from "@playwright/test";
import path from "node:path";
export default defineConfig({
  testDir: "./tests",
  // Parallel verification commands must never delete each other's traces.
  outputDir: process.env.AIMS_TEST_ARTIFACTS || path.resolve('../outputs/playwright', `run-${Date.now()}-${process.pid}`),
  testMatch: ["studio.spec.ts", "flagship.spec.ts"],
  timeout: 60000,
  workers: 1,
  retries: 0,
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    baseURL: process.env.AIMS_TEST_URL || "http://127.0.0.1:7860",
    browserName: "chromium",
    channel: "chrome",
    headless: true,
    permissions: ["camera"],
    launchOptions: {
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
        `--use-file-for-fake-video-capture=${path.resolve("../.cache/camera.y4m")}`,
      ],
    },
  },
  reporter: "list",
});

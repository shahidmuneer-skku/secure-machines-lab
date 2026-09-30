import { defineConfig, devices } from "@playwright/test"

/**
 * End-to-end tests against a running stack (scripts/dev.sh or a staging server):
 *   E2E_BASE_URL=http://localhost:3000 E2E_EMAIL=... E2E_PASSWORD=... npx playwright test
 * Tests that need an account are skipped when E2E_EMAIL / E2E_PASSWORD are not set.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    colorScheme: "dark",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
})

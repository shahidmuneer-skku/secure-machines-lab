import path from "node:path"

import { expect, hasAccount, signIn, test } from "./fixtures"

test.skip(!hasAccount, "set E2E_EMAIL and E2E_PASSWORD to run workspace tests")

test("dashboard shows the credit balance", async ({ page }) => {
  await signIn(page)
  await expect(page.getByText(/credits/i).first()).toBeVisible()
})

test("an uploaded image becomes a queued job with live progress", async ({ page }) => {
  await signIn(page)
  await page.goto("/app/detect")
  await page.locator("input[type=file]").setInputFiles(path.join(__dirname, "assets", "sample.png"))
  const start = page.getByRole("button", { name: /start analysis/i })
  await expect(start).toBeEnabled()
  await start.click()
  await page.waitForURL(/\/app\/results(\/|$)/)
  await page.goto("/app/results")
  await page.getByText("sample.png").first().click()
  await expect(page.getByText(/what.s happening now/i)).toBeVisible()
  await expect(page.getByText(/queued|analyzing|running|done|succeeded/i).first()).toBeVisible()
})

test("API keys can be created and revoked", async ({ page }) => {
  const name = `e2e-${Date.now()}`
  await signIn(page)
  await page.goto("/app/api-keys")
  await page.getByRole("button", { name: /create api key/i }).first().click()
  await page.getByLabel("Name").fill(name)
  await page.getByRole("button", { name: /^create key$/i }).click()
  // The secret is shown exactly once.
  await expect(page.getByText(/sml_(test|live)_[a-z0-9]{12}_/).first()).toBeVisible()
  await page.keyboard.press("Escape")

  const row = page.getByRole("row", { name: new RegExp(name) })
  await row.getByRole("button", { name: /actions/i }).click()
  await page.getByRole("menuitem", { name: /revoke/i }).click()
  await page.getByRole("alertdialog").getByRole("button", { name: /revoke/i }).click()
  await expect(page.getByText(/key revoked/i)).toBeVisible()
})

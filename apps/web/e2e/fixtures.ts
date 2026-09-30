import { expect, test as base, type Page } from "@playwright/test"

export const credentials = { email: process.env.E2E_EMAIL ?? "", password: process.env.E2E_PASSWORD ?? "" }
export const hasAccount = Boolean(credentials.email && credentials.password)

/** Fails the test on uncaught page errors and console errors (401s from session probes excepted). */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, use) => {
    const errors: string[] = []
    page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`))
    page.on("console", (m) => {
      if (m.type() !== "error" || /status of 401/.test(m.text())) return
      // The document's own status (e.g. an intentional 404 page) is not a broken resource.
      if (m.text().startsWith("Failed to load resource") && m.location().url === page.url()) return
      errors.push(m.text())
    })
    await use(page)
    expect(errors, "browser errors").toEqual([])
  },
})

export async function signIn(page: Page) {
  await page.goto("/login")
  await page.locator("input[type=email]").fill(credentials.email)
  await page.locator("input[autocomplete=current-password]").fill(credentials.password)
  await page.locator("button[type=submit]").click()
  await page.waitForURL("**/app")
}

export { expect }

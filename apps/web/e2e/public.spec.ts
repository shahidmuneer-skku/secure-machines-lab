import { expect, test } from "./fixtures"

test("homepage renders with security headers", async ({ page }) => {
  const response = await page.goto("/")
  const csp = response?.headers()["content-security-policy"] ?? ""
  expect(csp).toContain("nonce-")
  expect(csp).toContain("frame-ancestors 'none'")
  expect(response?.headers()["x-content-type-options"]).toBe("nosniff")
  await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible()
})

test("pricing lists packs and plans from the API", async ({ page }) => {
  await page.goto("/pricing")
  await expect(page.getByText("Starter").first()).toBeVisible()
  await expect(page.getByText("Business").first()).toBeVisible()
})

test("Korean locale is applied from the cookie", async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: "NEXT_LOCALE", value: "ko", url: baseURL! }])
  await page.goto("/pricing")
  await expect(page.locator("html")).toHaveAttribute("lang", "ko")
  await expect(page.getByText("크레딧").first()).toBeVisible()
})

test("unknown pages return 404 with a way back", async ({ page }) => {
  const response = await page.goto("/definitely-not-a-page")
  expect(response?.status()).toBe(404)
  await expect(page.getByRole("link", { name: /home/i })).toBeVisible()
})

test("workspace pages require sign-in", async ({ page }) => {
  await page.goto("/app/results")
  await expect(page).toHaveURL(/\/login\?next=%2Fapp%2Fresults/)
})

test("the Django data admin has no password form of its own", async ({ page }) => {
  await page.goto("/api/django-admin/")
  await expect(page).toHaveURL(/\/login\?next=%2Fapi%2Fdjango-admin%2F/)
})

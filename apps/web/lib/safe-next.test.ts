import { describe, expect, it } from "vitest"

import { safeNext } from "./safe-next"

describe("safeNext", () => {
  it.each([
    ["/app/results?status=queued#top", "/app/results?status=queued#top"],
    ["/admin", "/admin"],
  ])("keeps same-origin paths (%s)", (raw, expected) => {
    expect(safeNext(raw)).toBe(expected)
  })

  it.each([
    null,
    "",
    "https://evil.example/app",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "app",
    "/app\u0000",
    "/\t/evil.example",
  ])("falls back for unsafe value %j", (raw) => {
    expect(safeNext(raw as string | null)).toBe("/app")
  })

  it("uses the supplied fallback", () => {
    expect(safeNext("https://x.test", "/login")).toBe("/login")
  })
})

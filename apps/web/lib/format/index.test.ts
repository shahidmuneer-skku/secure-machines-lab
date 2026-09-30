import { describe, expect, it } from "vitest"

import { formatBytes, formatDuration, formatMoney, formatPercent, formatRelative } from "./index"

describe("format helpers", () => {
  it("bytes", () => {
    expect(formatBytes(0)).toBe("—")
    expect(formatBytes(512)).toBe("512 B")
    expect(formatBytes(1536)).toBe("1.5 KB")
    expect(formatBytes(50 * 1024 * 1024)).toBe("50 MB")
  })

  it("durations", () => {
    expect(formatDuration(null)).toBe("—")
    expect(formatDuration(42.4)).toBe("42s")
    expect(formatDuration(125)).toBe("2m 5s")
    expect(formatDuration(3 * 3600 + 120)).toBe("3h 2m")
  })

  it("percent from a 0–1 probability", () => {
    expect(formatPercent(0.8312)).toBe("83.1%")
    expect(formatPercent(undefined)).toBe("—")
  })

  it("money: KRW in won, USD in cents", () => {
    expect(formatMoney(15000, "KRW", "ko")).toBe("₩15,000")
    expect(formatMoney(1200, "USD", "en")).toBe("$12.00")
  })

  it("relative time", () => {
    const now = Date.parse("2026-09-30T12:00:00Z")
    expect(formatRelative("2026-09-30T11:58:00Z", "en", now)).toBe("2 minutes ago")
    expect(formatRelative("2026-10-01T12:00:00Z", "en", now)).toBe("tomorrow")
  })
})

import { describe, expect, it } from "vitest"

import { seededRandom } from "./seeded-random"

describe("seededRandom", () => {
  it("is deterministic per seed and stays in [0, 1)", () => {
    const a = seededRandom(42)
    const b = seededRandom(42)
    const xs = Array.from({ length: 200 }, () => a())
    expect(xs).toEqual(Array.from({ length: 200 }, () => b()))
    expect(xs.every((x) => x >= 0 && x < 1)).toBe(true)
    expect(seededRandom(7)()).not.toBe(seededRandom(8)())
  })
})

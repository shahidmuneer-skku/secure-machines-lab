import { describe, expect, it } from "vitest"

import { POSE_KEYS, STAGE_BOUNDS, STAGE_REST, sampleScan, stageAt } from "./timeline"

const steps = (n: number) => Array.from({ length: n + 1 }, (_, i) => i / n)

describe("scan timeline", () => {
  it("is deterministic: forward, backward and jumped progress give identical states", () => {
    const forward = steps(400).map(sampleScan)
    const backward = steps(400).reverse().map(sampleScan).reverse()
    expect(backward).toEqual(forward)
    // Jumping straight to a progress (reload half-way down) needs no history.
    expect(sampleScan(0.47)).toEqual(forward[188])
  })

  it("shows at most one text panel at a time, and always one at the stage rests", () => {
    for (const p of steps(1000)) {
      const visible = sampleScan(p).panels.filter((o) => o > 0.001)
      expect(visible.length).toBeLessThanOrEqual(1)
    }
    STAGE_REST.forEach((p, i) => expect(sampleScan(p).panels[i]).toBeCloseTo(1, 5))
  })

  it("keeps the brief's motion limits", () => {
    for (const p of steps(500)) {
      const s = sampleScan(p)
      expect(Math.abs(s.roll)).toBeLessThanOrEqual(6)
      expect(s.pitch).toBeGreaterThanOrEqual(0)
      expect(s.pitch).toBeLessThanOrEqual(20)
      expect(s.size).toBeGreaterThanOrEqual(0.85 - 1e-9)
      expect(s.size).toBeLessThanOrEqual(1.08 + 1e-9)
      for (const v of [s.surface, s.wire, s.band, s.landmarks, s.evidence, s.report, s.frame, s.field]) {
        expect(v).toBeGreaterThanOrEqual(0)
        expect(v).toBeLessThanOrEqual(1)
      }
    }
  })

  it("matches the stage keyframes", () => {
    expect(sampleScan(0).yaw).toBe(-12)
    const scan = sampleScan(0.35)
    expect(scan.yaw).toBeCloseTo(0)
    expect(scan.size).toBeCloseTo(1.08)
    expect(scan.pitch).toBeCloseTo(10)
    const inspect = sampleScan(0.58)
    expect(inspect.pitch).toBeCloseTo(20)
    expect(inspect.cy - POSE_KEYS[0][1].cy).toBeCloseTo(0.07, 1)
    expect(sampleScan(0.78).size).toBeCloseTo(0.85)
    expect(sampleScan(1).pitch).toBe(0)
    expect(sampleScan(1).field).toBe(0)
  })

  it("sweeps the scan band from forehead to chin during the scan stage only", () => {
    expect(sampleScan(0.1).band).toBe(0)
    expect(sampleScan(0.5).band).toBe(0)
    const ys = steps(100).map((t) => sampleScan(0.17 + t * 0.15).bandY)
    for (let i = 1; i < ys.length; i++) expect(ys[i]).toBeLessThanOrEqual(ys[i - 1])
  })

  it("maps progress to stages", () => {
    expect(STAGE_BOUNDS.slice(0, -1).map(stageAt)).toEqual([0, 1, 2, 3, 4])
    expect(stageAt(1)).toBe(4)
    expect(sampleScan(Number.NaN).stage).toBe(0)
  })
})

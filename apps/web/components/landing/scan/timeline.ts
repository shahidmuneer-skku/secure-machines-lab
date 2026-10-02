/**
 * The scan story as a pure function of scroll progress (0 → 1).
 *
 * Every visual value in the hero is derived from `sampleScan(progress)`, so any progress — scrolling
 * forwards, backwards, jumping or reloading half-way down — reconstructs exactly the same state.
 * There are no timers or accumulated state here; pointer offsets are applied separately.
 */

export const STAGES = ["intro", "scan", "inspect", "explain", "handoff"] as const
export type StageKey = (typeof STAGES)[number]

/** Stage boundaries in progress units: A 0–15 %, B 15–35 %, C 35–60 %, D 60–80 %, E 80–100 %. */
export const STAGE_BOUNDS = [0, 0.15, 0.35, 0.6, 0.8, 1] as const

/** Where each stage "rests" (used by stage buttons, the manual mode and "Explore the scan"). */
export const STAGE_REST = [0.04, 0.28, 0.55, 0.74, 0.97] as const

export type Pose = {
  /** Head centre as a fraction of the stage width / usable height (below the navigation). */
  cx: number
  cy: number
  /** Relative to the initial head size. */
  size: number
  /** Degrees. Positive pitch tilts the face forward (down), positive yaw turns it to the viewer's right. */
  yaw: number
  pitch: number
  roll: number
}

export type ScanState = Pose & {
  /** Index of the stage the progress is in (0–4). */
  stage: number
  /** Solid surface visibility (1 = sculpture, lower = darker surface for the mesh view). */
  surface: number
  /** Base wireframe strength, and extra wireframe revealed above the scan band. */
  wire: number
  reveal: number
  /** Scan band height in model units (forehead ≈ 3, chin ≈ −0.35) and its opacity. */
  bandY: number
  band: number
  /** Fraction of facial landmarks shown. */
  landmarks: number
  /** Illustrative evidence overlay on the selected regions. */
  evidence: number
  /** The two anchored explanations of the inspect stage (eye region, mouth boundary). */
  calloutEye: number
  calloutMouth: number
  /** Report preview (explain stage) and the framed sample (hand-off). */
  report: number
  frame: number
  /** Polygon background activity (1 = full, 0 = faded out). */
  field: number
  /** Opacity of each stage's text panel; at most one is above zero at any progress. */
  panels: [number, number, number, number, number]
}

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v)
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
/** Smootherstep: zero velocity at both ends, so keyframes settle without overshoot. */
const ease = (t: number) => t * t * t * (t * (t * 6 - 15) + 10)
/** 0 before `a`, 1 after `b`, eased in between. */
export const ramp = (p: number, a: number, b: number) => ease(clamp01((p - a) / (b - a)))
/** Rises over [a, b], holds, falls over [c, d]. */
const window4 = (p: number, a: number, b: number, c: number, d: number) => ramp(p, a, b) * (1 - ramp(p, c, d))

type Key<T> = readonly [number, T]

function track(keys: readonly Key<number>[], p: number): number {
  if (p <= keys[0][0]) return keys[0][1]
  for (let i = 1; i < keys.length; i++) {
    const [p1, v1] = keys[i]
    if (p <= p1) {
      const [p0, v0] = keys[i - 1]
      return lerp(v0, v1, ease((p - p0) / (p1 - p0)))
    }
  }
  return keys[keys.length - 1][1]
}

/** Head poses at the key moments of the story (desktop composition: text left 44 %, scene right 56 %). */
export const POSE_KEYS: readonly Key<Pose>[] = [
  [0.0, { cx: 0.715, cy: 0.5, size: 1, yaw: -12, pitch: 0, roll: 0 }],
  // A — introduction: hold so the headline can be read.
  [0.12, { cx: 0.715, cy: 0.5, size: 1, yaw: -11, pitch: 0, roll: 0 }],
  // B — scan: turn frontal, +8 % scale, pitch forward up to 10°.
  [0.35, { cx: 0.7, cy: 0.49, size: 1.08, yaw: 0, pitch: 10, roll: 0 }],
  // C — inspect: toward the centre, 8 % lower, pitch 20°, a small roll (≤ 6°). The "rolling down" move.
  [0.58, { cx: 0.655, cy: 0.57, size: 1.08, yaw: 4, pitch: 20, roll: -5 }],
  // D — explain: left part of the scene, frontal again, 85 % of the initial size.
  [0.78, { cx: 0.585, cy: 0.5, size: 0.85, yaw: 0, pitch: 3, roll: 0 }],
  // E — hand-off: neutral pitch, settled in the framed sample composition.
  [0.95, { cx: 0.7, cy: 0.5, size: 0.85, yaw: -5, pitch: 0, roll: 0 }],
  [1.0, { cx: 0.7, cy: 0.5, size: 0.85, yaw: -5, pitch: 0, roll: 0 }],
]

const poseTrack = (field: keyof Pose) => POSE_KEYS.map(([p, pose]) => [p, pose[field]] as const)
const TRACKS = {
  cx: poseTrack("cx"), cy: poseTrack("cy"), size: poseTrack("size"),
  yaw: poseTrack("yaw"), pitch: poseTrack("pitch"), roll: poseTrack("roll"),
  wire: [[0, 0.06], [0.15, 0.06], [0.35, 0.18], [0.56, 0.48], [0.62, 0.48], [0.78, 0.2], [0.92, 0.12], [1, 0.12]],
  reveal: [[0, 0], [0.16, 0], [0.35, 0.45], [0.58, 0.22], [0.78, 0.08], [1, 0.05]],
  surface: [[0, 1], [0.4, 1], [0.56, 0.9], [0.66, 0.96], [1, 1]],
  landmarks: [[0, 0], [0.2, 0], [0.33, 1], [0.62, 1], [0.78, 0.7], [0.92, 0.25], [1, 0.25]],
  evidence: [[0, 0], [0.4, 0], [0.5, 1], [0.6, 1], [0.68, 0.55], [0.8, 0.55], [0.87, 0], [1, 0]],
  field: [[0, 1], [0.15, 1], [0.35, 0.9], [0.6, 0.8], [0.7, 0.4], [0.82, 0.4], [1, 0]],
} as const satisfies Record<string, readonly Key<number>[]>

/** Band sweep: from the top of the forehead to below the chin during the scan stage. */
const BAND_TOP = 3.05
const BAND_BOTTOM = -0.45
const BAND_START = 0.17
const BAND_END = 0.32

export function stageAt(p: number): number {
  for (let i = STAGE_BOUNDS.length - 2; i >= 0; i--) if (p >= STAGE_BOUNDS[i]) return i
  return 0
}

/** Opacity of each text panel: the outgoing panel fades out before the incoming one fades in. */
function panelOpacities(p: number): ScanState["panels"] {
  const f = 0.03
  const b = STAGE_BOUNDS
  return [
    1 - ramp(p, b[1] - f, b[1]),
    window4(p, b[1], b[1] + f, b[2] - f, b[2]),
    window4(p, b[2], b[2] + f, b[3] - f, b[3]),
    window4(p, b[3], b[3] + f, b[4] - f, b[4]),
    ramp(p, b[4], b[4] + f),
  ]
}

export function sampleScan(progress: number): ScanState {
  const p = clamp01(Number.isFinite(progress) ? progress : 0)
  const sweep = clamp01((p - BAND_START) / (BAND_END - BAND_START))
  const bandY = p < BAND_START ? 4.5 : p > BAND_END ? -2.5 : lerp(BAND_TOP, BAND_BOTTOM, ease(sweep))
  return {
    stage: stageAt(p),
    cx: track(TRACKS.cx, p),
    cy: track(TRACKS.cy, p),
    size: track(TRACKS.size, p),
    yaw: track(TRACKS.yaw, p),
    pitch: track(TRACKS.pitch, p),
    roll: track(TRACKS.roll, p),
    surface: track(TRACKS.surface, p),
    wire: track(TRACKS.wire, p),
    reveal: track(TRACKS.reveal, p),
    bandY,
    band: window4(p, BAND_START - 0.01, BAND_START + 0.015, BAND_END - 0.01, BAND_END + 0.02),
    landmarks: track(TRACKS.landmarks, p),
    evidence: track(TRACKS.evidence, p),
    calloutEye: window4(p, 0.42, 0.46, 0.57, 0.6),
    calloutMouth: window4(p, 0.47, 0.51, 0.57, 0.6),
    report: window4(p, 0.63, 0.69, 0.79, 0.83),
    frame: ramp(p, 0.84, 0.92),
    field: track(TRACKS.field, p),
    panels: panelOpacities(p),
  }
}

/** Layer views the visitor can pin during the inspect stage ("follow" = driven by scroll). */
export type LayerMode = "follow" | "surface" | "mesh" | "evidence"

/** Values a pinned layer view overrides (blended in over a short tween). */
export const LAYER_OVERRIDES: Record<Exclude<LayerMode, "follow">, Pick<ScanState, "surface" | "wire" | "reveal" | "evidence" | "landmarks">> = {
  surface: { surface: 1, wire: 0.04, reveal: 0, evidence: 0, landmarks: 0.15 },
  mesh: { surface: 0.14, wire: 1, reveal: 0, evidence: 0, landmarks: 1 },
  evidence: { surface: 0.9, wire: 0.3, reveal: 0, evidence: 1, landmarks: 0.5 },
}

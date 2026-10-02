import { REGION_CAPSULES } from "./face-anchors"
import type { LayerMode } from "./timeline"

export const REGIONS = ["eyeL", "eyeR", "mouth", "jaw"] as const
export type RegionId = (typeof REGIONS)[number]

/** How the scene is driven: by scroll (pinned, desktop) or by stage buttons (small screens, reduced motion). */
export type ScanMode = "scroll" | "manual"

/**
 * The compact animation state shared by the HTML overlay and the WebGL scene.
 *
 * It is a plain mutable object held in a ref: scroll, pointer and selection changes write to it and
 * request a frame; the scene's single render loop reads it. Nothing here triggers a React render.
 */
export type ScanController = {
  mode: ScanMode
  /** Scroll progress (0–1) from the master ScrollTrigger timeline, or the manual stage target. */
  progress: number
  /** In manual mode the shown progress eases toward `progress` (instantly when motion is reduced). */
  shownProgress: number
  /** Pointer in stage pixels; `overControl` while it is over a link, button or other control. */
  pointer: { x: number; y: number; inside: boolean; overControl: boolean }
  hover: RegionId | null
  selected: RegionId | null
  layer: LayerMode
  /** Pause pointer-follow, background reactions and tweens. */
  motionPaused: boolean
  reducedMotion: boolean
  /** Pointer-follow only on fine pointers, outside the manual mode. */
  pointerFollow: boolean
  /** Right edge of the text column in stage pixels (background activity is calmer to its left). */
  textRight: number
  /** Height of the fixed navigation over the stage, in pixels. */
  navHeight: number
  /** Render the head without the background field (used to capture the matching poster image). */
  hideField: boolean
  /** Whether the stage is on screen and the tab visible; no frames are requested otherwise. */
  visible: boolean
  /** Set by the scene: the eyelids' opening (1 open, 0 closed), for visual checks. */
  eyeOpen: number
  /** Set by the scene: request one frame (demand rendering). */
  invalidate: () => void
  /** Set by the scene: the region under a stage point, if any (raycast against the head). */
  pick: (x: number, y: number) => RegionId | null
  /** DOM nodes the scene positions every frame (region labels, the selected explanation, the sample frame). */
  dom: {
    labels: Partial<Record<RegionId, HTMLElement | null>>
    card: HTMLElement | null
    frame: HTMLElement | null
  }
}

export function createScanController(): ScanController {
  return {
    mode: "scroll",
    progress: 0,
    shownProgress: 0,
    pointer: { x: 0, y: 0, inside: false, overControl: false },
    hover: null,
    selected: null,
    layer: "follow",
    motionPaused: false,
    reducedMotion: false,
    pointerFollow: true,
    textRight: 0,
    navHeight: 72,
    hideField: false,
    visible: true,
    eyeOpen: 1,
    invalidate: () => {},
    pick: () => null,
    dom: { labels: {}, card: null, frame: null },
  }
}

/** Distance from a point to each region (in units of the region's radius; < 1 is inside). */
export function regionDistances(x: number, y: number, z: number): Record<RegionId, number> {
  const out: Record<RegionId, number> = { eyeL: Infinity, eyeR: Infinity, mouth: Infinity, jaw: Infinity }
  for (const { region, a, b, r } of REGION_CAPSULES) {
    const abx = b[0] - a[0], aby = b[1] - a[1], abz = b[2] - a[2]
    const apx = x - a[0], apy = y - a[1], apz = z - a[2]
    const t = Math.max(0, Math.min(1, (apx * abx + apy * aby + apz * abz) / (abx * abx + aby * aby + abz * abz)))
    const dx = apx - abx * t, dy = apy - aby * t, dz = apz - abz * t
    const d = Math.sqrt(dx * dx + dy * dy + dz * dz) / r
    if (d < out[region]) out[region] = d
  }
  return out
}

/** The region containing a point on the head surface, if any (picking a little generously). */
export function regionAt(x: number, y: number, z: number): RegionId | null {
  const d = regionDistances(x, y, z)
  let best: RegionId | null = null
  let bestD = 1.35
  for (const id of REGIONS) if (d[id] < bestD) { best = id; bestD = d[id] }
  return best
}

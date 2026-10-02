// Generated from the head scan by a one-off script (positions in the GLB's model units, face looking down +z).
// Landmarks locate facial regions for the demonstration; they are not detector output.

export type Vec3 = readonly [number, number, number]
export type Landmark = { p: Vec3; n: Vec3 }

export const LANDMARK_GROUPS: Record<"eyeL" | "eyeR" | "browL" | "browR" | "nose" | "mouth" | "jaw", Landmark[]> = {
  eyeL: [
    { p: [-0.88, 1.76, 1.91], n: [-0.506, -0.134, 0.852] },
    { p: [-0.72, 1.84, 1.962], n: [-0.003, -0.083, 0.997] },
    { p: [-0.46, 1.84, 1.887], n: [0.09, -0.402, 0.911] },
    { p: [-0.27, 1.71, 1.938], n: [-0.875, 0.052, 0.481] },
    { p: [-0.45, 1.62, 1.848], n: [-0.071, 0.179, 0.981] },
    { p: [-0.7, 1.63, 1.932], n: [-0.008, -0.239, 0.971] },
  ],
  eyeR: [
    { p: [0.9, 1.74, 1.604], n: [0.693, -0.29, 0.66] },
    { p: [0.74, 1.82, 1.843], n: [0.642, -0.312, 0.7] },
    { p: [0.48, 1.82, 1.959], n: [-0.036, -0.165, 0.986] },
    { p: [0.29, 1.69, 1.889], n: [-0.29, 0.014, 0.957] },
    { p: [0.47, 1.6, 1.895], n: [0.018, -0.233, 0.972] },
    { p: [0.72, 1.61, 1.782], n: [0.668, -0.007, 0.744] },
  ],
  browL: [
    { p: [-0.92, 2.0, 1.974], n: [-0.384, -0.281, 0.879] },
    { p: [-0.7, 2.06, 2.069], n: [-0.239, -0.45, 0.861] },
    { p: [-0.45, 2.06, 2.136], n: [-0.221, -0.496, 0.84] },
    { p: [-0.22, 2.0, 2.15], n: [-0.17, -0.396, 0.903] },
  ],
  browR: [
    { p: [0.94, 1.98, 1.657], n: [0.887, -0.028, 0.461] },
    { p: [0.72, 2.04, 1.955], n: [0.564, -0.044, 0.824] },
    { p: [0.47, 2.04, 2.069], n: [0.291, -0.363, 0.885] },
    { p: [0.24, 1.98, 2.103], n: [0.169, -0.722, 0.671] },
  ],
  nose: [
    { p: [0.0, 1.85, 2.069], n: [0.652, -0.244, 0.718] },
    { p: [0.0, 1.6, 2.197], n: [0.766, 0.36, 0.533] },
    { p: [0.0, 1.35, 2.374], n: [0.637, 0.543, 0.547] },
    { p: [0.0, 1.13, 2.553], n: [0.49, 0.076, 0.868] },
    { p: [-0.27, 1.0, 2.222], n: [-0.144, 0.005, 0.99] },
    { p: [-0.13, 0.94, 2.449], n: [-0.119, -0.874, 0.471] },
    { p: [0.0, 0.92, 2.294], n: [0.565, -0.194, 0.802] },
    { p: [0.13, 0.94, 2.263], n: [0.551, -0.284, 0.785] },
    { p: [0.27, 1.0, 2.028], n: [0.525, 0.148, 0.838] },
  ],
  mouth: [
    { p: [-0.47, 0.47, 2.163], n: [-0.333, -0.335, 0.882] },
    { p: [-0.25, 0.58, 2.312], n: [-0.298, -0.179, 0.937] },
    { p: [0.0, 0.55, 2.313], n: [0.234, -0.297, 0.926] },
    { p: [0.25, 0.58, 2.196], n: [0.479, -0.05, 0.876] },
    { p: [0.47, 0.47, 2.072], n: [0.411, -0.133, 0.902] },
    { p: [0.25, 0.37, 2.135], n: [0.521, -0.062, 0.851] },
    { p: [0.0, 0.33, 2.286], n: [0.143, 0.017, 0.99] },
    { p: [-0.25, 0.37, 2.246], n: [-0.349, 0.044, 0.936] },
    { p: [-0.2, 0.47, 2.242], n: [-0.225, -0.38, 0.897] },
    { p: [0.2, 0.47, 2.196], n: [0.424, -0.293, 0.857] },
  ],
  jaw: [
    { p: [-1.22, 0.95, 1.584], n: [-0.829, -0.069, 0.556] },
    { p: [-1.16, 0.55, 1.629], n: [-0.855, -0.058, 0.515] },
    { p: [-1.02, 0.18, 1.728], n: [-0.798, -0.282, 0.532] },
    { p: [-0.72, -0.12, 1.911], n: [-0.651, -0.332, 0.683] },
    { p: [-0.36, -0.27, 2.181], n: [-0.518, -0.217, 0.827] },
    { p: [0.0, -0.31, 2.247], n: [0.144, -0.301, 0.943] },
    { p: [0.36, -0.27, 2.057], n: [0.695, -0.267, 0.668] },
    { p: [0.72, -0.12, 1.691], n: [0.753, -0.453, 0.478] },
    { p: [1.02, 0.18, 1.077], n: [0.916, -0.388, 0.105] },
    { p: [1.16, 0.55, 0.908], n: [0.972, -0.224, 0.064] },
    { p: [1.22, 0.95, 0.877], n: [0.98, -0.077, 0.185] },
  ],
}

/** Where each region's label is anchored on the surface (and the surface normal there, for back-face hiding). */
export const REGION_ANCHORS = {
  eyeL: { p: [-0.57, 1.74, 1.923], n: [0.103, -0.151, 0.983] },
  eyeR: { p: [0.58, 1.72, 1.938], n: [0.277, -0.179, 0.944] },
  mouth: { p: [0.0, 0.47, 2.245], n: [0.195, -0.232, 0.953] },
  jaw: { p: [0.98, 0.22, 1.395], n: [0.933, -0.237, 0.272] },
} as const satisfies Record<string, Landmark>

/** Region shapes for the shader and for picking: capsules (segment a→b, radius r). */
export const REGION_CAPSULES: { region: "eyeL" | "eyeR" | "mouth" | "jaw"; a: Vec3; b: Vec3; r: number }[] = [
  { region: "eyeL", a: [-0.88, 1.76, 1.91], b: [-0.27, 1.71, 1.938], r: 0.27 },
  { region: "eyeR", a: [0.9, 1.74, 1.604], b: [0.29, 1.69, 1.889], r: 0.27 },
  { region: "mouth", a: [-0.47, 0.47, 2.163], b: [0.47, 0.47, 2.072], r: 0.27 },
  { region: "jaw", a: [-1.16, 0.55, 1.629], b: [-1.02, 0.18, 1.728], r: 0.21 },
  { region: "jaw", a: [-1.02, 0.18, 1.728], b: [-0.72, -0.12, 1.911], r: 0.21 },
  { region: "jaw", a: [-0.72, -0.12, 1.911], b: [-0.36, -0.27, 2.181], r: 0.21 },
  { region: "jaw", a: [-0.36, -0.27, 2.181], b: [0.0, -0.31, 2.247], r: 0.21 },
  { region: "jaw", a: [0.0, -0.31, 2.247], b: [0.36, -0.27, 2.057], r: 0.21 },
  { region: "jaw", a: [0.36, -0.27, 2.057], b: [0.72, -0.12, 1.691], r: 0.21 },
  { region: "jaw", a: [0.72, -0.12, 1.691], b: [1.02, 0.18, 1.077], r: 0.21 },
  { region: "jaw", a: [1.02, 0.18, 1.077], b: [1.16, 0.55, 0.908], r: 0.21 },
]

/** Head extents above the neck (crown to chin, ear to ear) and the point the head turns around. */
export const HEAD_BOUNDS = { min: [-1.897, -0.347, -1.987], max: [1.723, 3.973, 2.59] } as const
export const HEAD_PIVOT: Vec3 = [-0.07, 1.75, 0.25]
/** Below this height the neck fades out into the background (model units). */
export const NECK_FADE: readonly [number, number] = [-1.75, -0.55]

/**
 * Open eyes, painted by the face material over the scan's closed lids (the scan was captured with its
 * eyes closed), so the head can blink.
 *
 * Each eye's plane comes from its corner landmarks; within it the eye runs between the corners of the
 * scan's own lash line (`canthi`: position along the corner line in half widths, height in model units),
 * measured where the closed upper lid overhangs the lower lid. The frame is `o` (between the corners),
 * `u` (inner → outer), `v` (up) and `w` (facing). Shape, in model units: half width, how far the open
 * upper lid rises above the corner line (`upper`), how far the lower lid dips below it (`lower`), where
 * the lids meet when closed (`meet`, fitted to the lash line), the eyeball sphere used for shading
 * (`ball`: centre and radius) and the iris (height of its centre, radius, pupil radius).
 */
export type EyeShape = {
  o: Vec3; u: Vec3; v: Vec3; w: Vec3
  halfWidth: number; upper: number; lower: number; meet: number
  ball: readonly [number, number, number, number]
  /** Iris centre (height `t`, offset along the eye `s` in half widths), radius and pupil radius. */
  iris: { t: number; s: number; r: number; pupil: number }
}

type EyeInput = {
  inner: Vec3; outer: Vec3
  canthi: { inner: readonly [number, number]; outer: readonly [number, number] }
  /** Depth of the lid surface in front of the corner line (along `w`), for placing the eyeball. */
  surface: number
  upper: number; lower: number; meet: number; radius: number
  iris: EyeShape["iris"]
}

function eyeShape(e: EyeInput): EyeShape {
  const mid = [(e.inner[0] + e.outer[0]) / 2, (e.inner[1] + e.outer[1]) / 2, (e.inner[2] + e.outer[2]) / 2]
  const d = [e.outer[0] - e.inner[0], e.outer[1] - e.inner[1], e.outer[2] - e.inner[2]]
  const len = Math.hypot(d[0], d[1], d[2])
  const u0 = [d[0] / len, d[1] / len, d[2] / len]
  // Facing: forward, turned with the eye line; up: perpendicular to both.
  const f = [-u0[0] * u0[2], -u0[1] * u0[2], 1 - u0[2] * u0[2]]
  const fl = Math.hypot(f[0], f[1], f[2])
  const w: Vec3 = [f[0] / fl, f[1] / fl, f[2] / fl]
  let v0 = [w[1] * u0[2] - w[2] * u0[1], w[2] * u0[0] - w[0] * u0[2], w[0] * u0[1] - w[1] * u0[0]]
  if (v0[1] < 0) v0 = [-v0[0], -v0[1], -v0[2]]
  // Re-centre and turn the frame onto the measured lash-line corners (a rotation within the eye plane).
  const hw0 = len / 2
  const ax = e.canthi.inner[0] * hw0, ay = e.canthi.inner[1]
  const bx = e.canthi.outer[0] * hw0, by = e.canthi.outer[1]
  const cx = (ax + bx) / 2, cy = (ay + by) / 2
  const span = Math.hypot(bx - ax, by - ay)
  const c = (bx - ax) / span, sn = (by - ay) / span
  const at = (k: number) => mid[k] + u0[k] * cx + v0[k] * cy
  const o: Vec3 = [at(0), at(1), at(2)]
  const u: Vec3 = [u0[0] * c + v0[0] * sn, u0[1] * c + v0[1] * sn, u0[2] * c + v0[2] * sn]
  const v: Vec3 = [v0[0] * c - u0[0] * sn, v0[1] * c - u0[1] * sn, v0[2] * c - u0[2] * sn]
  // The eyeball sits behind the lid surface at the eye's centre.
  const back = e.surface - e.radius
  const ball = [o[0] + w[0] * back, o[1] + w[1] * back, o[2] + w[2] * back, e.radius] as const
  return { o, u, v, w, halfWidth: span / 2, upper: e.upper, lower: e.lower, meet: e.meet, ball, iris: e.iris }
}

export const EYES: readonly [EyeShape, EyeShape] = [
  eyeShape({
    inner: [-0.27, 1.71, 1.938], outer: [-0.88, 1.76, 1.91], canthi: { inner: [-0.62, -0.008], outer: [1.0, -0.163] },
    surface: 0.0, upper: 0.11, lower: 0.05, meet: 0.031, radius: 0.34, iris: { t: 0.03, s: -0.1, r: 0.104, pupil: 0.038 },
  }),
  eyeShape({
    inner: [0.29, 1.69, 1.889], outer: [0.9, 1.74, 1.604], canthi: { inner: [-1.0, -0.028], outer: [0.8, -0.075] },
    surface: 0.15, upper: 0.1, lower: 0.075, meet: 0.056, radius: 0.34, iris: { t: 0.012, s: -0.16, r: 0.104, pupil: 0.038 },
  }),
]

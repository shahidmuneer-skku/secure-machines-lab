import * as THREE from "three"

import { LANDMARK_GROUPS, type Landmark } from "./face-anchors"
import { SCAN_COLORS } from "./face-material"

/** Order in which landmarks appear during the scan (top to bottom, like the band). */
const ORDER: (keyof typeof LANDMARK_GROUPS)[] = ["browL", "browR", "eyeL", "eyeR", "nose", "mouth", "jaw"]
/** Closed contours; the others are open chains. */
const CLOSED = new Set<keyof typeof LANDMARK_GROUPS>(["eyeL", "eyeR"])

const VERTEX = /* glsl */ `
attribute vec3 aNormal;
attribute float aIndex;
uniform float uCount;
uniform float uOpacity;
uniform float uSize;
uniform float uPixelRatio;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position + aNormal * 0.02, 1.0);
  gl_Position = projectionMatrix * mv;
  vec3 n = normalize(normalMatrix * aNormal);
  // Hide markers on surfaces turned away from the camera (the depth test hides the rest).
  float facing = smoothstep(0.08, 0.4, dot(n, normalize(-mv.xyz)));
  float reveal = clamp(uCount - aIndex, 0.0, 1.0);
  vAlpha = facing * reveal * uOpacity;
  gl_PointSize = uSize * uPixelRatio * (0.55 + 0.45 * reveal);
}`

const POINT_FRAGMENT = /* glsl */ `
uniform vec3 uColor;
varying float vAlpha;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float r = length(c);
  float disc = 1.0 - smoothstep(0.38, 0.5, r);
  float core = 1.0 - smoothstep(0.12, 0.22, r);
  float a = (disc * 0.55 + core * 0.45) * vAlpha;
  if (a < 0.01) discard;
  gl_FragColor = vec4(uColor, a);
}`

const LINE_FRAGMENT = /* glsl */ `
uniform vec3 uColor;
varying float vAlpha;
void main() {
  if (vAlpha < 0.01) discard;
  gl_FragColor = vec4(uColor, vAlpha * 0.5);
}`

/**
 * Facial landmarks as points plus thin contours, offset slightly off the surface along its normal so
 * they stay attached as the head moves. Depth-tested against the head, so markers behind the face or
 * on the back of the head never show through. They only ever connect to other facial landmarks.
 */
export function createLandmarkLayer() {
  const points: Landmark[] = []
  const pairs: [number, number][] = []
  for (const group of ORDER) {
    const list = LANDMARK_GROUPS[group]
    const start = points.length
    points.push(...list)
    for (let i = 0; i < list.length - 1; i++) pairs.push([start + i, start + i + 1])
    if (CLOSED.has(group)) pairs.push([start + list.length - 1, start])
  }

  const uniforms = {
    uCount: { value: 0 },
    uOpacity: { value: 1 },
    uSize: { value: 6 },
    uPixelRatio: { value: 1 },
    uColor: { value: new THREE.Color(SCAN_COLORS.scan) },
  }

  const pointGeometry = new THREE.BufferGeometry()
  pointGeometry.setAttribute("position", new THREE.Float32BufferAttribute(points.flatMap((l) => [...l.p]), 3))
  pointGeometry.setAttribute("aNormal", new THREE.Float32BufferAttribute(points.flatMap((l) => [...l.n]), 3))
  pointGeometry.setAttribute("aIndex", new THREE.Float32BufferAttribute(points.map((_, i) => i), 1))

  const lineGeometry = new THREE.BufferGeometry()
  lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(pairs.flatMap(([a, b]) => [...points[a].p, ...points[b].p]), 3))
  lineGeometry.setAttribute("aNormal", new THREE.Float32BufferAttribute(pairs.flatMap(([a, b]) => [...points[a].n, ...points[b].n]), 3))
  // A segment appears once both of its ends have.
  lineGeometry.setAttribute("aIndex", new THREE.Float32BufferAttribute(pairs.flatMap(([a, b]) => [Math.max(a, b), Math.max(a, b)]), 1))

  const common = { uniforms, vertexShader: VERTEX, transparent: true, depthWrite: false, depthTest: true }
  const pointMaterial = new THREE.ShaderMaterial({ ...common, fragmentShader: POINT_FRAGMENT })
  const lineMaterial = new THREE.ShaderMaterial({ ...common, fragmentShader: LINE_FRAGMENT })

  const group = new THREE.Group()
  const pointsObject = new THREE.Points(pointGeometry, pointMaterial)
  const linesObject = new THREE.LineSegments(lineGeometry, lineMaterial)
  pointsObject.renderOrder = 3
  linesObject.renderOrder = 2
  pointsObject.frustumCulled = false
  linesObject.frustumCulled = false
  group.add(linesObject, pointsObject)

  return {
    group,
    count: points.length,
    /** fraction 0–1 of landmarks shown, overall opacity, point size (CSS px) and device pixel ratio. */
    update(fraction: number, opacity: number, size: number, pixelRatio: number) {
      uniforms.uCount.value = fraction * points.length
      uniforms.uOpacity.value = opacity
      uniforms.uSize.value = size
      uniforms.uPixelRatio.value = pixelRatio
      group.visible = fraction > 0.001 && opacity > 0.001
    },
    dispose() {
      pointGeometry.dispose()
      lineGeometry.dispose()
      pointMaterial.dispose()
      lineMaterial.dispose()
    },
  }
}

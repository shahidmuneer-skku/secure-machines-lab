import * as THREE from "three"

import { NECK_FADE, REGION_CAPSULES } from "./face-anchors"

/** Palette shared with the CSS (validated for contrast in globals.css). */
export const SCAN_COLORS = {
  background: "#080F1C",
  surface: "#111D30",
  scan: "#39D9E6",
  complete: "#30D2B0",
  evidence: "#FFAD70",
  action: "#4268F6",
} as const

export type FaceUniforms = {
  uBandY: { value: number }
  uBand: { value: number }
  uWire: { value: number }
  uReveal: { value: number }
  uSurface: { value: number }
  uOpacity: { value: number }
  uScan: { value: THREE.Color }
  uAmber: { value: THREE.Color }
  uDeep: { value: THREE.Color }
  /** Per region (eyeL, eyeR, mouth, jaw): hover tint, outline, amber outline (selected) and evidence overlay. */
  uFill: { value: THREE.Vector4 }
  uLine: { value: THREE.Vector4 }
  uLineAmber: { value: THREE.Vector4 }
  uEvidence: { value: THREE.Vector4 }
  uCapA: { value: THREE.Vector3[] }
  uCapB: { value: THREE.Vector4[] }
  uNeck: { value: THREE.Vector2 }
}

const CAPSULES = REGION_CAPSULES.length
const JAW_FIRST = REGION_CAPSULES.findIndex((c) => c.region === "jaw")

/**
 * The head's material: a sculptural MeshStandardMaterial (soft key, fill and cyan rim come from the
 * scene lights) with the forensic layers drawn in the same pass, so they can never drift off the face:
 * - triangulated wireframe from per-triangle barycentrics (the scan's own topology, denser around
 *   the eyes, nose and mouth), revealed behind the scan band;
 * - the scan band itself;
 * - region outlines and an illustrative amber evidence overlay, computed from the region capsules;
 * - a fade of the neck into the background.
 */
export function createFaceMaterial(normalMap: THREE.Texture | null) {
  const uniforms: FaceUniforms = {
    uBandY: { value: 4.5 },
    uBand: { value: 0 },
    uWire: { value: 0.07 },
    uReveal: { value: 0 },
    uSurface: { value: 1 },
    uOpacity: { value: 1 },
    uScan: { value: new THREE.Color(SCAN_COLORS.scan) },
    uAmber: { value: new THREE.Color(SCAN_COLORS.evidence) },
    uDeep: { value: new THREE.Color("#0b1626") },
    uFill: { value: new THREE.Vector4() },
    uLine: { value: new THREE.Vector4() },
    uLineAmber: { value: new THREE.Vector4() },
    uEvidence: { value: new THREE.Vector4() },
    uCapA: { value: REGION_CAPSULES.map((c) => new THREE.Vector3(...c.a)) },
    uCapB: { value: REGION_CAPSULES.map((c) => new THREE.Vector4(c.b[0], c.b[1], c.b[2], c.r)) },
    uNeck: { value: new THREE.Vector2(NECK_FADE[0], NECK_FADE[1]) },
  }

  const material = new THREE.MeshStandardMaterial({
    color: new THREE.Color("#b8c2d2"),
    roughness: 0.58,
    metalness: 0,
    normalMap: normalMap ?? undefined,
    normalScale: new THREE.Vector2(0.85, 0.85),
    transparent: true,
    depthWrite: true,
  })

  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms)
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
attribute vec3 aBary;
attribute float aFacet;
varying vec3 vObj;
varying vec3 vBary;
varying float vFacet;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
vObj = position;
vBary = aBary;
vFacet = aFacet;`,
      )

    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
#define CAPSULES ${CAPSULES}
#define JAW_FIRST ${JAW_FIRST}
uniform float uBandY;
uniform float uBand;
uniform float uWire;
uniform float uReveal;
uniform float uSurface;
uniform float uOpacity;
uniform vec3 uScan;
uniform vec3 uAmber;
uniform vec3 uDeep;
uniform vec4 uFill;
uniform vec4 uLine;
uniform vec4 uLineAmber;
uniform vec4 uEvidence;
uniform vec3 uCapA[CAPSULES];
uniform vec4 uCapB[CAPSULES];
uniform vec2 uNeck;
varying vec3 vObj;
varying vec3 vBary;
varying float vFacet;

float capsuleD(vec3 p, vec3 a, vec4 b) {
  vec3 ab = b.xyz - a;
  float t = clamp(dot(p - a, ab) / dot(ab, ab), 0.0, 1.0);
  return length(p - a - ab * t) / b.w;
}

float wireEdge(vec3 bary, float width) {
  vec3 d = fwidth(bary);
  vec3 a = smoothstep(vec3(0.0), d * width, bary);
  return 1.0 - min(min(a.x, a.y), a.z);
}`,
      )
      .replace(
        "#include <opaque_fragment>",
        `
// ---- forensic layers (model space) ----
float dEyeL = capsuleD(vObj, uCapA[0], uCapB[0]);
float dEyeR = capsuleD(vObj, uCapA[1], uCapB[1]);
float dMouth = capsuleD(vObj, uCapA[2], uCapB[2]);
float dJaw = 1e3;
for (int i = JAW_FIRST; i < CAPSULES; i++) dJaw = min(dJaw, capsuleD(vObj, uCapA[i], uCapB[i]));
vec4 dReg = vec4(dEyeL, dEyeR, dMouth, dJaw);
vec4 inside = 1.0 - smoothstep(0.7, 1.0, dReg);
vec4 ringW = fwidth(dReg) * 1.25 + 0.012;
vec4 ring = 1.0 - smoothstep(ringW * 0.4, ringW, abs(dReg - 1.0));

// Wire detail is stronger around the eyes, nose and mouth, calmer on cheeks and forehead.
float dNose = capsuleD(vObj, vec3(0.0, 1.85, 2.07), vec4(0.0, 1.0, 2.42, 0.28));
float feature = 1.0 - smoothstep(1.0, 2.8, min(min(dEyeL, dEyeR), min(dMouth, dNose)));
float scanned = smoothstep(uBandY - 0.02, uBandY + 0.3, vObj.y);
float wireAmt = clamp(uWire + uReveal * scanned, 0.0, 1.0) * mix(0.38, 1.0, feature);
float edge = wireEdge(vBary, 1.15);

float bandDist = abs(vObj.y - uBandY);
float bandCore = (1.0 - smoothstep(0.0, 0.03, bandDist)) * uBand;
float bandGlow = (1.0 - smoothstep(0.0, 0.32, bandDist)) * uBand * step(uBandY, vObj.y + 0.32);

vec3 lit = outgoingLight;
// Dimmed surface for the mesh view: deep navy with a faint rim so the silhouette still reads.
float rim = pow(1.0 - clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0), 2.0);
vec3 dim = uDeep + uScan * rim * 0.08;
vec3 col = mix(dim, lit, uSurface);

col = mix(col, uScan, edge * wireAmt * 0.7);
col = mix(col, uScan, edge * bandGlow * 0.6);
col += uScan * (bandCore * 0.9 + bandGlow * 0.12);

float hoverFill = dot(inside, uFill);
col = mix(col, uScan, hoverFill * 0.16);
float amberFacet = dot(inside, uEvidence) * (0.25 + 0.75 * step(0.42, vFacet));
col = mix(col, uAmber, amberFacet * 0.42);
col = mix(col, uAmber, edge * dot(inside, uEvidence) * 0.55);
col = mix(col, uScan, clamp(dot(ring, uLine), 0.0, 1.0) * 0.9);
col = mix(col, uAmber, clamp(dot(ring, uLineAmber), 0.0, 1.0));

float neck = smoothstep(uNeck.x, uNeck.y, vObj.y);
outgoingLight = col;
diffuseColor.a = neck * uOpacity;
#include <opaque_fragment>`,
      )
  }
  // Every head shares one compiled program.
  material.customProgramCacheKey = () => "sml-face-v1"
  return { material, uniforms }
}

/**
 * Converts the loaded (quantized, indexed) head geometry into the non-indexed geometry the material
 * needs: float positions in model units, smooth normals, UVs, barycentrics and a per-triangle random.
 */
export function prepareFaceGeometry(source: THREE.BufferGeometry, matrix: THREE.Matrix4) {
  const g = source.index ? source.toNonIndexed() : source.clone()
  const pos = g.getAttribute("position")
  const nor = g.getAttribute("normal")
  const uv = g.getAttribute("uv")
  const count = pos.count
  const position = new Float32Array(count * 3)
  const normal = new Float32Array(count * 3)
  const uvs = new Float32Array(count * 2)
  const bary = new Float32Array(count * 3)
  const facet = new Float32Array(count)
  const v = new THREE.Vector3()
  const n = new THREE.Vector3()
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(matrix)
  let seed = 7
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647)
  for (let i = 0; i < count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(matrix)
    position.set([v.x, v.y, v.z], i * 3)
    if (nor) {
      n.fromBufferAttribute(nor, i).applyMatrix3(normalMatrix).normalize()
      normal.set([n.x, n.y, n.z], i * 3)
    }
    if (uv) uvs.set([uv.getX(i), uv.getY(i)], i * 2)
    bary[i * 3 + (i % 3)] = 1
    if (i % 3 === 0) {
      const r = rand()
      facet[i] = facet[i + 1] = facet[i + 2] = r
    }
  }
  g.dispose()
  const out = new THREE.BufferGeometry()
  out.setAttribute("position", new THREE.BufferAttribute(position, 3))
  out.setAttribute("normal", new THREE.BufferAttribute(normal, 3))
  out.setAttribute("uv", new THREE.BufferAttribute(uvs, 2))
  out.setAttribute("aBary", new THREE.BufferAttribute(bary, 3))
  out.setAttribute("aFacet", new THREE.BufferAttribute(facet, 1))
  if (!nor) out.computeVertexNormals()
  out.computeBoundingBox()
  out.computeBoundingSphere()
  return out
}

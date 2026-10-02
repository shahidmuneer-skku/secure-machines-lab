import * as THREE from "three"

import { seededRandom } from "@/lib/seeded-random"

import { SCAN_COLORS } from "./face-material"

/** Pointer influence radius and push distance, in CSS pixels; easing time constant in seconds. */
const RADIUS = 140
const PUSH = 11
const TAU = 0.15

type Layer = {
  nodes: { x: number; y: number; ox: number; oy: number; k: number; tx: number; ty: number; tk: number }[]
  edges: [number, number][]
  tris: [number, number, number, number][] // a, b, c, random
  depth: number
  edgeGeometry: THREE.BufferGeometry
  facetGeometry: THREE.BufferGeometry
  edgeAlpha: Float32Array
  facetAlpha: Float32Array
  edgePos: Float32Array
  facetPos: Float32Array
  group: THREE.Group
}

const VERTEX = /* glsl */ `
attribute float aAlpha;
varying float vAlpha;
void main() {
  vAlpha = aAlpha;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`
const FRAGMENT = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying float vAlpha;
void main() {
  float a = vAlpha * uOpacity;
  if (a < 0.002) discard;
  gl_FragColor = vec4(uColor, a);
}`

/**
 * The triangulated background field: a jittered triangular lattice (stable local adjacency, so the
 * triangles never re-wire) in two slightly separated depth layers. Nodes near the pointer shift away
 * by ~11 px, nearby edges brighten and a few facets change opacity, then everything eases back.
 * Activity is much weaker behind the text column. It is purely decorative and never receives events.
 */
export class PolygonField {
  readonly scene = new THREE.Scene()
  readonly camera = new THREE.OrthographicCamera(0, 1, 0, -1, -10, 10)
  private layers: Layer[] = []
  private width = 1
  private height = 1
  private edgeMaterial: THREE.ShaderMaterial
  private facetMaterial: THREE.ShaderMaterial

  constructor(private readonly budget: number) {
    this.edgeMaterial = new THREE.ShaderMaterial({
      uniforms: { uColor: { value: new THREE.Color(SCAN_COLORS.scan) }, uOpacity: { value: 1 } },
      vertexShader: VERTEX, fragmentShader: FRAGMENT, transparent: true, depthTest: false, depthWrite: false,
    })
    this.facetMaterial = new THREE.ShaderMaterial({
      uniforms: { uColor: { value: new THREE.Color("#5b86ff") }, uOpacity: { value: 1 } },
      vertexShader: VERTEX, fragmentShader: FRAGMENT, transparent: true, depthTest: false, depthWrite: false,
    })
  }

  /** Rebuilds the lattice for a new stage size (deterministic: same size → same field). */
  resize(width: number, height: number) {
    if (Math.abs(width - this.width) < 1 && Math.abs(height - this.height) < 1 && this.layers.length) return
    this.width = width
    this.height = height
    this.camera.left = 0
    this.camera.right = width
    this.camera.top = 0
    this.camera.bottom = -height
    this.camera.updateProjectionMatrix()
    this.disposeLayers()
    const back = Math.round(this.budget * 0.28)
    this.layers = [this.buildLayer(back, 0.55, 11), this.buildLayer(this.budget - back, 1, 23)]
  }

  private buildLayer(count: number, depth: number, seed: number): Layer {
    const rand = seededRandom(seed + Math.round(this.width) * 3 + Math.round(this.height))
    const margin = 60
    const w = this.width + margin * 2
    const h = this.height + margin * 2
    const spacing = Math.sqrt((w * h) / (count * 0.866))
    const cols = Math.max(2, Math.round(w / spacing) + 1)
    const rows = Math.max(2, Math.round(h / (spacing * 0.866)) + 1)
    const sx = w / (cols - 1)
    const sy = h / (rows - 1)
    const nodes: Layer["nodes"] = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const edgeNode = r === 0 || c === 0 || r === rows - 1 || c === cols - 1
        const jx = edgeNode ? 0 : (rand() - 0.5) * sx * 0.55
        const jy = edgeNode ? 0 : (rand() - 0.5) * sy * 0.55
        const x = -margin + c * sx + (r % 2 ? sx * 0.5 : 0) + jx
        const y = -margin + r * sy + jy
        nodes.push({ x, y, ox: 0, oy: 0, k: 0, tx: 0, ty: 0, tk: 0 })
      }
    }
    const id = (r: number, c: number) => r * cols + c
    const edges: [number, number][] = []
    const tris: Layer["tris"] = []
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (c < cols - 1) edges.push([id(r, c), id(r, c + 1)])
        if (r < rows - 1) {
          // Offset rows: odd rows lean right, so connect down-left/down-right accordingly.
          const dl = r % 2 ? c : c - 1
          const dr = r % 2 ? c + 1 : c
          if (dl >= 0 && dl < cols) edges.push([id(r, c), id(r + 1, dl)])
          if (dr >= 0 && dr < cols) edges.push([id(r, c), id(r + 1, dr)])
          if (dl >= 0 && dr < cols && dl < cols && dr >= 0) tris.push([id(r, c), id(r + 1, dl), id(r + 1, dr), rand()])
          if (c < cols - 1 && dr < cols && dr >= 0) tris.push([id(r, c), id(r, c + 1), id(r + 1, dr), rand()])
        }
      }
    }
    const edgePos = new Float32Array(edges.length * 6)
    const edgeAlpha = new Float32Array(edges.length * 2)
    const facetPos = new Float32Array(tris.length * 9)
    const facetAlpha = new Float32Array(tris.length * 3)
    const edgeGeometry = new THREE.BufferGeometry()
    edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePos, 3).setUsage(THREE.DynamicDrawUsage))
    edgeGeometry.setAttribute("aAlpha", new THREE.BufferAttribute(edgeAlpha, 1).setUsage(THREE.DynamicDrawUsage))
    const facetGeometry = new THREE.BufferGeometry()
    facetGeometry.setAttribute("position", new THREE.BufferAttribute(facetPos, 3).setUsage(THREE.DynamicDrawUsage))
    facetGeometry.setAttribute("aAlpha", new THREE.BufferAttribute(facetAlpha, 1).setUsage(THREE.DynamicDrawUsage))
    const group = new THREE.Group()
    const lines = new THREE.LineSegments(edgeGeometry, this.edgeMaterial)
    const facets = new THREE.Mesh(facetGeometry, this.facetMaterial)
    lines.frustumCulled = false
    facets.frustumCulled = false
    group.add(facets, lines)
    this.scene.add(group)
    const layer: Layer = { nodes, edges, tris, depth, edgeGeometry, facetGeometry, edgeAlpha, facetAlpha, edgePos, facetPos, group }
    this.write(layer, 1, 0, 0)
    return layer
  }

  /**
   * Advances the easing and writes the buffers. Returns true while anything is still moving.
   * `pointer` is in stage pixels (null when outside), `activity` scales the whole field (0–1),
   * `parallax` shifts the layers by a few pixels with scroll, `textRight` calms the text column.
   */
  update(dt: number, pointer: { x: number; y: number } | null, activity: number, parallax: number, textRight: number, reactive: boolean) {
    let moving = false
    const step = reactive ? 1 - Math.exp(-dt / TAU) : 1
    for (const layer of this.layers) {
      const py = parallax * layer.depth
      for (const n of layer.nodes) {
        let tx = 0, ty = 0, tk = 0
        if (pointer && reactive) {
          const dx = n.x - pointer.x
          const dy = n.y + py - pointer.y
          const d = Math.hypot(dx, dy)
          if (d < RADIUS) {
            const f = (1 - d / RADIUS) ** 2 * calm(n.x, textRight)
            const push = PUSH * layer.depth * f
            tx = d > 0.001 ? (dx / d) * push : 0
            ty = d > 0.001 ? (dy / d) * push : 0
            tk = f
          }
        }
        n.ox += (tx - n.ox) * step
        n.oy += (ty - n.oy) * step
        n.k += (tk - n.k) * step
        if (Math.abs(tx - n.ox) > 0.05 || Math.abs(ty - n.oy) > 0.05 || Math.abs(tk - n.k) > 0.004) moving = true
      }
      this.write(layer, activity, py, textRight)
    }
    return moving
  }

  private write(layer: Layer, activity: number, py: number, textRight: number) {
    const { nodes, edges, tris, edgePos, edgeAlpha, facetPos, facetAlpha, depth } = layer
    const baseEdge = 0.05 + 0.05 * depth
    for (let i = 0; i < edges.length; i++) {
      const a = nodes[edges[i][0]]
      const b = nodes[edges[i][1]]
      edgePos[i * 6] = a.x + a.ox
      edgePos[i * 6 + 1] = -(a.y + a.oy + py)
      edgePos[i * 6 + 3] = b.x + b.ox
      edgePos[i * 6 + 4] = -(b.y + b.oy + py)
      const calmA = calm(a.x, textRight)
      const calmB = calm(b.x, textRight)
      edgeAlpha[i * 2] = (baseEdge * (0.45 + 0.55 * calmA) + 0.22 * a.k) * activity
      edgeAlpha[i * 2 + 1] = (baseEdge * (0.45 + 0.55 * calmB) + 0.22 * b.k) * activity
    }
    for (let i = 0; i < tris.length; i++) {
      const [ia, ib, ic, r] = tris[i]
      const pts = [nodes[ia], nodes[ib], nodes[ic]]
      const k = (pts[0].k + pts[1].k + pts[2].k) / 3
      const cx = (pts[0].x + pts[1].x + pts[2].x) / 3
      // A faint, varied base so the field has depth; only a few facets (r > .62) respond to the pointer.
      const alpha = ((0.012 + 0.03 * r * r) * depth * (0.35 + 0.65 * calm(cx, textRight)) + (r > 0.62 ? 0.07 : 0.015) * k) * activity
      for (let j = 0; j < 3; j++) {
        facetPos[i * 9 + j * 3] = pts[j].x + pts[j].ox
        facetPos[i * 9 + j * 3 + 1] = -(pts[j].y + pts[j].oy + py)
        facetAlpha[i * 3 + j] = alpha
      }
    }
    layer.edgeGeometry.attributes.position.needsUpdate = true
    layer.edgeGeometry.attributes.aAlpha.needsUpdate = true
    layer.facetGeometry.attributes.position.needsUpdate = true
    layer.facetGeometry.attributes.aAlpha.needsUpdate = true
  }

  get nodeCount() {
    return this.layers.reduce((n, l) => n + l.nodes.length, 0)
  }

  private disposeLayers() {
    for (const l of this.layers) {
      this.scene.remove(l.group)
      l.edgeGeometry.dispose()
      l.facetGeometry.dispose()
    }
    this.layers = []
  }

  dispose() {
    this.disposeLayers()
    this.edgeMaterial.dispose()
    this.facetMaterial.dispose()
  }
}

/** 0.2 behind the text column, rising to 1 a little to its right. */
function calm(x: number, textRight: number) {
  if (textRight <= 0) return 1
  const t = Math.min(1, Math.max(0, (x - (textRight - 60)) / 180))
  return 0.2 + 0.8 * t * t * (3 - 2 * t)
}

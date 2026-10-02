import * as THREE from "three"
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js"

import { REGIONS, type RegionId, type ScanController, regionAt } from "./controller"
import { HEAD_PIVOT, REGION_ANCHORS } from "./face-anchors"
import { createFaceMaterial, prepareFaceGeometry, type FaceUniforms } from "./face-material"
import { createLandmarkLayer } from "./landmark-layer"
import { PolygonField } from "./polygon-field"
import { LAYER_OVERRIDES, type LayerMode, sampleScan, type ScanState } from "./timeline"

export type Tier = "full" | "lite"

const DEG = Math.PI / 180
/** Crown-to-chin height of the head in model units (sets the on-screen size). */
const HEAD_HEIGHT = 4.32
const CAMERA_DISTANCE = 24
const FOV = 30

/** Points used to frame the head on screen in the hand-off stage (crown, chin, ears, nose). */
const FRAME_POINTS = [
  new THREE.Vector3(-0.07, 3.97, 0.2), new THREE.Vector3(0, -0.35, 2.2), new THREE.Vector3(-1.9, 1.3, 0.15),
  new THREE.Vector3(1.72, 1.4, 0.1), new THREE.Vector3(0, 1.12, 2.59), new THREE.Vector3(0, 1.8, -1.98),
]

/** Which side of the head each region's label prefers (the other side is used when there is no room). */
const LABEL_SIDE: Record<RegionId, "left" | "right"> = { eyeL: "left", eyeR: "right", mouth: "right", jaw: "right" }

type Rect = { x: number; y: number; w: number; h: number }
const damp = (current: number, target: number, tau: number, dt: number) => current + (target - current) * (1 - Math.exp(-dt / tau))

/**
 * Everything the WebGL scene does, independent of React: loads the head, owns the THREE objects and
 * renders one frame from the controller's state. The React wrapper calls `frame()` from its single
 * render loop and disposes this object on unmount.
 */
export class FaceStage {
  private readonly scene = new THREE.Scene()
  private readonly camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 100)
  /** Parent: scroll timeline transform. Child: pointer offsets. Inner: centres the head on its pivot. */
  private readonly scrollGroup = new THREE.Group()
  private readonly pointerGroup = new THREE.Group()
  private readonly modelGroup = new THREE.Group()
  private readonly field: PolygonField
  private readonly landmarks = createLandmarkLayer()
  private readonly raycaster = new THREE.Raycaster()
  private mesh: THREE.Mesh | null = null
  private uniforms: FaceUniforms | null = null
  private disposables: { dispose: () => void }[] = []
  private disposed = false
  private width = 1
  private height = 1
  // eased values
  private yawOffset = 0
  private pitchOffset = 0
  private layerMix = 0
  private lastLayer: Exclude<LayerMode, "follow"> = "mesh"
  private regionHover: Record<RegionId, number> = { eyeL: 0, eyeR: 0, mouth: 0, jaw: 0 }
  private regionSelect: Record<RegionId, number> = { eyeL: 0, eyeR: 0, mouth: 0, jaw: 0 }
  private labelSizes = new Map<HTMLElement, { w: number; h: number }>()
  private tmp = new THREE.Vector3()
  private tmpN = new THREE.Vector3()
  private camPos = new THREE.Vector3()
  ready = false

  constructor(private readonly controller: ScanController, private readonly tier: Tier) {
    this.field = new PolygonField(tier === "full" ? 132 : 56)
    this.camera.position.set(0, 0, CAMERA_DISTANCE)
    this.scrollGroup.rotation.order = "YXZ"
    this.modelGroup.position.set(-HEAD_PIVOT[0], -HEAD_PIVOT[1], -HEAD_PIVOT[2])
    this.scrollGroup.add(this.pointerGroup)
    this.pointerGroup.add(this.modelGroup)
    this.modelGroup.add(this.landmarks.group)
    this.scene.add(this.scrollGroup)

    // Soft key, subtle fill, restrained cyan rim. No shadow maps.
    const key = new THREE.DirectionalLight("#fff3e8", 2.3)
    key.position.set(-6.5, 5, 6)
    const fill = new THREE.DirectionalLight("#9fb6ff", 0.32)
    fill.position.set(7, 0, 4)
    const rim = new THREE.DirectionalLight("#39D9E6", 1.6)
    rim.position.set(5, 3, -6)
    const hemi = new THREE.HemisphereLight("#b4c4e0", "#070d18", 0.32)
    this.scene.add(key, fill, rim, hemi)
  }

  async load(baseUrl = "/models/face") {
    const loader = new GLTFLoader()
    const textureLoader = new THREE.TextureLoader()
    const [gltf, normalMap] = await Promise.all([
      loader.loadAsync(`${baseUrl}/${this.tier === "full" ? "head.glb" : "head-lite.glb"}`),
      textureLoader.loadAsync(`${baseUrl}/${this.tier === "full" ? "normal.webp" : "normal-512.webp"}`).catch(() => null),
    ])
    let source: THREE.Mesh | null = null
    gltf.scene.updateMatrixWorld(true)
    gltf.scene.traverse((o) => { if (!source && (o as THREE.Mesh).isMesh) source = o as THREE.Mesh })
    if (!source) throw new Error("The head model contains no mesh")
    const src = source as THREE.Mesh
    const geometry = prepareFaceGeometry(src.geometry, src.matrixWorld)
    // Release everything the loader created.
    gltf.scene.traverse((o) => {
      const m = o as THREE.Mesh
      if (m.isMesh) {
        m.geometry.dispose()
        ;(Array.isArray(m.material) ? m.material : [m.material]).forEach((mat) => mat.dispose())
      }
    })
    if (normalMap) {
      normalMap.flipY = false
      normalMap.colorSpace = THREE.NoColorSpace
      normalMap.anisotropy = 4
    }
    if (this.disposed) {
      // Finished loading after unmount: free it immediately.
      geometry.dispose()
      normalMap?.dispose()
      return
    }
    const { material, uniforms } = createFaceMaterial(normalMap)
    this.uniforms = uniforms
    this.mesh = new THREE.Mesh(geometry, material)
    this.mesh.renderOrder = 1
    this.modelGroup.add(this.mesh)
    this.disposables.push(geometry, material)
    if (normalMap) this.disposables.push(normalMap)
    this.ready = true
  }

  resize(width: number, height: number) {
    this.width = Math.max(1, width)
    this.height = Math.max(1, height)
    this.camera.aspect = this.width / this.height
    this.camera.updateProjectionMatrix()
    this.field.resize(this.width, this.height)
    this.labelSizes.clear()
  }

  /** Advances eased values and renders. Returns true while another frame is needed. */
  frame(gl: THREE.WebGLRenderer, dt: number, pixelRatio: number): boolean {
    const c = this.controller
    let moving = false
    const instant = c.reducedMotion || c.motionPaused

    // Progress: scroll mode is already smoothed by ScrollTrigger's scrub; the manual mode tweens here.
    if (c.mode === "manual" && !instant) {
      const next = damp(c.shownProgress, c.progress, 0.32, dt)
      c.shownProgress = Math.abs(next - c.progress) < 0.0005 ? c.progress : next
      if (c.shownProgress !== c.progress) moving = true
    } else {
      c.shownProgress = c.progress
    }
    const s = sampleScan(c.shownProgress)

    // Layer views (Surface / Mesh / Evidence) blend over the timeline until "Follow scroll".
    const pinned = c.layer !== "follow"
    if (c.layer !== "follow") this.lastLayer = c.layer
    const mixTarget = pinned ? 1 : 0
    this.layerMix = instant ? mixTarget : damp(this.layerMix, mixTarget, 0.12, dt)
    if (Math.abs(this.layerMix - mixTarget) > 0.002) moving = true
    else this.layerMix = mixTarget
    const o = LAYER_OVERRIDES[this.lastLayer]
    const m = this.layerMix
    const surface = s.surface + (o.surface - s.surface) * m
    const wire = s.wire + (o.wire - s.wire) * m
    const reveal = s.reveal * (1 - m)
    const landmarks = s.landmarks + (o.landmarks - s.landmarks) * m
    const evidence = s.evidence + (o.evidence - s.evidence) * m

    // Layout: the head's on-screen centre and size.
    const manual = c.mode === "manual"
    const top = manual ? 0 : c.navHeight
    const usable = this.height - top
    // Manual mode (own scene box): the head stays near the centre, with a little of the lateral story.
    const cx = manual ? 0.5 + (s.cx - 0.715) * 0.3 : s.cx
    const cy = manual ? 0.5 + (s.cy - 0.5) * 0.35 : s.cy
    const base = manual ? Math.min(0.74 * this.height, 0.78 * this.width) : Math.min(0.62 * usable, 0.46 * this.width)
    const headPx = base * s.size
    const px = cx * this.width
    const py = top + cy * usable
    this.camera.setViewOffset(this.width, this.height, this.width / 2 - px, this.height / 2 - py, this.width, this.height)
    const worldPerPx = (2 * CAMERA_DISTANCE * Math.tan((FOV / 2) * DEG)) / this.height
    this.scrollGroup.scale.setScalar((headPx * worldPerPx) / HEAD_HEIGHT)
    this.scrollGroup.rotation.set(s.pitch * DEG, s.yaw * DEG, s.roll * DEG)

    // Pointer-follow (child transform): ±5° yaw, ±3° pitch; paused while a region is selected.
    const follow = c.pointerFollow && !c.selected && !instant && c.mode === "scroll" && c.pointer.inside
    const ty = follow ? clampUnit((c.pointer.x - px) / (this.width * 0.5)) * 5 : 0
    const tp = follow ? clampUnit((c.pointer.y - py) / (this.height * 0.5)) * 3 : 0
    this.yawOffset = instant ? ty : damp(this.yawOffset, ty, 0.3, dt)
    this.pitchOffset = instant ? tp : damp(this.pitchOffset, tp, 0.3, dt)
    if (Math.abs(this.yawOffset - ty) > 0.02 || Math.abs(this.pitchOffset - tp) > 0.02) moving = true
    this.pointerGroup.rotation.set(this.pitchOffset * DEG, this.yawOffset * DEG, 0)
    this.scene.updateMatrixWorld()

    // Region highlights: hover (cyan tint + outline), selection (amber outline), evidence overlay.
    for (const id of REGIONS) {
      const h = c.hover === id ? 1 : 0
      const sel = c.selected === id ? 1 : 0
      this.regionHover[id] = instant ? h : damp(this.regionHover[id], h, 0.08, dt)
      this.regionSelect[id] = instant ? sel : damp(this.regionSelect[id], sel, 0.08, dt)
      if (Math.abs(this.regionHover[id] - h) > 0.01 || Math.abs(this.regionSelect[id] - sel) > 0.01) moving = true
    }
    if (this.uniforms) {
      const u = this.uniforms
      u.uBandY.value = s.bandY
      u.uBand.value = s.band * (1 - m)
      u.uWire.value = wire
      u.uReveal.value = reveal
      u.uSurface.value = surface
      const rh = this.regionHover, rs = this.regionSelect
      u.uFill.value.set(rh.eyeL, rh.eyeR, rh.mouth, rh.jaw).multiplyScalar(1)
      u.uLine.value.set(
        rh.eyeL * (1 - rs.eyeL),
        Math.max(rh.eyeR, s.calloutEye * (1 - m)) * (1 - rs.eyeR),
        Math.max(rh.mouth, s.calloutMouth * (1 - m)) * (1 - rs.mouth),
        Math.max(rh.jaw, evidence * 0.6) * (1 - rs.jaw),
      )
      u.uLineAmber.value.set(rs.eyeL, rs.eyeR, rs.mouth, rs.jaw)
      // Illustrative overlay: the mouth and face boundary during inspection, plus any selected region.
      const evMouth = evidence
      const evJaw = s.stage >= 3 && !pinned ? 0 : evidence * 0.8
      u.uEvidence.value.set(rs.eyeL * 0.5, rs.eyeR * 0.5, Math.max(evMouth, rs.mouth * 0.5), Math.max(evJaw, rs.jaw * 0.5))
    }
    this.landmarks.update(landmarks, 0.9, this.tier === "full" ? 6 : 5, pixelRatio)

    // Polygon background: calmer behind the text, fades out in the hand-off.
    const pointer = c.pointer.inside && !c.pointer.overControl ? { x: c.pointer.x, y: c.pointer.y } : null
    const reactive = !instant && c.mode === "scroll" && c.pointerFollow
    if (this.field.update(dt, pointer, s.field, c.reducedMotion ? 0 : -c.shownProgress * 30, manual ? 0 : c.textRight, reactive)) moving = true

    // Render: background field (orthographic, CSS pixels), then the head.
    gl.autoClear = false
    gl.clear()
    if (!c.hideField) gl.render(this.field.scene, this.field.camera)
    gl.clearDepth()
    if (this.ready) gl.render(this.scene, this.camera)

    this.placeOverlay(s)
    return moving
  }

  /** Projects the region anchors into overlay coordinates and places labels, the selected card and the frame. */
  private placeOverlay(s: ScanState) {
    const c = this.controller
    const mesh = this.mesh
    const labels = c.dom.labels
    const shown: { id: RegionId; alpha: number }[] = []
    if (mesh && !c.selected) {
      const m = this.layerMix
      if (c.hover) shown.push({ id: c.hover, alpha: 1 })
      const auto: { id: RegionId; alpha: number }[] = [
        { id: "eyeR", alpha: s.calloutEye * (1 - m) },
        { id: "mouth", alpha: s.calloutMouth * (1 - m) },
      ]
      // At most two anchored explanations (one in the small manual-mode scene box).
      const max = c.mode === "manual" ? 1 : 2
      for (const a of [...auto].reverse()) if (a.alpha > 0.01 && shown.length < max && !shown.some((x) => x.id === a.id)) shown.push(a)
    }
    const placed: Rect[] = []
    // Keep labels out of the text column, below the navigation and clear of the report preview.
    const reportReserve = c.mode === "scroll" && s.report > 0.05 ? Math.min(340, this.width * 0.27) + 56 : 0
    const bounds = {
      left: c.mode === "manual" ? 8 : Math.max(8, c.textRight + 12),
      top: (c.mode === "manual" ? 0 : c.navHeight) + 8,
      right: this.width - 8 - reportReserve,
      bottom: this.height - (c.mode === "manual" ? 8 : 48),
    }
    const head = mesh && (shown.length || c.selected || s.frame > 0.001) ? this.headRect() : null
    const order = shown
      .map((entry) => ({ entry, anchor: this.project(entry.id) }))
      .sort((a, b) => a.anchor.y - b.anchor.y)
    for (const id of REGIONS) {
      const el = labels[id]
      if (!el) continue
      const item = order.find((o) => o.entry.id === id)
      if (!item || !item.anchor.facing || !head) {
        if (el.dataset.shown !== "0") {
          el.style.opacity = "0"
          el.dataset.shown = "0"
        }
      }
    }
    for (const { entry, anchor } of order) {
      const el = labels[entry.id]
      if (!el || !anchor.facing || !head) continue
      placed.push(this.place(el, anchor, LABEL_SIDE[entry.id], head, bounds, placed))
      el.dataset.shown = "1"
      el.style.opacity = entry.alpha.toFixed(3)
    }

    // The selected explanation is anchored on large screens; on small ones it sits under the scene.
    const card = c.dom.card
    if (card && c.mode === "scroll" && c.selected && head) {
      const anchor = this.project(c.selected)
      this.place(card, anchor, LABEL_SIDE[c.selected], head, bounds, [])
      card.dataset.anchored = anchor.facing ? "1" : "0"
    }

    // Hand-off: frame the head as a sample.
    const frame = c.dom.frame
    if (frame) {
      if (s.frame > 0.001 && head) {
        const pad = 28
        frame.style.transform = `translate(${Math.round(head.x - pad)}px, ${Math.round(head.y - pad)}px)`
        frame.style.width = `${Math.round(head.w + pad * 2)}px`
        frame.style.height = `${Math.round(head.h + pad * 2)}px`
        frame.style.opacity = s.frame.toFixed(3)
        frame.dataset.placed = "1"
      } else if (frame.dataset.placed === "1") {
        frame.style.opacity = "0"
        frame.dataset.placed = "0"
      }
    }
  }

  /** The head's bounding box on screen (crown, chin, ears, nose, back of the head). */
  private headRect(): Rect {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
    for (const p of FRAME_POINTS) {
      const q = this.toScreen(this.tmp.copy(p))
      x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y)
    }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
  }

  private toScreen(local: THREE.Vector3) {
    this.mesh!.localToWorld(local)
    local.project(this.camera)
    return { x: (local.x * 0.5 + 0.5) * this.width, y: (-local.y * 0.5 + 0.5) * this.height }
  }

  private project(id: RegionId) {
    const a = REGION_ANCHORS[id]
    const mesh = this.mesh!
    const world = this.tmp.set(a.p[0], a.p[1], a.p[2])
    mesh.localToWorld(world)
    const n = this.tmpN.set(a.n[0], a.n[1], a.n[2]).transformDirection(mesh.matrixWorld)
    this.camPos.copy(this.camera.position).sub(world).normalize()
    const facing = n.dot(this.camPos) > 0.2
    world.project(this.camera)
    const x = (world.x * 0.5 + 0.5) * this.width
    const y = (-world.y * 0.5 + 0.5) * this.height
    const inView = x > 0 && x < this.width && y > 0 && y < this.height
    return { x, y, facing: facing && inView }
  }

  /**
   * Positions a label: the anchor dot sits on the region, the box just outside the head's silhouette
   * (preferred side first, then the other side), clear of the text column, the bounds and labels
   * already placed. A leader line joins them.
   */
  private place(el: HTMLElement, anchor: { x: number; y: number }, prefer: "left" | "right", head: Rect,
    b: { left: number; top: number; right: number; bottom: number }, placed: Rect[]): Rect {
    let size = this.labelSizes.get(el)
    const box = el.querySelector<HTMLElement>("[data-box]")
    if (!size || size.w === 0) {
      size = { w: box?.offsetWidth ?? 160, h: box?.offsetHeight ?? 40 }
      if (size.w > 0) this.labelSizes.set(el, size)
    }
    const { w, h } = size
    const clampY = (y: number) => Math.min(Math.max(y, b.top), b.bottom - h)
    const y = clampY(anchor.y - h / 2)
    const sides = prefer === "left" ? ["left", "right"] as const : ["right", "left"] as const
    const candidates = sides.map((side) => ({ side, x: side === "right" ? head.x + head.w + 20 : head.x - 20 - w, y }))
    const fitsX = (x: number) => x >= b.left && x + w <= b.right
    let pick = candidates.find((k) => fitsX(k.x))
    if (!pick) {
      // No room beside the head: as far right as the bounds allow (covering as little face as possible).
      const x = Math.max(b.left, b.right - w)
      pick = { side: "right", x, y: clampY(anchor.y + 28) }
    }
    // Stack below labels already placed when they would overlap.
    for (const p of placed) {
      if (pick.x < p.x + p.w + 8 && pick.x + w + 8 > p.x && pick.y < p.y + p.h + 8 && pick.y + h + 8 > p.y) {
        pick = { ...pick, y: clampY(p.y + p.h + 10) }
      }
    }
    const boxX = Math.round(pick.x - anchor.x)
    const boxY = Math.round(pick.y - anchor.y)
    el.style.transform = `translate(${Math.round(anchor.x)}px, ${Math.round(anchor.y)}px)`
    el.dataset.side = pick.side
    if (box) box.style.transform = `translate(${boxX}px, ${boxY}px)`
    // Leader line from the anchor to the nearest point of the box.
    const lx = Math.min(Math.max(0, boxX), boxX + w)
    const ly = Math.min(Math.max(0, boxY), boxY + h)
    const leader = el.querySelector<HTMLElement>("[data-leader]")
    if (leader) {
      const len = Math.hypot(lx, ly)
      leader.style.width = `${Math.max(0, len - 2)}px`
      leader.style.transform = `rotate(${Math.atan2(ly, lx)}rad)`
    }
    return { x: pick.x, y: pick.y, w, h }
  }

  /** The facial region under a stage pixel (raycast against the head), for hover and click. */
  pick(x: number, y: number): RegionId | null {
    if (!this.mesh) return null
    const ndc = new THREE.Vector2((x / this.width) * 2 - 1, -(y / this.height) * 2 + 1)
    this.raycaster.setFromCamera(ndc, this.camera)
    const hit = this.raycaster.intersectObject(this.mesh, false)[0]
    if (!hit) return null
    const local = this.mesh.worldToLocal(hit.point.clone())
    return regionAt(local.x, local.y, local.z)
  }

  dispose() {
    this.disposed = true
    this.ready = false
    this.landmarks.dispose()
    this.field.dispose()
    for (const d of this.disposables) d.dispose()
    this.disposables = []
    this.scene.clear()
    this.mesh = null
  }
}

function clampUnit(v: number) {
  return v < -1 ? -1 : v > 1 ? 1 : v
}

"use client"

import { Canvas, useFrame, useThree } from "@react-three/fiber"
import { useEffect, useRef } from "react"

import type { ScanController } from "./controller"
import { FaceStage, type Tier } from "./face-stage"

export type SceneStatus = "loading" | "ready" | "error"

type Props = { controllerRef: { readonly current: ScanController }; tier: Tier; onStatus: (s: SceneStatus) => void }

/** Wires the FaceStage to React Three Fiber: one canvas, one render loop (this useFrame), demand rendering. */
function Driver({ controllerRef, tier, onStatus }: Props) {
  const gl = useThree((s) => s.gl)
  const size = useThree((s) => s.size)
  const invalidate = useThree((s) => s.invalidate)
  const stageRef = useRef<FaceStage | null>(null)

  useEffect(() => {
    const controller = controllerRef.current
    const stage = new FaceStage(controller, tier)
    stageRef.current = stage
    stage.resize(gl.domElement.clientWidth, gl.domElement.clientHeight)
    controller.invalidate = () => {
      if (controller.visible) invalidate()
    }
    controller.pick = (x, y) => stage.pick(x, y)
    let alive = true
    stage.load().then(
      () => {
        if (!alive) return
        onStatus("ready")
        invalidate()
      },
      (error: unknown) => {
        if (!alive) return
        console.warn("[scan] 3D head unavailable, showing the poster instead:", error)
        onStatus("error")
      },
    )
    // Context loss (GPU reset, too many contexts): fall back to the poster.
    const canvas = gl.domElement
    const onLost = (e: Event) => {
      e.preventDefault()
      onStatus("error")
    }
    canvas.addEventListener("webglcontextlost", onLost)
    invalidate()
    return () => {
      alive = false
      canvas.removeEventListener("webglcontextlost", onLost)
      controller.invalidate = () => {}
      controller.pick = () => null
      stage.dispose()
      stageRef.current = null
    }
  }, [controllerRef, tier, gl, invalidate, onStatus])

  useEffect(() => {
    stageRef.current?.resize(size.width, size.height)
    invalidate()
  }, [size.width, size.height, invalidate])

  // Priority 1: this callback owns rendering (R3F does not render on its own when one exists).
  useFrame((state, delta) => {
    const stage = stageRef.current
    if (!stage) return
    const more = stage.frame(state.gl, Math.min(delta, 1 / 20), state.viewport.dpr)
    if (more && controllerRef.current.visible) state.invalidate()
  }, 1)

  return null
}

export default function FaceCanvas({ controllerRef, tier, onStatus }: Props) {
  return (
    <Canvas
      frameloop="demand"
      flat
      dpr={[1, tier === "full" ? 1.5 : 1]}
      gl={{ antialias: tier === "full", alpha: true, powerPreference: tier === "full" ? "high-performance" : "low-power", stencil: false }}
      camera={{ fov: 30, position: [0, 0, 24] }}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      onCreated={({ gl }) => gl.setClearColor(0x000000, 0)}
    >
      <Driver controllerRef={controllerRef} tier={tier} onStatus={onStatus} />
    </Canvas>
  )
}

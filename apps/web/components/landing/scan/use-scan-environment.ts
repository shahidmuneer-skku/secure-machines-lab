"use client"

import { useSyncExternalStore } from "react"

import type { ScanMode } from "./controller"
import type { Tier } from "./face-stage"

const SCROLL_QUERY = "(min-width: 768px) and (prefers-reduced-motion: no-preference)"
const REDUCED_QUERY = "(prefers-reduced-motion: reduce)"
const SMALL_QUERY = "(max-width: 767.98px)"
const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)"

function subscribeMedia(onChange: () => void) {
  const lists = [SCROLL_QUERY, REDUCED_QUERY, SMALL_QUERY, FINE_POINTER_QUERY].map((q) => window.matchMedia(q))
  lists.forEach((l) => l.addEventListener("change", onChange))
  return () => lists.forEach((l) => l.removeEventListener("change", onChange))
}

const noop = () => () => {}

let webglSupport: boolean | null = null
/** WebGL2 available (checked once; the context is released immediately). */
function hasWebGL(): boolean {
  if (webglSupport !== null) return webglSupport
  try {
    const canvas = document.createElement("canvas")
    const gl = canvas.getContext("webgl2", { failIfMajorPerformanceCaveat: false })
    webglSupport = !!gl
    gl?.getExtension("WEBGL_lose_context")?.loseContext()
  } catch {
    webglSupport = false
  }
  return webglSupport
}

/** Lightweight tier for small screens and constrained devices (fewer triangles, DPR 1, smaller field). */
function readTier(): Tier {
  const nav = navigator as Navigator & { deviceMemory?: number; connection?: { saveData?: boolean } }
  const small = window.matchMedia(SMALL_QUERY).matches
  const weak = (nav.hardwareConcurrency ?? 8) <= 4 || (nav.deviceMemory ?? 8) <= 4 || nav.connection?.saveData === true
  return small || weak ? "lite" : "full"
}

/**
 * Where and how the scan hero runs. The server snapshot assumes the desktop scroll mode; CSS media
 * queries already lay out small screens correctly before hydration, so nothing jumps.
 */
export function useScanEnvironment() {
  const mode = useSyncExternalStore<ScanMode>(subscribeMedia,
    () => (window.matchMedia(SCROLL_QUERY).matches ? "scroll" : "manual"), () => "scroll")
  const reducedMotion = useSyncExternalStore(subscribeMedia, () => window.matchMedia(REDUCED_QUERY).matches, () => false)
  const finePointer = useSyncExternalStore(subscribeMedia, () => window.matchMedia(FINE_POINTER_QUERY).matches, () => true)
  const tier = useSyncExternalStore<Tier>(subscribeMedia, readTier, () => "full")
  const webgl = useSyncExternalStore(noop, hasWebGL, () => true)
  const hydrated = useSyncExternalStore(noop, () => true, () => false)
  return { mode, reducedMotion, finePointer, tier, webgl, hydrated }
}

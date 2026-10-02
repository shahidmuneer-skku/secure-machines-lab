"use client"

import dynamic from "next/dynamic"
import { useTheme } from "next-themes"

import { useHydrated } from "@/hooks/use-hydrated"
import { DEFAULT_THEME } from "@/lib/theme/palette"

/** ApexCharts (the Modernize template's charts), client-only. */
export const Chart = dynamic(() => import("react-apexcharts"), { ssr: false })

// Validated categorical palettes (dataviz validate_palette, all checks pass): light on #fff, dark on
// the dark card #2a3447. Same values as the --chart-*/--viz-* tokens in globals.css.
const LIGHT = { blue: "#4c74f0", coral: "#e0603f", teal: "#0e9f85", amber: "#c2860a", violet: "#7d5bd6",
  text: "#5a6a85", grid: "#e5eaef", surface: "#ffffff" }
const DARK = { blue: "#5f86f5", coral: "#e46a49", teal: "#12a58a", amber: "#b8820c", violet: "#8b70e6",
  text: "#9aa9c2", grid: "rgba(255,255,255,0.07)", surface: "#2a3447" }

/** Chart colours for the current theme, plus the verdict mapping (fake coral, real teal, other violet). */
export function useChartColors() {
  const { resolvedTheme } = useTheme()
  const hydrated = useHydrated()
  const dark = hydrated ? resolvedTheme === "dark" : DEFAULT_THEME === "dark"
  const c = dark ? DARK : LIGHT
  return { ...c, dark, categorical: [c.blue, c.coral, c.teal, c.amber, c.violet],
    verdict: { fake: c.coral, real: c.teal, other: c.violet } }
}

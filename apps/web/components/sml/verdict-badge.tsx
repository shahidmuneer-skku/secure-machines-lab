"use client"

import { AlertTriangle, CircleHelp, ScanFace, ShieldCheck } from "lucide-react"
import { useTranslations } from "next-intl"

import { cn } from "@/lib/utils"

const STYLE = {
  fake: { icon: AlertTriangle, cls: "border-fake/40 bg-fake/10 text-fake" },
  real: { icon: ShieldCheck, cls: "border-real/40 bg-real/10 text-real" },
  no_face: { icon: ScanFace, cls: "border-warn/40 bg-warn/10 text-warn" },
  inconclusive: { icon: CircleHelp, cls: "border-border bg-muted text-muted-foreground" },
} as const

/** Plain-language verdict with icon + text (WCAG: not color alone). */
export function VerdictBadge({ verdict, probability, size = "md", className }: {
  verdict?: string | null
  probability?: number | null
  size?: "sm" | "md" | "lg"
  className?: string
}) {
  const t = useTranslations("verdict")
  const key = (verdict && verdict in STYLE ? verdict : "inconclusive") as keyof typeof STYLE
  const { icon: Icon, cls } = STYLE[key]
  const pct = probability != null ? ` · ${(probability * 100).toFixed(1)}%` : ""
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-medium",
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-2.5 py-1 text-sm",
        size === "lg" && "px-3 py-1.5 text-base",
        cls,
        className,
      )}
    >
      <Icon className={size === "lg" ? "size-5" : "size-4"} aria-hidden />
      {t(key)}
      {key !== "no_face" && key !== "inconclusive" && pct}
    </span>
  )
}

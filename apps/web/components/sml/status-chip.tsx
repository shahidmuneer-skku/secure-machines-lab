"use client"

import { useTranslations } from "next-intl"

import { cn } from "@/lib/utils"

const TONE: Record<string, string> = {
  queued: "text-violet",
  pending: "text-violet",
  dispatched: "text-violet",
  running: "text-primary",
  succeeded: "text-real",
  failed: "text-fake",
  canceled: "text-muted-foreground",
  skipped: "text-muted-foreground",
  expired: "text-muted-foreground",
}

/** Status pill with an LED dot. Always carries text (never color alone). */
export function StatusChip({ status, className }: { status: string; className?: string }) {
  const t = useTranslations("status")
  const active = status === "running" || status === "queued" || status === "dispatched"
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-2.5 py-0.5 mono-label",
        TONE[status] ?? "text-muted-foreground",
        className,
      )}
    >
      <span className="led-dot" data-pulse={active} aria-hidden />
      <span className="text-foreground/90">{t.has(status) ? t(status) : status}</span>
    </span>
  )
}

"use client"

import { Clock } from "lucide-react"
import { useTranslations } from "next-intl"

export function formatEta(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

export function QueuePill({ position, eta, workersOnline = true }: { position: number; eta: number;
  workersOnline?: boolean }) {
  const t = useTranslations("queue")
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-violet/10 px-2 py-0.5 text-xs text-violet">
      <Clock className="size-3.5" aria-hidden />
      {workersOnline ? t("position", { position, eta: formatEta(eta) }) : t("waitingForWorker", { position })}
    </span>
  )
}

"use client"

import { Ban, Check, Circle, Loader2, TriangleAlert } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { QueuePill } from "@/components/sml/queue-pill"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { JobDetail, JobStep, TimelineEvent } from "@/lib/api/types"
import { cn } from "@/lib/utils"

function StepIcon({ status }: { status: string }) {
  if (status === "done") return <Check className="size-4 text-real" aria-hidden />
  if (status === "running") return <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
  if (status === "failed" || status === "expired") return <TriangleAlert className="size-4 text-fake" aria-hidden />
  if (status === "canceled") return <Ban className="size-4 text-muted-foreground" aria-hidden />
  return <Circle className="size-4 text-muted-foreground/60" aria-hidden />
}

/**
 * What is happening behind the scenes, in generic steps: queued → checks → analysis (→ verification)
 * → results. Users see progress and their place in the queue, never which detectors run.
 */
export function ProcessingPanel({ job }: { job: JobDetail }) {
  const t = useTranslations("job")
  const steps = job.steps as JobStep[]
  const media = job.kind === "news" ? "attachments" : job.media_type || "other"
  return (
    <HudCard>
      <CardHeader>
        <Eyebrow index={2}>{t("processing.eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("processing.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3" aria-label={t("stages")}>
          {steps.map((step) => {
            const active = step.status === "running"
            return (
              <li key={step.id} aria-current={active ? "step" : undefined}
                className={cn("rounded-lg border p-3", active ? "border-primary/40 bg-primary/5" : "bg-background/40")}>
                <div className="flex items-center gap-3">
                  <StepIcon status={step.status} />
                  <span className={cn("flex-1 text-sm", step.status === "pending" ? "text-muted-foreground" : "font-medium")}>
                    {t(`step.${step.id}`, { media })}
                  </span>
                  <span className="mono-label text-muted-foreground">{t(`stepStatus.${step.status}`)}</span>
                </div>
                {step.id === "queued" && active && job.queue && (
                  <div className="mt-2 pl-7"><QueuePill position={job.queue.position} eta={job.queue.eta_seconds}
                    workersOnline={job.queue.workers_online} /></div>
                )}
                {(step.id === "analysis" || step.id === "verification") && active && (
                  <div className="mt-2 flex items-center gap-2 pl-7">
                    <Progress value={step.progress} className="h-1.5" aria-label={t(`step.${step.id}`, { media })} />
                    <span className="w-10 font-mono text-xs tabular-nums text-muted-foreground">{Math.round(step.progress)}%</span>
                  </div>
                )}
              </li>
            )
          })}
        </ol>
      </CardContent>
    </HudCard>
  )
}

const LEVEL_DOT: Record<string, string> = {
  info: "text-muted-foreground", success: "text-real", warning: "text-warn", error: "text-fake",
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const t = useTranslations("job")
  const locale = useLocale()
  return (
    <HudCard>
      <CardHeader>
        <Eyebrow index={5}>{t("timeline.eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("timeline.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-3 border-l border-border pl-5">
          {events.map((e) => (
            <li key={e.id} className="relative">
              <span className={cn("led-dot absolute -left-[25px] top-1.5", LEVEL_DOT[e.level])} aria-hidden />
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm">{e.message}</span>
                <time className="font-mono text-xs text-muted-foreground" dateTime={e.created_at}>
                  {new Intl.DateTimeFormat(locale, { timeStyle: "medium" }).format(new Date(e.created_at))}
                </time>
              </div>
            </li>
          ))}
        </ol>
      </CardContent>
    </HudCard>
  )
}

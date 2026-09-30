"use client"

import { useQuery } from "@tanstack/react-query"
import { Check, ChevronDown, Cpu, Loader2, Terminal, TriangleAlert } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { QueuePill } from "@/components/sml/queue-pill"
import { StatusChip } from "@/components/sml/status-chip"
import { Badge } from "@/components/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Progress } from "@/components/ui/progress"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import type { TaskView, TimelineEvent } from "@/lib/api/types"
import { formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"

const STAGES = ["queued", "analyzing", "aggregating", "done"] as const

export function StageStepper({ stage, status }: { stage: string; status: string }) {
  const t = useTranslations("job")
  const current = status === "succeeded" || status === "failed" || status === "canceled" || status === "expired"
    ? 3 : Math.max(0, STAGES.indexOf(stage as (typeof STAGES)[number]))
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label={t("stages")}>
      {STAGES.map((s, i) => {
        const done = i < current || (i === 3 && current === 3)
        const active = i === current && current !== 3
        return (
          <li key={s} className="space-y-1.5" aria-current={active ? "step" : undefined}>
            <div className={cn("h-1 rounded-full bg-muted", done && "bg-primary", active && "bg-primary/60 animate-pulse")} />
            <div className={cn("flex items-center gap-1 mono-label", done || active ? "text-foreground" : "text-muted-foreground")}>
              {done ? <Check className="size-3" /> : active ? <Loader2 className="size-3 animate-spin" /> : null}
              {t(`stage.${s}`)}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function TaskLog({ jobId, taskId, running }: { jobId: string; taskId: string; running: boolean }) {
  const t = useTranslations("job")
  const { data: log } = useQuery({
    queryKey: qk.taskLog(jobId, taskId),
    queryFn: async () => data(await api.GET("/api/v1/jobs/{id}/tasks/{task_id}/log", {
      params: { path: { id: jobId, task_id: taskId } } })),
    refetchInterval: running ? 2000 : false,
  })
  const lines = log?.lines ?? []
  return (
    <div className="max-h-56 overflow-auto rounded-md border bg-black/40 p-3 font-mono text-xs leading-relaxed text-[#b8f5ff]"
      role="log" aria-live="polite" aria-label={t("liveLog")}>
      {lines.length ? lines.map((l, i) => (
        <div key={i} className="flex gap-3">
          <span className="shrink-0 text-muted-foreground">{new Date(l.at).toLocaleTimeString()}</span>
          <span className="break-all">{l.message}</span>
        </div>
      )) : <span className="text-muted-foreground">{running ? t("logWaiting") : t("logEmpty")}</span>}
    </div>
  )
}

function TaskRow({ jobId, task, live }: { jobId: string; task: TaskView;
  live?: { progress?: number; message?: string; lastLog?: string } }) {
  const t = useTranslations("job")
  const [open, setOpen] = useState(false)
  const running = task.status === "running"
  const progress = task.status === "succeeded" ? 100
    : running ? Math.max(task.live?.progress ?? 0, live?.progress ?? 0) : task.progress
  const message = live?.message || task.live?.message || task.stage_message
  const r = task.result ?? {}
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="rounded-lg border bg-background/40">
      <div className="flex flex-wrap items-center gap-3 p-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{task.name}</span>
            <span className="mono-label text-muted-foreground">{t(`taskKind.${task.kind}`)}</span>
            {r.simulated && <Badge variant="outline" className="border-warn/50 text-warn">{t("simulated")}</Badge>}
            {task.attempt > 1 && <Badge variant="outline">{t("attempt", { n: task.attempt })}</Badge>}
            {r.fallback && <Badge variant="outline" className="border-violet/50 text-violet">{t("fallbackUsed", { model: r.fallback.model })}</Badge>}
          </div>
          {(running || task.status === "succeeded") && (
            <div className="flex items-center gap-2">
              <Progress value={progress} className="h-1.5" aria-label={t("taskProgress", { name: task.name })} />
              <span className="w-10 font-mono text-xs tabular-nums text-muted-foreground">{Math.round(progress)}%</span>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {task.queue_info && <QueuePill position={task.queue_info.position} eta={task.queue_info.eta_seconds}
              workersOnline={task.queue_info.workers_online} />}
            {running && message && <span className="truncate">{message}</span>}
            {task.gpu && <span className="inline-flex items-center gap-1"><Cpu className="size-3" /> GPU {task.gpu}</span>}
            {task.duration_ms != null && <span>{formatDuration(task.duration_ms / 1000)}</span>}
            {task.status === "succeeded" && r.fake_prob != null && (
              <span className="font-mono tabular-nums text-foreground">{t("scoreFake", { pct: (r.fake_prob * 100).toFixed(1) })}</span>
            )}
            {r.no_face && <span className="text-warn">{t("noFace")}</span>}
            {r.summary && <span>{r.summary}</span>}
            {task.status === "failed" && (
              <span className="inline-flex items-center gap-1 text-fake"><TriangleAlert className="size-3" />
                {t.has(`taskError.${task.error_code}`) ? t(`taskError.${task.error_code}`) : task.error_message || task.error_code}</span>
            )}
          </div>
        </div>
        <StatusChip status={task.status} />
        <CollapsibleTrigger asChild>
          <button type="button" className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
            aria-label={t("toggleLog", { name: task.name })}>
            <Terminal className="size-3.5" /> {t("log")}
            <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
          </button>
        </CollapsibleTrigger>
      </div>
      <CollapsibleContent className="px-3 pb-3">
        {open && <TaskLog jobId={jobId} taskId={task.id} running={running} />}
      </CollapsibleContent>
    </Collapsible>
  )
}

export function ProcessingPanel({ jobId, tasks, stage, status }: { jobId: string; tasks: TaskView[]; stage: string;
  status: string }) {
  const t = useTranslations("job")
  const { data: live } = useQuery<Record<string, { progress?: number; message?: string }>>({
    queryKey: ["jobs", "live", jobId], queryFn: () => ({}), enabled: false, staleTime: Infinity })
  const models = tasks.filter((x) => x.kind !== "audit")
  const audits = tasks.filter((x) => x.kind === "audit")
  return (
    <HudCard>
      <CardHeader className="space-y-3">
        <div>
          <Eyebrow index={2}>{t("processing.eyebrow")}</Eyebrow>
          <CardTitle className="mt-1 text-base">{t("processing.title")}</CardTitle>
        </div>
        <StageStepper stage={stage} status={status} />
      </CardHeader>
      <CardContent className="space-y-4">
        <section className="space-y-2" aria-label={t("processing.models")}>
          <h3 className="hud-eyebrow">{t("processing.models")}</h3>
          {models.map((task) => <TaskRow key={task.id} jobId={jobId} task={task} live={live?.[task.id]} />)}
        </section>
        {audits.length > 0 && (
          <section className="space-y-2" aria-label={t("processing.audit")}>
            <h3 className="hud-eyebrow">{t("processing.audit")}</h3>
            {audits.map((task) => <TaskRow key={task.id} jobId={jobId} task={task} live={live?.[task.id]} />)}
          </section>
        )}
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

"use client"

import { useQuery } from "@tanstack/react-query"
import { Film, ImageIcon, Newspaper, Timer } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"

import { QueuePill } from "@/components/sml/queue-pill"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Progress } from "@/components/ui/progress"
import type { Job } from "@/lib/api/types"
import { formatRelative } from "@/lib/format"
import { cn } from "@/lib/utils"

import { JobActions } from "./job-actions"

type LiveMap = Record<string, { progress?: number; message?: string }>

/** Live progress from SSE (per task) merged with the persisted job progress. */
export function useLiveJobProgress(job: Pick<Job, "id" | "progress" | "status">) {
  const { data: live } = useQuery<LiveMap>({ queryKey: ["jobs", "live", job.id], queryFn: () => ({}), enabled: false,
    staleTime: Infinity })
  const values = Object.values(live ?? {})
  const message = values.map((v) => v.message).filter(Boolean).at(-1)
  if (job.status !== "running" || !values.length) return { progress: job.progress, message }
  const livePct = values.reduce((a, v) => a + (v.progress ?? 0), 0) / values.length
  return { progress: Math.max(job.progress, Math.min(99, livePct)), message }
}

function KindIcon({ job }: { job: Job }) {
  if (job.kind === "news") return <Newspaper className="size-5 text-muted-foreground" />
  return job.media_type === "video" ? <Film className="size-5 text-muted-foreground" /> : <ImageIcon className="size-5 text-muted-foreground" />
}

export function JobRow({ job, compact = false, selected, onSelect }: {
  job: Job
  compact?: boolean
  selected?: boolean
  onSelect?: (on: boolean) => void
}) {
  const t = useTranslations("results")
  const locale = useLocale()
  const { progress, message } = useLiveJobProgress(job)
  const models = job.models.map((m) => m.name)
  return (
    <div className={cn("group relative flex items-center gap-3 rounded-lg border bg-background/40 p-3 transition-colors hover:bg-accent/40",
      selected && "border-primary/60")}>
      {onSelect && (
        <Checkbox checked={selected} onCheckedChange={(v) => onSelect(v === true)} aria-label={t("select", { name: job.title })}
          className="relative z-10" />
      )}
      <div className="flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
        {job.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={job.thumbnail_url} alt="" className="size-full object-cover" loading="lazy" />
        ) : <KindIcon job={job} />}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={job.kind === "news" ? `/app/news/${job.id}` : `/app/results/${job.id}`}
            className="truncate font-medium after:absolute after:inset-0 hover:underline">
            {job.title || t("untitled")}
          </Link>
          <span className="mono-label text-muted-foreground">{t(`kind.${job.kind}`)}</span>
          {job.source !== "web" && <span className="mono-label text-violet">{t(`source.${job.source}`)}</span>}
        </div>
        {!compact && (
          <p className="truncate text-xs text-muted-foreground">
            {models.slice(0, 4).join(" · ")}{models.length > 4 ? ` · +${models.length - 4}` : ""}
          </p>
        )}
        {job.status === "running" && (
          <div className="flex items-center gap-2">
            <Progress value={progress} className="h-1.5 max-w-64" aria-label={t("progress")} />
            <span className="font-mono text-xs tabular-nums text-muted-foreground">{Math.round(progress)}%</span>
            {message && !compact && <span className="truncate text-xs text-muted-foreground">{message}</span>}
          </div>
        )}
        {job.status === "queued" && job.queue && (
          <QueuePill position={job.queue.position} eta={job.queue.eta_seconds} workersOnline={job.queue.workers_online} />
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <div className="flex items-center gap-2">
          {job.status === "succeeded" ? (
            <VerdictBadge verdict={job.verdict} probability={job.fake_probability} size="sm" />
          ) : (
            <StatusChip status={job.status} />
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span title={job.created_at}>{formatRelative(job.created_at, locale)}</span>
          {job.credits_charged > 0 && <span className="tabular-nums">· {t("credits", { count: job.credits_charged })}</span>}
          {job.expires_at && job.status !== "expired" && !compact && (
            <span className="hidden items-center gap-1 md:inline-flex"><Timer className="size-3" />
              {t("expires", { when: formatRelative(job.expires_at, locale) })}</span>
          )}
        </div>
      </div>
      {!compact && <div className="relative z-10"><JobActions job={job} /></div>}
    </div>
  )
}

"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Ban, Clock, Coins, RotateCw, Timer } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { StatusChip } from "@/components/sml/status-chip"
import { Button } from "@/components/ui/button"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { JobDetail as JobDetailT } from "@/lib/api/types"
import { formatDateTime, formatRelative } from "@/lib/format"

import { ExplainCard, ReportsCard } from "./explain-reports"
import { JobActions, useJobMutations } from "./job-actions"
import { MediaViewer } from "./media-viewer"
import { ProcessingPanel, Timeline } from "./processing-panel"
import { ProvenanceCard, VerdictPanel } from "./verdict-panel"

export function useJob(id: string) {
  return useQuery({
    queryKey: qk.job(id),
    queryFn: async () => data(await api.GET("/api/v1/jobs/{id}", { params: { path: { id } } })),
    // SSE invalidates on every event; polling is only the fallback for active jobs.
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 5000 : false),
  })
}

export function JobDetailView({ id }: { id: string }) {
  const t = useTranslations("job")
  const locale = useLocale()
  const router = useRouter()
  const { data: job, isLoading, error, refetch } = useJob(id)
  const { cancel, rerun } = useJobMutations(id)

  if (isLoading) {
    return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><div className="grid gap-4 lg:grid-cols-3">
      <Skeleton className="h-96 lg:col-span-2" /><Skeleton className="h-96" /></div></div>
  }
  if (error || !job) {
    const missing = isApiError(error) && error.status === 404
    return (
      <Empty><EmptyHeader><EmptyTitle>{missing ? t("notFound") : t("loadError")}</EmptyTitle></EmptyHeader>
        <EmptyContent className="flex-row justify-center gap-2">
          {!missing && <Button onClick={() => refetch()}>{t("retry")}</Button>}
          <Button asChild variant="outline"><Link href="/app/results">{t("backToResults")}</Link></Button>
        </EmptyContent></Empty>
    )
  }
  const active = job.status === "queued" || job.status === "running"
  const finished = ["succeeded", "failed", "canceled"].includes(job.status)
  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-2">
          <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
            <Link href="/app/results"><ArrowLeft className="size-4" /> {t("backToResults")}</Link>
          </Button>
          <Eyebrow>{t("eyebrow", { kind: t(`kind.${job.kind}`), run: job.run_number })}</Eyebrow>
          <h1 className="break-all text-2xl font-semibold tracking-tight">{job.title}</h1>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <StatusChip status={job.status} />
            <span className="inline-flex items-center gap-1"><Clock className="size-3" /> {formatDateTime(job.created_at, locale)}</span>
            <span className="inline-flex items-center gap-1"><Coins className="size-3" />
              {job.status === "succeeded" ? t("charged", { count: job.credits_charged })
                : active ? t("reserved", { count: job.credits_quoted }) : t("notCharged")}</span>
            {job.expires_at && job.status !== "expired" && (
              <span className="inline-flex items-center gap-1"><Timer className="size-3" /> {t("expires", { when: formatRelative(job.expires_at, locale) })}</span>
            )}
            <span className="font-mono">{job.id}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {active && <Button variant="outline" onClick={() => cancel.mutate()} disabled={cancel.isPending}><Ban className="size-4" /> {t("cancel")}</Button>}
          {finished && job.kind !== "news" && (
            <Button variant="outline" onClick={() => rerun.mutate()} disabled={rerun.isPending}><RotateCw className="size-4" /> {t("rerun")}</Button>
          )}
          <JobActions job={job} onDeleted={() => router.push("/app/results")} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <MediaViewer job={job} />
          <ProcessingPanel job={job} />
          <ExplainCard job={job} />
        </div>
        <div className="space-y-5">
          <VerdictPanel job={job} />
          <ProvenanceCard job={job} />
          <ReportsCard job={job} />
          <CreditsCard job={job} />
          <Timeline events={job.events} />
        </div>
      </div>
    </div>
  )
}

function CreditsCard({ job }: { job: JobDetailT }) {
  const t = useTranslations("job.creditsCard")
  const lines = job.quote_lines as { label: string; credits: number }[]
  return (
    <HudCard>
      <CardHeader><Eyebrow index={8}>{t("eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("title")}</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        {lines.map((l, i) => (
          <div key={i} className="flex justify-between"><span className="text-muted-foreground">{l.label}</span>
            <span className="font-mono tabular-nums">{l.credits}</span></div>
        ))}
        <div className="flex justify-between border-t pt-2 font-medium">
          <span>{job.status === "succeeded" ? t("charged") : ["failed", "canceled", "expired"].includes(job.status) ? t("refunded") : t("reserved")}</span>
          <span className="font-mono tabular-nums">{job.status === "succeeded" ? job.credits_charged : job.credits_quoted}</span>
        </div>
        {job.source === "trial" && <p className="text-xs text-muted-foreground">{t("trial")}</p>}
      </CardContent>
    </HudCard>
  )
}

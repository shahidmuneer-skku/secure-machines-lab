"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lock } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Badge } from "@/components/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useCan } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import type {
  AdminJobDetector, AdminJobDetectors, DetectorAccuracy, DetectorBenchmark, JobDetail, JobTruth,
} from "@/lib/api/types"
import { formatDuration, formatPercent, formatTimestamp } from "@/lib/format"

const ANALYSES = ["face_swap", "ai_generated"] as const
const COLOR = { face_swap: "var(--viz-analysis-face-swap)", ai_generated: "var(--viz-analysis-ai-generated)" }
const TRUTHS: JobTruth[] = ["authentic", "face_swap", "ai_generated"]

/**
 * Administrators only: what each detector said about this file, its weight, its benchmark figures
 * and its accuracy measured on labelled files. Users never get this card or its endpoint (ADR 0011).
 */
export function DetectorBreakdown({ job }: { job: JobDetail }) {
  const canView = useCan("view_all_jobs")
  if (!canView || job.kind !== "detect") return null
  return <BreakdownCard job={job} />
}

function BreakdownCard({ job }: { job: JobDetail }) {
  const t = useTranslations("job.detectors")
  const active = job.status === "queued" || job.status === "running"
  const { data: info, isLoading } = useQuery({
    // The status in the key refetches once more when the job finishes (polling stops then).
    queryKey: qk.admin("job", job.id, "detectors", job.status),
    queryFn: async () => data(await api.GET("/api/v1/admin/jobs/{id}/detectors", { params: { path: { id: job.id } } })),
    refetchInterval: active ? 5000 : false,
  })
  return (
    <HudCard>
      <CardHeader>
        <Eyebrow><Lock className="inline size-3" /> {t("eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("title")}</CardTitle>
        <p className="text-xs text-muted-foreground">{t("hint")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading || !info ? <Skeleton className="h-40" /> : (
          <>
            <TruthControl jobId={job.id} truth={info.truth.truth ?? null} by={info.truth.labeled_by ?? null} />
            {ANALYSES.map((analysis) => {
              const rows = info.detectors.filter((d) => d.analysis === analysis)
              const exief = analysis === "ai_generated" ? info.exief : null
              if (!rows.length && !exief) return null
              return (
                <section key={analysis} className="space-y-2" aria-labelledby={`detectors-${analysis}`}>
                  <h3 id={`detectors-${analysis}`} className="hud-eyebrow">{t(`analysis.${analysis}`)}</h3>
                  <ul className="space-y-2">
                    {rows.map((d) => (
                      <DetectorRow key={d.task_id} d={d} threshold={info.threshold} duration={info.duration_seconds ?? null} />
                    ))}
                    {exief && <ExiefRow exief={exief} />}
                  </ul>
                </section>
              )
            })}
            {!info.detectors.length && <p className="text-sm text-muted-foreground">{t("none")}</p>}
          </>
        )}
      </CardContent>
    </HudCard>
  )
}

function TruthControl({ jobId, truth, by }: { jobId: string; truth: JobTruth | null; by: string | null }) {
  const t = useTranslations("job.detectors.truth")
  const canLabel = useCan("manage_models")
  const qc = useQueryClient()
  const save = useMutation({
    mutationFn: async (value: JobTruth | null) =>
      data(await api.PUT("/api/v1/admin/jobs/{id}/truth", { params: { path: { id: jobId } }, body: { truth: value } })),
    onSuccess: () => {
      toast.success(t("saved"))
      qc.invalidateQueries({ queryKey: ["admin"] })
    },
    onError: () => toast.error(t("failed")),
  })
  return (
    <div className="space-y-1.5 rounded-lg border bg-background/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={`truth-${jobId}`} className="text-sm font-medium">{t("label")}</label>
        <Select value={truth ?? "none"} disabled={!canLabel || save.isPending}
          onValueChange={(v) => save.mutate(v === "none" ? null : (v as JobTruth))}>
          <SelectTrigger id={`truth-${jobId}`} className="h-8 w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">{t("none")}</SelectItem>
            {TRUTHS.map((v) => <SelectItem key={v} value={v}>{t(`value.${v}`)}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <p className="text-xs text-muted-foreground">{truth && by ? t("by", { email: by }) : t("hint")}</p>
    </div>
  )
}

function DetectorRow({ d, threshold, duration }: { d: AdminJobDetector; threshold: number; duration: number | null }) {
  const t = useTranslations("job.detectors")
  const other = d.counted_in.filter((a) => a !== d.analysis)
  return (
    <li className="space-y-2 rounded-lg border bg-background/40 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="block truncate text-sm font-medium">{d.name}</span>
          <span className="block text-xs text-muted-foreground">
            {[d.weight != null ? t("weight", { weight: d.weight }) : null,
              d.duration_ms ? formatDuration(d.duration_ms / 1000) : null,
              d.gpu ? `GPU ${d.gpu}` : null,
              d.fallback_for ? t("fallback") : null].filter(Boolean).join(" · ")}
          </span>
        </div>
        {d.heatmap_url && <HeatmapThumb url={d.heatmap_url} name={d.name} />}
      </div>
      {d.status === "succeeded" && d.verdict ? (
        <>
          <VerdictBadge verdict={d.verdict} probability={d.fake_probability} size="sm" />
          {d.fake_probability != null && (
            <Progress value={d.fake_probability * 100} aria-label={t("probabilityOf", { name: d.name })}
              className={d.verdict === "fake" ? "h-1.5 [&>[data-slot=progress-indicator]]:bg-fake" : "h-1.5 [&>[data-slot=progress-indicator]]:bg-real"} />
          )}
        </>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip status={d.status} />
          {d.error_message && <span className="text-xs text-warn">{d.error_message}</span>}
        </div>
      )}
      {other.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {other.map((a) => <Badge key={a} variant="outline" className="text-[11px]">{t(`alsoCounts.${a}`)}</Badge>)}
        </div>
      )}
      {d.per_frame.length > 1 && <Sparkline points={d.per_frame} threshold={threshold} color={COLOR[d.analysis]}
        duration={duration} name={d.name} />}
      <Accuracy benchmark={d.benchmark ?? null} measured={d.measured ?? null} />
    </li>
  )
}

/** The EXIEF metadata scorer: what it found, and whether it counted in the AI-generation analysis. */
function ExiefRow({ exief }: { exief: NonNullable<AdminJobDetectors["exief"]> }) {
  const t = useTranslations("job.detectors.exief")
  return (
    <li className="space-y-2 rounded-lg border bg-background/40 p-3">
      <div className="min-w-0">
        <span className="block text-sm font-medium">{t("name")}</span>
        <span className="block text-xs text-muted-foreground">
          {[t("score", { score: exief.score ?? 0 }), exief.counted ? t("weight", { weight: exief.weight }) : null,
            exief.generator].filter(Boolean).join(" · ")}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className={exief.verdict === "unknown" ? "" : "border-fake/50 text-fake"}>{t(`verdict.${exief.verdict}`)}</Badge>
        <span className="text-xs text-muted-foreground">
          {exief.counted ? t("counted", { probability: formatPercent(exief.fake_probability) })
            : exief.untrustworthy.length ? t("notTrusted") : t("notCounted")}
        </span>
      </div>
      {exief.untrustworthy.length > 0 && (
        <ul className="space-y-0.5 text-xs text-warn">{exief.untrustworthy.map((r) => <li key={r}>{r}</li>)}</ul>
      )}
      {exief.signals.length > 0 && (
        <ul className="space-y-1 text-xs">
          {exief.signals.map((sig) => (
            <li key={sig.id}>
              <span className="font-medium">{sig.label}</span>
              <span className="text-muted-foreground"> · {t("signalWeight", { tier: sig.tier, weight: sig.weight ?? 0 })}</span>
              {sig.evidence.length > 0 && <span className="block break-all font-mono text-[10px] text-muted-foreground">{sig.evidence.join(" · ")}</span>}
            </li>
          ))}
        </ul>
      )}
      <Accuracy benchmark={null} measured={exief.measured ?? null} />
    </li>
  )
}

export function Accuracy({ benchmark, measured, compact = false }: {
  benchmark: DetectorBenchmark | null; measured: DetectorAccuracy | null; compact?: boolean
}) {
  const t = useTranslations("job.detectors.accuracy")
  const bench = benchmark && (benchmark.accuracy != null || benchmark.auc != null)
    ? [benchmark.accuracy != null ? t("acc", { value: formatPercent(benchmark.accuracy) }) : null,
       benchmark.auc != null ? t("auc", { value: benchmark.auc.toFixed(3) }) : null].filter(Boolean).join(" · ")
    : null
  return (
    <dl className={compact ? "space-y-0.5 text-xs" : "grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs"}>
      <dt className="text-muted-foreground">{t("benchmark")}</dt>
      <dd>{bench ? <>{bench}{benchmark?.dataset ? <span className="text-muted-foreground"> ({benchmark.dataset})</span> : null}</> : "—"}</dd>
      <dt className="text-muted-foreground">{t("measured")}</dt>
      <dd>{measured?.files ? (
        <>
          {[t("acc", { value: formatPercent(measured.accuracy) }),
            measured.auc != null ? t("auc", { value: measured.auc.toFixed(3) }) : null].filter(Boolean).join(" · ")}
          <span className="block text-muted-foreground">
            {t("detail", { files: measured.files, fake: measured.fake_files, authentic: measured.authentic_files,
              precision: formatPercent(measured.precision), recall: formatPercent(measured.recall) })}
          </span>
        </>
      ) : <span className="text-muted-foreground">{t("notMeasured")}</span>}</dd>
    </dl>
  )
}

function HeatmapThumb({ url, name }: { url: string; name: string }) {
  const t = useTranslations("job.detectors")
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button" className="shrink-0 overflow-hidden rounded-md border focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={t("heatmapOf", { name })}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="" className="size-12 object-cover" loading="lazy" />
        </button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogTitle>{t("heatmapOf", { name })}</DialogTitle>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt={t("heatmapOf", { name })} className="mx-auto max-h-[70vh] w-auto rounded-md border" />
      </DialogContent>
    </Dialog>
  )
}

/** One detector's per-frame fake probability (single series, so no legend), with the threshold dashed. */
function Sparkline({ points, threshold, color, duration, name }: {
  points: AdminJobDetector["per_frame"]; threshold: number; color: string; duration: number | null; name: string
}) {
  const t = useTranslations("job.detectors")
  const [hover, setHover] = useState<number | null>(null)
  const end = Math.max(duration ?? 0, points[points.length - 1].second) || 1
  const x = (s: number) => (s / end) * 100
  const y = (p: number) => 2 + (1 - p) * 24
  const line = points.map((p) => `${x(p.second).toFixed(2)},${y(p.fake_probability).toFixed(2)}`).join(" ")
  const shown = hover != null ? points[hover] : null
  return (
    <figure className="space-y-1">
      <figcaption className="flex justify-between text-[11px] text-muted-foreground">
        <span>{t("perFrame")}</span>
        <span className="tabular-nums">{shown ? `${formatTimestamp(shown.second)} · ${formatPercent(shown.fake_probability)}` : ""}</span>
      </figcaption>
      <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="h-8 w-full touch-none" role="img"
        aria-label={t("perFrameOf", { name })}
        onPointerMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect()
          const s = ((e.clientX - box.left) / box.width) * end
          let best = 0
          points.forEach((p, i) => { if (Math.abs(p.second - s) < Math.abs(points[best].second - s)) best = i })
          setHover(best)
        }}
        onPointerLeave={() => setHover(null)}>
        <line x1="0" x2="100" y1={y(threshold)} y2={y(threshold)} stroke="currentColor" strokeOpacity="0.35"
          strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
        <polyline points={line} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke"
          strokeLinejoin="round" strokeLinecap="round" />
        {shown && <line x1={x(shown.second)} x2={x(shown.second)} y1="0" y2="28" stroke="currentColor"
          strokeOpacity="0.5" vectorEffect="non-scaling-stroke" />}
      </svg>
    </figure>
  )
}

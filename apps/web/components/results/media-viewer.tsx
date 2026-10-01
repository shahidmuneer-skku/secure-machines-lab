"use client"

import { useQuery } from "@tanstack/react-query"
import { useTranslations } from "next-intl"
import { useMemo, useRef, useState } from "react"
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig,
} from "@/components/ui/chart"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { JobArtifact, JobDetail, TimelinePoint } from "@/lib/api/types"

export function MediaViewer({ job }: { job: JobDetail }) {
  const t = useTranslations("job")
  const xai = job.artifacts
    .filter((a: JobArtifact) => (a.kind === "heatmap" || a.kind === "face") && a.content_type.startsWith("image/"))
    .sort((a: JobArtifact, b: JobArtifact) => Number(a.kind === "face") - Number(b.kind === "face"))
  const [overlay, setOverlay] = useState<string>("none")
  const [opacity, setOpacity] = useState(60)
  const videoRef = useRef<HTMLVideoElement>(null)
  const current = xai.find((a: JobArtifact) => a.id === overlay)
  const mediaUrl = job.media?.content_url
  // Streamed long-form scans keep no video, only a preview frame (served as the thumbnail).
  const streamPreview = job.options?.stream ? job.thumbnail_url : null
  // Unlabelled evidence: "Heatmap 1, 2, …" (users are not told which detector produced which map).
  // Numbered only when the admin shows several (n = 0 renders "Heatmap").
  const label = (a: JobArtifact) => {
    const same = xai.filter((x) => x.kind === a.kind)
    return t(`media.artifact.${a.kind}`, { n: same.length > 1 ? same.indexOf(a) + 1 : 0 })
  }

  return (
    <HudCard>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <Eyebrow index={1}>{t("media.eyebrow")}</Eyebrow>
          <CardTitle className="mt-1 text-base break-all">{job.title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!mediaUrl && streamPreview ? (
          <figure className="space-y-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={streamPreview} alt={t("media.streamPreview")}
              className="mx-auto max-h-[360px] w-auto rounded-lg border object-contain" />
            <figcaption className="text-center text-xs text-muted-foreground">{t("media.streamNotStored")}</figcaption>
          </figure>
        ) : !mediaUrl ? (
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            {job.status === "expired" ? t("media.expired") : t("media.unavailable")}
          </div>
        ) : job.media_type === "image" ? (
          <div className="relative overflow-hidden rounded-lg border bg-black/40">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={mediaUrl} alt={t("media.original")} className="mx-auto max-h-[520px] w-auto object-contain" />
            {current && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={current.url} alt={t("media.overlayAlt", { label: label(current) })}
                className="absolute inset-0 mx-auto h-full max-h-[520px] w-auto object-contain mix-blend-normal"
                style={{ opacity: opacity / 100 }} />
            )}
          </div>
        ) : (
          <video ref={videoRef} src={mediaUrl} controls className="max-h-[520px] w-full rounded-lg border bg-black" preload="metadata" />
        )}

        {xai.length > 0 && job.media_type === "image" && (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="hud-eyebrow">{t("media.explainability")}</Label>
              <ToggleGroup type="single" value={overlay} onValueChange={(v) => setOverlay(v || "none")} variant="outline"
                size="sm" className="flex-wrap justify-start">
                <ToggleGroupItem value="none">{t("media.original")}</ToggleGroupItem>
                {xai.map((a: JobArtifact) => (
                  <ToggleGroupItem key={a.id} value={a.id}>{label(a)}</ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>
            {current && (
              <div className="flex items-center gap-3">
                <Label htmlFor="overlay-opacity" className="mono-label text-muted-foreground">{t("media.opacity")}</Label>
                <Slider id="overlay-opacity" value={[opacity]} onValueChange={([v]) => setOpacity(v)} max={100} step={5}
                  className="max-w-48" aria-label={t("media.opacity")} />
                <span className="font-mono text-xs tabular-nums">{opacity}%</span>
              </div>
            )}
          </div>
        )}
        {job.media_type === "video" && <VideoTimeline job={job} videoRef={videoRef} />}
        {xai.length > 0 && job.media_type === "video" && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {xai.slice(0, 6).map((a: JobArtifact) => (
              <figure key={a.id} className="space-y-1">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={a.url} alt={label(a)} className="aspect-square w-full rounded-md border object-cover" loading="lazy" />
                <figcaption className="truncate text-xs text-muted-foreground">{label(a)}</figcaption>
              </figure>
            ))}
          </div>
        )}
      </CardContent>
    </HudCard>
  )
}

const ANALYSES = ["face_swap", "ai_generated", "general"] as const
type AnalysisId = (typeof ANALYSES)[number]
const ANALYSIS_COLOR: Record<AnalysisId, string> = {
  face_swap: "var(--viz-analysis-face-swap)", ai_generated: "var(--viz-analysis-ai-generated)",
  general: "var(--viz-analysis-general)",
}
const formatClock = (v: number) => `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, "0")}`

/** Fake probability over time, one line per analysis (live intervals while a scan runs); click to seek. */
function VideoTimeline({ job, videoRef }: { job: JobDetail; videoRef: React.RefObject<HTMLVideoElement | null> }) {
  const t = useTranslations("job")
  const { data: liveIntervals } = useQuery<{ start_sec: number; fake_prob: number }[]>({
    queryKey: ["jobs", "intervals", job.id], queryFn: () => [], enabled: false, staleTime: Infinity })
  const { rows, present } = useMemo(() => {
    const points: TimelinePoint[] = job.timeline.length ? job.timeline
      : (liveIntervals ?? []).map((i) => ({ ...i, analysis: "general", end_sec: i.start_sec } as TimelinePoint))
    const byTime = new Map<number, Record<string, number>>()
    const seen = new Set<AnalysisId>()
    for (const p of points) {
      const row = byTime.get(p.start_sec) ?? { x: p.start_sec }
      row[p.analysis] = Math.round((p.fake_prob ?? 0) * 1000) / 10
      byTime.set(p.start_sec, row)
      seen.add(p.analysis as AnalysisId)
    }
    return { rows: [...byTime.values()].sort((a, b) => a.x - b.x), present: ANALYSES.filter((a) => seen.has(a)) }
  }, [job.timeline, liveIntervals])
  const config = Object.fromEntries(present.map((a) => [a, { label: t(`analysis.name.${a}`), color: ANALYSIS_COLOR[a] }])) satisfies ChartConfig
  if (!rows.length) return null
  return (
    <div className="space-y-1.5">
      <p className="hud-eyebrow">{t("media.timeline")}</p>
      <ChartContainer config={config} className="h-44 w-full">
        <LineChart data={rows} margin={{ left: -16, right: 8 }}
          onClick={(e) => { const x = Number(e?.activeLabel); if (videoRef.current && Number.isFinite(x)) videoRef.current.currentTime = x }}>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
          <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tickLine={false} axisLine={false} tickFormatter={formatClock} />
          <YAxis domain={[0, 100]} tickLine={false} axisLine={false} width={40} tickFormatter={(v) => `${v}%`} />
          <ReferenceLine y={50} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => formatClock(Number(p?.[0]?.payload?.x ?? 0))} />} />
          {present.length > 1 && <ChartLegend content={<ChartLegendContent />} />}
          {present.map((a) => (
            <Line key={a} dataKey={a} type="monotone" stroke={`var(--color-${a})`} strokeWidth={2} dot={false}
              activeDot={{ r: 4 }} connectNulls />
          ))}
        </LineChart>
      </ChartContainer>
      <p className="text-xs text-muted-foreground">{t("media.timelineHint")}</p>
    </div>
  )
}

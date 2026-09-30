"use client"

import { useQuery } from "@tanstack/react-query"
import { useTranslations } from "next-intl"
import { useMemo, useRef, useState } from "react"
import { Area, AreaChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from "recharts"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { JobDetail, TaskView } from "@/lib/api/types"

type Artifact = JobDetail["artifacts"][number]

export function MediaViewer({ job, tasks }: { job: JobDetail; tasks: TaskView[] }) {
  const t = useTranslations("job")
  const xai = job.artifacts.filter((a: Artifact) => (a.kind === "xai" || a.kind === "face") && a.content_type.startsWith("image/"))
  const [overlay, setOverlay] = useState<string>("none")
  const [opacity, setOpacity] = useState(60)
  const videoRef = useRef<HTMLVideoElement>(null)
  const current = xai.find((a: Artifact) => a.id === overlay)
  const mediaUrl = job.media?.content_url
  const taskName = (id: string | null | undefined) => tasks.find((x) => x.id === id)?.name ?? ""

  return (
    <HudCard>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <Eyebrow index={1}>{t("media.eyebrow")}</Eyebrow>
          <CardTitle className="mt-1 text-base break-all">{job.title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!mediaUrl ? (
          <div className="flex h-64 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            {job.status === "expired" ? t("media.expired") : t("media.unavailable")}
          </div>
        ) : job.media_type === "image" ? (
          <div className="relative overflow-hidden rounded-lg border bg-black/40">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={mediaUrl} alt={t("media.original")} className="mx-auto max-h-[520px] w-auto object-contain" />
            {current && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={current.url} alt={t("media.overlayAlt", { label: current.label })}
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
                {xai.map((a: Artifact) => (
                  <ToggleGroupItem key={a.id} value={a.id}>{taskName(a.task)} · {a.label}</ToggleGroupItem>
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
        {job.media_type === "video" && <VideoTimeline job={job} tasks={tasks} videoRef={videoRef} />}
        {xai.length > 0 && job.media_type === "video" && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {xai.slice(0, 6).map((a: Artifact) => (
              <figure key={a.id} className="space-y-1">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={a.url} alt={a.label} className="aspect-square w-full rounded-md border object-cover" loading="lazy" />
                <figcaption className="truncate text-xs text-muted-foreground">{taskName(a.task)} · {a.label}</figcaption>
              </figure>
            ))}
          </div>
        )}
      </CardContent>
    </HudCard>
  )
}

/** Per-frame / per-interval fake probability across models; click to seek. */
function VideoTimeline({ job, tasks, videoRef }: { job: JobDetail; tasks: TaskView[];
  videoRef: React.RefObject<HTMLVideoElement | null> }) {
  const t = useTranslations("job")
  const { data: liveIntervals } = useQuery<{ index: number; start_sec: number; end_sec: number; fake_prob: number }[]>({
    queryKey: ["jobs", "intervals", job.id], queryFn: () => [], enabled: false, staleTime: Infinity })
  const series = useMemo(() => {
    const longTask = tasks.find((x) => x.kind === "long_video")
    const intervals = longTask?.result?.intervals?.length ? longTask.result.intervals : liveIntervals ?? []
    if (intervals.length) {
      return intervals.map((i) => ({ x: i.start_sec, fake: Math.round((i.fake_prob ?? 0) * 1000) / 10 }))
    }
    const primary = tasks.find((x) => x.kind === "model" && (x.result?.per_frame?.length ?? 0) > 0)
    const duration = job.media?.duration_seconds ?? 0
    const frames = primary?.result?.per_frame ?? []
    const fps = job.media?.fps || 25
    return frames.map((f, idx) => {
      const n = Number(f.frame)
      const x = Number.isFinite(n) ? n / fps : (duration * idx) / Math.max(1, frames.length)
      return { x: Math.round(x * 10) / 10, fake: Math.round(f.fake_prob * 1000) / 10 }
    })
  }, [tasks, liveIntervals, job.media])
  const config = { fake: { label: t("media.fakePct"), color: "var(--viz-fake)" } } satisfies ChartConfig
  if (!series.length) return null
  return (
    <div className="space-y-1.5">
      <p className="hud-eyebrow">{t("media.timeline")}</p>
      <ChartContainer config={config} className="h-40 w-full">
        <AreaChart data={series} margin={{ left: -16, right: 8 }}
          onClick={(e) => { const x = Number(e?.activeLabel); if (videoRef.current && Number.isFinite(x)) videoRef.current.currentTime = x }}>
          <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
          <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tickLine={false} axisLine={false}
            tickFormatter={(v) => `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, "0")}`} />
          <YAxis domain={[0, 100]} tickLine={false} axisLine={false} width={40} tickFormatter={(v) => `${v}%`} />
          <ReferenceLine y={50} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => {
            const x = Number(p?.[0]?.payload?.x ?? 0)
            return `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, "0")}`
          }} />} />
          <Area dataKey="fake" type="monotone" stroke="var(--color-fake)" strokeWidth={2} fill="var(--color-fake)"
            fillOpacity={0.15} dot={false} activeDot={{ r: 4 }} />
        </AreaChart>
      </ChartContainer>
      <p className="text-xs text-muted-foreground">{t("media.timelineHint")}</p>
    </div>
  )
}

"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight, CircleStop, FileVideo, Loader2, RotateCcw, TriangleAlert } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useEffect, useMemo, useRef, useState } from "react"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { useBalance } from "@/components/sml/credit-meter"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useLongVideoStream } from "@/hooks/use-long-video-stream"
import { api, data } from "@/lib/api/client"
import { formatBytes, formatTimestamp } from "@/lib/format"

import { LongVideoTimeline } from "./long-video-timeline"

const VIDEO_TYPES = "video/mp4,video/webm,video/quicktime,video/x-matroska,video/x-msvideo,.mkv,.avi,.mov"

/**
 * Long-form scanner. The video plays locally; on Start it is streamed to the GPU stream service,
 * analysed there interval by interval, and deleted afterwards. Only the analysed minutes are charged.
 */
export function LongVideoScanner() {
  const t = useTranslations("longVideo")
  const locale = useLocale()
  const catalog = useQuery({
    queryKey: ["long-video", "models"],
    queryFn: async () => data(await api.GET("/api/v1/long-video/models")),
    staleTime: 30_000,
  })
  const balance = useBalance()
  const stream = useLongVideoStream()
  const video = useRef<HTMLVideoElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [range, setRange] = useState<[number, number]>([0, 0])
  const [modelId, setModelId] = useState<string | null>(null)
  const [mode, setMode] = useState<"intervals" | "whole">("intervals")
  const [interval, setIntervalSec] = useState(5)
  const [faceCrop, setFaceCrop] = useState<boolean | null>(null)

  useEffect(() => () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }, [objectUrl])

  const models = catalog.data?.models ?? []
  const available = models.filter((m) => m.available)
  const model = models.find((m) => m.model_id === (modelId ?? available[0]?.model_id))
  const cropSupport = model?.face_crop.support ?? "none"
  const cropOn = cropSupport === "always" ? true : cropSupport === "none" ? false : (faceCrop ?? model?.face_crop.default ?? false)
  const [start, end] = range
  const seconds = Math.max(0, end - start)
  const pricePerMinute = catalog.data?.price_per_minute ?? 0
  const cost = seconds > 0 ? Math.max(1, Math.ceil(seconds / 60)) * pricePerMinute : 0
  const affordable = balance.data?.unlimited || (balance.data?.balance ?? 0) >= cost
  const busy = ["paying", "connecting", "uploading", "queued", "analyzing"].includes(stream.phase)
  const tooBig = !!file && !!catalog.data && file.size > catalog.data.max_bytes
  const canStart = !!file && !!model?.available && duration > 0 && seconds > 0 && affordable && !busy && !tooBig

  const choose = (f: File | undefined) => {
    if (!f) return
    stream.reset()
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    setFile(f)
    setObjectUrl(URL.createObjectURL(f))
    setDuration(0)
    setRange([0, 0])
  }

  const begin = () => {
    if (!file || !model) return
    void stream.start(file, duration, {
      modelId: model.model_id, startSec: start, endSec: end >= duration - 0.05 ? null : end, intervalSec: interval,
      wholeVideo: mode === "whole", faceCrop: cropSupport === "optional" ? cropOn : null, locale,
    })
  }

  const seek = (s: number) => {
    if (video.current) {
      video.current.currentTime = s
      void video.current.play().catch(() => undefined)
    }
  }

  const analysedUntil = stream.intervals.length ? stream.intervals[stream.intervals.length - 1].end_sec : null
  const progress = stream.expected ? Math.min(100, (stream.intervals.length / stream.expected) * 100) : null
  const uploadPct = file ? Math.min(100, (stream.uploaded / file.size) * 100) : 0
  const average = useMemo(() => stream.intervals.length
    ? stream.intervals.reduce((a, i) => a + i.fake_probability, 0) / stream.intervals.length : null, [stream.intervals])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={2} title={t("title")} description={t("subtitle")} />
      {catalog.data && !catalog.data.online && (
        <Alert variant="destructive"><TriangleAlert className="size-4" /><AlertDescription>{t("offline")}</AlertDescription></Alert>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <HudCard>
            <CardHeader>
              <Eyebrow index={1}>{t("step1")}</Eyebrow>
              <CardTitle className="text-base">{t("videoTitle")}</CardTitle>
              <CardDescription>{t("videoHint")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {!file ? (
                <label className="flex h-48 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground hover:bg-accent/40">
                  <FileVideo className="size-8 text-primary" />
                  <span className="font-medium text-foreground">{t("choose")}</span>
                  <span className="text-xs">{t("chooseHint")}</span>
                  <input type="file" accept={VIDEO_TYPES} className="sr-only" onChange={(e) => choose(e.target.files?.[0])} />
                </label>
              ) : (
                <>
                  <video ref={video} src={objectUrl ?? undefined} controls preload="metadata"
                    className="max-h-[440px] w-full rounded-lg border bg-black"
                    onLoadedMetadata={(e) => {
                      const d = e.currentTarget.duration
                      if (Number.isFinite(d)) { setDuration(d); setRange([0, d]) }
                    }}
                    onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)} />
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="truncate font-mono">{file.name} · {formatBytes(file.size)}
                      {duration > 0 && ` · ${formatTimestamp(duration)}`}</span>
                    <label className="cursor-pointer text-primary hover:underline">
                      {t("replace")}
                      <input type="file" accept={VIDEO_TYPES} className="sr-only" disabled={busy}
                        onChange={(e) => choose(e.target.files?.[0])} />
                    </label>
                  </div>
                  {tooBig && <p className="text-xs text-fake">{t("tooBig", { size: formatBytes(catalog.data!.max_bytes) })}</p>}
                  {duration > 0 && (
                    <LongVideoTimeline intervals={stream.intervals} rangeStart={start} rangeEnd={end}
                      currentTime={currentTime} analysedUntil={stream.phase === "analyzing" ? analysedUntil ?? start : null}
                      onSeek={seek} />
                  )}
                </>
              )}
            </CardContent>
          </HudCard>

          <HudCard>
            <CardHeader>
              <Eyebrow index={2}>{t("step2")}</Eyebrow>
              <CardTitle className="text-base">{t("settingsTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label className="hud-eyebrow">{t("model")}</Label>
                {catalog.isLoading ? <Loader2 className="size-4 animate-spin" /> : (
                  <RadioGroup value={model?.model_id ?? ""} onValueChange={setModelId} className="grid gap-2 sm:grid-cols-2"
                    disabled={busy}>
                    {models.map((m) => (
                      <label key={m.model_id} className={`flex items-start gap-3 rounded-lg border p-3 ${m.available ? "" : "opacity-60"}`}>
                        <RadioGroupItem value={m.model_id} disabled={!m.available} className="mt-0.5" />
                        <span className="min-w-0">
                          <span className="font-medium">{m.name}</span>
                          <span className="block text-xs text-muted-foreground">
                            {m.available ? t(`faceCropSupport.${m.face_crop.support}`) : t("unavailable")}
                          </span>
                        </span>
                      </label>
                    ))}
                  </RadioGroup>
                )}
              </div>

              <div className="space-y-2">
                <Label className="hud-eyebrow">{t("mode")}</Label>
                <ToggleGroup type="single" value={mode} variant="outline" disabled={busy}
                  onValueChange={(v) => v && setMode(v as "intervals" | "whole")}>
                  <ToggleGroupItem value="intervals">{t("modeIntervals")}</ToggleGroupItem>
                  <ToggleGroupItem value="whole">{t("modeWhole")}</ToggleGroupItem>
                </ToggleGroup>
                <p className="text-xs text-muted-foreground">{mode === "whole" ? t("modeWholeHint") : t("modeIntervalsHint")}</p>
              </div>

              {mode === "intervals" && (
                <div className="space-y-2">
                  <div className="flex justify-between"><Label htmlFor="interval" className="hud-eyebrow">{t("interval")}</Label>
                    <span className="font-mono text-sm">{t("seconds", { count: interval })}</span></div>
                  <Slider id="interval" min={1} max={60} step={1} value={[interval]} disabled={busy}
                    onValueChange={([v]) => setIntervalSec(v)} className="max-w-md" />
                  <p className="text-xs text-muted-foreground">{t("intervalHint")}</p>
                </div>
              )}

              {duration > 0 && (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label className="hud-eyebrow">{t("range")}</Label>
                    <span className="font-mono text-sm">{formatTimestamp(start)} – {formatTimestamp(end)}</span>
                  </div>
                  <Slider min={0} max={duration} step={0.1} value={range} disabled={busy} minStepsBetweenThumbs={1}
                    onValueChange={(v) => setRange([v[0], v[1]] as [number, number])} aria-label={t("range")} />
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" disabled={busy}
                      onClick={() => setRange([Math.min(currentTime, end - 1), end])}>{t("setStart")}</Button>
                    <Button type="button" size="sm" variant="outline" disabled={busy}
                      onClick={() => setRange([start, Math.max(currentTime, start + 1)])}>{t("setEnd")}</Button>
                    <Button type="button" size="sm" variant="ghost" disabled={busy}
                      onClick={() => setRange([0, duration])}>{t("wholeRange")}</Button>
                  </div>
                </div>
              )}

              {cropSupport === "optional" && (
                <label className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
                  <span>{t("faceCrop")}<span className="block text-xs text-muted-foreground">{t("faceCropHint")}</span></span>
                  <Switch checked={cropOn} disabled={busy} onCheckedChange={setFaceCrop} />
                </label>
              )}
            </CardContent>
          </HudCard>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <HudCard>
            <CardHeader>
              <Eyebrow index={3}>{t("step3")}</Eyebrow>
              <CardTitle className="text-base">{t("summary")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">{t("selected")}</span>
                <span className="font-mono">{formatTimestamp(seconds)}</span></div>
              <div className="flex justify-between text-base font-semibold"><span>{t("maxCost")}</span>
                <span className="font-mono">{t("credits", { count: cost })}</span></div>
              <p className="text-xs text-muted-foreground">{t("pricing", { price: pricePerMinute })}</p>
              {!busy ? (
                <Button className="w-full" size="lg" disabled={!canStart} onClick={begin}>
                  <ArrowRight className="size-4" /> {t("start")}
                </Button>
              ) : (
                <Button className="w-full" size="lg" variant="destructive" onClick={stream.stop}
                  disabled={stream.phase === "paying" || stream.phase === "connecting"}>
                  <CircleStop className="size-4" /> {t("stop")}
                </Button>
              )}
              {!affordable && file && <p className="text-xs text-fake">{t("notEnough")}</p>}
            </CardContent>
          </HudCard>

          {stream.phase !== "idle" && (
            <HudCard>
              <CardHeader>
                <Eyebrow index={4}>{t("liveEyebrow")}</Eyebrow>
                <CardTitle className="text-base">{t(`phase.${stream.phase}`)}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {(stream.phase === "uploading" || (stream.uploaded > 0 && stream.phase === "connecting")) && (
                  <div className="space-y-1">
                    <Progress value={uploadPct} />
                    <p className="font-mono text-xs text-muted-foreground">
                      {formatBytes(stream.uploaded)} / {formatBytes(file?.size)} · {Math.round(uploadPct)}%
                    </p>
                  </div>
                )}
                {stream.phase === "queued" && (
                  <p className="text-muted-foreground">
                    {stream.queuePosition ? t("queuePosition", { count: stream.queuePosition }) : t("preparing")}
                  </p>
                )}
                {(stream.phase === "analyzing" || stream.intervals.length > 0) && (
                  <div className="space-y-1">
                    <Progress value={progress ?? undefined} />
                    <p className="font-mono text-xs text-muted-foreground">
                      {t("intervalsDone", { count: stream.intervals.length })}
                      {stream.expected ? ` / ${stream.expected}` : ""}
                      {average != null && ` · ${t("runningAverage", { pct: Math.round(average * 100) })}`}
                    </p>
                  </div>
                )}
                {stream.error && <p className="text-xs text-fake">{stream.error}</p>}
                {stream.result && stream.result.status !== "error" && (
                  <div className="space-y-3 border-t pt-3">
                    <VerdictBadge verdict={stream.result.average >= 0.5 ? "fake" : "real"} probability={stream.result.average} />
                    <p className="text-xs text-muted-foreground">
                      {t(stream.result.status === "stopped" ? "resultStopped" : "resultDone", {
                        time: formatTimestamp(stream.result.analysedSeconds),
                        credits: stream.result.creditsCharged ?? 0,
                      })}
                    </p>
                  </div>
                )}
                {stream.jobId && (stream.phase === "finished" || stream.phase === "error") && (
                  <div className="flex flex-wrap gap-2">
                    <Button asChild size="sm"><Link href={`/app/results/${stream.jobId}`}>{t("openResult")}</Link></Button>
                    <Button size="sm" variant="outline" onClick={stream.reset}><RotateCcw className="size-4" /> {t("again")}</Button>
                  </div>
                )}
              </CardContent>
            </HudCard>
          )}
        </aside>
      </div>
    </div>
  )
}

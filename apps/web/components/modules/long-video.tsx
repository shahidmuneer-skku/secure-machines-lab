"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Loader2 } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useState } from "react"

import { Dropzone } from "@/components/detect/dropzone"
import { UploadList } from "@/components/detect/upload-list"
import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Slider } from "@/components/ui/slider"
import { useCatalog } from "@/hooks/use-catalog"
import { quoteRequest, useSubmitJobs } from "@/hooks/use-submit-jobs"
import { useUploads } from "@/hooks/use-uploads"
import { formatDuration } from "@/lib/format"

/** Long-form scanner: scores every interval of a long video and streams the timeline live. */
export function LongVideoScanner() {
  const t = useTranslations("longVideo")
  const router = useRouter()
  const uploads = useUploads(1)
  const catalog = useCatalog()
  const submit = useSubmitJobs()
  const [interval, setInterval] = useState(5)
  const models = catalog.data?.long_video_models ?? []
  const [model, setModel] = useState<string | null>(null)
  const selected = model ?? models.find((m) => m.default_selected)?.id ?? models[0]?.id
  const ready = uploads.ready.filter((r) => r.media?.media_type === "video")
  const request = { media: ready.map((r) => r.media!), models: selected ? [selected] : [], catalog: [], auditSteps: [] as never[],
    module: "long_video" as const, options: { interval_seconds: interval } }
  const quote = useQuery({ queryKey: ["quote-long", ready.map((r) => r.media!.id), selected], enabled: ready.length > 0 && !!selected,
    queryFn: () => quoteRequest(request), retry: false })
  const start = async () => {
    const jobs = await submit.mutateAsync(request)
    router.push(`/app/results/${jobs[0].id}`)
  }
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={2} title={t("title")} description={t("subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <HudCard>
            <CardHeader><Eyebrow index={1}>{t("step1")}</Eyebrow><CardTitle className="text-base">{t("uploadTitle")}</CardTitle>
              <CardDescription>{t("uploadHint")}</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              {uploads.items.length === 0 && <Dropzone onFiles={(f) => uploads.add(f.slice(0, 1))} videosOnly multiple={false} />}
              <UploadList items={uploads.items} onRemove={uploads.remove} onRetry={uploads.retry} />
            </CardContent>
          </HudCard>
          <HudCard>
            <CardHeader><Eyebrow index={2}>{t("step2")}</Eyebrow><CardTitle className="text-base">{t("settingsTitle")}</CardTitle></CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label className="hud-eyebrow">{t("model")}</Label>
                <RadioGroup value={selected} onValueChange={setModel} className="gap-2">
                  {models.map((m) => (
                    <label key={m.id} className="flex items-start gap-3 rounded-lg border p-3">
                      <RadioGroupItem value={m.id} className="mt-0.5" />
                      <span><span className="font-medium">{m.name}</span><span className="block text-xs text-muted-foreground">{m.description}</span></span>
                    </label>
                  ))}
                </RadioGroup>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between"><Label htmlFor="interval" className="hud-eyebrow">{t("interval")}</Label>
                  <span className="font-mono text-sm">{t("seconds", { count: interval })}</span></div>
                <Slider id="interval" min={1} max={30} step={1} value={[interval]} onValueChange={([v]) => setInterval(v)} className="max-w-md" />
                <p className="text-xs text-muted-foreground">{t("intervalHint")}</p>
              </div>
            </CardContent>
          </HudCard>
        </div>
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <HudCard>
            <CardHeader><Eyebrow index={3}>{t("step3")}</Eyebrow><CardTitle className="text-base">{t("summary")}</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              {ready[0]?.media?.duration_seconds != null && (
                <div className="flex justify-between"><span className="text-muted-foreground">{t("duration")}</span>
                  <span className="font-mono">{formatDuration(ready[0].media.duration_seconds)}</span></div>
              )}
              {quote.data && <div className="flex justify-between text-base font-semibold"><span>{t("cost")}</span>
                <span className="font-mono">{t("credits", { count: quote.data.credits })}</span></div>}
              <p className="text-xs text-muted-foreground">{t("pricing")}</p>
              <Button className="w-full" size="lg" disabled={!ready.length || !selected || submit.isPending || quote.data?.affordable === false} onClick={start}>
                {submit.isPending ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />} {t("start")}
              </Button>
              {quote.data?.affordable === false && <p className="text-xs text-fake">{t("notEnough")}</p>}
            </CardContent>
          </HudCard>
        </aside>
      </div>
    </div>
  )
}

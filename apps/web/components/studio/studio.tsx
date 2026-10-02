"use client"

import {
  AlertTriangle, Ban, ChevronDown, Coins, Dices, ImagePlus, Loader2, RotateCcw, ShieldCheck, Sparkles,
  Wand2, X,
} from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { Dropzone } from "@/components/detect/dropzone"
import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { QueuePill } from "@/components/sml/queue-pill"
import { StatusChip } from "@/components/sml/status-chip"
import { useBalance } from "@/components/sml/credit-meter"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  isActive, useCancelStudio, useDetectImage, useStudioConfig, useStudioHistory, useStudioJob, useSubmitStudio,
} from "@/hooks/use-studio"
import { useUploads } from "@/hooks/use-uploads"
import { isApiError } from "@/lib/api/errors"
import type { StudioControls, StudioImage, StudioJob, StudioMode } from "@/lib/api/types"
import { cn } from "@/lib/utils"

import { AspectGlyph, HistoryGrid, Lightbox, OutputTile, useLightbox } from "./parts"

const MATCH_INPUT = "match"
const MODE_ICON = { generate: Sparkles, edit: Wand2 } as const

/**
 * Image studio: generate images from a prompt or edit reference images by instruction. The controls
 * follow the model the administrator chose for each mode (formats, number of references, steps,
 * guidance, transparency…); users never see or choose the model. Administrators can try others.
 */
export function Studio() {
  const t = useTranslations("studio")
  const router = useRouter()
  const config = useStudioConfig()
  const history = useStudioHistory()
  const balance = useBalance()
  const submit = useSubmitStudio()
  const cancel = useCancelStudio()
  const detect = useDetectImage()
  const uploads = useUploads(2)
  const lightbox = useLightbox()

  const [modeChoice, setModeChoice] = useState<StudioMode>("generate")
  const [model, setModelChoice] = useState("")  // administrators: "" = the admin's model for the mode
  const [prompt, setPrompt] = useState("")
  const [negative, setNegative] = useState("")
  const [aspectChoice, setAspect] = useState("")
  const [countChoice, setCount] = useState(1)
  const [transparentChoice, setTransparent] = useState(false)
  const [steps, setSteps] = useState<number | null>(null)
  const [guidance, setGuidance] = useState<number | null>(null)
  const [seed, setSeed] = useState("")
  const [picked, setPicked] = useState<StudioImage[]>([])  // earlier images used as references
  const [consent, setConsent] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [advanced, setAdvanced] = useState(false)
  const promptRef = useRef<HTMLTextAreaElement>(null)

  const cfg = config.data
  const models = cfg?.models
  const availableModes = (["generate", "edit"] as const).filter((m) => cfg?.modes[m].available)
  const mode: StudioMode = cfg?.modes[modeChoice].available || !availableModes.length ? modeChoice : availableModes[0]
  const chosen = model ? models?.find((m) => m.id === model) : undefined
  const controls: StudioControls | null | undefined = chosen ? chosen.controls[mode] : cfg?.modes[mode].controls
  const price = cfg?.modes[mode].price ?? 0
  // The request always stays inside what the current model offers.
  const count = Math.min(countChoice, controls?.max_outputs ?? 1)
  const aspect = aspectChoice === MATCH_INPUT || controls?.aspect_ratios.some((r) => r.id === aspectChoice)
    ? aspectChoice : ""
  const transparent = transparentChoice && !!controls?.transparent && mode === "generate"

  // Steps and guidance ranges differ per model: back to the model's defaults on a switch.
  const setMode = (next: StudioMode) => {
    setModeChoice(next)
    setSteps(null)
    setGuidance(null)
  }
  const setModel = (next: string) => {
    setModelChoice(next)
    setSteps(null)
    setGuidance(null)
  }

  const jobs = useMemo(() => history.data?.pages.flatMap((p) => p.results) ?? [], [history.data])
  const latestId = selectedId ?? jobs[0]?.id ?? null
  const job = useStudioJob(latestId)
  const shown: StudioJob | undefined = job.data ?? jobs.find((j) => j.id === latestId)

  const refCount = picked.length + uploads.items.filter((i) => i.state !== "invalid" && i.state !== "error").length
  const maxRefs = controls?.references.max ?? 0
  const references = [...picked.map((p) => p.id), ...uploads.ready.map((u) => u.media!.id)]
  const cost = price * count
  const affordable = balance.data ? balance.data.unlimited || balance.data.balance >= cost : true
  const canSubmit = !!controls && prompt.trim().length > 0 && !submit.isPending && !uploads.busy && affordable
    && (mode === "generate" || (references.length >= (controls?.references.min ?? 1) && references.length <= maxRefs))

  const run = async (overrides: { consent?: boolean } = {}) => {
    if (!controls) return
    try {
      const created = await submit.mutateAsync({
        mode, prompt, negative_prompt: controls.negative_prompt ? negative : "",
        aspect_ratio: aspect === MATCH_INPUT ? "" : aspect, steps, guidance, count,
        seed: seed.trim() ? Number(seed) : null, transparent,
        reference_ids: mode === "edit" ? references : [], consent: overrides.consent ?? consent, model,
      })
      setSelectedId(created.id)
      toast.success(t("queued"), { description: t("queuedHint", { credits: created.credits_quoted }) })
    } catch (e) {
      if (isApiError(e) && e.code === "INSUFFICIENT_CREDITS") {
        toast.error(t("insufficient"), { description: e.detail,
          action: { label: t("buyCredits"), onClick: () => router.push("/app/billing") } })
      } else {
        toast.error(t("submitFailed"), { description: isApiError(e) ? e.detail : undefined })
      }
    }
  }

  // A job refused because a reference shows a person: ask for consent next to the references.
  const consentNeeded = shown?.status === "failed" && shown.error?.code === "CONSENT_REQUIRED"

  const editAgain = (image: StudioImage) => {
    setMode("edit")
    setPicked((prev) => (prev.some((p) => p.id === image.id) ? prev : [...prev, image]).slice(-Math.max(1,
      (cfg?.modes.edit.controls?.references.max ?? 1))))
    setPrompt("")
    promptRef.current?.focus()
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const reuse = (j: StudioJob) => {
    setMode(j.mode)
    setPrompt(j.params.prompt)
    setNegative(j.params.negative_prompt ?? "")
    setAspect(j.params.aspect_ratio ?? "")
    setCount(j.params.count)
    setSeed(j.params.seed != null ? String(j.params.seed) : "")
    if (j.mode === "edit") setPicked(j.references)
    promptRef.current?.focus()
  }

  const analyse = async (image: StudioImage) => {
    try {
      const created = await detect.mutateAsync(image.id)
      router.push(`/app/results/${created.id}`)
    } catch (e) {
      toast.error(t("detectFailed"), { description: isApiError(e) ? e.detail : undefined })
    }
  }

  if (config.isPending) return <StudioSkeleton />
  if (!cfg?.enabled) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")} />
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon"><Ban /></EmptyMedia>
            <EmptyTitle>{t("unavailableTitle")}</EmptyTitle>
            <EmptyDescription>{t("unavailableHint")}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    )
  }

  const ModeIcon = MODE_ICON[mode]
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")}
        actions={!cfg.online && <Badge variant="outline" className="border-warn/50 text-warn">{t("warmingUp")}</Badge>} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        {/* Composer */}
        <HudCard className="xl:sticky xl:top-20 xl:self-start">
          <CardHeader className="space-y-4">
            <Tabs value={mode} onValueChange={(v) => setMode(v as StudioMode)}>
              <TabsList className="grid w-full grid-cols-2">
                {(["generate", "edit"] as const).map((m) => {
                  const Icon = MODE_ICON[m]
                  return (
                    <TabsTrigger key={m} value={m} disabled={!cfg.modes[m].available} className="gap-1.5">
                      <Icon className="size-4" aria-hidden /> {t(`modes.${m}`)}
                    </TabsTrigger>
                  )
                })}
              </TabsList>
            </Tabs>
            <CardDescription>{t(`modeHint.${mode}`)}</CardDescription>
            {models && (
              <div className="space-y-1.5 rounded-lg border border-dashed p-3">
                <Label htmlFor="studio-model" className="mono-label text-muted-foreground">{t("adminModel")}</Label>
                <Select value={model || "active"} onValueChange={(v) => setModel(v === "active" ? "" : v)}>
                  <SelectTrigger id="studio-model" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">
                      {t("adminModelActive", { name: models.find((m) => m.id === cfg.active?.[mode])?.name ?? "—" })}
                    </SelectItem>
                    {models.filter((m) => m.modes.includes(mode)).map((m) => (
                      <SelectItem key={m.id} value={m.id} disabled={!m.installed}>
                        {m.name}{m.commercial ? "" : ` · ${t("nonCommercial")}`}{m.loaded ? ` · ${t("loaded")}` : ""}
                        {m.installed ? "" : ` · ${t("notInstalled")}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{t("adminModelHint")}</p>
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-5">
            {mode === "edit" && controls && (
              <section className="space-y-2">
                <div className="flex items-baseline justify-between">
                  <Label className="font-medium">{t("references")}</Label>
                  <span className="mono-label text-muted-foreground">{refCount}/{maxRefs}</span>
                </div>
                <ul className="grid grid-cols-4 gap-2">
                  {picked.map((p, i) => (
                    <RefThumb key={p.id} index={i + 1} src={p.thumbnail_url ?? p.url}
                      onRemove={() => setPicked((prev) => prev.filter((x) => x.id !== p.id))} />
                  ))}
                  {uploads.items.map((u, i) => (
                    <RefThumb key={u.key} index={picked.length + i + 1} src={u.previewUrl ?? ""}
                      busy={u.state === "uploading"} failed={u.state === "error" || u.state === "invalid"}
                      onRemove={() => uploads.remove(u.key)} />
                  ))}
                </ul>
                {refCount < maxRefs && (
                  <Dropzone imagesOnly compact multiple={maxRefs - refCount > 1}
                    onFiles={(files) => uploads.add(files.slice(0, maxRefs - refCount))} />
                )}
                <p className="text-xs text-muted-foreground">{t("referencesHint", { max: maxRefs })}</p>
                {refCount > 0 && (
                  <label className={cn("flex items-start gap-2 rounded-lg border p-3 text-xs",
                    consentNeeded && !consent ? "border-warn bg-warn/10" : "border-border")}>
                    <Checkbox checked={consent} onCheckedChange={(v) => setConsent(v === true)} className="mt-0.5" />
                    <span className="space-y-1">
                      <span className="flex items-center gap-1 font-medium"><ShieldCheck className="size-3.5" />
                        {t("consentTitle")}</span>
                      <span className="block text-muted-foreground">{t("consentText")}</span>
                    </span>
                  </label>
                )}
              </section>
            )}

            <section className="space-y-2">
              <div className="flex items-baseline justify-between">
                <Label htmlFor="studio-prompt" className="font-medium">{t(`promptLabel.${mode}`)}</Label>
                <span className="mono-label text-muted-foreground">{prompt.length}/{controls?.prompt_max_chars ?? 2000}</span>
              </div>
              <Textarea id="studio-prompt" ref={promptRef} value={prompt} rows={4}
                maxLength={controls?.prompt_max_chars ?? 2000} placeholder={t(`placeholder.${mode}`)}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canSubmit) void run() }} />
              <div className="flex flex-wrap gap-1.5">
                {(t.raw(`examples.${mode}`) as string[]).map((ex) => (
                  <button key={ex} type="button" onClick={() => setPrompt(ex)}
                    className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground">
                    {ex.length > 42 ? `${ex.slice(0, 40)}…` : ex}
                  </button>
                ))}
              </div>
            </section>

            {controls && (controls.aspect_ratios.length > 0 || mode === "edit") && (
              <section className="space-y-2">
                <Label className="font-medium">{t("format")}</Label>
                <ToggleGroup type="single" variant="outline" size="sm" className="flex flex-wrap justify-start"
                  value={aspect || (mode === "edit" ? MATCH_INPUT : controls.aspect_ratios[0]?.id)}
                  onValueChange={(v) => v && setAspect(v)}>
                  {mode === "edit" && (
                    <ToggleGroupItem value={MATCH_INPUT} className="gap-1.5 px-2.5" aria-label={t("matchInput")}>
                      <ImagePlus className="size-4" aria-hidden /> {t("matchInput")}
                    </ToggleGroupItem>
                  )}
                  {controls.aspect_ratios.map((r) => (
                    <ToggleGroupItem key={r.id} value={r.id} className="gap-1.5 px-2.5"
                      aria-label={`${r.id} (${r.width}×${r.height})`} title={`${r.width}×${r.height}`}>
                      <AspectGlyph width={r.width} height={r.height} /> {r.id}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </section>
            )}

            {controls && (
              <section className="flex flex-wrap items-end justify-between gap-4">
                <div className="space-y-2">
                  <Label className="font-medium">{t("count")}</Label>
                  <ToggleGroup type="single" variant="outline" size="sm" value={String(count)}
                    onValueChange={(v) => v && setCount(Number(v))}>
                    {Array.from({ length: controls.max_outputs }, (_, i) => (
                      <ToggleGroupItem key={i} value={String(i + 1)} className="w-9">{i + 1}</ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </div>
                {controls.transparent && mode === "generate" && (
                  <label className="flex items-center gap-2 text-sm">
                    <Switch checked={transparent} onCheckedChange={setTransparent} />
                    {t("transparent")}
                  </label>
                )}
              </section>
            )}

            {controls && (
              <Collapsible open={advanced} onOpenChange={setAdvanced}>
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm" className="-ml-2 gap-1 text-muted-foreground">
                    <ChevronDown className={cn("size-4 transition-transform", advanced && "rotate-180")} />
                    {t("advanced")}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-4 pt-2">
                  {controls.negative_prompt && (
                    <div className="space-y-1.5">
                      <Label htmlFor="studio-negative">{t("negative")}</Label>
                      <Textarea id="studio-negative" rows={2} value={negative} placeholder={t("negativePlaceholder")}
                        onChange={(e) => setNegative(e.target.value)} maxLength={controls.prompt_max_chars} />
                    </div>
                  )}
                  {controls.steps && (
                    <RangeControl label={t("steps")} hint={t("stepsHint")} spec={controls.steps} value={steps}
                      onChange={setSteps} integer />
                  )}
                  {controls.guidance && (
                    <RangeControl label={t("guidance")} hint={t("guidanceHint")} spec={controls.guidance}
                      value={guidance} onChange={setGuidance} />
                  )}
                  <div className="space-y-1.5">
                    <Label htmlFor="studio-seed">{t("seed")}</Label>
                    <div className="flex gap-2">
                      <Input id="studio-seed" inputMode="numeric" value={seed} placeholder={t("seedRandom")}
                        onChange={(e) => setSeed(e.target.value.replace(/\D/g, "").slice(0, 10))} />
                      <Button type="button" variant="outline" size="icon" aria-label={t("seedRoll")}
                        onClick={() => setSeed(String(Math.floor(Math.random() * 2 ** 31)))}><Dices /></Button>
                      {seed && <Button type="button" variant="ghost" size="icon" aria-label={t("seedClear")}
                        onClick={() => setSeed("")}><X /></Button>}
                    </div>
                    <p className="text-xs text-muted-foreground">{t("seedHint")}</p>
                  </div>
                </CollapsibleContent>
              </Collapsible>
            )}

            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-1.5 text-muted-foreground"><Coins className="size-4" />
                  {t("cost", { count, price })}</span>
                <span className="text-base font-bold tabular-nums">{t("creditsN", { count: cost })}</span>
              </div>
              {!affordable && (
                <Alert className="border-warn/40 bg-warn/10">
                  <AlertTriangle className="size-4" />
                  <AlertDescription className="flex items-center justify-between gap-2">
                    {t("notEnough")}
                    <Button asChild size="sm" variant="outline"><Link href="/app/billing">{t("buyCredits")}</Link></Button>
                  </AlertDescription>
                </Alert>
              )}
              <Button className="w-full" size="lg" disabled={!canSubmit} onClick={() => void run()}>
                {submit.isPending ? <Loader2 className="size-4 animate-spin" /> : <ModeIcon className="size-4" />}
                {t(`submit.${mode}`)}
              </Button>
              <p className="text-xs text-muted-foreground">{t("chargeHint")}</p>
            </div>
          </CardContent>
        </HudCard>

        {/* Result and history */}
        <div className="min-w-0 space-y-6">
          <JobPanel job={shown} loading={!!latestId && !shown}
            onCancel={(id) => cancel.mutate(id, { onSuccess: () => toast.success(t("canceled")) })}
            canceling={cancel.isPending} onOpen={lightbox.open} onEdit={cfg.modes.edit.available ? editAgain : undefined}
            onDetect={analyse} detectingId={detect.isPending ? detect.variables : undefined} onReuse={reuse}
            onConsentRetry={() => { setConsent(true); void run({ consent: true }) }} />

          <section className="space-y-3">
            <Eyebrow>{t("history")}</Eyebrow>
            {history.isPending ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{Array.from({ length: 4 }, (_, i) =>
                <Skeleton key={i} className="aspect-square rounded-xl" />)}</div>
            ) : jobs.length ? (
              <>
                <HistoryGrid jobs={jobs} selectedId={latestId} onSelect={(j) => setSelectedId(j.id)} />
                {history.hasNextPage && (
                  <div className="flex justify-center">
                    <Button variant="outline" size="sm" onClick={() => history.fetchNextPage()}
                      disabled={history.isFetchingNextPage}>
                      {history.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />} {t("more")}
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{t("historyEmpty")}</p>
            )}
          </section>
        </div>
      </div>
      <Lightbox image={lightbox.image} prompt={shown?.params.prompt} onClose={lightbox.close} />
    </div>
  )
}

function RangeControl({ label, hint, spec, value, onChange, integer = false }: {
  label: string
  hint: string
  spec: { default: number; min: number; max: number; step?: number }
  value: number | null
  onChange: (v: number | null) => void
  integer?: boolean
}) {
  const t = useTranslations("studio")
  const current = value ?? spec.default
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <Label>{label}</Label>
        <span className="flex items-center gap-1">
          <span className="font-semibold tabular-nums">{integer ? current : current.toFixed(1)}</span>
          {value != null && (
            <Button variant="ghost" size="icon" className="size-6" aria-label={t("reset")} onClick={() => onChange(null)}>
              <RotateCcw className="size-3.5" />
            </Button>
          )}
        </span>
      </div>
      <Slider min={spec.min} max={spec.max} step={spec.step ?? (integer ? 1 : 0.5)} value={[current]}
        onValueChange={([v]) => onChange(v)} aria-label={label} />
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  )
}

function RefThumb({ index, src, busy, failed, onRemove }: {
  index: number; src: string; busy?: boolean; failed?: boolean; onRemove: () => void
}) {
  const t = useTranslations("studio")
  return (
    <li className={cn("relative aspect-square overflow-hidden rounded-lg border", failed && "border-fake")}>
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={t("referenceN", { n: index })} className={cn("size-full object-cover", busy && "opacity-50")} />
      )}
      <span className="absolute left-1 top-1 rounded bg-background/85 px-1 mono-label">{t("imageN", { n: index })}</span>
      {busy && <Loader2 className="absolute inset-0 m-auto size-5 animate-spin text-primary" />}
      <button type="button" onClick={onRemove} aria-label={t("removeReference", { n: index })}
        className="absolute right-1 top-1 rounded-full bg-background/85 p-0.5 hover:bg-background">
        <X className="size-3.5" />
      </button>
    </li>
  )
}

function JobPanel({ job, loading, onCancel, canceling, onOpen, onEdit, onDetect, detectingId, onReuse, onConsentRetry }: {
  job: StudioJob | undefined
  loading: boolean
  onCancel: (id: string) => void
  canceling: boolean
  onOpen: (image: StudioImage) => void
  onEdit?: (image: StudioImage) => void
  onDetect: (image: StudioImage) => void
  detectingId?: string
  onReuse: (job: StudioJob) => void
  onConsentRetry: () => void
}) {
  const t = useTranslations("studio")
  if (loading) return <Skeleton className="h-80 rounded-xl" />
  if (!job) {
    return (
      <HudCard>
        <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <Sparkles className="size-10 text-primary" aria-hidden />
          <p className="font-medium">{t("emptyTitle")}</p>
          <p className="max-w-md text-sm text-muted-foreground">{t("emptyHint")}</p>
        </CardContent>
      </HudCard>
    )
  }
  const active = isActive(job)
  const progress = job.live?.progress ?? (job.status === "succeeded" ? 100 : job.progress)
  const placeholders = active ? job.params.count : 0
  const errorText = job.error ? (t.has(`errors.${job.error.code}`) ? t(`errors.${job.error.code}`) : job.error.message) : ""
  return (
    <HudCard>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <StatusChip status={job.status} />
            <Badge variant="outline" className="mono-label">{t(`modes.${job.mode}`)}</Badge>
            {job.model && <Badge variant="secondary" className="mono-label">{job.model.name}</Badge>}
            {job.queue && <QueuePill position={job.queue.position} eta={job.queue.eta_seconds}
              workersOnline={job.queue.workers_online} />}
          </div>
          <div className="flex items-center gap-2">
            {!active && <Button variant="ghost" size="sm" onClick={() => onReuse(job)}><RotateCcw className="size-4" /> {t("reuse")}</Button>}
            {active && (
              <Button variant="outline" size="sm" disabled={canceling} onClick={() => onCancel(job.id)}>
                <Ban className="size-4" /> {t("cancel")}
              </Button>
            )}
          </div>
        </div>
        <CardTitle className="line-clamp-3 text-sm font-normal leading-relaxed">{job.params.prompt}</CardTitle>
        {job.references.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="mono-label text-muted-foreground">{t("from")}</span>
            {job.references.map((r, i) => (
              <button key={r.id} type="button" onClick={() => onOpen(r)} className="size-9 overflow-hidden rounded-md border">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={r.thumbnail_url ?? r.url} alt={t("referenceN", { n: i + 1 })} className="size-full object-cover" />
              </button>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {active && (
          <div className="space-y-1.5" aria-live="polite">
            <Progress value={job.status === "queued" ? 0 : progress} />
            <p className="flex justify-between text-xs text-muted-foreground">
              <span>{job.status === "queued" ? t("waiting") : job.live?.message || t("working")}</span>
              <span className="font-semibold tabular-nums">{Math.round(job.status === "queued" ? 0 : progress)}%</span>
            </p>
          </div>
        )}
        {job.status === "failed" && (
          <Alert className="border-fake/40 bg-fake/10">
            <AlertTriangle className="size-4" />
            <AlertTitle>{t("failedTitle")}</AlertTitle>
            <AlertDescription className="space-y-2">
              <p>{errorText}</p>
              {job.error?.code === "CONSENT_REQUIRED" && (
                <Button size="sm" variant="outline" onClick={onConsentRetry}>
                  <ShieldCheck className="size-4" /> {t("consentRetry")}
                </Button>
              )}
            </AlertDescription>
          </Alert>
        )}
        {job.blocked > 0 && job.status === "succeeded" && (
          <p className="flex items-center gap-1.5 text-xs text-warn"><AlertTriangle className="size-3.5" />
            {t("blocked", { count: job.blocked })}</p>
        )}
        {(job.outputs.length > 0 || placeholders > 0) && (
          <div className={cn("grid gap-3", (job.outputs.length || placeholders) > 1 ? "sm:grid-cols-2" : "")}>
            {job.outputs.map((image) => (
              <OutputTile key={image.id} image={image} onOpen={() => onOpen(image)}
                onEdit={onEdit ? () => onEdit(image) : undefined} onDetect={() => onDetect(image)}
                detecting={detectingId === image.id} />
            ))}
            {Array.from({ length: placeholders }, (_, i) => (
              <div key={i} className="relative aspect-square overflow-hidden rounded-xl border">
                <Skeleton className="size-full rounded-none" />
                <Sparkles className="absolute inset-0 m-auto size-8 animate-pulse text-primary/60" aria-hidden />
              </div>
            ))}
          </div>
        )}
        {job.status === "succeeded" && (
          <p className="text-xs text-muted-foreground">{t("charged", { count: job.credits_charged })}</p>
        )}
      </CardContent>
    </HudCard>
  )
}

function StudioSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-16 w-80" />
      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <Skeleton className="h-[560px] rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    </div>
  )
}

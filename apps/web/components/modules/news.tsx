"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Loader2, MapPin, Newspaper, Send } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { Dropzone } from "@/components/detect/dropzone"
import { UploadList } from "@/components/detect/upload-list"
import { ControlledField } from "@/components/forms/controlled-field"
import { Markdown } from "@/components/results/explain-reports"
import { JobRow } from "@/components/results/job-row"
import { ProcessingPanel, Timeline } from "@/components/results/processing-panel"
import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useUploads } from "@/hooks/use-uploads"
import { api, data } from "@/lib/api/client"
import { newIdempotencyKey } from "@/lib/api/csrf"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { formatDateTime } from "@/lib/format"

const CATEGORIES = ["conflict", "politics", "disaster", "health", "society", "other"] as const
const VIOLENCE = ["none", "low", "medium", "high"] as const

export function NewsHome() {
  const t = useTranslations("news")
  const router = useRouter()
  const qc = useQueryClient()
  const uploads = useUploads()
  const { data: prices } = useQuery({ queryKey: qk.prices, queryFn: async () => data(await api.GET("/api/v1/credits/prices")) })
  const { data: cases, isLoading } = useQuery({ queryKey: qk.news, queryFn: async () => data(await api.GET("/api/v1/news/cases")),
    refetchInterval: 15_000 })
  const cost = prices?.prices.find((p) => p.key === "news_case")?.credits
  const schema = z.object({
    title: z.string().min(3, t("form.titleRequired")).max(255),
    location: z.string().max(255), category: z.string(), violence_level: z.string(),
    description: z.string().max(10_000), social_media_link: z.union([z.literal(""), z.string().url(t("form.badUrl"))]),
  })
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: {
    title: "", location: "", category: "other", violence_level: "none", description: "", social_media_link: "" } })
  const create = useMutation({
    mutationFn: async (v: z.infer<typeof schema>) => data(await api.POST("/api/v1/news/cases", {
      body: { ...v, media_ids: uploads.ready.map((r) => r.media!.id) },
      params: { header: { "Idempotency-Key": newIdempotencyKey() } } })),
    onSuccess: (job) => { qc.invalidateQueries({ queryKey: qk.news }); qc.invalidateQueries({ queryKey: qk.balance }); router.push(`/app/news/${job.id}`) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={2} title={t("title")} description={t("subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <HudCard>
          <CardHeader><Eyebrow index={1}>{t("form.eyebrow")}</Eyebrow><CardTitle className="text-base">{t("form.title")}</CardTitle>
            <CardDescription>{t("form.hint")}</CardDescription></CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={form.handleSubmit((v) => create.mutate(v))} noValidate>
              <ControlledField control={form.control} name="title" label={t("form.caseTitle")}>{(f) => <Input {...f} />}</ControlledField>
              <div className="grid gap-4 sm:grid-cols-3">
                <ControlledField control={form.control} name="location" label={t("form.location")}>{(f) => <Input {...f} />}</ControlledField>
                <ControlledField control={form.control} name="category" label={t("form.category")}>
                  {(f) => <Select value={f.value} onValueChange={f.onChange}><SelectTrigger id={f.id}><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{t(`category.${c}`)}</SelectItem>)}</SelectContent></Select>}
                </ControlledField>
                <ControlledField control={form.control} name="violence_level" label={t("form.violence")}>
                  {(f) => <Select value={f.value} onValueChange={f.onChange}><SelectTrigger id={f.id}><SelectValue /></SelectTrigger>
                    <SelectContent>{VIOLENCE.map((c) => <SelectItem key={c} value={c}>{t(`violence.${c}`)}</SelectItem>)}</SelectContent></Select>}
                </ControlledField>
              </div>
              <ControlledField control={form.control} name="description" label={t("form.description")} description={t("form.descriptionHint")}>
                {(f) => <Textarea rows={5} {...f} />}
              </ControlledField>
              <ControlledField control={form.control} name="social_media_link" label={t("form.link")}>
                {(f) => <Input type="url" placeholder="https://" {...f} />}
              </ControlledField>
              <div className="space-y-2">
                <p className="text-sm font-medium">{t("form.media")}</p>
                <Dropzone onFiles={uploads.add} compact />
                <UploadList items={uploads.items} onRemove={uploads.remove} onRetry={uploads.retry} />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button type="submit" disabled={create.isPending || uploads.busy}>
                  {create.isPending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />} {t("form.submit")}
                </Button>
                {cost != null && <span className="text-sm text-muted-foreground">{t("form.cost", { count: cost })}</span>}
              </div>
              <p className="text-xs text-muted-foreground">{t("form.duration")}</p>
            </form>
          </CardContent>
        </HudCard>
        <HudCard>
          <CardHeader><Eyebrow index={2}>{t("list.eyebrow")}</Eyebrow><CardTitle className="text-base">{t("list.title")}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {isLoading ? <Skeleton className="h-32" /> : cases?.length ? cases.map((c) => <JobRow key={c.id} job={c} compact />)
              : <p className="py-6 text-center text-sm text-muted-foreground">{t("list.empty")}</p>}
          </CardContent>
        </HudCard>
      </div>
    </div>
  )
}

export function NewsCaseView({ id }: { id: string }) {
  const t = useTranslations("news")
  const locale = useLocale()
  const { data: job, isLoading } = useQuery({
    queryKey: qk.newsCase(id),
    queryFn: async () => data(await api.GET("/api/v1/news/cases/{id}", { params: { path: { id } } })),
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 5000 : false),
  })
  if (isLoading || !job) return <Skeleton className="h-96" />
  const news = job.news && {
    ...job.news,
    meta: job.news.meta as { tags?: string[]; coordinates?: { lat: number; lng: number; label?: string }; when?: string;
      who?: string; sources?: { title?: string; url?: string; date?: string }[] },
  }
  const c = job.case as Record<string, string> | null
  return (
    <div className="space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground"><Link href="/app/news"><ArrowLeft className="size-4" /> {t("back")}</Link></Button>
      <div className="flex flex-wrap items-center gap-3">
        <Newspaper className="size-6 text-primary" />
        <h1 className="text-2xl font-semibold tracking-tight">{job.title}</h1>
        <StatusChip status={job.status} />
        {job.status === "succeeded" && <VerdictBadge verdict={job.verdict} aiGenerated={job.ai_generated} />}
        {news?.status && <Badge variant="outline">{news.status}</Badge>}
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          {news?.report_markdown ? (
            <HudCard><CardHeader><Eyebrow index={1}>{t("report.eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("report.title")}</CardTitle></CardHeader>
              <CardContent><Markdown>{news.report_markdown}</Markdown></CardContent></HudCard>
          ) : (
            <ProcessingPanel job={job} />
          )}
          {news?.report_markdown && <ProcessingPanel job={job} />}
        </div>
        <div className="space-y-5">
          <HudCard>
            <CardHeader><Eyebrow index={2}>{t("case.eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("case.title")}</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {c?.location && <p className="flex items-center gap-1.5"><MapPin className="size-4 text-muted-foreground" />{c.location}</p>}
              {c?.description && <p className="whitespace-pre-wrap text-muted-foreground">{c.description}</p>}
              {c?.["social media link"] && <a className="break-all text-primary underline" href={c["social media link"]} target="_blank" rel="noopener noreferrer">{c["social media link"]}</a>}
              <p className="text-xs text-muted-foreground">{formatDateTime(job.created_at, locale)}</p>
              <div className="flex flex-wrap gap-2 pt-2">
                {(job.case_media ?? []).map((m) => m.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img key={m.id} src={m.thumbnail_url} alt={m.name} className="size-16 rounded-md border object-cover" />
                ) : <Badge key={m.id} variant="outline">{m.name}</Badge>)}
              </div>
            </CardContent>
          </HudCard>
          {news?.meta && (
            <HudCard>
              <CardHeader><Eyebrow index={3}>{t("meta.eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("meta.title")}</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                {news.confidence != null && <p>{t("meta.confidence", { value: news.confidence })}</p>}
                {news.meta.when && <p><span className="text-muted-foreground">{t("meta.when")}:</span> {news.meta.when}</p>}
                {news.meta.who && <p><span className="text-muted-foreground">{t("meta.who")}:</span> {news.meta.who}</p>}
                {news.meta.coordinates && <p className="font-mono text-xs">{news.meta.coordinates.lat.toFixed(5)}, {news.meta.coordinates.lng.toFixed(5)} {news.meta.coordinates.label}</p>}
                {news.meta.tags?.length ? <div className="flex flex-wrap gap-1">{news.meta.tags.map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}</div> : null}
                {news.meta.sources?.length ? (
                  <ul className="space-y-1 pt-1 text-xs">{news.meta.sources.map((s, i) => (
                    <li key={i}><a className="text-primary underline" href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a>{s.date ? ` · ${s.date}` : ""}</li>))}</ul>
                ) : null}
              </CardContent>
            </HudCard>
          )}
          <Timeline events={job.events} />
        </div>
      </div>
    </div>
  )
}

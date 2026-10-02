"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Brain, Download, FileSpreadsheet, FileText, FileArchive, Loader2, Sparkles } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"
import { toast } from "sonner"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { StatusChip } from "@/components/sml/status-chip"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api, data } from "@/lib/api/client"
import { newIdempotencyKey } from "@/lib/api/csrf"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { JobDetail } from "@/lib/api/types"
import { formatBytes, formatDateTime } from "@/lib/format"
import { useCan } from "@/hooks/use-me"

/** `breaks`: a single line break is kept, as in chat messages. */
export function Markdown({ children, breaks = false }: { children: string; breaks?: boolean }) {
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert prose-headings:font-semibold prose-headings:tracking-tight
      [&_h3]:mt-4 [&_h3]:text-sm [&_h3]:uppercase [&_h3]:tracking-wider [&_p]:leading-relaxed [&_a]:text-primary [&_ul]:list-disc [&_ul]:pl-5 [&_table]:text-xs">
      <ReactMarkdown remarkPlugins={breaks ? [remarkGfm, remarkBreaks] : [remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}

export function ExplainCard({ job }: { job: JobDetail }) {
  const t = useTranslations("job.explain")
  const locale = useLocale()
  const qc = useQueryClient()
  const canUse = useCan("use_reasoning")
  const { data: prices } = useQuery({
    queryKey: qk.prices, queryFn: async () => data(await api.GET("/api/v1/credits/prices")), staleTime: 300_000 })
  const cost = prices?.prices.find((p) => p.key === "explain")?.credits
  const latest = job.explanations[0]
  const ask = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/jobs/{id}/explain", {
      params: { path: { id: job.id }, header: { "Idempotency-Key": newIdempotencyKey() } }, body: { locale } as never })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.job(job.id) }); qc.invalidateQueries({ queryKey: qk.balance }) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  if (!canUse || job.status !== "succeeded") return null
  const running = latest && (latest.status === "queued" || latest.status === "running")
  return (
    <HudCard>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <Eyebrow index={6}>{t("eyebrow")}</Eyebrow>
          <CardTitle className="mt-1 flex items-center gap-2 text-base"><Brain className="size-4 text-violet" /> {t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </div>
        {!running && (
          <Button onClick={() => ask.mutate()} disabled={ask.isPending || !!job.purged_at} variant={latest ? "outline" : "default"}>
            {ask.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {latest ? t("again") : t("ask")}{cost != null && ` · ${t("cost", { count: cost })}`}
          </Button>
        )}
      </CardHeader>
      {latest && (
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <StatusChip status={latest.status === "succeeded" ? "succeeded" : latest.status} />
          </div>
          {running && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" /> {t("thinking")}
            </p>
          )}
          {latest.status === "succeeded" && latest.content && <Markdown>{latest.content}</Markdown>}
          {latest.status === "failed" && <p className="text-sm text-fake">{latest.error_message || t("failed")}</p>}
        </CardContent>
      )}
    </HudCard>
  )
}

const FORMATS = [
  { id: "pdf", icon: FileText }, { id: "hwp", icon: FileText }, { id: "csv", icon: FileSpreadsheet },
  { id: "zip", icon: FileArchive },
] as const

export function ReportsCard({ job }: { job: JobDetail }) {
  const t = useTranslations("job.reports")
  const locale = useLocale()
  const qc = useQueryClient()
  const [reportLocale, setReportLocale] = useState(locale)
  const create = useMutation({
    mutationFn: async (format: string) => data(await api.POST("/api/v1/jobs/{id}/reports", {
      params: { path: { id: job.id } }, body: { format, locale: reportLocale } as never })),
    onSuccess: () => { toast.success(t("generating")); qc.invalidateQueries({ queryKey: qk.job(job.id) }) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  if (job.status !== "succeeded") return null
  const reports = job.reports as unknown as { id: string; format: string; locale: string; status: string; version: number;
    size_bytes: number; created_at: string; download_url: string | null; filename: string }[]
  return (
    <HudCard>
      <CardHeader>
        <Eyebrow index={7}>{t("eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("title")}</CardTitle>
        <CardDescription>{t("subtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Select value={reportLocale} onValueChange={setReportLocale}>
            <SelectTrigger size="sm" className="w-32" aria-label={t("language")}><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="ko">한국어</SelectItem>
              <SelectItem value="de">Deutsch</SelectItem>
            </SelectContent>
          </Select>
          {FORMATS.map((f) => (
            <Button key={f.id} size="sm" variant="outline" onClick={() => create.mutate(f.id)} disabled={create.isPending ||
              (f.id === "zip" && !!job.purged_at)}>
              <f.icon className="size-4" /> {t(`format.${f.id}`)}
            </Button>
          ))}
        </div>
        {reports.length > 0 && (
          <ul className="divide-y rounded-lg border text-sm">
            {reports.map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-3 py-2">
                <span className="mono-label w-10">{r.format}</span>
                <span className="text-muted-foreground">{r.locale.toUpperCase()} · v{r.version}</span>
                <span className="text-xs text-muted-foreground">{formatDateTime(r.created_at, locale)}</span>
                <span className="ml-auto flex items-center gap-2">
                  {r.status === "ready" && r.download_url ? (
                    <Button asChild size="sm" variant="ghost">
                      <a href={r.download_url} download={r.filename}><Download className="size-4" /> {formatBytes(r.size_bytes)}</a>
                    </Button>
                  ) : <StatusChip status={r.status === "failed" ? "failed" : "running"} />}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </HudCard>
  )
}

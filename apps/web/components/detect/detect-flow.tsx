"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Coins, Loader2, ShieldAlert } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useMemo, useState } from "react"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { useCatalog } from "@/hooks/use-catalog"
import { quoteRequest, useSubmitJobs } from "@/hooks/use-submit-jobs"
import { useUploads } from "@/hooks/use-uploads"
import { isApiError } from "@/lib/api/errors"

import { AuditPicker, type AuditStep } from "./audit-picker"
import { Dropzone } from "./dropzone"
import { ModelPicker } from "./model-picker"
import { UploadList } from "./upload-list"

export function DetectFlow() {
  const t = useTranslations("detect")
  const router = useRouter()
  const uploads = useUploads()
  const catalog = useCatalog()
  const submit = useSubmitJobs()
  const [models, setModels] = useState<string[] | null>(null)
  const [audit, setAudit] = useState<AuditStep[]>([])

  const mediaTypes = useMemo(
    () => Array.from(new Set(uploads.items.filter((i) => i.kind && i.state !== "invalid").map((i) => i.kind!))),
    [uploads.items],
  )
  const available = catalog.data?.models ?? []

  // Default to the recommended set once the catalog loads.
  useEffect(() => {
    if (models === null && available.length) {
      setModels(available.filter((m) => m.default_selected && m.allowed !== false).map((m) => m.id))
    }
  }, [available, models])

  const selected = models ?? []
  const request = useMemo(() => ({
    media: uploads.ready.map((r) => r.media!), models: selected,
    catalog: available.map((m) => ({ id: m.id, media: m.media })), auditSteps: audit,
  }), [uploads.ready, selected, available, audit])

  const quote = useQuery({
    queryKey: ["quote", request.media.map((m) => m.id), selected, audit],
    queryFn: () => quoteRequest(request),
    enabled: request.media.length > 0 && selected.length > 0,
    retry: false,
  })

  const noModelForType = mediaTypes.filter((mt) => !available.some((m) => selected.includes(m.id) && m.media.includes(mt)))
  const canSubmit = request.media.length > 0 && selected.length > 0 && !uploads.busy && noModelForType.length === 0
    && !submit.isPending && quote.data?.affordable !== false

  const onSubmit = async () => {
    const jobs = await submit.mutateAsync(request)
    uploads.clear()
    router.push(jobs.length === 1 ? `/app/results/${jobs[0].id}` : "/app/results")
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={2} title={t("title")} description={t("subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <HudCard>
            <CardHeader>
              <Eyebrow index={1}>{t("step1")}</Eyebrow>
              <CardTitle className="text-base">{t("filesTitle")}</CardTitle>
              <CardDescription>{t("filesHint")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Dropzone onFiles={uploads.add} />
              <UploadList items={uploads.items} onRemove={uploads.remove} onRetry={uploads.retry} />
            </CardContent>
          </HudCard>

          <HudCard>
            <CardHeader>
              <Eyebrow index={2}>{t("step2")}</Eyebrow>
              <CardTitle className="text-base">{t("modelsTitle")}</CardTitle>
              <CardDescription>{t("modelsHint")}</CardDescription>
            </CardHeader>
            <CardContent>
              {catalog.isLoading ? <Skeleton className="h-48" /> : (
                <ModelPicker models={available} selected={selected} onChange={setModels} mediaTypes={mediaTypes} />
              )}
            </CardContent>
          </HudCard>

          <HudCard>
            <CardHeader>
              <Eyebrow index={3}>{t("step3")}</Eyebrow>
              <CardTitle className="text-base">{t("auditTitle")}</CardTitle>
              <CardDescription>{t("auditHint")}</CardDescription>
            </CardHeader>
            <CardContent>
              {catalog.data && <AuditPicker steps={catalog.data.audit_steps} selected={audit} onChange={setAudit} />}
            </CardContent>
          </HudCard>
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <HudCard>
            <CardHeader>
              <Eyebrow index={4}>{t("step4")}</Eyebrow>
              <CardTitle className="text-base">{t("summaryTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <dl className="space-y-2">
                <div className="flex justify-between"><dt className="text-muted-foreground">{t("filesReady")}</dt>
                  <dd className="font-mono tabular-nums">{uploads.ready.length}/{uploads.items.filter((i) => i.state !== "invalid").length}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">{t("modelsSelected")}</dt>
                  <dd className="font-mono tabular-nums">{selected.length}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">{t("auditSelected")}</dt>
                  <dd className="font-mono tabular-nums">{audit.length + 1}</dd></div>
              </dl>
              <Separator />
              {quote.isFetching ? <Skeleton className="h-16" /> : quote.data ? (
                <div className="space-y-2">
                  <ul className="max-h-40 space-y-1 overflow-auto text-xs text-muted-foreground">
                    {quote.data.lines.map((l, i) => (
                      <li key={i} className="flex justify-between gap-2"><span className="truncate">{l.label}</span>
                        <span className="tabular-nums">{l.credits}</span></li>
                    ))}
                  </ul>
                  <div className="flex items-center justify-between text-base font-semibold">
                    <span className="flex items-center gap-1.5"><Coins className="size-4" /> {t("total")}</span>
                    <span className="font-mono tabular-nums">{t("creditsN", { count: quote.data.credits })}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{t("balanceAfter", { balance: quote.data.balance,
                    after: Math.max(0, quote.data.balance - quote.data.credits) })}</p>
                  <p className="text-xs text-muted-foreground">{t("flatPriceHint")}</p>
                </div>
              ) : quote.isError ? (
                <p className="text-xs text-fake">{isApiError(quote.error) ? quote.error.detail : t("quoteFailed")}</p>
              ) : (
                <p className="text-xs text-muted-foreground">{t("quoteHint")}</p>
              )}
              {quote.data && !quote.data.affordable && (
                <Alert className="border-warn/40 bg-warn/10">
                  <ShieldAlert className="size-4" />
                  <AlertDescription className="space-y-2">
                    <p>{t("notEnough")}</p>
                    <Button asChild size="sm" variant="outline"><Link href="/app/billing">{t("buyCredits")}</Link></Button>
                  </AlertDescription>
                </Alert>
              )}
              {noModelForType.length > 0 && (
                <p className="text-xs text-fake">{t("noModelFor", { types: noModelForType.map((x) => t(x)).join(", ") })}</p>
              )}
              <Button className="w-full" size="lg" disabled={!canSubmit} onClick={onSubmit}>
                {submit.isPending ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
                {t("submit")}
              </Button>
              <p className="text-xs text-muted-foreground">{t("submitHint")}</p>
            </CardContent>
          </HudCard>
        </aside>
      </div>
    </div>
  )
}

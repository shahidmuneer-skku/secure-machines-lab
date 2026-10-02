"use client"

import { AlertTriangle, Info, ScanFace } from "lucide-react"
import { useTranslations } from "next-intl"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { ProbabilityGauge } from "@/components/sml/probability-gauge"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { JobDetail } from "@/lib/api/types"

type Reason = { code: string; reasoning?: string }
type Analysis = JobDetail["analyses"][number]

/**
 * One result per analysis (face swap, AI generation). Users see each analysis' verdict and
 * probability, never how many detectors it combines.
 */
function AnalysisResults({ analyses }: { analyses: Analysis[] }) {
  const t = useTranslations("job.analysis")
  if (!analyses.length) return null
  return (
    <section aria-labelledby="analyses-title" className="space-y-2">
      <h3 id="analyses-title" className="hud-eyebrow">{t("title")}</h3>
      <ul className="space-y-2">
        {analyses.map((a) => (
          <li key={a.id} className="space-y-2 rounded-lg border bg-background/40 p-3">
            <div className="flex flex-col items-start gap-1.5">
              <span className="text-sm font-medium">{t(`name.${a.id}`)}</span>
              {a.status === "failed"
                ? <span className="text-xs text-muted-foreground">{t("failed")}</span>
                : <VerdictBadge verdict={a.verdict} probability={a.fake_probability} size="sm" />}
            </div>
            {a.fake_probability != null && (
              <Progress value={a.fake_probability * 100} aria-label={t("probabilityOf", { name: t(`name.${a.id}`) })}
                className={a.verdict === "fake" ? "h-1.5 [&>[data-slot=progress-indicator]]:bg-fake" : "h-1.5 [&>[data-slot=progress-indicator]]:bg-real"} />
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The combined verdict and why. Users see the result and its evidence, never the detectors. */
export function VerdictPanel({ job }: { job: JobDetail }) {
  const t = useTranslations("job")
  const reasons = (job.verdict_reasons ?? []) as Reason[]
  const done = job.status === "succeeded"

  return (
    <HudCard className="scanline-frame" data-active={job.status === "running"}>
      <CardHeader>
        <Eyebrow index={3}>{t("verdict.eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("verdict.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {done ? (
          <>
            <ProbabilityGauge value={job.fake_probability} label={t("verdict.fakeProbability")} />
            <div className="flex justify-center"><VerdictBadge verdict={job.verdict} aiGenerated={job.ai_generated} size="lg" /></div>
            <AnalysisResults analyses={job.analyses as Analysis[]} />
          </>
        ) : (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <StatusChip status={job.status} />
            <p className="text-sm text-muted-foreground">
              {job.status === "failed" ? job.error_message || t("verdict.failed")
                : job.status === "canceled" ? t("verdict.canceled")
                : job.status === "expired" ? t("verdict.expired") : t("verdict.pending")}
            </p>
          </div>
        )}

        {reasons.length > 0 && (
          <ul className="space-y-2 text-sm">
            {reasons.map((r, i) => (
              <li key={i} className="flex gap-2">
                {r.code === "no_face" ? <ScanFace className="mt-0.5 size-4 shrink-0 text-warn" />
                  : <Info className="mt-0.5 size-4 shrink-0 text-primary" />}
                <span>
                  {t(`reason.${r.code}`)}
                  {r.reasoning ? <span className="block text-xs text-muted-foreground">{r.reasoning}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        )}
        {job.partial && (
          <Alert className="border-warn/40 bg-warn/10"><AlertTriangle className="size-4" />
            <AlertDescription>{t("verdict.partial")}</AlertDescription></Alert>
        )}
        <p className="text-xs text-muted-foreground">{t("disclaimer")}</p>
      </CardContent>
    </HudCard>
  )
}

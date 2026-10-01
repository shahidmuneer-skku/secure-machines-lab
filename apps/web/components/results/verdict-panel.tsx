"use client"

import { AlertTriangle, Camera, FileBadge2, Info, ScanFace, ShieldAlert, ShieldCheck } from "lucide-react"
import { useTranslations } from "next-intl"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { ProbabilityGauge } from "@/components/sml/probability-gauge"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { JobCheck, JobDetail } from "@/lib/api/types"

type Reason = { code: string; strength?: string; evidence?: { detail: string }[]; reasoning?: string }
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
                {r.code === "metadata_ai_indicator" ? <FileBadge2 className="mt-0.5 size-4 shrink-0 text-fake" />
                  : r.code === "no_face" ? <ScanFace className="mt-0.5 size-4 shrink-0 text-warn" />
                  : <Info className="mt-0.5 size-4 shrink-0 text-primary" />}
                <span>
                  {r.code === "metadata_ai_indicator" && r.strength === "weak" ? t("reason.metadata_hint") : t(`reason.${r.code}`)}
                  {r.evidence?.length ? <span className="block text-xs text-muted-foreground">{r.evidence.map((e) => e.detail).join(" · ")}</span> : null}
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

function checkText(check: JobCheck, t: ReturnType<typeof useTranslations>): string {
  if (check.status !== "done") return t(`check.status.${check.status}`)
  const r = check.result as { faces_found?: boolean; sensitive_content?: boolean; spoof_detected?: boolean }
  if (r.faces_found !== undefined) return r.faces_found ? t("check.facesFound") : t("check.noFace")
  if (r.sensitive_content !== undefined) return r.sensitive_content ? t("check.sensitive") : t("check.notSensitive")
  if (r.spoof_detected !== undefined) return r.spoof_detected ? t("check.spoof") : t("check.live")
  return t("check.status.done")
}

/** Metadata / C2PA evidence and the results of the extra checks the administrator runs. */
export function ProvenanceCard({ job }: { job: JobDetail }) {
  const t = useTranslations("job")
  const ind = job.provenance
  const checks = job.checks as JobCheck[]
  if (!ind && !checks.length) return null
  return (
    <HudCard>
      <CardHeader>
        <Eyebrow index={4}>{t("provenance.eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("provenance.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {ind && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              {ind.ai_generated ? <ShieldAlert className="size-5 text-fake" /> : <ShieldCheck className="size-5 text-muted-foreground" />}
              <span className="font-medium">{ind.ai_generated ? t("provenance.aiFound") : ind.evidence.length ? t("provenance.hintFound") : t("provenance.noneFound")}</span>
              <Badge variant="outline">{t(`provenance.confidence.${ind.confidence}`)}</Badge>
            </div>
            {ind.evidence.length > 0 && (
              <ul className="space-y-1.5">
                {ind.evidence.map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <Badge variant="outline" className={e.strength === "strong" ? "border-fake/50 text-fake" : ""}>{e.source}</Badge>
                    <span>{e.detail}</span>
                  </li>
                ))}
              </ul>
            )}
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
              <dt className="mono-label text-muted-foreground"><Camera className="mr-1 inline size-3" />{t("provenance.camera")}</dt>
              <dd>{ind.camera || "—"}</dd>
              <dt className="mono-label text-muted-foreground">{t("provenance.software")}</dt>
              <dd className="break-all">{ind.software || "—"}</dd>
              <dt className="mono-label text-muted-foreground">C2PA</dt>
              <dd>{t.has(`provenance.c2pa.${ind.c2pa_status}`) ? t(`provenance.c2pa.${ind.c2pa_status}`) : ind.c2pa_status}</dd>
            </dl>
            {ind.notes.map((n, i) => <p key={i} className="text-xs text-muted-foreground">{n}</p>)}
          </div>
        )}
        {checks.length > 0 && (
          <div className="space-y-1.5">
            <p className="hud-eyebrow">{t("provenance.checks")}</p>
            {checks.map((c) => (
              <div key={c.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
                <span>{t(`check.name.${c.id}`)}</span>
                <span className={c.status === "failed" ? "text-xs text-warn" : "text-xs text-muted-foreground"}>{checkText(c, t)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </HudCard>
  )
}

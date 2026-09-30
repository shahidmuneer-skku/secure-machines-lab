"use client"

import { AlertTriangle, Camera, FileBadge2, Info, ScanFace, ShieldAlert, ShieldCheck } from "lucide-react"
import { useTranslations } from "next-intl"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { ProbabilityGauge } from "@/components/sml/probability-gauge"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { AiIndicators, JobDetail, TaskView } from "@/lib/api/types"
import { formatDuration, formatPercent } from "@/lib/format"

interface ModelSummary {
  model: string
  name: string
  status: string
  fake_prob: number | null
  no_face: boolean
  weight: number
  duration_ms: number | null
  fallback?: { model: string; reason: string } | null
  error_code?: string
}

export function VerdictPanel({ job, tasks }: { job: JobDetail; tasks: TaskView[] }) {
  const t = useTranslations("job")
  const summary = (job.summary ?? {}) as { models?: ModelSummary[]; ai_indicators?: AiIndicators }
  const reasons = (job.verdict_reasons ?? []) as { code: string; evidence?: { detail: string }[]; reasoning?: string }[]
  const simulated = tasks.some((x) => x.result?.simulated)
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
            <div className="flex justify-center"><VerdictBadge verdict={job.verdict} size="lg" /></div>
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
                  {t(`reason.${r.code}`)}
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
        {simulated && (
          <Alert className="border-warn/40 bg-warn/10"><ShieldAlert className="size-4" />
            <AlertDescription>{t("verdict.simulated")}</AlertDescription></Alert>
        )}

        {summary.models?.length ? (
          <Accordion type="single" collapsible>
            <AccordionItem value="details" className="border-b-0">
              <AccordionTrigger className="text-sm">{t("verdict.details")}</AccordionTrigger>
              <AccordionContent>
                <Table>
                  <TableHeader><TableRow>
                    <TableHead>{t("verdict.model")}</TableHead>
                    <TableHead className="text-right">{t("verdict.fakePct")}</TableHead>
                    <TableHead className="text-right">{t("verdict.weight")}</TableHead>
                    <TableHead className="text-right">{t("verdict.time")}</TableHead>
                  </TableRow></TableHeader>
                  <TableBody>
                    {summary.models.map((m) => (
                      <TableRow key={m.model}>
                        <TableCell>
                          <span className="font-medium">{m.name}</span>
                          {m.fallback && <span className="block text-xs text-violet">{t("fallbackUsed", { model: m.fallback.model })}</span>}
                        </TableCell>
                        <TableCell className="text-right font-mono tabular-nums">
                          {m.no_face ? <span className="text-warn">{t("noFace")}</span>
                            : m.status === "failed" ? <span className="text-fake">{t("verdict.failedShort")}</span>
                            : formatPercent(m.fake_prob)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{m.weight}</TableCell>
                        <TableCell className="text-right tabular-nums">{m.duration_ms ? formatDuration(m.duration_ms / 1000) : "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        ) : null}
        <p className="text-xs text-muted-foreground">{t("disclaimer")}</p>
      </CardContent>
    </HudCard>
  )
}

export function ProvenanceCard({ tasks }: { tasks: TaskView[] }) {
  const t = useTranslations("job")
  const meta = tasks.find((x) => x.kind === "audit" && x.target === "metadata")
  const ind = meta?.result?.ai_indicators
  const audits = tasks.filter((x) => x.kind === "audit" && x.target !== "metadata" && x.status === "succeeded")
  if (!ind && !audits.length) return null
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
              <span className="font-medium">{ind.ai_generated ? t("provenance.aiFound") : t("provenance.noneFound")}</span>
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
              <dd>{t(`provenance.c2pa.${ind.c2pa_status ?? "none"}`)}</dd>
            </dl>
            {ind.notes?.map((n, i) => <p key={i} className="text-xs text-muted-foreground">{n}</p>)}
          </div>
        )}
        {audits.length > 0 && (
          <div className="space-y-1.5">
            <p className="hud-eyebrow">{t("provenance.audit")}</p>
            {audits.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2">
                <span>{a.name}</span>
                <span className="text-xs text-muted-foreground">{a.result?.summary ?? t("provenance.completed")}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </HudCard>
  )
}

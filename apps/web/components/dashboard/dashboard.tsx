"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Clock, Coins, Gauge, ListChecks, ScanSearch, Table2 } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"
import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis, LabelList } from "recharts"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig,
} from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { JobRow } from "@/components/results/job-row"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatDuration, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

import { QuickUpload } from "./quick-upload"

const RANGES = [7, 30, 90] as const

function StatTile({ label, value, hint, icon: Icon, tone }: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  icon: typeof Gauge
  tone?: "warn"
}) {
  return (
    <HudCard className="gap-2 py-4">
      <CardContent className="space-y-1 px-4">
        <div className="flex items-center justify-between">
          <span className="mono-label text-muted-foreground">{label}</span>
          <Icon className={cn("size-4 text-muted-foreground", tone === "warn" && "text-warn")} aria-hidden />
        </div>
        <div className="font-mono text-2xl font-semibold tabular-nums">{value}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </HudCard>
  )
}

function shortDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" }).format(new Date(value))
}

export function Dashboard() {
  const t = useTranslations("dashboard")
  const locale = useLocale()
  const [days, setDays] = useState<(typeof RANGES)[number]>(30)
  const [tableView, setTableView] = useState(false)
  const { data: summary, isLoading, isError, refetch } = useQuery({
    queryKey: qk.dashboard(days),
    queryFn: async () => data(await api.GET("/api/v1/dashboard/summary", { params: { query: { days } } as never })),
    refetchInterval: 30_000,
  })

  const verdictConfig = {
    fake: { label: t("series.fake"), color: "var(--viz-fake)" },
    real: { label: t("series.real"), color: "var(--viz-real)" },
    other: { label: t("series.other"), color: "var(--viz-other)" },
  } satisfies ChartConfig
  const creditsConfig = {
    added: { label: t("series.added"), color: "var(--viz-real)" },
    spent: { label: t("series.spent"), color: "var(--viz-other)" },
  } satisfies ChartConfig
  const modelConfig = { runs: { label: t("series.runs"), color: "var(--viz-real)" } } satisfies ChartConfig
  const waitConfig = { avg_seconds: { label: t("series.wait"), color: "var(--viz-real)" } } satisfies ChartConfig

  const k = summary?.kpis
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={1} title={t("title")} description={t("subtitle")}
        actions={
          <>
            <ToggleGroup type="single" value={String(days)} variant="outline" size="sm"
              onValueChange={(v) => v && setDays(Number(v) as (typeof RANGES)[number])} aria-label={t("range")}>
              {RANGES.map((r) => <ToggleGroupItem key={r} value={String(r)}>{t("days", { count: r })}</ToggleGroupItem>)}
            </ToggleGroup>
            <Button asChild><Link href="/app/detect"><ScanSearch className="size-4" /> {t("newDetection")}</Link></Button>
          </>
        } />

      {isError && (
        <HudCard><CardContent className="flex items-center justify-between py-4">
          <span className="text-sm">{t("loadError")}</span>
          <Button variant="outline" size="sm" onClick={() => refetch()}>{t("retry")}</Button>
        </CardContent></HudCard>
      )}

      <section aria-label={t("kpis")} className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {isLoading || !k ? (
          Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <StatTile label={t("kpi.balance")} icon={Coins} tone={k.low_balance ? "warn" : undefined}
              value={k.unlimited ? "∞" : k.balance}
              hint={k.held ? t("kpi.held", { count: k.held }) : k.low_balance ? t("kpi.low") : t("kpi.credits")} />
            <StatTile label={t("kpi.jobs")} icon={ListChecks} value={k.jobs_in_period} hint={t("days", { count: days })} />
            <StatTile label={t("kpi.fakeRate")} icon={Gauge} value={formatPercent(k.fake_rate, 0)} hint={t("kpi.fakeRateHint")} />
            <StatTile label={t("kpi.turnaround")} icon={Clock} value={formatDuration(k.avg_turnaround_seconds)}
              hint={t("kpi.turnaroundHint")} />
            <StatTile label={t("kpi.inQueue")} icon={ListChecks} value={k.in_queue} hint={t("kpi.inQueueHint")} />
          </>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <HudCard className="lg:col-span-2">
          <CardHeader className="flex flex-row items-start justify-between gap-2">
            <div>
              <Eyebrow index={2}>{t("jobsChart.eyebrow")}</Eyebrow>
              <CardTitle className="mt-1 text-base">{t("jobsChart.title")}</CardTitle>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setTableView((v) => !v)} aria-pressed={tableView}>
              <Table2 className="size-4" /> {tableView ? t("showChart") : t("showTable")}
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-64" /> : !summary?.jobs_by_day.length ? (
              <EmptyChart label={t("noData")} />
            ) : tableView ? (
              <Table>
                <TableHeader><TableRow>
                  <TableHead>{t("date")}</TableHead><TableHead className="text-right">{verdictConfig.fake.label}</TableHead>
                  <TableHead className="text-right">{verdictConfig.real.label}</TableHead>
                  <TableHead className="text-right">{verdictConfig.other.label}</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {summary.jobs_by_day.map((r) => (
                    <TableRow key={r.date}>
                      <TableCell>{shortDate(r.date, locale)}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.fake}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.real}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.other}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <ChartContainer config={verdictConfig} className="h-64 w-full">
                <BarChart data={summary.jobs_by_day} margin={{ left: -16, right: 8 }} barCategoryGap="28%">
                  <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24}
                    tickFormatter={(v) => shortDate(v, locale)} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={40} />
                  <ChartTooltip cursor={{ fill: "var(--accent)" }}
                    content={<ChartTooltipContent labelFormatter={(v) => shortDate(String(v), locale)} />} />
                  <ChartLegend content={<ChartLegendContent />} verticalAlign="top" />
                  {/* 2px surface gap between stacked segments; only the top segment is rounded */}
                  <Bar dataKey="real" stackId="v" fill="var(--color-real)" stroke="var(--card)" strokeWidth={2} />
                  <Bar dataKey="other" stackId="v" fill="var(--color-other)" stroke="var(--card)" strokeWidth={2} />
                  <Bar dataKey="fake" stackId="v" fill="var(--color-fake)" stroke="var(--card)" strokeWidth={2}
                    radius={[4, 4, 0, 0]} />
                </BarChart>
              </ChartContainer>
            )}
          </CardContent>
        </HudCard>

        <HudCard>
          <CardHeader>
            <Eyebrow index={3}>{t("quick.eyebrow")}</Eyebrow>
            <CardTitle className="mt-1 text-base">{t("quick.title")}</CardTitle>
            <CardDescription>{t("quick.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent><QuickUpload /></CardContent>
        </HudCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <HudCard>
          <CardHeader>
            <Eyebrow index={4}>{t("modelChart.eyebrow")}</Eyebrow>
            <CardTitle className="mt-1 text-base">{t("modelChart.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-56" /> : !summary?.usage_by_model.length ? <EmptyChart label={t("noData")} /> : (
              <ChartContainer config={modelConfig} className="h-56 w-full">
                <BarChart data={summary.usage_by_model} layout="vertical" margin={{ left: 8, right: 32 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="target" type="category" tickLine={false} axisLine={false} width={96} />
                  <ChartTooltip cursor={{ fill: "var(--accent)" }} content={<ChartTooltipContent hideIndicator />} />
                  <Bar dataKey="runs" fill="var(--color-runs)" radius={[0, 4, 4, 0]} barSize={14}>
                    <LabelList dataKey="runs" position="right" className="fill-muted-foreground" fontSize={11} />
                  </Bar>
                </BarChart>
              </ChartContainer>
            )}
          </CardContent>
        </HudCard>

        <HudCard>
          <CardHeader>
            <Eyebrow index={5}>{t("creditsChart.eyebrow")}</Eyebrow>
            <CardTitle className="mt-1 text-base">{t("creditsChart.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-56" /> : !summary?.credits_by_day.length ? <EmptyChart label={t("noData")} /> : (
              <ChartContainer config={creditsConfig} className="h-56 w-full">
                <BarChart data={summary.credits_by_day} margin={{ left: -16, right: 8 }} barGap={2}>
                  <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24}
                    tickFormatter={(v) => shortDate(v, locale)} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={40} />
                  <ChartTooltip cursor={{ fill: "var(--accent)" }}
                    content={<ChartTooltipContent labelFormatter={(v) => shortDate(String(v), locale)} />} />
                  <ChartLegend content={<ChartLegendContent />} verticalAlign="top" />
                  <Bar dataKey="added" fill="var(--color-added)" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="spent" fill="var(--color-spent)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ChartContainer>
            )}
          </CardContent>
        </HudCard>

        <HudCard>
          <CardHeader>
            <Eyebrow index={6}>{t("waitChart.eyebrow")}</Eyebrow>
            <CardTitle className="mt-1 text-base">{t("waitChart.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-56" /> : !summary?.queue_wait_by_day.length ? <EmptyChart label={t("noData")} /> : (
              <ChartContainer config={waitConfig} className="h-56 w-full">
                <LineChart data={summary.queue_wait_by_day} margin={{ left: -8, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24}
                    tickFormatter={(v) => shortDate(v, locale)} />
                  <YAxis tickLine={false} axisLine={false} width={44} tickFormatter={(v) => formatDuration(Number(v))} />
                  <ChartTooltip content={<ChartTooltipContent labelFormatter={(v) => shortDate(String(v), locale)}
                    formatter={(v) => formatDuration(Number(v))} />} />
                  <Line dataKey="avg_seconds" stroke="var(--color-avg_seconds)" strokeWidth={2}
                    dot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }} activeDot={{ r: 5 }} />
                </LineChart>
              </ChartContainer>
            )}
          </CardContent>
        </HudCard>
      </div>

      <HudCard>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <Eyebrow index={7}>{t("recent.eyebrow")}</Eyebrow>
            <CardTitle className="mt-1 text-base">{t("recent.title")}</CardTitle>
          </div>
          <Button asChild variant="ghost" size="sm"><Link href="/app/results">{t("recent.all")} <ArrowRight className="size-4" /></Link></Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {isLoading ? Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-16" />) :
            summary?.recent_jobs.length ? summary.recent_jobs.map((job) => <JobRow key={job.id} job={job} compact />) : (
              <p className="py-6 text-center text-sm text-muted-foreground">{t("recent.empty")}</p>
            )}
        </CardContent>
      </HudCard>

      {summary && summary.api_usage.requests > 0 && (
        <HudCard>
          <CardContent className="flex flex-wrap items-center gap-6 py-4 text-sm">
            <span className="mono-label text-muted-foreground">{t("api.title")}</span>
            <span>{t("api.requests", { count: summary.api_usage.requests })}</span>
            <span>{t("api.jobs", { count: summary.api_usage.jobs })}</span>
            <span>{t("api.credits", { count: summary.api_usage.credits })}</span>
            <Button asChild variant="link" size="sm" className="ml-auto"><Link href="/app/api-keys">{t("api.manage")}</Link></Button>
          </CardContent>
        </HudCard>
      )}
    </div>
  )
}

function EmptyChart({ label }: { label: string }) {
  return <div className="flex h-48 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">{label}</div>
}

"use client"

import Timeline from "@mui/lab/Timeline"
import TimelineConnector from "@mui/lab/TimelineConnector"
import TimelineContent from "@mui/lab/TimelineContent"
import TimelineDot from "@mui/lab/TimelineDot"
import TimelineItem, { timelineItemClasses } from "@mui/lab/TimelineItem"
import TimelineOppositeContent from "@mui/lab/TimelineOppositeContent"
import TimelineSeparator from "@mui/lab/TimelineSeparator"
import Avatar from "@mui/material/Avatar"
import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Card from "@mui/material/Card"
import CardContent from "@mui/material/CardContent"
import Chip from "@mui/material/Chip"
import IconButton from "@mui/material/IconButton"
import LinearProgress from "@mui/material/LinearProgress"
import MenuItem from "@mui/material/MenuItem"
import Select from "@mui/material/Select"
import Stack from "@mui/material/Stack"
import Table from "@mui/material/Table"
import TableBody from "@mui/material/TableBody"
import TableCell from "@mui/material/TableCell"
import TableHead from "@mui/material/TableHead"
import TableRow from "@mui/material/TableRow"
import Tooltip from "@mui/material/Tooltip"
import Typography from "@mui/material/Typography"
import {
  IconArrowRight, IconChartBar, IconClock, IconCoins, IconGauge, IconListCheck, IconMovie, IconNews, IconPhoto,
  IconPhotoScan, IconSparkles, IconTable, IconTrendingDown, type Icon,
} from "@tabler/icons-react"
import type { ApexOptions } from "apexcharts"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useState, type ReactNode } from "react"

import { LogoMark } from "@/components/brand/logo"
import { Chart, useChartColors } from "@/components/mui/chart"
import { DashboardCard } from "@/components/mui/dashboard-card"
import type { Schemas } from "@/lib/api/client"
import type { Job } from "@/lib/api/types"
import { formatRelative } from "@/lib/format"

export type Summary = Schemas["DashboardSummary"]
export const RANGES = [7, 30, 90] as const
export type Range = (typeof RANGES)[number]

const shortDate = (value: string, locale: string) =>
  new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" }).format(new Date(value))

// --- welcome --------------------------------------------------------------------------------------

/** Illustration for the welcome banner: a photo being scanned and checked. */
function ScanIllustration() {
  return (
    // Shown only when the banner itself is wide enough (container query on the card).
    <Box component="svg" viewBox="0 0 260 180" aria-hidden
      sx={{ width: 250, flexShrink: 0, height: "auto", display: "none", "@container (min-width: 680px)": { display: "block" } }}>
      <defs>
        <linearGradient id="sml-g1" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5d87ff" /><stop offset="1" stopColor="#49beff" />
        </linearGradient>
      </defs>
      <circle cx="190" cy="70" r="62" fill="#5d87ff" opacity="0.10" />
      <rect x="40" y="26" width="132" height="122" rx="12" fill="#ffffff" stroke="#c9d6f7" strokeWidth="2" />
      <rect x="52" y="38" width="108" height="78" rx="7" fill="#ecf2ff" />
      <circle cx="106" cy="70" r="17" fill="#c9d6f7" />
      <path d="M78 116c4-17 15-26 28-26s24 9 28 26" fill="#c9d6f7" />
      <rect x="52" y="74" width="108" height="3" rx="1.5" fill="url(#sml-g1)" opacity="0.85" />
      <rect x="52" y="124" width="68" height="7" rx="3.5" fill="#dfe5ef" />
      <rect x="52" y="136" width="44" height="6" rx="3" fill="#eaeff4" />
      {/* a round "checked" badge, so it doesn't compete with the company shield beside the greeting */}
      <circle cx="190" cy="100" r="33" fill="url(#sml-g1)" />
      <path d="M176 101l10 10 19-20" fill="none" stroke="#fff" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
    </Box>
  )
}

export function WelcomeCard({ name, summary, days, canStudio }: {
  name: string
  summary?: Summary
  days: number
  canStudio: boolean
}) {
  const t = useTranslations("dashboard")
  const k = summary?.kpis
  const fakes = (summary?.jobs_by_day ?? []).reduce((n, r) => n + r.fake, 0)
  return (
    <Card sx={{ bgcolor: "primary.light", boxShadow: "none", position: "relative", overflow: "hidden", height: "100%", containerType: "inline-size" }}>
      <CardContent sx={{ p: { xs: 3, md: 4 }, "&:last-child": { pb: { xs: 3, md: 4 } } }}>
        <Stack direction="row" spacing={3} sx={{ alignItems: "center", justifyContent: "space-between" }}>
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mb: 2 }}>
              <LogoMark className="h-12" />
              <Box>
                <Typography sx={{ fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "primary.main" }}>
                  Secure Machines Lab
                </Typography>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 700 }}>{t("welcome.greeting", { name })}</Typography>
              </Box>
            </Stack>
            <Typography variant="subtitle1" sx={{ color: "text.secondary", maxWidth: 520 }}>{t("welcome.subtitle")}</Typography>
            <Stack direction="row" spacing={4} sx={{ mt: 3 }}>
              <Box>
                <Typography variant="h3" sx={{ fontWeight: 700 }}>{k ? k.jobs_in_period.toLocaleString() : "—"}</Typography>
                <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>{t("welcome.analyses", { days })}</Typography>
              </Box>
              <Box sx={{ borderLeft: "1px solid", borderColor: "divider", pl: 4 }}>
                <Typography variant="h3" sx={{ fontWeight: 700, color: "error.main" }}>{summary ? fakes.toLocaleString() : "—"}</Typography>
                <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>{t("welcome.manipulated")}</Typography>
              </Box>
            </Stack>
            <Stack direction="row" spacing={1.5} useFlexGap sx={{ mt: 3, flexWrap: "wrap" }}>
              <Button component={Link} href="/app/detect" variant="contained" startIcon={<IconPhotoScan size={18} />}>
                {t("newDetection")}
              </Button>
              {canStudio && (
                <Button component={Link} href="/app/studio" variant="outlined" startIcon={<IconSparkles size={18} />}
                  sx={{ bgcolor: "background.paper" }}>
                  {t("welcome.studio")}
                </Button>
              )}
            </Stack>
          </Box>
          <ScanIllustration />
        </Stack>
      </CardContent>
    </Card>
  )
}

// --- stat tiles ------------------------------------------------------------------------------------

type Tone = "primary" | "error" | "secondary" | "warning" | "success"

export function StatCard({ icon: ItemIcon, tone, label, value, hint }: {
  icon: Icon
  tone: Tone
  label: string
  value: ReactNode
  hint?: ReactNode
}) {
  return (
    <Card sx={{ height: "100%", boxShadow: "none", bgcolor: `${tone}.light` }}>
      <CardContent sx={{ p: 3, "&:last-child": { pb: 3 } }}>
        <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
          <Avatar variant="rounded" sx={{ bgcolor: "background.paper", color: `${tone}.main`, width: 48, height: 48, borderRadius: "10px" }}>
            <ItemIcon size={24} stroke={1.6} />
          </Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle2" sx={{ color: "text.secondary", fontWeight: 600, lineHeight: 1.3 }}>{label}</Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: `${tone}.main`, fontVariantNumeric: "tabular-nums" }}>{value}</Typography>
          </Box>
        </Stack>
        {hint && <Typography variant="body2" sx={{ color: "text.secondary", mt: 1.5 }}>{hint}</Typography>}
      </CardContent>
    </Card>
  )
}

export const KPI_ICONS = { jobs: IconListCheck, fakeRate: IconGauge, turnaround: IconClock, inQueue: IconChartBar }

// --- analyses overview ------------------------------------------------------------------------

export function AnalysesOverview({ summary, days, onDays }: { summary?: Summary; days: Range; onDays: (d: Range) => void }) {
  const t = useTranslations("dashboard")
  const locale = useLocale()
  const colors = useChartColors()
  const [table, setTable] = useState(false)
  const rows = summary?.jobs_by_day ?? []
  const dense = rows.length > 40
  const series = [
    { name: t("series.real"), data: rows.map((r) => r.real) },
    { name: t("series.fake"), data: rows.map((r) => r.fake) },
    { name: t("series.other"), data: rows.map((r) => r.other) },
  ]
  const options: ApexOptions = {
    chart: { type: "bar", stacked: true, toolbar: { show: false }, fontFamily: "inherit", foreColor: colors.text,
      background: "transparent", animations: { speed: 300 } },
    colors: [colors.verdict.real, colors.verdict.fake, colors.verdict.other],
    plotOptions: { bar: { columnWidth: dense ? "70%" : "45%", borderRadius: dense ? 2 : 4, borderRadiusApplication: "end",
      borderRadiusWhenStacked: "last" } },
    // The surface-coloured stroke is the gap between stacked segments; it is drawn around the whole bar, so it
    // thins out where bars are narrow (90 days, phones) and would otherwise swallow them.
    stroke: { show: true, width: dense ? 1 : 2, colors: [colors.surface] },
    responsive: [{ breakpoint: 600, options: { stroke: { width: dense ? 0 : 1 },
      plotOptions: { bar: { columnWidth: dense ? "90%" : "65%", borderRadius: 2 } } } }],
    dataLabels: { enabled: false },
    legend: { position: "top", horizontalAlign: "left", fontWeight: 500, markers: { size: 6 } },
    grid: { borderColor: colors.grid, strokeDashArray: 3, xaxis: { lines: { show: false } } },
    xaxis: { categories: rows.map((r) => shortDate(r.date, locale)), axisBorder: { show: false }, axisTicks: { show: false },
      labels: { rotate: 0, hideOverlappingLabels: true } },
    yaxis: { tickAmount: 4, labels: { formatter: (v) => String(Math.round(v)) } },
    tooltip: { theme: colors.dark ? "dark" : "light", shared: true, intersect: false },
    theme: { mode: colors.dark ? "dark" : "light" },
  }
  return (
    <DashboardCard title={t("jobsChart.title")} subtitle={t("jobsChart.subtitle", { days })}
      action={
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Tooltip title={table ? t("showChart") : t("showTable")}>
            <IconButton size="small" onClick={() => setTable((v) => !v)} aria-pressed={table}
              aria-label={table ? t("showChart") : t("showTable")}><IconTable size={19} /></IconButton>
          </Tooltip>
          <Select size="small" value={days} onChange={(e) => onDays(Number(e.target.value) as Range)} aria-label={t("range")}
            sx={{ minWidth: 120 }}>
            {RANGES.map((r) => <MenuItem key={r} value={r}>{t("days", { count: r })}</MenuItem>)}
          </Select>
        </Stack>
      }>
      {!rows.length ? <EmptyState label={t("noData")} height={320} /> : table ? (
        <Box sx={{ maxHeight: 330, overflow: "auto" }}>
          <Table size="small">
            <TableHead><TableRow>
              <TableCell>{t("date")}</TableCell><TableCell align="right">{t("series.real")}</TableCell>
              <TableCell align="right">{t("series.fake")}</TableCell><TableCell align="right">{t("series.other")}</TableCell>
            </TableRow></TableHead>
            <TableBody>{rows.map((r) => (
              <TableRow key={r.date}><TableCell>{shortDate(r.date, locale)}</TableCell><TableCell align="right">{r.real}</TableCell>
                <TableCell align="right">{r.fake}</TableCell><TableCell align="right">{r.other}</TableCell></TableRow>
            ))}</TableBody>
          </Table>
        </Box>
      ) : (
        <Box sx={{ mx: -1 }}><Chart type="bar" height={392} width="100%" options={options} series={series} /></Box>
      )}
    </DashboardCard>
  )
}

// --- verdict breakdown (donut) -------------------------------------------------------------------

export function VerdictBreakdown({ summary, sx }: { summary?: Summary; sx?: object }) {
  const t = useTranslations("dashboard")
  const colors = useChartColors()
  const rows = summary?.jobs_by_day ?? []
  const totals = rows.reduce((acc, r) => ({ real: acc.real + r.real, fake: acc.fake + r.fake, other: acc.other + r.other }),
    { real: 0, fake: 0, other: 0 })
  const total = totals.real + totals.fake + totals.other
  const fakeRate = summary?.kpis.fake_rate
  const items = [
    { key: "real", label: t("series.real"), value: totals.real, color: colors.verdict.real },
    { key: "fake", label: t("series.fake"), value: totals.fake, color: colors.verdict.fake },
    { key: "other", label: t("series.other"), value: totals.other, color: colors.verdict.other },
  ]
  const options: ApexOptions = {
    chart: { type: "donut", fontFamily: "inherit", foreColor: colors.text, background: "transparent" },
    colors: items.map((i) => i.color),
    labels: items.map((i) => i.label),
    stroke: { width: 2, colors: [colors.surface] },
    plotOptions: { pie: { donut: { size: "72%", labels: { show: true, name: { show: true, offsetY: 18 },
      value: { show: true, offsetY: -14, fontSize: "22px", fontWeight: 700, color: colors.dark ? "#eaeff4" : "#2a3547" },
      total: { show: true, label: t("verdicts.total"), color: colors.text, fontSize: "12px", formatter: () => String(total) } } } } },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: { theme: colors.dark ? "dark" : "light", fillSeriesColor: false },
  }
  return (
    <DashboardCard title={t("verdicts.title")} sx={sx}>
      {!total ? <EmptyState label={t("noData")} height={200} /> : (
        <>
          <Stack direction="row" spacing={2} sx={{ alignItems: "center", justifyContent: "space-between" }}>
            <Box>
              <Typography variant="h3" sx={{ fontWeight: 700 }}>
                {fakeRate == null ? "—" : `${Math.round(fakeRate * 100)}%`}
              </Typography>
              <Typography variant="subtitle2" sx={{ color: "text.secondary", whiteSpace: "nowrap" }}>{t("kpi.fakeRate")}</Typography>
            </Box>
            <Box sx={{ width: 170, flexShrink: 0 }}>
              <Chart type="donut" height={180} width="100%" options={options} series={items.map((i) => i.value)} />
            </Box>
          </Stack>
          <Stack spacing={1} sx={{ mt: 1.5 }}>
            {items.map((i) => (
              <Stack key={i.key} direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: i.color, flexShrink: 0 }} />
                <Typography variant="subtitle2" sx={{ color: "text.secondary", flex: 1 }}>{i.label}</Typography>
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{i.value}</Typography>
              </Stack>
            ))}
          </Stack>
        </>
      )}
    </DashboardCard>
  )
}

// --- credits (sparkline) ----------------------------------------------------------------------

export function CreditsCard({ summary, days }: { summary?: Summary; days: number }) {
  const t = useTranslations()
  const colors = useChartColors()
  const k = summary?.kpis
  const spent = summary?.credits_by_day ?? []
  const options: ApexOptions = {
    chart: { type: "area", sparkline: { enabled: true }, fontFamily: "inherit", background: "transparent",
      toolbar: { show: false } },
    colors: [colors.blue],
    stroke: { curve: "smooth", width: 2 },
    fill: { type: "gradient", gradient: { shadeIntensity: 0, opacityFrom: 0.25, opacityTo: 0.02 } },
    tooltip: { theme: colors.dark ? "dark" : "light", x: { show: false },
      y: { formatter: (v) => `${v} ${t("credits.credits")}`, title: { formatter: () => t("dashboard.series.spent") } } },
  }
  return (
    <DashboardCard title={t("dashboard.credits.title")}
      action={<Avatar sx={{ bgcolor: "secondary.light", color: "secondary.main", width: 44, height: 44 }}><IconCoins size={24} /></Avatar>}
      footer={spent.length ? <Chart type="area" height={70} width="100%" options={options}
        series={[{ name: t("dashboard.series.spent"), data: spent.map((r) => r.spent) }]} /> : undefined}>
      <Typography variant="h3" sx={{ fontWeight: 700, mt: -1.5 }}>
        {k ? (k.unlimited ? "∞" : k.balance.toLocaleString()) : "—"}
        <Typography component="span" variant="subtitle1" sx={{ color: "text.secondary", ml: 1 }}>{t("credits.credits")}</Typography>
      </Typography>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", my: 1.5 }}>
        <Avatar sx={{ bgcolor: "error.light", color: "error.main", width: 27, height: 27 }}><IconTrendingDown size={18} /></Avatar>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{(k?.credits_spent ?? 0).toLocaleString()}</Typography>
        <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>{t("dashboard.credits.spent", { days })}</Typography>
      </Stack>
      {k?.held ? <Typography variant="body2" sx={{ color: "text.secondary" }}>{t("dashboard.kpi.held", { count: k.held })}</Typography> : null}
      <Button component={Link} href="/app/billing" size="small" endIcon={<IconArrowRight size={16} />} sx={{ mt: 1, px: 0 }}>
        {t("credits.buy")}
      </Button>
    </DashboardCard>
  )
}

// --- recent activity (timeline) & results (table) -------------------------------------------------

const jobHref = (job: Job) => (job.kind === "studio" ? "/app/studio" : job.kind === "news" ? `/app/news/${job.id}` : `/app/results/${job.id}`)

type Dot = "primary" | "secondary" | "success" | "warning" | "error" | "grey"
function dotFor(job: Job): Dot {
  if (job.status === "queued" || job.status === "running") return "primary"
  if (job.status === "failed") return "warning"
  if (job.kind === "studio") return "secondary"
  if (job.verdict === "fake") return "error"
  if (job.verdict === "real") return "success"
  return "grey"
}

function verdictLabel(job: Job, t: ReturnType<typeof useTranslations>): string {
  if (job.status !== "succeeded") return t(`status.${job.status}`)
  if (job.kind === "studio") return t("dashboard.activity.studioDone")
  if (job.verdict === "fake" && job.ai_generated) return t("verdict.ai_generated")
  return job.verdict ? t(`verdict.${job.verdict}`) : t("status.succeeded")
}

export function RecentActivity({ summary }: { summary?: Summary }) {
  const t = useTranslations()
  const locale = useLocale()
  const jobs = (summary?.recent_jobs ?? []) as Job[]
  return (
    <DashboardCard title={t("dashboard.activity.title")}>
      {!jobs.length ? <EmptyState label={t("dashboard.recent.empty")} height={240} /> : (
        <Timeline sx={{ p: 0, m: 0, [`& .${timelineItemClasses.root}:before`]: { flex: 0, p: 0 },
          "& .MuiTimelineConnector-root": { width: "1px", bgcolor: "divider" } }}>
          {jobs.map((job, i) => (
            <TimelineItem key={job.id} sx={{ minHeight: 64 }}>
              <TimelineOppositeContent sx={{ flex: "0 0 104px", pl: 0, pr: 1.5, pt: 0.75, textAlign: "right" }}>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>{formatRelative(job.created_at, locale)}</Typography>
              </TimelineOppositeContent>
              <TimelineSeparator>
                <TimelineDot variant="outlined" color={dotFor(job) === "grey" ? "grey" : dotFor(job)} sx={{ my: 1 }} />
                {i < jobs.length - 1 && <TimelineConnector />}
              </TimelineSeparator>
              <TimelineContent sx={{ pt: 0.5, pr: 0, minWidth: 0 }}>
                <Typography component={Link} href={jobHref(job)} variant="subtitle2"
                  sx={{ fontWeight: 600, color: "text.primary", textDecoration: "none", display: "block", "&:hover": { color: "primary.main" } }} noWrap>
                  {job.title || t("results.untitled")}
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>{verdictLabel(job, t)}</Typography>
              </TimelineContent>
            </TimelineItem>
          ))}
        </Timeline>
      )}
    </DashboardCard>
  )
}

const WIDE = { xs: "none", sm: "table-cell" } as const
const KIND_ICON: Record<string, Icon> = { detect: IconPhoto, long_video: IconMovie, news: IconNews, studio: IconSparkles }

function VerdictChip({ job }: { job: Job }) {
  const t = useTranslations()
  const tone = dotFor(job)
  const pct = job.status === "succeeded" && job.fake_probability != null && job.kind !== "studio"
    ? ` · ${Math.round(job.fake_probability * 100)}%` : ""
  return (
    <Chip size="small" label={`${verdictLabel(job, t)}${pct}`}
      sx={{ bgcolor: tone === "grey" ? "grey.100" : `${tone}.light`, color: tone === "grey" ? "text.secondary" : `${tone}.main` }} />
  )
}

export function RecentResults({ summary }: { summary?: Summary }) {
  const t = useTranslations()
  const locale = useLocale()
  const jobs = (summary?.recent_jobs ?? []) as Job[]
  return (
    <DashboardCard title={t("dashboard.recent.title")}
      action={<Button component={Link} href="/app/results" size="small" endIcon={<IconArrowRight size={16} />}>{t("dashboard.recent.all")}</Button>}>
      {!jobs.length ? <EmptyState label={t("dashboard.recent.empty")} height={240} /> : (
        <Box sx={{ overflowX: "auto", mx: { xs: -2.5, md: -3.75 }, px: { xs: 2.5, md: 3.75 } }}>
          {/* Phones show file and result only; the job page has the rest. */}
          <Table sx={{ whiteSpace: "nowrap", tableLayout: "fixed", minWidth: { sm: 560 } }}>
            <TableHead>
              <TableRow>
                <TableCell sx={{ pl: 0, width: { xs: "56%", sm: "40%" } }}>{t("dashboard.table.file")}</TableCell>
                <TableCell sx={{ width: { xs: "44%", sm: "32%" }, pr: { xs: 0, sm: 2 } }}>{t("dashboard.table.result")}</TableCell>
                <TableCell align="right" sx={{ width: "10%", display: WIDE }}>{t("dashboard.table.credits")}</TableCell>
                <TableCell align="right" sx={{ pr: 0, width: "18%", display: WIDE }}>{t("dashboard.table.when")}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {jobs.map((job) => {
                const KindIcon = job.kind === "detect" && job.media_type === "video" ? IconMovie : KIND_ICON[job.kind] ?? IconPhoto
                return (
                  <TableRow key={job.id} hover>
                    <TableCell sx={{ pl: 0, overflow: "hidden" }}>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", minWidth: 0 }}>
                        <Avatar variant="rounded" sx={{ bgcolor: "primary.light", color: "primary.main", width: 40, height: 40, borderRadius: "8px" }}>
                          <KindIcon size={20} stroke={1.6} />
                        </Avatar>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography component={Link} href={jobHref(job)} variant="subtitle2" noWrap
                            sx={{ fontWeight: 600, color: "text.primary", textDecoration: "none", display: "block", "&:hover": { color: "primary.main" } }}>
                            {job.title || t("results.untitled")}
                          </Typography>
                          <Typography variant="body2" sx={{ color: "text.secondary" }}>{t(`results.kind.${job.kind}`)}</Typography>
                        </Box>
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ overflow: "hidden", pr: { xs: 0, sm: 2 } }}><VerdictChip job={job} /></TableCell>
                    <TableCell align="right" sx={{ display: WIDE }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{job.credits_charged || job.credits_quoted || 0}</Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ pr: 0, overflow: "hidden", display: WIDE }}>
                      <Typography variant="subtitle2" sx={{ color: "text.secondary" }} noWrap>{formatRelative(job.created_at, locale)}</Typography>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Box>
      )}
    </DashboardCard>
  )
}

// --- usage by type ------------------------------------------------------------------------------

// One measure across labelled categories: a single hue, the label carries identity.
export function UsageByType({ summary, sx }: { summary?: Summary; sx?: object }) {
  const t = useTranslations("dashboard")
  const usage = summary?.usage_by_type ?? []
  const max = Math.max(1, ...usage.map((u) => u.jobs))
  return (
    <DashboardCard title={t("usageChart.title")} sx={sx}>
      {!usage.length ? <EmptyState label={t("noData")} height={160} /> : (
        <Stack spacing={2.5}>
          {usage.map((u) => (
            <Box key={u.type}>
              <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.75 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{t(`usageType.${u.type}`)}</Typography>
                <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>{u.jobs}</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={(u.jobs / max) * 100}
                aria-label={`${t(`usageType.${u.type}`)}: ${u.jobs}`}
                sx={{ height: 8, borderRadius: 4, bgcolor: "grey.100", "& .MuiLinearProgress-bar": { borderRadius: 4 } }} />
            </Box>
          ))}
        </Stack>
      )}
    </DashboardCard>
  )
}

export function EmptyState({ label, height }: { label: string; height: number }) {
  return (
    <Box sx={{ height, display: "flex", alignItems: "center", justifyContent: "center", border: "1px dashed", borderColor: "divider",
      borderRadius: "7px", color: "text.secondary", textAlign: "center", px: 2 }}>
      <Typography variant="subtitle2">{label}</Typography>
    </Box>
  )
}

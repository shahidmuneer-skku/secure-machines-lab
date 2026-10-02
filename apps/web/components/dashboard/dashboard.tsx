"use client"

import Alert from "@mui/material/Alert"
import Button from "@mui/material/Button"
import Grid from "@mui/material/Grid"
import Skeleton from "@mui/material/Skeleton"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import { IconKey } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { useState } from "react"

import { DashboardCard } from "@/components/mui/dashboard-card"
import { useCan, useMe } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatDuration, formatPercent } from "@/lib/format"

import { QuickUpload } from "./quick-upload"
import {
  AnalysesOverview, CreditsCard, KPI_ICONS, RecentActivity, RecentResults, StatCard, UsageByType, VerdictBreakdown,
  WelcomeCard, type Range,
} from "./widgets"

/** Dashboard after the Modernize template (owner, 2026-10-02): welcome, key figures, charts, activity. */
export function Dashboard() {
  const t = useTranslations("dashboard")
  const { data: me } = useMe()
  const canStudio = useCan("use_studio")
  const [days, setDays] = useState<Range>(30)
  const { data: summary, isLoading, isError, refetch } = useQuery({
    queryKey: qk.dashboard(days),
    queryFn: async () => data(await api.GET("/api/v1/dashboard/summary", { params: { query: { days } } as never })),
    refetchInterval: 30_000,
  })
  const name = me?.display_name?.trim() || me?.email?.split("@")[0] || ""
  const k = summary?.kpis
  const api_ = summary?.api_usage

  return (
    <Stack spacing={3}>
      {isError && (
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={() => refetch()}>{t("retry")}</Button>}>
          {t("loadError")}
        </Alert>
      )}
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}>
          <WelcomeCard name={name} summary={summary} days={days} canStudio={canStudio} />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          {isLoading ? <Skeleton variant="rounded" height="100%" sx={{ minHeight: 240 }} /> : <CreditsCard summary={summary} days={days} />}
        </Grid>

        {(["jobs", "fakeRate", "turnaround", "inQueue"] as const).map((key) => {
          const tone = ({ jobs: "primary", fakeRate: "error", turnaround: "secondary", inQueue: "warning" } as const)[key]
          const value = !k ? "—" : key === "jobs" ? k.jobs_in_period : key === "fakeRate" ? formatPercent(k.fake_rate, 0)
            : key === "turnaround" ? formatDuration(k.avg_turnaround_seconds) : k.in_queue
          const hint = key === "jobs" ? t("days", { count: days }) : key === "fakeRate" ? t("kpi.fakeRateHint")
            : key === "turnaround" ? t("kpi.turnaroundHint") : t("kpi.inQueueHint")
          return (
            <Grid key={key} size={{ xs: 12, sm: 6, lg: 3 }}>
              {isLoading ? <Skeleton variant="rounded" height={128} /> : (
                <StatCard icon={KPI_ICONS[key]} tone={tone} label={t(`kpi.${key}`)} value={value} hint={hint} />
              )}
            </Grid>
          )
        })}

        <Grid size={{ xs: 12, lg: 8 }}>
          {isLoading ? <Skeleton variant="rounded" height={440} /> : <AnalysesOverview summary={summary} days={days} onDays={setDays} />}
        </Grid>
        <Grid size={{ xs: 12, lg: 4 }}>
          {/* Side by side on tablets; stacked beside the chart from `lg`, where the donut keeps its natural height. */}
          <Stack direction={{ xs: "column", md: "row", lg: "column" }} spacing={3} sx={{ height: "100%" }}>
            {isLoading ? <Skeleton variant="rounded" height={260} /> : <VerdictBreakdown summary={summary} sx={{ height: "auto", flex: { md: 1, lg: "0 0 auto" } }} />}
            {isLoading ? <Skeleton variant="rounded" height={160} /> : <UsageByType summary={summary} sx={{ height: "auto", flex: 1 }} />}
          </Stack>
        </Grid>

        <Grid size={{ xs: 12, lg: 4 }}>
          {isLoading ? <Skeleton variant="rounded" height={420} /> : <RecentActivity summary={summary} />}
        </Grid>
        <Grid size={{ xs: 12, lg: 8 }}>
          {isLoading ? <Skeleton variant="rounded" height={420} /> : <RecentResults summary={summary} />}
        </Grid>

        <Grid size={{ xs: 12, lg: api_?.requests ? 8 : 12 }}>
          <DashboardCard title={t("quick.title")} subtitle={t("quick.subtitle")}><QuickUpload /></DashboardCard>
        </Grid>
        {!!api_?.requests && (
          <Grid size={{ xs: 12, lg: 4 }}>
            <DashboardCard title={t("api.title")}>
              <Stack spacing={1}>
                <Typography variant="h4" sx={{ fontWeight: 700 }}>{t("api.requests", { count: api_.requests })}</Typography>
                <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>
                  {t("api.jobs", { count: api_.jobs })} · {t("api.credits", { count: api_.credits })}
                </Typography>
                <Button component={Link} href="/app/api-keys" startIcon={<IconKey size={18} />} sx={{ alignSelf: "flex-start", px: 0 }}>
                  {t("api.manage")}
                </Button>
              </Stack>
            </DashboardCard>
          </Grid>
        )}
      </Grid>
    </Stack>
  )
}

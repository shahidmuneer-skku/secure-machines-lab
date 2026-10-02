"use client"

import { useQuery } from "@tanstack/react-query"
import { Activity, AlertTriangle, Coins, Cpu, ListChecks, UserRound, Users } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"

import { useBalance } from "@/components/sml/credit-meter"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { Badge } from "@/components/ui/badge"
import { CardContent } from "@/components/ui/card"
import { useMe } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatMoney } from "@/lib/format"

import { AdminError, Loading } from "./common"
import { SystemHealth } from "./system-health"

function Tile({ label, value, hint, icon: Icon, href, tone }: { label: string; value: React.ReactNode; hint?: string;
  icon: typeof Users; href?: string; tone?: "warn" }) {
  const body = (
    <HudCard interactive={!!href} className="h-full gap-2 py-4">
      <CardContent className="space-y-1 px-4">
        <div className="flex items-center justify-between"><span className="mono-label text-muted-foreground">{label}</span>
          <Icon className={tone === "warn" ? "size-4 text-warn" : "size-4 text-muted-foreground"} /></div>
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </CardContent>
    </HudCard>
  )
  return href ? <Link href={href}>{body}</Link> : body
}

export function AdminOverview() {
  const t = useTranslations("admin.overview")
  const locale = useLocale()
  const me = useMe()
  const balance = useBalance()
  const { data: o, isLoading, error } = useQuery({ queryKey: qk.admin("overview"), refetchInterval: 15_000,
    queryFn: async () => data(await api.GET("/api/v1/admin/overview")) })
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={1} title={t("title")} description={t("subtitle")} />
      <AdminError error={error} />
      {isLoading ? <Loading /> : o && (
        <>
          {o.maintenance_mode && <Badge className="bg-warn text-black">{t("maintenance")}</Badge>}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tile label={t("users")} icon={Users} value={o.users.total} hint={t("usersHint", { new: o.users.new_7d, active: o.users.active_24h })} href="/admin/users" />
            <Tile label={t("jobs24h")} icon={Activity} value={Object.values(o.jobs_24h).reduce((a, b) => a + b, 0)}
              hint={Object.entries(o.jobs_24h).map(([k, v]) => `${k} ${v}`).join(" · ")} href="/admin/jobs" />
            <Tile label={t("tasksNow")} icon={ListChecks} value={Object.values(o.tasks_now).reduce((a, b) => a + b, 0)}
              hint={Object.entries(o.tasks_now).map(([k, v]) => `${k} ${v}`).join(" · ") || t("idle")} href="/admin/queues" />
            <Tile label={t("failed24h")} icon={AlertTriangle} value={o.failed_tasks_24h} tone={o.failed_tasks_24h ? "warn" : undefined} href="/admin/jobs?status=failed" />
            <Tile label={t("workers")} icon={Cpu} value={o.workers_online} hint={o.gpus.join(", ") || t("noGpu")} href="/admin/queues"
              tone={o.workers_online ? undefined : "warn"} />
            <Tile label={t("credits30d")} icon={Coins} value={o.credits_spent_30d} />
            {me.data && (
              <Tile label={t("myCredits")} icon={UserRound} value={balance.data?.balance ?? "—"} hint={t("myCreditsHint")}
                href={`/admin/users/${me.data.id}#credits`} />
            )}
            {(o.revenue_30d as { currency: string; total: number; refunded: number | null }[]).map((r) => (
              <Tile key={r.currency} label={t("revenue", { currency: r.currency })} icon={Coins}
                value={formatMoney(r.total - (r.refunded ?? 0), r.currency, locale)} href="/admin/billing" />
            ))}
          </div>
        </>
      )}
      <SystemHealth />
    </div>
  )
}

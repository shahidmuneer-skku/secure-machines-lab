"use client"

import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, Cpu, Film, RefreshCw, Sparkles, XCircle } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { useCan } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatDateTime } from "@/lib/format"
import { cn } from "@/lib/utils"

import { AdminError } from "./common"

const gb = (mb: number) => (mb / 1024).toFixed(1)

/** Icon + text, so state never relies on colour alone. */
function State({ ok, warn, children }: { ok: boolean; warn?: boolean; children: React.ReactNode }) {
  const Icon = ok ? CheckCircle2 : warn ? AlertTriangle : XCircle
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className={cn("size-4 shrink-0", ok ? "text-real" : warn ? "text-warn" : "text-fake")} aria-hidden />
      {children}
    </span>
  )
}

function Memory({ used, total }: { used: number; total: number }) {
  const t = useTranslations("admin.system")
  return (
    <div className="space-y-1">
      <Progress value={(used / Math.max(1, total)) * 100} className="h-1.5" aria-label={t("vram")} />
      <p className="text-xs text-muted-foreground">{t("vramUsed", { used: gb(used), total: gb(total) })}</p>
    </div>
  )
}

function Panel({ icon: Icon, title, badge, children }: { icon: typeof Cpu; title: React.ReactNode; badge?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-2 rounded-lg border p-3 text-sm">
      <div className="flex items-center gap-2"><Icon className="size-4 text-primary" aria-hidden />
        <span className="min-w-0 flex-1 truncate font-medium">{title}</span>{badge}</div>
      {children}
    </div>
  )
}

/**
 * Admin overview: are the services up, what is on each GPU (running and waiting work), which AI
 * model is loaded, and which settings still need attention before going live.
 */
export function SystemHealth() {
  const t = useTranslations("admin.system")
  const locale = useLocale()
  const canView = useCan("view_system")
  const { data: s, error, isFetching, refetch } = useQuery({
    queryKey: qk.admin("system"), refetchInterval: 15_000, enabled: canView,
    queryFn: async () => data(await api.GET("/api/v1/admin/system")),
  })
  if (!canView) return null

  const services = s && [
    ...Object.entries(s.checks).map(([name, c]) => ({ name, ok: c.status === "ok", detail: c.status === "ok" ? t("latency", { ms: c.latency_ms }) : t("unreachable") })),
    { name: "stream", ok: s.stream.status === "ok", detail: s.stream.status === "ok" ? (s.stream.busy ? t("busy") : t("idle")) : t("unreachable") },
    { name: "ollama", ok: s.agents.status === "ok", detail: s.agents.status === "ok" ? t("modelsLoaded", { count: s.agents.loaded.length }) : t("unreachable") },
  ]
  const c = s?.configuration
  const config = c && [
    { key: "email", ok: c.email === "smtp", value: c.email === "smtp" ? t("config.smtp") : t("config.emailLog") },
    { key: "toss", ok: c.toss === "live", value: t(`config.mode.${c.toss}`) },
    { key: "stripe", ok: c.stripe === "live", value: t(`config.mode.${c.stripe}`) },
    { key: "captcha", ok: c.captcha, value: c.captcha ? t("config.on") : t("config.off") },
    { key: "storage", ok: c.storage === "s3", value: c.storage === "s3" ? t("config.s3") : t("config.local") },
    { key: "debug", ok: !c.debug, value: c.debug ? t("config.on") : t("config.off") },
    { key: "maintenance", ok: !c.maintenance_mode, value: c.maintenance_mode ? t("config.on") : t("config.off") },
  ]

  return (
    <HudCard>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
        <div>
          <Eyebrow index={2}>{t("eyebrow")}</Eyebrow>
          <CardTitle className="mt-1 text-base">{t("title")}</CardTitle>
          {s && <CardDescription>{t("checkedAt", { when: formatDateTime(new Date(s.checked_at * 1000).toISOString(), locale) })}</CardDescription>}
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw className={cn("size-4", isFetching && "animate-spin")} /> {t("refresh")}
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        <AdminError error={error} />
        {!s ? !error && <Skeleton className="h-48 w-full" /> : (
          <>
            <section aria-labelledby="sys-services" className="space-y-2">
              <h3 id="sys-services" className="hud-eyebrow">{t("services")}</h3>
              <ul className="grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
                {services!.map((x) => (
                  <li key={x.name} className="rounded-lg border px-3 py-2 text-sm">
                    <State ok={x.ok}><span className="font-medium">{t(`service.${x.name}`)}</span></State>
                    <span className="block pl-5.5 text-xs text-muted-foreground">{x.detail}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="sys-gpus" className="space-y-2">
              <h3 id="sys-gpus" className="hud-eyebrow">{t("gpus")}</h3>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {s.gpus.map((g) => (
                  <Panel key={`${g.host}:${g.index}`} icon={Cpu} title={`${t("detectors")} · GPU ${g.index}`}
                    badge={<Badge variant="outline" className="font-mono text-[10px]">{g.host}</Badge>}>
                    {g.stats && <><p className="text-xs text-muted-foreground">{g.stats.name} · {t("util", { value: g.stats.util })} · {g.stats.temp_c}°C</p>
                      <Memory used={g.stats.mem_used_mb} total={g.stats.mem_total_mb} /></>}
                    <p className="text-xs">{t("gpuWork", { running: g.running, waiting: g.waiting, reserved: gb(g.reserved_mb) })}</p>
                  </Panel>
                ))}
                {!s.gpus.length && (
                  <Panel icon={Cpu} title={t("detectors")}><State ok={false} warn>{t("noGpuWorkers")}</State></Panel>
                )}

                <Panel icon={Film} title={s.stream.gpu ? `${t("longVideo")} · GPU ${s.stream.gpu.index}` : t("longVideo")}
                  badge={s.stream.status === "ok" && <Badge variant="outline">{s.stream.busy ? t("busy") : t("idle")}</Badge>}>
                  {s.stream.status !== "ok" ? <State ok={false}>{t("unreachable")}</State> : (
                    <>
                      {s.stream.gpu && <><p className="text-xs text-muted-foreground">{s.stream.gpu.name} · {t("util", { value: s.stream.gpu.util })}</p>
                        <Memory used={s.stream.gpu.mem_used_mb} total={s.stream.gpu.mem_total_mb} /></>}
                      <p className="text-xs">{t("streamWork", { active: s.stream.active_sessions, waiting: s.stream.waiting })}</p>
                      <State ok={s.stream.model_loaded} warn><span className="text-xs">{s.stream.model_loaded ? t("modelReady") : t("modelNotLoaded")}</span></State>
                    </>
                  )}
                </Panel>

                <Panel icon={Sparkles} title={t("aiModel")}>
                  {s.agents.status !== "ok" ? <State ok={false}>{t("unreachable")}</State> : (
                    <>
                      {s.agents.loaded.map((m) => (
                        <div key={m.name} className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-mono">{m.name}</span>
                          <span className="text-muted-foreground">{t("vramGb", { value: gb(m.vram_mb) })}</span>
                          {m.pinned && <Badge variant="secondary" className="text-[10px]">{t("pinned")}</Badge>}
                        </div>
                      ))}
                      {!s.agents.loaded.length && <p className="text-xs text-muted-foreground">{t("noModelLoaded")}</p>}
                      <p className="text-xs">{t("agentWork", { running: s.agents.running, waiting: s.agents.waiting })}</p>
                      {!s.agents.workers && <State ok={false} warn><span className="text-xs">{t("noAgentWorkers")}</span></State>}
                    </>
                  )}
                </Panel>
              </div>
            </section>

            <section aria-labelledby="sys-config" className="space-y-2">
              <h3 id="sys-config" className="hud-eyebrow">{t("configuration")}</h3>
              <dl className="grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2 xl:grid-cols-4">
                {config!.map((x) => (
                  <div key={x.key} className="flex items-center justify-between gap-2 border-b border-dashed py-1">
                    <dt className="text-muted-foreground">{t(`config.${x.key}`)}</dt>
                    <dd><State ok={x.ok} warn>{x.value}</State></dd>
                  </div>
                ))}
              </dl>
            </section>
          </>
        )}
      </CardContent>
    </HudCard>
  )
}

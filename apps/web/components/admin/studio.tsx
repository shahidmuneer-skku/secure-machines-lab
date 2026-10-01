"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Cpu } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { Badge } from "@/components/ui/badge"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCan } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { StudioAdmin, StudioMode, StudioModelInfo } from "@/lib/api/types"

import { AdminError } from "./common"

const OFF = "__off"
const SERVER_TONE: Record<string, string> = { ready: "text-real", loading: "text-primary", down: "text-fake" }

/** Admin → Studio: the model users get per mode (kept loaded on the studio GPU) and the server's state. */
export function AdminStudio() {
  const t = useTranslations("admin.studio")
  const qc = useQueryClient()
  const canEdit = useCan("manage_models")
  const { data: studio, error } = useQuery({
    queryKey: qk.admin("studio"), refetchInterval: 10_000,
    queryFn: async () => data(await api.GET("/api/v1/admin/studio")),
  })
  const save = useMutation({
    mutationFn: async (body: { enabled?: boolean; generate_model?: string; edit_model?: string }) =>
      data(await api.PATCH("/api/v1/admin/studio", { body })),
    onSuccess: (next) => {
      qc.setQueryData(qk.admin("studio"), next)
      qc.invalidateQueries({ queryKey: qk.studioConfig })
      toast.success(t("saved"))
    },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  if (!studio) return <AdminError error={error} />
  const byId = Object.fromEntries(studio.models.map((m) => [m.id, m]))
  const server = studio.server
  const chosen = [byId[studio.generate_model], byId[studio.edit_model]].filter(Boolean) as StudioModelInfo[]
  const unique = [...new Map(chosen.map((m) => [m.id, m])).values()]
  const keptGb = unique.reduce((sum, m) => sum + (m.weights_gb ?? 0), 0)
  const tooBig = unique.length > 1 && server.budget_gb != null && keptGb + 16 > server.budget_gb
  return (
    <div className="min-w-0 space-y-6">
      <PageHeader eyebrow={t("eyebrow")} title={t("title")} description={t("subtitle")} />
      <div className="grid gap-5 lg:grid-cols-2">
        <HudCard>
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-base">{t("modelsTitle")}</CardTitle>
              <p className="text-xs text-muted-foreground">{t("modelsHint")}</p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={studio.enabled} disabled={!canEdit || save.isPending}
                onCheckedChange={(enabled) => save.mutate({ enabled })} />
              {studio.enabled ? t("on") : t("off")}
            </label>
          </CardHeader>
          <CardContent className="space-y-4">
            {(["generate", "edit"] as const).map((mode) => (
              <ModeChoice key={mode} mode={mode} studio={studio} disabled={!canEdit || save.isPending}
                onChange={(id) => save.mutate({ [`${mode}_model`]: id })} />
            ))}
            {tooBig && (
              <p className="flex gap-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs">
                <AlertTriangle className="size-4 shrink-0 text-warn" />
                {t("swapHint", { gb: Math.round(keptGb) })}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {t("prices", { generate: studio.prices.generate, edit: studio.prices.edit })}{" "}
              <Link href="/admin/pricing" className="underline underline-offset-2">{t("editPrices")}</Link>
            </p>
          </CardContent>
        </HudCard>

        <HudCard>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><Cpu className="size-4" /> {t("serverTitle")}</CardTitle>
            <p className="text-xs text-muted-foreground">{t("serverHint")}</p>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">{t("state")}</dt>
              <dd><Badge variant="outline" className={SERVER_TONE[server.state] ?? "text-muted-foreground"}>
                {t(`states.${server.state in SERVER_TONE ? server.state : "unknown"}`)}</Badge></dd>
              <dt className="text-muted-foreground">{t("gpu")}</dt><dd className="font-mono">{server.gpu || "—"}</dd>
              <dt className="text-muted-foreground">{t("loaded")}</dt>
              <dd className="flex flex-wrap gap-1">{server.loaded?.length
                ? server.loaded.map((id) => <Badge key={id} variant="secondary">{byId[id]?.name ?? id}</Badge>)
                : <span className="text-muted-foreground">—</span>}
                {server.loading && <Badge variant="outline">{t("loading", { name: byId[server.loading]?.name ?? server.loading })}</Badge>}
              </dd>
              <dt className="text-muted-foreground">{t("activity")}</dt>
              <dd>{server.busy ? t("busy", { waiting: server.waiting ?? 0 }) : t("idle")}</dd>
              <dt className="text-muted-foreground">{t("memory")}</dt>
              <dd className="font-mono tabular-nums">{server.device_free_gb != null
                ? t("memoryValue", { free: server.device_free_gb, budget: server.budget_gb ?? 0 }) : "—"}</dd>
            </dl>
          </CardContent>
        </HudCard>
      </div>

      <HudCard>
        <CardHeader><CardTitle className="text-base">{t("installedTitle")}</CardTitle>
          <p className="text-xs text-muted-foreground">{t("installedHint")}</p></CardHeader>
        <CardContent className="min-w-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("model")}</TableHead><TableHead>{t("modes")}</TableHead>
                <TableHead>{t("license")}</TableHead><TableHead>{t("abilities")}</TableHead>
                <TableHead className="text-right">{t("size")}</TableHead><TableHead>{t("status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {studio.models.map((m) => {
                const edit = m.controls.edit
                const generate = m.controls.generate
                return (
                  <TableRow key={m.id}>
                    <TableCell><span className="font-medium">{m.name}</span>
                      <span className="block text-xs text-muted-foreground">{m.vendor}</span></TableCell>
                    <TableCell className="space-x-1">{m.modes.map((mode) =>
                      <Badge key={mode} variant="outline">{t(`mode.${mode}`)}</Badge>)}</TableCell>
                    <TableCell className="max-w-56 whitespace-normal">
                      <span className="text-xs">{m.license}</span>
                      {!m.commercial && <Badge variant="outline" className="ml-1 border-warn/50 text-warn">{t("nonCommercial")}</Badge>}
                    </TableCell>
                    <TableCell className="max-w-72 whitespace-normal text-xs text-muted-foreground">
                      {[edit && t("refs", { n: edit.references.max }),
                        (generate ?? edit)?.transparent && t("transparent"),
                        generate && t("formats", { n: generate.aspect_ratios.length }),
                        (generate ?? edit)?.steps && t("stepsDefault", { n: (generate ?? edit)!.steps!.default })]
                        .filter(Boolean).join(" · ")}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{m.weights_gb ? `${m.weights_gb} GB` : "—"}</TableCell>
                    <TableCell>
                      {!m.installed ? <Badge variant="outline" className="text-fake">{t("notInstalled")}</Badge>
                        : m.loaded ? <Badge>{t("loadedBadge")}</Badge>
                        : <Badge variant="secondary">{t("onDemand")}</Badge>}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </HudCard>
    </div>
  )
}

function ModeChoice({ mode, studio, disabled, onChange }: {
  mode: StudioMode
  studio: StudioAdmin
  disabled: boolean
  onChange: (id: string) => void
}) {
  const t = useTranslations("admin.studio")
  const current = mode === "generate" ? studio.generate_model : studio.edit_model
  const model = studio.models.find((m) => m.id === current)
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`studio-${mode}`}>{t(`modeLabel.${mode}`)}</Label>
      <Select value={current || OFF} disabled={disabled} onValueChange={(v) => onChange(v === OFF ? "" : v)}>
        <SelectTrigger id={`studio-${mode}`} className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value={OFF}>{t("modeOff")}</SelectItem>
          {studio.models.filter((m) => m.modes.includes(mode)).map((m) => (
            <SelectItem key={m.id} value={m.id} disabled={!m.installed}>
              {m.name}{m.commercial ? "" : ` · ${t("nonCommercial")}`}{m.installed ? "" : ` · ${t("notInstalled")}`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {model && !model.commercial && (
        <p className="text-xs text-warn">{t("licenseWarning", { license: model.license })}</p>
      )}
    </div>
  )
}

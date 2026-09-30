"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Cpu, RotateCw, Search, Thermometer } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDraft } from "@/hooks/use-draft"
import { useCan } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { formatDuration, formatRelative } from "@/lib/format"

import { AdminError, LoadMore, Loading, usePaged } from "./common"

/* ---------------- roles ---------------- */

const NO_CAPS: Record<number, string[]> = {}

export function AdminRoles() {
  const t = useTranslations("admin.roles")
  const qc = useQueryClient()
  const canEdit = useCan("manage_roles")
  const { data: r, isLoading, error } = useQuery({ queryKey: qk.admin("roles"), queryFn: async () => data(await api.GET("/api/v1/admin/roles")) as unknown as {
    roles: { id: number; name: string; description: string; mfa_required: boolean; is_staff_role: boolean; capabilities: string[]; members: number }[]
    capabilities: { id: string; label: string }[] } })
  const serverDraft = useMemo(() => r && Object.fromEntries(r.roles.map((x) => [x.id, x.capabilities])), [r])
  const edits = useDraft<Record<number, string[]>>(serverDraft, NO_CAPS)
  const draft = edits.value
  const setDraft = edits.set
  const save = useMutation({
    mutationFn: async (id: number) => data(await api.PUT("/api/v1/admin/roles/{id}", { params: { path: { id } }, body: { capabilities: draft[id] } as never })),
    onSuccess: async () => {
      toast.success(t("saved"))
      await qc.invalidateQueries({ queryKey: qk.admin("roles") })
      edits.reset()
    },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  if (isLoading) return <Loading />
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={3} title={t("title")} description={t("subtitle")} />
      <AdminError error={error} />
      {r && (
        <HudCard><CardContent className="overflow-x-auto pt-4">
          <Table>
            <TableHeader><TableRow>
              <TableHead className="min-w-56">{t("capability")}</TableHead>
              {r.roles.map((role) => (
                <TableHead key={role.id} className="text-center"><span className="font-mono">{role.name}</span>
                  <span className="block text-[10px] font-normal text-muted-foreground">{t("members", { count: role.members })}{role.mfa_required ? " · MFA" : ""}</span></TableHead>
              ))}
            </TableRow></TableHeader>
            <TableBody>
              {r.capabilities.map((cap) => (
                <TableRow key={cap.id}>
                  <TableCell><span className="font-mono text-xs">{cap.id}</span><span className="block text-xs text-muted-foreground">{cap.label}</span></TableCell>
                  {r.roles.map((role) => (
                    <TableCell key={role.id} className="text-center">
                      <Checkbox checked={(draft[role.id] ?? []).includes(cap.id)} disabled={!canEdit || role.name === "super_admin"}
                        aria-label={`${role.name}: ${cap.id}`}
                        onCheckedChange={(on) => setDraft((d) => ({ ...d, [role.id]: on ? [...(d[role.id] ?? []), cap.id] : (d[role.id] ?? []).filter((x) => x !== cap.id) }))} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
              {canEdit && (
                <TableRow><TableCell />
                  {r.roles.map((role) => (
                    <TableCell key={role.id} className="text-center">
                      {role.name !== "super_admin" && <Button size="sm" variant="outline" onClick={() => save.mutate(role.id)}>{t("save")}</Button>}
                    </TableCell>))}
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent></HudCard>
      )}
    </div>
  )
}

/* ---------------- jobs ---------------- */

export function AdminJobs() {
  const t = useTranslations("admin.jobs")
  const locale = useLocale()
  const [q, setQ] = useState("")
  const [status, setStatus] = useState("any")
  const [open, setOpen] = useState<string | null>(null)
  const list = usePaged(qk.admin("jobs", { q, status }), async (cursor) => data(await api.GET("/api/v1/admin/jobs", {
    params: { query: { cursor, q: q || undefined, status: status === "any" ? undefined : [status] } as never } })))
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={4} title={t("title")} description={t("subtitle")} />
      <div className="flex flex-wrap gap-2">
        <div className="relative min-w-64 flex-1"><Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} aria-label={t("search")} /></div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40" aria-label={t("status")}><SelectValue /></SelectTrigger>
          <SelectContent>{["any", "queued", "running", "succeeded", "failed", "canceled", "expired"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <AdminError error={list.error} />
      {list.isLoading ? <Loading /> : (
        <HudCard><CardContent className="pt-4">
          <Table>
            <TableHeader><TableRow><TableHead>{t("col.job")}</TableHead><TableHead>{t("col.source")}</TableHead><TableHead>{t("col.status")}</TableHead>
              <TableHead>{t("col.result")}</TableHead><TableHead className="text-right">{t("col.credits")}</TableHead><TableHead>{t("col.created")}</TableHead></TableRow></TableHeader>
            <TableBody>
              {list.rows.map((j) => (
                <TableRow key={j.id} className="cursor-pointer" onClick={() => setOpen(j.id)}>
                  <TableCell><span className="font-medium">{j.title}</span><span className="block font-mono text-[10px] text-muted-foreground">{j.id}</span></TableCell>
                  <TableCell className="text-xs">{j.kind} · {j.source}</TableCell>
                  <TableCell><StatusChip status={j.status} /></TableCell>
                  <TableCell>{j.status === "succeeded" ? <VerdictBadge verdict={j.verdict} probability={j.fake_probability} size="sm" /> :
                    j.status === "running" ? <Progress value={j.progress} className="h-1.5 w-24" /> : j.error_code || "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{j.credits_charged}</TableCell>
                  <TableCell className="text-xs">{formatRelative(j.created_at, locale)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <LoadMore q={list} />
        </CardContent></HudCard>
      )}
      <AdminJobSheet id={open} onClose={() => setOpen(null)} />
    </div>
  )
}

function AdminJobSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const t = useTranslations("admin.jobs")
  const qc = useQueryClient()
  const canManage = useCan("manage_all_jobs")
  const canQueues = useCan("manage_queues")
  const { data: job } = useQuery({ queryKey: qk.admin("job", id ?? ""), enabled: !!id,
    queryFn: async () => data(await api.GET("/api/v1/admin/jobs/{id}", { params: { path: { id: id! } } })) })
  const cancel = useMutation({ mutationFn: async () => data(await api.POST("/api/v1/admin/jobs/{id}", { params: { path: { id: id! } } })),
    onSuccess: () => { toast.success(t("canceled")); qc.invalidateQueries({ queryKey: ["admin"] }) } })
  const retry = useMutation({ mutationFn: async (taskId: string) => data(await api.POST("/api/v1/admin/tasks/{id}/retry", { params: { path: { id: taskId } } })),
    onSuccess: () => { toast.success(t("retried")); qc.invalidateQueries({ queryKey: ["admin"] }) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")) })
  const tasks = (job?.tasks_internal ?? []) as { id: string; target: string; status: string; worker: string; gpu: string; attempt: number;
    error_code: string; error_message: string; error_detail: string; duration_ms: number | null }[]
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader><SheetTitle>{job?.title}</SheetTitle></SheetHeader>
        {job && (
          <div className="space-y-4 px-4 pb-6 text-sm">
            <div className="flex flex-wrap items-center gap-2"><StatusChip status={job.status} />
              <span className="text-muted-foreground">{job.user_email ?? t("guest")}</span>
              {canManage && ["queued", "running"].includes(job.status) && <Button size="sm" variant="outline" onClick={() => cancel.mutate()}>{t("cancel")}</Button>}
            </div>
            <Table>
              <TableHeader><TableRow><TableHead>{t("task")}</TableHead><TableHead>{t("status")}</TableHead><TableHead>{t("worker")}</TableHead>
                <TableHead>{t("time")}</TableHead><TableHead /></TableRow></TableHeader>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-mono text-xs">{task.target}<span className="block text-fake">{task.error_message}</span>
                      {task.error_detail && <pre className="mt-1 max-w-xl whitespace-pre-wrap break-all text-[11px] text-muted-foreground">
                        {task.error_detail}</pre>}</TableCell>
                    <TableCell><StatusChip status={task.status} /></TableCell>
                    <TableCell className="text-xs">{task.worker || "—"}{task.gpu ? ` · GPU ${task.gpu}` : ""} · #{task.attempt}</TableCell>
                    <TableCell className="text-xs">{task.duration_ms ? formatDuration(task.duration_ms / 1000) : "—"}</TableCell>
                    <TableCell>{canQueues && task.status === "failed" && !["succeeded", "failed", "canceled", "expired"].includes(job.status) && (
                      <Button size="icon" variant="ghost" aria-label={t("retry")} onClick={() => retry.mutate(task.id)}><RotateCw className="size-4" /></Button>)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Button asChild variant="link" className="px-0"><Link href={`/app/results/${job.id}`} target="_blank">{t("openAsUser")}</Link></Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}

/* ---------------- queues, workers & GPUs ---------------- */

export function AdminQueues() {
  const t = useTranslations("admin.queues")
  const locale = useLocale()
  const queues = useQuery({ queryKey: qk.admin("queues"), refetchInterval: 5000, queryFn: async () => data(await api.GET("/api/v1/admin/queues")) })
  const workers = useQuery({ queryKey: qk.admin("workers"), refetchInterval: 5000, queryFn: async () => data(await api.GET("/api/v1/admin/workers")) })
  const byQueue = queues.data?.tasks_by_queue ?? {}
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={5} title={t("title")} description={t("subtitle")} />
      <AdminError error={queues.error || workers.error} />
      <HudCard>
        <CardHeader><Eyebrow index={1}>{t("workersEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("workersTitle", { count: workers.data?.length ?? 0 })}</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {(workers.data ?? []).map((w) => (
            <div key={w.id} className="space-y-2 rounded-lg border p-3 text-sm">
              <div className="flex items-center gap-2"><Cpu className="size-4 text-primary" /><span className="font-mono text-xs">{w.hostname}:{w.pid}</span>
                <Badge variant="outline">{w.gpu ? `GPU ${w.gpu}` : t("cpu")}</Badge>
                {w.simulate !== "0" && <Badge variant="outline" className="border-warn/50 text-warn">simulate={w.simulate}</Badge>}</div>
              {w.gpu_stats && (
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <span>{w.gpu_stats.name}</span>
                  <span>{t("util", { value: w.gpu_stats.util })}</span>
                  <span className="inline-flex items-center gap-1"><Thermometer className="size-3" />{w.gpu_stats.temp_c}°C</span>
                  <div className="col-span-3 space-y-1"><Progress value={(w.gpu_stats.mem_used_mb / w.gpu_stats.mem_total_mb) * 100} className="h-1.5" />
                    <span className="text-muted-foreground">{t("vram", { used: Math.round(w.gpu_stats.mem_used_mb / 1024), total: Math.round(w.gpu_stats.mem_total_mb / 1024) })}</span></div>
                </div>
              )}
              <p className="text-xs text-muted-foreground">{w.current_task ? t("busy", { target: String((w.current_task as Record<string, string>).target) }) : t("idle")}
                {" · "}{t("since", { when: formatRelative(w.started_at, locale) })}</p>
              <p className="line-clamp-2 font-mono text-[10px] text-muted-foreground">{w.queues.join(", ")}</p>
            </div>
          ))}
          {!workers.data?.length && <p className="text-sm text-warn">{t("noWorkers")}</p>}
        </CardContent>
      </HudCard>
      <HudCard>
        <CardHeader><Eyebrow index={2}>{t("queuesEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("queuesTitle")}</CardTitle>
          {queues.data && <p className="text-xs text-muted-foreground">{t("oldest", { seconds: queues.data.oldest_waiting_seconds })}</p>}</CardHeader>
        <CardContent>
          {queues.data?.rabbitmq_error && <p className="mb-3 text-sm text-warn">{queues.data.rabbitmq_error}</p>}
          <Table>
            <TableHeader><TableRow><TableHead>{t("queue")}</TableHead><TableHead className="text-right">{t("ready")}</TableHead>
              <TableHead className="text-right">{t("unacked")}</TableHead><TableHead className="text-right">{t("consumers")}</TableHead>
              <TableHead className="text-right">{t("pending")}</TableHead><TableHead className="text-right">{t("running")}</TableHead></TableRow></TableHeader>
            <TableBody>
              {(queues.data?.rabbitmq ?? []).map((q) => (
                <TableRow key={q.name}>
                  <TableCell className="font-mono text-xs">{q.name}</TableCell>
                  <TableCell className="text-right tabular-nums">{q.ready}</TableCell>
                  <TableCell className="text-right tabular-nums">{q.unacked}</TableCell>
                  <TableCell className={`text-right tabular-nums ${q.consumers === 0 && q.name.startsWith("sml.model") ? "text-warn" : ""}`}>{q.consumers}</TableCell>
                  <TableCell className="text-right tabular-nums">{byQueue[q.name]?.pending ?? 0}</TableCell>
                  <TableCell className="text-right tabular-nums">{byQueue[q.name]?.running ?? 0}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </HudCard>
    </div>
  )
}

/* ---------------- models ---------------- */

export function AdminModels() {
  const t = useTranslations("admin.models")
  const qc = useQueryClient()
  const canEdit = useCan("manage_models")
  const { data: models, isLoading, error } = useQuery({ queryKey: qk.admin("models"), refetchInterval: 15_000,
    queryFn: async () => data(await api.GET("/api/v1/admin/models")) })
  const patch = useMutation({
    mutationFn: async (body: Record<string, unknown>) => data(await api.PATCH("/api/v1/admin/models", { body: body as never })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.admin("models") }); toast.success(t("saved")) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  if (isLoading) return <Loading />
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={6} title={t("title")} description={t("subtitle")} />
      <AdminError error={error} />
      <HudCard><CardContent className="overflow-x-auto pt-4">
        <Table>
          <TableHeader><TableRow><TableHead>{t("model")}</TableHead><TableHead>{t("enabled")}</TableHead><TableHead>{t("default")}</TableHead>
            <TableHead>{t("trial")}</TableHead><TableHead>{t("weight")}</TableHead><TableHead className="text-right">{t("consumers")}</TableHead>
            <TableHead className="text-right">{t("runs")}</TableHead><TableHead>{t("envs")}</TableHead></TableRow></TableHeader>
          <TableBody>
            {(models ?? []).map((m) => (
              <TableRow key={m.id}>
                <TableCell><span className="font-medium">{m.name}</span><span className="block font-mono text-[10px] text-muted-foreground">{m.id} · {m.media.join("/")} · {m.family}</span></TableCell>
                <TableCell><Switch checked={m.enabled} disabled={!canEdit} onCheckedChange={(v) => patch.mutate({ model_id: m.id, enabled: v })} aria-label={t("enabled")} /></TableCell>
                <TableCell><Switch checked={m.default_selected} disabled={!canEdit} onCheckedChange={(v) => patch.mutate({ model_id: m.id, default_selected: v })} aria-label={t("default")} /></TableCell>
                <TableCell><Switch checked={m.trial} disabled={!canEdit} onCheckedChange={(v) => patch.mutate({ model_id: m.id, trial: v })} aria-label={t("trial")} /></TableCell>
                <TableCell><Input type="number" step="0.1" min="0" max="10" defaultValue={m.weight} disabled={!canEdit} className="h-8 w-20"
                  onBlur={(e) => Number(e.target.value) !== m.weight && patch.mutate({ model_id: m.id, weight: Number(e.target.value) })} aria-label={t("weight")} /></TableCell>
                <TableCell className={`text-right tabular-nums ${m.consumers ? "" : "text-warn"}`}>{m.consumers}</TableCell>
                <TableCell className="text-right text-xs tabular-nums">{m.stats_24h.runs} / <span className="text-fake">{m.stats_24h.failed}</span> / {m.stats_24h.waiting}</TableCell>
                <TableCell className="font-mono text-[10px]">{m.conda_envs.join(", ")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <p className="pt-3 text-xs text-muted-foreground">{t("legend")}</p>
      </CardContent></HudCard>
    </div>
  )
}

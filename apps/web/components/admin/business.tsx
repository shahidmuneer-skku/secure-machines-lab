"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Loader2, Plus, RotateCcw, Save } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useCan } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { formatDateTime, formatMoney } from "@/lib/format"

import { AdminError, LoadMore, Loading, usePaged } from "./common"

const onError = (fallback: string) => (e: unknown) => toast.error(isApiError(e) ? e.detail : fallback)

/* ---------------- pricing ---------------- */

export function AdminPricing() {
  const t = useTranslations("admin.pricing")
  const qc = useQueryClient()
  const canEdit = useCan("manage_pricing")
  const canSettings = useCan("manage_settings")
  const { data: prices, isLoading, error } = useQuery({ queryKey: qk.admin("pricing"), queryFn: async () => data(await api.GET("/api/v1/admin/pricing")) })
  const { data: settings } = useQuery({ queryKey: qk.admin("settings"), queryFn: async () => data(await api.GET("/api/v1/admin/settings")) })
  const [draft, setDraft] = useState<Record<string, number>>({})
  const [free, setFree] = useState<Record<string, number>>({})
  useEffect(() => { if (prices) setDraft(Object.fromEntries(prices.map((p) => [p.key, p.credits]))) }, [prices])
  useEffect(() => {
    if (settings) setFree({ guest_trial_images_per_day: settings.guest_trial_images_per_day ?? 0, signup_bonus_credits: settings.signup_bonus_credits ?? 0,
      signup_bonus_expiry_days: settings.signup_bonus_expiry_days ?? 0, daily_free_credits: settings.daily_free_credits ?? 0,
      purchased_credit_expiry_days: settings.purchased_credit_expiry_days ?? 0 })
  }, [settings])
  const savePrices = useMutation({ mutationFn: async () => data(await api.PUT("/api/v1/admin/pricing", { body: { prices: draft } })),
    onSuccess: () => { toast.success(t("saved")); qc.invalidateQueries({ queryKey: qk.admin("pricing") }) }, onError: onError(t("failed")) })
  const saveFree = useMutation({ mutationFn: async () => data(await api.PATCH("/api/v1/admin/settings", { body: free as never })),
    onSuccess: () => { toast.success(t("saved")); qc.invalidateQueries({ queryKey: qk.admin("settings") }) }, onError: onError(t("failed")) })
  if (isLoading) return <Loading />
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={7} title={t("title")} description={t("subtitle")} />
      <AdminError error={error} />
      <div className="grid gap-5 lg:grid-cols-2">
        <HudCard>
          <CardHeader><Eyebrow index={1}>{t("costsEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("costsTitle")}</CardTitle>
            <CardDescription>{t("costsHint")}</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {prices?.map((p) => (
              <div key={p.key} className="flex items-center justify-between gap-3">
                <Label htmlFor={`p-${p.key}`} className="font-normal">{p.label}</Label>
                <Input id={`p-${p.key}`} type="number" min={0} className="w-24 text-right" disabled={!canEdit}
                  value={draft[p.key] ?? 0} onChange={(e) => setDraft({ ...draft, [p.key]: Number(e.target.value) })} />
              </div>
            ))}
            {canEdit && <Button size="sm" onClick={() => savePrices.mutate()} disabled={savePrices.isPending}><Save className="size-4" /> {t("save")}</Button>}
          </CardContent>
        </HudCard>
        <HudCard>
          <CardHeader><Eyebrow index={2}>{t("freeEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("freeTitle")}</CardTitle>
            <CardDescription>{t("freeHint")}</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {Object.keys(free).map((k) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <Label htmlFor={`f-${k}`} className="font-normal">{t(`free.${k}`)}</Label>
                <Input id={`f-${k}`} type="number" min={0} className="w-24 text-right" disabled={!canSettings}
                  value={free[k]} onChange={(e) => setFree({ ...free, [k]: Number(e.target.value) })} />
              </div>
            ))}
            {canSettings && <Button size="sm" onClick={() => saveFree.mutate()} disabled={saveFree.isPending}><Save className="size-4" /> {t("save")}</Button>}
          </CardContent>
        </HudCard>
      </div>
    </div>
  )
}

/* ---------------- billing ---------------- */

type Json = Record<string, unknown>

function ProductEditor({ kind }: { kind: "packs" | "plans" }) {
  const t = useTranslations("admin.billing")
  const qc = useQueryClient()
  const canEdit = useCan("manage_billing")
  const list = useQuery({ queryKey: qk.admin(kind), queryFn: async () => kind === "packs"
    ? data(await api.GET("/api/v1/admin/packs")) as unknown as Json[] : data(await api.GET("/api/v1/admin/plans")) as unknown as Json[] })
  const [editing, setEditing] = useState<Json | null>(null)
  const [text, setText] = useState("")
  const save = useMutation({
    mutationFn: async () => {
      const body = JSON.parse(text) as Json
      if (editing?.id) {
        return kind === "packs" ? api.PATCH("/api/v1/admin/packs/{id}", { params: { path: { id: String(editing.id) } }, body: body as never })
          : api.PATCH("/api/v1/admin/plans/{id}", { params: { path: { id: String(editing.id) } }, body: body as never })
      }
      return kind === "packs" ? api.POST("/api/v1/admin/packs", { body: body as never }) : api.POST("/api/v1/admin/plans", { body: body as never })
    },
    onSuccess: () => { toast.success(t("saved")); setEditing(null); qc.invalidateQueries({ queryKey: qk.admin(kind) }) },
    onError: (e) => toast.error(e instanceof SyntaxError ? t("badJson") : isApiError(e) ? e.detail : t("failed")),
  })
  const open = (row: Json | null) => {
    const template: Json = kind === "packs"
      ? { slug: "new-pack", name: { en: "", ko: "", de: "" }, credits: 100, bonus_credits: 0, price_krw: 10000, price_usd_cents: 800, credit_expiry_days: null, highlight: false, active: true, sort_order: 9 }
      : { slug: "new-plan", name: { en: "", ko: "", de: "" }, description: { en: "" }, features: { en: [] }, monthly_credits: 500, price_krw: 50000,
          price_usd_cents: 3900, priority: 0, retention_days: 30, api_access: true, max_inflight_tasks: 8, highlight: false, active: true, sort_order: 9 }
    const { id, created_at, ...rest } = row ?? template
    void id; void created_at
    setText(JSON.stringify(rest, null, 2))
    setEditing(row ?? {})
  }
  return (
    <div className="space-y-3">
      {canEdit && <Button size="sm" onClick={() => open(null)}><Plus className="size-4" /> {t(kind === "packs" ? "newPack" : "newPlan")}</Button>}
      <Table>
        <TableHeader><TableRow><TableHead>{t("name")}</TableHead><TableHead className="text-right">{t("credits")}</TableHead>
          <TableHead className="text-right">KRW</TableHead><TableHead className="text-right">USD</TableHead><TableHead>{t("active")}</TableHead><TableHead /></TableRow></TableHeader>
        <TableBody>
          {(list.data ?? []).map((row) => (
            <TableRow key={String(row.id)}>
              <TableCell>{(row.name as Record<string, string>).en}<span className="block font-mono text-[10px] text-muted-foreground">{String(row.slug)}</span></TableCell>
              <TableCell className="text-right tabular-nums">{String(row.credits ?? row.monthly_credits)}</TableCell>
              <TableCell className="text-right tabular-nums">₩{Number(row.price_krw).toLocaleString()}</TableCell>
              <TableCell className="text-right tabular-nums">${(Number(row.price_usd_cents) / 100).toFixed(2)}</TableCell>
              <TableCell><StatusChip status={row.active ? "active" : "canceled"} /></TableCell>
              <TableCell>{canEdit && <Button size="sm" variant="ghost" onClick={() => open(row)}>{t("edit")}</Button>}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader><DialogTitle>{editing?.id ? t("edit") : t(kind === "packs" ? "newPack" : "newPlan")}</DialogTitle>
            <DialogDescription>{t("jsonHint")}</DialogDescription></DialogHeader>
          <Textarea rows={16} className="font-mono text-xs" value={text} onChange={(e) => setText(e.target.value)} />
          <DialogFooter><Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending && <Loader2 className="size-4 animate-spin" />} {t("save")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function RefundDialog({ payment, onClose }: { payment: { id: string; order_id: string; currency: string } | null; onClose: () => void }) {
  const t = useTranslations("admin.billing")
  const locale = useLocale()
  const qc = useQueryClient()
  const [override, setOverride] = useState(false)
  const [reason, setReason] = useState("")
  const quote = useQuery({ queryKey: qk.admin("refund", payment?.id ?? "", { override }), enabled: !!payment,
    queryFn: async () => data(await api.GET("/api/v1/admin/payments/{id}/refund", { params: { path: { id: payment!.id }, query: { override_full: override ? "true" : undefined } as never } })) })
  const refund = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/admin/payments/{id}/refund", { params: { path: { id: payment!.id } }, body: { reason, override_full: override } })),
    onSuccess: (r) => { toast.success(t("refunded", { credits: r.credits_revoked })); qc.invalidateQueries({ queryKey: qk.admin("payments") }); onClose() },
    onError: onError(t("failed")),
  })
  const q = quote.data
  return (
    <Dialog open={!!payment} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>{t("refundTitle", { order: payment?.order_id ?? "" })}</DialogTitle>
          <DialogDescription>{t("refundHint")}</DialogDescription></DialogHeader>
        {q && (
          <div className="space-y-2 rounded-lg border p-3 text-sm">
            <p>{q.reason}</p>
            <p className="font-medium">{q.eligible ? t("refundAmount", { amount: formatMoney(q.amount, q.currency, locale), credits: q.credits_to_revoke }) : t("notEligible")}</p>
          </div>
        )}
        <label className="flex items-center gap-2 text-sm"><Switch checked={override} onCheckedChange={setOverride} /> {t("override")}</label>
        <div className="space-y-1.5"><Label htmlFor="reason">{t("reason")}</Label><Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} /></div>
        <DialogFooter><Button variant="destructive" disabled={!q?.eligible || !reason || refund.isPending} onClick={() => refund.mutate()}>
          {refund.isPending && <Loader2 className="size-4 animate-spin" />} {t("issueRefund")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function AdminBilling() {
  const t = useTranslations("admin.billing")
  const locale = useLocale()
  const [q, setQ] = useState("")
  const [refunding, setRefunding] = useState<{ id: string; order_id: string; currency: string } | null>(null)
  const canRefundLimited = useCan("refund_limited")
  const canManageBilling = useCan("manage_billing")
  const canRefund = canRefundLimited || canManageBilling
  const payments = usePaged(qk.admin("payments", { q }), async (cursor) => data(await api.GET("/api/v1/admin/payments", {
    params: { query: { cursor, q: q || undefined } as never } })))
  const webhooks = usePaged(qk.admin("webhooks"), async (cursor) => data(await api.GET("/api/v1/admin/webhooks", { params: { query: { cursor } as never } })))
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={8} title={t("title")} description={t("subtitle")} />
      <Tabs defaultValue="payments" className="space-y-4">
        <TabsList><TabsTrigger value="payments">{t("tabs.payments")}</TabsTrigger><TabsTrigger value="packs">{t("tabs.packs")}</TabsTrigger>
          <TabsTrigger value="plans">{t("tabs.plans")}</TabsTrigger><TabsTrigger value="webhooks">{t("tabs.webhooks")}</TabsTrigger></TabsList>
        <TabsContent value="payments">
          <HudCard><CardContent className="space-y-3 pt-4">
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} className="max-w-sm" aria-label={t("search")} />
            <AdminError error={payments.error} />
            <Table>
              <TableHeader><TableRow><TableHead>{t("date")}</TableHead><TableHead>{t("customer")}</TableHead><TableHead>{t("item")}</TableHead>
                <TableHead>{t("status")}</TableHead><TableHead className="text-right">{t("amount")}</TableHead><TableHead /></TableRow></TableHeader>
              <TableBody>
                {payments.rows.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="text-xs">{formatDateTime(p.paid_at ?? p.created_at, locale)}</TableCell>
                    <TableCell className="text-xs">{p.user_email}</TableCell>
                    <TableCell>{p.order_name}<span className="block font-mono text-[10px] text-muted-foreground">{p.provider} · {p.order_id}</span></TableCell>
                    <TableCell><StatusChip status={p.status === "paid" ? "succeeded" : p.status === "failed" ? "failed" : p.status} /></TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{formatMoney(p.amount, p.currency, locale)}
                      {p.refunded_amount > 0 && <span className="block text-xs text-fake">−{formatMoney(p.refunded_amount, p.currency, locale)}</span>}</TableCell>
                    <TableCell>{canRefund && ["paid", "partially_refunded"].includes(p.status) && (
                      <Button size="sm" variant="ghost" onClick={() => setRefunding({ id: p.id, order_id: p.order_id, currency: p.currency })}>
                        <RotateCcw className="size-4" /> {t("refund")}</Button>)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <LoadMore q={payments} />
          </CardContent></HudCard>
        </TabsContent>
        <TabsContent value="packs"><HudCard><CardContent className="pt-4"><ProductEditor kind="packs" /></CardContent></HudCard></TabsContent>
        <TabsContent value="plans"><HudCard><CardContent className="pt-4"><ProductEditor kind="plans" /></CardContent></HudCard></TabsContent>
        <TabsContent value="webhooks">
          <HudCard><CardContent className="pt-4">
            <Table>
              <TableHeader><TableRow><TableHead>{t("received")}</TableHead><TableHead>{t("provider")}</TableHead><TableHead>{t("event")}</TableHead><TableHead>{t("status")}</TableHead></TableRow></TableHeader>
              <TableBody>
                {webhooks.rows.map((w) => (
                  <TableRow key={w.id}>
                    <TableCell className="text-xs">{formatDateTime(w.received_at, locale)}</TableCell><TableCell>{w.provider}</TableCell>
                    <TableCell className="font-mono text-xs">{w.event_type}<span className="block text-muted-foreground">{w.event_id}</span></TableCell>
                    <TableCell>{w.error ? <span className="text-xs text-fake">{w.error.slice(0, 120)}</span> : <StatusChip status={w.processed_at ? "succeeded" : "pending"} />}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <LoadMore q={webhooks} />
          </CardContent></HudCard>
        </TabsContent>
      </Tabs>
      <RefundDialog payment={refunding} onClose={() => setRefunding(null)} />
    </div>
  )
}

/* ---------------- API usage / audit log ---------------- */

export function AdminApiUsage() {
  const t = useTranslations("admin.apiUsage")
  const { data: usage, isLoading, error } = useQuery({ queryKey: qk.admin("api-usage"), queryFn: async () => data(await api.GET("/api/v1/admin/api-usage")) })
  if (isLoading) return <Loading />
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={9} title={t("title")} description={t("subtitle", { count: usage?.active_keys ?? 0 })} />
      <AdminError error={error} />
      <HudCard><CardContent className="pt-4">
        <Table>
          <TableHeader><TableRow><TableHead>{t("key")}</TableHead><TableHead>{t("owner")}</TableHead><TableHead className="text-right">{t("requests")}</TableHead>
            <TableHead className="text-right">{t("errors")}</TableHead><TableHead className="text-right">{t("jobs")}</TableHead><TableHead className="text-right">{t("credits")}</TableHead></TableRow></TableHeader>
          <TableBody>
            {(usage?.keys ?? []).map((k) => (
              <TableRow key={k.api_key_id}>
                <TableCell>{k.api_key__name}<span className="block font-mono text-[10px] text-muted-foreground">{k.api_key__prefix}</span></TableCell>
                <TableCell className="text-xs">{k.api_key__user__email}</TableCell>
                <TableCell className="text-right tabular-nums">{k.requests}</TableCell>
                <TableCell className="text-right tabular-nums">{k.errors}</TableCell>
                <TableCell className="text-right tabular-nums">{k.jobs}</TableCell>
                <TableCell className="text-right tabular-nums">{k.credits}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent></HudCard>
    </div>
  )
}

export function AdminAuditLog() {
  const t = useTranslations("admin.audit")
  const locale = useLocale()
  const [action, setAction] = useState("")
  const list = usePaged(qk.admin("audit", { action }), async (cursor) => data(await api.GET("/api/v1/admin/audit-log", {
    params: { query: { cursor, action: action || undefined } as never } })))
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={10} title={t("title")} description={t("subtitle")}
        actions={<Button asChild variant="outline"><a href={`/api/v1/admin/audit-log?format=csv${action ? `&action=${encodeURIComponent(action)}` : ""}`} download>
          <Download className="size-4" /> {t("export")}</a></Button>} />
      <Input value={action} onChange={(e) => setAction(e.target.value)} placeholder={t("filter")} className="max-w-sm" aria-label={t("filter")} />
      <AdminError error={list.error} />
      <HudCard><CardContent className="pt-4">
        <Table>
          <TableHeader><TableRow><TableHead>{t("when")}</TableHead><TableHead>{t("actor")}</TableHead><TableHead>{t("action")}</TableHead>
            <TableHead>{t("target")}</TableHead><TableHead>{t("ip")}</TableHead></TableRow></TableHeader>
          <TableBody>
            {list.rows.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap text-xs">{formatDateTime(e.created_at, locale)}</TableCell>
                <TableCell className="text-xs">{e.actor_label}</TableCell>
                <TableCell className="font-mono text-xs">{e.action}</TableCell>
                <TableCell className="text-xs">{e.target_label || e.target_id}<span className="block text-muted-foreground">{e.target_type}</span></TableCell>
                <TableCell className="font-mono text-xs">{e.ip ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <LoadMore q={list} />
      </CardContent></HudCard>
    </div>
  )
}

/* ---------------- platform settings ---------------- */

export function AdminSettings() {
  const t = useTranslations("admin.settings")
  const qc = useQueryClient()
  const canEdit = useCan("manage_settings")
  const { data: s, isLoading, error } = useQuery({ queryKey: qk.admin("settings"), queryFn: async () => data(await api.GET("/api/v1/admin/settings")) })
  const [form, setForm] = useState<Record<string, unknown>>({})
  useEffect(() => { if (s) setForm(s as Record<string, unknown>) }, [s])
  const save = useMutation({ mutationFn: async () => {
      const { updated_at, ...body } = form
      void updated_at
      return data(await api.PATCH("/api/v1/admin/settings", { body: body as never }))
    },
    onSuccess: () => { toast.success(t("saved")); qc.invalidateQueries({ queryKey: qk.admin("settings") }); qc.invalidateQueries({ queryKey: qk.config }) },
    onError: onError(t("failed")) })
  if (isLoading) return <Loading />
  const bool = (k: string) => (
    <label key={k} className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
      <span>{t(`field.${k}`)}<span className="block text-xs text-muted-foreground">{t(`hint.${k}`)}</span></span>
      <Switch checked={!!form[k]} disabled={!canEdit} onCheckedChange={(v) => setForm({ ...form, [k]: v })} />
    </label>
  )
  const num = (k: string) => (
    <div key={k} className="flex items-center justify-between gap-3">
      <Label htmlFor={k} className="font-normal">{t(`field.${k}`)}</Label>
      <Input id={k} type="number" step={k === "fake_threshold" ? 0.05 : 1} min={0} className="w-28 text-right" disabled={!canEdit}
        value={Number(form[k] ?? 0)} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} />
    </div>
  )
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={11} title={t("title")} description={t("subtitle")}
        actions={canEdit && <Button onClick={() => save.mutate()} disabled={save.isPending}><Save className="size-4" /> {t("save")}</Button>} />
      <AdminError error={error} />
      <div className="grid gap-5 lg:grid-cols-2">
        <HudCard><CardHeader><Eyebrow index={1}>{t("opsEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("opsTitle")}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {["maintenance_mode", "signups_enabled", "guest_trial_enabled", "api_access_requires_plan"].map(bool)}
            <div className="space-y-1.5"><Label htmlFor="announcement">{t("field.announcement")}</Label>
              <Textarea id="announcement" rows={2} disabled={!canEdit} value={String(form.announcement ?? "")} onChange={(e) => setForm({ ...form, announcement: e.target.value })} /></div>
          </CardContent></HudCard>
        <HudCard><CardHeader><Eyebrow index={2}>{t("limitsEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("limitsTitle")}</CardTitle></CardHeader>
          <CardContent className="space-y-3">{["free_retention_days", "free_max_inflight_tasks", "fake_threshold"].map(num)}</CardContent></HudCard>
        <HudCard className="lg:col-span-2"><CardHeader><Eyebrow index={3}>{t("aiEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("aiTitle")}</CardTitle>
          <CardDescription>{t("aiHint")}</CardDescription></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {([["reasoning_engine", ["openclaude", "ollama"]], ["news_engine", ["openclaude", "claude"]]] as const).map(([k, options]) => (
              <div key={k} className="space-y-1.5"><Label>{t(`field.${k}`)}</Label>
                <Select value={String(form[k] ?? "")} onValueChange={(v) => setForm({ ...form, [k]: v })} disabled={!canEdit}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{options.map((o) => <SelectItem key={o} value={o}>{t(`engine.${o}`)}</SelectItem>)}</SelectContent>
                </Select></div>
            ))}
            {["reasoning_model", "news_model"].map((k) => (
              <div key={k} className="space-y-1.5"><Label htmlFor={k}>{t(`field.${k}`)}</Label>
                <Input id={k} className="font-mono" disabled={!canEdit} value={String(form[k] ?? "")} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>
            ))}
          </CardContent></HudCard>
      </div>
    </div>
  )
}

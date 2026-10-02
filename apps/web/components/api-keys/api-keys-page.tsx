"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BarChart3, Check, Copy, KeyRound, Loader2, MoreHorizontal, Pencil, Plus, RotateCw, ShieldAlert, Trash2 } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { toast } from "sonner"
import { z } from "zod"

import { ControlledField } from "@/components/forms/controlled-field"
import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { StatusChip } from "@/components/sml/status-chip"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { ApiKey } from "@/lib/api/types"
import { formatDateTime, formatRelative } from "@/lib/format"

const EXPIRY = ["never", "30", "90", "365"] as const

function CopyButton({ value, label }: { value: string; label: string }) {
  const [done, setDone] = useState(false)
  return (
    <Button type="button" variant="outline" size="sm" aria-label={label}
      onClick={async () => { await navigator.clipboard.writeText(value); setDone(true); setTimeout(() => setDone(false), 1500) }}>
      {done ? <Check className="size-4" /> : <Copy className="size-4" />}
    </Button>
  )
}

function SecretDialog({ secret, onClose }: { secret: string | null; onClose: () => void }) {
  const t = useTranslations("apiKeys")
  const origin = typeof window !== "undefined" ? window.location.origin : "https://securemachineslab.com"
  const curl = `curl -X POST ${origin}/api/v1/detect \\\n  -H "Authorization: Bearer ${secret}" \\\n  -H "Idempotency-Key: $(uuidgen)" \\\n  -F file=@photo.jpg`
  return (
    <Dialog open={!!secret} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("secret.title")}</DialogTitle>
          <DialogDescription>{t("secret.body")}</DialogDescription>
        </DialogHeader>
        <Alert className="border-warn/40 bg-warn/10"><ShieldAlert className="size-4" /><AlertDescription>{t("secret.warning")}</AlertDescription></Alert>
        <div className="flex items-center gap-2">
          <code className="flex-1 break-all rounded-md border bg-muted px-3 py-2 font-mono text-sm">{secret}</code>
          <CopyButton value={secret ?? ""} label={t("copy")} />
        </div>
        <div className="space-y-1.5">
          <p className="hud-eyebrow">{t("secret.tryIt")}</p>
          <pre className="overflow-x-auto rounded-md border bg-[#1f2a3d] p-3 font-mono text-xs text-[#dbe7ff]">{curl}</pre>
        </div>
        <DialogFooter><Button onClick={onClose}>{t("secret.done")}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function KeyForm({ initial, onDone }: { initial?: ApiKey; onDone: (plaintext?: string) => void }) {
  const t = useTranslations("apiKeys")
  const qc = useQueryClient()
  const { data: scopes } = useQuery({ queryKey: qk.scopes, queryFn: async () => data(await api.GET("/api/v1/api-keys/scopes")) })
  const schema = z.object({
    name: z.string().min(1, t("form.nameRequired")).max(100),
    scopes: z.array(z.string()).min(1, t("form.scopeRequired")),
    expiry: z.enum(EXPIRY),
    allowed_ips: z.string(),
    rate_limit_per_minute: z.string().regex(/^\d*$/, t("form.number")),
  })
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: initial?.name ?? "", scopes: initial?.scopes ?? ["detect:write", "jobs:read", "reports:read", "credits:read"],
      expiry: "never", allowed_ips: (initial?.allowed_ips ?? []).join("\n"),
      rate_limit_per_minute: initial?.rate_limit_per_minute ? String(initial.rate_limit_per_minute) : "",
    },
  })
  const save = useMutation({
    mutationFn: async (v: z.infer<typeof schema>) => {
      const body = {
        name: v.name, scopes: v.scopes as ApiKey["scopes"],
        allowed_ips: v.allowed_ips.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean),
        rate_limit_per_minute: v.rate_limit_per_minute ? Number(v.rate_limit_per_minute) : null,
        ...(v.expiry !== "never" ? { expires_at: new Date(Date.now() + Number(v.expiry) * 86400_000).toISOString() } : {}),
      }
      if (initial) {
        data(await api.PATCH("/api/v1/api-keys/{id}", { params: { path: { id: initial.id } }, body }))
        return undefined
      }
      return data(await api.POST("/api/v1/api-keys", { body: body as never })).key
    },
    onSuccess: (plaintext) => { qc.invalidateQueries({ queryKey: qk.apiKeys }); onDone(plaintext) },
    onError: (e) => {
      if (isApiError(e)) {
        for (const [field, message] of Object.entries(e.fieldErrors)) {
          if (field in form.getValues()) form.setError(field as "name", { message })
        }
        toast.error(e.detail)
      }
    },
  })
  return (
    <form onSubmit={form.handleSubmit((v) => save.mutate(v))} className="space-y-4">
      <ControlledField control={form.control} name="name" label={t("form.name")} description={t("form.nameHint")}>
        {(field) => <Input autoFocus {...field} />}
      </ControlledField>
      <ControlledField control={form.control} name="scopes" label={t("form.scopes")}>
        {({ value, onChange }) => (
          <div className="grid gap-2 sm:grid-cols-2">
            {scopes?.map((s) => (
              <label key={s.id} className="flex items-start gap-2 rounded-md border p-2 text-sm">
                <Checkbox checked={value.includes(s.id)}
                  onCheckedChange={(on) => onChange(on ? [...value, s.id] : value.filter((x) => x !== s.id))} />
                <span><span className="font-mono text-xs">{s.id}</span><span className="block text-xs text-muted-foreground">{s.label}</span></span>
              </label>
            ))}
          </div>
        )}
      </ControlledField>
      {!initial && (
        <ControlledField control={form.control} name="expiry" label={t("form.expiry")}>
          {(field) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger id={field.id} className="w-48"><SelectValue /></SelectTrigger>
              <SelectContent>{EXPIRY.map((e) => <SelectItem key={e} value={e}>{t(`form.expiryOption.${e}`)}</SelectItem>)}</SelectContent>
            </Select>
          )}
        </ControlledField>
      )}
      <ControlledField control={form.control} name="allowed_ips" label={t("form.ips")} description={t("form.ipsHint")}>
        {(field) => <Textarea rows={3} className="font-mono text-xs" placeholder="203.0.113.10&#10;198.51.100.0/24" {...field} />}
      </ControlledField>
      <ControlledField control={form.control} name="rate_limit_per_minute" label={t("form.rateLimit")} description={t("form.rateLimitHint")}>
        {(field) => <Input inputMode="numeric" className="w-40" placeholder="240" {...field} />}
      </ControlledField>
      <DialogFooter>
        <Button type="submit" disabled={save.isPending}>{save.isPending && <Loader2 className="size-4 animate-spin" />}
          {initial ? t("form.save") : t("form.create")}</Button>
      </DialogFooter>
    </form>
  )
}

function UsageSheet({ apiKey, onClose }: { apiKey: ApiKey | null; onClose: () => void }) {
  const t = useTranslations("apiKeys")
  const locale = useLocale()
  const { data: usage, isLoading } = useQuery({
    queryKey: qk.apiKeyUsage(apiKey?.id ?? ""), enabled: !!apiKey,
    queryFn: async () => data(await api.GET("/api/v1/api-keys/{id}/usage", { params: { path: { id: apiKey!.id } } })),
  })
  const config = { requests: { label: t("usage.requests"), color: "var(--viz-real)" } } satisfies ChartConfig
  return (
    <Sheet open={!!apiKey} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{apiKey?.name}</SheetTitle>
          <SheetDescription className="font-mono">{apiKey?.display_key}</SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-6">
          {isLoading || !usage ? <Skeleton className="h-64" /> : (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {(["requests", "errors", "jobs_created", "credits_spent"] as const).map((k) => (
                  <div key={k} className="rounded-lg border p-3">
                    <p className="mono-label text-muted-foreground">{t(`usage.${k}`)}</p>
                    <p className="font-mono text-xl tabular-nums">{usage.totals[k]}</p>
                  </div>
                ))}
              </div>
              {usage.daily.length > 0 && (
                <ChartContainer config={config} className="h-40 w-full">
                  <BarChart data={usage.daily} margin={{ left: -16 }}>
                    <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
                    <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24}
                      tickFormatter={(v) => new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" }).format(new Date(v))} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={36} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="requests" fill="var(--color-requests)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ChartContainer>
              )}
              <div className="space-y-2">
                <p className="hud-eyebrow">{t("usage.recent")}</p>
                {usage.recent_requests.length ? (
                  <Table>
                    <TableHeader><TableRow><TableHead>{t("usage.when")}</TableHead><TableHead>{t("usage.request")}</TableHead>
                      <TableHead className="text-right">{t("usage.status")}</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {usage.recent_requests.map((r, i) => (
                        <TableRow key={i}>
                          <TableCell className="whitespace-nowrap text-xs">{formatRelative(r.created_at, locale)}</TableCell>
                          <TableCell className="font-mono text-xs">{r.method} {r.path}<span className="block text-muted-foreground">{r.ip} · {r.duration_ms}ms</span></TableCell>
                          <TableCell className={`text-right font-mono text-xs ${r.status >= 400 ? "text-fake" : ""}`}>{r.status}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : <p className="text-sm text-muted-foreground">{t("usage.none")}</p>}
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function ApiKeysPage() {
  const t = useTranslations("apiKeys")
  const locale = useLocale()
  const qc = useQueryClient()
  const { data: keys, isLoading } = useQuery({ queryKey: qk.apiKeys, queryFn: async () => data(await api.GET("/api/v1/api-keys")) })
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<ApiKey | null>(null)
  const [secret, setSecret] = useState<string | null>(null)
  const [usageFor, setUsageFor] = useState<ApiKey | null>(null)
  const [revoking, setRevoking] = useState<ApiKey | null>(null)
  const rotate = useMutation({
    mutationFn: async (id: string) => data(await api.POST("/api/v1/api-keys/{id}/rotate", { params: { path: { id } } })),
    onSuccess: (k) => { setSecret(k.key); qc.invalidateQueries({ queryKey: qk.apiKeys }) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  const revoke = useMutation({
    mutationFn: async (id: string) => api.DELETE("/api/v1/api-keys/{id}", { params: { path: { id } } }),
    onSuccess: () => { toast.success(t("revoked")); qc.invalidateQueries({ queryKey: qk.apiKeys }) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  const visible = (keys ?? []).filter((k) => k.status !== "revoked")
  const revoked = (keys ?? []).filter((k) => k.status === "revoked")

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={5} title={t("title")} description={t("subtitle")}
        actions={<><Button variant="outline" asChild><a href="/docs">{t("docs")}</a></Button>
          <Button onClick={() => setCreating(true)}><Plus className="size-4" /> {t("create")}</Button></>} />

      {isLoading ? <Skeleton className="h-48" /> : !visible.length ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon"><KeyRound /></EmptyMedia>
            <EmptyTitle>{t("emptyTitle")}</EmptyTitle>
            <EmptyDescription>{t("emptyHint")}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent><Button onClick={() => setCreating(true)}><Plus className="size-4" /> {t("create")}</Button></EmptyContent>
        </Empty>
      ) : (
        <HudCard>
          <CardContent className="pt-4">
            <Table>
              <TableHeader><TableRow>
                <TableHead>{t("col.name")}</TableHead><TableHead>{t("col.scopes")}</TableHead>
                <TableHead>{t("col.restrictions")}</TableHead><TableHead>{t("col.lastUsed")}</TableHead>
                <TableHead>{t("col.status")}</TableHead><TableHead className="w-10"><span className="sr-only">{t("col.actions")}</span></TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {visible.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell><span className="font-medium">{k.name}</span><span className="block font-mono text-xs text-muted-foreground">{k.display_key}</span></TableCell>
                    <TableCell><div className="flex max-w-64 flex-wrap gap-1">{k.scopes.map((s) => <Badge key={s} variant="outline" className="font-mono text-[10px]">{s}</Badge>)}</div></TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {k.allowed_ips.length ? t("ipCount", { count: k.allowed_ips.length }) : t("anyIp")}
                      {k.rate_limit_per_minute ? ` · ${t("perMinute", { count: k.rate_limit_per_minute })}` : ""}
                      {k.expires_at ? <span className="block">{t("expires", { date: formatDateTime(k.expires_at, locale) })}</span> : null}
                    </TableCell>
                    <TableCell className="text-xs">{k.last_used_at ? formatRelative(k.last_used_at, locale) : t("never")}
                      {k.last_used_ip && <span className="block font-mono text-muted-foreground">{k.last_used_ip}</span>}</TableCell>
                    <TableCell><StatusChip status={k.status === "active" ? "active" : "expired"} /></TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label={t("col.actions")}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onSelect={() => setUsageFor(k)}><BarChart3 /> {t("usage.title")}</DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => setEditing(k)}><Pencil /> {t("edit")}</DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => rotate.mutate(k.id)}><RotateCw /> {t("rotate")}</DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem variant="destructive" onSelect={() => setRevoking(k)}><Trash2 /> {t("revoke")}</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </HudCard>
      )}

      <HudCard>
        <CardHeader>
          <Eyebrow>{t("security.eyebrow")}</Eyebrow>
          <CardTitle className="mt-1 text-base">{t("security.title")}</CardTitle>
          <CardDescription>{t("security.body")}</CardDescription>
        </CardHeader>
      </HudCard>

      {revoked.length > 0 && (
        <details className="text-sm text-muted-foreground">
          <summary className="cursor-pointer">{t("revokedKeys", { count: revoked.length })}</summary>
          <ul className="mt-2 space-y-1">{revoked.map((k) => <li key={k.id} className="font-mono text-xs">{k.name} · {k.display_key}</li>)}</ul>
        </details>
      )}

      <Dialog open={creating || !!editing} onOpenChange={(o) => { if (!o) { setCreating(false); setEditing(null) } }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editing ? t("editTitle") : t("createTitle")}</DialogTitle>
            <DialogDescription>{t("createHint")}</DialogDescription>
          </DialogHeader>
          <KeyForm key={editing?.id ?? "new"} initial={editing ?? undefined}
            onDone={(plain) => { setCreating(false); setEditing(null); if (plain) setSecret(plain); else toast.success(t("saved")) }} />
        </DialogContent>
      </Dialog>
      <SecretDialog secret={secret} onClose={() => setSecret(null)} />
      <UsageSheet apiKey={usageFor} onClose={() => setUsageFor(null)} />
      <AlertDialog open={!!revoking} onOpenChange={(o) => !o && setRevoking(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("revokeTitle", { name: revoking?.name ?? "" })}</AlertDialogTitle>
            <AlertDialogDescription>{t("revokeBody")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("keep")}</AlertDialogCancel>
            <AlertDialogAction onClick={() => revoking && revoke.mutate(revoking.id)}>{t("revoke")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <Label className="sr-only">{t("title")}</Label>
    </div>
  )
}

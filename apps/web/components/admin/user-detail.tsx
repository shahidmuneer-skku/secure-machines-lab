"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Ban, CheckCircle2, KeyRound, LogOut } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { StatusChip } from "@/components/sml/status-chip"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useDraft } from "@/hooks/use-draft"
import { useCan, useMe } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { formatDateTime } from "@/lib/format"

import { BlockUserDialog } from "./block-user-dialog"
import { AdminError, Loading } from "./common"
import { CreditAdjust } from "./credit-adjust"

const MODULES = ["detect", "long_video", "news"] as const
const AUDIT = ["face", "safety", "fas", "metadata"] as const
const ROLES = ["super_admin", "admin", "billing_admin", "support", "user"]

type Nullable<T> = T[] | null

/** null = unrestricted; array = allow only these. */
function RestrictionPicker<T extends string>({ label, all, value, onChange, labelFor }: {
  label: string; all: readonly T[]; value: Nullable<T>; onChange: (v: Nullable<T>) => void; labelFor: (v: T) => string
}) {
  const t = useTranslations("admin.user")
  const restricted = value !== null
  return (
    <fieldset className="space-y-2 rounded-lg border p-3">
      <legend className="px-1 text-sm font-medium">{label}</legend>
      <label className="flex items-center gap-2 text-sm">
        <Switch checked={restricted} onCheckedChange={(on) => onChange(on ? [...all] : null)} />
        {restricted ? t("restricted") : t("unrestricted")}
      </label>
      {restricted && (
        <div className="grid gap-1.5 sm:grid-cols-2">
          {all.map((item) => (
            <label key={item} className="flex items-center gap-2 text-sm">
              <Checkbox checked={value!.includes(item)}
                onCheckedChange={(on) => onChange(on ? [...value!, item] : value!.filter((x) => x !== item))} />
              {labelFor(item)}
            </label>
          ))}
        </div>
      )}
    </fieldset>
  )
}

type AccessForm = {
  allowed_modules: Nullable<string>; allowed_models: Nullable<string>; allowed_audit_steps: Nullable<string>
  max_inflight_tasks: string; retention_days_override: string; unlimited_credits: boolean; notes: string
}
const NO_ROLES: string[] = []

export function AdminUserDetail({ id }: { id: string }) {
  const t = useTranslations("admin.user")
  const locale = useLocale()
  const qc = useQueryClient()
  // Detector ids for the access-policy restriction list (admin endpoint; users never see these).
  const detectors = useQuery({ queryKey: qk.admin("models"),
    queryFn: async () => data(await api.GET("/api/v1/admin/models")) })
  const canManage = useCan("manage_users")
  const canAccess = useCan("manage_user_access")
  const canRoles = useCan("manage_roles")
  const canGrant = useCan("grant_credits")
  const user = useQuery({ queryKey: qk.admin("user", id), queryFn: async () => data(await api.GET("/api/v1/admin/users/{id}", { params: { path: { id } } })) })
  const policy = useQuery({ queryKey: qk.admin("user", id, "access"), queryFn: async () => data(await api.GET("/api/v1/admin/users/{id}/access", { params: { path: { id } } })) })
  const ledger = useQuery({ queryKey: qk.admin("user", id, "ledger"), queryFn: async () => data(await api.GET("/api/v1/admin/users/{id}/ledger", { params: { path: { id } } })) as unknown as
    { id: string; created_at: string; kind: string; delta: number; balance_after: number; memo: string; actor__email: string | null }[] })
  const rolesDraft = useDraft<string[]>(user.data?.roles, NO_ROLES)
  const roles = rolesDraft.value
  const setRoles = rolesDraft.set
  const serverAccess = useMemo<AccessForm | undefined>(() => policy.data && {
    allowed_modules: policy.data.allowed_modules ?? null, allowed_models: policy.data.allowed_models ?? null,
    allowed_audit_steps: policy.data.allowed_audit_steps ?? null, max_inflight_tasks: policy.data.max_inflight_tasks?.toString() ?? "",
    retention_days_override: policy.data.retention_days_override?.toString() ?? "", unlimited_credits: !!policy.data.unlimited_credits,
    notes: policy.data.notes ?? "" }, [policy.data])
  const accessDraft = useDraft<AccessForm | null>(serverAccess, null)
  const access = accessDraft.value
  const setAccess = accessDraft.set
  const me = useMe()
  const [blockOpen, setBlockOpen] = useState(false)

  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: qk.admin("user", id) }),
    qc.invalidateQueries({ queryKey: ["admin", "users"] })])
  const onError = (e: unknown) => toast.error(isApiError(e) ? e.detail : t("failed"))
  const saveRoles = useMutation({ mutationFn: async () => data(await api.PUT("/api/v1/admin/users/{id}/roles", { params: { path: { id } }, body: { roles } as never })),
    onSuccess: async () => { toast.success(t("rolesSaved")); await refresh(); rolesDraft.reset() }, onError })
  const saveAccess = useMutation({
    mutationFn: async () => data(await api.PUT("/api/v1/admin/users/{id}/access", { params: { path: { id } }, body: {
      allowed_modules: access!.allowed_modules as never, allowed_models: access!.allowed_models, allowed_audit_steps: access!.allowed_audit_steps as never,
      max_inflight_tasks: access!.max_inflight_tasks ? Number(access!.max_inflight_tasks) : null,
      retention_days_override: access!.retention_days_override ? Number(access!.retention_days_override) : null,
      unlimited_credits: access!.unlimited_credits, notes: access!.notes } as never })),
    onSuccess: async () => { toast.success(t("accessSaved")); await refresh(); accessDraft.reset() }, onError })
  const action = useMutation({
    mutationFn: async (a: "reset-mfa" | "revoke-sessions") => {
      const params = { path: { id } }
      return data(a === "reset-mfa" ? await api.POST("/api/v1/admin/users/{id}/reset-mfa", { params })
        : await api.POST("/api/v1/admin/users/{id}/revoke-sessions", { params }))
    },
    onSuccess: () => { toast.success(t("done")); refresh() }, onError })

  if (user.isLoading) return <Loading />
  if (user.error || !user.data) return <AdminError error={user.error} />
  const u = user.data
  const isSelf = me.data?.id === u.id
  const modelIds = (detectors.data ?? []).map((m) => m.id)
  return (
    <div className="space-y-5">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground"><Link href="/admin/users"><ArrowLeft className="size-4" /> {t("back")}</Link></Button>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{u.email}</h1>
        {isSelf && <Badge variant="secondary">{t("you")}</Badge>}
        <StatusChip status={u.is_active ? "active" : "blocked"} />
        <span className="text-sm text-muted-foreground">{t("balance", { count: u.balance })}</span>
        <div className="ml-auto flex flex-wrap gap-2">
          {canManage && (isSelf ? (
            <Tooltip>
              <TooltipTrigger asChild><span tabIndex={0}><Button variant="outline" size="sm" disabled><Ban className="size-4" /> {t("block")}</Button></span></TooltipTrigger>
              <TooltipContent>{t("cannotBlockSelf")}</TooltipContent>
            </Tooltip>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setBlockOpen(true)}
              className={u.is_active ? "text-fake hover:text-fake" : undefined}>
              {u.is_active ? <><Ban className="size-4" /> {t("block")}</> : <><CheckCircle2 className="size-4" /> {t("unblock")}</>}
            </Button>
          ))}
          {canManage && <Button variant="outline" size="sm" onClick={() => action.mutate("revoke-sessions")}><LogOut className="size-4" /> {t("revokeSessions")}</Button>}
          {canManage && u.has_mfa && (
            <AlertDialog>
              <AlertDialogTrigger asChild><Button variant="outline" size="sm"><KeyRound className="size-4" /> {t("resetMfa")}</Button></AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader><AlertDialogTitle>{t("resetMfaTitle", { email: u.email })}</AlertDialogTitle>
                  <AlertDialogDescription>{t("resetMfaBody")}</AlertDialogDescription></AlertDialogHeader>
                <AlertDialogFooter><AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
                  <AlertDialogAction variant="destructive" onClick={() => action.mutate("reset-mfa")}>{t("resetMfa")}</AlertDialogAction></AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </div>
      {!u.is_active && (
        <Alert variant="destructive">
          <Ban className="size-4" />
          <AlertTitle>{t("blockedTitle")}</AlertTitle>
          <AlertDescription>{u.disabled_reason || t("blockedNoReason")}</AlertDescription>
        </Alert>
      )}
      <BlockUserDialog user={u} open={blockOpen} onOpenChange={setBlockOpen} />

      <div className="grid gap-5 lg:grid-cols-2">
        <HudCard>
          <CardHeader><Eyebrow index={1}>{t("rolesEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("rolesTitle")}</CardTitle>
            <CardDescription>{t("rolesHint")}</CardDescription></CardHeader>
          <CardContent className="space-y-3">
            {ROLES.map((r) => (
              <label key={r} className="flex items-center gap-2 text-sm">
                <Checkbox checked={roles.includes(r)} disabled={!canRoles}
                  onCheckedChange={(on) => setRoles(on ? [...roles, r] : roles.filter((x) => x !== r))} />
                <span className="font-mono">{r}</span>
              </label>
            ))}
            {canRoles && <Button size="sm" onClick={() => saveRoles.mutate()} disabled={saveRoles.isPending}>{t("saveRoles")}</Button>}
          </CardContent>
        </HudCard>

        <HudCard id="credits" className="scroll-mt-20">
          <CardHeader><Eyebrow index={2}>{t("creditsEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("creditsTitle")}</CardTitle>
            <CardDescription>{t("creditsHint")}</CardDescription></CardHeader>
          <CardContent>
            {canGrant ? <CreditAdjust user={u} isSelf={isSelf} /> : <p className="text-sm text-muted-foreground">{t("noPermission")}</p>}
          </CardContent>
        </HudCard>
      </div>

      {access && (
        <HudCard>
          <CardHeader><Eyebrow index={3}>{t("accessEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("accessTitle")}</CardTitle>
            <CardDescription>{t("accessHint")}</CardDescription></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-3">
              <RestrictionPicker label={t("modules")} all={MODULES as readonly string[]} value={access.allowed_modules}
                onChange={(v) => setAccess({ ...access, allowed_modules: v })} labelFor={(m) => t(`module.${m}`)} />
              <RestrictionPicker label={t("auditSteps")} all={AUDIT as readonly string[]} value={access.allowed_audit_steps}
                onChange={(v) => setAccess({ ...access, allowed_audit_steps: v })} labelFor={(s) => s} />
              <RestrictionPicker label={t("models")} all={modelIds} value={access.allowed_models}
                onChange={(v) => setAccess({ ...access, allowed_models: v })} labelFor={(m) => m} />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1.5"><Label htmlFor="inflight">{t("maxInflight")}</Label>
                <Input id="inflight" inputMode="numeric" value={access.max_inflight_tasks} placeholder={t("planDefault")}
                  onChange={(e) => setAccess({ ...access, max_inflight_tasks: e.target.value })} /></div>
              <div className="space-y-1.5"><Label htmlFor="ret">{t("retention")}</Label>
                <Input id="ret" inputMode="numeric" value={access.retention_days_override} placeholder={t("planDefault")}
                  onChange={(e) => setAccess({ ...access, retention_days_override: e.target.value })} /></div>
              <label className="flex items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                <span>{t("unlimited")}<span className="block text-xs text-muted-foreground">{t("unlimitedHint")}</span></span>
                <Switch checked={access.unlimited_credits} onCheckedChange={(v) => setAccess({ ...access, unlimited_credits: v })} />
              </label>
            </div>
            <div className="space-y-1.5"><Label htmlFor="notes">{t("notes")}</Label>
              <Textarea id="notes" rows={2} value={access.notes} onChange={(e) => setAccess({ ...access, notes: e.target.value })} /></div>
            {canAccess && <Button size="sm" onClick={() => saveAccess.mutate()} disabled={saveAccess.isPending}>{t("saveAccess")}</Button>}
          </CardContent>
        </HudCard>
      )}

      <HudCard>
        <CardHeader><Eyebrow index={4}>{t("ledgerEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("ledgerTitle")}</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>{t("when")}</TableHead><TableHead>{t("kind")}</TableHead><TableHead className="text-right">{t("change")}</TableHead>
              <TableHead className="text-right">{t("after")}</TableHead><TableHead>{t("by")}</TableHead></TableRow></TableHeader>
            <TableBody>
              {(ledger.data ?? []).map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="text-xs">{formatDateTime(e.created_at, locale)}</TableCell>
                  <TableCell>{e.kind}<span className="block text-xs text-muted-foreground">{e.memo}</span></TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{e.delta > 0 ? `+${e.delta}` : e.delta}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{e.balance_after}</TableCell>
                  <TableCell className="text-xs">{e.actor__email ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </HudCard>
    </div>
  )
}

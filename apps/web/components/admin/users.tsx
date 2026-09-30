"use client"

import { Ban, CheckCircle2, Coins, MoreHorizontal, Search, ShieldCheck, UserRound } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"

import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent } from "@/components/ui/card"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCan, useMe } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatDate, formatRelative } from "@/lib/format"

import { type BlockTarget, BlockUserDialog } from "./block-user-dialog"
import { AdminError, LoadMore, Loading, usePaged } from "./common"

const ROLES = ["super_admin", "admin", "billing_admin", "support", "user"]
const STATUSES = { any: undefined, active: "true", blocked: "false" } as const

export function AdminUsers() {
  const t = useTranslations("admin.users")
  const locale = useLocale()
  const me = useMe()
  const canManage = useCan("manage_users")
  const canGrant = useCan("grant_credits")
  const [q, setQ] = useState("")
  const [role, setRole] = useState("any")
  const [status, setStatus] = useState<keyof typeof STATUSES>("any")
  const [blockTarget, setBlockTarget] = useState<BlockTarget | null>(null)
  const list = usePaged(qk.admin("users", { q, role, status }), async (cursor) => data(await api.GET("/api/v1/admin/users", {
    params: { query: { cursor, q: q || undefined, role: role === "any" ? undefined : role, is_active: STATUSES[status] } as never } })))
  const myId = me.data?.id

  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={2} title={t("title")} description={t("subtitle")}
        actions={myId && (
          <Button asChild variant="outline" size="sm">
            <Link href={`/admin/users/${myId}#credits`}><UserRound className="size-4" /> {t("myAccount")}</Link>
          </Button>
        )} />
      <div className="flex flex-wrap gap-2">
        <div className="relative min-w-64 flex-1"><Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} aria-label={t("search")} /></div>
        <Select value={role} onValueChange={setRole}>
          <SelectTrigger className="w-44" aria-label={t("role")}><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="any">{t("anyRole")}</SelectItem>
            {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={status} onValueChange={(v) => setStatus(v as keyof typeof STATUSES)}>
          <SelectTrigger className="w-40" aria-label={t("status")}><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="any">{t("anyStatus")}</SelectItem>
            <SelectItem value="active">{t("statusActive")}</SelectItem>
            <SelectItem value="blocked">{t("statusBlocked")}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <AdminError error={list.error} />
      {list.isLoading ? <Loading /> : (
        <HudCard><CardContent className="pt-4">
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("col.user")}</TableHead><TableHead>{t("col.roles")}</TableHead><TableHead className="text-right">{t("col.balance")}</TableHead>
              <TableHead className="text-right">{t("col.jobs")}</TableHead><TableHead>{t("col.joined")}</TableHead><TableHead>{t("col.lastLogin")}</TableHead>
              <TableHead>{t("col.status")}</TableHead><TableHead className="w-10"><span className="sr-only">{t("col.actions")}</span></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {list.rows.map((u) => {
                const self = u.id === myId
                return (
                  <TableRow key={u.id}>
                    <TableCell>
                      <span className="flex items-center gap-2">
                        <Link href={`/admin/users/${u.id}`} className="font-medium hover:underline">{u.email}</Link>
                        {self && <Badge variant="secondary" className="text-[10px]">{t("you")}</Badge>}
                      </span>
                      <span className="block text-xs text-muted-foreground">{u.display_name}</span>
                    </TableCell>
                    <TableCell><div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} variant="outline">{r}</Badge>)}
                      {u.has_mfa && <ShieldCheck className="size-4 text-real" aria-label="MFA" />}</div></TableCell>
                    <TableCell className="text-right font-mono tabular-nums">{u.balance}</TableCell>
                    <TableCell className="text-right tabular-nums">{u.jobs_count}</TableCell>
                    <TableCell className="text-xs">{formatDate(u.date_joined, locale)}</TableCell>
                    <TableCell className="text-xs">{u.last_login ? formatRelative(u.last_login, locale) : "—"}</TableCell>
                    <TableCell>
                      <StatusChip status={u.is_active ? (u.email_verified ? "active" : "unverified") : "blocked"} />
                      {!u.is_active && u.disabled_reason && (
                        <span className="mt-0.5 block max-w-48 truncate text-xs text-muted-foreground" title={u.disabled_reason}>{u.disabled_reason}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm" aria-label={t("actionsFor", { email: u.email })}><MoreHorizontal className="size-4" /></Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild><Link href={`/admin/users/${u.id}`}><UserRound className="size-4" /> {t("open")}</Link></DropdownMenuItem>
                          {canGrant && (
                            <DropdownMenuItem asChild><Link href={`/admin/users/${u.id}#credits`}><Coins className="size-4" /> {t("adjustCredits")}</Link></DropdownMenuItem>
                          )}
                          {canManage && !self && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem variant={u.is_active ? "destructive" : "default"}
                                onSelect={() => setBlockTarget({ id: u.id, email: u.email, is_active: u.is_active ?? true })}>
                                {u.is_active ? <><Ban className="size-4" /> {t("block")}</> : <><CheckCircle2 className="size-4" /> {t("unblock")}</>}
                              </DropdownMenuItem>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })}
              {!list.rows.length && (
                <TableRow><TableCell colSpan={8} className="py-8 text-center text-sm text-muted-foreground">{t("empty")}</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
          <LoadMore q={list} />
        </CardContent></HudCard>
      )}
      <BlockUserDialog user={blockTarget} open={!!blockTarget} onOpenChange={(open) => { if (!open) setBlockTarget(null) }} />
    </div>
  )
}

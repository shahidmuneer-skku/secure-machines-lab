"use client"

import { Search, ShieldCheck } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"

import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { Badge } from "@/components/ui/badge"
import { CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatDate, formatRelative } from "@/lib/format"

import { AdminError, LoadMore, Loading, usePaged } from "./common"

const ROLES = ["super_admin", "admin", "billing_admin", "support", "user"]

export function AdminUsers() {
  const t = useTranslations("admin.users")
  const locale = useLocale()
  const [q, setQ] = useState("")
  const [role, setRole] = useState("any")
  const list = usePaged(qk.admin("users", { q, role }), async (cursor) => data(await api.GET("/api/v1/admin/users", {
    params: { query: { cursor, q: q || undefined, role: role === "any" ? undefined : role } as never } })))
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={2} title={t("title")} description={t("subtitle")} />
      <div className="flex flex-wrap gap-2">
        <div className="relative min-w-64 flex-1"><Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} aria-label={t("search")} /></div>
        <Select value={role} onValueChange={setRole}>
          <SelectTrigger className="w-44" aria-label={t("role")}><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="any">{t("anyRole")}</SelectItem>
            {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <AdminError error={list.error} />
      {list.isLoading ? <Loading /> : (
        <HudCard><CardContent className="pt-4">
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("col.user")}</TableHead><TableHead>{t("col.roles")}</TableHead><TableHead className="text-right">{t("col.balance")}</TableHead>
              <TableHead className="text-right">{t("col.jobs")}</TableHead><TableHead>{t("col.joined")}</TableHead><TableHead>{t("col.lastLogin")}</TableHead>
              <TableHead>{t("col.status")}</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {list.rows.map((u) => (
                <TableRow key={u.id} className="cursor-pointer">
                  <TableCell><Link href={`/admin/users/${u.id}`} className="font-medium hover:underline">{u.email}</Link>
                    <span className="block text-xs text-muted-foreground">{u.display_name}</span></TableCell>
                  <TableCell><div className="flex flex-wrap gap-1">{u.roles.map((r) => <Badge key={r} variant="outline">{r}</Badge>)}
                    {u.has_mfa && <ShieldCheck className="size-4 text-real" aria-label="MFA" />}</div></TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{u.balance}</TableCell>
                  <TableCell className="text-right tabular-nums">{u.jobs_count}</TableCell>
                  <TableCell className="text-xs">{formatDate(u.date_joined, locale)}</TableCell>
                  <TableCell className="text-xs">{u.last_login ? formatRelative(u.last_login, locale) : "—"}</TableCell>
                  <TableCell><StatusChip status={u.is_active ? (u.email_verified ? "active" : "pending") : "canceled"} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <LoadMore q={list} />
        </CardContent></HudCard>
      )}
    </div>
  )
}

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Loader2, Trash2 } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { PasswordInput } from "@/components/auth/password-input"
import { setLocaleCookie } from "@/components/app-shell/locale-switcher"
import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import {
  AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LOCALE_LABELS, LOCALES, type Locale } from "@/i18n/config"
import { useMe } from "@/hooks/use-me"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { formatDateTime } from "@/lib/format"

import { SecuritySection } from "./security-section"

const TIME_ZONES = ["Asia/Seoul", "UTC", "Europe/Berlin", "Europe/London", "America/New_York", "America/Los_Angeles", "Asia/Tokyo"]

function ProfileSection() {
  const t = useTranslations("settings.profile")
  const { data: me, isLoading } = useMe()
  const qc = useQueryClient()
  const router = useRouter()
  const [form, setForm] = useState({ display_name: "", locale: "en", time_zone: "Asia/Seoul", marketing_opt_in: false })
  useEffect(() => {
    if (me) setForm({ display_name: me.display_name ?? "", locale: me.locale ?? "en", time_zone: me.time_zone ?? "Asia/Seoul",
      marketing_opt_in: !!me.marketing_opt_in })
  }, [me])
  const save = useMutation({
    mutationFn: async () => data(await api.PATCH("/api/v1/me", { body: form as never })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.me })
      setLocaleCookie(form.locale as Locale)
      router.refresh()
      toast.success(t("saved"))
    },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })
  if (isLoading || !me) return <Skeleton className="h-64" />
  return (
    <HudCard>
      <CardHeader><Eyebrow index={1}>{t("eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("title")}</CardTitle></CardHeader>
      <CardContent>
        <form className="grid max-w-lg gap-4" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
          <div className="space-y-1.5"><Label htmlFor="email">{t("email")}</Label><Input id="email" value={me.email} disabled /></div>
          <div className="space-y-1.5"><Label htmlFor="name">{t("name")}</Label>
            <Input id="name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5"><Label htmlFor="lang">{t("language")}</Label>
              <Select value={form.locale} onValueChange={(v) => setForm({ ...form, locale: v })}>
                <SelectTrigger id="lang"><SelectValue /></SelectTrigger>
                <SelectContent>{LOCALES.map((l) => <SelectItem key={l} value={l}>{LOCALE_LABELS[l].native}</SelectItem>)}</SelectContent>
              </Select></div>
            <div className="space-y-1.5"><Label htmlFor="tz">{t("timeZone")}</Label>
              <Select value={form.time_zone} onValueChange={(v) => setForm({ ...form, time_zone: v })}>
                <SelectTrigger id="tz"><SelectValue /></SelectTrigger>
                <SelectContent>{TIME_ZONES.map((z) => <SelectItem key={z} value={z}>{z}</SelectItem>)}</SelectContent>
              </Select></div>
          </div>
          <label className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
            <span>{t("marketing")}<span className="block text-xs text-muted-foreground">{t("marketingHint")}</span></span>
            <Switch checked={form.marketing_opt_in} onCheckedChange={(v) => setForm({ ...form, marketing_opt_in: v })} />
          </label>
          <p className="text-xs text-muted-foreground">{t("roles", { roles: me.roles.join(", ") })} · {t("joined", { date: formatDateTime(me.date_joined, form.locale) })}</p>
          <Button type="submit" className="w-fit" disabled={save.isPending}>{save.isPending && <Loader2 className="size-4 animate-spin" />} {t("save")}</Button>
        </form>
      </CardContent>
    </HudCard>
  )
}

function PrivacySection() {
  const t = useTranslations("settings.privacy")
  const qc = useQueryClient()
  const { data: consent } = useQuery({ queryKey: qk.consent, queryFn: async () => data(await api.GET("/api/v1/me/consent")) })
  const setConsent = useMutation({
    mutationFn: async (granted: boolean) => data(await api.PUT("/api/v1/me/consent", { body: { granted } })),
    onSuccess: (c) => { qc.setQueryData(qk.consent, c); toast.success(c.granted ? t("consentGranted") : t("consentWithdrawn")) },
  })
  const [deleting, setDeleting] = useState(false)
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const remove = useMutation({
    mutationFn: async () => api.POST("/api/v1/me/delete", { body: { password, confirm } }),
    onSuccess: () => window.location.assign("/"),
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("deleteFailed")),
  })
  return (
    <div className="space-y-5">
      <HudCard>
        <CardHeader><Eyebrow index={1}>{t("eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("consentTitle")}</CardTitle>
          <CardDescription>{t("consentBody")}</CardDescription></CardHeader>
        <CardContent>
          <label className="flex items-center justify-between gap-3 rounded-lg border p-3 text-sm">
            <span>{t("consentToggle")}{consent?.granted_at && consent.granted && (
              <span className="block text-xs text-muted-foreground">{t("since", { date: formatDateTime(consent.granted_at, "en") })}</span>)}</span>
            <Switch checked={!!consent?.granted} onCheckedChange={(v) => setConsent.mutate(v)} aria-label={t("consentToggle")} />
          </label>
        </CardContent>
      </HudCard>
      <HudCard>
        <CardHeader><Eyebrow index={2}>{t("dataEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("exportTitle")}</CardTitle>
          <CardDescription>{t("exportBody")}</CardDescription></CardHeader>
        <CardContent><Button asChild variant="outline"><a href="/api/v1/me/export" download><Download className="size-4" /> {t("export")}</a></Button></CardContent>
      </HudCard>
      <HudCard className="border-fake/40">
        <CardHeader><Eyebrow index={3}>{t("dangerEyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("deleteTitle")}</CardTitle>
          <CardDescription>{t("deleteBody")}</CardDescription></CardHeader>
        <CardContent><Button variant="destructive" onClick={() => setDeleting(true)}><Trash2 className="size-4" /> {t("delete")}</Button></CardContent>
      </HudCard>
      <AlertDialog open={deleting} onOpenChange={setDeleting}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>{t("confirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("confirmBody")}</AlertDialogDescription></AlertDialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label htmlFor="del-pw">{t("password")}</Label>
              <PasswordInput id="del-pw" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></div>
            <div className="space-y-1.5"><Label htmlFor="del-confirm">{t("typeDelete")}</Label>
              <Input id="del-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="font-mono" /></div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <Button variant="destructive" disabled={confirm !== "DELETE" || !password || remove.isPending} onClick={() => remove.mutate()}>
              {remove.isPending && <Loader2 className="size-4 animate-spin" />} {t("deleteForever")}</Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export function SettingsPage() {
  const t = useTranslations("settings")
  const params = useSearchParams()
  const router = useRouter()
  const tab = params.get("tab") ?? "profile"
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={6} title={t("title")} description={t("subtitle")} />
      <Tabs value={tab} onValueChange={(v) => router.replace(`/app/settings?tab=${v}`, { scroll: false })} className="space-y-4">
        <TabsList>
          <TabsTrigger value="profile">{t("tabs.profile")}</TabsTrigger>
          <TabsTrigger value="security">{t("tabs.security")}</TabsTrigger>
          <TabsTrigger value="privacy">{t("tabs.privacy")}</TabsTrigger>
        </TabsList>
        <TabsContent value="profile"><ProfileSection /></TabsContent>
        <TabsContent value="security"><SecuritySection /></TabsContent>
        <TabsContent value="privacy"><PrivacySection /></TabsContent>
      </Tabs>
    </div>
  )
}

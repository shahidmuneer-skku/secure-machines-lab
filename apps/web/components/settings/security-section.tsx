"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Fingerprint, KeyRound, Laptop, Loader2, LogOut, ShieldCheck, Smartphone, Trash2 } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { QRCodeSVG } from "qrcode.react"
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react"
import { toast } from "sonner"

import { PasswordInput } from "@/components/auth/password-input"
import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { useMe } from "@/hooks/use-me"
import { usePasskeysSupported } from "@/hooks/use-passkeys-supported"
import { qk } from "@/lib/api/keys"
import { allauth, AuthError, pendingFlow, type AuthResponse } from "@/lib/auth/allauth"
import { registerPasskey } from "@/lib/auth/passkey"
import { formatDateTime } from "@/lib/format"

/* ---------- re-authentication (allauth asks for it before sensitive changes) ---------- */

type Reauth = <T extends AuthResponse>(action: () => Promise<T>) => Promise<T | null>
const ReauthContext = createContext<Reauth>(async (a) => a())

export function ReauthProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("settings.reauth")
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<"password" | "mfa">("password")
  const [value, setValue] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pending = useRef<{ resolve: (ok: boolean) => void } | null>(null)

  const ask = (flow: "password" | "mfa") => new Promise<boolean>((resolve) => {
    setMode(flow)
    setValue("")
    setError(null)
    pending.current = { resolve }
    setOpen(true)
  })

  const reauth: Reauth = useCallback(async (action) => {
    let res = await action()
    const flow = pendingFlow(res)?.id ?? res.data?.flows?.map((f) => f.id).find((id) => id.includes("reauthenticate"))
    if (res.status === 401 && flow) {
      const ok = await ask(flow === "mfa_reauthenticate" ? "mfa" : "password")
      if (!ok) return null
      res = await action()
    }
    return res
  }, [])

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = mode === "password" ? await allauth.reauthenticate(value) : await allauth.mfaReauthenticate(value)
      if (res.status === 200) {
        setOpen(false)
        pending.current?.resolve(true)
      } else setError(t("failed"))
    } catch (e) {
      setError(e instanceof AuthError ? e.message : t("failed"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ReauthContext.Provider value={reauth}>
      {children}
      <Dialog open={open} onOpenChange={(o) => { if (!o) { setOpen(false); pending.current?.resolve(false) } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("title")}</DialogTitle>
            <DialogDescription>{mode === "password" ? t("passwordHint") : t("codeHint")}</DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); submit() }} className="space-y-3">
            {mode === "password" ? (
              <PasswordInput autoFocus autoComplete="current-password" value={value} onChange={(e) => setValue(e.target.value)}
                aria-label={t("password")} />
            ) : (
              <Input autoFocus inputMode="numeric" autoComplete="one-time-code" value={value} onChange={(e) => setValue(e.target.value)}
                aria-label={t("code")} className="font-mono" />
            )}
            {error && <p className="text-sm text-fake" role="alert">{error}</p>}
            <DialogFooter><Button type="submit" disabled={busy || !value}>{busy && <Loader2 className="size-4 animate-spin" />} {t("confirm")}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </ReauthContext.Provider>
  )
}

export const useReauth = () => useContext(ReauthContext)

/* ---------- password ---------- */

function PasswordCard() {
  const t = useTranslations("settings.password")
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [error, setError] = useState<string | null>(null)
  const change = useMutation({
    mutationFn: () => allauth.changePassword(current, next),
    onSuccess: () => { toast.success(t("changed")); setCurrent(""); setNext(""); setError(null) },
    onError: (e) => setError(e instanceof AuthError ? e.fieldError("new_password") ?? e.fieldError("current_password") ?? e.message : t("failed")),
  })
  return (
    <HudCard>
      <CardHeader><Eyebrow index={1}>{t("eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("title")}</CardTitle>
        <CardDescription>{t("hint")}</CardDescription></CardHeader>
      <CardContent>
        <form className="grid max-w-md gap-3" onSubmit={(e) => { e.preventDefault(); change.mutate() }}>
          <div className="space-y-1.5"><Label htmlFor="cur">{t("current")}</Label>
            <PasswordInput id="cur" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="new">{t("new")}</Label>
            <PasswordInput id="new" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></div>
          {error && <p className="text-sm text-fake" role="alert">{error}</p>}
          <Button type="submit" className="w-fit" disabled={change.isPending || next.length < 12 || !current}>
            {change.isPending && <Loader2 className="size-4 animate-spin" />} {t("submit")}</Button>
        </form>
      </CardContent>
    </HudCard>
  )
}

/* ---------- two-factor ---------- */

function TwoFactorCard() {
  const t = useTranslations("settings.mfa")
  const locale = useLocale()
  const qc = useQueryClient()
  const reauth = useReauth()
  const passkeys = usePasskeysSupported()
  const { data: auths, isLoading } = useQuery({ queryKey: qk.authenticators, queryFn: async () => (await allauth.authenticators()).data ?? [] })
  const [setup, setSetup] = useState<{ secret: string; url: string } | null>(null)
  const [code, setCode] = useState("")
  const [codes, setCodes] = useState<string[] | null>(null)
  const refresh = () => { qc.invalidateQueries({ queryKey: qk.authenticators }); qc.invalidateQueries({ queryKey: qk.me }) }
  const totp = auths?.find((a) => a.type === "totp")
  const recovery = auths?.find((a) => a.type === "recovery_codes")
  const webauthn = auths?.filter((a) => a.type === "webauthn") ?? []

  const startTotp = async () => {
    // allauth answers 404 "not configured yet" together with a fresh secret to enrol.
    let meta: { secret?: string; totp_url?: string } | undefined
    try {
      meta = (await reauth(() => allauth.totp()))?.meta as typeof meta
    } catch (e) {
      if (e instanceof AuthError && e.response.status === 404) meta = e.response.meta as typeof meta
      else return toast.error(e instanceof AuthError ? e.message : t("failed"))
    }
    if (meta?.secret && meta.totp_url) setSetup({ secret: meta.secret, url: meta.totp_url })
  }
  const activateTotp = async () => {
    try {
      const res = await reauth(() => allauth.activateTotp(code))
      if (res?.status === 200) {
        toast.success(t("totpEnabled"))
        setSetup(null)
        setCode("")
        refresh()
        const rc = await allauth.recoveryCodes()
        if (rc.data?.unused_codes) setCodes(rc.data.unused_codes)
      }
    } catch (e) {
      toast.error(e instanceof AuthError ? e.message : t("invalidCode"))
    }
  }
  const disableTotp = async () => {
    const res = await reauth(() => allauth.deactivateTotp())
    if (res) { toast.success(t("totpDisabled")); refresh() }
  }
  const showCodes = async (regenerate: boolean) => {
    const res = regenerate ? await reauth(() => allauth.regenerateRecoveryCodes()) : await reauth(() => allauth.recoveryCodes())
    if (!res) return
    const again = regenerate ? await allauth.recoveryCodes() : res
    const list = (again.data as { unused_codes?: string[] } | undefined)?.unused_codes
    if (list) setCodes(list)
    refresh()
  }
  const addPasskey = async () => {
    const name = window.prompt(t("passkeyName"), t("passkeyDefaultName"))
    if (!name) return
    try {
      const res = await reauth(() => allauth.passkeyCreateOptions(true))
      if (!res) return
      await registerPasskey(name)
      toast.success(t("passkeyAdded"))
      refresh()
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "NotAllowedError")) toast.error(e instanceof Error ? e.message : t("failed"))
    }
  }
  const removePasskey = async (id: number) => {
    const res = await reauth(() => allauth.deletePasskeys([id]))
    if (res) { toast.success(t("passkeyRemoved")); refresh() }
  }

  return (
    <HudCard>
      <CardHeader><Eyebrow index={2}>{t("eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("title")}</CardTitle>
        <CardDescription>{t("hint")}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? <Skeleton className="h-32" /> : (
          <>
            <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
              <Smartphone className="size-5 text-primary" />
              <div className="flex-1"><p className="font-medium">{t("totp")}</p><p className="text-xs text-muted-foreground">{t("totpHint")}</p></div>
              {totp ? (<><Badge className="gap-1"><ShieldCheck className="size-3" />{t("enabled")}</Badge>
                <Button size="sm" variant="ghost" onClick={disableTotp}>{t("disable")}</Button></>)
                : <Button size="sm" onClick={startTotp}>{t("enable")}</Button>}
            </div>
            {setup && (
              <div className="grid gap-4 rounded-lg border border-primary/40 p-4 md:grid-cols-[auto_1fr]">
                <div className="rounded-lg bg-white p-3"><QRCodeSVG value={setup.url} size={168} /></div>
                <div className="space-y-3">
                  <p className="text-sm">{t("scan")}</p>
                  <p className="text-xs text-muted-foreground">{t("manual")} <code className="break-all font-mono">{setup.secret}</code></p>
                  <InputOTP maxLength={6} value={code} onChange={setCode} aria-label={t("code")}>
                    <InputOTPGroup>{Array.from({ length: 6 }, (_, i) => <InputOTPSlot key={i} index={i} />)}</InputOTPGroup>
                  </InputOTP>
                  <div className="flex gap-2"><Button size="sm" onClick={activateTotp} disabled={code.length < 6}>{t("activate")}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setSetup(null)}>{t("cancel")}</Button></div>
                </div>
              </div>
            )}
            {recovery && (
              <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
                <KeyRound className="size-5 text-primary" />
                <div className="flex-1"><p className="font-medium">{t("recovery")}</p>
                  <p className="text-xs text-muted-foreground">{t("recoveryLeft", { count: recovery.unused_code_count ?? 0 })}</p></div>
                <Button size="sm" variant="outline" onClick={() => showCodes(false)}>{t("view")}</Button>
                <Button size="sm" variant="ghost" onClick={() => showCodes(true)}>{t("regenerate")}</Button>
              </div>
            )}
            <div className="space-y-2 rounded-lg border p-3">
              <div className="flex flex-wrap items-center gap-3">
                <Fingerprint className="size-5 text-primary" />
                <div className="flex-1"><p className="font-medium">{t("passkeys")}</p><p className="text-xs text-muted-foreground">{t("passkeysHint")}</p></div>
                {passkeys && <Button size="sm" variant="outline" onClick={addPasskey}>{t("addPasskey")}</Button>}
              </div>
              {webauthn.map((w) => (
                <div key={w.id} className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2 text-sm">
                  <span>{w.name}<span className="block text-xs text-muted-foreground">{t("added", { date: formatDateTime(new Date(w.created_at * 1000).toISOString(), locale) })}</span></span>
                  <Button size="icon" variant="ghost" aria-label={t("removePasskey")} onClick={() => w.id && removePasskey(w.id)}><Trash2 className="size-4" /></Button>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
      <Dialog open={!!codes} onOpenChange={(o) => !o && setCodes(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t("recoveryTitle")}</DialogTitle><DialogDescription>{t("recoveryBody")}</DialogDescription></DialogHeader>
          <ul className="grid grid-cols-2 gap-2 font-mono text-sm">{codes?.map((c) => <li key={c} className="rounded border bg-muted px-2 py-1 text-center">{c}</li>)}</ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => navigator.clipboard.writeText((codes ?? []).join("\n"))}>{t("copyCodes")}</Button>
            <Button onClick={() => setCodes(null)}>{t("savedCodes")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </HudCard>
  )
}

/* ---------- sessions ---------- */

function SessionsCard() {
  const t = useTranslations("settings.sessions")
  const locale = useLocale()
  const qc = useQueryClient()
  const { data: sessions, isLoading } = useQuery({ queryKey: qk.sessions, queryFn: async () => (await allauth.sessions()).data ?? [] })
  const end = useMutation({
    mutationFn: (ids: number[]) => allauth.endSessions(ids),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.sessions }); toast.success(t("ended")) },
  })
  const others = sessions?.filter((s) => !s.is_current) ?? []
  return (
    <HudCard>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div><Eyebrow index={3}>{t("eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("title")}</CardTitle>
          <CardDescription>{t("hint")}</CardDescription></div>
        {others.length > 0 && <Button size="sm" variant="outline" onClick={() => end.mutate(others.map((s) => s.id))}>
          <LogOut className="size-4" /> {t("endOthers")}</Button>}
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading ? <Skeleton className="h-24" /> : sessions?.map((s) => (
          <div key={s.id} className="flex items-center gap-3 rounded-lg border p-3 text-sm">
            <Laptop className="size-5 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate">{s.user_agent || t("unknownDevice")}</p>
              <p className="text-xs text-muted-foreground">{s.ip} · {t("since", { date: formatDateTime(new Date(s.created_at * 1000).toISOString(), locale) })}
                {s.last_seen_at ? ` · ${t("lastSeen", { date: formatDateTime(new Date(s.last_seen_at * 1000).toISOString(), locale) })}` : ""}</p>
            </div>
            {s.is_current ? <Badge>{t("current")}</Badge> : (
              <Button size="sm" variant="ghost" onClick={() => end.mutate([s.id])}>{t("end")}</Button>
            )}
          </div>
        ))}
      </CardContent>
    </HudCard>
  )
}

export function SecuritySection() {
  const { data: me } = useMe()
  const t = useTranslations("settings")
  return (
    <ReauthProvider>
      <div className="space-y-5">
        {me?.requires_mfa && !me.has_mfa && (
          <div className="rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm">{t("mfaRequiredForRole")}</div>
        )}
        <PasswordCard />
        <TwoFactorCard />
        <SessionsCard />
      </div>
    </ReauthProvider>
  )
}

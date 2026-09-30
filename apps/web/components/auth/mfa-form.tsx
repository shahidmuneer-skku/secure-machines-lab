"use client"

import { Fingerprint, KeyRound, Loader2 } from "lucide-react"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import { Label } from "@/components/ui/label"
import { allauth, AuthError, pendingFlow } from "@/lib/auth/allauth"
import { usePasskeysSupported } from "@/hooks/use-passkeys-supported"
import { passkeySecondFactor } from "@/lib/auth/passkey"
import { isServerPage } from "@/lib/safe-next"

import { AuthCard } from "./auth-card"
import { FormError } from "./form-error"

export function MfaForm({ next }: { next: string }) {
  const t = useTranslations("auth")
  const router = useRouter()
  const passkeys = usePasskeysSupported()
  const [types, setTypes] = useState<string[]>([])
  const [code, setCode] = useState("")
  const [recovery, setRecovery] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Continue to `next` once signed in; Django-rendered pages (the data admin) need a full load.
  const continueTo = useCallback(() => {
    if (isServerPage(next)) {
      window.location.assign(next)
      return
    }
    router.replace(next)
    router.refresh()
  }, [next, router])

  useEffect(() => {
    allauth.session().then((res) => {
      if (res.meta?.is_authenticated) return continueTo()
      const flow = pendingFlow(res)
      if (flow?.id !== "mfa_authenticate") return router.replace(`/login?next=${encodeURIComponent(next)}`)
      setTypes(flow.types ?? [])
    })
  }, [continueTo, next, router])

  const done = continueTo

  const submit = async (value: string) => {
    setBusy(true)
    setError(null)
    try {
      const res = await allauth.mfaAuthenticate(value.trim())
      if (res.meta?.is_authenticated) return done()
      setError(t("mfaFailed"))
    } catch (e) {
      setError(e instanceof AuthError ? e.message : t("mfaFailed"))
    } finally {
      setBusy(false)
    }
  }

  const passkey = async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await passkeySecondFactor()
      if (res.meta?.is_authenticated) return done()
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "NotAllowedError")) {
        setError(e instanceof AuthError ? e.message : t("passkeyFailed"))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard eyebrow={t("mfaEyebrow")} title={t("mfaTitle")} description={recovery ? t("mfaRecoveryHint") : t("mfaHint")}>
      <FormError message={error} />
      {!recovery ? (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); submit(code) }}>
          <div className="flex justify-center">
            <InputOTP maxLength={6} value={code} onChange={(v) => { setCode(v); if (v.length === 6) submit(v) }}
              autoFocus aria-label={t("authCode")}>
              <InputOTPGroup>
                {Array.from({ length: 6 }, (_, i) => <InputOTPSlot key={i} index={i} />)}
              </InputOTPGroup>
            </InputOTP>
          </div>
          <Button type="submit" className="w-full" disabled={busy || code.length < 6}>
            {busy && <Loader2 className="size-4 animate-spin" />} {t("verify")}
          </Button>
        </form>
      ) : (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); submit(code) }}>
          <Label htmlFor="recovery">{t("recoveryCode")}</Label>
          <Input id="recovery" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code"
            className="font-mono" autoFocus />
          <Button type="submit" className="w-full" disabled={busy || code.length < 6}>{t("verify")}</Button>
        </form>
      )}
      <div className="flex flex-col gap-2">
        {types.includes("webauthn") && passkeys && (
          <Button variant="outline" onClick={passkey} disabled={busy}>
            <Fingerprint className="size-4" /> {t("usePasskey")}
          </Button>
        )}
        {types.includes("recovery_codes") && (
          <Button variant="ghost" size="sm" onClick={() => { setRecovery((r) => !r); setCode("") }}>
            <KeyRound className="size-4" /> {recovery ? t("useAuthenticator") : t("useRecoveryCode")}
          </Button>
        )}
      </div>
    </AuthCard>
  )
}

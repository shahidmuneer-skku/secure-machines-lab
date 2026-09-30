"use client"

import { Loader2, MailCheck } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { allauth, AuthError } from "@/lib/auth/allauth"

import { AuthCard } from "./auth-card"
import { FormError } from "./form-error"
import { PasswordInput } from "./password-input"

export function ForgotPasswordForm() {
  const t = useTranslations("auth")
  const [email, setEmail] = useState("")
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await allauth.requestPasswordReset(email)
    } catch {
      /* generic response: never reveal whether the account exists */
    }
    setSent(true)
    setBusy(false)
  }
  return (
    <AuthCard eyebrow={t("resetEyebrow")} title={t("forgotTitle")} description={sent ? undefined : t("forgotSubtitle")}
      footer={<Link href="/login" className="text-primary hover:underline">{t("backToLogin")}</Link>}>
      {sent ? (
        <div className="flex flex-col items-center gap-3 text-center">
          <MailCheck className="size-10 text-primary" />
          <p className="text-sm text-muted-foreground">{t("resetSent")}</p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">{t("email")}</Label>
            <Input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" />} {t("sendResetLink")}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}

export function ResetPasswordForm({ encodedKey }: { encodedKey: string }) {
  const t = useTranslations("auth")
  const router = useRouter()
  const key = decodeURIComponent(encodedKey)
  const [valid, setValid] = useState<boolean | null>(null)
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    allauth.checkResetKey(key).then(() => setValid(true)).catch(() => setValid(false))
  }, [key])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password.length < 12) return setError(t("passwordMin"))
    setBusy(true)
    setError(null)
    try {
      const res = await allauth.resetPassword(key, password)
      router.replace(res.meta?.is_authenticated ? "/app" : "/login?reset=1")
    } catch (err) {
      setError(err instanceof AuthError ? err.fieldError("password") ?? err.message : t("resetFailed"))
    } finally {
      setBusy(false)
    }
  }

  if (valid === false) {
    return (
      <AuthCard eyebrow={t("resetEyebrow")} title={t("resetInvalid")}>
        <Button asChild className="w-full"><Link href="/forgot-password">{t("requestNewLink")}</Link></Button>
      </AuthCard>
    )
  }
  return (
    <AuthCard eyebrow={t("resetEyebrow")} title={t("resetTitle")} description={t("resetSubtitle")}>
      <FormError message={error} />
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">{t("newPassword")}</Label>
          <PasswordInput id="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <p className="text-xs text-muted-foreground">{t("passwordHint")}</p>
        </div>
        <Button type="submit" className="w-full" disabled={busy || valid === null}>
          {busy && <Loader2 className="size-4 animate-spin" />} {t("setPassword")}
        </Button>
      </form>
    </AuthCard>
  )
}

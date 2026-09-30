"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { Fingerprint, Loader2 } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ControlledField } from "@/components/forms/controlled-field"
import { Input } from "@/components/ui/input"
import { allauth, AuthError, pendingFlow, type AuthResponse } from "@/lib/auth/allauth"
import { passkeysSupported, signInWithPasskey } from "@/lib/auth/passkey"

import { AuthCard } from "./auth-card"
import { FormError } from "./form-error"
import { PasswordInput } from "./password-input"

export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("auth")
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [unverified, setUnverified] = useState(false)
  const [passkeyBusy, setPasskeyBusy] = useState(false)
  const schema = z.object({
    email: z.string().email(t("invalidEmail")),
    password: z.string().min(1, t("passwordRequired")),
    remember: z.boolean(),
  })
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", remember: false },
  })

  const route = (res: AuthResponse) => {
    if (res.status === 200 && res.meta?.is_authenticated) {
      router.replace(next)
      router.refresh()
      return
    }
    const flow = pendingFlow(res)
    if (flow?.id === "mfa_authenticate") {
      router.push(`/login/mfa?next=${encodeURIComponent(next)}`)
    } else if (flow?.id === "verify_email") {
      setUnverified(true)
    } else {
      setError(t("loginFailed"))
    }
  }

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null)
    setUnverified(false)
    try {
      const res = await allauth.login(values.email, values.password, values.remember)
      route(res)
    } catch (e) {
      setError(e instanceof AuthError ? e.message : t("loginFailed"))
    }
  })

  const passkey = async () => {
    setError(null)
    setPasskeyBusy(true)
    try {
      route(await signInWithPasskey())
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "NotAllowedError")) {
        setError(e instanceof AuthError ? e.message : t("passkeyFailed"))
      }
    } finally {
      setPasskeyBusy(false)
    }
  }

  return (
    <AuthCard eyebrow={t("loginEyebrow")} title={t("loginTitle")} description={t("loginSubtitle")}
      footer={<>{t("noAccount")} <Link className="text-primary hover:underline" href={`/signup?next=${encodeURIComponent(next)}`}>{t("createAccount")}</Link></>}>
      <FormError message={error} />
      {unverified && (
        <div role="status" className="rounded-md border border-warn/40 bg-warn/10 p-3 text-sm">
          {t("verifyFirst")}{" "}
          <button type="button" className="text-primary underline" onClick={() => allauth.resendVerification()}>
            {t("resendEmail")}
          </button>
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <ControlledField control={form.control} name="email" label={t("email")}>
          {(field) => <Input type="email" autoComplete="username webauthn" autoFocus {...field} />}
        </ControlledField>
        <div className="space-y-1">
          <ControlledField control={form.control} name="password" label={t("password")}>
            {(field) => <PasswordInput autoComplete="current-password" {...field} />}
          </ControlledField>
          <div className="text-right">
            <Link href="/forgot-password" className="text-xs text-muted-foreground hover:text-foreground">
              {t("forgotPassword")}
            </Link>
          </div>
        </div>
        <ControlledField control={form.control} name="remember" label={t("rememberMe")} orientation="horizontal">
          {({ value, onChange, ...field }) => (
            <Checkbox {...field} checked={value} onCheckedChange={(v) => onChange(v === true)} />
          )}
        </ControlledField>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />}
          {t("signIn")}
        </Button>
      </form>
      {passkeysSupported() && (
        <>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />{t("or")}<span className="h-px flex-1 bg-border" />
          </div>
          <Button variant="outline" className="w-full" onClick={passkey} disabled={passkeyBusy}>
            {passkeyBusy ? <Loader2 className="size-4 animate-spin" /> : <Fingerprint className="size-4" />}
            {t("signInWithPasskey")}
          </Button>
        </>
      )}
    </AuthCard>
  )
}

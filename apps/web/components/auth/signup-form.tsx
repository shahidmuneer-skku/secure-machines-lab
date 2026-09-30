"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { Turnstile } from "@marsidev/react-turnstile"
import { Loader2, MailCheck } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ControlledField } from "@/components/forms/controlled-field"
import { Input } from "@/components/ui/input"
import { usePublicConfig } from "@/hooks/use-me"
import { allauth, AuthError, pendingFlow } from "@/lib/auth/allauth"

import { AuthCard } from "./auth-card"
import { FormError } from "./form-error"
import { PasswordInput } from "./password-input"

export function SignupForm({ next }: { next: string }) {
  const t = useTranslations("auth")
  const locale = useLocale()
  const { data: config } = usePublicConfig()
  const [error, setError] = useState<string | null>(null)
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [captcha, setCaptcha] = useState("")
  const schema = z.object({
    display_name: z.string().max(120).optional(),
    email: z.string().email(t("invalidEmail")),
    password: z.string().min(12, t("passwordMin")),
    accept_terms: z.literal(true, { message: t("acceptTermsRequired") }),
    marketing_opt_in: z.boolean(),
  })
  const form = useForm<z.input<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { display_name: "", email: "", password: "", accept_terms: false as unknown as true,
      marketing_opt_in: false },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null)
    try {
      const res = await allauth.signup({ ...values, locale, captcha_token: captcha })
      if (res.meta?.is_authenticated) return window.location.assign(next)
      if (pendingFlow(res)?.id === "verify_email") return setSentTo(values.email)
      setError(t("signupFailed"))
    } catch (e) {
      if (e instanceof AuthError) {
        for (const field of ["email", "password", "accept_terms"] as const) {
          const msg = e.fieldError(field === "password" ? "password" : field)
          if (msg) form.setError(field, { message: msg })
        }
        setError(e.fieldError("captcha_token") ?? (e.response.errors?.some((x) => !x.param) ? e.message : null))
      } else {
        setError(t("signupFailed"))
      }
    }
  })

  if (sentTo) {
    return (
      <AuthCard eyebrow={t("signupEyebrow")} title={t("checkInbox")}>
        <div className="flex flex-col items-center gap-3 text-center">
          <MailCheck className="size-10 text-primary" aria-hidden />
          <p className="text-sm text-muted-foreground">{t("verificationSent", { email: sentTo })}</p>
          <Button variant="outline" onClick={() => allauth.resendVerification()}>{t("resendEmail")}</Button>
        </div>
      </AuthCard>
    )
  }

  if (config && !config.signups_enabled) {
    return <AuthCard eyebrow={t("signupEyebrow")} title={t("signupClosed")}><p className="text-sm">{t("signupClosedBody")}</p></AuthCard>
  }

  return (
    <AuthCard eyebrow={t("signupEyebrow")} title={t("signupTitle")} description={t("signupSubtitle")}
      footer={<>{t("haveAccount")} <Link className="text-primary hover:underline" href={`/login?next=${encodeURIComponent(next)}`}>{t("signIn")}</Link></>}>
      <FormError message={error} />
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <ControlledField control={form.control} name="display_name"
          label={<>{t("displayName")} <span className="text-muted-foreground">({t("optional")})</span></>}>
          {(field) => <Input autoComplete="name" {...field} value={field.value ?? ""} />}
        </ControlledField>
        <ControlledField control={form.control} name="email" label={t("email")}>
          {(field) => <Input type="email" autoComplete="email" {...field} />}
        </ControlledField>
        <ControlledField control={form.control} name="password" label={t("password")} description={t("passwordHint")}>
          {(field) => <PasswordInput autoComplete="new-password" {...field} />}
        </ControlledField>
        <ControlledField control={form.control} name="accept_terms" orientation="horizontal"
          label={t.rich("acceptTerms", {
            terms: (c) => <Link href="/terms" target="_blank" className="text-primary underline">{c}</Link>,
            privacy: (c) => <Link href="/privacy" target="_blank" className="text-primary underline">{c}</Link>,
          })}>
          {({ value, onChange, ...field }) => (
            <Checkbox {...field} checked={value === true} onCheckedChange={(v) => onChange(v === true)} />
          )}
        </ControlledField>
        <ControlledField control={form.control} name="marketing_opt_in" orientation="horizontal" label={t("marketingOptIn")}>
          {({ value, onChange, ...field }) => (
            <Checkbox {...field} checked={value} onCheckedChange={(v) => onChange(v === true)} />
          )}
        </ControlledField>
        {config?.captcha_enabled && config.captcha_site_key && (
          <Turnstile siteKey={String(config.captcha_site_key)} onSuccess={setCaptcha} options={{ theme: "dark" }} />
        )}
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />} {t("createAccount")}
        </Button>
        <p className="text-center text-xs text-muted-foreground">{t("signupBonusHint")}</p>
      </form>
    </AuthCard>
  )
}

"use client"

import { CheckCircle2, Loader2, XCircle } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { allauth, AuthError } from "@/lib/auth/allauth"

import { AuthCard } from "./auth-card"

export function VerifyEmail({ encodedKey }: { encodedKey: string }) {
  const t = useTranslations("auth")
  const [state, setState] = useState<"working" | "ok" | "error">("working")
  const [signedIn, setSignedIn] = useState(false)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true
    allauth
      .verifyEmail(decodeURIComponent(encodedKey))
      .then((res) => {
        // 200 = verified and signed in; 401 without a pending verify_email flow = verified, sign in next.
        setSignedIn(!!res.meta?.is_authenticated)
        setState(res.data?.flows?.some((f) => f.id === "verify_email" && f.is_pending) ? "error" : "ok")
      })
      .catch((e) => setState(e instanceof AuthError ? "error" : "error"))
  }, [encodedKey])

  return (
    <AuthCard eyebrow={t("verifyEyebrow")} title={state === "ok" ? t("emailVerified") : state === "error" ? t("verifyFailed") : t("verifying")}>
      <div className="flex flex-col items-center gap-4 text-center">
        {state === "working" && <Loader2 className="size-10 animate-spin text-primary" />}
        {state === "ok" && <CheckCircle2 className="size-10 text-real" />}
        {state === "error" && <XCircle className="size-10 text-fake" />}
        <p className="text-sm text-muted-foreground">
          {state === "ok" ? t("emailVerifiedBody") : state === "error" ? t("verifyFailedBody") : null}
        </p>
        {state !== "working" && (
          <Button asChild>
            <Link href={signedIn ? "/app" : "/login"}>{signedIn ? t("openDashboard") : t("signIn")}</Link>
          </Button>
        )}
      </div>
    </AuthCard>
  )
}

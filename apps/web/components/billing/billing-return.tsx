"use client"

import { useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, Loader2, XCircle } from "lucide-react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { HudCard } from "@/components/sml/hud-card"
import { Button } from "@/components/ui/button"
import { CardContent } from "@/components/ui/card"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"

type State = { kind: "working" } | { kind: "ok"; credits: number } | { kind: "error"; message: string }

/**
 * Landing page after the provider's hosted checkout. Credits are granted only by
 * the server: Toss via its confirm API, Stripe via a verified webhook (we poll).
 */
export function BillingReturn() {
  const t = useTranslations("billing.return")
  const params = useSearchParams()
  const qc = useQueryClient()
  // A canceled/failed checkout is known from the URL alone; only real returns need the server.
  const canceled = params.get("status") === "cancel" || !!params.get("code")
  const [state, setState] = useState<State>(() =>
    canceled ? { kind: "error", message: params.get("message") || t("canceled") } : { kind: "working" })
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current || canceled) return
    ran.current = true
    const provider = params.get("provider")
    const kind = params.get("kind")
    const order = params.get("order") ?? params.get("orderId") ?? ""
    const finish = (credits: number) => {
      qc.invalidateQueries({ queryKey: qk.balance })
      qc.invalidateQueries({ queryKey: ["billing"] })
      setState({ kind: "ok", credits })
    }
    const run = async () => {
      try {
        if (provider === "toss" && kind === "pack") {
          const p = data(await api.POST("/api/v1/billing/toss/confirm", { body: {
            payment_key: params.get("paymentKey") ?? "", order_id: order, amount: Number(params.get("amount")) } }))
          return finish(p.credits + p.bonus_credits)
        }
        if (provider === "toss" && kind === "subscription") {
          const p = data(await api.POST("/api/v1/billing/toss/billing-confirm", { body: {
            auth_key: params.get("authKey") ?? "", customer_key: params.get("customerKey") ?? "", order_id: order } }))
          return finish(p.credits)
        }
        // Stripe: the webhook grants credits; wait for it (up to ~90s).
        for (let i = 0; i < 45; i++) {
          const p = data(await api.GET("/api/v1/billing/payments/{order_id}", { params: { path: { order_id: order } } }))
          if (p.status === "paid") return finish(p.credits + p.bonus_credits)
          if (p.status === "failed" || p.status === "canceled") throw new Error(p.failure_reason || t("failed"))
          await new Promise((r) => setTimeout(r, 2000))
        }
        setState({ kind: "error", message: t("pending") })
      } catch (e) {
        setState({ kind: "error", message: isApiError(e) ? e.detail : (e as Error).message || t("failed") })
      }
    }
    void run()
  }, [canceled, params, qc, t])

  return (
    <div className="mx-auto max-w-lg py-10">
      <HudCard>
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          {state.kind === "working" && <><Loader2 className="size-10 animate-spin text-primary" /><p>{t("working")}</p></>}
          {state.kind === "ok" && (
            <>
              <CheckCircle2 className="size-12 text-real" />
              <h1 className="text-xl font-semibold">{t("success")}</h1>
              <p className="text-sm text-muted-foreground">{t("successBody", { count: state.credits })}</p>
              <div className="flex gap-2"><Button asChild><Link href="/app/detect">{t("startDetecting")}</Link></Button>
                <Button asChild variant="outline"><Link href="/app/billing">{t("backToBilling")}</Link></Button></div>
            </>
          )}
          {state.kind === "error" && (
            <>
              <XCircle className="size-12 text-fake" />
              <h1 className="text-xl font-semibold">{t("notCompleted")}</h1>
              <p className="text-sm text-muted-foreground">{state.message}</p>
              <Button asChild variant="outline"><Link href="/app/billing">{t("backToBilling")}</Link></Button>
            </>
          )}
        </CardContent>
      </HudCard>
    </div>
  )
}

export function MockCheckout() {
  const t = useTranslations("billing.mock")
  const params = useSearchParams()
  const router = useRouter()
  const order = params.get("order") ?? ""
  const [busy, setBusy] = useState(false)
  const complete = async () => {
    setBusy(true)
    try {
      await api.POST("/api/v1/billing/mock/complete" as never, { body: { order_id: order } } as never)
      router.push(`/app/billing/return?provider=mock&kind=pack&order=${encodeURIComponent(order)}&status=success`)
    } catch (e) {
      setBusy(false)
      toast.error(isApiError(e) ? e.detail : String(e))
    }
  }
  return (
    <div className="mx-auto max-w-md py-10">
      <HudCard>
        <CardContent className="space-y-4 py-8 text-center">
          <p className="mono-label text-warn">{t("badge")}</p>
          <h1 className="text-lg font-semibold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("body", { order })}</p>
          <div className="flex justify-center gap-2">
            <Button onClick={complete} disabled={busy}>{busy && <Loader2 className="size-4 animate-spin" />} {t("pay")}</Button>
            <Button asChild variant="outline"><Link href="/app/billing/return?status=cancel">{t("cancel")}</Link></Button>
          </div>
        </CardContent>
      </HudCard>
    </div>
  )
}

"use client"

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { loadTossPayments } from "@tosspayments/tosspayments-sdk"
import { Check, Coins, CreditCard, Download, ExternalLink, Loader2, Receipt, Sparkles } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import { Eyebrow } from "@/components/sml/eyebrow"
import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useBalance } from "@/components/sml/credit-meter"
import { api, data } from "@/lib/api/client"
import { newIdempotencyKey } from "@/lib/api/csrf"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { formatDate, formatDateTime, formatRelative } from "@/lib/format"
import { cn } from "@/lib/utils"

type Provider = "toss" | "stripe" | "mock"
type Currency = "KRW" | "USD"

function useCatalog() {
  const locale = useLocale()
  return useQuery({
    queryKey: [...qk.billingCatalog, locale],
    queryFn: async () => data(await api.GET("/api/v1/billing/catalog", { params: { query: { lang: locale } } as never })),
  })
}

/** Starts checkout: Stripe redirects to hosted Checkout, Toss opens its payment window (no card data touches us). */
function useCheckout() {
  const t = useTranslations("billing")
  return useMutation({
    mutationFn: async (vars: { product: "pack" | "plan"; product_id: string; provider: Provider }) => {
      const res = data(await api.POST("/api/v1/billing/checkout", {
        body: vars, params: { header: { "Idempotency-Key": newIdempotencyKey() } } }))
      if (res.redirect_url) {
        window.location.assign(res.redirect_url)
        return
      }
      const p = res.client_params as {
        clientKey: string; customerKey: string; flow: "payment" | "billing"; orderId: string; orderName: string
        amount: { currency: "KRW"; value: number }; successUrl: string; failUrl: string; customerEmail: string
      }
      const toss = await loadTossPayments(p.clientKey)
      const payment = toss.payment({ customerKey: p.customerKey })
      if (p.flow === "billing") {
        await payment.requestBillingAuth({ method: "CARD", successUrl: p.successUrl, failUrl: p.failUrl,
          customerEmail: p.customerEmail })
      } else {
        await payment.requestPayment({ method: "CARD", amount: p.amount, orderId: p.orderId, orderName: p.orderName,
          successUrl: p.successUrl, failUrl: p.failUrl, customerEmail: p.customerEmail })
      }
    },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("checkoutFailed")),
  })
}

function BalanceCard() {
  const t = useTranslations("billing")
  const locale = useLocale()
  const { data: b, isLoading } = useBalance()
  const sources = Object.entries(b?.by_source ?? {})
  return (
    <HudCard>
      <CardHeader>
        <Eyebrow index={1}>{t("balance.eyebrow")}</Eyebrow>
        <CardTitle className="mt-1 text-base">{t("balance.title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading || !b ? <Skeleton className="h-32" /> : (
          <>
            <div className="flex items-end gap-2">
              <span className="font-mono text-4xl font-semibold tabular-nums">{b.unlimited ? "∞" : b.balance}</span>
              <span className="mb-1 mono-label text-muted-foreground">{t("credits")}</span>
            </div>
            {b.held > 0 && <p className="text-xs text-muted-foreground">{t("balance.held", { count: b.held })}</p>}
            <ul className="space-y-1.5 text-sm">
              {sources.map(([source, amount]) => (
                <li key={source} className="flex justify-between">
                  <span className="text-muted-foreground">{t(`source.${source}`)}</span>
                  <span className="font-mono tabular-nums">{amount}</span>
                </li>
              ))}
            </ul>
            {b.next_expiry_at && (
              <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs">
                {t("balance.nextExpiry", { amount: b.next_expiry_amount, when: formatRelative(b.next_expiry_at, locale) })}
              </p>
            )}
            <p className="text-xs text-muted-foreground">{t("balance.daily", { count: b.daily_free_credits })}</p>
          </>
        )}
      </CardContent>
    </HudCard>
  )
}

function PacksAndPlans() {
  const t = useTranslations("billing")
  const locale = useLocale()
  const { data: catalog, isLoading } = useCatalog()
  const checkout = useCheckout()
  const qc = useQueryClient()
  const { data: sub } = useQuery({ queryKey: qk.subscription,
    queryFn: async () => data(await api.GET("/api/v1/billing/subscription")) })
  const providers = (catalog?.providers ?? []) as { id: Provider; currency: Currency }[]
  const [provider, setProvider] = useState<Provider | null>(null)
  const active = provider ?? providers.find((p) => p.id === (locale === "ko" ? "toss" : "stripe"))?.id ?? providers[0]?.id
  const currency: Currency = providers.find((p) => p.id === active)?.currency ?? (locale === "ko" ? "KRW" : "USD")
  const subAction = useMutation({
    mutationFn: async (action: "cancel" | "resume") => data(await api.POST("/api/v1/billing/subscription/{action}",
      { params: { path: { action } } })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: qk.subscription }); toast.success(t("subscription.updated")) },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("checkoutFailed")),
  })
  const portal = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/billing/portal")),
    onSuccess: (r) => window.location.assign(r.url),
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("checkoutFailed")),
  })

  if (isLoading) return <Skeleton className="h-96" />
  if (!catalog?.billing_enabled || !providers.length) {
    return <HudCard><CardContent className="py-8 text-center text-sm text-muted-foreground">{t("disabled")}</CardContent></HudCard>
  }
  const busy = checkout.isPending
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <span className="mono-label text-muted-foreground">{t("payWith")}</span>
        <ToggleGroup type="single" variant="outline" size="sm" value={active} onValueChange={(v) => v && setProvider(v as Provider)}>
          {providers.map((p) => (
            <ToggleGroupItem key={p.id} value={p.id} aria-label={t(`provider.${p.id}`)}>
              <CreditCard className="size-4" /> {t(`provider.${p.id}`)} · {p.currency}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>

      <section className="space-y-3" aria-labelledby="plans-title">
        <div>
          <Eyebrow index={2}>{t("plans.eyebrow")}</Eyebrow>
          <h2 id="plans-title" className="mt-1 text-lg font-semibold">{t("plans.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("plans.subtitle")}</p>
        </div>
        {sub && (
          <HudCard className="border-primary/40">
            <CardContent className="flex flex-wrap items-center gap-3 py-4 text-sm">
              <Sparkles className="size-4 text-primary" />
              <span className="font-medium">{sub.plan.display_name}</span>
              <StatusChip status={sub.status === "active" ? "active" : sub.status} />
              {sub.current_period_end && (
                <span className="text-muted-foreground">
                  {sub.cancel_at_period_end ? t("subscription.endsOn", { date: formatDate(sub.current_period_end, locale) })
                    : t("subscription.renewsOn", { date: formatDate(sub.current_period_end, locale) })}
                </span>
              )}
              <span className="ml-auto flex gap-2">
                {sub.provider === "stripe" && <Button size="sm" variant="outline" onClick={() => portal.mutate()}>
                  <ExternalLink className="size-4" /> {t("subscription.manage")}</Button>}
                {sub.cancel_at_period_end ? (
                  <Button size="sm" onClick={() => subAction.mutate("resume")}>{t("subscription.resume")}</Button>
                ) : (sub.status === "active" || sub.status === "past_due") && (
                  <Button size="sm" variant="ghost" onClick={() => subAction.mutate("cancel")}>{t("subscription.cancel")}</Button>
                )}
              </span>
            </CardContent>
          </HudCard>
        )}
        <div className="grid gap-4 md:grid-cols-3">
          {catalog.plans.map((plan) => {
            const current = sub?.plan.id === plan.id && (sub.status === "active" || sub.status === "past_due")
            return (
              <HudCard key={plan.id} interactive className={cn("flex flex-col", plan.highlight && "border-primary/50")}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>{plan.display_name}</CardTitle>
                    {plan.highlight && <Badge>{t("popular")}</Badge>}
                  </div>
                  <CardDescription>{plan.display_description}</CardDescription>
                </CardHeader>
                <CardContent className="flex-1 space-y-3">
                  <div>
                    <span className="font-mono text-3xl font-semibold">{plan.prices[currency].display}</span>
                    <span className="text-sm text-muted-foreground"> / {t("month")}</span>
                  </div>
                  <ul className="space-y-1.5 text-sm">
                    {plan.display_features.map((f) => (
                      <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-primary" />{f}</li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter>
                  <Button className="w-full" variant={plan.highlight ? "default" : "outline"} disabled={busy || current || !!sub && ["active", "past_due"].includes(sub.status)}
                    onClick={() => checkout.mutate({ product: "plan", product_id: plan.id, provider: active! })}>
                    {busy && <Loader2 className="size-4 animate-spin" />}
                    {current ? t("plans.current") : t("plans.subscribe")}
                  </Button>
                </CardFooter>
              </HudCard>
            )
          })}
        </div>
      </section>

      <section className="space-y-3" aria-labelledby="packs-title">
        <div>
          <Eyebrow index={3}>{t("packs.eyebrow")}</Eyebrow>
          <h2 id="packs-title" className="mt-1 text-lg font-semibold">{t("packs.title")}</h2>
          <p className="text-sm text-muted-foreground">{t("packs.subtitle")}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {catalog.packs.map((pack) => (
            <HudCard key={pack.id} interactive className={cn(pack.highlight && "border-primary/50")}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{pack.display_name}</CardTitle>
                  {pack.highlight && <Badge>{t("bestValue")}</Badge>}
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center gap-2"><Coins className="size-5 text-primary" />
                  <span className="font-mono text-2xl font-semibold">{pack.credits.toLocaleString(locale)}</span>
                  <span className="mono-label text-muted-foreground">{t("credits")}</span></div>
                {pack.bonus_credits > 0 && <p className="text-xs text-primary">{t("packs.bonus", { count: pack.bonus_credits })}</p>}
                <p className="font-mono text-xl">{pack.prices[currency].display}</p>
                <p className="text-xs text-muted-foreground">{t("packs.expiry", { days: pack.credit_expiry_days ?? 365 })}</p>
              </CardContent>
              <CardFooter>
                <Button className="w-full" variant="outline" disabled={busy}
                  onClick={() => checkout.mutate({ product: "pack", product_id: pack.id, provider: active! })}>
                  {busy && <Loader2 className="size-4 animate-spin" />} {t("packs.buy")}
                </Button>
              </CardFooter>
            </HudCard>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{t.rich("legal", {
          refund: (c) => <a className="underline" href="/refund-policy" target="_blank">{c}</a>,
          terms: (c) => <a className="underline" href="/terms" target="_blank">{c}</a> })}</p>
      </section>
    </div>
  )
}

function Payments() {
  const t = useTranslations("billing")
  const locale = useLocale()
  const { data: payments, isLoading } = useQuery({ queryKey: qk.payments,
    queryFn: async () => data(await api.GET("/api/v1/billing/payments")) })
  if (isLoading) return <Skeleton className="h-40" />
  if (!payments?.results.length) return <p className="py-8 text-center text-sm text-muted-foreground">{t("payments.empty")}</p>
  return (
    <Table>
      <TableHeader><TableRow>
        <TableHead>{t("payments.date")}</TableHead><TableHead>{t("payments.item")}</TableHead>
        <TableHead>{t("payments.status")}</TableHead><TableHead className="text-right">{t("payments.amount")}</TableHead>
        <TableHead className="text-right">{t("payments.receipt")}</TableHead>
      </TableRow></TableHeader>
      <TableBody>
        {payments.results.map((p) => (
          <TableRow key={p.id}>
            <TableCell className="whitespace-nowrap">{formatDateTime(p.paid_at ?? p.created_at, locale)}</TableCell>
            <TableCell>{p.order_name}<span className="block text-xs text-muted-foreground">{t(`provider.${p.provider}`)} · {p.order_id}</span></TableCell>
            <TableCell><StatusChip status={p.status === "paid" ? "succeeded" : p.status === "failed" ? "failed" : p.status} /></TableCell>
            <TableCell className="text-right font-mono tabular-nums">{p.display_amount}</TableCell>
            <TableCell className="text-right">
              {p.receipt_url ? <Button asChild size="sm" variant="ghost"><a href={p.receipt_url} target="_blank" rel="noopener noreferrer">
                <Receipt className="size-4" /></a></Button> : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Ledger() {
  const t = useTranslations("billing")
  const locale = useLocale()
  const q = useInfiniteQuery({
    queryKey: qk.ledger({}), initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => data(await api.GET("/api/v1/credits/ledger", {
      params: { query: { cursor: pageParam, limit: 50 } as never } })),
    getNextPageParam: (last) => last.next ? new URL(last.next, "http://x").searchParams.get("cursor") ?? undefined : undefined,
  })
  const rows = q.data?.pages.flatMap((p) => p.results) ?? []
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button asChild size="sm" variant="outline"><a href="/api/v1/credits/ledger.csv" download><Download className="size-4" /> {t("ledger.export")}</a></Button>
      </div>
      {q.isLoading ? <Skeleton className="h-40" /> : !rows.length ? (
        <p className="py-8 text-center text-sm text-muted-foreground">{t("ledger.empty")}</p>
      ) : (
        <Table>
          <TableHeader><TableRow>
            <TableHead>{t("ledger.date")}</TableHead><TableHead>{t("ledger.entry")}</TableHead>
            <TableHead className="text-right">{t("ledger.change")}</TableHead><TableHead className="text-right">{t("ledger.balance")}</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {rows.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap text-xs">{formatDateTime(e.created_at, locale)}</TableCell>
                <TableCell>{t(`kind.${e.kind}`)}<span className="block text-xs text-muted-foreground">{e.memo}</span></TableCell>
                <TableCell className={cn("text-right font-mono tabular-nums", e.delta > 0 && "text-real", e.delta < 0 && "text-foreground")}>
                  {e.delta > 0 ? `+${e.delta}` : e.delta === 0 ? "·" : e.delta}</TableCell>
                <TableCell className="text-right font-mono tabular-nums">{e.balance_after}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {q.hasNextPage && <div className="flex justify-center"><Button variant="outline" onClick={() => q.fetchNextPage()}>{t("ledger.more")}</Button></div>}
    </div>
  )
}

export function BillingPage() {
  const t = useTranslations("billing")
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={t("eyebrow")} index={4} title={t("title")} description={t("subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        <div className="space-y-4 lg:sticky lg:top-20 lg:self-start"><BalanceCard /><PriceList /></div>
        <Tabs defaultValue="buy" className="space-y-4">
          <TabsList>
            <TabsTrigger value="buy">{t("tabs.buy")}</TabsTrigger>
            <TabsTrigger value="payments">{t("tabs.payments")}</TabsTrigger>
            <TabsTrigger value="ledger">{t("tabs.ledger")}</TabsTrigger>
          </TabsList>
          <TabsContent value="buy"><PacksAndPlans /></TabsContent>
          <TabsContent value="payments"><HudCard><CardContent className="pt-4"><Payments /></CardContent></HudCard></TabsContent>
          <TabsContent value="ledger"><HudCard><CardContent className="pt-4"><Ledger /></CardContent></HudCard></TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

function PriceList() {
  const t = useTranslations("billing")
  const { data: prices } = useQuery({ queryKey: qk.prices, queryFn: async () => data(await api.GET("/api/v1/credits/prices")) })
  const show = ["image", "video_base", "video_per_extra_minute", "long_video_per_minute", "news_case", "explain"]
  return (
    <HudCard>
      <CardHeader><Eyebrow>{t("prices.eyebrow")}</Eyebrow><CardTitle className="mt-1 text-base">{t("prices.title")}</CardTitle></CardHeader>
      <CardContent>
        <ul className="space-y-1.5 text-sm">
          {prices?.prices.filter((p) => show.includes(p.key)).map((p) => (
            <li key={p.key} className="flex justify-between gap-2">
              <span className="text-muted-foreground">{t(`prices.${p.key}`)}</span>
              <span className="font-mono tabular-nums">{p.credits}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </HudCard>
  )
}

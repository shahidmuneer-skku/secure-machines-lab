import { Check, Coins, Gift, ImageIcon } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"
import { getLocale, getTranslations } from "next-intl/server"

import { Eyebrow } from "@/components/sml/eyebrow"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { serverApi } from "@/lib/api/server"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("pricing")
  return { title: t("title"), description: t("subtitle") }
}

export default async function PricingPage() {
  const t = await getTranslations("pricing")
  const locale = await getLocale()
  const [{ data: catalog }, { data: prices }] = await Promise.all([
    serverApi.GET("/api/v1/billing/catalog", { params: { query: { lang: locale } } as never }),
    serverApi.GET("/api/v1/credits/prices"),
  ])
  const primary = locale === "ko" ? "KRW" : "USD"
  const secondary = primary === "KRW" ? "USD" : "KRW"
  const price = (key: string) => prices?.prices.find((p) => p.key === key)?.credits ?? 0
  const free = prices?.free
  return (
    <div className="space-y-16">
      <section className="space-y-4 text-center">
        <Eyebrow className="justify-center">{t("eyebrow")}</Eyebrow>
        <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{t("title")}</h1>
        <p className="mx-auto max-w-2xl text-muted-foreground">{t("subtitle")}</p>
      </section>

      {free && (
        <section className="grid gap-4 md:grid-cols-3" aria-label={t("free.title")}>
          {[{ icon: ImageIcon, title: t("free.trial", { count: free.guest_trial_images_per_day }), body: t("free.trialBody") },
            { icon: Gift, title: t("free.bonus", { count: free.signup_bonus_credits }), body: t("free.bonusBody", { days: free.signup_bonus_expiry_days }) },
            { icon: Coins, title: t("free.daily", { count: free.daily_free_credits }), body: t("free.dailyBody") }].map((f) => (
            <Card key={f.title} className="border-border/80 bg-card/80">
              <CardHeader><f.icon className="size-6 text-primary" /><CardTitle className="mt-2 text-lg">{f.title}</CardTitle>
                <CardDescription>{f.body}</CardDescription></CardHeader>
            </Card>
          ))}
        </section>
      )}

      <section className="space-y-4">
        <Eyebrow index={1}>{t("costs.eyebrow")}</Eyebrow>
        <h2 className="text-2xl font-semibold">{t("costs.title")}</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[["image", t("costs.image")], ["video", t("costs.video", { base: price("video_base"), extra: price("video_per_extra_minute") })],
            ["long", t("costs.long", { count: price("long_video_per_minute") })], ["news", t("costs.news", { count: price("news_case") })],
            ["explain", t("costs.explain", { count: price("explain") })], ["reports", t("costs.reports")]].map(([k, label]) => (
            <div key={k} className="flex items-center justify-between rounded-lg border bg-card/60 px-4 py-3 text-sm">
              <span>{label}</span>
              {k === "image" && <span className="font-mono">{t("credits", { count: price("image") })}</span>}
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{t("costs.flat")}</p>
      </section>

      <section className="space-y-4">
        <Eyebrow index={2}>{t("plans.eyebrow")}</Eyebrow>
        <h2 className="text-2xl font-semibold">{t("plans.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("plans.subtitle")}</p>
        <div className="grid gap-4 md:grid-cols-3">
          {catalog?.plans.map((plan) => (
            <Card key={plan.id} className={plan.highlight ? "border-primary/60 bg-card/90" : "border-border/80 bg-card/80"}>
              <CardHeader>
                <div className="flex items-center justify-between"><CardTitle>{plan.display_name}</CardTitle>
                  {plan.highlight && <Badge>{t("popular")}</Badge>}</div>
                <CardDescription>{plan.display_description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p><span className="font-mono text-3xl font-semibold">{plan.prices[primary].display}</span>
                  <span className="text-sm text-muted-foreground"> / {t("month")}</span></p>
                <p className="text-xs text-muted-foreground">{plan.prices[secondary].display} / {t("month")}</p>
                <ul className="space-y-1.5 text-sm">{plan.display_features.map((f) => (
                  <li key={f} className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-primary" />{f}</li>))}</ul>
              </CardContent>
              <CardFooter><Button asChild className="w-full" variant={plan.highlight ? "default" : "outline"}>
                <Link href="/signup?next=/app/billing">{t("choose")}</Link></Button></CardFooter>
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <Eyebrow index={3}>{t("packs.eyebrow")}</Eyebrow>
        <h2 className="text-2xl font-semibold">{t("packs.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("packs.subtitle")}</p>
        <div className="grid gap-4 md:grid-cols-3">
          {catalog?.packs.map((pack) => (
            <Card key={pack.id} className="border-border/80 bg-card/80">
              <CardHeader><CardTitle>{pack.display_name}</CardTitle>
                <CardDescription>{t("credits", { count: pack.credits })}</CardDescription></CardHeader>
              <CardContent><p className="font-mono text-2xl">{pack.prices[primary].display}</p>
                <p className="text-xs text-muted-foreground">{pack.prices[secondary].display}</p></CardContent>
              <CardFooter><Button asChild variant="outline" className="w-full"><Link href="/signup?next=/app/billing">{t("buy")}</Link></Button></CardFooter>
            </Card>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-3xl space-y-4">
        <h2 className="text-2xl font-semibold">{t("faq.title")}</h2>
        <Accordion type="single" collapsible>
          {["expire", "models", "refund", "payment", "api", "enterprise"].map((k) => (
            <AccordionItem key={k} value={k}>
              <AccordionTrigger>{t(`faq.${k}.q`)}</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">{t(`faq.${k}.a`)}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </div>
  )
}

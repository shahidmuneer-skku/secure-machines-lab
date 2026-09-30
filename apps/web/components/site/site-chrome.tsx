import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { BrandMark } from "@/components/app-shell/brand"
import { LocaleSwitcher } from "@/components/app-shell/locale-switcher"
import { Button } from "@/components/ui/button"
import { COMPANY } from "@/lib/company"

export async function SiteHeader() {
  const t = await getTranslations("nav")
  return (
    <header className="sticky top-0 z-20 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <BrandMark />
        <nav className="hidden items-center gap-5 text-sm text-muted-foreground md:flex" aria-label="Main">
          <Link href="/#trial" className="hover:text-foreground">{t("home")}</Link>
          <Link href="/pricing" className="hover:text-foreground">{t("pricing")}</Link>
          <Link href="/docs" className="hover:text-foreground">{t("docs")}</Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <LocaleSwitcher compact />
          <Button asChild size="sm"><Link href="/login">{t("signIn")}</Link></Button>
        </div>
      </div>
    </header>
  )
}

export async function SiteFooter() {
  const t = await getTranslations("site")
  return (
    <footer className="border-t border-border/70 py-10 text-xs text-muted-foreground">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 md:grid-cols-[1fr_auto]">
        <div className="space-y-1">
          <p className="font-medium text-foreground">{COMPANY.name}</p>
          <p>{t("representative")}: {COMPANY.representative} · {t("bizNo")}: {COMPANY.businessRegistrationNo}</p>
          <p>{t("mailOrderNo")}: {COMPANY.mailOrderRegistrationNo}</p>
          <p>{COMPANY.address}</p>
          <p>{COMPANY.supportEmail} · {COMPANY.phone}</p>
        </div>
        <nav className="flex flex-wrap items-start gap-4" aria-label={t("legal")}>
          <Link href="/terms" className="hover:text-foreground">{t("terms")}</Link>
          <Link href="/privacy" className="font-medium text-foreground hover:underline">{t("privacy")}</Link>
          <Link href="/refund-policy" className="hover:text-foreground">{t("refunds")}</Link>
          <Link href="/docs" className="hover:text-foreground">{t("api")}</Link>
        </nav>
      </div>
    </footer>
  )
}

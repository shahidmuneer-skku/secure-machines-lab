import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { BrandMark } from "@/components/app-shell/brand"
import { LocaleSwitcher } from "@/components/app-shell/locale-switcher"

/** Auth pages always use the dark brand look of the homepage. */
export default async function AuthLayout({ children }: LayoutProps<"/">) {
  const t = await getTranslations("auth")
  return (
    <div className="dark body-gradient relative min-h-screen bg-background text-foreground">
      <div className="noise-overlay" aria-hidden />
      <header className="relative z-10 flex items-center justify-between px-6 py-5">
        <BrandMark />
        <LocaleSwitcher />
      </header>
      <main className="relative z-10 mx-auto flex w-full max-w-md flex-col px-4 pb-16 pt-6 md:pt-12">{children}</main>
      <footer className="relative z-10 flex justify-center gap-4 pb-8 text-xs text-muted-foreground">
        <Link href="/terms" className="hover:text-foreground">{t("terms")}</Link>
        <Link href="/privacy" className="hover:text-foreground">{t("privacy")}</Link>
        <Link href="/refund-policy" className="hover:text-foreground">{t("refunds")}</Link>
      </footer>
    </div>
  )
}

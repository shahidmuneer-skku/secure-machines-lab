import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { LanguageMenu, ThemeButton } from "@/components/app-shell/header-controls"
import { Logo } from "@/components/brand/logo"

/** Sign-in and sign-up pages (Modernize's auth layout): a centred card on a soft brand background. */
export default async function AuthLayout({ children }: LayoutProps<"/">) {
  const t = await getTranslations("auth")
  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(800px_420px_at_15%_0%,color-mix(in_oklab,var(--brand)_16%,transparent),transparent_70%),radial-gradient(700px_420px_at_100%_100%,color-mix(in_oklab,var(--brand-2)_14%,transparent),transparent_70%)]" />
      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-5 md:px-6">
        <Logo href="/" />
        <div className="flex items-center gap-1"><LanguageMenu /><ThemeButton /></div>
      </header>
      <main className="relative z-10 mx-auto flex w-full max-w-md flex-col px-4 pb-12 pt-4 md:pt-10">{children}</main>
      <footer className="relative z-10 flex justify-center gap-5 pb-8 text-sm text-muted-foreground">
        <Link href="/terms" className="hover:text-primary">{t("terms")}</Link>
        <Link href="/privacy" className="hover:text-primary">{t("privacy")}</Link>
        <Link href="/refund-policy" className="hover:text-primary">{t("refunds")}</Link>
      </footer>
    </div>
  )
}

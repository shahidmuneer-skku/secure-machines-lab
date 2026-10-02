import { SiteFooter } from "@/components/landing/site-footer"
import { SiteNav } from "@/components/landing/site-nav"

/** Public content pages (pricing, legal, docs): the landing page's navigation and footer. */
export default function SiteLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteNav />
      <main className="mx-auto w-full max-w-6xl px-4 py-10 md:py-14">{children}</main>
      <SiteFooter />
    </div>
  )
}

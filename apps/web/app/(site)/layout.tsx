import { SiteFooter, SiteHeader } from "@/components/site/site-chrome"

/** Public content pages (pricing, legal, docs): dark brand look, readable layout. */
export default function SiteLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="dark app-gradient min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-10 md:py-14">{children}</main>
      <SiteFooter />
    </div>
  )
}

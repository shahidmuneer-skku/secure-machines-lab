import type { Metadata, Viewport } from "next"
import { JetBrains_Mono, Noto_Sans_KR, Plus_Jakarta_Sans } from "next/font/google"
import { headers } from "next/headers"
import { NextIntlClientProvider } from "next-intl"
import { getLocale } from "next-intl/server"

import { Providers } from "@/components/providers"

import "./globals.css"

// Plus Jakarta Sans: the Modernize design's typeface (owner, 2026-10-02).
const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700", "800"],
  variable: "--font-jakarta" })
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" })
// Korean glyph fallback; loaded on demand (not preloaded) to keep LCP low for other locales.
const notoKr = Noto_Sans_KR({ weight: ["400", "500", "700"], variable: "--font-noto-kr", preload: false })

export const metadata: Metadata = {
  title: { default: "Secure Machines Lab — Deepfake & AI-generated media detection", template: "%s · SML" },
  description:
    "Detect deepfakes and AI-generated images and videos, verify news media and get explainable forensic reports.",
  applicationName: "Secure Machines Lab",
}

export const viewport: Viewport = {
  // The site opens dark whatever the system setting (owner, 2026-10-02).
  themeColor: "#1e2735",
  colorScheme: "dark light",
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale()
  const nonce = (await headers()).get("x-nonce") ?? undefined
  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${jakarta.variable} ${jetbrains.variable} ${notoKr.variable}`}
    >
      <body className="min-h-screen font-sans antialiased">
        <NextIntlClientProvider>
          <Providers nonce={nonce}>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}

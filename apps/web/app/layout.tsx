import type { Metadata, Viewport } from "next"
import { Instrument_Serif, JetBrains_Mono, Noto_Sans_KR, Space_Grotesk } from "next/font/google"
import { headers } from "next/headers"
import { NextIntlClientProvider } from "next-intl"
import { getLocale } from "next-intl/server"

import { Providers } from "@/components/providers"

import "./globals.css"

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: "--font-space-grotesk" })
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" })
const instrument = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"],
  variable: "--font-instrument" })
// Korean glyph fallback; loaded on demand (not preloaded) to keep LCP low for other locales.
const notoKr = Noto_Sans_KR({ weight: ["400", "500", "700"], variable: "--font-noto-kr", preload: false })

export const metadata: Metadata = {
  title: { default: "Secure Machines Lab — Deepfake & AI-generated media detection", template: "%s · SML" },
  description:
    "Detect deepfakes and AI-generated images and videos, verify news media and get explainable forensic reports.",
  applicationName: "Secure Machines Lab",
}

export const viewport: Viewport = { themeColor: "#07080b", colorScheme: "dark light" }

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const locale = await getLocale()
  const nonce = (await headers()).get("x-nonce") ?? undefined
  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${spaceGrotesk.variable} ${jetbrains.variable} ${instrument.variable} ${notoKr.variable}`}
    >
      <body className="min-h-screen font-sans antialiased">
        <NextIntlClientProvider>
          <Providers nonce={nonce}>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}

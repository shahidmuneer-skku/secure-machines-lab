"use client"

import Box from "@mui/material/Box"
import { useLocale } from "next-intl"

import { isLanguage, type Language } from "@/lib/marketing/i18n"

import { ScanHero } from "./scan/scan-hero"
import { AboutAndContact, Benefits, CredibilityBand, FinalCta, ProductSuite, Research, Workflow } from "./sections"
import { SiteFooter } from "./site-footer"
import { SiteNav } from "./site-nav"
import { TrialSection } from "./trial"

/**
 * Landing page (3D scan redesign, 2026-10-02). The previous design is kept in ./legacy and served at
 * /landing-legacy. Order: scan hero → free upload (the hero hands off to it) → credibility → products →
 * workflow → benefits → research → final CTA → about & contact.
 */
export function LandingPage() {
  const locale = useLocale()
  const language: Language = isLanguage(locale) ? locale : "en"
  return (
    <Box className="sml-landing" sx={{ bgcolor: "background.default", color: "text.primary", minHeight: "100vh" }}>
      <SiteNav />
      <main>
        <ScanHero />
        <TrialSection language={language} />
        <CredibilityBand language={language} />
        <ProductSuite />
        <Workflow />
        <Benefits />
        <Research language={language} />
        <FinalCta />
        <AboutAndContact language={language} />
      </main>
      <SiteFooter />
    </Box>
  )
}

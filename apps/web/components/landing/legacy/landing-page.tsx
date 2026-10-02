"use client"

import Box from "@mui/material/Box"
import { useLocale } from "next-intl"

import { isLanguage, type Language } from "@/lib/marketing/i18n"

import { Hero } from "./hero"
import { AboutAndContact, CallToAction, Features, HowItWorks, Products, Research, TrustStrip } from "./sections"
import { SiteFooter } from "./site-footer"
import { SiteNav } from "./site-nav"
import { TrialSection } from "./trial"

/**
 * BACKUP of the landing page as it was before the 3D scan redesign (2026-10-02), served at
 * /landing-legacy for comparison. Frozen: imports only from this folder and shared app components.
 *
 * Landing page (owner, 2026-10-02): product-focused, Modernize design, dark by default. Keeps the
 * lab's content (research areas, publications, collaborators, contact) and the guest trial.
 */
export function LegacyLandingPage() {
  const locale = useLocale()
  const language: Language = isLanguage(locale) ? locale : "en"
  return (
    <Box sx={{ bgcolor: "background.default", color: "text.primary", minHeight: "100vh" }}>
      <SiteNav />
      <main>
        <Hero />
        <TrustStrip language={language} />
        <TrialSection language={language} />
        <Products />
        <HowItWorks />
        <Features />
        <Research language={language} />
        <CallToAction />
        <AboutAndContact language={language} />
      </main>
      <SiteFooter />
    </Box>
  )
}

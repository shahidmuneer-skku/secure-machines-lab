import type { Metadata } from "next"

import { LegacyLandingPage } from "@/components/landing/legacy/landing-page"

/** Backup of the previous landing page design (before the 3D scan redesign), kept for comparison. */
export const metadata: Metadata = {
  title: "Landing page (previous design)",
  robots: { index: false, follow: false },
}

export default function LegacyHome() {
  return <LegacyLandingPage />
}

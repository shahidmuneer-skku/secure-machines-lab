import { LandingPage } from "@/components/landing/landing-page"

/**
 * Homepage: the 3D scan design (ADR 0014). The previous design is kept at /landing-legacy; to switch
 * back, render `LegacyLandingPage` from "@/components/landing/legacy/landing-page" here.
 */
export default function Home() {
  return <LandingPage />
}

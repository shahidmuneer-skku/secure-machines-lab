"use client"

/**
 * Marketing homepage — ported from dash-lab-website-production/app/page.tsx.
 * Visual structure is unchanged. Differences: language uses the shared
 * NEXT_LOCALE cookie, the nav links to Pricing/Docs/Sign in, and a guest
 * trial section sits right under the hero.
 */
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useLocale } from "next-intl"
import { useCallback, useEffect, useState } from "react"

import { setLocaleCookie } from "@/components/app-shell/locale-switcher"
import { api, data } from "@/lib/api/client"
import { SUPPORTED_LANGUAGES, dashTranslations, isLanguage, type DashTranslations, type Language } from "@/lib/marketing/i18n"

import AboutSection from "./about-section"
import ContactSection from "./contact-section"
import CustomersSection from "./customers-section"
import HeroSection from "./hero-section"
import LiquidCanvas from "./liquid-canvas"
import SpiderCursor from "./spider-cursor"
import ToolsSection from "./tools-section"
import { TrialSection } from "./trial-section"

function smoothScrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
}

function useSignedIn(): boolean {
  const { data: me } = useQuery({
    queryKey: ["me", "optional"], retry: false, staleTime: 60_000,
    queryFn: async () => { try { return data(await api.GET("/api/v1/me")) } catch { return null } },
  })
  return !!me
}

function Navbar({ t, language, onLanguageChange }: {
  t: DashTranslations["nav"]; language: Language; onLanguageChange: (language: Language) => void
}) {
  const [isOnLightSurface, setIsOnLightSurface] = useState(false)
  const signedIn = useSignedIn()
  const labels = NAV_EXTRA[language]

  const handleClick = useCallback((e: React.MouseEvent<HTMLAnchorElement>) => {
    const href = e.currentTarget.getAttribute("href")
    if (href && href.startsWith("#")) {
      e.preventDefault()
      smoothScrollTo(href.slice(1))
    }
  }, [])

  useEffect(() => {
    const customersSection = document.querySelector<HTMLElement>(".customers-section")
    if (!customersSection) return
    let frame: number | null = null
    const updateTone = () => {
      frame = null
      const { top, bottom } = customersSection.getBoundingClientRect()
      setIsOnLightSurface(top <= 56 && bottom >= 56)
    }
    const schedule = () => { if (frame === null) frame = window.requestAnimationFrame(updateTone) }
    schedule()
    window.addEventListener("scroll", schedule, { passive: true })
    window.addEventListener("resize", schedule)
    return () => {
      if (frame !== null) window.cancelAnimationFrame(frame)
      window.removeEventListener("scroll", schedule)
      window.removeEventListener("resize", schedule)
    }
  }, [])

  return (
    <nav className={`nav${isOnLightSurface ? " nav--on-light" : ""}`}>
      <div className="nav-mark">
        <span className="nav-dot"></span> SML
        <span style={{ opacity: 0.4, marginLeft: 8 }}>/</span>
        <span style={{ opacity: 0.7, marginLeft: 8 }}>DASH</span>
      </div>
      <ul className="nav-links">
        <li><a href="#trial" onClick={handleClick}>{labels.trial}</a></li>
        <li><a href="#tools" onClick={handleClick}>{t.systems}</a></li>
        <li><a href="#research" onClick={handleClick}>{t.research}</a></li>
        <li><Link href="/pricing">{labels.pricing}</Link></li>
        <li><Link href="/docs">{labels.docs}</Link></li>
        <li><a href="#contact" onClick={handleClick}>{t.contact}</a></li>
      </ul>
      <div className="nav-actions">
        <div className="lang-switch" role="group" aria-label={t.language}>
          {SUPPORTED_LANGUAGES.map((item) => (
            <button key={item.code} type="button" className={`lang-button ${item.code === language ? "is-active" : ""}`}
              aria-pressed={item.code === language} title={item.nativeName} onClick={() => onLanguageChange(item.code)}>
              {item.label}
            </button>
          ))}
        </div>
        <Link className="nav-cta" href={signedIn ? "/app" : "/login"}>{signedIn ? labels.openApp : labels.signIn}</Link>
      </div>
    </nav>
  )
}

const NAV_EXTRA: Record<Language, { trial: string; pricing: string; docs: string; signIn: string; openApp: string }> = {
  en: { trial: "Try it", pricing: "Pricing", docs: "API", signIn: "Sign in", openApp: "Open app" },
  ko: { trial: "체험하기", pricing: "요금", docs: "API", signIn: "로그인", openApp: "앱 열기" },
  de: { trial: "Testen", pricing: "Preise", docs: "API", signIn: "Anmelden", openApp: "App öffnen" },
}

function CursorGlow() {
  useEffect(() => {
    if (!window.matchMedia?.("(pointer: fine)").matches || window.innerWidth <= 900) return
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    const cursor = document.createElement("div")
    cursor.id = "cursor-glow"
    document.body.appendChild(cursor)
    let tx = 0, ty = 0, cx = 0, cy = 0
    const onMove = (e: PointerEvent) => { tx = e.clientX; ty = e.clientY; cursor.style.opacity = "0.9" }
    window.addEventListener("pointermove", onMove)
    let raf = 0
    const anim = () => {
      cx += (tx - cx) * 0.22
      cy += (ty - cy) * 0.22
      cursor.style.transform = `translate(${cx}px, ${cy}px) translate(-50%, -50%)`
      raf = requestAnimationFrame(anim)
    }
    raf = requestAnimationFrame(anim)
    const onOver = (e: MouseEvent) => {
      const big = (e.target as HTMLElement).closest("a, button, .tool-card, .research-card, .pub-row, .contact-row")
      cursor.style.width = big ? "40px" : "14px"
      cursor.style.height = big ? "40px" : "14px"
    }
    document.addEventListener("mouseover", onOver)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("pointermove", onMove)
      document.removeEventListener("mouseover", onOver)
      cursor.remove()
    }
  }, [])
  return null
}

export function HomePage() {
  const locale = useLocale()
  const router = useRouter()
  const language: Language = isLanguage(locale) ? locale : "en"
  const t = dashTranslations[language]

  const handleLanguageChange = useCallback((next: Language) => {
    setLocaleCookie(next)
    document.documentElement.lang = SUPPORTED_LANGUAGES.find((i) => i.code === next)?.htmlLang ?? "en"
    router.refresh()
  }, [router])

  return (
    <div className="dark body-gradient min-h-screen text-[var(--sml-ink)]">
      <div className="noise-overlay" />
      <div className="vignette-overlay" />
      <div id="face-bg" className="face-bg" aria-hidden="true" />
      <LiquidCanvas />
      <SpiderCursor />
      <Navbar t={t.nav} language={language} onLanguageChange={handleLanguageChange} />
      <CursorGlow />
      <main>
        <HeroSection t={t.hero} language={language} />
        <TrialSection language={language} />
        <ToolsSection t={t.tools} />
        <AboutSection t={t.research} about={t.about} />
        <CustomersSection t={t.customers} language={language} />
        <ContactSection t={t.contact} />
      </main>
    </div>
  )
}

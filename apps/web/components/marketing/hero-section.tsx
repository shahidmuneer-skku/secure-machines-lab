"use client"

import { useEffect, useState } from "react"
import type { DashTranslations, Language } from "@/lib/marketing/i18n"
import { watermarkGalleryImages } from "@/lib/marketing/watermark-gallery.generated"

function useMouseParallax(strength = 1) {
  const [xy, setXY] = useState({ x: 0, y: 0 })
  useEffect(() => {
    function onMove(e: PointerEvent) {
      const nx = (e.clientX / window.innerWidth - 0.5) * strength
      const ny = (e.clientY / window.innerHeight - 0.5) * strength
      setXY({ x: nx, y: ny })
    }
    window.addEventListener("pointermove", onMove)
    return () => window.removeEventListener("pointermove", onMove)
  }, [strength])
  return xy
}

function useScrollProgress() {
  const [y, setY] = useState(0)
  useEffect(() => {
    function onScroll() { setY(window.scrollY) }
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])
  return y
}

function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  const pad = (n: number) => String(n).padStart(2, "0")
  const utc = new Date(now.getTime() + now.getTimezoneOffset() * 60000)
  const kst = new Date(utc.getTime() + 9 * 3600 * 1000)
  return (
    <span style={{ fontVariantNumeric: "tabular-nums" }}>
      {pad(kst.getUTCHours())}:{pad(kst.getUTCMinutes())}:{pad(kst.getUTCSeconds())} KST
    </span>
  )
}

function HeroMarquee({ items }: { items: DashTranslations["hero"]["marquee"] }) {
  const full = [...items, ...items]
  return (
    <div className="marquee-strip">
      <div className="marquee">
        {full.map((t, i) => (
          <span key={i} className="marquee-item">
            <span className="marquee-dot"></span>
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}

function WatermarkGallery({ language }: { language: Language }) {
  const localeImages = language === "ko"
    ? watermarkGalleryImages.korean
    : watermarkGalleryImages.english
  const images = [...watermarkGalleryImages.common, ...localeImages]

  if (images.length === 0) return null

  return (
    <section className="watermark-gallery" aria-label="Collaborating organizations">
      <div className="watermark-gallery__viewport">
        <div className="watermark-gallery__rail">
          {[false, true].map((isDuplicate) => (
            <div
              key={isDuplicate ? "duplicate" : "source"}
              className={`watermark-gallery__group${isDuplicate ? " watermark-gallery__group--duplicate" : ""}`}
              aria-hidden={isDuplicate || undefined}
            >
              {images.map((image, index) => (
                <img
                  className={`watermark-gallery__logo${image.tickerWide ? " watermark-gallery__logo--extra-large" : image.tickerProminent ? " watermark-gallery__logo--prominent" : ""}`}
                  key={`${isDuplicate ? "duplicate" : "source"}-${image.src}`}
                  src={image.src}
                  alt={isDuplicate ? "" : image.alt}
                  loading={index < 4 ? "eager" : "lazy"}
                  decoding="async"
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function HeroStats({ stats }: { stats: DashTranslations["hero"]["stats"] }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
      gap: 1, padding: "0 clamp(20px, 4vw, 48px)", background: "var(--line)",
    }}>
      {stats.map((s, i) => (
        <div key={i} style={{
          background: "var(--bg-elevated)", padding: "22px 20px", position: "relative",
          border: "1px solid var(--line)",
        }}>
          <div style={{
            fontSize: "clamp(26px, 3vw + 8px, 44px)", fontFamily: "var(--serif)",
            fontStyle: "italic", letterSpacing: "-0.02em", lineHeight: 1, marginBottom: 10,
            color: "var(--accent-2)",
          }}>{s.v}</div>
          <div style={{
            fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.22em",
            textTransform: "uppercase", color: "var(--ink)", marginBottom: 4,
          }}>{s.l}</div>
          <div style={{
            fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.12em",
            color: "var(--ink-faint)",
          }}>{s.sub}</div>
        </div>
      ))}
    </div>
  )
}

export default function HeroSection({ t, language }: { t: DashTranslations["hero"], language: Language }) {
  const { x, y } = useMouseParallax(20)
  const scrollY = useScrollProgress()
  const [vh, setVh] = useState(800)

  useEffect(() => {
    setVh(window.innerHeight)
    const onResize = () => setVh(window.innerHeight)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])

  const heroOpacity = Math.max(0, 1 - scrollY / (vh * 0.8))
  const heroTranslate = scrollY * 0.25

  return (
    <section id="hero" style={{
      position: "relative", minHeight: "100vh",
      paddingTop: "clamp(80px, 14vh, 140px)", paddingBottom: "80px",
      display: "flex", flexDirection: "column", justifyContent: "space-between",
      overflow: "hidden", zIndex: 2,
    }}>
      {/* Top meta bar */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        padding: "0 clamp(20px, 4vw, 48px)",
        fontFamily: "var(--mono)", fontSize: 11, color: "var(--ink-dim)",
        letterSpacing: "0.18em", textTransform: "uppercase",
        opacity: heroOpacity,
      }}>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          {/* <span>EST. 2025 · Suwon, KR</span> */}
          <span className="chip"><span className="led"></span> {t.status}</span>
        </div>
        <div style={{ display: "flex", gap: 24, textAlign: "right" }}>
          {/* <span className="hide-sm"><LiveClock /></span> */}
          {/* <span>v26.4</span> */}
        </div>
      </div>

      {/* HERO CENTERPIECE */}
      <div style={{
        position: "relative", flex: 1, display: "flex", flexDirection: "column",
        justifyContent: "center", padding: "0 clamp(20px, 4vw, 48px)",
        opacity: heroOpacity,
        transform: `translateY(${heroTranslate}px)`,
      }}>
        {/* Small label row */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginBottom: "clamp(20px, 4vh, 40px)",
          fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.24em", textTransform: "uppercase",
          color: "var(--ink-dim)", flexWrap: "wrap", gap: 12,
        }}>
          {/* <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ width: 6, height: 6, borderRadius: 2, background: "var(--accent)" }}></span>
            Forensic AI · Media integrity · Generative defense
          </span>
          <span className="hide-sm" style={{ color: "var(--ink-faint)" }}>Index / Introduction · 001</span> */}
        </div>

        {/* Glitch headline */}
        <h1 className="hero-headline hero-headline--glitch" style={{
          margin: 0, fontSize: "140px", fontWeight: 500, lineHeight: 0.88, letterSpacing: "-0.03em",
          transform: `translate3d(${x * -0.4}px, ${y * -0.4}px, 0)`,
        }}>
          <div className="h-row h-row--top">
            <span className="h-word h-glitch" data-text={t.title.secure}>{t.title.secure}</span>
          </div>
          <div className="h-row h-row--mid">
            <span className="h-word h-glitch" data-text={t.title.machines}>{t.title.machines}</span>
          </div>
          <div className="h-row h-row--bot">
            <span className="h-word h-word--fill h-glitch" data-text={t.title.lab}>{t.title.lab}</span>
          </div>
        </h1>

        {/* Subtitle row */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr auto", alignItems: "end",
          gap: 24, marginTop: "clamp(28px, 5vh, 56px)",
        }}>
          <p style={{
            margin: 0, maxWidth: 560,
            fontSize: "clamp(16px, 1.15vw + 8px, 20px)",
            lineHeight: 1.55, color: "var(--ink-dim)",
          }}>
            {t.subtitle}
          </p>
          <div className="hide-sm" style={{ textAlign: "right" }}>
            <div style={{
              fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.2em",
              textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 8,
            }}>
              {t.affiliation}
            </div>
            <a href="#tools" onClick={(e) => {
              e.preventDefault()
              document.getElementById("tools")?.scrollIntoView({ behavior: "smooth", block: "start" })
            }} style={{
              display: "inline-flex", alignItems: "center", gap: 10,
              fontFamily: "var(--mono)", fontSize: 12, letterSpacing: "0.2em", textTransform: "uppercase",
              color: "var(--ink)", borderBottom: "1px solid var(--line-2)", paddingBottom: 6,
              textDecoration: "none", cursor: "pointer",
            }}>{t.exploreSystems}</a>
          </div>
        </div>
      </div>

      {/* Bottom: marquee + watermark gallery + stats */}
      <div style={{ opacity: heroOpacity }}>
        <HeroMarquee items={t.marquee} />
        <WatermarkGallery language={language} />
        <HeroStats stats={t.stats} />
      </div>
    </section>
  )
}

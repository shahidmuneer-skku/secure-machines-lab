"use client"

import { useEffect, useRef, useState, useMemo } from "react"
import { Search, Ban, Network } from "lucide-react"
import type { DashTranslations } from "@/lib/marketing/i18n"

function SectionHeader({ idx, eyebrow, title, sub }: {
  idx: string; eyebrow: string; title: React.ReactNode; sub?: string
}) {
  return (
    <div className="section-header" style={{
      display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.6fr)",
      gap: 40, marginBottom: "clamp(48px, 8vh, 96px)", alignItems: "end",
    }}>
      <div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.3em", textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 14 }}>
          {idx}
        </div>
        <div className="eyebrow">{eyebrow}</div>
      </div>
      <div>
        <h2 style={{
          margin: 0, fontSize: "clamp(40px, 6.5vw, 96px)", fontWeight: 500,
          lineHeight: 0.95, letterSpacing: "-0.03em",
        }}>{title}</h2>
        {sub && <p style={{
          maxWidth: 560, marginTop: 28,
          fontSize: "clamp(15px, 1vw + 8px, 18px)",
          color: "var(--ink-dim)", lineHeight: 1.55,
        }}>{sub}</p>}
      </div>
    </div>
  )
}

function ResearchBackdrop() {
  const particles = useMemo(() => {
    const arr = []
    for (let i = 0; i < 60; i++) {
      arr.push({
        x: 20 + Math.random() * 40, y: 10 + Math.random() * 80,
        size: Math.random() * 2.5 + 0.5, delay: Math.random() * 6,
        dur: 5 + Math.random() * 6,
        driftX: (Math.random() - 0.5) * 80, driftY: -30 - Math.random() * 100,
        hue: Math.random() > 0.7 ? "var(--accent-2)" : Math.random() > 0.5 ? "var(--accent-3)" : "var(--accent)",
      })
    }
    return arr
  }, [])

  const streaks = useMemo(() => {
    const arr = []
    for (let i = 0; i < 14; i++) {
      arr.push({ y: 20 + Math.random() * 60, len: 60 + Math.random() * 180, delay: Math.random() * 5, dur: 3 + Math.random() * 4 })
    }
    return arr
  }, [])

  return (
    <div className="research-bg" aria-hidden="true">
      <div className="research-bg-glow"></div>
      {/* Real face image as backdrop */}
      <div className="research-bg-face-img" style={{
        position: "absolute", inset: 0, overflow: "hidden",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <img src="/images/background.png" alt="" style={{
          width: "100%", height: "100%", objectFit: "cover", objectPosition: "center 30%",
          opacity: 0.18, filter: "saturate(1.4) contrast(1.1)",
          maskImage: "radial-gradient(ellipse 60% 70% at 45% 45%, black 20%, transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse 60% 70% at 45% 45%, black 20%, transparent 75%)",
        }} />
      </div>
      <svg className="research-bg-face" viewBox="0 0 800 900" preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="faceFill" cx="45%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.15"/>
            <stop offset="40%" stopColor="var(--accent-3)" stopOpacity="0.08"/>
            <stop offset="80%" stopColor="#0a0c14" stopOpacity="0.2"/>
            <stop offset="100%" stopColor="#0a0c14" stopOpacity="0"/>
          </radialGradient>
          <linearGradient id="faceEdge" x1="0" x2="1">
            <stop offset="0%" stopColor="var(--accent-2)" stopOpacity="0"/>
            <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.45"/>
            <stop offset="100%" stopColor="var(--accent-3)" stopOpacity="0"/>
          </linearGradient>
          <filter id="faceBlur2"><feGaussianBlur stdDeviation="2.5"/></filter>
        </defs>

        <path
          d="M 240,200 Q 220,120 320,90 Q 420,60 500,110 Q 580,160 600,280 Q 620,400 580,500 Q 540,600 440,640 Q 320,680 260,580 Q 200,480 210,360 Q 220,250 240,200 Z"
          fill="none" stroke="url(#faceEdge)" strokeWidth="1.2" className="face-rim"
        />

        <g className="flares">
          {particles.map((p, i) => (
            <circle key={i} cx={p.x * 8} cy={p.y * 9} r={p.size} fill={p.hue}
              style={{ "--dx": `${p.driftX}px`, "--dy": `${p.driftY}px`, animation: `flareFloat ${p.dur}s ease-out ${p.delay}s infinite` } as React.CSSProperties}
            />
          ))}
        </g>

        <g className="streaks">
          {streaks.map((s, i) => (
            <line key={i} x1="380" x2={380 + s.len} y1={s.y * 9} y2={s.y * 9}
              stroke="var(--accent)" strokeWidth="0.6" opacity="0.4"
              style={{ animation: `streakFlow ${s.dur}s ease-out ${s.delay}s infinite` }}
            />
          ))}
        </g>
      </svg>
    </div>
  )
}

function ResearchCard({
  area,
  i,
}: {
  area: { tag: string; title: string; desc: string; icon: React.ReactNode; venues: readonly string[] }
  i: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true) }, { threshold: 0.2 })
    if (ref.current) io.observe(ref.current)
    return () => io.disconnect()
  }, [])

  return (
    <div ref={ref} className={`research-card ${visible ? "is-visible" : ""}`} style={{ animationDelay: `${i * 0.12}s` }}>
      <div className="research-card-img" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 240, color: 'var(--accent)' }}>
        {area.icon}
        <div className="research-card-hud">
          <span className="research-card-tag">{area.tag}</span>
          <span className="research-card-num">0{i + 1}</span>
        </div>
      </div>
      <div className="research-card-body">
        <h3>{area.title}</h3>
        <p>{area.desc}</p>
        <div className="research-card-venues">
          {area.venues.map((v, k) => <span key={k}>{v}</span>)}
        </div>
      </div>
      <div className="research-card-bar"></div>
    </div>
  )
}

export default function AboutSection({
  t,
  about,
}: {
  t: DashTranslations["research"]
  about: DashTranslations["about"]
}) {
  const areas = [
    {
      ...t.areas[0],
      icon: <Search size={120} strokeWidth={1} />,
    },
    {
      ...t.areas[1],
      icon: <Ban size={120} strokeWidth={1} />,
    },
    {
      ...t.areas[2],
      icon: <Network size={120} strokeWidth={1} />,
    },
  ]

  const pubs = [
    { year: "2025", title: "SOK: Systematization of deepfake detection and generation", venue: "EuroS&P", tag: "Full" },
    { year: "2024", title: "UGAD: Universal generative AI detector utilizing frequency fingerprints", venue: "ACM CIKM", tag: "Full" },
    { year: "2024", title: "Gradient alignment for cross-domain face anti-spoofing", venue: "CVPR", tag: "Full" },
    { year: "2024", title: "Beyond the screen: Moiré pattern effects on deepfake detectors", venue: "CVPR", tag: "Full" },
    { year: "2023", title: "Quality-agnostic deepfake detection with intra-model collaborative learning", venue: "ICCV", tag: "Full" },
    { year: "2022", title: "ADD: Frequency attention and multi-view based knowledge distillation to detect low-quality compressed deepfake images", venue: "AAAI", tag: "Full" },
    { year: "2021", title: "FakeAVCeleb: A novel audio-video multimodal deepfake dataset", venue: "NeurIPS", tag: "Datasets" },
    { year: "2021", title: "One detector to rule them all: Towards a general deepfake attack detection framework", venue: "WWW", tag: "Full" },
    { year: "2021", title: "FReTAL: Generalizing deepfake detection using knowledge distillation and representation learning", venue: "CVPR", tag: "Full" },
    { year: "2020", title: "OC-FakeDect: Classifying deepfakes using one-class variational autoencoder", venue: "CVPR", tag: "Workshop" },
  ]

  return (
    <section id="research" style={{
      position: "relative", padding: "clamp(100px, 14vh, 180px) clamp(20px, 4vw, 48px)", zIndex: 2,
    }}>
      <div style={{ maxWidth: 1400, margin: "0 auto", position: "relative", zIndex: 2 }}>
        <div className="research-header-wrap">
          <ResearchBackdrop />
          <SectionHeader
            idx={t.idx} eyebrow={t.eyebrow}
            title={<>{t.titleMain}<br /><em style={{ fontFamily: "var(--serif)", fontStyle: "italic", fontWeight: 400, color: "var(--accent-3)" }}>{t.titleEm}</em></>}
            sub={t.subtitle}
          />
        </div>

        <div className="research-grid">
          {areas.map((a, i) => <ResearchCard key={i} area={a} i={i} />)}
        </div>

        {/* Publications list */}
        <div style={{ marginTop: "clamp(80px, 12vh, 140px)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 32, flexWrap: "wrap", gap: 12 }}>
            <div>
              <div className="eyebrow">{t.publications.eyebrow}</div>
              <div style={{ fontFamily: "var(--serif)", fontStyle: "italic", fontSize: "clamp(28px, 4vw, 44px)", marginTop: 12 }}>{t.publications.title}</div>
            </div>
            <a href="https://scholar.google.com/citations?user=mHnj60cAAAAJ&hl=en" target="_blank" rel="noopener noreferrer" style={{
              fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.2em", textTransform: "uppercase",
              color: "var(--ink-dim)", borderBottom: "1px solid var(--line-2)", paddingBottom: 4, textDecoration: "none",
            }}>{t.publications.all}</a>
          </div>

          <div className="pubs">
            {pubs.map((p, i) => (
              <a key={i} href="#" className="pub-row">
                <span className="pub-year">{p.year}</span>
                <span className="pub-title">{p.title}</span>
                <span className="pub-venue">{p.venue}</span>
                <span className="pub-tag">
                  {p.tag === "Datasets"
                    ? t.publications.tags.datasets
                    : p.tag === "Workshop"
                      ? t.publications.tags.workshop
                      : t.publications.tags.full}
                </span>
                <span className="pub-arrow">↗</span>
              </a>
            ))}
          </div>
        </div>

        {/* About lab */}
        <div id="about" className="about-grid" style={{
          marginTop: "clamp(100px, 14vh, 160px)", display: "grid",
          gridTemplateColumns: "1.2fr 1fr", gap: 60, alignItems: "start",
        }}>
          <div>
            <div className="about-index">{about.idx}</div>
            <div className="eyebrow">{about.eyebrow}</div>
            <h3 style={{
              marginTop: 18, fontSize: "clamp(32px, 4.5vw, 64px)", fontWeight: 500, lineHeight: 1.05, letterSpacing: "-0.02em",
            }}>
              {about.headingPrefix} <span style={{ fontFamily: "var(--serif)", fontStyle: "italic", color: "var(--accent)" }}>{about.university}</span>,
              {" "}{about.headingSuffix}
            </h3>
            <p style={{ marginTop: 24, fontSize: 17, lineHeight: 1.6, color: "var(--ink-dim)", maxWidth: 640 }}>
              {about.body}
            </p>
          </div>
          <div className="about-facts">
            {about.facts.map(([k, v], i) => (
              <div key={i} className="about-fact">
                <div className="about-fact-k">{k}</div>
                <div className="about-fact-v">{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

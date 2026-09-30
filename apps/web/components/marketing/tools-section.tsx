"use client"

import { useEffect, useRef, useState } from "react"
import { ShieldCheck, Bot } from "lucide-react"
import type { DashTranslations } from "@/lib/marketing/i18n"
import { useHydrated } from "@/hooks/use-hydrated"

// The detector now lives inside the platform; the assistant card opens the
// legacy chatbot when configured, otherwise the news-verification agent.
function getWebUrl(): string {
  return "/app/detect"
}

function getChatBotUrl(): string {
  return process.env.NEXT_PUBLIC_CHAT_BOT_URL || "/app/news"
}


interface Tool {
  id: string
  idx: string
  title: string
  kicker: string
  desc: string
  url: string
  icon: React.ReactNode
  metrics: readonly { k: string; v: string }[]
  tags: string[]
  accent: string
  launch: string
}

function ForensicFace({ t }: { t: DashTranslations["tools"]["face"] }) {
  const landmarks: [number, number][] = [
    [150,360],[158,420],[174,478],[200,528],[240,568],[290,592],[340,604],[392,596],[440,574],[482,540],[516,498],[540,450],[552,400],[556,344],[552,288],
    [212,286],[238,266],[272,262],[306,270],[334,286],
    [370,282],[400,266],[432,262],[460,266],[484,284],
    [352,320],[354,354],[356,388],[358,420],
    [318,446],[338,454],[358,460],[378,454],[398,446],
    [246,330],[266,318],[290,318],[310,332],[288,340],[266,340],
    [388,330],[408,316],[432,316],[452,328],[434,338],[412,340],
    [284,504],[306,490],[332,482],[356,486],[380,482],[406,488],[430,504],[410,528],[384,540],[356,544],[330,540],[306,528],
    [298,504],[332,498],[356,500],[380,498],[412,504],[380,514],[356,516],[332,514],
  ]

  const edges: [number, number][] = []
  for (let i = 0; i < 14; i++) edges.push([i, i + 1])
  for (let i = 15; i < 19; i++) edges.push([i, i + 1])
  for (let i = 20; i < 24; i++) edges.push([i, i + 1])
  edges.push([25,26],[26,27],[27,28])
  for (let i = 29; i < 33; i++) edges.push([i, i + 1])
  edges.push([27,31])
  for (let i = 0; i < 5; i++) edges.push([34 + i, 34 + i + 1])
  edges.push([39, 34])
  for (let i = 0; i < 5; i++) edges.push([40 + i, 40 + i + 1])
  edges.push([45, 40])
  for (let i = 0; i < 11; i++) edges.push([46 + i, 46 + i + 1])
  edges.push([57, 46])
  edges.push([15,34],[19,39],[20,40],[24,45],[28,31],[27,46],[27,52],[31,51],[17,27],[22,27])
  edges.push([3,46],[11,52])
  edges.push([0,15],[14,24])

  const [scanT, setScanT] = useState(0)
  useEffect(() => {
    let raf: number
    const start = performance.now()
    function tick() {
      setScanT(((performance.now() - start) / 4000) % 1)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  const scanY = 180 + scanT * 460
  const hitIdxs = [3, 17, 27, 36, 43, 52, 59]

  return (
    <div className="forensic-face" aria-hidden="true">
      <svg viewBox="0 0 600 700" preserveAspectRatio="xMidYMid meet">
        <defs>
          <radialGradient id="faceGlow" cx="50%" cy="45%" r="55%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.18"/>
            <stop offset="60%" stopColor="var(--accent)" stopOpacity="0.04"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
          </radialGradient>
          <linearGradient id="scanGrad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0"/>
            <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.9"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
          </linearGradient>
          <filter id="faceBlur"><feGaussianBlur stdDeviation="0.4"/></filter>
          <clipPath id="faceBoundary"><ellipse cx="352" cy="430" rx="230" ry="290"/></clipPath>
        </defs>

        <ellipse cx="352" cy="430" rx="260" ry="320" fill="url(#faceGlow)"/>

        <g className="face-frame" stroke="var(--accent)" strokeWidth="1" fill="none" opacity="0.25">
          <line x1="352" y1="80" x2="352" y2="160"/>
          <line x1="352" y1="700" x2="352" y2="780"/>
          <line x1="80" y1="400" x2="160" y2="400"/>
          <line x1="544" y1="400" x2="624" y2="400"/>
          <rect x="110" y="150" width="484" height="560" rx="8" strokeDasharray="2 6" opacity="0.5"/>
        </g>

        <g stroke="var(--accent)" strokeWidth="1.5" fill="none" opacity="0.6">
          <path d="M 110 180 L 110 150 L 140 150"/>
          <path d="M 564 150 L 594 150 L 594 180"/>
          <path d="M 594 680 L 594 710 L 564 710"/>
          <path d="M 140 710 L 110 710 L 110 680"/>
        </g>

        <path
          d="M 150,360 Q 150,220 250,160 Q 352,110 454,160 Q 556,220 556,360 Q 556,510 450,590 Q 352,640 254,590 Q 150,510 150,360 Z"
          fill="none" stroke="var(--accent)" strokeWidth="1" opacity="0.22" className="face-silhouette"
        />

        <g stroke="var(--accent)" strokeWidth="0.8" fill="none" opacity="0.35" filter="url(#faceBlur)">
          {edges.map(([a, b], i) => {
            if (!landmarks[a] || !landmarks[b]) return null
            return <line key={i} x1={landmarks[a][0]} y1={landmarks[a][1]}
              x2={landmarks[b][0]} y2={landmarks[b][1]}
              className="face-edge" style={{ animationDelay: `${(i % 20) * 0.08}s` }}
            />
          })}
        </g>

        <g>
          {landmarks.map(([lx, ly], i) => {
            const isHit = hitIdxs.includes(i)
            return (
              <g key={i}>
                <circle cx={lx} cy={ly} r={isHit ? 3.2 : 1.6}
                  fill={isHit ? "var(--accent-2)" : "var(--accent)"}
                  className={isHit ? "face-dot face-dot--hit" : "face-dot"}
                  style={{ animationDelay: `${(i % 24) * 0.06}s` }}
                />
                {isHit && (
                  <circle cx={lx} cy={ly} r="8"
                    fill="none" stroke="var(--accent-2)" strokeWidth="1"
                    className="face-hit-ring" style={{ animationDelay: `${i * 0.2}s` }}
                  />
                )}
              </g>
            )
          })}
        </g>

        <g clipPath="url(#faceBoundary)">
          <line x1="80" y1={scanY} x2="624" y2={scanY}
            stroke="url(#scanGrad)" strokeWidth="2" opacity="0.7"/>
          <rect x="80" y={scanY - 22} width="544" height="22" fill="var(--accent)" opacity="0.04"/>
        </g>

        <g className="face-labels" fontFamily="var(--mono), monospace" fontSize="9" fill="var(--accent)" opacity="0.75" letterSpacing="1">
          <g transform="translate(430, 268)">
            <line x1="0" y1="16" x2="60" y2="16" stroke="var(--accent)" strokeWidth="0.5" opacity="0.4"/>
            <text x="64" y="14" textAnchor="start">{t.eyeTitle}</text>
            <text x="64" y="26" fill="var(--ink-dim)" fontSize="7">{t.eyeSub}</text>
          </g>
          <g transform="translate(480, 450)">
            <line x1="0" y1="10" x2="40" y2="10" stroke="var(--accent)" strokeWidth="0.5" opacity="0.4"/>
            <text x="44" y="8" textAnchor="start">{t.noseTitle}</text>
            <text x="44" y="20" fill="var(--ink-dim)" fontSize="7">{t.noseSub}</text>
          </g>
          <g transform="translate(100, 340)" textAnchor="end">
            <line x1="0" y1="10" x2="-40" y2="10" stroke="var(--accent)" strokeWidth="0.5" opacity="0.4"/>
            <text x="-44" y="8">{t.browTitle}</text>
            <text x="-44" y="20" fill="var(--ink-dim)" fontSize="7">{t.browSub}</text>
          </g>
          <g transform="translate(100, 520)" textAnchor="end">
            <line x1="0" y1="10" x2="-50" y2="10" stroke="var(--accent-2)" strokeWidth="0.5" opacity="0.6"/>
            <text x="-54" y="8" fill="var(--accent-2)">{t.mouthTitle}</text>
            <text x="-54" y="20" fill="var(--ink-dim)" fontSize="7">{t.mouthSub}</text>
          </g>
        </g>

        <g transform="translate(120, 670)" fontFamily="var(--mono), monospace" fontSize="10" fill="var(--ink-dim)" letterSpacing="2">
          <text x="0" y="0">{t.footer}</text>
        </g>
      </svg>
    </div>
  )
}

function ToolCard({
  tool,
  labels,
  onOpen,
}: {
  tool: Tool
  labels: DashTranslations["tools"]["labels"]
  onOpen: () => void
}) {
  const cardRef = useRef<HTMLDivElement>(null)
  const [mouse, setMouse] = useState({ x: 0.5, y: 0.5, active: false })

  function onMove(e: React.MouseEvent) {
    const r = cardRef.current!.getBoundingClientRect()
    setMouse({ x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height, active: true })
  }

  return (
    <div ref={cardRef} className="tool-card"
      onMouseMove={onMove}
      onMouseLeave={() => setMouse(m => ({ ...m, active: false }))}
      style={{ "--tool-accent": tool.accent } as React.CSSProperties}
    >
      <div className="tool-spotlight" style={{
        opacity: mouse.active ? 1 : 0,
        background: `radial-gradient(320px circle at ${mouse.x * 100}% ${mouse.y * 100}%, ${tool.accent}22, transparent 60%)`,
      }} />

      <div className="tool-inner">
        <div className="tool-head">
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div className="tool-idx">{tool.idx}</div>
            <div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.24em", textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 4 }}>
                {tool.kicker}
              </div>
              <div style={{ fontSize: "clamp(26px, 2.6vw, 40px)", fontWeight: 500, letterSpacing: "-0.02em" }}>{tool.title}</div>
            </div>
          </div>
          <div className="chip" style={{ borderColor: tool.accent + "55" }}>
            <span className="led" style={{ background: tool.accent, boxShadow: `0 0 8px ${tool.accent}` }}></span> {labels.live}
          </div>
        </div>

        <p style={{
          margin: "28px 0 0", color: "var(--ink-dim)",
          fontSize: "clamp(15px, 1vw + 7px, 17px)", lineHeight: 1.55, maxWidth: 500,
        }}>{tool.desc}</p>

        <button onClick={onOpen} className="tool-preview" style={{ marginTop: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-elevated)', border: '1px solid var(--line)', borderRadius: 12, height: 200, color: 'var(--ink-dim)' }}>
          {tool.icon}
          <div className="tool-preview-overlay">
            <div className="tool-preview-btn">
              <span className="tool-preview-arrow">↗</span>
              {labels.openLivePreview}
            </div>
          </div>
          <div className="tool-scanline"></div>
        </button>

        <div className="tool-metrics">
          {tool.metrics.map((m, i) => (
            <div key={i} className="tool-metric">
              <div className="tool-metric-v">{m.v}</div>
              <div className="tool-metric-k">{m.k}</div>
            </div>
          ))}
        </div>

        <a href={tool.url} className="tool-launch" rel="noopener noreferrer">
          <span>{tool.launch}</span>
          <span className="tool-launch-arrow">→</span>
        </a>
      </div>
    </div>
  )
}

function ToolModal({
  tool,
  labels,
  onClose,
}: {
  tool: Tool
  labels: DashTranslations["tools"]["labels"]
  onClose: () => void
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  return (
    <div className="tool-modal" onClick={onClose}>
      <div className="tool-modal-inner" onClick={e => e.stopPropagation()}>
        <div className="tool-modal-head">
          <div style={{ display: "flex", gap: 6 }}>
            <span className="dot-r"></span><span className="dot-a"></span><span className="dot-g"></span>
          </div>
          <div className="tool-modal-url">
            <span style={{ color: "var(--accent)" }}>●</span> securemachineslab.com / {tool.id}
          </div>
          <button onClick={onClose} className="tool-modal-close">ESC ×</button>
        </div>
        <div className="tool-modal-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-elevated)', minHeight: 400, color: 'var(--ink-dim)' }}>
          {tool.icon}
          <div className="tool-modal-scan"></div>
        </div>
        <div className="tool-modal-foot">
          <div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.24em", textTransform: "uppercase", color: "var(--ink-faint)" }}>{tool.kicker}</div>
            <div style={{ fontSize: 22, fontWeight: 500, marginTop: 4 }}>{tool.title}</div>
          </div>
          <a href={tool.url} className="tool-launch" style={{ margin: 0 }} rel="noopener noreferrer">
            <span>{labels.openFullSystem}</span>
            <span className="tool-launch-arrow">→</span>
          </a>
        </div>
      </div>
    </div>
  )
}

export default function ToolsSection({ t }: { t: DashTranslations["tools"] }) {
  const [active, setActive] = useState<number | null>(null)
  // Tool URLs depend on window.location, so they are only filled in after hydration.
  const mounted = useHydrated()

  const tools: Tool[] = [
    {
      id: "detector", idx: "01", title: t.cards.detector.title, kicker: t.cards.detector.kicker,
      desc: t.cards.detector.desc,
      url: mounted ? getWebUrl() : "#", icon: <ShieldCheck size={120} strokeWidth={1} />,
      metrics: t.cards.detector.metrics,
      tags: ["Image", "Video", "Forensics"], accent: "var(--accent)",
      launch: t.cards.detector.launch,
    },
    {
      id: "chatbot", idx: "02", title: t.cards.assistant.title, kicker: t.cards.assistant.kicker,
      desc: t.cards.assistant.desc,
      url: mounted ? getChatBotUrl() : "#", icon: <Bot size={120} strokeWidth={1} />,
      metrics: t.cards.assistant.metrics,
      tags: ["LLM", "Analysis", "Agents"], accent: "var(--accent-3)",
      launch: t.cards.assistant.launch,
    },
  ]

  return (
    <section id="tools" style={{
      position: "relative", padding: "clamp(100px, 14vh, 180px) clamp(20px, 4vw, 48px)", zIndex: 2,
    }}>
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        {/* Header with forensic face */}
        <div className="tools-header">
          <ForensicFace t={t.face} />
          <div className="tools-header-inner">
            <div className="tools-header-meta">
              <div className="tools-header-idx">{t.sectionIdx}</div>
              <div className="eyebrow">{t.eyebrow}</div>
            </div>
            <h2 className="tools-header-title">
              {t.titleLine}<br />
              <em>{t.titleEm}</em>
            </h2>
            <p className="tools-header-sub">
              {t.subtitle}
            </p>
          </div>
        </div>

        <div className="tools-grid">
          {tools.map((tool, i) => (
            <ToolCard key={tool.id} tool={tool} labels={t.labels} onOpen={() => setActive(i)} />
          ))}
        </div>

        {/* Use-case strip */}
        <div style={{
          marginTop: "clamp(60px, 10vh, 120px)", borderTop: "1px solid var(--line)",
          paddingTop: 40, display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 40,
        }}>
          <div style={{ gridColumn: "1 / -1", marginBottom: 10 }}>
            <div className="eyebrow">{t.useCases.eyebrow}</div>
          </div>
          {t.useCases.items.map((c, i) => (
            <div key={i} style={{ borderLeft: "1px solid var(--line-2)", paddingLeft: 18 }}>
              <div style={{ fontFamily: "var(--serif)", fontSize: 26, fontStyle: "italic", marginBottom: 8 }}>{c.h}</div>
              <div style={{ color: "var(--ink-dim)", fontSize: 14, lineHeight: 1.5 }}>{c.b}</div>
            </div>
          ))}
        </div>
      </div>

      {active !== null && <ToolModal tool={tools[active]} labels={t.labels} onClose={() => setActive(null)} />}
    </section>
  )
}

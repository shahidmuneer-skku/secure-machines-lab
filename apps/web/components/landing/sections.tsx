"use client"

import Box from "@mui/material/Box"
import Container from "@mui/material/Container"
import Grid from "@mui/material/Grid"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import {
  IconApi, IconArrowRight, IconArrowUpRight, IconBroadcast, IconCertificate, IconCheck, IconEye, IconLanguage, IconLock,
  IconMail, IconMapPin, IconNews, IconPhotoScan, IconReportAnalytics, IconScan, IconSparkles, IconUpload, type Icon,
} from "@tabler/icons-react"
import Image from "next/image"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { useEffect, useRef, type ReactNode } from "react"

import { dashTranslations, type Language } from "@/lib/marketing/i18n"
import { partnersFor } from "@/lib/marketing/partners"
import { PUBLICATIONS } from "@/lib/marketing/publications"

const CONTACT_EMAIL = "woo@securemachineslab.com"

/** Landing tokens (globals.css): accent/amber/done adapt to the theme, the hero palette in dark. */
const ACCENT = "var(--landing-accent)"
const AMBER = "var(--landing-amber)"
const DONE = "var(--landing-done)"
const LINE = "var(--landing-line)"

const MONO = {
  fontFamily: "var(--sml-mono)", fontSize: "0.75rem", fontWeight: 500, letterSpacing: "0.12em", textTransform: "uppercase",
} as const
const BODY = { color: "text.secondary", fontSize: { xs: "1rem", md: "1.0625rem" }, lineHeight: 1.65 } as const

// ---------- shared pieces ------------------------------------------------------------------------

/**
 * Short entrance transition below the hero. Content is visible without JavaScript and with reduced
 * motion; only sections still below the fold when the page hydrates fade in once.
 */
function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    if (el.getBoundingClientRect().top < window.innerHeight) return
    el.dataset.reveal = "hidden"
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        el.dataset.reveal = "shown"
        io.disconnect()
      }
    }, { rootMargin: "0px 0px -8% 0px" })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <Box ref={ref} sx={{
      transition: `opacity .5s ease ${delay}ms, transform .5s cubic-bezier(.2,.7,.2,1) ${delay}ms`,
      "&[data-reveal='hidden']": { opacity: 0, transform: "translateY(16px)" },
    }}>
      {children}
    </Box>
  )
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <Typography component="p" sx={{ ...MONO, color: ACCENT, display: "inline-flex", alignItems: "center", gap: 1.25,
      "&::before": { content: '""', width: 18, height: "1px", bgcolor: "currentColor", opacity: 0.8 } }}>
      {children}
    </Typography>
  )
}

function SectionHeading({ eyebrow, title, subtitle, id }: { eyebrow: string; title: ReactNode; subtitle?: ReactNode; id?: string }) {
  return (
    <Box sx={{ maxWidth: 760, mb: { xs: 5, md: 7 } }}>
      <Eyebrow>{eyebrow}</Eyebrow>
      <Typography id={id} variant="h2" component="h2" sx={{ mt: 1.75, fontWeight: 800, letterSpacing: "-0.025em",
        fontSize: { xs: "2rem", md: "2.75rem" }, lineHeight: 1.1, textWrap: "balance" }}>{title}</Typography>
      {subtitle && <Typography sx={{ ...BODY, mt: 2, maxWidth: 640 }}>{subtitle}</Typography>}
    </Box>
  )
}

function Section({ id, children, raised = false, labelledBy }: { id?: string; children: ReactNode; raised?: boolean; labelledBy?: string }) {
  return (
    <Box component="section" id={id} aria-labelledby={labelledBy} sx={{
      py: { xs: 9, md: 13 }, scrollMarginTop: 72, bgcolor: raised ? "background.paper" : "transparent",
      borderTop: raised ? "1px solid" : "none", borderBottom: raised ? "1px solid" : "none", borderColor: "divider",
    }}>
      <Container maxWidth="lg">{children}</Container>
    </Box>
  )
}

/** Panel with a hairline border, the landing's surface style. */
const PANEL = {
  bgcolor: "background.paper", border: "1px solid", borderColor: "divider", borderRadius: "16px",
} as const

/** A small triangulated lattice, the polygon language of the hero, for accents. */
function Lattice({ cols = 7, rows = 4, size = 34, opacity = 0.35 }: { cols?: number; rows?: number; size?: number; opacity?: number }) {
  const h = size * 0.866
  const lines: string[] = []
  for (let r = 0; r <= rows; r++) {
    const off = r % 2 ? size / 2 : 0
    lines.push(`M${off} ${r * h}h${cols * size}`)
    if (r < rows) {
      for (let c = 0; c <= cols; c++) {
        const x = c * size + off
        lines.push(`M${x} ${r * h}l${size / 2} ${h}`, `M${x} ${r * h}l${-size / 2} ${h}`)
      }
    }
  }
  return (
    <svg aria-hidden width={cols * size + size} height={rows * h} viewBox={`0 0 ${cols * size + size} ${rows * h}`} style={{ display: "block" }}>
      <path d={lines.join("")} fill="none" stroke="currentColor" strokeOpacity={opacity} strokeWidth={1} />
    </svg>
  )
}

// ---------- credibility: partners + research facts -----------------------------------------------

export function CredibilityBand({ language }: { language: Language }) {
  const t = useTranslations("landing")
  const partners = partnersFor(language)
  const venues = [...new Set(PUBLICATIONS.map((p) => p.venue))]
  const years = PUBLICATIONS.map((p) => Number(p.year))
  const dataset = PUBLICATIONS.find((p) => p.tag === "Datasets")
  return (
    <Box component="section" aria-labelledby="partners-title" sx={{ py: { xs: 7, md: 9 }, bgcolor: "background.paper", borderTop: "1px solid",
      borderBottom: "1px solid", borderColor: "divider" }}>
      <Container maxWidth="lg">
        <Grid container spacing={{ xs: 5, md: 6 }}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Eyebrow>{t("credibility.title")}</Eyebrow>
            <Typography component="p" sx={{ mt: 2, fontWeight: 800, fontSize: { xs: "1.5rem", md: "1.75rem" }, lineHeight: 1.2, letterSpacing: "-0.02em" }}>
              {t("credibility.papers", { count: PUBLICATIONS.length })}
            </Typography>
            <Typography sx={{ color: "text.secondary", mt: 1 }}>
              {t("credibility.papersSub", { from: Math.min(...years), to: Math.max(...years) })}
            </Typography>
            <Typography component="p" sx={{ ...MONO, fontSize: "0.6875rem", color: "text.secondary", mt: 3 }}>{t("credibility.venues")}</Typography>
            <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.75, mt: 1 }}>
              {venues.map((v) => (
                <Box key={v} component="span" sx={{ px: 1.25, py: 0.5, borderRadius: "6px", border: "1px solid", borderColor: "divider",
                  fontSize: "0.8125rem", fontWeight: 600 }}>{v}</Box>
              ))}
            </Stack>
            {dataset && (
              <Typography sx={{ mt: 3, color: "text.secondary" }}>
                {t("credibility.dataset")}:{" "}
                <Box component="a" href={dataset.url} target="_blank" rel="noopener noreferrer"
                  sx={{ color: "text.primary", fontWeight: 700, textDecorationColor: LINE, textUnderlineOffset: "3px" }}>FakeAVCeleb</Box>
                {" · "}{t("credibility.datasetSub")}
              </Typography>
            )}
            <Box component={Link} href="#research" sx={{ mt: 3, display: "inline-flex", alignItems: "center", gap: 1, minHeight: 44,
              color: "text.primary", fontWeight: 700, textDecoration: "none", "&:hover": { color: ACCENT } }}>
              {t("credibility.all")}<IconArrowRight size={18} aria-hidden />
            </Box>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <Typography id="partners-title" component="h2" sx={{ fontWeight: 700, fontSize: "1.0625rem", mb: 2.5 }}>{t("trust.title")}</Typography>
            <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 1.25,
              gridTemplateColumns: { xs: "repeat(2, 1fr)", sm: "repeat(3, 1fr)", lg: "repeat(4, 1fr)" } }}>
              {partners.map((logo) => (
                <Box component="li" key={logo.src} title={logo.name} sx={{
                  // Logos keep their official colours on a white tile, also in the dark theme.
                  height: 72, bgcolor: "#ffffff", borderRadius: "10px", border: "1px solid", borderColor: "divider",
                  display: "flex", alignItems: "center", justifyContent: "center", px: 2, position: "relative" }}>
                  <Image src={logo.src} alt={logo.name} width={180} height={52}
                    style={{ objectFit: "contain", maxHeight: 44, width: "auto", maxWidth: "100%" }} />
                </Box>
              ))}
            </Box>
          </Grid>
        </Grid>
      </Container>
    </Box>
  )
}

// ---------- product suite -------------------------------------------------------------------------

function Check({ children }: { children: ReactNode }) {
  return (
    <Stack component="li" direction="row" spacing={1.25} sx={{ alignItems: "flex-start" }}>
      <Box sx={{ color: DONE, mt: "3px", display: "flex" }}><IconCheck size={17} stroke={2.4} aria-hidden /></Box>
      <Typography sx={{ color: "text.primary", fontSize: "0.9375rem", lineHeight: 1.5 }}>{children}</Typography>
    </Stack>
  )
}

/** The featured product's visual: the sample head in the evidence view with its region-level findings. */
function DetectVisual() {
  const t = useTranslations("landing")
  const rows: [string, string][] = [
    [t("scan.regions.eyeR.short"), ACCENT],
    [t("scan.regions.mouth.short"), AMBER],
    [t("scan.regions.jaw.short"), AMBER],
  ]
  return (
    <Box sx={{ position: "relative", height: "100%", minHeight: { xs: 300, md: 380 }, borderRadius: "14px", overflow: "hidden",
      bgcolor: "#080f1c", color: "#eef4ff", display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1.1fr 1fr" } }}>
      <Box sx={{ position: "relative", minHeight: { xs: 260, sm: "auto" } }}>
        <Image src="/images/hero/face-evidence.webp" alt="" fill sizes="(max-width: 900px) 100vw, 420px"
          style={{ objectFit: "contain", objectPosition: "center 40%" }} />
      </Box>
      <Box sx={{ p: { xs: 2.5, md: 3 }, display: "flex", flexDirection: "column", justifyContent: "center", gap: 1.5,
        borderLeft: { sm: "1px solid rgb(166 181 203 / .14)" } }}>
        <Typography component="p" sx={{ ...MONO, fontSize: "0.625rem", color: "#a6b5cb" }}>{t("suite.regionFindings")}</Typography>
        {rows.map(([label, color]) => (
          <Stack key={label} direction="row" spacing={1.25} sx={{ alignItems: "center", py: 1, borderBottom: "1px solid rgb(166 181 203 / .14)" }}>
            <Box sx={{ width: 10, height: 10, borderRadius: "3px", bgcolor: color, flexShrink: 0 }} />
            <Typography sx={{ fontSize: "0.9375rem", fontWeight: 600 }}>{label}</Typography>
          </Stack>
        ))}
        <Typography component="p" sx={{ ...MONO, fontSize: "0.625rem", color: "#ffad70", mt: 1 }}>{t("suite.illustrative")}</Typography>
      </Box>
    </Box>
  )
}

function TimelineVisual() {
  const t = useTranslations("landing.suite")
  const marked = new Set([7, 8, 9, 17, 18])
  return (
    <Box aria-hidden>
      <Typography component="p" sx={{ ...MONO, fontSize: "0.625rem", color: "text.secondary", mb: 1.25 }}>{t("timeline")}</Typography>
      <Stack direction="row" sx={{ gap: "3px", height: 40, alignItems: "stretch" }}>
        {Array.from({ length: 24 }, (_, i) => (
          <Box key={i} sx={{ flex: 1, borderRadius: "3px", bgcolor: marked.has(i) ? AMBER : "action.selected",
            opacity: marked.has(i) ? 0.9 : 1, border: "1px solid", borderColor: marked.has(i) ? AMBER : "divider" }} />
        ))}
      </Stack>
      <Stack direction="row" spacing={1} sx={{ mt: 1.25, alignItems: "center" }}>
        <Box sx={{ width: 10, height: 10, borderRadius: "3px", bgcolor: AMBER }} />
        <Typography sx={{ fontSize: "0.8125rem", color: "text.secondary" }}>{t("marked")}</Typography>
      </Stack>
    </Box>
  )
}

function SourcesVisual() {
  const t = useTranslations("landing.suite")
  return (
    <Box aria-hidden>
      <Typography component="p" sx={{ ...MONO, fontSize: "0.625rem", color: "text.secondary", mb: 1 }}>{t("sources")}</Typography>
      {[t("source1"), t("source2"), t("source3")].map((s, i) => (
        <Stack key={s} direction="row" spacing={1.25} sx={{ alignItems: "center", py: 0.75, borderBottom: i < 2 ? "1px solid" : "none", borderColor: "divider" }}>
          <Box component="span" sx={{ fontFamily: "var(--sml-mono)", fontSize: "0.75rem", color: ACCENT, width: 24 }}>[{i + 1}]</Box>
          <Typography sx={{ fontSize: "0.875rem", flex: 1 }}>{s}</Typography>
          <Box sx={{ color: DONE, display: "flex" }}><IconCheck size={16} stroke={2.4} /></Box>
        </Stack>
      ))}
    </Box>
  )
}

function CompareVisual() {
  const t = useTranslations("landing.suite")
  const scene = (edited: boolean) => (
    <Box sx={{ flex: 1, position: "relative", height: 84, borderRadius: "8px", overflow: "hidden",
      background: edited ? "linear-gradient(160deg, #2b3f7a, #6f5bd6 55%, #ffad70)" : "linear-gradient(160deg, #1d2c4a, #3e5f8a 60%, #8fb3c9)" }}>
      <Box sx={{ position: "absolute", left: "18%", bottom: 0, width: "34%", height: "62%", bgcolor: "rgb(8 15 28 / .55)", clipPath: "polygon(50% 0, 100% 100%, 0 100%)" }} />
      <Box sx={{ position: "absolute", right: "14%", top: "18%", width: 18, height: 18, borderRadius: "50%", bgcolor: edited ? "#ffe2c4" : "#dfe9f5" }} />
      <Typography component="span" sx={{ ...MONO, fontSize: "0.5625rem", position: "absolute", left: 8, top: 6, color: "#eef4ff" }}>
        {edited ? t("after") : t("before")}
      </Typography>
    </Box>
  )
  return (
    <Box aria-hidden>
      <Stack direction="row" spacing={0.75}>{scene(false)}{scene(true)}</Stack>
      <Stack direction="row" spacing={1} sx={{ mt: 1.25, alignItems: "center", color: "text.secondary" }}>
        <Box sx={{ color: DONE, display: "flex" }}><IconCheck size={16} stroke={2.4} /></Box>
        <Typography sx={{ fontSize: "0.8125rem" }}>{t("consent")}</Typography>
      </Stack>
    </Box>
  )
}

const MODULES: { key: "longVideo" | "news" | "studio"; icon: Icon; href: string; visual: () => ReactNode }[] = [
  { key: "longVideo", icon: IconBroadcast, href: "/app/long-video", visual: () => <TimelineVisual /> },
  { key: "news", icon: IconNews, href: "/app/news", visual: () => <SourcesVisual /> },
  { key: "studio", icon: IconSparkles, href: "/app/studio", visual: () => <CompareVisual /> },
]

export function ProductSuite() {
  const t = useTranslations("landing")
  const p = useTranslations("landing.products")
  return (
    <Section id="products" labelledBy="products-title">
      <Reveal><SectionHeading id="products-title" eyebrow={p("eyebrow")} title={p("title")} subtitle={p("subtitle")} /></Reveal>
      <Reveal>
        <Box component="article" sx={{ ...PANEL, p: { xs: 2, md: 2.5 }, display: "grid", gap: { xs: 3, md: 4 },
          gridTemplateColumns: { xs: "1fr", md: "1.15fr 1fr" }, alignItems: "stretch" }}>
          <DetectVisual />
          <Box sx={{ p: { xs: 1, md: 2.5 }, display: "flex", flexDirection: "column" }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Box sx={{ display: "flex", color: ACCENT }}><IconPhotoScan size={24} stroke={1.6} aria-hidden /></Box>
              <Typography component="span" sx={{ ...MONO, fontSize: "0.6875rem", color: "text.secondary" }}>
                {t("suite.featured")} · {t("suite.available")}
              </Typography>
            </Stack>
            <Typography variant="h3" component="h3" sx={{ mt: 2, fontWeight: 800, fontSize: { xs: "1.5rem", md: "1.875rem" }, letterSpacing: "-0.02em", lineHeight: 1.15 }}>
              {p("items.detect.title")}
            </Typography>
            <Typography sx={{ ...BODY, mt: 1.5 }}>{p("items.detect.desc")}</Typography>
            <Stack component="ul" spacing={1.25} sx={{ listStyle: "none", p: 0, mt: 2.5, mb: 3 }}>
              {(p.raw("items.detect.points") as string[]).map((pt) => <Check key={pt}>{pt}</Check>)}
            </Stack>
            <Box sx={{ mt: "auto", display: "flex", flexWrap: "wrap", gap: 1.5 }}>
              <Box component="a" href="#trial" sx={{ display: "inline-flex", alignItems: "center", gap: 1, minHeight: 46, px: 2.5,
                borderRadius: "10px", bgcolor: "#4268f6", color: "#fff", fontWeight: 700, textDecoration: "none", "&:hover": { bgcolor: "#3557d8" } }}>
                {t("scan.primary")}<IconArrowRight size={18} aria-hidden />
              </Box>
              <Box component={Link} href="/app/detect" sx={{ display: "inline-flex", alignItems: "center", gap: 1, minHeight: 46, px: 1,
                color: "text.primary", fontWeight: 700, textDecoration: "none", "&:hover": { color: ACCENT } }}>
                {p("learnMore")}<IconArrowRight size={18} aria-hidden />
              </Box>
            </Box>
          </Box>
        </Box>
      </Reveal>
      <Grid container spacing={2.5} sx={{ mt: 0.5 }}>
        {MODULES.map(({ key, icon: ModuleIcon, href, visual }, i) => (
          <Grid key={key} size={{ xs: 12, md: 4 }}>
            <Reveal delay={i * 60}>
              <Box component="article" sx={{ ...PANEL, p: 3, height: "100%", display: "flex", flexDirection: "column", gap: 2 }}>
                <Stack direction="row" spacing={1.25} sx={{ alignItems: "center" }}>
                  <Box sx={{ display: "flex", color: ACCENT }}><ModuleIcon size={22} stroke={1.6} aria-hidden /></Box>
                  <Typography variant="h5" component="h3" sx={{ fontWeight: 700, fontSize: "1.125rem" }}>{p(`items.${key}.title`)}</Typography>
                </Stack>
                <Typography sx={{ color: "text.secondary", fontSize: "0.9375rem", lineHeight: 1.6 }}>{p(`items.${key}.desc`)}</Typography>
                <Box sx={{ p: 2, borderRadius: "10px", bgcolor: "background.default", border: "1px solid", borderColor: "divider" }}>{visual()}</Box>
                <Stack component="ul" spacing={1} sx={{ listStyle: "none", p: 0, m: 0 }}>
                  {(p.raw(`items.${key}.points`) as string[]).map((pt) => <Check key={pt}>{pt}</Check>)}
                </Stack>
                <Box component={Link} href={href} aria-label={`${p("learnMore")}: ${p(`items.${key}.title`)}`}
                  sx={{ mt: "auto", display: "inline-flex", alignItems: "center", gap: 1, minHeight: 44, color: "text.primary",
                    fontWeight: 700, textDecoration: "none", "&:hover": { color: ACCENT } }}>
                  {p("learnMore")}<IconArrowRight size={18} aria-hidden />
                </Box>
              </Box>
            </Reveal>
          </Grid>
        ))}
      </Grid>
    </Section>
  )
}

// ---------- workflow: Upload → Analyse → Explain ------------------------------------------------

export function Workflow() {
  const t = useTranslations("landing.how")
  const steps = t.raw("steps") as { title: string; body: string }[]
  const icons = [IconUpload, IconScan, IconReportAnalytics]
  return (
    <Section id="how" raised labelledBy="how-title">
      <Reveal><SectionHeading id="how-title" eyebrow={t("eyebrow")} title={t("title")} /></Reveal>
      <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: { xs: 4, md: 3 },
        gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" }, position: "relative" }}>
        {/* The scan line that connects the steps (the hero's band, laid flat). */}
        <Box aria-hidden sx={{ display: { xs: "none", md: "block" }, position: "absolute", left: "8%", right: "8%", top: 27, height: "1px",
          background: `linear-gradient(90deg, transparent, ${ACCENT} 12%, ${ACCENT} 88%, transparent)`, opacity: 0.55 }} />
        {steps.map((step, i) => {
          const StepIcon = icons[i]
          return (
            <Box component="li" key={step.title} sx={{ position: "relative" }}>
              <Reveal delay={i * 80}>
                <Box sx={{ position: "relative", width: 56, height: 56, display: "grid", placeItems: "center", color: i === 2 ? DONE : ACCENT,
                  bgcolor: "background.paper" }}>
                  <svg aria-hidden width="56" height="56" viewBox="0 0 56 56" style={{ position: "absolute", inset: 0 }}>
                    <path d="M28 3 L51 16 L51 40 L28 53 L5 40 L5 16 Z" fill="none" stroke="currentColor" strokeOpacity=".55" />
                  </svg>
                  <StepIcon size={24} stroke={1.6} aria-hidden />
                </Box>
                <Typography component="p" sx={{ ...MONO, color: "text.secondary", mt: 2.5 }}>{String(i + 1).padStart(2, "0")}</Typography>
                <Typography variant="h5" component="h3" sx={{ mt: 0.75, fontWeight: 700, fontSize: "1.25rem" }}>{step.title}</Typography>
                <Typography sx={{ ...BODY, mt: 1, maxWidth: 360 }}>{step.body}</Typography>
              </Reveal>
            </Box>
          )
        })}
      </Box>
    </Section>
  )
}

// ---------- benefits ------------------------------------------------------------------------------

export function Benefits() {
  const t = useTranslations("landing")
  const items = t.raw("features.items") as { title: string; body: string }[]
  const icons = [IconEye, IconCertificate, IconBroadcast, IconApi, IconLock, IconLanguage]
  return (
    <Section labelledBy="benefits-title">
      <Reveal><SectionHeading id="benefits-title" eyebrow={t("benefits.eyebrow")} title={t("features.title")} /></Reveal>
      <Reveal>
        <Box component="ul" sx={{ ...PANEL, listStyle: "none", m: 0, p: 0, overflow: "hidden", display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" } }}>
          {items.map((item, i) => {
            const ItemIcon = icons[i]
            return (
              <Box component="li" key={item.title} sx={{ p: { xs: 3, md: 3.5 }, display: "flex", gap: 2,
                borderTop: "1px solid", borderLeft: "1px solid", borderColor: "divider", mt: "-1px", ml: "-1px" }}>
                <Box sx={{ color: ACCENT, display: "flex", mt: "2px" }}><ItemIcon size={22} stroke={1.6} aria-hidden /></Box>
                <Box>
                  <Typography variant="h6" component="h3" sx={{ fontWeight: 700, fontSize: "1.0625rem" }}>{item.title}</Typography>
                  <Typography sx={{ color: "text.secondary", mt: 0.75, fontSize: "0.9375rem", lineHeight: 1.6 }}>{item.body}</Typography>
                </Box>
              </Box>
            )
          })}
        </Box>
      </Reveal>
    </Section>
  )
}

// ---------- research ------------------------------------------------------------------------------

/** One visual language for the three research threads: the same lattice, a different motif. */
function ResearchMotif({ kind }: { kind: 0 | 1 | 2 }) {
  return (
    <Box aria-hidden sx={{ position: "relative", height: 132, overflow: "hidden", color: ACCENT, bgcolor: "background.default",
      borderBottom: "1px solid", borderColor: "divider" }}>
      <Box sx={{ position: "absolute", inset: 0, opacity: 0.8, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Lattice cols={9} rows={5} size={34} opacity={0.18} />
      </Box>
      <svg width="100%" height="132" viewBox="0 0 320 132" preserveAspectRatio="xMidYMid meet" style={{ position: "relative" }}>
        {kind === 0 && (
          // Detect: a face outline under a scan band.
          <g fill="none" stroke="currentColor">
            <path d="M160 22c-30 0-46 22-46 50 0 30 20 44 46 44s46-14 46-44c0-28-16-50-46-50z" strokeOpacity=".7" />
            <path d="M140 64h12M168 64h12M152 90c6 4 10 4 16 0" strokeOpacity=".7" />
            <path d="M96 76h128" stroke="var(--landing-accent)" strokeWidth="2" />
            <circle cx="146" cy="64" r="2.5" fill="currentColor" />
            <circle cx="174" cy="64" r="2.5" fill="currentColor" />
          </g>
        )}
        {kind === 1 && (
          // Prevent: a shield over the lattice.
          <g fill="none" stroke="currentColor">
            <path d="M160 18l40 14v28c0 26-18 44-40 52-22-8-40-26-40-52V32z" strokeOpacity=".75" />
            <path d="M144 66l11 11 22-24" stroke="var(--landing-done)" strokeWidth="2" />
          </g>
        )}
        {kind === 2 && (
          // Propagation: a cascade across a network.
          <g stroke="currentColor" fill="none">
            {[[100, 70, 140, 40], [100, 70, 140, 100], [140, 40, 190, 30], [140, 40, 190, 64], [140, 100, 190, 96], [140, 100, 190, 120],
              [190, 30, 236, 44], [190, 64, 236, 44], [190, 96, 236, 92]].map(([x1, y1, x2, y2], i) => (
              <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} strokeOpacity=".6" />
            ))}
            {[[100, 70], [140, 40], [140, 100], [190, 30], [190, 64], [190, 96], [190, 120], [236, 44], [236, 92]].map(([cx, cy], i) => (
              <circle key={i} cx={cx} cy={cy} r={i === 0 ? 5 : 3.5} fill={i === 0 ? "var(--landing-amber)" : "currentColor"} stroke="none" />
            ))}
          </g>
        )}
      </svg>
    </Box>
  )
}

export function Research({ language }: { language: Language }) {
  const t = useTranslations("landing")
  const areas = dashTranslations[language].research.areas
  return (
    <Section id="research" raised labelledBy="research-title">
      <Reveal><SectionHeading id="research-title" eyebrow={t("research.eyebrow")} title={t("research.title")} subtitle={t("research.subtitle")} /></Reveal>
      <Grid container spacing={2.5}>
        {areas.map((area, i) => (
          <Grid key={area.title} size={{ xs: 12, md: 4 }}>
            <Reveal delay={i * 60}>
              <Box component="article" sx={{ ...PANEL, bgcolor: "background.default", overflow: "hidden", height: "100%" }}>
                <ResearchMotif kind={i as 0 | 1 | 2} />
                <Box sx={{ p: 3 }}>
                  <Typography component="p" sx={{ ...MONO, fontSize: "0.625rem", color: i === 0 ? DONE : "text.secondary" }}>
                    {i === 0 ? t("researchV2.inProduct") : t("researchV2.direction")}
                  </Typography>
                  <Typography variant="h5" component="h3" sx={{ mt: 1.25, fontWeight: 700, fontSize: "1.1875rem" }}>{area.title}</Typography>
                  <Typography sx={{ color: "text.secondary", mt: 1.25, fontSize: "0.9375rem", lineHeight: 1.6 }}>{area.desc}</Typography>
                </Box>
              </Box>
            </Reveal>
          </Grid>
        ))}
      </Grid>
      <Typography sx={{ color: "text.secondary", mt: 2.5, fontSize: "0.875rem" }}>{t("researchV2.directionNote")}</Typography>

      <Reveal>
        <Box sx={{ mt: { xs: 7, md: 9 } }}>
          <Typography variant="h4" component="h3" sx={{ mb: 2.5, fontWeight: 700, fontSize: "1.375rem" }}>{t("research.publications")}</Typography>
          <Box component="ol" sx={{ ...PANEL, listStyle: "none", m: 0, p: 0, overflow: "hidden" }}>
            {PUBLICATIONS.map((pub, i) => (
              <Box component="li" key={pub.title} sx={{ borderTop: i ? "1px solid" : "none", borderColor: "divider" }}>
                <Box component="a" href={pub.url} target="_blank" rel="noopener noreferrer"
                  sx={{ px: { xs: 2.5, md: 3 }, py: 2, display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: { xs: 0.75, sm: 3 },
                    alignItems: { sm: "center" }, color: "text.primary", textDecoration: "none", minHeight: 56,
                    "&:hover": { bgcolor: "action.hover" }, "&:hover .pub-title": { color: ACCENT } }}>
                  <Typography component="span" sx={{ fontFamily: "var(--sml-mono)", fontSize: "0.8125rem", color: "text.secondary", width: 44, flexShrink: 0 }}>{pub.year}</Typography>
                  <Typography component="span" className="pub-title" sx={{ fontWeight: 600, flex: 1, fontSize: "0.9375rem", lineHeight: 1.45, transition: "color .15s" }}>
                    {pub.title}
                    <Box component="span" sx={{ display: "inline-flex", verticalAlign: "-2px", ml: 0.75, color: "text.secondary" }}>
                      <IconArrowUpRight size={15} aria-label={t("researchV2.open")} />
                    </Box>
                  </Typography>
                  <Stack direction="row" spacing={0.75} sx={{ flexShrink: 0 }}>
                    <Box component="span" sx={{ px: 1, py: 0.25, borderRadius: "6px", border: "1px solid", borderColor: "divider", fontSize: "0.75rem", fontWeight: 700 }}>{pub.venue}</Box>
                    {pub.tag !== "Full" && (
                      <Box component="span" sx={{ px: 1, py: 0.25, borderRadius: "6px", fontSize: "0.75rem", color: "text.secondary", bgcolor: "action.selected" }}>
                        {pub.tag === "Datasets" ? t("researchV2.dataset") : t("researchV2.workshop")}
                      </Box>
                    )}
                  </Stack>
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      </Reveal>
    </Section>
  )
}

// ---------- final CTA, about, contact ------------------------------------------------------------

export function FinalCta() {
  const t = useTranslations("landing.cta")
  return (
    <Box component="section" aria-labelledby="cta-title" sx={{ py: { xs: 8, md: 12 } }}>
      <Container maxWidth="lg">
        <Reveal>
          <Box sx={{ position: "relative", overflow: "hidden", borderRadius: "20px", px: { xs: 3, md: 8 }, py: { xs: 6, md: 8 },
            bgcolor: "#111d30", color: "#eef4ff", border: "1px solid rgb(166 181 203 / .16)" }}>
            <Box aria-hidden sx={{ position: "absolute", right: -40, top: -10, color: "#39d9e6", opacity: 0.9,
              maskImage: "linear-gradient(90deg, transparent, #000 60%)", WebkitMaskImage: "linear-gradient(90deg, transparent, #000 60%)" }}>
              <Lattice cols={12} rows={8} size={44} opacity={0.16} />
            </Box>
            <Box sx={{ position: "relative", maxWidth: 620 }}>
              <Typography id="cta-title" variant="h2" component="h2" sx={{ fontWeight: 800, letterSpacing: "-0.025em", fontSize: { xs: "2rem", md: "2.75rem" }, lineHeight: 1.1 }}>
                {t("title")}
              </Typography>
              <Typography sx={{ mt: 2, fontSize: { xs: "1rem", md: "1.125rem" }, lineHeight: 1.65, color: "#a6b5cb" }}>{t("subtitle")}</Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 4, alignItems: { sm: "center" } }}>
                <Box component={Link} href="/signup" sx={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 1,
                  minHeight: 50, px: 3, borderRadius: "10px", bgcolor: "#4268f6", color: "#fff", fontWeight: 700, fontSize: "1rem",
                  textDecoration: "none", "&:hover": { bgcolor: "#3557d8" }, "&:focus-visible": { outline: "2px solid #39d9e6", outlineOffset: 3 } }}>
                  {t("primary")}<IconArrowRight size={18} aria-hidden />
                </Box>
                <Box component={Link} href="/pricing" sx={{ color: "#eef4ff", fontWeight: 600, minHeight: 44, display: "inline-flex", alignItems: "center",
                  textUnderlineOffset: "4px", textDecorationColor: "rgb(166 181 203 / .5)", "&:hover": { color: "#39d9e6" } }}>
                  {t("secondary")}
                </Box>
              </Stack>
            </Box>
          </Box>
        </Reveal>
      </Container>
    </Box>
  )
}

export function AboutAndContact({ language }: { language: Language }) {
  const t = useTranslations("landing")
  const about = dashTranslations[language].about
  const contact = dashTranslations[language].contact
  return (
    <Section id="about" raised labelledBy="about-title">
      <Grid container spacing={{ xs: 6, md: 10 }}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Reveal>
            <Eyebrow>{t("about.eyebrow")}</Eyebrow>
            <Typography id="about-title" variant="h2" component="h2" sx={{ mt: 1.75, fontWeight: 800, letterSpacing: "-0.02em",
              fontSize: { xs: "1.75rem", md: "2.25rem" }, lineHeight: 1.2, textWrap: "balance" }}>
              {about.headingPrefix} <Box component="span" sx={{ color: ACCENT }}>{about.university}</Box>, {about.headingSuffix}
            </Typography>
            <Typography sx={{ ...BODY, mt: 2.5 }}>{about.body}</Typography>
            <Box component="dl" sx={{ mt: 4, mb: 0, display: "grid", gridTemplateColumns: { xs: "repeat(2, 1fr)", sm: "repeat(3, 1fr)" },
              borderTop: "1px solid", borderColor: "divider" }}>
              {about.facts.map(([k, v]) => (
                <Box key={k} sx={{ py: 2, pr: 2, borderBottom: "1px solid", borderColor: "divider" }}>
                  <Typography component="dt" sx={{ ...MONO, fontSize: "0.625rem", color: "text.secondary" }}>{k}</Typography>
                  <Typography component="dd" sx={{ m: 0, mt: 0.75, fontWeight: 700 }}>{v}</Typography>
                </Box>
              ))}
            </Box>
          </Reveal>
        </Grid>
        <Grid size={{ xs: 12, md: 5 }} id="contact" sx={{ scrollMarginTop: 72 }}>
          <Reveal delay={80}>
            <Box sx={{ ...PANEL, bgcolor: "background.default", p: { xs: 3, md: 4 } }}>
              <Eyebrow>{t("contact.eyebrow")}</Eyebrow>
              <Typography variant="h3" component="h2" sx={{ mt: 1.5, fontWeight: 800, fontSize: "1.75rem" }}>{t("contact.title")}</Typography>
              <Typography sx={{ color: "text.secondary", mt: 1.5, lineHeight: 1.6 }}>{contact.subtitle}</Typography>
              <Stack component="dl" spacing={2.5} sx={{ mt: 3.5, mb: 0 }}>
                <Stack direction="row" spacing={2} sx={{ alignItems: "flex-start" }}>
                  <Box sx={{ color: ACCENT, display: "flex", mt: "2px" }}><IconMail size={22} stroke={1.6} aria-hidden /></Box>
                  <Box>
                    <Typography component="dt" sx={{ ...MONO, fontSize: "0.625rem", color: "text.secondary" }}>{t("contact.email")}</Typography>
                    <Typography component="dd" sx={{ m: 0, mt: 0.5 }}>
                      <Box component="a" href={`mailto:${CONTACT_EMAIL}`} sx={{ fontWeight: 700, color: "text.primary", textUnderlineOffset: "3px",
                        textDecorationColor: LINE, "&:hover": { color: ACCENT } }}>{CONTACT_EMAIL}</Box>
                    </Typography>
                  </Box>
                </Stack>
                <Stack direction="row" spacing={2} sx={{ alignItems: "flex-start" }}>
                  <Box sx={{ color: ACCENT, display: "flex", mt: "2px" }}><IconMapPin size={22} stroke={1.6} aria-hidden /></Box>
                  <Box>
                    <Typography component="dt" sx={{ ...MONO, fontSize: "0.625rem", color: "text.secondary" }}>{t("contact.visit")}</Typography>
                    <Typography component="dd" sx={{ m: 0, mt: 0.5, fontWeight: 700 }}>{contact.location}</Typography>
                    <Typography sx={{ color: "text.secondary", fontSize: "0.875rem" }}>{contact.address}</Typography>
                  </Box>
                </Stack>
              </Stack>
              <Box component="a" href={`mailto:${CONTACT_EMAIL}`} sx={{ mt: 4, display: "flex", alignItems: "center", justifyContent: "center", gap: 1,
                minHeight: 48, borderRadius: "10px", bgcolor: "#4268f6", color: "#fff", fontWeight: 700, textDecoration: "none",
                "&:hover": { bgcolor: "#3557d8" } }}>
                {t("contact.write")}<IconArrowRight size={18} aria-hidden />
              </Box>
            </Box>
          </Reveal>
        </Grid>
      </Grid>
    </Section>
  )
}

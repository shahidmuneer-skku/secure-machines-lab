"use client"

import Avatar from "@mui/material/Avatar"
import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Card from "@mui/material/Card"
import CardContent from "@mui/material/CardContent"
import Chip from "@mui/material/Chip"
import Container from "@mui/material/Container"
import Grid from "@mui/material/Grid"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import {
  IconApi, IconArrowRight, IconBroadcast, IconCertificate, IconCheck, IconEye, IconLanguage, IconLock, IconMail,
  IconMapPin, IconNews, IconPhotoScan, IconReportAnalytics, IconScan, IconSparkles, IconUpload, type Icon,
} from "@tabler/icons-react"
import Image from "next/image"
import Link from "next/link"
import { useTranslations } from "next-intl"
import type { ReactNode } from "react"

import { dashTranslations, type Language } from "@/lib/marketing/i18n"
import { PUBLICATIONS } from "@/lib/marketing/publications"
import { watermarkGalleryImages } from "@/lib/marketing/watermark-gallery.generated"

const CONTACT_EMAIL = "woo@securemachineslab.com"

/** Body copy on the landing page: a size up from the app's 14 px, for reading at a distance. */
const BODY = { color: "text.secondary", fontSize: "0.9375rem", lineHeight: 1.65 } as const

function SectionHeading({ eyebrow, title, subtitle, center = true }: { eyebrow: string; title: ReactNode; subtitle?: ReactNode; center?: boolean }) {
  return (
    <Box sx={{ textAlign: center ? "center" : "left", maxWidth: center ? 720 : "none", mx: center ? "auto" : 0, mb: { xs: 5, md: 7 } }}>
      <Typography variant="overline" sx={{ color: "primary.main" }}>{eyebrow}</Typography>
      <Typography variant="h2" component="h2" sx={{ mt: 1, fontWeight: 800, fontSize: { xs: "1.75rem", md: "2.25rem" }, lineHeight: 1.2 }}>{title}</Typography>
      {subtitle && <Typography sx={{ mt: 2, color: "text.secondary", fontSize: { xs: "1rem", md: "1.0625rem" }, lineHeight: 1.7 }}>{subtitle}</Typography>}
    </Box>
  )
}

function Section({ id, children, tinted = false }: { id?: string; children: ReactNode; tinted?: boolean }) {
  return (
    <Box component="section" id={id} sx={{ py: { xs: 8, md: 11 }, scrollMarginTop: 72, bgcolor: tinted ? "background.paper" : "transparent",
      borderTop: tinted ? "1px solid" : "none", borderBottom: tinted ? "1px solid" : "none", borderColor: "divider" }}>
      <Container maxWidth="lg">{children}</Container>
    </Box>
  )
}

// --- trust: collaborator logos + numbers -----------------------------------------------------

export function TrustStrip({ language }: { language: Language }) {
  const t = useTranslations("landing")
  const logos = [...watermarkGalleryImages.common, ...(language === "ko" ? watermarkGalleryImages.korean : watermarkGalleryImages.english)]
  const stats = t.raw("stats") as { value: string; label: string; sub: string }[]
  return (
    <Box component="section" sx={{ py: { xs: 6, md: 8 }, bgcolor: "background.paper", borderTop: "1px solid", borderBottom: "1px solid", borderColor: "divider" }}>
      <Container maxWidth="lg">
        <Typography sx={{ ...BODY, textAlign: "center", fontWeight: 600, mb: 4 }}>{t("trust.title")}</Typography>
        <Grid container spacing={2} sx={{ justifyContent: "center" }}>
          {logos.map((logo) => (
            <Grid key={logo.src} size={{ xs: 6, sm: 4, md: 2 }}>
              {/* Logos keep their own colours on a white tile, also in the dark theme. */}
              <Box sx={{ height: 76, bgcolor: "#ffffff", border: "1px solid", borderColor: "divider", borderRadius: "9px",
                display: "flex", alignItems: "center", justifyContent: "center", px: 1.5, position: "relative" }}>
                <Image src={logo.src} alt={logo.alt} width={160} height={56} style={{ objectFit: "contain", maxHeight: 52, width: "auto" }} />
              </Box>
            </Grid>
          ))}
        </Grid>
        <Grid container spacing={3} sx={{ mt: { xs: 5, md: 7 } }}>
          {stats.map((s) => (
            <Grid key={s.label} size={{ xs: 6, md: 3 }} sx={{ textAlign: "center" }}>
              <Typography sx={{ fontSize: { xs: "2rem", md: "2.5rem" }, fontWeight: 800, color: "primary.main", lineHeight: 1.1 }}>{s.value}</Typography>
              <Typography variant="h6" component="p" sx={{ mt: 1 }}>{s.label}</Typography>
              <Typography variant="subtitle2" sx={{ color: "text.secondary" }}>{s.sub}</Typography>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  )
}

// --- products ---------------------------------------------------------------------------------

const PRODUCTS: { key: "detect" | "longVideo" | "news" | "studio"; icon: Icon; tone: string; href: string }[] = [
  { key: "detect", icon: IconPhotoScan, tone: "primary", href: "/app/detect" },
  { key: "longVideo", icon: IconBroadcast, tone: "secondary", href: "/app/long-video" },
  { key: "news", icon: IconNews, tone: "success", href: "/app/news" },
  { key: "studio", icon: IconSparkles, tone: "warning", href: "/app/studio" },
]

export function Products() {
  const t = useTranslations("landing.products")
  return (
    <Section id="products">
      <SectionHeading eyebrow={t("eyebrow")} title={t("title")} subtitle={t("subtitle")} />
      <Grid container spacing={3}>
        {PRODUCTS.map(({ key, icon: ItemIcon, tone, href }) => (
          <Grid key={key} size={{ xs: 12, sm: 6, lg: 3 }}>
            <Card className="hud-card-hover" sx={{ height: "100%" }}>
              <CardContent sx={{ p: 3.5, height: "100%", display: "flex", flexDirection: "column", "&:last-child": { pb: 3.5 } }}>
                <Avatar variant="rounded" sx={{ width: 52, height: 52, borderRadius: "12px", bgcolor: `${tone}.light`, color: `${tone}.main` }}>
                  <ItemIcon size={26} stroke={1.6} />
                </Avatar>
                <Typography variant="h5" component="h3" sx={{ mt: 2.5 }}>{t(`items.${key}.title`)}</Typography>
                <Typography sx={{ ...BODY, mt: 1.25 }}>{t(`items.${key}.desc`)}</Typography>
                <Stack spacing={1} sx={{ mt: 2.5, mb: 3 }}>
                  {(t.raw(`items.${key}.points`) as string[]).map((p) => (
                    <Stack key={p} direction="row" spacing={1} sx={{ alignItems: "flex-start" }}>
                      <Box sx={{ color: "success.main", mt: "2px", display: "flex" }}><IconCheck size={17} stroke={2.4} /></Box>
                      <Typography sx={{ color: "text.primary", fontSize: "0.9rem", lineHeight: 1.5 }}>{p}</Typography>
                    </Stack>
                  ))}
                </Stack>
                <Button component={Link} href={href} endIcon={<IconArrowRight size={17} />} sx={{ mt: "auto", alignSelf: "flex-start", px: 0 }}>
                  {t("learnMore")}
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Section>
  )
}

// --- how it works -------------------------------------------------------------------------------

export function HowItWorks() {
  const t = useTranslations("landing.how")
  const steps = t.raw("steps") as { title: string; body: string }[]
  const icons = [IconUpload, IconScan, IconReportAnalytics]
  return (
    <Section id="how" tinted>
      <SectionHeading eyebrow={t("eyebrow")} title={t("title")} />
      <Grid container spacing={{ xs: 4, md: 5 }}>
        {steps.map((step, i) => {
          const StepIcon = icons[i]
          return (
            <Grid key={step.title} size={{ xs: 12, md: 4 }} sx={{ position: "relative", textAlign: "center" }}>
              {i < steps.length - 1 && (
                <Box aria-hidden sx={{ display: { xs: "none", md: "block" }, position: "absolute", top: 36, left: "calc(50% + 52px)",
                  right: "calc(-50% + 52px)", borderTop: "2px dashed", borderColor: "divider" }} />
              )}
              <Box sx={{ position: "relative", display: "inline-flex", mb: 2.5 }}>
                <Avatar sx={{ width: 72, height: 72, bgcolor: "primary.light", color: "primary.main" }}><StepIcon size={32} stroke={1.6} /></Avatar>
                <Avatar sx={{ position: "absolute", top: -4, right: -6, width: 28, height: 28, bgcolor: "#426de8", color: "#fff",
                  fontSize: "0.8rem", fontWeight: 800, border: "3px solid", borderColor: "background.paper" }}>{i + 1}</Avatar>
              </Box>
              <Typography variant="h5" component="h3">{step.title}</Typography>
              <Typography sx={{ ...BODY, mt: 1.25, maxWidth: 340, mx: "auto" }}>{step.body}</Typography>
            </Grid>
          )
        })}
      </Grid>
    </Section>
  )
}

// --- features -----------------------------------------------------------------------------------

export function Features() {
  const t = useTranslations("landing.features")
  const items = t.raw("items") as { title: string; body: string }[]
  const icons = [IconEye, IconCertificate, IconBroadcast, IconApi, IconLock, IconLanguage]
  return (
    <Section>
      <SectionHeading eyebrow={t("eyebrow")} title={t("title")} />
      <Grid container spacing={3}>
        {items.map((item, i) => {
          const ItemIcon = icons[i]
          return (
            <Grid key={item.title} size={{ xs: 12, sm: 6, md: 4 }}>
              <Stack direction="row" spacing={2} sx={{ p: 3, height: "100%", borderRadius: "9px", bgcolor: "background.paper",
                border: "1px solid", borderColor: "divider" }}>
                <Avatar variant="rounded" sx={{ width: 44, height: 44, borderRadius: "10px", bgcolor: "primary.light", color: "primary.main" }}>
                  <ItemIcon size={22} stroke={1.7} />
                </Avatar>
                <Box>
                  <Typography variant="h6" component="h3">{item.title}</Typography>
                  <Typography sx={{ ...BODY, mt: 0.75 }}>{item.body}</Typography>
                </Box>
              </Stack>
            </Grid>
          )
        })}
      </Grid>
    </Section>
  )
}

// --- research -----------------------------------------------------------------------------------

const RESEARCH_IMAGES = ["/images/research-detection.png", "/images/research-digital.png", "/images/research-auc.png"]

export function Research({ language }: { language: Language }) {
  const t = useTranslations("landing.research")
  const areas = dashTranslations[language].research.areas
  const tags = dashTranslations[language].research.publications.tags
  return (
    <Section id="research" tinted>
      <SectionHeading eyebrow={t("eyebrow")} title={t("title")} subtitle={t("subtitle")} />
      <Grid container spacing={3}>
        {areas.map((area, i) => (
          <Grid key={area.title} size={{ xs: 12, md: 4 }}>
            <Card sx={{ height: "100%", overflow: "hidden" }}>
              <Box sx={{ position: "relative", aspectRatio: "16 / 9", bgcolor: "#0b1a33" }}>
                <Image src={RESEARCH_IMAGES[i]} alt="" fill sizes="(max-width: 900px) 100vw, 380px" style={{ objectFit: "cover" }} />
              </Box>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h5" component="h3">{area.title}</Typography>
                <Typography sx={{ ...BODY, mt: 1.25 }}>{area.desc}</Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                  {area.venues.map((v) => <Chip key={v} size="small" label={v} sx={{ bgcolor: "primary.light", color: "primary.main" }} />)}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Box sx={{ mt: { xs: 6, md: 8 } }}>
        <Typography variant="h4" component="h3" sx={{ mb: 2.5 }}>{t("publications")}</Typography>
        <Card>
          {PUBLICATIONS.map((p, i) => (
            <Stack key={p.title} direction={{ xs: "column", sm: "row" }} spacing={{ xs: 0.5, sm: 3 }}
              sx={{ px: 3, py: 2, alignItems: { sm: "center" }, borderTop: i ? "1px solid" : "none", borderColor: "divider" }}>
              <Typography variant="subtitle2" sx={{ color: "text.secondary", fontWeight: 700, width: 48, flexShrink: 0 }}>{p.year}</Typography>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, flex: 1, color: "text.primary" }}>{p.title}</Typography>
              <Stack direction="row" spacing={1} sx={{ flexShrink: 0 }}>
                <Chip size="small" label={p.venue} sx={{ fontWeight: 700, bgcolor: "secondary.light", color: "secondary.main" }} />
                {p.tag !== "Full" && <Chip size="small" variant="outlined" label={p.tag === "Datasets" ? tags.datasets : tags.workshop} />}
              </Stack>
            </Stack>
          ))}
        </Card>
      </Box>
    </Section>
  )
}

// --- CTA, about, contact -------------------------------------------------------------------------

export function CallToAction() {
  const t = useTranslations("landing.cta")
  return (
    <Box component="section" sx={{ py: { xs: 8, md: 10 } }}>
      <Container maxWidth="lg">
        <Box sx={{ position: "relative", overflow: "hidden", borderRadius: "16px", px: { xs: 3, md: 8 }, py: { xs: 6, md: 8 }, textAlign: "center",
          color: "#fff", background: "linear-gradient(120deg, #3557c7 0%, #426de8 45%, #1f8fd6 100%)" }}>
          <Box aria-hidden sx={{ position: "absolute", width: 360, height: 360, borderRadius: "50%", bgcolor: "rgba(255,255,255,.08)", top: -160, right: -80 }} />
          <Box aria-hidden sx={{ position: "absolute", width: 240, height: 240, borderRadius: "50%", bgcolor: "rgba(255,255,255,.06)", bottom: -120, left: -60 }} />
          <Typography variant="h2" component="h2" sx={{ position: "relative", fontWeight: 800, fontSize: { xs: "1.75rem", md: "2.4rem" } }}>{t("title")}</Typography>
          <Typography sx={{ position: "relative", mt: 2, fontSize: "1.0625rem", opacity: 0.95, maxWidth: 620, mx: "auto", lineHeight: 1.7 }}>{t("subtitle")}</Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ position: "relative", mt: 4, justifyContent: "center" }}>
            <Button component={Link} href="/signup" size="large" variant="contained"
              sx={{ bgcolor: "#fff !important", color: "#2a3547 !important", px: 3.5, py: 1.4, fontSize: "1rem", "&:hover": { bgcolor: "#ecf2ff !important" } }}>
              {t("primary")}
            </Button>
            <Button component={Link} href="/pricing" size="large" variant="outlined"
              sx={{ color: "#fff", borderColor: "rgba(255,255,255,.7)", px: 3.5, py: 1.4, fontSize: "1rem", "&:hover": { borderColor: "#fff", bgcolor: "rgba(255,255,255,.08)" } }}>
              {t("secondary")}
            </Button>
          </Stack>
        </Box>
      </Container>
    </Box>
  )
}

export function AboutAndContact({ language }: { language: Language }) {
  const t = useTranslations("landing")
  const about = dashTranslations[language].about
  const contact = dashTranslations[language].contact
  return (
    <Section id="about" tinted>
      <Grid container spacing={{ xs: 5, md: 8 }}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Typography variant="overline" sx={{ color: "primary.main" }}>{t("about.eyebrow")}</Typography>
          <Typography variant="h2" component="h2" sx={{ mt: 1, fontWeight: 800, fontSize: { xs: "1.75rem", md: "2.25rem" }, lineHeight: 1.25 }}>
            {about.headingPrefix}{" "}
            <Box component="span" sx={{ color: "primary.main" }}>{about.university}</Box>, {about.headingSuffix}
          </Typography>
          <Typography sx={{ mt: 2.5, color: "text.secondary", fontSize: "1.0625rem", lineHeight: 1.75 }}>{about.body}</Typography>
          <Grid container spacing={2} sx={{ mt: 3 }}>
            {about.facts.map(([k, v]) => (
              <Grid key={k} size={{ xs: 6, sm: 4 }}>
                <Box sx={{ p: 2, borderRadius: "9px", bgcolor: "primary.light", height: "100%" }}>
                  <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>{k}</Typography>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 0.5 }}>{v}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Grid>
        <Grid size={{ xs: 12, md: 5 }} id="contact" sx={{ scrollMarginTop: 72 }}>
          <Card>
            <CardContent sx={{ p: { xs: 3, md: 4 } }}>
              <Typography variant="overline" sx={{ color: "primary.main" }}>{t("contact.eyebrow")}</Typography>
              <Typography variant="h3" component="h2" sx={{ mt: 1, fontWeight: 800 }}>{t("contact.title")}</Typography>
              <Typography sx={{ ...BODY, mt: 1.5 }}>{contact.subtitle}</Typography>
              <Stack spacing={2.5} sx={{ mt: 3.5 }}>
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <Avatar variant="rounded" sx={{ bgcolor: "primary.light", color: "primary.main", borderRadius: "10px" }}><IconMail size={22} /></Avatar>
                  <Box>
                    <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>{t("contact.email")}</Typography>
                    <Typography component="a" href={`mailto:${CONTACT_EMAIL}`} variant="subtitle1"
                      sx={{ fontWeight: 700, color: "text.primary", textDecoration: "none", "&:hover": { color: "primary.main" } }}>{CONTACT_EMAIL}</Typography>
                  </Box>
                </Stack>
                <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
                  <Avatar variant="rounded" sx={{ bgcolor: "primary.light", color: "primary.main", borderRadius: "10px" }}><IconMapPin size={22} /></Avatar>
                  <Box>
                    <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>{t("contact.visit")}</Typography>
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{contact.location}</Typography>
                    <Typography variant="body2" sx={{ color: "text.secondary" }}>{contact.address}</Typography>
                  </Box>
                </Stack>
              </Stack>
              <Button component="a" href={`mailto:${CONTACT_EMAIL}`} variant="contained" fullWidth size="large"
                endIcon={<IconArrowRight size={18} />} sx={{ mt: 4 }}>{t("contact.write")}</Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Section>
  )
}

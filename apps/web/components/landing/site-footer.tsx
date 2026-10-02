"use client"

import Box from "@mui/material/Box"
import Container from "@mui/material/Container"
import Divider from "@mui/material/Divider"
import Grid from "@mui/material/Grid"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import { IconMail, IconMapPin } from "@tabler/icons-react"
import Link from "next/link"
import { useTranslations } from "next-intl"

import { Logo } from "@/components/brand/logo"
import { COMPANY } from "@/lib/company"

const CONTACT_EMAIL = "woo@securemachineslab.com"

function FooterLink({ href, children }: { href: string; children: React.ReactNode }) {
  // The privacy policy is emphasised, as Korean privacy law asks.
  const strong = href === "/privacy"
  return (
    <Typography component={Link} href={href} variant="subtitle1"
      sx={{ color: strong ? "text.primary" : "text.secondary", fontWeight: strong ? 700 : 400, textDecoration: "none", "&:hover": { color: "primary.main" } }}>
      {children}
    </Typography>
  )
}

/** Public footer (landing, pricing, docs, legal). */
export function SiteFooter() {
  const t = useTranslations("landing.footer")
  const legal = useTranslations("site")
  const columns = [
    { title: t("product"), links: [["/app/detect", t("detection")], ["/app/long-video", t("longVideo")], ["/app/news", t("news")],
      ["/app/studio", t("studio")], ["/pricing", t("pricing")]] },
    { title: t("developers"), links: [["/docs", t("apiDocs")], ["/login", t("signIn")]] },
    { title: t("company"), links: [["/#about", t("about")], ["/#research", t("research")], ["/#contact", t("contact")]] },
    { title: t("legal"), links: [["/terms", t("terms")], ["/privacy", t("privacy")], ["/refund-policy", t("refunds")]] },
  ]
  return (
    <Box component="footer" sx={{ bgcolor: "background.paper", borderTop: "1px solid", borderColor: "divider", pt: { xs: 7, md: 9 }, pb: 4 }}>
      <Container maxWidth="lg">
        <Grid container spacing={{ xs: 5, md: 4 }}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Logo href="/" />
            <Typography variant="subtitle1" sx={{ color: "text.secondary", mt: 2, maxWidth: 320 }}>{t("tagline")}</Typography>
            <Stack spacing={1} sx={{ mt: 2.5 }}>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", color: "text.secondary" }}>
                <IconMail size={18} />
                <Typography component="a" href={`mailto:${CONTACT_EMAIL}`} variant="subtitle1"
                  sx={{ color: "text.secondary", textDecoration: "none", "&:hover": { color: "primary.main" } }}>{CONTACT_EMAIL}</Typography>
              </Stack>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", color: "text.secondary" }}>
                <IconMapPin size={18} />
                <Typography variant="subtitle1">Suwon-si, Gyeonggi-do · South Korea</Typography>
              </Stack>
            </Stack>
          </Grid>
          {columns.map((col) => (
            <Grid key={col.title} size={{ xs: 6, sm: 3, md: 2 }}>
              <Typography variant="h6" component="p" sx={{ mb: 2 }}>{col.title}</Typography>
              <Stack spacing={1.25}>{col.links.map(([href, label]) => <FooterLink key={href} href={href}>{label}</FooterLink>)}</Stack>
            </Grid>
          ))}
        </Grid>
        <Divider sx={{ my: 4 }} />
        {/* Business details required on the site by Korean e-commerce law (lib/company.ts). */}
        <Typography variant="body2" component="p" sx={{ color: "text.secondary", lineHeight: 1.8 }}>
          {COMPANY.name} · {legal("representative")}: {COMPANY.representative} · {legal("bizNo")}: {COMPANY.businessRegistrationNo} ·{" "}
          {legal("mailOrderNo")}: {COMPANY.mailOrderRegistrationNo}<br />
          {COMPANY.address} · {COMPANY.supportEmail} · {COMPANY.phone}
        </Typography>
        <Typography variant="body1" sx={{ color: "text.secondary", mt: 2 }}>{t("rights", { year: new Date().getFullYear() })}</Typography>
      </Container>
    </Box>
  )
}

"use client"

import Avatar from "@mui/material/Avatar"
import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Card from "@mui/material/Card"
import Chip from "@mui/material/Chip"
import Container from "@mui/material/Container"
import Grid from "@mui/material/Grid"
import LinearProgress from "@mui/material/LinearProgress"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import { IconArrowRight, IconCircleCheck, IconFileTypePdf, IconFlame, IconMessageChatbot, IconPhoto, IconShieldCheck } from "@tabler/icons-react"
import Image from "next/image"
import Link from "next/link"
import { useTranslations } from "next-intl"

/** A floating mini card around the preview. */
function Floating({ icon, label, tone, sx }: { icon: React.ReactNode; label: string; tone: "primary" | "success"; sx: object }) {
  return (
    <Card sx={{ position: "absolute", px: 1.75, py: 1.25, display: { xs: "none", sm: "flex" }, alignItems: "center", gap: 1.25,
      borderRadius: "10px", ...sx }}>
      <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: `${tone}.light`, color: `${tone}.main`, borderRadius: "8px" }}>{icon}</Avatar>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>{label}</Typography>
    </Card>
  )
}

/** The product, as the user sees a result: verdict, analyses and provenance. */
function ResultPreview() {
  const t = useTranslations("landing.preview")
  return (
    <Box sx={{ position: "relative", maxWidth: 520, mx: "auto", px: { sm: 3 } }}>
      <Card sx={{ borderRadius: "14px", overflow: "hidden" }}>
        <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", px: 2.5, py: 1.75, borderBottom: "1px solid", borderColor: "divider" }}>
          <Stack direction="row" spacing={1.25} sx={{ alignItems: "center", minWidth: 0 }}>
            <Avatar variant="rounded" sx={{ width: 34, height: 34, bgcolor: "primary.light", color: "primary.main", borderRadius: "8px" }}>
              <IconPhoto size={18} />
            </Avatar>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }} noWrap>{t("file")}</Typography>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>{t("done")}</Typography>
            </Box>
          </Stack>
          <IconCircleCheck size={22} color="var(--mui-palette-success-main)" />
        </Stack>
        <Box sx={{ position: "relative", aspectRatio: "16 / 9", bgcolor: "#0b1a33" }}>
          <Image src="/images/research-detection.png" alt="" fill priority sizes="(max-width: 900px) 100vw, 520px" style={{ objectFit: "cover" }} />
          {/* the heatmap: where the evidence is */}
          <Box aria-hidden sx={{ position: "absolute", inset: 0, mixBlendMode: "screen",
            background: "radial-gradient(22% 30% at 46% 58%, rgba(250,80,60,.85), rgba(250,170,40,.45) 45%, transparent 70%), radial-gradient(14% 18% at 58% 40%, rgba(250,120,60,.6), transparent 70%)" }} />
          <Chip label={t("heatmap")} size="small" sx={{ position: "absolute", left: 12, top: 12, bgcolor: "rgba(11,26,51,.72)", color: "#fff", fontWeight: 600 }} />
        </Box>
        <Box sx={{ p: 2.5 }}>
          <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", mb: 2 }}>
            <Chip icon={<IconFlame size={16} />} label={t("verdict")}
              sx={{ bgcolor: "error.light", color: "error.main", fontWeight: 700, "& .MuiChip-icon": { color: "inherit" } }} />
            <Typography variant="h3" sx={{ fontWeight: 800, color: "error.main" }}>92%</Typography>
          </Stack>
          {[{ label: t("faceSwap"), value: 92, color: "error" as const }, { label: t("aiGenerated"), value: 18, color: "primary" as const }].map((row) => (
            <Box key={row.label} sx={{ mb: 1.5 }}>
              <Stack direction="row" sx={{ justifyContent: "space-between", mb: 0.5 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{row.label}</Typography>
                <Typography variant="subtitle2" sx={{ color: "text.secondary", fontWeight: 600 }}>{row.value}%</Typography>
              </Stack>
              <LinearProgress variant="determinate" value={row.value} color={row.color} aria-label={`${row.label} ${row.value}%`}
                sx={{ height: 8, borderRadius: 4, bgcolor: "grey.100", "& .MuiLinearProgress-bar": { borderRadius: 4 } }} />
            </Box>
          ))}
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", mt: 2, color: "text.secondary" }}>
            <IconShieldCheck size={18} />
            <Typography variant="subtitle2">{t("analysed")}</Typography>
          </Stack>
        </Box>
      </Card>
      <Floating icon={<IconFileTypePdf size={18} />} label={t("report")} tone="success" sx={{ right: { sm: -8, md: -24 }, top: 92 }} />
      <Floating icon={<IconMessageChatbot size={18} />} label={t("explained")} tone="primary" sx={{ left: { sm: -8, md: -28 }, top: 228 }} />
    </Box>
  )
}

export function Hero() {
  const t = useTranslations("landing.hero")
  return (
    <Box component="section" sx={{
      position: "relative", overflow: "hidden", pt: { xs: 6, md: 10 }, pb: { xs: 8, md: 12 },
      background: (theme) => `radial-gradient(900px 480px at 85% 10%, rgba(${theme.vars.palette.primary.mainChannel} / 0.12), transparent 70%), linear-gradient(180deg, ${theme.vars.palette.primary.light} 0%, ${theme.vars.palette.background.default} 100%)`,
    }}>
      <Container maxWidth="lg">
        <Grid container spacing={{ xs: 6, md: 8 }} sx={{ alignItems: "center" }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Chip icon={<IconShieldCheck size={16} />} label={t("badge")}
              sx={{ bgcolor: "background.paper", color: "primary.main", fontWeight: 700, border: "1px solid", borderColor: "divider",
                "& .MuiChip-icon": { color: "inherit" } }} />
            <Typography component="h1" sx={{ mt: 3, fontWeight: 800, letterSpacing: "-0.02em", color: "text.primary",
              fontSize: { xs: "2.4rem", sm: "3rem", md: "3.5rem" }, lineHeight: 1.08 }}>
              {t("title")}
              <Box component="span" sx={{ display: "block", mt: 1, fontSize: { xs: "1.75rem", sm: "2.1rem", md: "2.4rem" }, lineHeight: 1.15,
                color: "primary.main" }}>
                {t("titleAccent")}
              </Box>
            </Typography>
            <Typography sx={{ mt: 3, color: "text.secondary", fontSize: { xs: "1rem", md: "1.125rem" }, lineHeight: 1.7, maxWidth: 560 }}>
              {t("subtitle")}
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 4 }}>
              <Button component={Link} href="#trial" variant="contained" size="large" endIcon={<IconArrowRight size={18} />}
                sx={{ px: 3.5, py: 1.4, fontSize: "1rem" }}>{t("primary")}</Button>
              <Button component={Link} href="/signup" variant="outlined" size="large"
                sx={{ px: 3.5, py: 1.4, fontSize: "1rem", bgcolor: "background.paper" }}>{t("secondary")}</Button>
            </Stack>
            <Typography variant="subtitle2" sx={{ mt: 2.5, color: "text.secondary" }}>{t("note")}</Typography>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}><ResultPreview /></Grid>
        </Grid>
      </Container>
    </Box>
  )
}

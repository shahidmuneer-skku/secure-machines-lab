"use client"

import AppBar from "@mui/material/AppBar"
import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Container from "@mui/material/Container"
import Drawer from "@mui/material/Drawer"
import IconButton from "@mui/material/IconButton"
import List from "@mui/material/List"
import ListItemButton from "@mui/material/ListItemButton"
import ListItemText from "@mui/material/ListItemText"
import Stack from "@mui/material/Stack"
import Toolbar from "@mui/material/Toolbar"
import { IconMenu2, IconX } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useState } from "react"

import { LanguageMenu, ThemeButton } from "@/components/app-shell/header-controls"
import { Logo } from "@/components/brand/logo"
import { api, data } from "@/lib/api/client"

export function useSignedIn(): boolean {
  const { data: me } = useQuery({
    queryKey: ["me", "optional"], retry: false, staleTime: 60_000,
    queryFn: async () => { try { return data(await api.GET("/api/v1/me")) } catch { return null } },
  })
  return !!me
}

/** Public navigation bar (landing, pricing, docs, legal): sticky, turns solid with a hairline when scrolled. */
export function SiteNav() {
  const t = useTranslations("landing.nav")
  const signedIn = useSignedIn()
  const pathname = usePathname()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])
  // Section links work from every public page: on the landing page they scroll, elsewhere they navigate.
  const home = pathname === "/" ? "" : "/"
  const links = [
    { href: `${home}#products`, label: t("products") },
    { href: `${home}#how`, label: t("how") },
    { href: `${home}#research`, label: t("research") },
    { href: "/pricing", label: t("pricing") },
    { href: "/docs", label: t("docs") },
  ]
  return (
    <AppBar position="sticky" sx={{
      bgcolor: (theme) => `rgba(${theme.vars.palette.background.paperChannel} / ${scrolled ? 0.92 : 0.75})`,
      backdropFilter: "saturate(180%) blur(10px)", borderBottom: "1px solid",
      borderColor: scrolled ? "divider" : "transparent", transition: "border-color .2s, background-color .2s",
    }}>
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ minHeight: { xs: 64, md: 72 }, gap: 2 }}>
          <Logo href="/" />
          <Stack component="nav" direction="row" spacing={0.5} sx={{ display: { xs: "none", md: "flex" }, ml: 4, flexGrow: 1 }}>
            {links.map((l) => (
              <Button key={l.href} component={Link} href={l.href} color="inherit"
                sx={{ color: "text.secondary", fontWeight: 600, px: 1.5, "&:hover": { color: "primary.main", bgcolor: "primary.light" } }}>
                {l.label}
              </Button>
            ))}
          </Stack>
          <Box sx={{ flexGrow: { xs: 1, md: 0 } }} />
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
            <Box sx={{ display: { xs: "none", sm: "flex" }, alignItems: "center" }}><LanguageMenu /><ThemeButton /></Box>
            {signedIn ? (
              <Button component={Link} href="/app" variant="contained" sx={{ display: { xs: "none", sm: "inline-flex" } }}>{t("openApp")}</Button>
            ) : (
              <>
                <Button component={Link} href="/login" color="inherit" sx={{ display: { xs: "none", sm: "inline-flex" }, fontWeight: 600 }}>{t("signIn")}</Button>
                <Button component={Link} href="/signup" variant="contained" sx={{ display: { xs: "none", sm: "inline-flex" } }}>{t("getStarted")}</Button>
              </>
            )}
            <IconButton aria-label={t("menu")} onClick={() => setOpen(true)} sx={{ display: { md: "none" }, color: "text.primary" }}>
              <IconMenu2 size={24} stroke={1.6} />
            </IconButton>
          </Stack>
        </Toolbar>
      </Container>
      <Drawer anchor="right" open={open} onClose={() => setOpen(false)} slotProps={{ paper: { sx: { width: 300, p: 2 } } }}>
        <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", mb: 2 }}>
          <Logo href="/" />
          <IconButton aria-label={t("menu")} onClick={() => setOpen(false)}><IconX size={22} /></IconButton>
        </Stack>
        <List>
          {links.map((l) => (
            <ListItemButton key={l.href} component={Link} href={l.href} onClick={() => setOpen(false)}>
              <ListItemText primary={l.label} slotProps={{ primary: { sx: { fontWeight: 600 } } }} />
            </ListItemButton>
          ))}
        </List>
        <Stack spacing={1.5} sx={{ mt: 2 }}>
          {signedIn ? (
            <Button component={Link} href="/app" variant="contained" fullWidth>{t("openApp")}</Button>
          ) : (
            <>
              <Button component={Link} href="/signup" variant="contained" fullWidth>{t("getStarted")}</Button>
              <Button component={Link} href="/login" variant="outlined" fullWidth>{t("signIn")}</Button>
            </>
          )}
          <Stack direction="row" spacing={1} sx={{ justifyContent: "center" }}><LanguageMenu /><ThemeButton /></Stack>
        </Stack>
      </Drawer>
    </AppBar>
  )
}

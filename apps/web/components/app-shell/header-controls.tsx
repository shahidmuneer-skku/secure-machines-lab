"use client"

import Avatar from "@mui/material/Avatar"
import Box from "@mui/material/Box"
import Chip from "@mui/material/Chip"
import Divider from "@mui/material/Divider"
import IconButton from "@mui/material/IconButton"
import ListItemIcon from "@mui/material/ListItemIcon"
import Menu from "@mui/material/Menu"
import MenuItem from "@mui/material/MenuItem"
import Tooltip from "@mui/material/Tooltip"
import Typography from "@mui/material/Typography"
import { IconCheck, IconCoins, IconCreditCard, IconKey, IconLanguage, IconLogout, IconMoon, IconSettings,
  IconShieldCheck, IconSun } from "@tabler/icons-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { useTheme } from "next-themes"
import { useState, useTransition } from "react"

import { setLocaleCookie } from "@/components/app-shell/locale-switcher"
import { useBalance } from "@/components/sml/credit-meter"
import { useHydrated } from "@/hooks/use-hydrated"
import { useMe } from "@/hooks/use-me"
import { LOCALE_LABELS, LOCALES, type Locale } from "@/i18n/config"
import { api } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { allauth } from "@/lib/auth/allauth"

/** Light/dark switch (light is the default; the choice is remembered by next-themes). */
export function ThemeButton() {
  const { resolvedTheme, setTheme } = useTheme()
  const hydrated = useHydrated()
  const t = useTranslations("common")
  const dark = hydrated && resolvedTheme === "dark"
  return (
    <Tooltip title={`${t("theme")}: ${dark ? t("dark") : t("light")}`}>
      <IconButton aria-label={`${t("theme")}: ${dark ? t("dark") : t("light")}`} onClick={() => setTheme(dark ? "light" : "dark")}
        sx={{ color: "text.secondary" }}>
        {dark ? <IconMoon size={21} stroke={1.5} /> : <IconSun size={21} stroke={1.5} />}
      </IconButton>
    </Tooltip>
  )
}

/** Language menu; also saves the choice to the profile when signed in (emails, reports). */
export function LanguageMenu({ signedIn = false }: { signedIn?: boolean }) {
  const locale = useLocale() as Locale
  const t = useTranslations("common")
  const router = useRouter()
  const qc = useQueryClient()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [pending, start] = useTransition()
  const save = useMutation({
    mutationFn: async (value: Locale) => api.PATCH("/api/v1/me", { body: { locale: value } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me }),
  })
  const choose = (next: Locale) => {
    setAnchor(null)
    if (next === locale) return
    setLocaleCookie(next)
    if (signedIn) save.mutate(next)
    start(() => router.refresh())
  }
  return (
    <>
      <Tooltip title={t("language")}>
        <IconButton aria-label={t("language")} disabled={pending} onClick={(e) => setAnchor(e.currentTarget)}
          sx={{ color: "text.secondary", gap: 0.5, borderRadius: 2 }}>
          <IconLanguage size={21} stroke={1.5} />
          <Typography component="span" sx={{ fontSize: "0.75rem", fontWeight: 700 }}>{LOCALE_LABELS[locale].short}</Typography>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }} transformOrigin={{ vertical: "top", horizontal: "right" }}>
        {LOCALES.map((l) => (
          <MenuItem key={l} selected={l === locale} onClick={() => choose(l)} sx={{ minWidth: 160 }}>
            <ListItemIcon>{l === locale ? <IconCheck size={18} /> : null}</ListItemIcon>
            {LOCALE_LABELS[l].native}
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}

/** Credit balance; amber when low. Links to billing. */
export function CreditChip() {
  const t = useTranslations("credits")
  const { data: balance } = useBalance()
  const value = balance ? (balance.unlimited ? "∞" : balance.balance.toLocaleString()) : "—"
  const tip = balance?.held ? t("held", { count: balance.held }) : t("balanceHint", { daily: balance?.daily_free_credits ?? 0 })
  return (
    <Tooltip title={tip}>
      <Chip component={Link} href="/app/billing" clickable icon={<IconCoins size={18} />}
        label={<><b>{value}</b><Box component="span" sx={{ display: { xs: "none", md: "inline" }, ml: 0.5, fontWeight: 500 }}>{t("credits")}</Box></>}
        sx={{
          height: 36, px: 0.5, fontSize: "0.8125rem",
          bgcolor: balance?.low_balance ? "warning.light" : "primary.light",
          color: balance?.low_balance ? "warning.main" : "primary.main",
          "& .MuiChip-icon": { color: "inherit" },
        }} />
    </Tooltip>
  )
}

function initialsOf(name: string): string {
  const words = name.split(/[\s._-]+/).filter(Boolean)
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase()
}

/** Avatar menu: account details, settings, billing, API keys, admin (staff) and sign out. */
export function ProfileMenu({ area }: { area: "app" | "admin" }) {
  const { data: me } = useMe()
  const t = useTranslations()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const logout = useMutation({
    mutationFn: () => allauth.logout(),
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- full reload drops the previous user's cached data
    onSettled: () => window.location.assign("/login"),
  })
  const name = me?.display_name?.trim() || me?.email?.split("@")[0] || "?"
  const close = () => setAnchor(null)
  return (
    <>
      <IconButton aria-label={t("shell.account")} onClick={(e) => setAnchor(e.currentTarget)} sx={{ p: 0.5 }}>
        <Avatar sx={{ width: 35, height: 35, bgcolor: "primary.light", color: "primary.main", fontSize: "0.85rem", fontWeight: 700 }}>
          {initialsOf(name)}
        </Avatar>
      </IconButton>
      <Menu anchorEl={anchor} open={!!anchor} onClose={close}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }} transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{ paper: { sx: { width: 260, mt: 1 } } }}>
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography variant="h6" noWrap>{me?.display_name || name}</Typography>
          <Typography variant="body2" color="text.secondary" noWrap>{me?.email}</Typography>
          {!!me?.roles?.length && (
            <Typography variant="body2" color="primary.main" sx={{ mt: 0.5, fontWeight: 600, textTransform: "capitalize" }}>
              {me.roles.join(", ").replaceAll("_", " ")}
            </Typography>
          )}
        </Box>
        <Divider />
        <MenuItem component={Link} href="/app/settings" onClick={close}>
          <ListItemIcon><IconSettings size={19} stroke={1.5} /></ListItemIcon>{t("nav.settings")}
        </MenuItem>
        <MenuItem component={Link} href="/app/billing" onClick={close}>
          <ListItemIcon><IconCreditCard size={19} stroke={1.5} /></ListItemIcon>{t("nav.billing")}
        </MenuItem>
        {me?.capabilities?.includes("manage_own_api_keys") && (
          <MenuItem component={Link} href="/app/api-keys" onClick={close}>
            <ListItemIcon><IconKey size={19} stroke={1.5} /></ListItemIcon>{t("nav.apiKeys")}
          </MenuItem>
        )}
        {me?.is_staff_user && (
          <MenuItem component={Link} href={area === "admin" ? "/app" : "/admin"} onClick={close}>
            <ListItemIcon><IconShieldCheck size={19} stroke={1.5} /></ListItemIcon>
            {area === "admin" ? t("nav.backToApp") : t("nav.admin")}
          </MenuItem>
        )}
        <Divider />
        <MenuItem onClick={() => { close(); logout.mutate() }}>
          <ListItemIcon><IconLogout size={19} stroke={1.5} /></ListItemIcon>{t("common.signOut")}
        </MenuItem>
      </Menu>
    </>
  )
}

"use client"

import Alert from "@mui/material/Alert"
import AppBar from "@mui/material/AppBar"
import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Drawer from "@mui/material/Drawer"
import IconButton from "@mui/material/IconButton"
import List from "@mui/material/List"
import ListItemButton from "@mui/material/ListItemButton"
import ListItemIcon from "@mui/material/ListItemIcon"
import ListItemText from "@mui/material/ListItemText"
import ListSubheader from "@mui/material/ListSubheader"
import Stack from "@mui/material/Stack"
import Toolbar from "@mui/material/Toolbar"
import Tooltip from "@mui/material/Tooltip"
import Typography from "@mui/material/Typography"
import {
  IconActivity, IconAdjustmentsHorizontal, IconArrowLeft, IconBook, IconChartBar, IconCoins, IconCpu,
  IconFileDescription, IconFileText, IconGauge, IconKey, IconLayoutDashboard, IconListCheck, IconMenu2, IconMovie,
  IconNews, IconPalette, IconPhotoScan, IconReceipt, IconSettings, IconShieldCheck, IconSparkles, IconUserShield,
  IconUsers, type Icon,
} from "@tabler/icons-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"
import { useState, type ReactNode } from "react"

import { Logo } from "@/components/brand/logo"
import { useBalance } from "@/components/sml/credit-meter"
import { useEventStream } from "@/hooks/use-event-stream"
import { useMe, usePublicConfig } from "@/hooks/use-me"
import { activeFill } from "@/lib/theme/palette"

import { CreditChip, LanguageMenu, ProfileMenu, ThemeButton } from "./header-controls"

/** App frame after the Modernize template (owner, 2026-10-02): white sidebar, sticky header, content. */

const SIDEBAR_WIDTH = 270

type NavItem = { href: string; key: string; icon: Icon; capability?: string; exact?: boolean }

const APP_NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "workspace",
    items: [
      { href: "/app", key: "dashboard", icon: IconLayoutDashboard, exact: true },
      { href: "/app/detect", key: "detect", icon: IconPhotoScan, capability: "run_detection" },
      { href: "/app/long-video", key: "longVideo", icon: IconMovie, capability: "run_long_video" },
      { href: "/app/news", key: "news", icon: IconNews, capability: "run_news_verification" },
      { href: "/app/studio", key: "studio", icon: IconSparkles, capability: "use_studio" },
      { href: "/app/results", key: "results", icon: IconListCheck },
      { href: "/app/reports", key: "reports", icon: IconFileText },
    ],
  },
  {
    group: "account",
    items: [
      { href: "/app/billing", key: "billing", icon: IconCoins },
      { href: "/app/api-keys", key: "apiKeys", icon: IconKey, capability: "manage_own_api_keys" },
      { href: "/app/settings", key: "settings", icon: IconSettings },
      { href: "/docs", key: "docs", icon: IconBook },
    ],
  },
]

const ADMIN_NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "administration",
    items: [
      { href: "/admin", key: "adminOverview", icon: IconGauge, capability: "view_users", exact: true },
      { href: "/admin/users", key: "adminUsers", icon: IconUsers, capability: "view_users" },
      { href: "/admin/roles", key: "adminRoles", icon: IconUserShield, capability: "view_users" },
      { href: "/admin/jobs", key: "adminJobs", icon: IconActivity, capability: "view_all_jobs" },
      { href: "/admin/queues", key: "adminQueues", icon: IconCpu, capability: "view_queues" },
      { href: "/admin/models", key: "adminModels", icon: IconShieldCheck, capability: "view_queues" },
      { href: "/admin/studio", key: "adminStudio", icon: IconPalette, capability: "view_queues" },
      { href: "/admin/pricing", key: "adminPricing", icon: IconAdjustmentsHorizontal, capability: "view_billing" },
      { href: "/admin/billing", key: "adminBilling", icon: IconReceipt, capability: "view_billing" },
      { href: "/admin/api-usage", key: "adminApiUsage", icon: IconChartBar, capability: "view_api_usage" },
      { href: "/admin/audit-log", key: "adminAudit", icon: IconFileDescription, capability: "view_audit_log" },
      { href: "/admin/settings", key: "adminSettings", icon: IconSettings, capability: "view_users" },
    ],
  },
]

function isActive(pathname: string, item: NavItem) {
  return item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`)
}

function SidebarContent({ area, onNavigate }: { area: "app" | "admin"; onNavigate?: () => void }) {
  const t = useTranslations("nav")
  const pathname = usePathname()
  const { data: me } = useMe()
  const caps = new Set(me?.capabilities ?? [])
  const sections = area === "admin" ? ADMIN_NAV : APP_NAV
  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ display: "flex", alignItems: "center", minHeight: 70, px: 3 }}>
        <Logo href={area === "admin" ? "/admin" : "/app"} tag={area === "admin" ? "Admin" : undefined} />
      </Box>
      <Box component="nav" aria-label={t(area === "admin" ? "administration" : "workspace")}
        sx={{ flex: 1, overflowY: "auto", px: 3, pb: 2 }}>
        {sections.map((section) => (
          <List key={section.group} disablePadding
            subheader={<ListSubheader disableSticky sx={{ px: 1.5, mt: 2.5, mb: 0.5, lineHeight: "26px", bgcolor: "transparent",
              fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "text.primary" }}>
              {t(section.group)}</ListSubheader>}>
            {section.items.filter((i) => !i.capability || caps.has(i.capability)).map((item) => {
              const active = isActive(pathname, item)
              const ItemIcon = item.icon
              return (
                <ListItemButton key={item.href} component={Link} href={item.href} onClick={onNavigate} selected={active}
                  aria-current={active ? "page" : undefined}
                  sx={{
                    mb: 0.5, px: 1.5, py: 1, color: "text.secondary",
                    "&:hover": { bgcolor: "primary.light", color: "primary.main" },
                    "&.Mui-selected, &.Mui-selected:hover": { bgcolor: activeFill, color: "#FFFFFF" },
                  }}>
                  <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}><ItemIcon size={21} stroke={1.5} /></ListItemIcon>
                  <ListItemText primary={t(item.key)} slotProps={{ primary: { sx: { fontSize: "0.9375rem", fontWeight: active ? 600 : 500 } } }} />
                </ListItemButton>
              )
            })}
          </List>
        ))}
        {me?.is_staff_user && (
          <List disablePadding sx={{ mt: 2 }}>
            <ListItemButton component={Link} href={area === "admin" ? "/app" : "/admin"} onClick={onNavigate}
              sx={{ px: 1.5, py: 1, color: "text.secondary", "&:hover": { bgcolor: "primary.light", color: "primary.main" } }}>
              <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}>
                {area === "admin" ? <IconArrowLeft size={21} stroke={1.5} /> : <IconShieldCheck size={21} stroke={1.5} />}
              </ListItemIcon>
              <ListItemText primary={area === "admin" ? t("backToApp") : t("admin")}
                slotProps={{ primary: { sx: { fontSize: "0.9375rem", fontWeight: 500 } } }} />
            </ListItemButton>
          </List>
        )}
      </Box>
      {area === "app" && <CreditsBox />}
    </Box>
  )
}

/** The credits box at the foot of the sidebar (Modernize's "upgrade" card). */
function CreditsBox() {
  const t = useTranslations()
  const { data: balance } = useBalance()
  return (
    <Box sx={{ m: 3, mt: 0, p: 2.5, borderRadius: "7px", bgcolor: "primary.light", position: "relative", overflow: "hidden" }}>
      <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>{t("shell.balance")}</Typography>
      <Typography variant="h3" sx={{ mt: 0.5, color: "text.primary", fontWeight: 700 }}>
        {balance ? (balance.unlimited ? "∞" : balance.balance.toLocaleString()) : "—"}
        <Typography component="span" variant="body1" sx={{ ml: 0.75, color: "text.secondary", fontWeight: 500 }}>{t("credits.credits")}</Typography>
      </Typography>
      <Button component={Link} href="/app/billing" variant="contained" size="small" sx={{ mt: 1.5 }}>{t("credits.buy")}</Button>
      <Box aria-hidden sx={{ position: "absolute", right: -18, bottom: -18, width: 86, height: 86, borderRadius: "50%",
        bgcolor: "primary.main", opacity: 0.12 }} />
    </Box>
  )
}

function LiveIndicator({ connected }: { connected: boolean }) {
  const t = useTranslations("shell")
  return (
    <Tooltip title={connected ? t("liveHint") : t("offlineHint")}>
      <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", color: connected ? "success.main" : "text.secondary" }}>
        <span className="led-dot" data-pulse={connected} aria-hidden />
        <Typography variant="body2" sx={{ display: { xs: "none", sm: "block" }, fontWeight: 600 }}>
          {connected ? t("live") : t("offline")}
        </Typography>
      </Stack>
    </Tooltip>
  )
}

function Banners() {
  const { data: config } = usePublicConfig()
  const { data: balance } = useBalance()
  const t = useTranslations()
  const items: ReactNode[] = []
  if (config?.maintenance_mode) items.push(<Alert key="m" severity="warning">{t("errors.MAINTENANCE")}</Alert>)
  if (config?.announcement) items.push(<Alert key="a" severity="info">{String(config.announcement)}</Alert>)
  if (balance?.low_balance) {
    items.push(
      <Alert key="c" severity="warning" action={<Button component={Link} href="/app/billing" color="inherit" size="small">{t("credits.buy")}</Button>}>
        {t("credits.low")}
      </Alert>,
    )
  }
  return items.length ? <Stack spacing={1.5} sx={{ mb: 3 }}>{items}</Stack> : null
}

export function AppShell({ children, area = "app" }: { children: ReactNode; area?: "app" | "admin" }) {
  const t = useTranslations("shell")
  const { data: me } = useMe()
  const { connected } = useEventStream(!!me)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2">
        {t("skipToContent")}
      </a>
      {/* Both drawers render; CSS shows the permanent one from `lg` and the menu-button one below it. */}
      <Box component="aside" sx={{ width: SIDEBAR_WIDTH, flexShrink: 0, display: { xs: "none", lg: "block" } }}>
        <Drawer variant="permanent" open slotProps={{ paper: { sx: { width: SIDEBAR_WIDTH, boxSizing: "border-box",
          borderRight: "1px solid", borderColor: "divider", bgcolor: "background.paper" } } }}>
          <SidebarContent area={area} />
        </Drawer>
      </Box>
      <Drawer variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: "block", lg: "none" } }}
        slotProps={{ paper: { sx: { width: SIDEBAR_WIDTH, bgcolor: "background.paper" } } }}>
        <SidebarContent area={area} onNavigate={() => setMobileOpen(false)} />
      </Drawer>
      <Box sx={{ display: "flex", flexDirection: "column", flexGrow: 1, minWidth: 0 }}>
        <AppBar position="sticky" sx={{ bgcolor: "background.paper", borderBottom: "1px solid", borderColor: "divider",
          backdropFilter: "blur(4px)" }}>
          <Toolbar sx={{ minHeight: { xs: 64, lg: 70 }, gap: 1, px: { xs: 2, md: 3 } }}>
            <IconButton aria-label={t("openMenu")} onClick={() => setMobileOpen(true)}
              sx={{ color: "text.secondary", display: { xs: "inline-flex", lg: "none" } }}>
              <IconMenu2 size={22} stroke={1.5} />
            </IconButton>
            <LiveIndicator connected={connected} />
            <Box sx={{ flexGrow: 1 }} />
            <Stack direction="row" spacing={{ xs: 0.5, sm: 1 }} sx={{ alignItems: "center" }}>
              {area === "app" && <CreditChip />}
              <LanguageMenu signedIn />
              <ThemeButton />
              <ProfileMenu area={area} />
            </Stack>
          </Toolbar>
        </AppBar>
        <Box component="main" id="main" sx={{ flexGrow: 1, width: "100%", maxWidth: 1280, mx: "auto", px: { xs: 2, md: 3 }, py: { xs: 2.5, md: 3.5 } }}>
          <Banners />
          {children}
        </Box>
      </Box>
    </Box>
  )
}

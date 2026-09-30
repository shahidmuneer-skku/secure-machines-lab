"use client"

import { useMutation } from "@tanstack/react-query"
import {
  Activity, BookOpen, Coins, FileText, FilmIcon, Gauge, KeyRound, LayoutDashboard, ListChecks, LogOut, Newspaper,
  ScanSearch, Settings, ShieldCheck, Users, Cpu, Receipt, SlidersHorizontal, ScrollText, BarChart3, BadgeCheck,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"
import type { ReactNode } from "react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader,
  SidebarInset, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarProvider, SidebarRail, SidebarTrigger,
} from "@/components/ui/sidebar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { CreditMeter, useBalance } from "@/components/sml/credit-meter"
import { useEventStream } from "@/hooks/use-event-stream"
import { useMe, usePublicConfig } from "@/hooks/use-me"
import { allauth } from "@/lib/auth/allauth"
import { cn } from "@/lib/utils"

import { BrandMark } from "./brand"
import { LocaleSwitcher } from "./locale-switcher"
import { ThemeToggle } from "./theme-toggle"

type NavItem = { href: string; key: string; icon: typeof Gauge; capability?: string; exact?: boolean }

const APP_NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "workspace",
    items: [
      { href: "/app", key: "dashboard", icon: LayoutDashboard, exact: true },
      { href: "/app/detect", key: "detect", icon: ScanSearch, capability: "run_detection" },
      { href: "/app/long-video", key: "longVideo", icon: FilmIcon, capability: "run_long_video" },
      { href: "/app/news", key: "news", icon: Newspaper, capability: "run_news_verification" },
      { href: "/app/results", key: "results", icon: ListChecks },
      { href: "/app/reports", key: "reports", icon: FileText },
    ],
  },
  {
    group: "account",
    items: [
      { href: "/app/billing", key: "billing", icon: Coins },
      { href: "/app/api-keys", key: "apiKeys", icon: KeyRound, capability: "manage_own_api_keys" },
      { href: "/app/settings", key: "settings", icon: Settings },
      { href: "/docs", key: "docs", icon: BookOpen },
    ],
  },
]

const ADMIN_NAV: NavItem[] = [
  { href: "/admin", key: "adminOverview", icon: Gauge, capability: "view_users", exact: true },
  { href: "/admin/users", key: "adminUsers", icon: Users, capability: "view_users" },
  { href: "/admin/roles", key: "adminRoles", icon: BadgeCheck, capability: "view_users" },
  { href: "/admin/jobs", key: "adminJobs", icon: Activity, capability: "view_all_jobs" },
  { href: "/admin/queues", key: "adminQueues", icon: Cpu, capability: "view_queues" },
  { href: "/admin/models", key: "adminModels", icon: ShieldCheck, capability: "view_queues" },
  { href: "/admin/pricing", key: "adminPricing", icon: SlidersHorizontal, capability: "view_billing" },
  { href: "/admin/billing", key: "adminBilling", icon: Receipt, capability: "view_billing" },
  { href: "/admin/api-usage", key: "adminApiUsage", icon: BarChart3, capability: "view_api_usage" },
  { href: "/admin/audit-log", key: "adminAudit", icon: ScrollText, capability: "view_audit_log" },
  { href: "/admin/settings", key: "adminSettings", icon: Settings, capability: "view_users" },
]

function isActive(pathname: string, item: NavItem) {
  return item.exact ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`)
}

function NavMenu({ items, caps }: { items: NavItem[]; caps: Set<string> }) {
  const pathname = usePathname()
  const t = useTranslations("nav")
  return (
    <SidebarMenu>
      {items
        .filter((i) => !i.capability || caps.has(i.capability))
        .map((item) => (
          <SidebarMenuItem key={item.href}>
            <SidebarMenuButton asChild isActive={isActive(pathname, item)} tooltip={t(item.key)}>
              <Link href={item.href}>
                <item.icon aria-hidden />
                <span>{t(item.key)}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
    </SidebarMenu>
  )
}

function UserMenu() {
  const { data: me } = useMe()
  const t = useTranslations()
  const logout = useMutation({
    mutationFn: () => allauth.logout(),
    onSettled: () => window.location.assign("/login"),
  })
  const initials = (me?.display_name || me?.email || "?").slice(0, 2).toUpperCase()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
          <Avatar className="size-8 rounded-lg">
            <AvatarFallback className="rounded-lg bg-primary/15 font-mono text-xs text-primary">{initials}</AvatarFallback>
          </Avatar>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-medium">{me?.display_name || me?.email}</span>
            <span className="truncate text-xs text-muted-foreground">{me?.roles?.join(", ")}</span>
          </div>
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-60" align="end" side="top">
        <DropdownMenuLabel className="truncate font-normal text-muted-foreground">{me?.email}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/app/settings"><Settings /> {t("nav.settings")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/app/billing"><Coins /> {t("nav.billing")}</Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => logout.mutate()}>
          <LogOut /> {t("common.signOut")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function LiveIndicator({ connected }: { connected: boolean }) {
  const t = useTranslations("shell")
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("inline-flex items-center gap-1.5 mono-label", connected ? "text-real" : "text-muted-foreground")}>
          <span className="led-dot" data-pulse={connected} aria-hidden />
          <span className="hidden sm:inline">{connected ? t("live") : t("offline")}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{connected ? t("liveHint") : t("offlineHint")}</TooltipContent>
    </Tooltip>
  )
}

function Banners() {
  const { data: config } = usePublicConfig()
  const { data: balance } = useBalance()
  const t = useTranslations()
  return (
    <div className="space-y-2 px-4 pt-3 md:px-6 empty:hidden">
      {config?.maintenance_mode && (
        <Alert className="border-warn/40 bg-warn/10">
          <AlertDescription>{t("errors.MAINTENANCE")}</AlertDescription>
        </Alert>
      )}
      {config?.announcement && (
        <Alert className="border-primary/40 bg-primary/5">
          <AlertDescription>{String(config.announcement)}</AlertDescription>
        </Alert>
      )}
      {balance?.low_balance && (
        <Alert className="border-warn/40 bg-warn/10">
          <AlertDescription className="flex flex-wrap items-center gap-3">
            {t("credits.low")}
            <Button asChild size="sm" variant="outline">
              <Link href="/app/billing">{t("credits.buy")}</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

export function AppShell({ children, area = "app" }: { children: ReactNode; area?: "app" | "admin" }) {
  const t = useTranslations("nav")
  const { data: me } = useMe()
  const caps = new Set(me?.capabilities ?? [])
  const { connected } = useEventStream(!!me)
  const isStaff = !!me?.is_staff_user

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" variant="inset">
        <SidebarHeader className="px-3 py-3">
          <BrandMark href="/app" suffix={area === "admin" ? "ADMIN" : "DASH"} />
        </SidebarHeader>
        <SidebarContent>
          {area === "admin" ? (
            <SidebarGroup>
              <SidebarGroupLabel className="hud-eyebrow">{t("administration")}</SidebarGroupLabel>
              <SidebarGroupContent><NavMenu items={ADMIN_NAV} caps={caps} /></SidebarGroupContent>
            </SidebarGroup>
          ) : (
            APP_NAV.map((section) => (
              <SidebarGroup key={section.group}>
                <SidebarGroupLabel className="hud-eyebrow">{t(section.group)}</SidebarGroupLabel>
                <SidebarGroupContent><NavMenu items={section.items} caps={caps} /></SidebarGroupContent>
              </SidebarGroup>
            ))
          )}
          {isStaff && (
            <SidebarGroup className="mt-auto">
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild tooltip={area === "admin" ? t("backToApp") : t("admin")}>
                      <Link href={area === "admin" ? "/app" : "/admin"}>
                        {area === "admin" ? <LayoutDashboard aria-hidden /> : <ShieldCheck aria-hidden />}
                        <span>{area === "admin" ? t("backToApp") : t("admin")}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}
        </SidebarContent>
        <SidebarFooter>
          <SidebarMenu><SidebarMenuItem><UserMenu /></SidebarMenuItem></SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>
      <SidebarInset className="app-gradient min-h-screen">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border/70 bg-background/70 px-4 backdrop-blur-md md:px-6">
          <SidebarTrigger className="-ml-1" />
          <LiveIndicator connected={connected} />
          <div className="ml-auto flex items-center gap-1.5">
            <CreditMeter />
            <LocaleSwitcher signedIn compact />
            <ThemeToggle />
          </div>
        </header>
        <Banners />
        <main id="main" className="relative z-10 mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-6 md:py-8">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

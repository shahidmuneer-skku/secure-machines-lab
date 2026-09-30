"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Languages } from "lucide-react"
import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { useTransition } from "react"

import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger }
  from "@/components/ui/dropdown-menu"
import { LOCALE_COOKIE, LOCALE_LABELS, LOCALES, type Locale } from "@/i18n/config"
import { api } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"

export function setLocaleCookie(locale: Locale) {
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`
}

/** Switches UI language; persists to the cookie (all pages) and the profile (emails, reports). */
export function LocaleSwitcher({ signedIn = false, compact = false }: { signedIn?: boolean; compact?: boolean }) {
  const locale = useLocale() as Locale
  const t = useTranslations("common")
  const router = useRouter()
  const qc = useQueryClient()
  const [pending, start] = useTransition()
  const save = useMutation({
    mutationFn: async (value: Locale) => api.PATCH("/api/v1/me", { body: { locale: value } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me }),
  })
  const change = (value: string) => {
    const next = value as Locale
    setLocaleCookie(next)
    if (signedIn) save.mutate(next)
    start(() => router.refresh())
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={compact ? "icon" : "sm"} aria-label={t("language")} disabled={pending}>
          <Languages className="size-4" />
          {!compact && <span className="mono-label">{LOCALE_LABELS[locale].short}</span>}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuRadioGroup value={locale} onValueChange={change}>
          {LOCALES.map((l) => (
            <DropdownMenuRadioItem key={l} value={l}>
              {LOCALE_LABELS[l].native}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

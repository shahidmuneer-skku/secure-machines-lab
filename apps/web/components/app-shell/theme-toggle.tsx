"use client"

import { Moon, Sun } from "lucide-react"
import { useTranslations } from "next-intl"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const t = useTranslations("common")
  const dark = resolvedTheme !== "light"
  return (
    <Button variant="ghost" size="icon" aria-label={`${t("theme")}: ${dark ? t("dark") : t("light")}`}
      onClick={() => setTheme(dark ? "light" : "dark")}>
      {dark ? <Moon className="size-4" /> : <Sun className="size-4" />}
    </Button>
  )
}

export const LOCALES = ["en", "ko", "de"] as const
export type Locale = (typeof LOCALES)[number]
export const DEFAULT_LOCALE: Locale = "en"
export const LOCALE_COOKIE = "NEXT_LOCALE"

export const LOCALE_LABELS: Record<Locale, { short: string; native: string; htmlLang: string }> = {
  en: { short: "EN", native: "English", htmlLang: "en" },
  ko: { short: "KO", native: "한국어", htmlLang: "ko" },
  de: { short: "DE", native: "Deutsch", htmlLang: "de" },
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value)
}

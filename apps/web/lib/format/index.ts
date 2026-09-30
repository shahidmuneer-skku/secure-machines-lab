/** Locale-aware formatting helpers (all times are shown in the viewer's time zone). */

export function formatDateTime(value: string | null | undefined, locale: string): string {
  if (!value) return "—"
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

export function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return "—"
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value))
}

export function formatRelative(value: string | null | undefined, locale: string, now = Date.now()): string {
  if (!value) return "—"
  const diff = (new Date(value).getTime() - now) / 1000
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" })
  const abs = Math.abs(diff)
  if (abs < 60) return rtf.format(Math.round(diff), "second")
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute")
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour")
  return rtf.format(Math.round(diff / 86400), "day")
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let v = bytes
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—"
  const s = Math.round(seconds)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}

export function formatPercent(p: number | null | undefined, digits = 1): string {
  return p == null ? "—" : `${(p * 100).toFixed(digits)}%`
}

export function formatMoney(amount: number, currency: string, locale: string): string {
  const value = currency === "USD" ? amount / 100 : amount
  return new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: currency === "KRW" ? 0 : 2 })
    .format(value)
}

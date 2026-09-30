const CSRF_COOKIES = ["__Host-sml_csrftoken", "sml_csrftoken"]

export function readCsrfToken(): string {
  if (typeof document === "undefined") return ""
  for (const part of document.cookie.split(";")) {
    const [name, ...rest] = part.trim().split("=")
    if (CSRF_COOKIES.includes(name)) return decodeURIComponent(rest.join("="))
  }
  return ""
}

let priming: Promise<void> | null = null

/** Ensures the CSRF cookie exists (allauth's config endpoint sets it). */
export function ensureCsrf(): Promise<void> {
  if (readCsrfToken()) return Promise.resolve()
  priming ??= fetch("/api/_allauth/browser/v1/config", { credentials: "same-origin" }).then(() => undefined)
  return priming
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

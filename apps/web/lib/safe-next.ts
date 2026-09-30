/** Accept only same-origin relative paths for post-login redirects (prevents open redirects). */
export function safeNext(raw: string | null | undefined, fallback = "/app"): string {
  if (!raw) return fallback
  if (!raw.startsWith("/") || raw.startsWith("//") || /[\\\u0000-\u001f]/.test(raw)) return fallback
  try {
    const url = new URL(raw, "http://internal.invalid")
    if (url.origin !== "http://internal.invalid") return fallback
    return url.pathname + url.search + url.hash
  } catch {
    return fallback
  }
}

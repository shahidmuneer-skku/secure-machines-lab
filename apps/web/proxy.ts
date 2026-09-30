import { NextResponse, type NextRequest } from "next/server"

import { safeNext } from "@/lib/safe-next"

/**
 * Next.js Proxy (formerly "middleware"), runs before every page request:
 *  1. Request ID      — forwarded to Django via the /api rewrite for log correlation
 *  2. Auth redirects  — optimistic: /app and /admin need a session cookie; signed-in users skip /login
 *                       (Django is the real authority: every API call re-checks the session)
 *  3. Safe `next=`    — only same-origin relative paths are accepted (no open redirects)
 *  4. Locale cookie   — first visit gets NEXT_LOCALE from Accept-Language (shared with Django)
 *  5. CSP             — per-request nonce; inline scripts without it are blocked
 */

const SESSION_COOKIES = ["sml_session", "__Host-sml_session"]
const PROTECTED = ["/app", "/admin"]
const AUTH_PAGES = ["/login", "/signup"]
const LOCALE_COOKIE = "NEXT_LOCALE"
const LOCALES = ["en", "ko", "de"]

function matches(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}

function csp(nonce: string): string {
  const isDev = process.env.NODE_ENV === "development"
  const storage = process.env.NEXT_PUBLIC_STORAGE_ORIGIN ? ` ${process.env.NEXT_PUBLIC_STORAGE_ORIGIN}` : ""
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    // Inline style *attributes* (Radix, Recharts, homepage) cannot carry nonces.
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' blob: data:${storage}`,
    `media-src 'self' blob:${storage}`,
    "font-src 'self' data:",
    `connect-src 'self'${storage} https://api.tosspayments.com https://*.tosspayments.com https://challenges.cloudflare.com`,
    "frame-src https://*.tosspayments.com https://checkout.stripe.com https://challenges.cloudflare.com",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self' https://*.tosspayments.com https://checkout.stripe.com",
    "frame-ancestors 'none'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ")
}

function preferredLocale(request: NextRequest): string | null {
  if (request.cookies.has(LOCALE_COOKIE)) return null
  const accept = request.headers.get("accept-language")?.toLowerCase() ?? ""
  return LOCALES.find((l) => accept.startsWith(l)) ?? "en"
}

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const hasSession = SESSION_COOKIES.some((c) => request.cookies.has(c))

  if (matches(pathname, PROTECTED) && !hasSession) {
    const login = request.nextUrl.clone()
    login.pathname = "/login"
    login.search = `?next=${encodeURIComponent(safeNext(pathname + search))}`
    return NextResponse.redirect(login)
  }
  if (matches(pathname, AUTH_PAGES) && hasSession && !request.nextUrl.searchParams.has("reauth")) {
    const target = request.nextUrl.clone()
    const next = safeNext(request.nextUrl.searchParams.get("next"))
    const [path, query = ""] = next.split("?")
    target.pathname = path
    target.search = query ? `?${query}` : ""
    return NextResponse.redirect(target)
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64")
  const requestId = request.headers.get("x-request-id") ?? crypto.randomUUID().replaceAll("-", "")
  const policy = csp(nonce)
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set("x-nonce", nonce)
  requestHeaders.set("x-request-id", requestId)
  requestHeaders.set("Content-Security-Policy", policy)

  const response = NextResponse.next({ request: { headers: requestHeaders } })
  response.headers.set("Content-Security-Policy", policy)
  response.headers.set("X-Request-ID", requestId)
  const locale = preferredLocale(request)
  if (locale) {
    response.cookies.set(LOCALE_COOKIE, locale, { path: "/", sameSite: "lax", maxAge: 60 * 60 * 24 * 365 })
  }
  return response
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|images|favicon.ico|icon|robots.txt|sitemap.xml).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
}

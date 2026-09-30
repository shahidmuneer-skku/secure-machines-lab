import type { NextConfig } from "next"
import createNextIntlPlugin from "next-intl/plugin"

const withNextIntl = createNextIntlPlugin("./i18n/request.ts")

// In development Next proxies /api/* to Django so cookies stay same-origin.
// In production nginx routes /api/* to Django directly (deploy/nginx).
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000"

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Django URLs end in '/' (the /api rewrite must keep it); proxy.ts strips it for app pages instead.
  skipTrailingSlashRedirect: true,
  experimental: {
    // Next buffers request bodies it proxies (10 MB by default), which truncated video uploads to
    // /api in development. Match nginx: browser uploads up to 200 MB go through /api/v1/uploads,
    // larger videos go straight to object storage in parts.
    proxyClientMaxBodySize: "250mb",
  },
  reactStrictMode: true,
  typedRoutes: false,
  async rewrites() {
    return [
      // `:path*` drops a trailing slash, which Django URLs need (the admin would redirect-loop).
      { source: "/api/:path*/", destination: `${API_ORIGIN}/api/:path*/` },
      { source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` },
    ]
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(self)" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
        ],
      },
    ]
  },
}

export default withNextIntl(nextConfig)

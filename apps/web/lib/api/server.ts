import "server-only"

import { cookies } from "next/headers"
import createClient from "openapi-fetch"

import type { paths } from "@contracts/schema"

/** Server-side client for public endpoints (Server Components). Talks to Django directly. */
export const serverApi = createClient<paths>({ baseUrl: process.env.API_ORIGIN ?? "http://127.0.0.1:8000" })

/**
 * The signed-in user as the API sees them, asked with the browser's session cookie. For pages that
 * must send staff-only content (the admin console, its texts) to staff and to no one else.
 * Null when nobody is signed in.
 */
export async function serverMe() {
  const cookie = (await cookies()).toString()
  if (!cookie) return null
  const { data, response } = await serverApi.GET("/api/v1/me", { headers: { cookie }, cache: "no-store" })
  if (response.status === 401 || response.status === 403) return null
  if (!data) throw new Error(`Could not read the session (HTTP ${response.status})`)
  return data
}

import "server-only"

import createClient from "openapi-fetch"

import type { paths } from "@contracts/schema"

/** Server-side client for public endpoints (Server Components). Talks to Django directly. */
export const serverApi = createClient<paths>({ baseUrl: process.env.API_ORIGIN ?? "http://127.0.0.1:8000" })

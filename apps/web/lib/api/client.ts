/**
 * Typed API client generated from the Django OpenAPI schema
 * (packages/contracts, `npm run gen:api`). No hand-written URLs.
 */
import createClient, { type Middleware } from "openapi-fetch"

import type { paths } from "@contracts/schema"

import { ensureCsrf, readCsrfToken } from "./csrf"
import { ApiError, problemFromResponse } from "./errors"

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"])

const csrfMiddleware: Middleware = {
  async onRequest({ request }) {
    if (UNSAFE.has(request.method)) {
      await ensureCsrf()
      request.headers.set("X-CSRFToken", readCsrfToken())
    }
    return request
  },
}

const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (!response.ok) {
      throw new ApiError(await problemFromResponse(response))
    }
    return response
  },
}

export const api = createClient<paths>({ baseUrl: "", credentials: "same-origin" })
api.use(csrfMiddleware, errorMiddleware)

/** Unwraps an openapi-fetch result (errors are already thrown by the middleware). */
export function data<T>(result: { data?: T }): T {
  return result.data as T
}

export type Paths = paths
export type Schemas = import("@contracts/schema").components["schemas"]

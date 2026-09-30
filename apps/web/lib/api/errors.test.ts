import { describe, expect, it } from "vitest"

import { ApiError, problemFromResponse } from "./errors"

describe("ApiError", () => {
  it("exposes problem details and field errors", () => {
    const err = new ApiError({
      status: 400, code: "VALIDATION_ERROR", detail: "One or more fields are invalid.", request_id: "abc",
      errors: [{ field: "name", message: "This field is required." }],
    })
    expect(err.code).toBe("VALIDATION_ERROR")
    expect(err.fieldErrors).toEqual({ name: "This field is required." })
    expect(err.requestId).toBe("abc")
    expect(err.isAuth).toBe(false)
  })

  it("reads problem+json bodies and tolerates non-JSON", async () => {
    const json = new Response(JSON.stringify({ code: "INSUFFICIENT_CREDITS", required: 10, balance: 2 }), {
      status: 402, headers: { "Content-Type": "application/problem+json" },
    })
    expect(await problemFromResponse(json)).toMatchObject({ status: 402, code: "INSUFFICIENT_CREDITS", required: 10 })
    const html = new Response("<html>bad gateway</html>", { status: 502, statusText: "Bad Gateway" })
    expect(await problemFromResponse(html)).toEqual({ status: 502, title: "Bad Gateway" })
  })
})

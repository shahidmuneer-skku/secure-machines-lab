import type { components } from "@contracts/schema"

import { ensureCsrf, readCsrfToken } from "./api/csrf"
import { ApiError, problemFromResponse } from "./api/errors"

type Schemas = components["schemas"]
export type Conversation = Schemas["Conversation"]
export type ConversationDetail = Schemas["ConversationDetail"]
export type ChatMessage = Schemas["Message"]

export const CONVERSATIONS_URL = "/api/v1/assistant/conversations"

export interface StreamHandlers {
  meta?: (data: { conversation?: Conversation; user_message?: ChatMessage; results_for?: string }) => void
  delta: (text: string) => void
  done: (message: ChatMessage) => void
  error: (detail: string, code: string) => void
}

/**
 * POSTs to an assistant endpoint and reads its Server-Sent Events as they arrive (EventSource only does
 * GET). Problems before the stream starts (e.g. not enough credits) throw an ApiError like any API call.
 */
export async function streamChat(url: string, body: unknown, on: StreamHandlers, signal?: AbortSignal): Promise<void> {
  await ensureCsrf()
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", "X-CSRFToken": readCsrfToken() },
    body: JSON.stringify(body ?? {}),
    signal,
  })
  if (!res.ok || !res.body) throw new ApiError(await problemFromResponse(res))
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let end: number
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = "message"
      let data = ""
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7)
        else if (line.startsWith("data: ")) data += line.slice(6)
      }
      if (!data) continue
      const payload = JSON.parse(data)
      if (event === "meta") on.meta?.(payload)
      else if (event === "delta") on.delta(payload.text ?? "")
      else if (event === "done") on.done(payload.message)
      else if (event === "error") on.error(payload.detail ?? "", payload.code ?? "ERROR")
    }
  }
}

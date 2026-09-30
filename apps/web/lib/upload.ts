/**
 * Browser uploads with real progress (XHR) and client-side validation.
 * Small files: multipart POST /api/v1/uploads. Large videos: resumable
 * multipart upload straight to object storage via presigned part URLs.
 */
import { ensureCsrf, readCsrfToken } from "@/lib/api/csrf"
import { ApiError, type ProblemDetails } from "@/lib/api/errors"
import type { MediaObject } from "@/lib/api/types"

export const IMAGE_EXT = ["jpg", "jpeg", "png", "webp", "bmp", "avif"]
export const VIDEO_EXT = ["mp4", "webm", "mov", "avi", "mkv", "gif"]
export const MAX_IMAGE_BYTES = 50 * 1024 * 1024
export const MAX_VIDEO_BYTES = 4 * 1024 * 1024 * 1024
const MULTIPART_THRESHOLD = 200 * 1024 * 1024

export type MediaKind = "image" | "video"

export function detectKind(file: File): MediaKind | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? ""
  if (file.type.startsWith("image/") && file.type !== "image/gif") return "image"
  if (file.type.startsWith("video/") || file.type === "image/gif") return "video"
  if (IMAGE_EXT.includes(ext)) return "image"
  if (VIDEO_EXT.includes(ext)) return "video"
  return null
}

export type ValidationIssue = "type" | "size"

export function validateFile(file: File): ValidationIssue | null {
  const kind = detectKind(file)
  if (!kind) return "type"
  if (file.size > (kind === "image" ? MAX_IMAGE_BYTES : MAX_VIDEO_BYTES)) return "size"
  return null
}

function xhr(method: string, url: string, body: XMLHttpRequestBodyInit, opts: {
  headers?: Record<string, string>
  onProgress?: (loaded: number) => void
  signal?: AbortSignal
}): Promise<{ status: number; body: string; etag: string | null }> {
  return new Promise((resolve, reject) => {
    const req = new XMLHttpRequest()
    req.open(method, url)
    req.withCredentials = url.startsWith("/")
    for (const [k, v] of Object.entries(opts.headers ?? {})) req.setRequestHeader(k, v)
    req.upload.onprogress = (e) => opts.onProgress?.(e.loaded)
    req.onload = () => resolve({ status: req.status, body: req.responseText, etag: req.getResponseHeader("ETag") })
    req.onerror = () => reject(new ApiError({ status: 0, code: "NETWORK", title: "Network error" }))
    req.onabort = () => reject(new DOMException("Upload canceled", "AbortError"))
    opts.signal?.addEventListener("abort", () => req.abort())
    req.send(body)
  })
}

function parseProblem(status: number, body: string): ProblemDetails {
  try {
    return { status, ...JSON.parse(body) }
  } catch {
    return { status, title: "Upload failed" }
  }
}

async function readHeadBase64(file: File): Promise<string> {
  const buf = new Uint8Array(await file.slice(0, 4096).arrayBuffer())
  let bin = ""
  for (const b of buf) bin += String.fromCharCode(b)
  return btoa(bin)
}

export async function uploadFile(file: File, onProgress: (fraction: number) => void,
  signal?: AbortSignal): Promise<MediaObject> {
  await ensureCsrf()
  const csrf = { "X-CSRFToken": readCsrfToken() }
  if (detectKind(file) === "video" && file.size > MULTIPART_THRESHOLD) {
    const start = await xhr("POST", "/api/v1/uploads/multipart", JSON.stringify({
      file_name: file.name, size_bytes: file.size, head_base64: await readHeadBase64(file),
    }), { headers: { ...csrf, "Content-Type": "application/json" }, signal })
    // Fall back to a direct upload when object storage isn't configured.
    if (start.status < 300) {
      const { media_id, part_size, part_urls } = JSON.parse(start.body) as {
        media_id: string; part_size: number; part_urls: string[] }
      const done: number[] = new Array(part_urls.length).fill(0)
      const parts: { part_number: number; etag: string }[] = []
      for (let i = 0; i < part_urls.length; i++) {
        const chunk = file.slice(i * part_size, Math.min(file.size, (i + 1) * part_size))
        let attempt = 0
        for (;;) {
          try {
            const res = await xhr("PUT", part_urls[i], chunk, {
              signal, onProgress: (loaded) => { done[i] = loaded; onProgress(done.reduce((a, b) => a + b, 0) / file.size) },
            })
            if (res.status >= 300 || !res.etag) throw new Error(`part ${i + 1} failed (${res.status})`)
            parts.push({ part_number: i + 1, etag: res.etag })
            break
          } catch (e) {
            if ((e as Error).name === "AbortError" || ++attempt >= 3) throw e
          }
        }
      }
      const complete = await xhr("POST", `/api/v1/uploads/${media_id}/complete`, JSON.stringify({ parts }),
        { headers: { ...csrf, "Content-Type": "application/json" }, signal })
      if (complete.status >= 300) throw new ApiError(parseProblem(complete.status, complete.body))
      onProgress(1)
      return JSON.parse(complete.body) as MediaObject
    }
  }
  const form = new FormData()
  form.append("file", file, file.name)
  const res = await xhr("POST", "/api/v1/uploads", form, {
    headers: csrf, signal, onProgress: (loaded) => onProgress(Math.min(0.99, loaded / file.size)),
  })
  if (res.status >= 300) throw new ApiError(parseProblem(res.status, res.body))
  onProgress(1)
  return JSON.parse(res.body) as MediaObject
}

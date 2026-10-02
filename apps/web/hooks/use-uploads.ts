"use client"

import { useCallback, useRef, useState } from "react"

import { isApiError } from "@/lib/api/errors"
import type { MediaObject } from "@/lib/api/types"
import { detectKind, uploadFile, validateFile, type MediaKind, type ValidationIssue } from "@/lib/upload"

export interface UploadItem {
  key: string
  file: File
  kind: MediaKind | null
  previewUrl: string | null
  progress: number
  state: "invalid" | "uploading" | "ready" | "error"
  issue?: ValidationIssue
  error?: string
  media?: MediaObject
}

/** Manages a list of files: validation, previews, concurrent uploads with progress, retry and removal. */
export function useUploads(concurrency = 3) {
  const [items, setItems] = useState<UploadItem[]>([])
  const controllers = useRef(new Map<string, AbortController>())

  const patch = useCallback((key: string, update: Partial<UploadItem>) => {
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...update } : it)))
  }, [])

  const start = useCallback(async (item: UploadItem) => {
    const controller = new AbortController()
    controllers.current.set(item.key, controller)
    patch(item.key, { state: "uploading", progress: 0, error: undefined })
    try {
      const media = await uploadFile(item.file, (p) => patch(item.key, { progress: p }), controller.signal)
      patch(item.key, { state: "ready", progress: 1, media })
    } catch (e) {
      if ((e as Error).name === "AbortError") return
      patch(item.key, { state: "error", error: isApiError(e) ? e.detail || e.code : (e as Error).message })
    } finally {
      controllers.current.delete(item.key)
    }
  }, [patch])

  const add = useCallback((files: File[]) => {
    const created: UploadItem[] = files.map((file) => {
      const issue = validateFile(file)
      const kind = detectKind(file)
      return {
        key: `${file.name}-${file.size}-${crypto.randomUUID()}`, file, kind,
        previewUrl: kind === "image" || kind === "video" ? URL.createObjectURL(file) : null,
        progress: 0, state: issue ? "invalid" : "uploading", issue: issue ?? undefined,
      }
    })
    setItems((prev) => [...prev, ...created])
    const queue = created.filter((c) => c.state !== "invalid")
    let index = 0
    const worker = async () => {
      while (index < queue.length) {
        const next = queue[index++]
        await start(next)
      }
    }
    void Promise.all(Array.from({ length: Math.min(concurrency, queue.length) }, worker))
  }, [concurrency, start])

  const remove = useCallback((key: string) => {
    controllers.current.get(key)?.abort()
    setItems((prev) => {
      const item = prev.find((i) => i.key === key)
      if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl)
      return prev.filter((i) => i.key !== key)
    })
  }, [])

  const retry = useCallback((key: string) => {
    const item = items.find((i) => i.key === key)
    if (item) void start(item)
  }, [items, start])

  const clear = useCallback(() => {
    controllers.current.forEach((c) => c.abort())
    setItems((prev) => {
      prev.forEach((i) => i.previewUrl && URL.revokeObjectURL(i.previewUrl))
      return []
    })
  }, [])

  /** Hands the files over (previews kept, for the caller to release) and empties the list; `restore` puts them back. */
  const take = useCallback((): UploadItem[] => {
    const taken = items
    setItems([])
    return taken
  }, [items])

  const restore = useCallback((taken: UploadItem[]) => setItems((prev) => [...taken, ...prev]), [])

  const ready = items.filter((i) => i.state === "ready" && i.media)
  const busy = items.some((i) => i.state === "uploading")
  return { items, add, remove, retry, clear, take, restore, ready, busy }
}

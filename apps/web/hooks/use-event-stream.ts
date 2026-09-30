"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useEffectEvent, useState } from "react"

import { qk } from "@/lib/api/keys"

type Handler = (type: string, data: Record<string, unknown>) => void

const EVENTS = [
  "job.updated", "job.event", "task.progress", "task.log", "task.interval", "credits.updated", "report.updated",
  "explanation.updated", "billing.payment",
]

/**
 * One SSE connection per tab (GET /api/v1/events/stream). Patches TanStack Query
 * caches in place so lists and detail pages update without refetch storms.
 * Falls back to polling (via `connected=false`) when the stream is unavailable.
 */
export function useEventStream(enabled: boolean, onEvent?: Handler) {
  const qc = useQueryClient()
  const [connected, setConnected] = useState(false)
  // Always calls the latest `onEvent` without reconnecting the stream when it changes.
  const emit = useEffectEvent((name: string, data: Record<string, unknown>) => onEvent?.(name, data))

  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return
    let source: EventSource | null = null
    let retry = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    let closed = false

    const connect = () => {
      source = new EventSource("/api/v1/events/stream", { withCredentials: true })
      source.addEventListener("ready", () => {
        retry = 0
        setConnected(true)
      })
      for (const name of EVENTS) {
        source.addEventListener(name, (ev) => {
          let payload: { data?: Record<string, unknown> } = {}
          try {
            payload = JSON.parse((ev as MessageEvent).data)
          } catch {
            return
          }
          const data = payload.data ?? {}
          apply(name, data)
          emit(name, data)
        })
      }
      source.onerror = () => {
        setConnected(false)
        source?.close()
        if (closed) return
        retry = Math.min(retry + 1, 6)
        timer = setTimeout(connect, 1000 * 2 ** retry)
      }
    }

    const apply = (name: string, data: Record<string, unknown>) => {
      const jobId = data.job_id as string | undefined
      switch (name) {
        case "job.updated":
          qc.invalidateQueries({ queryKey: ["jobs", "list"] })
          if (jobId) qc.invalidateQueries({ queryKey: qk.job(jobId) })
          qc.invalidateQueries({ queryKey: ["dashboard"] })
          break
        case "job.event":
          if (jobId) qc.invalidateQueries({ queryKey: qk.job(jobId) })
          break
        case "task.progress":
        case "task.log":
          if (jobId) {
            qc.setQueryData(["jobs", "live", jobId], (prev: Record<string, unknown> | undefined) => ({
              ...(prev ?? {}),
              [data.task_id as string]: {
                ...((prev ?? {})[data.task_id as string] as object),
                ...(name === "task.progress" ? { progress: data.progress, message: data.message } : {}),
                ...(name === "task.log" ? { lastLog: data.message } : {}),
                at: Date.now(),
              },
            }))
          }
          break
        case "task.interval":
          if (jobId) {
            qc.setQueryData(["jobs", "intervals", jobId], (prev: unknown[] | undefined) => [
              ...(prev ?? []),
              data.interval,
            ])
          }
          break
        case "credits.updated":
          qc.setQueryData(qk.balance, (prev: object | undefined) => (prev ? { ...prev, balance: data.balance } : prev))
          qc.invalidateQueries({ queryKey: qk.balance })
          break
        case "report.updated":
          qc.invalidateQueries({ queryKey: ["reports"] })
          if (jobId) qc.invalidateQueries({ queryKey: qk.job(jobId) })
          break
        case "explanation.updated":
          if (jobId) qc.invalidateQueries({ queryKey: qk.job(jobId) })
          break
        case "billing.payment":
          qc.invalidateQueries({ queryKey: ["billing"] })
          qc.invalidateQueries({ queryKey: qk.balance })
          break
      }
    }

    connect()
    return () => {
      closed = true
      if (timer) clearTimeout(timer)
      source?.close()
      setConnected(false)
    }
  }, [enabled, qc])

  return { connected }
}

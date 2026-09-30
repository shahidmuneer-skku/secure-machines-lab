"use client"

import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"

import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"

export type StreamPhase = "idle" | "paying" | "connecting" | "uploading" | "queued" | "analyzing" | "finished" | "error"

export interface StreamInterval {
  index: number
  start_sec: number
  end_sec: number
  fake_probability: number
}

export interface StreamSettings {
  modelId: string
  startSec: number
  endSec: number | null
  intervalSec: number
  wholeVideo: boolean
  faceCrop: boolean | null
  locale: string
}

export interface StreamResult {
  status: "done" | "stopped" | "error"
  average: number
  analysedSeconds: number
  jobId: string | null
  creditsCharged: number | null
}

type ServerEvent =
  | { type: "ready"; chunk_size: number; size: number }
  | { type: "uploaded"; bytes: number }
  | { type: "queued"; position: number }
  | { type: "meta"; num_intervals?: number }
  | ({ type: "interval" } & StreamInterval)
  | { type: "done" }
  | { type: "error"; message: string }
  | { type: "finished"; status: StreamResult["status"]; average: number; analysed_seconds: number; job_id?: string
      credits_charged?: number }

/** Relative URLs (production: "/stream/ws" behind nginx) resolve against the page's origin. */
function socketUrl(url: string): string {
  if (/^wss?:\/\//.test(url)) return url
  const scheme = window.location.protocol === "https:" ? "wss" : "ws"
  return `${scheme}://${window.location.host}${url.startsWith("/") ? url : `/${url}`}`
}

/**
 * Streams a local video file to the long-form stream service and follows the analysis live.
 * The file goes chunk by chunk over one WebSocket; each chunk waits for the server's
 * acknowledgement, which gives backpressure and an honest progress bar.
 */
export function useLongVideoStream() {
  const qc = useQueryClient()
  const [phase, setPhase] = useState<StreamPhase>("idle")
  const [uploaded, setUploaded] = useState(0)
  const [queuePosition, setQueuePosition] = useState<number | null>(null)
  const [expected, setExpected] = useState<number | null>(null)
  const [intervals, setIntervals] = useState<StreamInterval[]>([])
  const [result, setResult] = useState<StreamResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const socket = useRef<WebSocket | null>(null)
  const ack = useRef<((bytes: number) => void) | null>(null)
  const stopped = useRef(false)

  useEffect(() => () => socket.current?.close(), [])

  const reset = useCallback(() => {
    socket.current?.close()
    socket.current = null
    stopped.current = false
    setPhase("idle"); setUploaded(0); setQueuePosition(null); setExpected(null)
    setIntervals([]); setResult(null); setError(null); setJobId(null); setStartedAt(null)
  }, [])

  const start = useCallback(async (file: File, durationSec: number, settings: StreamSettings) => {
    reset()
    setPhase("paying")
    let session
    try {
      session = data(await api.POST("/api/v1/long-video/sessions", {
        body: {
          model_id: settings.modelId, file_name: file.name, file_size: file.size, duration_seconds: durationSec,
          start_seconds: settings.startSec, end_seconds: settings.endSec, interval_seconds: settings.intervalSec,
          whole_video: settings.wholeVideo, face_crop: settings.faceCrop, locale: settings.locale as "en",
        },
      }))
    } catch (e) {
      setPhase("error")
      setError(isApiError(e) ? e.detail : String(e))
      return
    }
    setJobId(session.job_id)
    qc.invalidateQueries({ queryKey: qk.balance })
    setPhase("connecting")

    const ws = new WebSocket(socketUrl(session.ws_url))
    ws.binaryType = "arraybuffer"
    socket.current = ws

    const sendFile = async (chunkSize: number) => {
      setPhase("uploading")
      for (let offset = 0; offset < file.size; offset += chunkSize) {
        if (stopped.current || ws.readyState !== WebSocket.OPEN) return
        const buffer = await file.slice(offset, offset + chunkSize).arrayBuffer()
        const acknowledged = new Promise<number>((resolve) => { ack.current = resolve })
        ws.send(buffer)
        await acknowledged
      }
      if (!stopped.current && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: "upload_done" }))
        setPhase("queued")
      }
    }

    ws.onopen = () => ws.send(JSON.stringify({ action: "auth", token: session.token }))
    ws.onmessage = (message) => {
      let event: ServerEvent
      try {
        event = JSON.parse(String(message.data))
      } catch {
        return
      }
      switch (event.type) {
        case "ready":
          void sendFile(event.chunk_size)
          break
        case "uploaded":
          setUploaded(event.bytes)
          ack.current?.(event.bytes)
          break
        case "queued":
          setPhase("queued")
          setQueuePosition(event.position)
          break
        case "meta":
          setPhase("analyzing")
          setQueuePosition(null)
          setStartedAt(Date.now())
          if (event.num_intervals) setExpected(event.num_intervals)
          break
        case "interval":
          setPhase("analyzing")
          setIntervals((prev) => [...prev.filter((i) => i.index !== event.index), {
            index: event.index, start_sec: event.start_sec, end_sec: event.end_sec,
            fake_probability: event.fake_probability,
          }].sort((a, b) => a.index - b.index))
          break
        case "error":
          setError(event.message)
          break
        case "finished":
          setResult({ status: event.status, average: event.average, analysedSeconds: event.analysed_seconds,
            jobId: event.job_id ?? session.job_id, creditsCharged: event.credits_charged ?? null })
          setPhase(event.status === "error" ? "error" : "finished")
          qc.invalidateQueries({ queryKey: qk.balance })
          qc.invalidateQueries({ queryKey: ["jobs"] })
          break
      }
    }
    ws.onerror = () => setError((prev) => prev ?? "The connection to the stream service failed.")
    ws.onclose = () => {
      ack.current?.(-1)
      setPhase((p) => (p === "finished" || p === "error" ? p : "error"))
    }
  }, [qc, reset])

  const stop = useCallback(() => {
    stopped.current = true
    const ws = socket.current
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ action: "stop" }))
    ack.current?.(-1)
  }, [])

  return { phase, uploaded, queuePosition, expected, intervals, result, error, jobId, startedAt, start, stop, reset }
}

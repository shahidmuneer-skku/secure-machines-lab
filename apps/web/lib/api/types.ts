import type { Schemas } from "./client"

export type Job = Schemas["JobList"]
export type JobDetail = Schemas["JobDetail"]
export type JobStatus = Job["status"]
export type Verdict = NonNullable<Job["verdict"]>
export type MediaObject = Schemas["Media"]
export type ApiKey = Schemas["ApiKey"]
export type ApiKeyCreated = Schemas["ApiKeyCreated"]
export type LedgerEntry = Schemas["LedgerEntry"]
export type Balance = Schemas["Balance"]
export type Report = Schemas["Report"]
export type Payment = Schemas["Payment"]
export type Subscription = Schemas["Subscription"]
export type CreditPack = Schemas["CreditPack"]
export type Plan = Schemas["Plan"]
export type Me = Schemas["Me"]
export type Explanation = Schemas["Explanation"]

export interface LiveTask {
  progress: number
  message: string
  updated_at?: string
}

export interface TaskView {
  id: string
  kind: "model" | "audit" | "long_video" | "news"
  target: string
  name: string
  status: "pending" | "dispatched" | "running" | "succeeded" | "failed" | "canceled" | "skipped"
  status_label: string
  attempt: number
  progress: number
  stage_message: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  gpu: string
  error_code: string
  error_message: string
  live: LiveTask | null
  queue_info: { position: number; consumers: number; eta_seconds: number; workers_online: boolean } | null
  result: {
    fake_prob?: number | null
    no_face?: boolean
    simulated?: boolean
    faces?: { score?: number; fake_prob?: number; bbox?: number[] }[]
    per_frame?: { frame: string; fake_prob: number }[]
    intervals?: { index: number; start_sec: number; end_sec: number; fake_prob: number }[]
    fallback?: { model: string; reason: string } | null
    summary?: string
    ai_indicators?: AiIndicators
    data?: Record<string, unknown>
    report_markdown?: string
    meta?: Record<string, unknown>
  }
}

export interface AiIndicators {
  ai_generated: boolean
  confidence: "strong" | "weak" | "none"
  evidence: { source: string; strength: "strong" | "weak"; detail: string }[]
  camera?: string | null
  software?: string | null
  c2pa_status?: string
  notes?: string[]
  fields?: Record<string, string>
}

export interface TimelineEvent {
  id: number
  created_at: string
  level: "info" | "success" | "warning" | "error"
  code: string
  message: string
  task: string | null
  data: Record<string, unknown>
}

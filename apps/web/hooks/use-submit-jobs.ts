"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { toast } from "sonner"

import { api, data } from "@/lib/api/client"
import { newIdempotencyKey } from "@/lib/api/csrf"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { Job, MediaObject } from "@/lib/api/types"

export interface CatalogModel {
  id: string
  media: ("image" | "video")[]
}

export interface SubmitRequest {
  media: MediaObject[]
  models: string[]
  catalog: CatalogModel[]
  auditSteps: ("face" | "safety" | "fas")[]
  module?: "detect" | "long_video"
  options?: Record<string, unknown>
  batchName?: string
}

/** Splits media by type so each group only gets models that support it. */
export function groupRequests(req: SubmitRequest) {
  const groups: { mediaType: "image" | "video"; ids: string[]; models: string[] }[] = []
  for (const mediaType of ["image", "video"] as const) {
    const ids = req.media.filter((m) => m.media_type === mediaType).map((m) => m.id)
    if (!ids.length) continue
    const supported = new Set(req.catalog.filter((c) => c.media.includes(mediaType)).map((c) => c.id))
    groups.push({ mediaType, ids, models: req.module === "long_video" ? req.models
      : req.models.filter((m) => supported.has(m)) })
  }
  return groups
}

function body(req: SubmitRequest, group: ReturnType<typeof groupRequests>[number]) {
  return {
    ...(group.ids.length === 1 ? { media_id: group.ids[0] } : { media_ids: group.ids }),
    module: req.module ?? "detect",
    models: group.models,
    audit_steps: req.auditSteps,
    options: req.options ?? {},
    batch_name: req.batchName,
  }
}

export async function quoteRequest(req: SubmitRequest) {
  let credits = 0
  let balance = 0
  let affordable = true
  const lines: { label: string; credits: number }[] = []
  for (const group of groupRequests(req)) {
    const q = data(await api.POST("/api/v1/jobs/quote", { body: body(req, group) as never }))
    credits += q.credits
    balance = q.balance
    affordable = affordable && q.affordable
    lines.push(...(q.lines as { label: string; credits: number }[]))
  }
  return { credits, balance, affordable: affordable && balance >= credits, lines }
}

export function useSubmitJobs() {
  const qc = useQueryClient()
  const router = useRouter()
  const t = useTranslations("detect")
  return useMutation({
    mutationFn: async (req: SubmitRequest) => {
      const jobs: Job[] = []
      for (const group of groupRequests(req)) {
        const res = data(await api.POST("/api/v1/jobs", {
          body: body(req, group) as never,
          headers: { "Idempotency-Key": newIdempotencyKey() },
        }))
        jobs.push(...res.jobs)
      }
      return jobs
    },
    onSuccess: (jobs) => {
      qc.invalidateQueries({ queryKey: qk.jobsAll })
      qc.invalidateQueries({ queryKey: qk.balance })
      const first = jobs[0]
      toast.success(t("queuedToast", { count: jobs.length }), {
        description: t("queuedToastHint"),
        action: { label: t("track"), onClick: () => router.push(jobs.length === 1 ? `/app/results/${first.id}` : "/app/results") },
      })
    },
    onError: (e) => {
      if (isApiError(e) && e.code === "INSUFFICIENT_CREDITS") {
        toast.error(t("insufficient"), {
          description: e.detail,
          action: { label: t("buyCredits"), onClick: () => router.push("/app/billing") },
        })
      } else {
        toast.error(t("submitFailed"), { description: isApiError(e) ? e.detail : undefined })
      }
    },
  })
}

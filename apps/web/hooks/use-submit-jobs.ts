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

/** What the user submits: files only. The administrator decides what runs on each media type. */
export interface SubmitRequest {
  media: MediaObject[]
  module?: "detect" | "long_video"
  options?: Record<string, unknown>
  batchName?: string
}

function body(req: SubmitRequest) {
  const ids = req.media.map((m) => m.id)
  return {
    ...(ids.length === 1 ? { media_id: ids[0] } : { media_ids: ids }),
    module: req.module ?? "detect",
    options: req.options ?? {},
    batch_name: req.batchName,
  }
}

export async function quoteRequest(req: SubmitRequest) {
  const q = data(await api.POST("/api/v1/jobs/quote", { body: body(req) as never }))
  return { credits: q.credits, balance: q.balance, affordable: q.affordable, lines: q.lines as { label: string; credits: number }[] }
}

export function useSubmitJobs() {
  const qc = useQueryClient()
  const router = useRouter()
  const t = useTranslations("detect")
  return useMutation({
    mutationFn: async (req: SubmitRequest): Promise<Job[]> => data(await api.POST("/api/v1/jobs", {
      body: body(req) as never,
      params: { header: { "Idempotency-Key": newIdempotencyKey() } },
    })).jobs,
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

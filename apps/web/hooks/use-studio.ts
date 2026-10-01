"use client"

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, data } from "@/lib/api/client"
import { newIdempotencyKey } from "@/lib/api/csrf"
import { qk } from "@/lib/api/keys"
import type { Schemas } from "@/lib/api/client"
import type { StudioJob } from "@/lib/api/types"

export type StudioRequest = Schemas["StudioJobCreateRequest"]

export const isActive = (job: Pick<StudioJob, "status"> | undefined) =>
  job?.status === "queued" || job?.status === "running"

function cursorOf(next: string | null | undefined): string | undefined {
  if (!next) return undefined
  return new URL(next, "http://x").searchParams.get("cursor") ?? undefined
}

/** What the studio offers right now: per mode, the controls of the admin's model and its price. */
export function useStudioConfig() {
  return useQuery({ queryKey: qk.studioConfig, queryFn: async () => data(await api.GET("/api/v1/studio/config")),
    staleTime: 30_000 })
}

export function useStudioHistory() {
  return useInfiniteQuery({
    queryKey: qk.studioJobs,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => data(await api.GET("/api/v1/studio/jobs", {
      params: { query: { cursor: pageParam, limit: 24 } as never },
    })),
    getNextPageParam: (last) => cursorOf(last.next),
    // The event stream refreshes it; this is the fallback while something is running.
    refetchInterval: (q) => q.state.data?.pages.some((p) => p.results.some(isActive)) ? 10_000 : false,
  })
}

export function useStudioJob(id: string | null) {
  return useQuery({
    queryKey: qk.studioJob(id ?? "none"),
    queryFn: async () => data(await api.GET("/api/v1/studio/jobs/{id}", { params: { path: { id: id! } } })),
    enabled: !!id,
    refetchInterval: (q) => isActive(q.state.data) ? 2_500 : false,
  })
}

export function useSubmitStudio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: StudioRequest) => data(await api.POST("/api/v1/studio/jobs", {
      body, params: { header: { "Idempotency-Key": newIdempotencyKey() } },
    })),
    onSuccess: (job) => {
      qc.setQueryData(qk.studioJob(job.id), job)
      qc.invalidateQueries({ queryKey: qk.studioJobs })
      qc.invalidateQueries({ queryKey: qk.balance })
    },
  })
}

export function useCancelStudio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => data(await api.POST("/api/v1/jobs/{id}/cancel", { params: { path: { id } } })),
    onSuccess: (_job, id) => {
      qc.invalidateQueries({ queryKey: qk.studioJob(id) })
      qc.invalidateQueries({ queryKey: qk.studioJobs })
      qc.invalidateQueries({ queryKey: qk.balance })
    },
  })
}

/** Analyse a studio image with the platform's detectors (a normal detection job). */
export function useDetectImage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (mediaId: string) => data(await api.POST("/api/v1/jobs", {
      body: { media_id: mediaId, module: "detect", options: {} } as never,
      params: { header: { "Idempotency-Key": newIdempotencyKey() } },
    })).jobs[0],
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.jobsAll })
      qc.invalidateQueries({ queryKey: qk.balance })
    },
  })
}

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import type { ChatMessage, ConversationDetail } from "@/lib/assistant"

export function useConversations(enabled = true) {
  return useQuery({
    queryKey: qk.conversations,
    enabled,
    queryFn: async () => data(await api.GET("/api/v1/assistant/conversations", { params: { query: { limit: 100 } as never } })).results,
  })
}

export const isRunning = (status: string) => status === "queued" || status === "running"

const running = (c?: ConversationDetail) => !!c?.messages.some((m) => m.jobs.some((j) => isRunning(j.status)))

/**
 * A conversation. While its analyses run it is refreshed from the live events (see `patchJob`), and
 * polled — slowly when the events are connected, as a safety net, every 4 s when they are not.
 */
export function useConversation(id: string | null, live = false) {
  return useQuery({
    queryKey: qk.conversation(id ?? ""),
    enabled: !!id,
    queryFn: async () => data(await api.GET("/api/v1/assistant/conversations/{id}", { params: { path: { id: id! } } })),
    refetchInterval: (q) => (running(q.state.data) ? (live ? 20_000 : 4_000) : false),
  })
}

/** Applies a `job.updated` event (status and progress) to the conversation's copy of that job. */
export function patchJob(c: ConversationDetail, event: Record<string, unknown>): ConversationDetail {
  const update = (j: ChatMessage["jobs"][number]) => (j.id !== event.job_id ? j : {
    ...j,
    status: (event.status as typeof j.status) ?? j.status,
    progress: typeof event.progress === "number" ? event.progress : j.progress,
  })
  return { ...c, messages: c.messages.map((m) => (m.jobs.some((j) => j.id === event.job_id) ? { ...m, jobs: m.jobs.map(update) } : m)) }
}

export function useConversationActions() {
  const qc = useQueryClient()
  const refresh = () => qc.invalidateQueries({ queryKey: qk.conversations })
  const create = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/assistant/conversations", { body: {} as never })),
  })
  const rename = useMutation({
    mutationFn: async ({ id, title }: { id: string; title: string }) =>
      data(await api.PATCH("/api/v1/assistant/conversations/{id}", { params: { path: { id } }, body: { title } as never })),
    onSuccess: (_, { id }) => Promise.all([refresh(), qc.invalidateQueries({ queryKey: qk.conversation(id) })]),
  })
  const remove = useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/api/v1/assistant/conversations/{id}", { params: { path: { id } } })
    },
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: qk.conversation(id) })
      return refresh()
    },
  })
  return { create, rename, remove, refresh }
}

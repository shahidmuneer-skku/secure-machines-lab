"use client"

import { useQuery } from "@tanstack/react-query"

import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"

export function useMe() {
  return useQuery({ queryKey: qk.me, queryFn: async () => data(await api.GET("/api/v1/me")), staleTime: 60_000 })
}

export function usePublicConfig() {
  return useQuery({ queryKey: qk.config, queryFn: async () => data(await api.GET("/api/v1/config")), staleTime: 60_000 })
}

export function useCan(capability: string): boolean {
  const { data: me } = useMe()
  return !!me?.capabilities?.includes(capability)
}

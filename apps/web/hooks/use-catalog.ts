"use client"

import { useQuery } from "@tanstack/react-query"
import { useLocale } from "next-intl"

import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"

export function useCatalog() {
  const locale = useLocale()
  return useQuery({
    queryKey: [...qk.catalog("all"), locale],
    queryFn: async () => data(await api.GET("/api/v1/catalog/models", { params: { query: { lang: locale } } as never })),
    staleTime: 5 * 60_000,
  })
}

export type CatalogData = NonNullable<ReturnType<typeof useCatalog>["data"]>
export type ModelInfo = CatalogData["models"][number]

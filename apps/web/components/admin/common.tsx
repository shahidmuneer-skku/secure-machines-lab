"use client"

import { useInfiniteQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useTranslations } from "next-intl"
import type { ReactNode } from "react"

import { HudCard } from "@/components/sml/hud-card"
import { Button } from "@/components/ui/button"
import { CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useCan } from "@/hooks/use-me"
import { isApiError } from "@/lib/api/errors"

export function cursorOf(next: string | null | undefined): string | undefined {
  return next ? new URL(next, "http://x").searchParams.get("cursor") ?? undefined : undefined
}

/** Cursor-paginated admin list. */
export function usePaged<T>(key: readonly unknown[], fetchPage: (cursor?: string) => Promise<{ next?: string | null; results: T[] }>) {
  const q = useInfiniteQuery({
    queryKey: key, initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => fetchPage(pageParam), getNextPageParam: (last) => cursorOf(last.next),
  })
  return { ...q, rows: q.data?.pages.flatMap((p) => p.results) ?? [] }
}

export function LoadMore({ q }: { q: { hasNextPage: boolean; isFetchingNextPage: boolean; fetchNextPage: () => unknown } }) {
  const t = useTranslations("admin.common")
  if (!q.hasNextPage) return null
  return (
    <div className="flex justify-center pt-3">
      <Button variant="outline" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
        {q.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />} {t("loadMore")}
      </Button>
    </div>
  )
}

export function AdminError({ error }: { error: unknown }) {
  const t = useTranslations("admin.common")
  if (!error) return null
  const code = isApiError(error) ? error.code : ""
  return (
    <HudCard className="border-fake/40"><CardContent className="py-4 text-sm">
      {code === "MFA_REQUIRED" ? t("mfaRequired") : isApiError(error) ? error.detail : t("error")}
    </CardContent></HudCard>
  )
}

export function Loading() {
  return <Skeleton className="h-64 w-full" />
}

export function RequireCap({ cap, children, fallback = null }: { cap: string; children: ReactNode; fallback?: ReactNode }) {
  return useCan(cap) ? <>{children}</> : <>{fallback}</>
}

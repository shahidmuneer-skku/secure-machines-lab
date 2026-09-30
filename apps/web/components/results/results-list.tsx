"use client"

import { useInfiniteQuery } from "@tanstack/react-query"
import { ListFilter, Loader2, ScanSearch, Search, Trash2 } from "lucide-react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useTranslations } from "next-intl"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { PageHeader } from "@/components/sml/page-header"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"

import { JobRow } from "./job-row"

const STATUSES = ["queued", "running", "succeeded", "failed", "canceled", "expired"] as const
const VERDICTS = ["fake", "real", "no_face", "inconclusive"] as const
const KINDS = ["detect", "long_video", "news"] as const
const MEDIA = ["image", "video"] as const
const ALL = "__all"

function cursorOf(next: string | null | undefined): string | undefined {
  if (!next) return undefined
  return new URL(next, "http://x").searchParams.get("cursor") ?? undefined
}

export function ResultsList() {
  const t = useTranslations("results")
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const [search, setSearch] = useState(params.get("q") ?? "")
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const filters = useMemo(() => ({
    status: params.get("status") ?? undefined, verdict: params.get("verdict") ?? undefined,
    kind: params.get("kind") ?? undefined, media_type: params.get("media_type") ?? undefined,
    q: params.get("q") ?? undefined, batch: params.get("batch") ?? undefined,
  }), [params])

  const setFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(params)
    if (!value || value === ALL) next.delete(key); else next.set(key, value)
    router.replace(`${pathname}?${next.toString()}`, { scroll: false })
  }

  useEffect(() => {
    const id = setTimeout(() => { if ((params.get("q") ?? "") !== search) setFilter("q", search || undefined) }, 350)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const query = useInfiniteQuery({
    queryKey: qk.jobs(filters),
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => data(await api.GET("/api/v1/jobs", {
      params: { query: { ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), cursor: pageParam, limit: 25 } as never },
    })),
    getNextPageParam: (last) => cursorOf(last.next),
    // SSE invalidates on changes; this is the polling fallback while work is active.
    refetchInterval: (q) => q.state.data?.pages.some((p) => p.results.some((j) => j.status === "queued" || j.status === "running")) ? 15_000 : false,
  })
  const jobs = query.data?.pages.flatMap((p) => p.results) ?? []
  const hasFilters = Object.values(filters).some(Boolean)

  const bulkDelete = async () => {
    const ids = [...selected]
    const results = await Promise.allSettled(ids.map((id) => api.DELETE("/api/v1/jobs/{id}", { params: { path: { id } } })))
    const failed = results.filter((r) => r.status === "rejected").length
    toast[failed ? "warning" : "success"](t("bulkDeleted", { count: ids.length - failed }))
    setSelected(new Set())
    query.refetch()
  }

  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={3} title={t("title")} description={t("subtitle")}
        actions={<Button asChild><Link href="/app/detect"><ScanSearch className="size-4" /> {t("newDetection")}</Link></Button>} />

      <div className="flex flex-wrap items-center gap-2" role="search">
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("searchPlaceholder")}
            className="pl-8" aria-label={t("search")} />
        </div>
        <ListFilter className="size-4 text-muted-foreground" aria-hidden />
        {([["status", STATUSES, "status"], ["verdict", VERDICTS, "verdict"], ["kind", KINDS, "kindFilter"],
          ["media_type", MEDIA, "mediaFilter"]] as const).map(([key, values, label]) => (
          <Select key={key} value={filters[key] ?? ALL} onValueChange={(v) => setFilter(key, v)}>
            <SelectTrigger size="sm" className="w-36" aria-label={t(`filter.${label}`)}><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t(`filter.${label}`)}: {t("filter.any")}</SelectItem>
              {values.map((v) => <SelectItem key={v} value={v}>{t(`values.${v}`)}</SelectItem>)}
            </SelectContent>
          </Select>
        ))}
        {hasFilters && <Button variant="ghost" size="sm" onClick={() => { setSearch(""); router.replace(pathname) }}>{t("clearFilters")}</Button>}
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 text-sm">
          <span>{t("selectedCount", { count: selected.size })}</span>
          <Button size="sm" variant="destructive" onClick={bulkDelete}><Trash2 className="size-4" /> {t("deleteSelected")}</Button>
          <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>{t("clearSelection")}</Button>
        </div>
      )}

      {query.isLoading ? (
        <div className="space-y-2">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-20" />)}</div>
      ) : query.isError ? (
        <Empty><EmptyHeader><EmptyTitle>{t("loadError")}</EmptyTitle></EmptyHeader>
          <EmptyContent><Button onClick={() => query.refetch()}>{t("retry")}</Button></EmptyContent></Empty>
      ) : !jobs.length ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon"><ScanSearch /></EmptyMedia>
            <EmptyTitle>{hasFilters ? t("noMatches") : t("emptyTitle")}</EmptyTitle>
            <EmptyDescription>{hasFilters ? t("noMatchesHint") : t("emptyHint")}</EmptyDescription>
          </EmptyHeader>
          {!hasFilters && <EmptyContent><Button asChild><Link href="/app/detect">{t("newDetection")}</Link></Button></EmptyContent>}
        </Empty>
      ) : (
        <div className="space-y-2" aria-live="polite">
          {jobs.map((job) => (
            <JobRow key={job.id} job={job} selected={selected.has(job.id)}
              onSelect={(on) => setSelected((prev) => { const n = new Set(prev); if (on) n.add(job.id); else n.delete(job.id); return n })} />
          ))}
          {query.hasNextPage && (
            <div className="flex justify-center pt-2">
              <Button variant="outline" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
                {query.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />} {t("loadMore")}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

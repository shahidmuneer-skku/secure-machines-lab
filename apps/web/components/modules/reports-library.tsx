"use client"

import { useInfiniteQuery } from "@tanstack/react-query"
import { Download, FileText } from "lucide-react"
import Link from "next/link"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"

import { HudCard } from "@/components/sml/hud-card"
import { PageHeader } from "@/components/sml/page-header"
import { StatusChip } from "@/components/sml/status-chip"
import { Button } from "@/components/ui/button"
import { CardContent } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { formatBytes, formatDateTime } from "@/lib/format"

export function ReportsLibrary() {
  const t = useTranslations("reports")
  const locale = useLocale()
  const [format, setFormat] = useState<string>("")
  const q = useInfiniteQuery({
    queryKey: qk.reports({ format }), initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => data(await api.GET("/api/v1/reports", {
      params: { query: { cursor: pageParam, format: format || undefined } as never } })),
    getNextPageParam: (last) => last.next ? new URL(last.next, "http://x").searchParams.get("cursor") ?? undefined : undefined,
  })
  const rows = q.data?.pages.flatMap((p) => p.results) ?? []
  return (
    <div className="space-y-5">
      <PageHeader eyebrow={t("eyebrow")} index={7} title={t("title")} description={t("subtitle")}
        actions={<ToggleGroup type="single" variant="outline" size="sm" value={format || "all"} onValueChange={(v) => setFormat(v === "all" || !v ? "" : v)}>
          {["all", "pdf", "hwp", "csv", "zip"].map((f) => <ToggleGroupItem key={f} value={f}>{t(`format.${f}`)}</ToggleGroupItem>)}
        </ToggleGroup>} />
      {q.isLoading ? <Skeleton className="h-48" /> : !rows.length ? (
        <Empty><EmptyHeader><EmptyMedia variant="icon"><FileText /></EmptyMedia><EmptyTitle>{t("emptyTitle")}</EmptyTitle>
          <EmptyDescription>{t("emptyHint")}</EmptyDescription></EmptyHeader></Empty>
      ) : (
        <HudCard><CardContent className="pt-4">
          <Table>
            <TableHeader><TableRow>
              <TableHead>{t("col.file")}</TableHead><TableHead>{t("col.format")}</TableHead><TableHead>{t("col.version")}</TableHead>
              <TableHead>{t("col.created")}</TableHead><TableHead>{t("col.status")}</TableHead><TableHead className="text-right">{t("col.download")}</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell><Link href={`/app/results/${r.job}`} className="font-medium hover:underline">{r.job_title}</Link></TableCell>
                  <TableCell className="mono-label">{r.format} · {r.locale}</TableCell>
                  <TableCell className="tabular-nums">{t("versionN", { run: r.run_number, version: r.version })}</TableCell>
                  <TableCell className="text-xs">{formatDateTime(r.created_at, locale)}</TableCell>
                  <TableCell><StatusChip status={r.status === "ready" ? "succeeded" : r.status === "failed" ? "failed" : "running"} /></TableCell>
                  <TableCell className="text-right">
                    {r.download_url ? <Button asChild size="sm" variant="ghost"><a href={r.download_url} download={r.filename}>
                      <Download className="size-4" /> {formatBytes(r.size_bytes)}</a></Button> : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {q.hasNextPage && <div className="flex justify-center pt-3"><Button variant="outline" onClick={() => q.fetchNextPage()}>{t("more")}</Button></div>}
        </CardContent></HudCard>
      )}
    </div>
  )
}

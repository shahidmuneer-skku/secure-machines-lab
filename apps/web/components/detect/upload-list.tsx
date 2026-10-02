"use client"

import { AlertCircle, CheckCircle2, Film, ImageIcon, RotateCcw, X } from "lucide-react"
import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import type { UploadItem } from "@/hooks/use-uploads"
import { formatBytes, formatDuration } from "@/lib/format"

export function UploadList({ items, onRemove, onRetry }: { items: UploadItem[]; onRemove: (key: string) => void;
  onRetry: (key: string) => void }) {
  const t = useTranslations("detect")
  if (!items.length) return null
  return (
    <ul className="divide-y divide-border rounded-xl border" aria-label={t("files")}>
      {items.map((item) => (
        <li key={item.key} className="flex items-center gap-3 p-3">
          <div className="relative size-12 shrink-0 overflow-hidden rounded-md bg-muted">
            {item.kind === "image" && item.previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.previewUrl} alt="" className="size-full object-cover" />
            ) : item.kind === "video" && item.previewUrl ? (
              <video src={item.previewUrl} muted className="size-full object-cover" preload="metadata" />
            ) : (
              <AlertCircle className="m-auto mt-3 size-6 text-muted-foreground" />
            )}
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">{item.file.name}</span>
              {item.kind && (
                <Badge variant="outline" className="gap-1">
                  {item.kind === "image" ? <ImageIcon className="size-3" /> : <Film className="size-3" />}
                  {t(item.kind)}
                </Badge>
              )}
            </div>
            <div className="text-xs text-muted-foreground">
              {formatBytes(item.file.size)}
              {item.media?.width ? ` · ${item.media.width}×${item.media.height}` : ""}
              {item.media?.duration_seconds ? ` · ${formatDuration(item.media.duration_seconds)}` : ""}
            </div>
            {item.state === "uploading" && <Progress value={item.progress * 100} aria-label={t("uploading")} className="h-1.5" />}
            {item.state === "invalid" && <p className="text-xs text-fake">{t(item.issue === "size" ? "tooLarge" : "badType")}</p>}
            {item.state === "error" && <p className="text-xs text-fake">{item.error ?? t("uploadFailed")}</p>}
          </div>
          <div className="flex items-center gap-1">
            {item.state === "ready" && <CheckCircle2 className="size-5 text-real" aria-label={t("uploaded")} />}
            {item.state === "uploading" && <span className="text-xs font-semibold tabular-nums">{Math.round(item.progress * 100)}%</span>}
            {item.state === "error" && (
              <Button variant="ghost" size="icon" onClick={() => onRetry(item.key)} aria-label={t("retryUpload")}>
                <RotateCcw className="size-4" />
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={() => onRemove(item.key)} aria-label={t("removeFile")}>
              <X className="size-4" />
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}

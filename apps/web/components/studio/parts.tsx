"use client"

import { Download, ImageOff, Loader2, Maximize2, ScanSearch, Wand2 } from "lucide-react"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"

import { StatusChip } from "@/components/sml/status-chip"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { StudioImage, StudioJob } from "@/lib/api/types"
import { formatRelative } from "@/lib/format"
import { cn } from "@/lib/utils"

/** A rectangle with the format's proportions, for the format picker. */
export function AspectGlyph({ width, height, className }: { width: number; height: number; className?: string }) {
  const scale = 18 / Math.max(width, height)
  return (
    <span className={cn("inline-flex size-5 items-center justify-center", className)} aria-hidden>
      <span className="rounded-[2px] border-[1.5px] border-current"
        style={{ width: Math.max(6, width * scale), height: Math.max(6, height * scale) }} />
    </span>
  )
}

/** One generated image: preview over a checkerboard (transparency shows), with its actions. */
export function OutputTile({ image, onOpen, onEdit, onDetect, detecting }: {
  image: StudioImage
  onOpen: () => void
  onEdit?: () => void
  onDetect?: () => void
  detecting?: boolean
}) {
  const t = useTranslations("studio")
  const w = image.width || 1
  const h = image.height || 1
  // As large as the column allows, but never taller than most of the screen.
  return (
    <figure className="group relative mx-auto overflow-hidden rounded-xl border bg-background/40"
      style={{ width: `min(100%, calc(72vh * ${w} / ${h}))` }}>
      <button type="button" onClick={onOpen} className="checkerboard block w-full" style={{ aspectRatio: `${w} / ${h}` }}
        aria-label={t("open")}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={image.url} alt={t("outputAlt")} loading="lazy" className="size-full object-contain" />
      </button>
      <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-2
        bg-gradient-to-t from-background/90 via-background/50 to-transparent p-2 opacity-100 transition-opacity
        md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
        <span className="mono-label text-muted-foreground">
          {image.width && image.height ? `${image.width}×${image.height}` : ""}{image.seed != null ? ` · ${t("seedN", { seed: image.seed })}` : ""}
        </span>
        <span className="pointer-events-auto flex gap-1">
          <IconAction label={t("open")} onClick={onOpen}><Maximize2 /></IconAction>
          <IconAction label={t("download")} href={image.download_url}><Download /></IconAction>
          {onEdit && <IconAction label={t("editAgain")} onClick={onEdit}><Wand2 /></IconAction>}
          {onDetect && (
            <IconAction label={t("detect")} onClick={onDetect} disabled={detecting}>
              {detecting ? <Loader2 className="animate-spin" /> : <ScanSearch />}
            </IconAction>
          )}
        </span>
      </figcaption>
    </figure>
  )
}

function IconAction({ label, onClick, href, disabled, children }: {
  label: string; onClick?: () => void; href?: string; disabled?: boolean; children: React.ReactNode
}) {
  const button = href ? (
    <Button asChild size="icon" variant="secondary" className="size-8">
      <a href={href} download aria-label={label}>{children}</a>
    </Button>
  ) : (
    <Button size="icon" variant="secondary" className="size-8" onClick={onClick} disabled={disabled} aria-label={label}>
      {children}
    </Button>
  )
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

/** Full-size view of one image. */
export function Lightbox({ image, prompt, onClose }: { image: StudioImage | null; prompt?: string; onClose: () => void }) {
  const t = useTranslations("studio")
  return (
    <Dialog open={!!image} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[min(96vw,1400px)] gap-3 p-3 sm:max-w-[min(96vw,1400px)]">
        <DialogTitle className="sr-only">{t("viewer")}</DialogTitle>
        <DialogDescription className="line-clamp-2 pr-8 text-xs">{prompt}</DialogDescription>
        {image && (
          <div className="checkerboard flex max-h-[80vh] items-center justify-center overflow-hidden rounded-lg">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={image.url} alt={t("outputAlt")} className="max-h-[80vh] w-auto object-contain" />
          </div>
        )}
        {image && (
          <div className="flex justify-end">
            <Button asChild size="sm" variant="outline">
              <a href={image.download_url} download><Download className="size-4" /> {t("download")}</a>
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

/** Earlier studio jobs: newest first, a thumbnail each. */
export function HistoryGrid({ jobs, selectedId, onSelect }: {
  jobs: StudioJob[]
  selectedId: string | null
  onSelect: (job: StudioJob) => void
}) {
  const t = useTranslations("studio")
  const locale = useLocale()
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {jobs.map((job) => {
        const cover = job.outputs[0] ?? job.references[0]
        return (
          <li key={job.id}>
            <button type="button" onClick={() => onSelect(job)}
              className={cn("group block w-full overflow-hidden rounded-xl border text-left transition-colors",
                "hover:border-primary/60 focus-visible:border-primary focus-visible:outline-none",
                selectedId === job.id && "border-primary ring-1 ring-primary/40")}>
              <span className="checkerboard relative block aspect-square">
                {cover?.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={cover.thumbnail_url} alt="" loading="lazy"
                    className={cn("size-full object-cover", !job.outputs.length && "opacity-40 grayscale")} />
                ) : (
                  <span className="flex size-full items-center justify-center text-muted-foreground">
                    <ImageOff className="size-6" aria-hidden />
                  </span>
                )}
                {job.outputs.length > 1 && (
                  <span className="absolute right-1.5 top-1.5 rounded-full bg-background/80 px-1.5 py-0.5 mono-label">
                    ×{job.outputs.length}
                  </span>
                )}
              </span>
              <span className="block space-y-1 p-2">
                <span className="line-clamp-2 text-xs">{job.params.prompt}</span>
                <span className="flex items-center justify-between gap-1">
                  <span className="mono-label text-muted-foreground">{t(`modes.${job.mode}`)}</span>
                  {job.status === "succeeded"
                    ? <span className="truncate text-[11px] text-muted-foreground">{formatRelative(job.created_at, locale)}</span>
                    : <StatusChip status={job.status} className="px-1.5" />}
                </span>
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export function useLightbox() {
  const [image, setImage] = useState<StudioImage | null>(null)
  return { image, open: setImage, close: () => setImage(null) }
}

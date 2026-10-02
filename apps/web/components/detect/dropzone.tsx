"use client"

import { UploadCloud } from "lucide-react"
import { useTranslations } from "next-intl"
import { useEffect } from "react"
import { useDropzone } from "react-dropzone"

import { cn } from "@/lib/utils"

/** Drag & drop, click-to-browse and paste-from-clipboard. Accepts images and videos. */
export function Dropzone({ onFiles, imagesOnly = false, videosOnly = false, multiple = true, compact = false,
  disabled = false, className }: {
  onFiles: (files: File[]) => void
  imagesOnly?: boolean
  videosOnly?: boolean
  multiple?: boolean
  compact?: boolean
  disabled?: boolean
  className?: string
}) {
  const t = useTranslations("detect")
  const accept: Record<string, string[]> = {}
  if (!videosOnly) accept["image/*"] = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".avif"]
  if (!imagesOnly) accept["video/*"] = [".mp4", ".webm", ".mov", ".avi", ".mkv"]
  if (!imagesOnly) accept["image/gif"] = [".gif"]
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => files.length && onFiles(files), multiple, disabled, accept,
  })

  useEffect(() => {
    if (disabled) return
    const onPaste = (e: ClipboardEvent) => {
      const files = Array.from(e.clipboardData?.files ?? [])
      if (files.length) {
        e.preventDefault()
        onFiles(multiple ? files : files.slice(0, 1))
      }
    }
    window.addEventListener("paste", onPaste)
    return () => window.removeEventListener("paste", onPaste)
  }, [disabled, multiple, onFiles])

  return (
    <div
      {...getRootProps()}
      className={cn(
        "scanline-frame group flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-background/40 text-center transition-colors",
        "hover:border-primary/60 focus-visible:border-primary focus-visible:outline-none",
        compact ? "p-6" : "p-10",
        isDragActive && "border-primary bg-primary/5",
        disabled && "pointer-events-none opacity-60",
        className,
      )}
      data-active={isDragActive}
    >
      <input {...getInputProps()} aria-label={t("dropLabel")} />
      <UploadCloud className={cn("text-primary", compact ? "size-7" : "size-10")} aria-hidden />
      <p className="font-medium">{isDragActive ? t("dropNow") : t(imagesOnly ? "dropImages" : "dropTitle")}</p>
      <p className="text-xs text-muted-foreground">{t(imagesOnly ? "dropImagesHint" : "dropHint")}</p>
    </div>
  )
}

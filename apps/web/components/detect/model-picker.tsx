"use client"

import { Film, ImageIcon, Lock, ScanFace, Sparkles } from "lucide-react"
import { useTranslations } from "next-intl"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { ModelInfo } from "@/hooks/use-catalog"
import { cn } from "@/lib/utils"

const FAMILIES = ["deepfake", "ai_generated", "general"] as const

/**
 * Users choose which models contribute to the single combined verdict.
 * Models with separate deepfake / AI-gen weights appear as separate variants.
 */
export function ModelPicker({ models, selected, onChange, mediaTypes }: {
  models: ModelInfo[]
  selected: string[]
  onChange: (ids: string[]) => void
  mediaTypes: ("image" | "video")[]
}) {
  const t = useTranslations("detect")
  const relevant = models.filter((m) => !mediaTypes.length || m.media.some((x) => mediaTypes.includes(x)))
  const toggle = (id: string, on: boolean) => onChange(on ? [...selected, id] : selected.filter((s) => s !== id))
  const allowedIds = relevant.filter((m) => m.allowed !== false).map((m) => m.id)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline"
          onClick={() => onChange(relevant.filter((m) => m.default_selected && m.allowed !== false).map((m) => m.id))}>
          {t("recommended")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onChange(allowedIds)}>{t("selectAll")}</Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onChange([])}>{t("clearSelection")}</Button>
        <span className="ml-auto mono-label text-muted-foreground">{t("selectedCount", { count: selected.length })}</span>
      </div>
      {FAMILIES.map((family) => {
        const group = relevant.filter((m) => m.family === family)
        if (!group.length) return null
        return (
          <fieldset key={family} className="space-y-2">
            <legend className="hud-eyebrow mb-2">{t(`family.${family}`)}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {group.map((m) => {
                const locked = m.allowed === false
                const checked = selected.includes(m.id)
                const partial = mediaTypes.length > 1 && !mediaTypes.every((x) => m.media.includes(x))
                return (
                  <label key={m.id}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
                      checked ? "border-primary/60 bg-primary/5" : "hover:bg-accent/50",
                      locked && "cursor-not-allowed opacity-50",
                    )}>
                    <Checkbox checked={checked} disabled={locked} onCheckedChange={(v) => toggle(m.id, v === true)}
                      className="mt-0.5" aria-describedby={`${m.id}-desc`} />
                    <span className="min-w-0 flex-1 space-y-1">
                      <span className="flex flex-wrap items-center gap-1.5">
                        <span className="text-sm font-medium">{m.name}</span>
                        {m.media.includes("image") && <ImageIcon className="size-3.5 text-muted-foreground" aria-label={t("image")} />}
                        {m.media.includes("video") && <Film className="size-3.5 text-muted-foreground" aria-label={t("video")} />}
                        {m.face_required && (
                          <Tooltip>
                            <TooltipTrigger asChild><ScanFace className="size-3.5 text-muted-foreground" aria-label={t("needsFace")} /></TooltipTrigger>
                            <TooltipContent>{t("needsFaceHint")}</TooltipContent>
                          </Tooltip>
                        )}
                        {m.xai !== "none" && <Sparkles className="size-3.5 text-violet" aria-label={t("hasXai")} />}
                        {locked && <Lock className="size-3.5" aria-label={t("locked")} />}
                        {partial && <Badge variant="outline" className="text-[10px]">{t(m.media.includes("image") ? "imageOnly" : "videoOnly")}</Badge>}
                      </span>
                      <span id={`${m.id}-desc`} className="block text-xs text-muted-foreground">{m.description}</span>
                    </span>
                  </label>
                )
              })}
            </div>
          </fieldset>
        )
      })}
    </div>
  )
}

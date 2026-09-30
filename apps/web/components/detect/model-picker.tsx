"use client"

import { Film, ImageIcon, Lock, ScanFace, Sparkles } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { ModelInfo } from "@/hooks/use-catalog"
import { cn } from "@/lib/utils"

const FAMILIES = ["deepfake", "ai_generated", "general"] as const

/**
 * Users choose which detectors contribute to the single combined verdict. Detectors are grouped by
 * what they look for, in collapsible sections that show the current selection when closed.
 */
export function ModelPicker({ models, selected, onChange, mediaTypes }: {
  models: ModelInfo[]
  selected: string[]
  onChange: (ids: string[]) => void
  mediaTypes: ("image" | "video")[]
}) {
  const t = useTranslations("detect")
  const [open, setOpen] = useState<string[]>([])
  const relevant = models.filter((m) => !mediaTypes.length || m.media.some((x) => mediaTypes.includes(x)))
  const usable = (m: ModelInfo) => m.allowed !== false
  const toggle = (id: string, on: boolean) => onChange(on ? [...selected, id] : selected.filter((s) => s !== id))
  const setGroup = (ids: string[], on: boolean) =>
    onChange(on ? Array.from(new Set([...selected, ...ids])) : selected.filter((s) => !ids.includes(s)))

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Button type="button" size="sm" variant="outline"
          onClick={() => onChange(relevant.filter((m) => m.default_selected && usable(m)).map((m) => m.id))}>
          {t("recommended")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onChange(relevant.filter(usable).map((m) => m.id))}>
          {t("selectAll")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onChange([])}>{t("clearSelection")}</Button>
        <Button type="button" size="sm" variant="ghost" className="ml-auto"
          onClick={() => setOpen(open.length ? [] : FAMILIES.filter((f) => relevant.some((m) => m.family === f)))}>
          {open.length ? t("collapseAll") : t("expandAll")}
        </Button>
      </div>

      <Accordion type="multiple" value={open} onValueChange={setOpen} className="rounded-lg border">
        {FAMILIES.map((family) => {
          const group = relevant.filter((m) => m.family === family)
          if (!group.length) return null
          const ids = group.filter(usable).map((m) => m.id)
          const chosen = group.filter((m) => selected.includes(m.id))
          const state = chosen.length === 0 ? false : chosen.length === ids.length ? true : "indeterminate"
          return (
            <AccordionItem key={family} value={family}>
              {/* The accordion header (h3) must stretch so the chevron sits at the right edge. */}
              <div className="flex items-center gap-3 px-3 [&>h3]:min-w-0 [&>h3]:flex-1">
                <Checkbox checked={state} disabled={!ids.length} aria-label={t("selectGroup", { group: t(`family.${family}`) })}
                  onCheckedChange={(v) => setGroup(ids, v === true)} />
                <AccordionTrigger className="min-w-0 flex-1 py-3 hover:no-underline">
                  <span className="flex min-w-0 flex-1 items-center gap-2 text-left">
                    <span className="shrink-0 whitespace-nowrap font-medium">{t(`family.${family}`)}</span>
                    <Badge variant="secondary" className="shrink-0 font-mono tabular-nums">{chosen.length}/{group.length}</Badge>
                    {!open.includes(family) && chosen.length > 0 && (
                      <span className="hidden min-w-0 truncate text-xs font-normal text-muted-foreground sm:inline">
                        {chosen.map((m) => m.name).join(", ")}
                      </span>
                    )}
                  </span>
                </AccordionTrigger>
              </div>
              <AccordionContent className="pb-1">
                <ul className="divide-y border-t">
                  {group.map((m) => {
                    const locked = !usable(m)
                    const checked = selected.includes(m.id)
                    const partial = mediaTypes.length > 1 && !mediaTypes.every((x) => m.media.includes(x))
                    return (
                      <li key={m.id}>
                        <label className={cn("flex cursor-pointer items-center gap-3 px-3 py-2 transition-colors",
                          checked ? "bg-primary/5" : "hover:bg-accent/40", locked && "cursor-not-allowed opacity-50")}>
                          <Checkbox checked={checked} disabled={locked} onCheckedChange={(v) => toggle(m.id, v === true)}
                            aria-describedby={`${m.id}-desc`} />
                          <span className="w-36 shrink-0 truncate text-sm font-medium">{m.name}</span>
                          <span className="flex shrink-0 items-center gap-1 text-muted-foreground">
                            {m.media.includes("image") && <ImageIcon className="size-3.5" aria-label={t("image")} />}
                            {m.media.includes("video") && <Film className="size-3.5" aria-label={t("video")} />}
                            {m.face_required && (
                              <Tooltip>
                                <TooltipTrigger asChild><ScanFace className="size-3.5" aria-label={t("needsFace")} /></TooltipTrigger>
                                <TooltipContent>{t("needsFaceHint")}</TooltipContent>
                              </Tooltip>
                            )}
                            {m.xai !== "none" && <Sparkles className="size-3.5 text-violet" aria-label={t("hasXai")} />}
                            {locked && <Lock className="size-3.5" aria-label={t("locked")} />}
                          </span>
                          <span id={`${m.id}-desc`} title={m.description}
                            className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{m.description}</span>
                          {partial && (
                            <Badge variant="outline" className="shrink-0 text-[10px]">
                              {t(m.media.includes("image") ? "imageOnly" : "videoOnly")}
                            </Badge>
                          )}
                        </label>
                      </li>
                    )
                  })}
                </ul>
              </AccordionContent>
            </AccordionItem>
          )
        })}
      </Accordion>
      <p className="mono-label text-right text-muted-foreground">{t("selectedCount", { count: selected.length })}</p>
    </div>
  )
}

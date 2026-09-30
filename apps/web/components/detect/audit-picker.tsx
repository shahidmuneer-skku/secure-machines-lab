"use client"

import { Lock } from "lucide-react"
import { useTranslations } from "next-intl"

import { Checkbox } from "@/components/ui/checkbox"
import type { CatalogData } from "@/hooks/use-catalog"

export type AuditStep = "face" | "safety" | "fas"

export function AuditPicker({ steps, selected, onChange }: {
  steps: CatalogData["audit_steps"]
  selected: AuditStep[]
  onChange: (steps: AuditStep[]) => void
}) {
  const t = useTranslations("detect")
  return (
    <div className="divide-y rounded-md border">
      {steps.map((s) => {
        const always = s.always_on
        const id = s.id as AuditStep
        const checked = always || selected.includes(id)
        return (
          <label key={s.id} className="flex cursor-pointer items-start gap-3 px-3 py-2 hover:bg-accent/40 aria-disabled:opacity-60"
            aria-disabled={!s.allowed && !always}>
            <Checkbox checked={checked} disabled={always || !s.allowed} className="mt-0.5"
              onCheckedChange={(v) => onChange(v === true ? [...selected, id] : selected.filter((x) => x !== id))} />
            <span className="space-y-0.5">
              <span className="flex items-center gap-1.5 text-sm font-medium">
                {s.name}
                {always && <span className="mono-label text-primary">{t("alwaysOn")}</span>}
                {!s.allowed && !always && <Lock className="size-3.5" aria-label={t("locked")} />}
              </span>
              <span className="block text-xs text-muted-foreground">{s.description}</span>
            </span>
          </label>
        )
      })}
    </div>
  )
}

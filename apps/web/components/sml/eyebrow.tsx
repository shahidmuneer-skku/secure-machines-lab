import { cn } from "@/lib/utils"

/** HUD-style mono label, e.g. "Index / Results · 002". */
export function Eyebrow({ index, children, className }: { index?: number; children: React.ReactNode;
  className?: string }) {
  return (
    <p className={cn("hud-eyebrow flex items-center gap-2", className)}>
      {index !== undefined && <span className="text-primary">{String(index).padStart(3, "0")}</span>}
      {index !== undefined && <span aria-hidden className="opacity-40">/</span>}
      <span>{children}</span>
    </p>
  )
}

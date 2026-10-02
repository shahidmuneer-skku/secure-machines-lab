import { cn } from "@/lib/utils"

/** A small uppercase section label (Modernize sub-heading). `index` is accepted for older callers. */
export function Eyebrow({ children, className }: { index?: number; children: React.ReactNode; className?: string }) {
  return <p className={cn("hud-eyebrow flex items-center gap-2", className)}>{children}</p>
}

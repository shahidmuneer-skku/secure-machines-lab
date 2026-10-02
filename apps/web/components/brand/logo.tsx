import Link from "next/link"

import { cn } from "@/lib/utils"

/** The SML mark: a shield with a check in the brand gradient. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span aria-hidden className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-[9px] bg-gradient-to-br from-[#5d87ff] to-[#49beff] text-white shadow-[0_6px_14px_-4px_rgb(93_135_255/0.55)]", className)}>
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3l7 3v5c0 4.6-3 8.4-7 10-4-1.6-7-5.4-7-10V6l7-3z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    </span>
  )
}

/** Logo with the lab's name; `tag` adds a small label (e.g. "Admin"). */
export function Logo({ href = "/", tag, compact = false, className }: {
  href?: string
  tag?: string
  compact?: boolean
  className?: string
}) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2.5 text-foreground no-underline", className)}
      aria-label="Secure Machines Lab">
      <LogoMark />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="text-[1.05rem] font-extrabold tracking-tight">Secure Machines</span>
          <span className="mt-1 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Lab{tag && <span className="rounded bg-primary-soft px-1.5 py-0.5 text-[0.62rem] tracking-[0.06em] text-primary">{tag}</span>}
          </span>
        </span>
      )}
    </Link>
  )
}

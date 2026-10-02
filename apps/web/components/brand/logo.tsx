import Link from "next/link"

import { cn } from "@/lib/utils"

/**
 * The company logo (owner, 2026-10-02; source: docs/brand/secure-machine-lab.svg). The shield is drawn exactly as
 * designed — navy blades, teal blades, pixels and the check — with the navy following `--logo-ink`, so
 * it turns white on the dark theme. The wordmark reads "Secure Machines Lab", the company name the
 * owner kept (the source file says "Secure Machine Lab").
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="128 145 460 520" aria-hidden className={cn("h-9 w-auto shrink-0 text-logo-ink", className)}>
      <g fill="currentColor">
        <path d="M140 242Q132 246 134 262L135 298Q135 308 144 316L233 378 348 164Q354 150 341 153Z" />
        <path d="M193 549L454 479 365 650Q360 661 348 654 256 606 193 549Z" />
        <path d="M397 639L485 396 574 433Q583 437 578 452 543 555 397 639Z" />
      </g>
      <g className="fill-logo-teal">
        <path d="M376 153Q380 149 389 154L532 218 288 303Z" />
        <path d="M135 312L317 492 190 526Q180 529 174 518 132 430 134 321Z" />
      </g>
      <path d="M293 397L337 442 441 353" fill="none" stroke="currentColor" strokeWidth={43} strokeLinecap="round"
        strokeLinejoin="round" />
      <path d="M430 275L470 257V306Q470 313 463 313H436Q430 313 430 307Z" fill="currentColor" />
      <rect x="485" y="239" width="43" height="44" rx="6" className="fill-logo-teal" />
      <rect x="540" y="238" width="43" height="45" rx="6" fill="currentColor" />
      <rect x="485" y="292" width="43" height="45" rx="6" fill="currentColor" />
      <rect x="540" y="292" width="43" height="45" rx="6" className="fill-logo-teal" />
      <path d="M485 347H527V396L485 380Z" fill="currentColor" />
      <path d="M540 347H583V417L540 401Z" className="fill-logo-teal" />
    </svg>
  )
}

/** Shield and wordmark, as in the company logo; `tag` adds a small label (e.g. "Admin"), `compact` shows the shield only. */
export function Logo({ href = "/", tag, compact = false, className }: {
  href?: string
  tag?: string
  compact?: boolean
  className?: string
}) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2.5 text-logo-ink no-underline", className)}
      aria-label="Secure Machines Lab">
      <LogoMark className="h-10" />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="text-[1.08rem] font-extrabold tracking-[-0.02em]">Secure Machines</span>
          <span className="mt-0.5 flex items-center gap-2 text-[1.08rem] font-light tracking-[-0.01em]">
            Lab{tag && <span className="rounded bg-primary-soft px-1.5 py-0.5 text-[0.62rem] font-semibold uppercase tracking-[0.06em] text-primary">{tag}</span>}
          </span>
        </span>
      )}
    </Link>
  )
}

import Link from "next/link"

export function BrandMark({ href = "/", suffix = "DASH" }: { href?: string; suffix?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 font-mono text-sm tracking-widest">
      <span className="led-dot text-primary" aria-hidden />
      <span className="font-semibold">SML</span>
      <span className="opacity-40">/</span>
      <span className="opacity-70">{suffix}</span>
    </Link>
  )
}

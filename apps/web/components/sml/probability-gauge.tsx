import { cn } from "@/lib/utils"

/** Semi-circular gauge for the fake probability (0–1). Text value is always rendered. */
export function ProbabilityGauge({ value, label, className }: { value: number | null | undefined; label: string;
  className?: string }) {
  const v = value == null ? null : Math.max(0, Math.min(1, value))
  const angle = v == null ? 0 : v * 180
  const r = 70
  const toXY = (deg: number) => {
    const rad = ((180 - deg) * Math.PI) / 180
    return [80 + r * Math.cos(rad), 85 - r * Math.sin(rad)]
  }
  const [x, y] = toXY(angle)
  const large = angle > 180 ? 1 : 0
  const color = v == null ? "var(--muted-foreground)" : v >= 0.5 ? "var(--fake)" : "var(--real)"
  return (
    <div className={cn("flex flex-col items-center", className)}>
      <svg viewBox="0 0 160 95" className="w-full max-w-56" role="img"
        aria-label={`${label}: ${v == null ? "—" : `${(v * 100).toFixed(1)}%`}`}>
        <path d="M10 85 A70 70 0 0 1 150 85" fill="none" stroke="var(--muted)" strokeWidth="12" strokeLinecap="round" />
        {v != null && v > 0 && (
          <path d={`M10 85 A70 70 0 ${large} 1 ${x.toFixed(2)} ${y.toFixed(2)}`} fill="none" stroke={color}
            strokeWidth="12" strokeLinecap="round" />
        )}
        <line x1="80" y1="12" x2="80" y2="22" stroke="var(--border)" strokeWidth="2" />
      </svg>
      <div className="-mt-9 text-center">
        <div className="font-mono text-3xl font-semibold tabular-nums" style={{ color }}>
          {v == null ? "—" : `${(v * 100).toFixed(1)}%`}
        </div>
        <div className="mono-label text-muted-foreground">{label}</div>
      </div>
    </div>
  )
}

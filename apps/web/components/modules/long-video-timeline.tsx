"use client"

import { useTranslations } from "next-intl"

import type { StreamInterval } from "@/hooks/use-long-video-stream"
import { formatTimestamp } from "@/lib/format"
import { cn } from "@/lib/utils"

/**
 * Diverging colour for P(fake): the "real" hue below 50 %, neutral grey at 50 %, the "fake" hue above.
 * Uses the validated --viz-real / --viz-fake tokens (light and dark themes).
 */
export function probabilityColor(p: number): string {
  const strength = Math.round(Math.min(1, Math.abs(p - 0.5) * 2) * 100)
  const hue = p >= 0.5 ? "var(--viz-fake)" : "var(--viz-real)"
  // Neutral midpoint must stay visible against the card in both themes.
  return `color-mix(in oklab, ${hue} ${strength}%, color-mix(in oklab, var(--muted-foreground) 45%, var(--card)))`
}

/** Live heat-strip of interval scores over the selected range; click a segment to seek the player. */
export function LongVideoTimeline({ intervals, rangeStart, rangeEnd, currentTime, analysedUntil, onSeek }: {
  intervals: StreamInterval[]
  rangeStart: number
  rangeEnd: number
  currentTime: number
  analysedUntil: number | null
  onSeek: (seconds: number) => void
}) {
  const t = useTranslations("longVideo")
  const span = Math.max(0.001, rangeEnd - rangeStart)
  const pct = (s: number) => `${(Math.min(Math.max(s, rangeStart), rangeEnd) - rangeStart) / span * 100}%`
  const suspicious = [...intervals].sort((a, b) => b.fake_probability - a.fake_probability)
    .filter((i) => i.fake_probability >= 0.5).slice(0, 5)

  return (
    <div className="space-y-3">
      <div className="relative h-10 overflow-hidden rounded-md border bg-muted/40" role="group" aria-label={t("timeline")}>
        {intervals.map((i) => (
          <button key={i.index} type="button" onClick={() => onSeek(i.start_sec)}
            className="absolute inset-y-0 border-r border-background/60 transition-opacity hover:opacity-80 focus-visible:outline-2"
            style={{ left: pct(i.start_sec), width: `calc(${pct(i.end_sec)} - ${pct(i.start_sec)})`,
              background: probabilityColor(i.fake_probability) }}
            title={t("segment", { from: formatTimestamp(i.start_sec), to: formatTimestamp(i.end_sec),
              pct: Math.round(i.fake_probability * 100) })}
            aria-label={t("segment", { from: formatTimestamp(i.start_sec), to: formatTimestamp(i.end_sec),
              pct: Math.round(i.fake_probability * 100) })} />
        ))}
        {analysedUntil != null && analysedUntil < rangeEnd && (
          <div className="pointer-events-none absolute inset-y-0 animate-pulse bg-primary/10"
            style={{ left: pct(analysedUntil), right: 0 }} aria-hidden />
        )}
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-foreground" style={{ left: pct(currentTime) }}
          aria-hidden />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="font-mono">{formatTimestamp(rangeStart)}</span>
        <span className="flex items-center gap-3">
          {[[0.05, t("legendReal")], [0.5, t("legendUncertain")], [0.95, t("legendFake")]].map(([p, label]) => (
            <span key={String(label)} className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: probabilityColor(Number(p)) }} />{label}
            </span>
          ))}
        </span>
        <span className="font-mono">{formatTimestamp(rangeEnd)}</span>
      </div>
      {suspicious.length > 0 && (
        <div className="space-y-1">
          <p className="hud-eyebrow">{t("mostSuspicious")}</p>
          <ul className="flex flex-wrap gap-1.5">
            {suspicious.map((i) => (
              <li key={i.index}>
                <button type="button" onClick={() => onSeek(i.start_sec)}
                  className={cn("rounded-md border px-2 py-1 font-mono text-xs hover:bg-accent")}>
                  {formatTimestamp(i.start_sec)} · <span className="text-fake">{Math.round(i.fake_probability * 100)}%</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

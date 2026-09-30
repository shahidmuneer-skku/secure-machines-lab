"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Turnstile } from "@marsidev/react-turnstile"
import { ArrowRight, Loader2, RotateCcw, Sparkles } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { Dropzone } from "@/components/detect/dropzone"
import { ProbabilityGauge } from "@/components/sml/probability-gauge"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { api, data } from "@/lib/api/client"
import { isApiError, problemFromResponse, ApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { Language } from "@/lib/marketing/i18n"

const COPY = {
  en: {
    eyebrow: "Index / Try it · 002", title: "Test an image — no account needed",
    body: "Drop a photo and our detectors check it for face manipulation and AI generation, plus EXIF/C2PA provenance.",
    left: (n: number, d: number) => `${n} of ${d} free checks left today`, analyzing: "Analyzing", again: "Try another image",
    doneTitle: "Result", signup: "Create a free account", signupBody: "Get a welcome bonus, free credits every day, videos, reports and the full model catalog.",
    exhausted: "You've used today's free checks.", error: "Something went wrong. Please try again.", disabled: "The free trial is currently unavailable.",
    queued: "Queued", disclaimer: "Probabilistic estimate — not legal evidence.", fake: "Fake probability", metadata: "AI indicator found in metadata",
  },
  ko: {
    eyebrow: "Index / 체험하기 · 002", title: "계정 없이 이미지 검사하기",
    body: "사진을 올리면 얼굴 조작·AI 생성 여부와 EXIF/C2PA 출처 정보를 분석합니다.",
    left: (n: number, d: number) => `오늘 무료 검사 ${d}회 중 ${n}회 남음`, analyzing: "분석 중", again: "다른 이미지 검사",
    doneTitle: "결과", signup: "무료 계정 만들기", signupBody: "가입 보너스, 매일 무료 크레딧, 영상 분석, 보고서와 전체 모델을 이용하세요.",
    exhausted: "오늘의 무료 검사를 모두 사용했습니다.", error: "오류가 발생했습니다. 다시 시도해 주세요.", disabled: "무료 체험을 현재 이용할 수 없습니다.",
    queued: "대기 중", disclaimer: "확률적 추정치이며 법적 증거가 아닙니다.", fake: "가짜 확률", metadata: "메타데이터에서 AI 생성 흔적 발견",
  },
  de: {
    eyebrow: "Index / Testen · 002", title: "Bild prüfen – ohne Konto",
    body: "Laden Sie ein Foto hoch: Unsere Detektoren prüfen es auf Gesichtsmanipulation, KI-Generierung und EXIF/C2PA-Herkunft.",
    left: (n: number, d: number) => `Noch ${n} von ${d} kostenlosen Prüfungen heute`, analyzing: "Analyse läuft", again: "Weiteres Bild prüfen",
    doneTitle: "Ergebnis", signup: "Kostenloses Konto erstellen", signupBody: "Willkommensbonus, täglich Gratis-Credits, Videos, Berichte und alle Modelle.",
    exhausted: "Die kostenlosen Prüfungen für heute sind aufgebraucht.", error: "Etwas ist schiefgelaufen. Bitte erneut versuchen.",
    disabled: "Die kostenlose Testversion ist derzeit nicht verfügbar.", queued: "In Warteschlange",
    disclaimer: "Probabilistische Schätzung – kein rechtlicher Beweis.", fake: "Fake-Wahrscheinlichkeit", metadata: "KI-Hinweis in den Metadaten",
  },
} as const

export function TrialSection({ language }: { language: Language }) {
  const c = COPY[language]
  const qc = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [captcha, setCaptcha] = useState("")
  const [live, setLive] = useState<{ progress: number; message: string }>({ progress: 0, message: "" })
  const status = useQuery({ queryKey: qk.trialStatus, queryFn: async () => data(await api.GET("/api/v1/trial/status")) })
  const job = useQuery({
    queryKey: qk.trialJob(jobId ?? ""), enabled: !!jobId,
    queryFn: async () => data(await api.GET("/api/v1/trial/jobs/{id}", { params: { path: { id: jobId! } } })),
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 2500 : false),
  })

  // Live progress over SSE (the trial cookie authorises the stream).
  useEffect(() => {
    if (!jobId) return
    const es = new EventSource(`/api/v1/trial/jobs/${jobId}/stream`)
    es.addEventListener("task.progress", (e) => {
      const d = JSON.parse((e as MessageEvent).data).data as { progress: number; message: string }
      setLive((prev) => ({ progress: Math.max(prev.progress, d.progress ?? 0), message: d.message || prev.message }))
    })
    es.addEventListener("job.updated", () => qc.invalidateQueries({ queryKey: qk.trialJob(jobId) }))
    return () => es.close()
  }, [jobId, qc])

  const submit = async (files: File[]) => {
    const file = files[0]
    if (!file) return
    setBusy(true)
    setError(null)
    setLive({ progress: 0, message: "" })
    try {
      const form = new FormData()
      form.append("file", file)
      form.append("locale", language)
      if (captcha) form.append("captcha_token", captcha)
      const res = await fetch("/api/v1/trial/detect", { method: "POST", body: form, credentials: "same-origin" })
      if (!res.ok) throw new ApiError(await problemFromResponse(res))
      const body = (await res.json()) as { job_id: string }
      setJobId(body.job_id)
    } catch (e) {
      setError(isApiError(e) ? (e.code === "TRIAL_EXHAUSTED" ? c.exhausted : e.detail) : c.error)
    } finally {
      setBusy(false)
      qc.invalidateQueries({ queryKey: qk.trialStatus })
    }
  }

  const s = status.data
  const j = job.data
  const running = j && (j.status === "queued" || j.status === "running")
  const aiMeta = (j?.verdict_reasons as { code: string }[] | undefined)?.some((r) => r.code === "metadata_ai_indicator")

  return (
    <section id="trial" className="relative z-10 mx-auto max-w-6xl px-6 py-24">
      <p className="hud-eyebrow text-[var(--sml-accent)]">{c.eyebrow}</p>
      <div className="mt-3 grid gap-10 lg:grid-cols-2">
        <div className="space-y-4">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">{c.title}</h2>
          <p className="max-w-lg text-[var(--sml-ink-dim)]">{c.body}</p>
          {s && s.enabled && <p className="mono-label text-[var(--sml-ink-dim)]">{c.left(s.remaining, s.per_day)}</p>}
          <div className="rounded-2xl border border-[var(--sml-line-2)] bg-black/30 p-5 backdrop-blur">
            <p className="mb-2 text-sm font-medium">{c.signup}</p>
            <p className="mb-4 text-sm text-[var(--sml-ink-dim)]">{c.signupBody}</p>
            <Button asChild><Link href="/signup">{c.signup} <ArrowRight className="size-4" /></Link></Button>
          </div>
        </div>
        <div className="space-y-4">
          {!s?.enabled ? (
            <p className="text-sm text-[var(--sml-ink-dim)]">{status.isLoading ? "…" : c.disabled}</p>
          ) : !jobId ? (
            <>
              {s.remaining > 0 ? <Dropzone onFiles={submit} imagesOnly multiple={false} disabled={busy} /> : (
                <div className="rounded-2xl border border-[var(--sml-accent-2)]/40 p-6 text-center">
                  <p className="mb-4">{c.exhausted}</p>
                  <Button asChild><Link href="/signup">{c.signup}</Link></Button>
                </div>
              )}
              {s.captcha_required && s.captcha_site_key && (
                <Turnstile siteKey={s.captcha_site_key} onSuccess={setCaptcha} options={{ theme: "dark", size: "flexible" }} />
              )}
              {busy && <p className="flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" /> {c.analyzing}…</p>}
            </>
          ) : (
            <div className="scanline-frame space-y-4 rounded-2xl border border-[var(--sml-line-2)] bg-black/40 p-5" data-active={!!running}>
              <div className="flex items-center gap-4">
                {j?.thumbnail_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={j.thumbnail_url} alt="" className="size-20 rounded-lg object-cover" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{j?.title}</p>
                  {running ? (
                    <div className="mt-2 space-y-1">
                      <Progress value={Math.max(live.progress, j?.progress ?? 0)} className="h-1.5" />
                      <p className="text-xs text-[var(--sml-ink-dim)]">{live.message || (j?.status === "queued" ? c.queued : c.analyzing)}</p>
                    </div>
                  ) : j?.status === "succeeded" ? <VerdictBadge verdict={j.verdict} className="mt-2" /> : null}
                </div>
              </div>
              {j?.status === "succeeded" && (
                <>
                  <ProbabilityGauge value={j.fake_probability} label={c.fake} />
                  {aiMeta && <p className="flex items-center gap-2 text-sm text-[var(--sml-accent-2)]"><Sparkles className="size-4" />{c.metadata}</p>}
                  <ul className="grid grid-cols-2 gap-2 text-xs">
                    {(j.summary as { models?: { name: string; fake_prob: number | null; no_face: boolean }[] }).models?.map((m) => (
                      <li key={m.name} className="flex justify-between rounded-md border border-[var(--sml-line)] px-2 py-1">
                        <span>{m.name}</span>
                        <span className="font-mono">{m.no_face ? "—" : m.fake_prob != null ? `${(m.fake_prob * 100).toFixed(0)}%` : "—"}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-xs text-[var(--sml-ink-faint)]">{c.disclaimer}</p>
                </>
              )}
              {j && !running && (
                <Button variant="outline" size="sm" onClick={() => { setJobId(null); setCaptcha("") }}>
                  <RotateCcw className="size-4" /> {c.again}
                </Button>
              )}
            </div>
          )}
          {error && <p className="text-sm text-[var(--sml-accent-2)]" role="alert">{error}</p>}
        </div>
      </div>
    </section>
  )
}

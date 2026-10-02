"use client"

import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Chip from "@mui/material/Chip"
import Container from "@mui/material/Container"
import Grid from "@mui/material/Grid"
import LinearProgress from "@mui/material/LinearProgress"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import { Turnstile } from "@marsidev/react-turnstile"
import { IconArrowRight, IconGift, IconLoader2, IconLock, IconRefresh } from "@tabler/icons-react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

import { Dropzone } from "@/components/detect/dropzone"
import { ProbabilityGauge } from "@/components/sml/probability-gauge"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import { api, data } from "@/lib/api/client"
import { ApiError, isApiError, problemFromResponse } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { Language } from "@/lib/marketing/i18n"

/**
 * Guest trial on the landing page: one image, no account (admin-set daily allowance). The hero hands off
 * here ("Try an image"). Retouched with the 3D scan redesign (2026-10-02); upload, quota, captcha,
 * progress, errors and results work exactly as before.
 */
const COPY = {
  en: {
    eyebrow: "Free trial", title: "Test an image — no account needed",
    body: "Drop a photo and we check it for face manipulation and AI generation.",
    left: (n: number, d: number) => `${n} of ${d} free checks left today`, analyzing: "Analyzing", again: "Try another image",
    doneTitle: "Result", signup: "Create a free account", signupBody: "Get a welcome bonus, free credits every day, videos, reports and the full model catalog.",
    exhausted: "You've used today's free checks.", error: "Something went wrong. Please try again.", disabled: "The free trial is currently unavailable.",
    queued: "Queued", disclaimer: "Probabilistic estimate — not legal evidence.", fake: "Fake probability",
    analyses: { face_swap: "Face-swap analysis", ai_generated: "AI-generation analysis" },
    noFace: "No face found", notCompleted: "Not completed",
    privacy: "Files are stored privately and deleted on schedule.", unavailableHint: "Create a free account to analyse images now.",
    preview: "Uploaded image",
  },
  ko: {
    eyebrow: "무료 체험", title: "계정 없이 이미지 검사하기",
    body: "사진을 올리면 얼굴 조작과 AI 생성 여부를 분석합니다.",
    left: (n: number, d: number) => `오늘 무료 검사 ${d}회 중 ${n}회 남음`, analyzing: "분석 중", again: "다른 이미지 검사",
    doneTitle: "결과", signup: "무료 계정 만들기", signupBody: "가입 보너스, 매일 무료 크레딧, 영상 분석, 보고서와 전체 모델을 이용하세요.",
    exhausted: "오늘의 무료 검사를 모두 사용했습니다.", error: "오류가 발생했습니다. 다시 시도해 주세요.", disabled: "무료 체험을 현재 이용할 수 없습니다.",
    queued: "대기 중", disclaimer: "확률적 추정치이며 법적 증거가 아닙니다.", fake: "가짜 확률",
    analyses: { face_swap: "얼굴 합성(페이스 스왑) 분석", ai_generated: "AI 생성 분석" },
    noFace: "얼굴 없음", notCompleted: "완료하지 못함",
    privacy: "파일은 비공개로 보관되고 일정에 따라 삭제됩니다.", unavailableHint: "무료 계정을 만들면 지금 바로 이미지를 분석할 수 있습니다.",
    preview: "업로드한 이미지",
  },
  de: {
    eyebrow: "Kostenlos testen", title: "Bild prüfen – ohne Konto",
    body: "Laden Sie ein Foto hoch: Wir prüfen es auf Gesichtsmanipulation und KI-Generierung.",
    left: (n: number, d: number) => `Noch ${n} von ${d} kostenlosen Prüfungen heute`, analyzing: "Analyse läuft", again: "Weiteres Bild prüfen",
    doneTitle: "Ergebnis", signup: "Kostenloses Konto erstellen", signupBody: "Willkommensbonus, täglich Gratis-Credits, Videos, Berichte und alle Modelle.",
    exhausted: "Die kostenlosen Prüfungen für heute sind aufgebraucht.", error: "Etwas ist schiefgelaufen. Bitte erneut versuchen.",
    disabled: "Die kostenlose Testversion ist derzeit nicht verfügbar.", queued: "In Warteschlange",
    disclaimer: "Probabilistische Schätzung – kein rechtlicher Beweis.", fake: "Fake-Wahrscheinlichkeit",
    analyses: { face_swap: "Face-Swap-Analyse", ai_generated: "KI-Generierungs-Analyse" },
    noFace: "Kein Gesicht", notCompleted: "Nicht abgeschlossen",
    privacy: "Dateien werden privat gespeichert und planmäßig gelöscht.", unavailableHint: "Mit einem kostenlosen Konto können Sie Bilder sofort analysieren.",
    preview: "Hochgeladenes Bild",
  },
} as const

export function TrialSection({ language }: { language: Language }) {
  const { resolvedTheme } = useTheme()
  const c = COPY[language]
  const qc = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [captcha, setCaptcha] = useState("")
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
    const refresh = () => qc.invalidateQueries({ queryKey: qk.trialJob(jobId) })
    es.addEventListener("job.updated", refresh)
    es.addEventListener("job.activity", refresh)
    return () => es.close()
  }, [jobId, qc])

  const submit = async (files: File[]) => {
    const file = files[0]
    if (!file) return
    setBusy(true)
    setError(null)
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

  const corner = (pos: "tl" | "br") => ({
    content: '""', position: "absolute", width: 22, height: 22, borderColor: "var(--landing-accent)", borderStyle: "solid", borderWidth: 0,
    ...(pos === "tl" ? { left: -1, top: -1, borderTopWidth: 2, borderLeftWidth: 2, borderTopLeftRadius: "16px" }
      : { right: -1, bottom: -1, borderBottomWidth: 2, borderRightWidth: 2, borderBottomRightRadius: "16px" }),
  })

  return (
    <Box component="section" id="trial" aria-labelledby="trial-title" sx={{ py: { xs: 8, md: 11 }, scrollMarginTop: 72 }}>
      <Container maxWidth="lg">
        <Grid container spacing={{ xs: 4, md: 6 }} sx={{ alignItems: "stretch" }}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Typography component="p" sx={{ fontFamily: "var(--sml-mono)", fontSize: "0.75rem", letterSpacing: "0.12em", textTransform: "uppercase",
              color: "var(--landing-accent)" }}>{c.eyebrow}</Typography>
            <Typography id="trial-title" variant="h2" component="h2" sx={{ mt: 1.5, fontWeight: 800, letterSpacing: "-0.025em",
              fontSize: { xs: "2rem", md: "2.5rem" }, lineHeight: 1.1, textWrap: "balance" }}>{c.title}</Typography>
            <Typography sx={{ mt: 2, color: "text.secondary", fontSize: { xs: "1rem", md: "1.0625rem" }, lineHeight: 1.65 }}>{c.body}</Typography>
            {s && s.enabled && (
              <Chip label={c.left(s.remaining, s.per_day)} sx={{ mt: 2.5, bgcolor: "transparent", border: "1px solid", borderColor: "divider",
                color: "text.primary", fontWeight: 700 }} />
            )}
            <Stack direction="row" spacing={1} sx={{ mt: 2.5, color: "text.secondary", alignItems: "flex-start" }}>
              <IconLock size={18} style={{ flexShrink: 0, marginTop: 2 }} aria-hidden />
              <Typography sx={{ fontSize: "0.875rem", lineHeight: 1.5 }}>{c.privacy}</Typography>
            </Stack>
            <Box sx={{ mt: 4, pt: 3, borderTop: "1px solid", borderColor: "divider" }}>
              <Stack direction="row" spacing={1.25} sx={{ alignItems: "center", mb: 1 }}>
                <IconGift size={20} color="var(--landing-done)" aria-hidden />
                <Typography variant="h6" component="h3" sx={{ fontWeight: 700 }}>{c.signup}</Typography>
              </Stack>
              <Typography sx={{ color: "text.secondary", mb: 2, fontSize: "0.9375rem", lineHeight: 1.55 }}>{c.signupBody}</Typography>
              <Button component={Link} href="/signup" variant="outlined" endIcon={<IconArrowRight size={18} />} sx={{ minHeight: 44 }}>{c.signup}</Button>
            </Box>
          </Grid>
          <Grid size={{ xs: 12, md: 8 }}>
            <Box sx={{ position: "relative", height: "100%", minHeight: { md: 420 }, borderRadius: "16px", border: "1px solid", borderColor: "divider",
              bgcolor: "background.paper", p: { xs: 2, md: 3 }, display: "flex", flexDirection: "column", justifyContent: "center", gap: 2,
              "&::before": corner("tl"), "&::after": corner("br") }}>
              {!s?.enabled ? (
                <Stack spacing={2} sx={{ alignItems: "center", textAlign: "center", py: { xs: 4, md: 6 } }}>
                  <Typography sx={{ color: "text.secondary" }}>{status.isLoading ? "…" : c.disabled}</Typography>
                  {!status.isLoading && (
                    <>
                      <Typography sx={{ color: "text.secondary", fontSize: "0.9375rem" }}>{c.unavailableHint}</Typography>
                      <Button component={Link} href="/signup" variant="contained" endIcon={<IconArrowRight size={18} />} sx={{ minHeight: 44 }}>{c.signup}</Button>
                    </>
                  )}
                </Stack>
              ) : !jobId ? (
                <>
                  {s.remaining > 0 ? <Dropzone onFiles={submit} imagesOnly multiple={false} disabled={busy} className="min-h-72 flex-1" /> : (
                    <Box sx={{ textAlign: "center", py: 6 }}>
                      <Typography sx={{ mb: 2, fontWeight: 600 }}>{c.exhausted}</Typography>
                      <Button component={Link} href="/signup" variant="contained">{c.signup}</Button>
                    </Box>
                  )}
                  {s.captcha_required && s.captcha_site_key && (
                    <Turnstile siteKey={s.captcha_site_key} onSuccess={setCaptcha}
                      options={{ theme: resolvedTheme === "dark" ? "dark" : "light", size: "flexible" }} />
                  )}
                  {busy && (
                    <Stack direction="row" spacing={1} sx={{ alignItems: "center", color: "text.secondary" }}>
                      <IconLoader2 size={18} className="animate-spin" /><Typography variant="subtitle2">{c.analyzing}…</Typography>
                    </Stack>
                  )}
                </>
              ) : (
                <Grid container spacing={{ xs: 2.5, md: 3 }} sx={{ alignItems: "flex-start" }}>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    {/* The uploaded image gets the room: it is what the evidence is about. */}
                    <Box sx={{ position: "relative", borderRadius: "12px", overflow: "hidden", bgcolor: "background.default", border: "1px solid",
                      borderColor: "divider", aspectRatio: "4 / 3", display: "grid", placeItems: "center" }}>
                      {j?.thumbnail_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={j.thumbnail_url} alt={c.preview} className="size-full object-contain" />
                      ) : (
                        <IconLoader2 size={24} className="animate-spin" aria-hidden />
                      )}
                    </Box>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <Stack spacing={2}>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography variant="h6" noWrap>{j?.title}</Typography>
                        {running ? (
                          <Box sx={{ mt: 1 }}>
                            <LinearProgress variant="determinate" value={j?.progress ?? 0} sx={{ height: 6, borderRadius: 3 }} aria-label={c.analyzing} />
                            <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.75 }}>{j?.status === "queued" ? c.queued : c.analyzing}</Typography>
                          </Box>
                        ) : j?.status === "succeeded" ? <VerdictBadge verdict={j.verdict} aiGenerated={j.ai_generated} className="mt-2" /> : null}
                      </Box>
                      {j?.status === "succeeded" && (
                        <>
                          <ProbabilityGauge value={j.fake_probability} label={c.fake} />
                          <Stack spacing={1}>
                            {j.analyses.map((a) => (
                              <Stack key={a.id} direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 1, px: 2, py: 1.25,
                                border: "1px solid", borderColor: "divider", borderRadius: "8px" }}>
                                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{c.analyses[a.id]}</Typography>
                                {a.status === "done" ? <VerdictBadge verdict={a.verdict} probability={a.fake_probability} size="sm" />
                                  : <Typography variant="body2" sx={{ color: "text.secondary" }}>{a.status === "no_face" ? c.noFace : c.notCompleted}</Typography>}
                              </Stack>
                            ))}
                          </Stack>
                          <Typography variant="body2" sx={{ color: "text.secondary" }}>{c.disclaimer}</Typography>
                        </>
                      )}
                      {j && !running && (
                        <Button variant="outlined" startIcon={<IconRefresh size={18} />} sx={{ alignSelf: "flex-start", minHeight: 44 }}
                          onClick={() => { setJobId(null); setCaptcha("") }}>{c.again}</Button>
                      )}
                    </Stack>
                  </Grid>
                </Grid>
              )}
              {error && <Typography role="alert" sx={{ color: "error.main", fontWeight: 600 }}>{error}</Typography>}
            </Box>
          </Grid>
        </Grid>
      </Container>
    </Box>
  )
}

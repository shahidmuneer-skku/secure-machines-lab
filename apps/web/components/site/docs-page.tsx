import { BookOpen, ExternalLink } from "lucide-react"
import Link from "next/link"
import { getLocale } from "next-intl/server"

import { Eyebrow } from "@/components/sml/eyebrow"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { serverApi } from "@/lib/api/server"

type L = "en" | "ko"

const TEXT = {
  en: {
    eyebrow: "Developers", title: "Secure Machines Lab API",
    intro: "Detect deepfakes and AI-generated media from your own systems. Every request is authenticated with a personal API key and spends credits from the same wallet as the web app.",
    reference: "Full API reference", toc: "On this page",
    quickstart: "Quickstart", quickstartBody: "1. Create an API key under Account → API keys (the secret is shown once). 2. Send a file to /api/v1/detect. 3. Follow the job until it finishes. 4. Download a report.",
    auth: "Authentication", authBody: "Send the key as a Bearer token. Keys are scoped (detect:write, jobs:read, jobs:write, reports:read, credits:read, news:write), can be restricted to IP ranges and can expire. Never embed keys in browser or mobile apps.",
    detect: "Upload and detect in one call", detectBody: "POST a multipart form with the file. Optional fields: models (comma-separated ids), audit_steps (face,safety,fas), module (detect | long_video). The response is 202 Accepted with the queued job — the API never waits for inference.",
    idempotency: "Every request that creates a job or spends credits needs an Idempotency-Key header (any unique string, e.g. a UUID). Retrying with the same key returns the original response instead of charging twice.",
    progress: "Following progress", progressBody: "Poll GET /api/v1/jobs/{id} (status: queued → running → succeeded | failed | canceled) or open the Server-Sent Events stream GET /api/v1/events/stream to receive job.updated, task.progress and job.event messages in real time.",
    result: "Reading results", resultBody: "A finished job contains verdict (fake | real | no_face | inconclusive), fake_probability (0–1, weighted across the selected models), verdict_reasons (including EXIF/C2PA AI indicators) and per-model details in summary.models.",
    reports: "Reports", reportsBody: "POST /api/v1/jobs/{id}/reports with {format: pdf|hwp|csv|zip, locale: en|ko|de}, then download from /api/v1/reports/{id}/download once status is ready.",
    credits: "Credits and pricing", creditsBody: "GET /api/v1/credits/balance shows your balance; POST /api/v1/jobs/quote prices a request without running it. Prices are per file, independent of the number of models. Failed analyses are not charged.",
    errors: "Errors", errorsBody: "Errors use RFC 9457 Problem Details (application/problem+json) with a stable code and a request_id to quote to support.",
    limits: "Rate limits", limitsBody: "Each key has a per-minute limit (default 240/min, configurable per key); job creation is additionally limited to 60/min. Exceeding a limit returns 429 with a Retry-After header.",
    models: "Model catalog", modelsBody: "Pass these ids in the models field. Your account may be limited to a subset — GET /api/v1/catalog/models lists what you may use.",
    code: "Code", status: "HTTP", meaning: "Meaning", id: "id", name: "Name", media: "Media", family: "Family",
  },
  ko: {
    eyebrow: "개발자", title: "Secure Machines Lab API",
    intro: "자체 시스템에서 딥페이크와 AI 생성 미디어를 탐지하세요. 모든 요청은 개인 API 키로 인증하며, 웹 앱과 동일한 크레딧이 차감됩니다.",
    reference: "전체 API 레퍼런스", toc: "목차",
    quickstart: "빠른 시작", quickstartBody: "1. 계정 → API 키에서 키를 생성합니다(비밀 값은 한 번만 표시). 2. /api/v1/detect로 파일을 전송합니다. 3. 작업이 끝날 때까지 진행 상황을 확인합니다. 4. 보고서를 내려받습니다.",
    auth: "인증", authBody: "키를 Bearer 토큰으로 전송합니다. 키에는 권한 범위(detect:write, jobs:read, jobs:write, reports:read, credits:read, news:write), IP 대역 제한, 만료일을 설정할 수 있습니다. 브라우저나 모바일 앱에 키를 포함하지 마세요.",
    detect: "업로드와 탐지를 한 번에", detectBody: "파일을 multipart 폼으로 POST합니다. 선택 항목: models(쉼표로 구분한 모델 id), audit_steps(face,safety,fas), module(detect | long_video). 응답은 대기열에 등록된 작업과 함께 202 Accepted이며, API는 추론을 기다리지 않습니다.",
    idempotency: "작업을 생성하거나 크레딧을 사용하는 요청에는 Idempotency-Key 헤더(UUID 등 고유 문자열)가 필요합니다. 같은 키로 재시도하면 중복 과금 없이 원래 응답을 반환합니다.",
    progress: "진행 상황 확인", progressBody: "GET /api/v1/jobs/{id}를 폴링하거나(status: queued → running → succeeded | failed | canceled), Server-Sent Events 스트림 GET /api/v1/events/stream으로 job.updated, task.progress, job.event 메시지를 실시간으로 받으세요.",
    result: "결과 읽기", resultBody: "완료된 작업에는 verdict(fake | real | no_face | inconclusive), fake_probability(선택한 모델의 가중 평균, 0–1), verdict_reasons(EXIF/C2PA AI 흔적 포함), summary.models의 모델별 상세가 포함됩니다.",
    reports: "보고서", reportsBody: "POST /api/v1/jobs/{id}/reports에 {format: pdf|hwp|csv|zip, locale: en|ko|de}를 보낸 뒤, status가 ready가 되면 /api/v1/reports/{id}/download에서 내려받습니다.",
    credits: "크레딧과 요금", creditsBody: "GET /api/v1/credits/balance로 잔액을, POST /api/v1/jobs/quote로 실행 없이 요금을 확인할 수 있습니다. 요금은 모델 수와 관계없이 파일당 부과되며, 실패한 분석은 차감되지 않습니다.",
    errors: "오류", errorsBody: "오류는 RFC 9457 Problem Details(application/problem+json) 형식이며, 고정된 code와 고객지원 문의 시 사용할 request_id를 포함합니다.",
    limits: "호출 제한", limitsBody: "키마다 분당 호출 제한이 있으며(기본 240/분, 키별 설정 가능), 작업 생성은 추가로 60/분으로 제한됩니다. 초과 시 Retry-After 헤더와 함께 429를 반환합니다.",
    models: "모델 목록", modelsBody: "models 필드에 아래 id를 사용하세요. 계정에 따라 일부 모델만 허용될 수 있으며, GET /api/v1/catalog/models에서 사용 가능한 모델을 확인할 수 있습니다.",
    code: "코드", status: "HTTP", meaning: "의미", id: "id", name: "이름", media: "미디어", family: "분류",
  },
} as const

const ERRORS: [string, number, { en: string; ko: string }][] = [
  ["NOT_AUTHENTICATED", 401, { en: "Missing, invalid, expired or revoked key", ko: "키 누락·무효·만료·폐기" }],
  ["PERMISSION_DENIED", 403, { en: "Key lacks the scope or role for this action", ko: "권한 범위 또는 역할 부족" }],
  ["INSUFFICIENT_CREDITS", 402, { en: "Balance is lower than the quoted cost", ko: "잔액이 요금보다 적음" }],
  ["MODEL_NOT_ALLOWED", 403, { en: "A requested model is disabled or not allowed for you", ko: "요청한 모델을 사용할 수 없음" }],
  ["INVALID_MEDIA", 422, { en: "File type not supported or file is corrupt / too large", ko: "지원하지 않거나 손상·용량 초과 파일" }],
  ["IDEMPOTENCY_KEY_REQUIRED", 400, { en: "Add an Idempotency-Key header", ko: "Idempotency-Key 헤더 필요" }],
  ["RATE_LIMITED", 429, { en: "Too many requests; honour Retry-After", ko: "요청 과다; Retry-After 준수" }],
  ["MAINTENANCE", 503, { en: "Writes are paused during maintenance", ko: "점검 중 쓰기 요청 일시 중단" }],
]

function Code({ children }: { children: string }) {
  return <pre className="overflow-x-auto rounded-lg border bg-black/50 p-4 font-mono text-xs leading-relaxed text-[#b8f5ff]">{children}</pre>
}

function Samples({ curl, python, js }: { curl: string; python: string; js: string }) {
  return (
    <Tabs defaultValue="curl">
      <TabsList><TabsTrigger value="curl">curl</TabsTrigger><TabsTrigger value="python">Python</TabsTrigger>
        <TabsTrigger value="js">JavaScript</TabsTrigger></TabsList>
      <TabsContent value="curl"><Code>{curl}</Code></TabsContent>
      <TabsContent value="python"><Code>{python}</Code></TabsContent>
      <TabsContent value="js"><Code>{js}</Code></TabsContent>
    </Tabs>
  )
}

const BASE = "https://securemachineslab.com"

export async function DocsPage() {
  const locale = await getLocale()
  const l: L = locale === "ko" ? "ko" : "en"
  const t = TEXT[l]
  const { data: models } = await serverApi.GET("/api/v1/catalog/public-models", { params: { query: { lang: locale } } as never })
  const sections: [string, string][] = [["quickstart", t.quickstart], ["auth", t.auth], ["detect", t.detect], ["progress", t.progress],
    ["result", t.result], ["reports", t.reports], ["credits", t.credits], ["errors", t.errors], ["limits", t.limits], ["models", t.models]]
  return (
    <div className="grid gap-10 lg:grid-cols-[200px_minmax(0,1fr)]">
      <nav className="hidden lg:block" aria-label={t.toc}>
        <div className="sticky top-20 space-y-1 text-sm">
          <p className="hud-eyebrow mb-2">{t.toc}</p>
          {sections.map(([id, label]) => <a key={id} href={`#${id}`} className="block text-muted-foreground hover:text-foreground">{label}</a>)}
        </div>
      </nav>
      <article className="max-w-3xl space-y-12">
        <header className="space-y-3">
          <Eyebrow>{t.eyebrow}</Eyebrow>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{t.title}</h1>
          <p className="text-muted-foreground">{t.intro}</p>
          <div className="flex flex-wrap gap-2">
            <Button asChild><Link href="/app/api-keys">API keys</Link></Button>
            <Button asChild variant="outline"><a href="/api/docs" target="_blank"><BookOpen className="size-4" /> {t.reference} <ExternalLink className="size-3" /></a></Button>
            <Button asChild variant="ghost"><a href="/api/openapi.json">openapi.json</a></Button>
          </div>
        </header>

        <section id="quickstart" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.quickstart}</h2>
          <p className="text-muted-foreground">{t.quickstartBody}</p></section>

        <section id="auth" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.auth}</h2>
          <p className="text-muted-foreground">{t.authBody}</p>
          <Code>{`Authorization: Bearer sml_live_<prefix>_<secret>`}</Code></section>

        <section id="detect" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.detect}</h2>
          <p className="text-muted-foreground">{t.detectBody}</p>
          <p className="text-sm text-muted-foreground">{t.idempotency}</p>
          <Samples
            curl={`curl -X POST ${BASE}/api/v1/detect \\
  -H "Authorization: Bearer $SML_API_KEY" \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -F file=@photo.jpg \\
  -F models=xception,skku-aigc,center`}
            python={`import os, uuid, requests

API = "${BASE}/api/v1"
headers = {"Authorization": f"Bearer {os.environ['SML_API_KEY']}"}

with open("photo.jpg", "rb") as f:
    job = requests.post(f"{API}/detect", headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
                        files={"file": f}, data={"models": "xception,skku-aigc,center"}).json()
print(job["id"], job["status"], job["queue"])`}
            js={`const form = new FormData()
form.append("file", fileBlob, "photo.jpg")
form.append("models", "xception,skku-aigc,center")

const res = await fetch("${BASE}/api/v1/detect", {
  method: "POST",
  headers: { Authorization: \`Bearer \${process.env.SML_API_KEY}\`, "Idempotency-Key": crypto.randomUUID() },
  body: form,
})
const job = await res.json() // 202 Accepted`} />
        </section>

        <section id="progress" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.progress}</h2>
          <p className="text-muted-foreground">{t.progressBody}</p>
          <Samples
            curl={`curl -N ${BASE}/api/v1/events/stream -H "Authorization: Bearer $SML_API_KEY"
# event: job.updated
# data: {"type":"job.updated","data":{"job_id":"…","status":"running","progress":42.5}}`}
            python={`import time
while True:
    job = requests.get(f"{API}/jobs/{job['id']}", headers=headers).json()
    if job["status"] in ("succeeded", "failed", "canceled"):
        break
    print(job["stage"], job["progress"])
    time.sleep(3)`}
            js={`const es = new EventSource("/api/v1/events/stream") // browser session
es.addEventListener("job.updated", (e) => console.log(JSON.parse(e.data).data))`} />
        </section>

        <section id="result" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.result}</h2>
          <p className="text-muted-foreground">{t.resultBody}</p>
          <Code>{`{
  "id": "01a0f047-…",
  "status": "succeeded",
  "verdict": "fake",
  "fake_probability": 0.9312,
  "verdict_reasons": [{"code": "model_consensus", "models": 3},
                      {"code": "metadata_ai_indicator", "evidence": [{"source": "C2PA", "detail": "…"}]}],
  "credits_charged": 1
}`}</Code></section>

        <section id="reports" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.reports}</h2>
          <p className="text-muted-foreground">{t.reportsBody}</p></section>
        <section id="credits" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.credits}</h2>
          <p className="text-muted-foreground">{t.creditsBody}</p></section>

        <section id="errors" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.errors}</h2>
          <p className="text-muted-foreground">{t.errorsBody}</p>
          <Table><TableHeader><TableRow><TableHead>{t.code}</TableHead><TableHead>{t.status}</TableHead><TableHead>{t.meaning}</TableHead></TableRow></TableHeader>
            <TableBody>{ERRORS.map(([code, status, meaning]) => (
              <TableRow key={code}><TableCell className="font-mono text-xs">{code}</TableCell><TableCell>{status}</TableCell><TableCell>{meaning[l]}</TableCell></TableRow>))}
            </TableBody></Table></section>

        <section id="limits" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.limits}</h2>
          <p className="text-muted-foreground">{t.limitsBody}</p></section>

        <section id="models" className="scroll-mt-20 space-y-3"><h2 className="text-xl font-semibold">{t.models}</h2>
          <p className="text-muted-foreground">{t.modelsBody}</p>
          <Table><TableHeader><TableRow><TableHead>{t.id}</TableHead><TableHead>{t.name}</TableHead><TableHead>{t.media}</TableHead>
            <TableHead>{t.family}</TableHead></TableRow></TableHeader>
            <TableBody>{(models ?? []).map((m) => (
              <TableRow key={m.id}><TableCell className="font-mono text-xs">{m.id}</TableCell>
                <TableCell>{m.name}<span className="block text-xs text-muted-foreground">{m.description}</span></TableCell>
                <TableCell className="space-x-1">{m.media.map((x) => <Badge key={x} variant="outline">{x}</Badge>)}</TableCell>
                <TableCell className="text-xs">{m.family}</TableCell></TableRow>))}
            </TableBody></Table></section>
      </article>
    </div>
  )
}

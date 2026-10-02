"use client"

import Avatar from "@mui/material/Avatar"
import Box from "@mui/material/Box"
import LinearProgress from "@mui/material/LinearProgress"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import { IconArrowUpRight, IconMovie, IconPhoto } from "@tabler/icons-react"
import { useTranslations } from "next-intl"

import { LogoMark } from "@/components/brand/logo"
import { Markdown } from "@/components/results/explain-reports"
import { VerdictBadge } from "@/components/sml/verdict-badge"
import type { Job } from "@/lib/api/types"
import type { ChatMessage } from "@/lib/assistant"

/** One analysed file: live progress, then the verdict as users see it, with a link to the full result. */
export function ResultCard({ job }: { job: Job }) {
  const t = useTranslations("assistant")
  const running = job.status === "queued" || job.status === "running"
  const KindIcon = job.media_type === "video" ? IconMovie : IconPhoto
  return (
    <Box component="a" href={`/app/results/${job.id}`} target="_blank" rel="noopener"
      sx={{ display: "flex", gap: 1.5, alignItems: "center", p: 1.25, pr: 1.5, borderRadius: "12px", border: "1px solid",
        borderColor: "divider", bgcolor: "background.paper", color: "text.primary", textDecoration: "none", minWidth: 0,
        transition: "border-color .15s", "&:hover": { borderColor: "primary.main" } }}>
      <Box sx={{ width: 52, height: 52, borderRadius: "9px", overflow: "hidden", flexShrink: 0, bgcolor: "action.hover",
        display: "grid", placeItems: "center", color: "text.secondary" }}>
        {job.thumbnail_url
          // eslint-disable-next-line @next/next/no-img-element -- private, short-lived thumbnail served by the API
          ? <img src={job.thumbnail_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <KindIcon size={22} stroke={1.6} />}
      </Box>
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="subtitle2" noWrap sx={{ fontWeight: 600 }}>{job.title}</Typography>
        {running ? (
          <Box sx={{ mt: 0.75 }}>
            <LinearProgress variant={job.status === "queued" ? "indeterminate" : "determinate"} value={job.progress}
              sx={{ height: 5, borderRadius: 3 }} aria-label={t("analysing")} />
            <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
              {job.status === "queued" ? t("queued") : `${t("analysing")} · ${Math.round(job.progress)}%`}
            </Typography>
          </Box>
        ) : job.status === "succeeded" && job.verdict === "no_face" ? (
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{t("noFace")}</Typography>
        ) : job.status === "succeeded" ? (
          <Stack direction="row" spacing={1} sx={{ mt: 0.5, alignItems: "center" }}>
            <VerdictBadge verdict={job.verdict} aiGenerated={job.ai_generated} size="sm" />
            {job.fake_probability != null && (
              <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>
                {Math.round(job.fake_probability * 100)}%
              </Typography>
            )}
          </Stack>
        ) : (
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
            {job.status === "canceled" ? t("canceled") : job.status === "expired" ? t("expired") : t("notCompleted")}
          </Typography>
        )}
      </Box>
      <Box sx={{ color: "text.secondary", display: "flex" }} aria-label={t("openResult")}><IconArrowUpRight size={17} /></Box>
    </Box>
  )
}

function Files({ message }: { message: ChatMessage }) {
  if (message.jobs.length) {
    // The user's files, on the user's side of the conversation.
    return (
      <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", justifyContent: "flex-end" }}>
        {message.jobs.map((j) => <Box key={j.id} sx={{ width: { xs: "100%", sm: 300 } }}><ResultCard job={j} /></Box>)}
      </Stack>
    )
  }
  if (!message.attachments.length) return null
  return (
    <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", justifyContent: "flex-end" }}>
      {message.attachments.map((a) => (
        <Box key={a.id} sx={{ px: 1.25, py: 0.75, borderRadius: "8px", border: "1px solid", borderColor: "divider",
          fontSize: "0.8125rem" }}>{a.name}</Box>
      ))}
    </Stack>
  )
}

export function UserBubble({ message, pendingFiles }: { message: ChatMessage; pendingFiles?: { name: string; url: string | null }[] }) {
  return (
    <Stack spacing={1} sx={{ alignItems: "flex-end", alignSelf: "stretch" }}>
      {pendingFiles && pendingFiles.length > 0 && (
        <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {pendingFiles.map((f) => (
            <Box key={f.name} sx={{ width: 64, height: 64, borderRadius: "10px", overflow: "hidden", bgcolor: "action.hover" }}>
              {/* eslint-disable-next-line @next/next/no-img-element -- local preview of a file being sent */}
              {f.url && <img src={f.url} alt={f.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />}
            </Box>
          ))}
        </Stack>
      )}
      {message.content && (
        <Box sx={{ maxWidth: { xs: "92%", md: "78%" }, px: 2, py: 1.25, borderRadius: "16px 16px 4px 16px",
          bgcolor: "primary.light", color: "text.primary", whiteSpace: "pre-wrap", wordBreak: "break-word",
          fontSize: "0.9375rem", lineHeight: 1.6 }}>
          {message.content}
        </Box>
      )}
      <Box sx={{ width: "100%" }}><Files message={message} /></Box>
    </Stack>
  )
}

export function AssistantBubble({ content, status, streaming = false, note }: {
  content: string
  status?: string
  streaming?: boolean
  note?: string
}) {
  const t = useTranslations("assistant")
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start" }}>
      <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: "transparent", mt: 0.25 }}>
        <LogoMark className="h-7" />
      </Avatar>
      <Box sx={{ minWidth: 0, flex: 1, fontSize: "0.9375rem", lineHeight: 1.65, "& p": { my: 0.75 },
        "& ul, & ol": { my: 0.75, pl: 3 }, "& li": { my: 0.25 }, "& pre": { whiteSpace: "pre-wrap" },
        // Headings in a chat reply stay close to the text size (the result page's style is for documents).
        "& .prose :is(h1, h2, h3, h4)": { fontSize: "1rem", fontWeight: 700, textTransform: "none", letterSpacing: "normal",
          lineHeight: 1.4, mt: 2, mb: 0.75 },
        "& .prose :is(h1, h2)": { fontSize: "1.0625rem" } }}>
        {content ? <Markdown breaks>{content}</Markdown> : null}
        {streaming && !content && (
          <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", py: 1, color: "text.secondary" }} aria-live="polite">
            {[0, 1, 2].map((i) => (
              <Box key={i} sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: "currentColor",
                animation: "sml-dot 1.2s ease-in-out infinite", animationDelay: `${i * 0.15}s`,
                "@keyframes sml-dot": { "0%, 80%, 100%": { opacity: 0.25 }, "40%": { opacity: 1 } },
                "@media (prefers-reduced-motion: reduce)": { animation: "none", opacity: 0.6 } }} />
            ))}
            {note && <Typography variant="body2" sx={{ ml: 1 }}>{note}</Typography>}
          </Stack>
        )}
        {status === "stopped" && <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{t("stopped")}</Typography>}
        {status === "failed" && <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{t("interrupted")}</Typography>}
      </Box>
    </Stack>
  )
}

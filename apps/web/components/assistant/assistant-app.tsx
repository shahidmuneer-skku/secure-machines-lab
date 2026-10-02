"use client"

import Alert from "@mui/material/Alert"
import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Drawer from "@mui/material/Drawer"
import IconButton from "@mui/material/IconButton"
import Skeleton from "@mui/material/Skeleton"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import { IconCoins, IconHelpCircle, IconMenu2, IconMovie, IconPhotoScan, IconUpload, type Icon } from "@tabler/icons-react"
import { useQueryClient } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { useEffect, useEffectEvent, useRef, useState, type DragEvent } from "react"

import { CreditChip, LanguageMenu, ThemeButton } from "@/components/app-shell/header-controls"
import { LogoMark } from "@/components/brand/logo"
import { isRunning, patchJob, useConversation, useConversationActions } from "@/hooks/use-assistant"
import { useEventStream } from "@/hooks/use-event-stream"
import { useMe } from "@/hooks/use-me"
import { useUploads } from "@/hooks/use-uploads"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import { CONVERSATIONS_URL, streamChat, type ChatMessage, type ConversationDetail } from "@/lib/assistant"

import { Composer, type ComposerHandle } from "./composer"
import { ConversationList } from "./conversation-list"
import { AssistantBubble, UserBubble } from "./thread"

/**
 * The assistant, a full-page chat app of its own (owner, 2026-10-02): conversations on the left, the
 * chat on the right; the dashboard opens it in a new tab. Attached files are analysed like any
 * detection; once their analyses finish the assistant explains the results unprompted.
 */

const SIDEBAR_WIDTH = 280
/** After Stop, the server stores what was said; give it a moment before reloading the conversation. */
const STOP_SETTLE_MS = 700
const SUGGESTION_ICONS: Icon[] = [IconPhotoScan, IconMovie, IconHelpCircle, IconCoins]

/** The exchange in progress: the user's words until the server has stored them, then the reply as it streams. */
type Live = {
  conversationId: string | null
  content: string
  files: { name: string; url: string | null }[]
  userMessage: ChatMessage | null
  resultsFor: string | null
  text: string
  reply: ChatMessage | null
  stopped: boolean
}

type Failure = { message: string; buy?: boolean; retry?: () => void }

/** User messages whose analyses have all finished and that the assistant has not summarised yet. */
function awaitingSummary(c: ConversationDetail | undefined): ChatMessage[] {
  return (c?.messages ?? []).filter((m) => m.role === "user" && m.started_analyses && !m.results_reply
    && m.jobs.length > 0 && m.jobs.every((j) => !isRunning(j.status)))
}

function pendingMessage(content: string): ChatMessage {
  return { id: "pending", role: "user", status: "complete", content, created_at: "", attachments: [], jobs: [],
    started_analyses: false, results_reply: null } as unknown as ChatMessage
}

export function AssistantApp() {
  const t = useTranslations("assistant")
  const tr = useTranslations()
  const locale = useLocale()
  const qc = useQueryClient()
  const params = useSearchParams()
  const jobParam = params.get("job")
  // The open conversation. Set together with the reply it is about (one render, no flicker); the URL
  // (?c=) follows it, and back/forward navigation sets it from the URL.
  const urlId = params.get("c")
  const [activeId, setActiveId] = useState(urlId)
  const [seenUrlId, setSeenUrlId] = useState(urlId)
  if (urlId !== seenUrlId) {
    setSeenUrlId(urlId)
    setActiveId(urlId)
  }
  const { data: me } = useMe()
  const allowed = !!me?.capabilities?.includes("use_assistant")

  // Analyses in a conversation update live: progress is patched in place, a finished job is reloaded.
  const { connected } = useEventStream(allowed, (name, event) => {
    if (name !== "job.updated" || !activeId) return
    const key = qk.conversation(activeId)
    const current = qc.getQueryData<ConversationDetail>(key)
    if (!current?.messages.some((m) => m.jobs.some((j) => j.id === event.job_id))) return
    qc.setQueryData(key, patchJob(current, event))
    if (!isRunning(String(event.status))) void qc.invalidateQueries({ queryKey: key })
  })
  const conversation = useConversation(allowed ? activeId : null, connected)
  const { create, refresh } = useConversationActions()
  const uploads = useUploads()
  const composer = useRef<ComposerHandle>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const abort = useRef<AbortController | null>(null)
  const summarised = useRef(new Set<string>())
  const opened = useRef<string | null>(null)
  const [draft, setDraft] = useState("")
  const [live, setLive] = useState<Live | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [dragging, setDragging] = useState(false)

  const messages = conversation.data?.messages ?? []
  const stored = new Set(messages.map((m) => m.id))
  const shown = live && live.conversationId === activeId ? live : null
  const empty = !messages.length && !shown
  const title = conversation.data?.title || (activeId ? t("untitled") : t("newChat"))

  const nearBottom = () => {
    const el = scroller.current
    return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 140
  }

  // Follow the conversation as it grows, unless the user has scrolled up to read.
  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  })

  const go = (id: string | null, replace = false) => {
    const url = id ? `/assistant?c=${id}` : "/assistant"
    setActiveId(id)
    // The History API keeps Next's router (and useSearchParams) in sync without a server round trip.
    if (replace) window.history.replaceState(null, "", url)
    else window.history.pushState(null, "", url)
    setMenuOpen(false)
    if (!replace) setFailure(null)
    stick.current = true
  }

  const describe = (e: unknown): Failure => {
    if (isApiError(e)) {
      if (e.status === 402) return { message: t("insufficient"), buy: true }
      if (e.status === 400 && e.detail) return { message: e.detail }
      if (tr.has(`errors.${e.code}`)) return { message: tr(`errors.${e.code}`) }
    }
    return { message: t("error") }
  }

  /** Streams one reply into `live` and resolves once it is stored, stopped or has failed. */
  const run = async (conversationId: string, url: string, body: object, start: Live) => {
    const controller = new AbortController()
    abort.current = controller
    setLive({ ...start, conversationId })
    let failed = false
    let error: unknown
    try {
      await streamChat(url, body, {
        meta: (m) => {
          if (m.user_message) setLive((l) => l && { ...l, userMessage: m.user_message ?? null })
          void refresh()
          void qc.invalidateQueries({ queryKey: qk.conversation(conversationId) })
        },
        delta: (text) => setLive((l) => l && { ...l, text: l.text + text }),
        done: (message) => setLive((l) => l && { ...l, reply: message }),
        error: (_detail, code) => {
          failed = code !== "CONFLICT" // another window summarised these results first
        },
      }, controller.signal)
    } catch (e) {
      if (controller.signal.aborted) {
        setLive((l) => l && { ...l, stopped: true })
        await new Promise((resolve) => setTimeout(resolve, STOP_SETTLE_MS))
      } else {
        error = e
      }
    } finally {
      abort.current = null
    }
    await Promise.all([qc.invalidateQueries({ queryKey: qk.conversation(conversationId) }), refresh()])
    setLive(null)
    return { error, failed }
  }

  const send = async (content: string, jobIds: string[] = []) => {
    if (live || !allowed) return
    const text = content.trim()
    const taken = uploads.take()
    const mediaIds = taken.flatMap((i) => (i.state === "ready" && i.media ? [i.media.id] : []))
    if (!text && !mediaIds.length && !jobIds.length) {
      uploads.restore(taken)
      return
    }
    setFailure(null)
    setDraft("")
    stick.current = true
    const start: Live = {
      conversationId: activeId, content: text, userMessage: null, resultsFor: null, text: "", reply: null, stopped: false,
      files: taken.map((i) => ({ name: i.file.name, url: i.kind === "image" ? i.previewUrl : null })),
    }
    setLive(start)
    let conversationId = activeId
    let result: { error?: unknown; failed?: boolean }
    try {
      if (!conversationId) {
        conversationId = (await create.mutateAsync()).id
        go(conversationId, true)
      }
      result = await run(conversationId, `${CONVERSATIONS_URL}/${conversationId}/messages`,
        { content: text, media_ids: mediaIds, job_ids: jobIds, locale }, start)
    } catch (e) {
      setLive(null)
      result = { error: e }
    }
    if (result.error) {
      // Nothing was sent: the message and its files go back into the box.
      uploads.restore(taken)
      setDraft((d) => d || text)
      setFailure(describe(result.error))
      return
    }
    taken.forEach((i) => i.previewUrl && URL.revokeObjectURL(i.previewUrl))
    if (result.failed) setFailure({ message: t("error") })
  }

  const summarise = async (conversationId: string, message: ChatMessage) => {
    summarised.current.add(message.id)
    stick.current = nearBottom()
    const start: Live = { conversationId, content: "", files: [], userMessage: null, resultsFor: message.id, text: "",
      reply: null, stopped: false }
    const { error, failed } = await run(conversationId,
      `${CONVERSATIONS_URL}/${conversationId}/messages/${message.id}/results`, { locale }, start)
    const summarisedElsewhere = isApiError(error) && error.status === 409
    if ((error && !summarisedElsewhere) || failed) {
      setFailure({ message: t("error"), retry: () => {
        setFailure(null)
        void summarise(conversationId, message)
      } })
    }
  }

  // Once every analysis a message started has finished, the assistant explains the results.
  const summariseNext = useEffectEvent(() => {
    if (live || !activeId || !allowed) return
    const next = awaitingSummary(conversation.data).find((m) => !summarised.current.has(m.id))
    if (next) void summarise(activeId, next)
  })
  useEffect(() => summariseNext(), [live, activeId, allowed, conversation.data])

  // "Ask the assistant" on a result opens /assistant?job=<id>: a new chat about that result.
  const openJob = useEffectEvent((jobId: string) => {
    if (live || opened.current === jobId) return
    opened.current = jobId
    void send(t("explainResult"), [jobId])
  })
  useEffect(() => {
    if (allowed && jobParam) openJob(jobParam)
  }, [allowed, jobParam])

  const stop = () => abort.current?.abort()

  const onDragOver = (e: DragEvent) => {
    if (!e.dataTransfer.types.includes("Files")) return
    e.preventDefault()
    setDragging(true)
  }
  const onDragLeave = (e: DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false)
  }
  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) uploads.add(Array.from(e.dataTransfer.files))
  }

  if (me && !allowed) {
    return (
      <Box sx={{ minHeight: "100dvh", display: "grid", placeItems: "center", p: 3, bgcolor: "background.default" }}>
        <Stack spacing={2.5} sx={{ alignItems: "center", textAlign: "center", maxWidth: 420 }}>
          <LogoMark className="h-14" />
          <Typography>{t("unavailable")}</Typography>
          <Button variant="contained" href="/app">{t("back")}</Button>
        </Stack>
      </Box>
    )
  }

  const list = (
    <ConversationList active={activeId} onSelect={(id) => go(id)} onNew={() => {
      go(null)
      composer.current?.focus()
    }} onDeleted={(id) => {
      if (id === activeId) go(null, true)
    }} />
  )

  const suggestions = t.raw("welcome.suggestions") as string[]

  return (
    <Box sx={{ display: "flex", height: "100dvh", bgcolor: "background.default", overflow: "hidden" }}>
      <Box component="aside" sx={{ width: SIDEBAR_WIDTH, flexShrink: 0, display: { xs: "none", md: "block" },
        borderRight: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}>
        {me && list}
      </Box>
      <Drawer variant="temporary" open={menuOpen} onClose={() => setMenuOpen(false)} ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: "block", md: "none" } }} slotProps={{ paper: { sx: { width: SIDEBAR_WIDTH, bgcolor: "background.paper" } } }}>
        {me && list}
      </Drawer>

      <Box component="main" onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
        sx={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", position: "relative" }}>
        <Box component="header" sx={{ height: 64, flexShrink: 0, display: "flex", alignItems: "center", gap: 1,
          px: { xs: 1.5, md: 3 }, borderBottom: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}>
          <IconButton aria-label={t("conversations")} onClick={() => setMenuOpen(true)}
            sx={{ display: { xs: "inline-flex", md: "none" }, color: "text.secondary" }}>
            <IconMenu2 size={22} stroke={1.5} />
          </IconButton>
          <Typography component="h1" noWrap sx={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: "1rem" }}>
            {conversation.isLoading ? <Skeleton width={180} /> : title}
          </Typography>
          <Stack direction="row" spacing={{ xs: 0.25, sm: 1 }} sx={{ alignItems: "center" }}>
            <CreditChip />
            <LanguageMenu signedIn />
            <ThemeButton />
          </Stack>
        </Box>

        <Box ref={scroller} onScroll={() => (stick.current = nearBottom())} sx={{ flex: 1, overflowY: "auto" }}>
          <Box sx={{ maxWidth: 820, mx: "auto", px: { xs: 2, md: 3 }, py: { xs: 3, md: 4 } }}>
            {conversation.isLoading ? (
              <Stack spacing={3}>
                <Skeleton variant="rounded" height={48} sx={{ alignSelf: "flex-end", width: "60%" }} />
                <Skeleton variant="rounded" height={110} />
              </Stack>
            ) : empty ? (
              <Stack sx={{ alignItems: "center", textAlign: "center", pt: { xs: 4, md: 10 } }}>
                <LogoMark className="h-14" />
                <Typography component="h2" variant="h3" sx={{ mt: 2.5 }}>{t("welcome.title")}</Typography>
                <Typography sx={{ color: "text.secondary", maxWidth: 520, mt: 1 }}>{t("welcome.subtitle")}</Typography>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.25, mt: 4, width: "100%",
                  maxWidth: 640 }}>
                  {suggestions.map((s, i) => {
                    const SuggestionIcon = SUGGESTION_ICONS[i] ?? IconHelpCircle
                    return (
                      <Button key={s} variant="outlined" disabled={!allowed || !!live}
                        startIcon={<SuggestionIcon size={19} stroke={1.6} />}
                        onClick={() => {
                          if (i === 0) {
                            // "Is this photo AI-generated?" needs a photo: ask for one first.
                            setDraft(s)
                            composer.current?.openFiles()
                          } else {
                            void send(s)
                          }
                        }}
                        sx={{ justifyContent: "flex-start", textAlign: "left", py: 1.5, px: 2, borderRadius: "12px",
                          color: "text.primary", borderColor: "divider", fontWeight: 500, lineHeight: 1.4,
                          "& .MuiButton-startIcon": { color: "primary.main" } }}>
                        {s}
                      </Button>
                    )
                  })}
                </Box>
              </Stack>
            ) : (
              <Stack spacing={3.5}>
                {messages.map((m) => (m.role === "user"
                  ? <UserBubble key={m.id} message={m} />
                  : <AssistantBubble key={m.id} content={m.content} status={m.status} />))}
                {shown && !shown.resultsFor && !(shown.userMessage && stored.has(shown.userMessage.id)) && (
                  <UserBubble message={shown.userMessage ?? pendingMessage(shown.content)}
                    pendingFiles={shown.userMessage ? undefined : shown.files} />
                )}
                {shown && !(shown.reply && stored.has(shown.reply.id)) && (
                  <AssistantBubble content={shown.text} streaming={!shown.reply && !shown.stopped}
                    status={shown.stopped ? "stopped" : undefined} note={shown.resultsFor ? t("summarising") : undefined} />
                )}
              </Stack>
            )}
          </Box>
        </Box>

        <Box sx={{ flexShrink: 0, px: { xs: 1.5, md: 3 }, pb: { xs: 1.5, md: 2 }, pt: 1 }}>
          <Box sx={{ maxWidth: 820, mx: "auto" }}>
            {failure && (
              <Alert severity={failure.buy ? "warning" : "error"} onClose={() => setFailure(null)} sx={{ mb: 1.5 }}
                action={failure.buy ? (
                  <Button color="inherit" size="small" href="/app/billing" target="_blank" rel="noopener">{t("buyCredits")}</Button>
                ) : failure.retry ? (
                  <Button color="inherit" size="small" onClick={failure.retry}>{t("retry")}</Button>
                ) : undefined}>
                {failure.message}
              </Alert>
            )}
            <Composer ref={composer} value={draft} onChange={setDraft} uploads={uploads} streaming={!!shown && !!live}
              disabled={!allowed || (!!live && !shown)} onSend={() => void send(draft)} onStop={stop} />
            <Typography variant="body2" sx={{ color: "text.secondary", textAlign: "center", mt: 1, fontSize: "0.75rem" }}>
              {t("disclaimer")}
            </Typography>
          </Box>
        </Box>

        {dragging && (
          <Box aria-hidden sx={{ position: "absolute", inset: 8, borderRadius: "16px", border: "2px dashed",
            borderColor: "primary.main", bgcolor: "rgb(66 109 232 / 0.08)", display: "grid", placeItems: "center",
            pointerEvents: "none", zIndex: 2 }}>
            <Stack spacing={1} sx={{ alignItems: "center", color: "primary.main" }}>
              <IconUpload size={34} stroke={1.5} />
              <Typography sx={{ fontWeight: 600 }}>{t("dropHere")}</Typography>
            </Stack>
          </Box>
        )}
      </Box>
    </Box>
  )
}

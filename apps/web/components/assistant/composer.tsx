"use client"

import Box from "@mui/material/Box"
import CircularProgress from "@mui/material/CircularProgress"
import IconButton from "@mui/material/IconButton"
import InputBase from "@mui/material/InputBase"
import Stack from "@mui/material/Stack"
import Tooltip from "@mui/material/Tooltip"
import Typography from "@mui/material/Typography"
import { IconAlertTriangle, IconArrowUp, IconMovie, IconPaperclip, IconPlayerStopFilled, IconX } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import { useTranslations } from "next-intl"
import { forwardRef, useImperativeHandle, useRef, type KeyboardEvent } from "react"

import { quoteRequest } from "@/hooks/use-submit-jobs"
import type { useUploads } from "@/hooks/use-uploads"
import { IMAGE_EXT, VIDEO_EXT } from "@/lib/upload"

export type ComposerHandle = { openFiles: () => void; focus: () => void }

type Uploads = ReturnType<typeof useUploads>

/** The message box: text, attachments (uploaded right away, priced before sending), send or stop. */
export const Composer = forwardRef<ComposerHandle, {
  value: string
  onChange: (value: string) => void
  uploads: Uploads
  streaming: boolean
  /** Sending is not possible right now (e.g. a reply is being written in another conversation). */
  disabled?: boolean
  onSend: () => void
  onStop: () => void
}>(function Composer({ value, onChange, uploads, streaming, disabled = false, onSend, onStop }, ref) {
  const t = useTranslations("assistant")
  const fileInput = useRef<HTMLInputElement>(null)
  const textInput = useRef<HTMLTextAreaElement>(null)
  useImperativeHandle(ref, () => ({ openFiles: () => fileInput.current?.click(), focus: () => textInput.current?.focus() }))

  const media = uploads.ready.map((r) => r.media!)
  const quote = useQuery({
    queryKey: ["quote", media.map((m) => m.id)],
    queryFn: () => quoteRequest({ media }),
    enabled: media.length > 0,
    retry: false,
  })
  const hasInvalid = uploads.items.some((i) => i.state === "invalid" || i.state === "error")
  const canSend = !streaming && !disabled && !uploads.busy && !hasInvalid && (value.trim().length > 0 || media.length > 0)
  const short = !!quote.data && !quote.data.affordable

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter is a new line; Enter while composing Hangul (IME) does nothing.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      if (canSend) onSend()
    }
  }

  return (
    <Box sx={{ borderRadius: "18px", border: "1px solid", borderColor: "divider", bgcolor: "background.paper",
      boxShadow: "0 8px 28px -12px rgb(0 0 0 / 0.25)", "&:focus-within": { borderColor: "primary.main" } }}>
      {uploads.items.length > 0 && (
        <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap", px: 1.5, pt: 1.5 }}>
          {uploads.items.map((item) => (
            <Box key={item.key} sx={{ position: "relative", width: 64, height: 64, borderRadius: "10px", overflow: "hidden",
              bgcolor: "action.hover", display: "grid", placeItems: "center", border: "1px solid", borderColor: "divider" }}>
              {item.previewUrl && item.kind === "image"
                // eslint-disable-next-line @next/next/no-img-element -- local preview of a chosen file
                ? <img src={item.previewUrl} alt={item.file.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <IconMovie size={22} />}
              {item.state === "uploading" && (
                <Box sx={{ position: "absolute", inset: 0, bgcolor: "rgb(0 0 0 / .45)", display: "grid", placeItems: "center" }}>
                  <CircularProgress size={22} variant="determinate" value={item.progress * 100} sx={{ color: "#fff" }}
                    aria-label={t("uploading")} />
                </Box>
              )}
              {(item.state === "invalid" || item.state === "error") && (
                <Tooltip title={t("failedFile")}>
                  <Box sx={{ position: "absolute", inset: 0, bgcolor: "rgb(201 63 35 / .55)", display: "grid", placeItems: "center",
                    color: "#fff" }}><IconAlertTriangle size={20} /></Box>
                </Tooltip>
              )}
              <IconButton size="small" aria-label={`${t("remove")}: ${item.file.name}`} onClick={() => uploads.remove(item.key)}
                sx={{ position: "absolute", top: 2, right: 2, width: 20, height: 20, bgcolor: "rgb(0 0 0 / .6)", color: "#fff",
                  "&:hover": { bgcolor: "rgb(0 0 0 / .8)" } }}>
                <IconX size={13} />
              </IconButton>
            </Box>
          ))}
        </Stack>
      )}
      <InputBase inputRef={textInput} value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown}
        onPaste={(e) => {
          const files = Array.from(e.clipboardData.files)
          if (files.length) {
            e.preventDefault()
            uploads.add(files)
          }
        }}
        placeholder={t("placeholder")} multiline maxRows={8} fullWidth inputProps={{ "aria-label": t("placeholder") }}
        sx={{ px: 2, pt: 1.5, pb: 0.5, fontSize: "0.9375rem", lineHeight: 1.6 }} />
      <Stack direction="row" sx={{ alignItems: "center", gap: 1, px: 1, pb: 1 }}>
        <input ref={fileInput} type="file" hidden multiple
          accept={[...IMAGE_EXT, ...VIDEO_EXT].map((e) => `.${e}`).join(",")}
          onChange={(e) => {
            uploads.add(Array.from(e.target.files ?? []))
            e.target.value = ""
          }} />
        <Tooltip title={t("attach")}>
          <IconButton onClick={() => fileInput.current?.click()} aria-label={t("attach")} sx={{ color: "text.secondary" }}>
            <IconPaperclip size={20} />
          </IconButton>
        </Tooltip>
        <Typography variant="body2" sx={{ color: short ? "warning.main" : "text.secondary", flex: 1, minWidth: 0 }} noWrap
          aria-live="polite">
          {uploads.busy ? t("uploading") : media.length && quote.data
            ? `${t("priceNote", { count: media.length, credits: quote.data.credits })}${short ? ` · ${t("insufficient")}` : ""}`
            : ""}
        </Typography>
        {streaming ? (
          <Tooltip title={t("stop")}>
            <IconButton onClick={onStop} aria-label={t("stop")}
              sx={{ bgcolor: "text.primary", color: "background.paper", "&:hover": { bgcolor: "text.secondary" } }}>
              <IconPlayerStopFilled size={16} />
            </IconButton>
          </Tooltip>
        ) : (
          <Tooltip title={t("send")}>
            <span>
              <IconButton onClick={onSend} disabled={!canSend} aria-label={t("send")}
                sx={{ bgcolor: "#426DE8", color: "#fff", "&:hover": { bgcolor: "#3557C7" },
                  "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" } }}>
                <IconArrowUp size={18} />
              </IconButton>
            </span>
          </Tooltip>
        )}
      </Stack>
    </Box>
  )
})

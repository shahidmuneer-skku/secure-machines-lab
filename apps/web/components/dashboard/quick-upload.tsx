"use client"

import { Loader2, Send } from "lucide-react"
import { useTranslations } from "next-intl"

import { Button } from "@/components/ui/button"
import { Dropzone } from "@/components/detect/dropzone"
import { UploadList } from "@/components/detect/upload-list"
import { useSubmitJobs } from "@/hooks/use-submit-jobs"
import { useUploads } from "@/hooks/use-uploads"

/** Drop files → queued. The full flow (with the price) lives on /app/detect. */
export function QuickUpload() {
  const t = useTranslations("dashboard.quick")
  const uploads = useUploads()
  const submit = useSubmitJobs()

  const send = async () => {
    await submit.mutateAsync({ media: uploads.ready.map((r) => r.media!) })
    uploads.clear()
  }

  return (
    <div className="space-y-3">
      <Dropzone onFiles={uploads.add} compact />
      <UploadList items={uploads.items} onRemove={uploads.remove} onRetry={uploads.retry} />
      {uploads.items.length > 0 && (
        <Button className="w-full" onClick={send} disabled={!uploads.ready.length || uploads.busy || submit.isPending}>
          {submit.isPending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          {t("analyze", { count: uploads.ready.length })}
        </Button>
      )}
    </div>
  )
}

"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Ban, Eye, MoreHorizontal, RotateCw, Trash2 } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { api, data } from "@/lib/api/client"
import { newIdempotencyKey } from "@/lib/api/csrf"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"
import type { Job } from "@/lib/api/types"

export function useJobMutations(jobId: string) {
  const qc = useQueryClient()
  const t = useTranslations("results")
  const router = useRouter()
  const refresh = () => {
    qc.invalidateQueries({ queryKey: qk.jobsAll })
    qc.invalidateQueries({ queryKey: qk.balance })
  }
  const onError = (e: unknown) => toast.error(isApiError(e) ? e.detail : t("actionFailed"))
  const cancel = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/jobs/{id}/cancel", { params: { path: { id: jobId } } })),
    onSuccess: () => { toast.success(t("canceled")); refresh() }, onError,
  })
  const rerun = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/jobs/{id}/rerun", {
      params: { path: { id: jobId } }, headers: { "Idempotency-Key": newIdempotencyKey() } })),
    onSuccess: (job) => { toast.success(t("rerunQueued")); refresh(); router.push(`/app/results/${job.id}`) }, onError,
  })
  const remove = useMutation({
    mutationFn: async () => api.DELETE("/api/v1/jobs/{id}", { params: { path: { id: jobId } } }),
    onSuccess: () => { toast.success(t("deleted")); refresh() }, onError,
  })
  return { cancel, rerun, remove }
}

export function JobActions({ job, onDeleted }: { job: Job; onDeleted?: () => void }) {
  const t = useTranslations("results")
  const { cancel, rerun, remove } = useJobMutations(job.id)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const active = job.status === "queued" || job.status === "running"
  const finished = job.status === "succeeded" || job.status === "failed" || job.status === "canceled"
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={t("actions")}><MoreHorizontal className="size-4" /></Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={job.kind === "news" ? `/app/news/${job.id}` : `/app/results/${job.id}`}><Eye /> {t("view")}</Link>
          </DropdownMenuItem>
          {finished && job.kind !== "news" && (
            <DropdownMenuItem onSelect={() => rerun.mutate()}><RotateCw /> {t("rerun")}</DropdownMenuItem>
          )}
          {active && <DropdownMenuItem onSelect={() => cancel.mutate()}><Ban /> {t("cancel")}</DropdownMenuItem>}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirmDelete(true)}><Trash2 /> {t("delete")}</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("deleteBody")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("keep")}</AlertDialogCancel>
            <AlertDialogAction onClick={() => remove.mutate(undefined, { onSuccess: onDeleted })}>{t("delete")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

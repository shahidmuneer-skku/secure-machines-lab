"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import {
  AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"

export type BlockTarget = { id: string; email: string; is_active: boolean }

/**
 * Confirms blocking (with a reason kept on the account) or unblocking a user. Blocking signs the
 * user out everywhere and stops their API keys; the server refuses self-blocks and, for anyone
 * but a super admin, blocking a super admin.
 */
export function BlockUserDialog({ user: target, open, onOpenChange }: {
  user: BlockTarget | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const t = useTranslations("admin.block")
  const qc = useQueryClient()
  const [reason, setReason] = useState("")
  // Keep showing the last user while the dialog animates closed (the caller clears it on close).
  const [user, setUser] = useState(target)
  if (target && target !== user) setUser(target)
  const blocking = !!user?.is_active
  const submit = useMutation({
    mutationFn: async (u: BlockTarget) => data(u.is_active
      ? await api.POST("/api/v1/admin/users/{id}/disable", { params: { path: { id: u.id } }, body: { reason } })
      : await api.POST("/api/v1/admin/users/{id}/enable", { params: { path: { id: u.id } } })),
    onSuccess: async (u) => {
      toast.success(u.is_active ? t("unblocked", { email: u.email }) : t("blocked", { email: u.email }))
      onOpenChange(false)
      setReason("")
      await qc.invalidateQueries({ queryKey: qk.admin() })
    },
    onError: (e) => toast.error(isApiError(e) ? e.detail : t("failed")),
  })

  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!submit.isPending) onOpenChange(v) }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{blocking ? t("blockTitle", { email: user?.email ?? "" }) : t("unblockTitle", { email: user?.email ?? "" })}</AlertDialogTitle>
          <AlertDialogDescription>{blocking ? t("blockBody") : t("unblockBody")}</AlertDialogDescription>
        </AlertDialogHeader>
        {blocking && (
          <div className="space-y-1.5">
            <Label htmlFor="block-reason">{t("reason")}</Label>
            <Textarea id="block-reason" rows={2} maxLength={255} value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder={t("reasonPlaceholder")} />
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={submit.isPending}>{t("cancel")}</AlertDialogCancel>
          {/* Not AlertDialogAction: that closes the dialog before the request finishes. */}
          <Button variant={blocking ? "destructive" : "default"} disabled={!user || submit.isPending}
            onClick={() => user && submit.mutate(user)}>
            {submit.isPending && <Loader2 className="size-4 animate-spin" />}
            {blocking ? t("block") : t("unblock")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

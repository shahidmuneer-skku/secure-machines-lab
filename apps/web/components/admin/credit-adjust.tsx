"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArrowRight, Loader2, Minus, Plus } from "lucide-react"
import { useTranslations } from "next-intl"
import { useState } from "react"
import { toast } from "sonner"

import {
  AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { api, data } from "@/lib/api/client"
import { isApiError } from "@/lib/api/errors"
import { qk } from "@/lib/api/keys"

const MAX = 1_000_000
const QUICK = [10, 50, 100, 500]

/**
 * Add or remove credits for one account (including the admin's own). The amount is always
 * positive; the direction is explicit. Removals are confirmed and never take the balance below
 * zero (the server removes at most what is available).
 */
export function CreditAdjust({ user, isSelf }: { user: { id: string; email: string; balance: number }; isSelf: boolean }) {
  const t = useTranslations("admin.credits")
  const qc = useQueryClient()
  const [mode, setMode] = useState<"add" | "remove">("add")
  const [amount, setAmount] = useState("")
  const [reason, setReason] = useState("")
  const [expires, setExpires] = useState("")
  const [confirming, setConfirming] = useState(false)

  const n = Number(amount)
  const valid = Number.isInteger(n) && n > 0 && n <= MAX
  const removable = Math.min(n || 0, user.balance)
  const next = mode === "add" ? user.balance + (valid ? n : 0) : user.balance - (valid ? removable : 0)
  const nothingToRemove = mode === "remove" && user.balance === 0

  const adjust = useMutation({
    mutationFn: async () => data(await api.POST("/api/v1/admin/users/{id}/credits", { params: { path: { id: user.id } }, body: {
      delta: mode === "add" ? n : -n, reason: reason.trim(),
      expires_in_days: mode === "add" && expires ? Number(expires) : null } })),
    onSuccess: async (r) => {
      toast.success(r.applied > 0 ? t("added", { count: r.applied, balance: r.balance })
        : t("removed", { count: -r.applied, balance: r.balance }))
      setAmount("")
      setReason("")
      setExpires("")
      setConfirming(false)
      await Promise.all([qc.invalidateQueries({ queryKey: qk.admin() }),
        // The header balance and the credits page show the admin's own wallet.
        isSelf && qc.invalidateQueries({ queryKey: ["credits"] })])
    },
    onError: (e) => { setConfirming(false); toast.error(isApiError(e) ? e.detail : t("failed")) },
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (mode === "remove") setConfirming(true)
    else adjust.mutate()
  }

  return (
    <form className="grid gap-4" onSubmit={submit}>
      {isSelf && <p className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-xs">{t("selfNote")}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup type="single" value={mode} variant="outline" aria-label={t("direction")}
          onValueChange={(v) => v && setMode(v as "add" | "remove")}>
          <ToggleGroupItem value="add" className="data-[state=on]:border-real/60 data-[state=on]:bg-real/15">
            <Plus className="size-4" /> {t("add")}</ToggleGroupItem>
          <ToggleGroupItem value="remove" className="data-[state=on]:border-fake/60 data-[state=on]:bg-fake/15">
            <Minus className="size-4" /> {t("remove")}</ToggleGroupItem>
        </ToggleGroup>
        <p className="flex items-center gap-2 font-mono text-sm tabular-nums" aria-live="polite">
          <span className="text-muted-foreground">{t("balance")}</span> {user.balance}
          {valid && !nothingToRemove && <><ArrowRight className="size-3.5 text-muted-foreground" aria-label={t("becomes")} />
            <span className={mode === "add" ? "text-real" : "text-fake"}>{next}</span></>}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="credit-amount">{mode === "add" ? t("amountAdd") : t("amountRemove")}</Label>
          <Input id="credit-amount" type="number" inputMode="numeric" min={1} max={MAX} step={1} value={amount}
            onChange={(e) => setAmount(e.target.value)} aria-invalid={amount !== "" && !valid} />
          <div className="flex flex-wrap gap-1">
            {QUICK.map((q) => (
              <Button key={q} type="button" size="xs" variant="ghost" className="font-mono" onClick={() => setAmount(String(q))}>
                {mode === "add" ? "+" : "−"}{q}
              </Button>
            ))}
            {mode === "remove" && user.balance > 0 && (
              <Button type="button" size="xs" variant="ghost" onClick={() => setAmount(String(user.balance))}>{t("all")}</Button>
            )}
          </div>
        </div>
        {mode === "add" ? (
          <div className="space-y-1.5">
            <Label htmlFor="credit-expires">{t("expiresIn")}</Label>
            <Input id="credit-expires" type="number" inputMode="numeric" min={1} value={expires}
              onChange={(e) => setExpires(e.target.value)} placeholder={t("never")} />
            <p className="text-xs text-muted-foreground">{t("expiresHint")}</p>
          </div>
        ) : (
          <p className="self-center text-xs text-muted-foreground">
            {nothingToRemove ? t("nothingToRemove") : valid && n > user.balance ? t("capped", { count: user.balance }) : t("removeHint")}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="credit-reason">{t("reason")}</Label>
        <Input id="credit-reason" maxLength={255} value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder={mode === "add" ? t("reasonAddPlaceholder") : t("reasonRemovePlaceholder")} />
      </div>

      <Button type="submit" size="sm" className="w-fit" variant={mode === "remove" ? "destructive" : "default"}
        disabled={!valid || !reason.trim() || nothingToRemove || adjust.isPending}>
        {adjust.isPending && <Loader2 className="size-4 animate-spin" />}
        {!valid || nothingToRemove ? (mode === "add" ? t("addCredits") : t("confirmRemove"))
          : mode === "add" ? t("submitAdd", { count: n }) : t("submitRemove", { count: removable })}
      </Button>

      <AlertDialog open={confirming} onOpenChange={(v) => { if (!adjust.isPending) setConfirming(v) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("confirmTitle", { count: removable, email: user.email })}</AlertDialogTitle>
            <AlertDialogDescription>{t("confirmBody", { balance: user.balance - removable })}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={adjust.isPending}>{t("cancel")}</AlertDialogCancel>
            <Button variant="destructive" disabled={adjust.isPending} onClick={() => adjust.mutate()}>
              {adjust.isPending && <Loader2 className="size-4 animate-spin" />} {t("confirmRemove")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  )
}

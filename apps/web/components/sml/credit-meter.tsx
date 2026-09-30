"use client"

import { useQuery } from "@tanstack/react-query"
import { Coins } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api, data } from "@/lib/api/client"
import { qk } from "@/lib/api/keys"
import { cn } from "@/lib/utils"

export function useBalance() {
  return useQuery({ queryKey: qk.balance, queryFn: async () => data(await api.GET("/api/v1/credits/balance")) })
}

/** Header credit meter; turns amber when the balance is low. */
export function CreditMeter({ className }: { className?: string }) {
  const t = useTranslations("credits")
  const { data: balance } = useBalance()
  const low = balance?.low_balance
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          href="/app/billing"
          className={cn(
            "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors hover:bg-accent",
            low ? "border-warn/50 text-warn" : "border-border",
            className,
          )}
        >
          <Coins className="size-4" aria-hidden />
          <span className="font-mono tabular-nums">{balance ? (balance.unlimited ? "∞" : balance.balance) : "—"}</span>
          <span className="sr-only md:not-sr-only mono-label text-muted-foreground">{t("credits")}</span>
        </Link>
      </TooltipTrigger>
      <TooltipContent>
        {balance?.held ? t("held", { count: balance.held }) : t("balanceHint", { daily: balance?.daily_free_credits ?? 0 })}
      </TooltipContent>
    </Tooltip>
  )
}

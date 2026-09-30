"use client"

import { ShieldAlert, ShieldCheck } from "lucide-react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { useMe } from "@/hooks/use-me"

/** UI gate for /admin. The API enforces roles + MFA on every admin endpoint regardless. */
export function AdminGate({ children }: { children: ReactNode }) {
  const t = useTranslations("admin")
  const { data: me, isLoading } = useMe()
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!me?.is_staff_user) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon"><ShieldAlert /></EmptyMedia>
          <EmptyTitle>{t("forbiddenTitle")}</EmptyTitle>
          <EmptyDescription>{t("forbiddenBody")}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent><Button asChild><Link href="/app">{t("backToApp")}</Link></Button></EmptyContent>
      </Empty>
    )
  }
  if (me.requires_mfa && !me.has_mfa) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon"><ShieldCheck /></EmptyMedia>
          <EmptyTitle>{t("mfaEnrollTitle")}</EmptyTitle>
          <EmptyDescription>{t("mfaEnrollBody")}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent><Button asChild><Link href="/app/settings?tab=security">{t("mfaEnrollCta")}</Link></Button></EmptyContent>
      </Empty>
    )
  }
  return <>{children}</>
}

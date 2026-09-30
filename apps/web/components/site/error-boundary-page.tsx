"use client"

import { RotateCw } from "lucide-react"
import { useTranslations } from "next-intl"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"

import { HomeLinks, StatusPage } from "./status-page"

/** Shared UI for route-level error.tsx boundaries. Server details never reach the browser, only the digest. */
export function ErrorBoundaryPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const t = useTranslations("pages")
  useEffect(() => {
    console.error(error)
  }, [error])
  return (
    <StatusPage code="500" eyebrow={t("error.eyebrow")} title={t("error.title")} body={t("error.body")}
      reference={error.digest ? t("error.reference", { digest: error.digest }) : undefined}
      actions={<>
        <Button onClick={() => retry()}><RotateCw className="size-4" /> {t("error.retry")}</Button>
        <HomeLinks home={t("home")} dashboard={t("dashboard")} />
      </>} />
  )
}

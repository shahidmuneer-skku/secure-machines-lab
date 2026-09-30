import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { HomeLinks, StatusPage } from "@/components/site/status-page"

export const metadata: Metadata = { title: "404" }

export default async function NotFound() {
  const t = await getTranslations("pages")
  return (
    <StatusPage code="404" eyebrow={t("notFound.eyebrow")} title={t("notFound.title")} body={t("notFound.body")}
      actions={<HomeLinks home={t("home")} dashboard={t("dashboard")} />} />
  )
}

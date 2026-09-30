import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { Suspense } from "react"

import { SettingsPage } from "@/components/settings/settings-page"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("settings"))("title") }
}

export default function Settings() {
  return <Suspense><SettingsPage /></Suspense>
}

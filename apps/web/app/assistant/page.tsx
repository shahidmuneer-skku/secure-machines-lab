import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { Suspense } from "react"

import { AssistantApp } from "@/components/assistant/assistant-app"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("assistant"))("title"), robots: { index: false, follow: false } }
}

/** The assistant has its own window: no dashboard frame (owner, 2026-10-02). */
export default function AssistantPage() {
  return <Suspense><AssistantApp /></Suspense>
}

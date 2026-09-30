import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { Suspense } from "react"

import { ResultsList } from "@/components/results/results-list"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("results"))("title") }
}

export default function ResultsPage() {
  return <Suspense><ResultsList /></Suspense>
}

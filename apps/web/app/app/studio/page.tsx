import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { Studio } from "@/components/studio/studio"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("studio"))("title") }
}

export default function StudioPage() {
  return <Studio />
}

import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { DetectFlow } from "@/components/detect/detect-flow"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("detect"))("title") }
}

export default function DetectPage() {
  return <DetectFlow />
}

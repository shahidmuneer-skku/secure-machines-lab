import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { ApiKeysPage } from "@/components/api-keys/api-keys-page"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("apiKeys"))("title") }
}

export default function ApiKeys() {
  return <ApiKeysPage />
}

import type { Metadata } from "next"
import { getLocale } from "next-intl/server"

import { LegalPage } from "@/components/site/legal-page"
import { PRIVACY } from "@/content/legal"

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getLocale()
  return { title: (locale === "ko" ? PRIVACY.ko : PRIVACY.en).title }
}

export default function Page() {
  return <LegalPage docs={PRIVACY} />
}

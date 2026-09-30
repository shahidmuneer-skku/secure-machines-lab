import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { BillingPage } from "@/components/billing/billing-page"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("billing"))("title") }
}

export default function Billing() {
  return <BillingPage />
}

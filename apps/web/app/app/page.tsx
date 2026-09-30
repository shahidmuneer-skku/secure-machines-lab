import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { Dashboard } from "@/components/dashboard/dashboard"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("dashboard"))("title") }
}

export default function DashboardPage() {
  return <Dashboard />
}

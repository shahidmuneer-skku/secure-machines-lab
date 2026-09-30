import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { LoginForm } from "@/components/auth/login-form"
import { safeNext } from "@/lib/safe-next"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("auth")
  return { title: t("loginTitle") }
}

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams
  const next = safeNext(typeof params.next === "string" ? params.next : null)
  return <LoginForm next={next} />
}

import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { SignupForm } from "@/components/auth/signup-form"
import { safeNext } from "@/lib/safe-next"

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("auth"))("signupTitle") }
}

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const params = await searchParams
  return <SignupForm next={safeNext(typeof params.next === "string" ? params.next : null)} />
}

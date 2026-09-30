import { MfaForm } from "@/components/auth/mfa-form"
import { safeNext } from "@/lib/safe-next"

export default async function MfaPage({ searchParams }: PageProps<"/login/mfa">) {
  const params = await searchParams
  return <MfaForm next={safeNext(typeof params.next === "string" ? params.next : null)} />
}

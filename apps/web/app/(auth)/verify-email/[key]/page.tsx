import { VerifyEmail } from "@/components/auth/verify-email"

export default async function VerifyEmailPage({ params }: PageProps<"/verify-email/[key]">) {
  const { key } = await params
  return <VerifyEmail encodedKey={key} />
}

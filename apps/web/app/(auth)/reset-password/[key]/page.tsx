import { ResetPasswordForm } from "@/components/auth/password-reset"

export default async function ResetPasswordPage({ params }: PageProps<"/reset-password/[key]">) {
  const { key } = await params
  return <ResetPasswordForm encodedKey={key} />
}

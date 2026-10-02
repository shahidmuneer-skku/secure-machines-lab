import { notFound, redirect } from "next/navigation"
import { NextIntlClientProvider } from "next-intl"
import { getMessages } from "next-intl/server"

import { AppShell } from "@/components/app-shell/app-shell"
import { AdminGate } from "@/components/admin/admin-gate"
import { serverMe } from "@/lib/api/server"

export default async function AdminLayout({ children }: LayoutProps<"/admin">) {
  // Checked on the server: the console and its texts (detectors, weights, the metadata vote) are sent
  // to staff only — anyone else gets a 404, not a page the browser merely hides (ADR 0015).
  const me = await serverMe()
  if (!me) redirect("/login?next=%2Fadmin")
  if (!me.is_staff_user) notFound()
  // The admin console's texts are sent only here (the root layout leaves them out: i18n/messages).
  const messages = await getMessages()
  return (
    <NextIntlClientProvider messages={messages}>
      <AppShell area="admin">
        <AdminGate>{children}</AdminGate>
      </AppShell>
    </NextIntlClientProvider>
  )
}

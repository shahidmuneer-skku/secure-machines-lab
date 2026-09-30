import { AppShell } from "@/components/app-shell/app-shell"
import { AdminGate } from "@/components/admin/admin-gate"

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <AppShell area="admin">
      <AdminGate>{children}</AdminGate>
    </AppShell>
  )
}

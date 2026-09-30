import { AppShell } from "@/components/app-shell/app-shell"

export default function AppLayout({ children }: LayoutProps<"/app">) {
  return <AppShell area="app">{children}</AppShell>
}

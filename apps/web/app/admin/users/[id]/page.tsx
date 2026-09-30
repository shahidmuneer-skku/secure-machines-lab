import { AdminUserDetail } from "@/components/admin/user-detail"

export default async function Page({ params }: PageProps<"/admin/users/[id]">) {
  const { id } = await params
  return <AdminUserDetail id={id} />
}

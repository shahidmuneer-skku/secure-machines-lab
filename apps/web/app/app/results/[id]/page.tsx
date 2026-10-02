import { getLocale } from "next-intl/server"

import { JobDetailView } from "@/components/results/job-detail"
import { WithStaffMessages } from "@/components/results/staff-messages"
import { serverMe } from "@/lib/api/server"

export default async function JobPage({ params }: PageProps<"/app/results/[id]">) {
  const { id } = await params
  const me = await serverMe()
  if (!me?.capabilities?.includes("view_all_jobs")) return <JobDetailView id={id} />
  // The detector breakdown's texts name detectors and the metadata vote: they are read here, on the
  // server, and sent to administrators only — never bundled for the browser (ADR 0015).
  const extra = (await import(`@/messages/detectors/${await getLocale()}.json`)).default
  return <WithStaffMessages job={extra.job}><JobDetailView id={id} /></WithStaffMessages>
}

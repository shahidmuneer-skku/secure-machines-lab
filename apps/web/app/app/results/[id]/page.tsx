import { JobDetailView } from "@/components/results/job-detail"

export default async function JobPage({ params }: PageProps<"/app/results/[id]">) {
  const { id } = await params
  return <JobDetailView id={id} />
}

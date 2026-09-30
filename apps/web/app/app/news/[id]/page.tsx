import { NewsCaseView } from "@/components/modules/news"

export default async function NewsCasePage({ params }: PageProps<"/app/news/[id]">) {
  const { id } = await params
  return <NewsCaseView id={id} />
}

import type { Metadata } from "next"

import { DocsPage } from "@/components/site/docs-page"

export const metadata: Metadata = { title: "API documentation" }

export default function Docs() {
  return <DocsPage />
}

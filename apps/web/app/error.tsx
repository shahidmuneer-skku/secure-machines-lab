"use client"

import { ErrorBoundaryPage } from "@/components/site/error-boundary-page"

export default function Error(props: { error: Error & { digest?: string }; retry: () => void }) {
  return <ErrorBoundaryPage {...props} />
}

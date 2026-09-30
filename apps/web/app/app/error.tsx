"use client"

import { ErrorBoundaryPage } from "@/components/site/error-boundary-page"

// Inside the workspace so the sidebar and header stay usable when one page fails.
export default function WorkspaceError(props: { error: Error & { digest?: string }; retry: () => void }) {
  return <ErrorBoundaryPage {...props} />
}

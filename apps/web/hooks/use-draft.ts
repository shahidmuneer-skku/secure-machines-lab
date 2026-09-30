"use client"

import { useCallback, useState } from "react"

/**
 * An editable copy of server data. Until the user edits, `value` is the server value; after that it
 * is the user's draft, so background refetches never overwrite unsaved edits. Call `reset()` after a
 * successful save (ideally once the refetch has landed) to follow the server again.
 */
export function useDraft<T>(server: T | undefined, fallback: T) {
  const [edited, setEdited] = useState<T | null>(null)
  const value = edited ?? server ?? fallback
  const set = useCallback(
    (next: T | ((current: T) => T)) =>
      setEdited((prev) => {
        const current = prev ?? server ?? fallback
        return typeof next === "function" ? (next as (c: T) => T)(current) : next
      }),
    [server, fallback],
  )
  const reset = useCallback(() => setEdited(null), [])
  return { value, set, reset, dirty: edited !== null }
}

"use client"

import { useSyncExternalStore } from "react"

const noopSubscribe = () => () => {}

/** False during SSR and hydration, true afterwards — without a setState-in-effect round trip. */
export function useHydrated(): boolean {
  return useSyncExternalStore(noopSubscribe, () => true, () => false)
}

/** A browser-only value read once on the client (e.g. feature detection); `serverValue` during SSR. */
export function useClientValue<T>(read: () => T, serverValue: T): T {
  return useSyncExternalStore(noopSubscribe, read, () => serverValue)
}

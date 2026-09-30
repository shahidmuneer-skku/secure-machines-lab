"use client"

import { passkeysSupported } from "@/lib/auth/passkey"

import { useClientValue } from "./use-hydrated"

/** WebAuthn support is only knowable in the browser; false during SSR so hydration matches. */
export function usePasskeysSupported(): boolean {
  return useClientValue(passkeysSupported, false)
}

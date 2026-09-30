"use client"

import { useEffect, useState } from "react"

import { passkeysSupported } from "@/lib/auth/passkey"

/** WebAuthn support is only knowable in the browser; resolve it after mount to avoid hydration mismatches. */
export function usePasskeysSupported(): boolean {
  const [supported, setSupported] = useState(false)
  useEffect(() => setSupported(passkeysSupported()), [])
  return supported
}

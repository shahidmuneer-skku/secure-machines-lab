import type { AbstractIntlMessages } from "next-intl"

/**
 * Namespaces only administrators may receive. Their texts describe how the analysis works (detectors,
 * metadata, checks), so pages for everyone else must not ship them to the browser (owner, 2026-10-02):
 * the root layout leaves them out and the admin console's layout adds them back.
 */
export const ADMIN_NAMESPACES = ["admin"] as const

export function withoutAdmin(messages: AbstractIntlMessages): AbstractIntlMessages {
  return Object.fromEntries(Object.entries(messages).filter(([ns]) => !(ADMIN_NAMESPACES as readonly string[]).includes(ns)))
}

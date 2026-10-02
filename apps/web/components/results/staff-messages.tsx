"use client"

import { NextIntlClientProvider, useLocale, useMessages, useTimeZone } from "next-intl"
import type { ReactNode } from "react"

/** Adds staff-only texts (sent by the server to staff only) to the page's messages. */
export function WithStaffMessages({ job, children }: { job: Record<string, unknown>; children: ReactNode }) {
  const locale = useLocale()
  const timeZone = useTimeZone()
  const outer = useMessages()
  const messages = { ...outer, job: { ...(outer.job as Record<string, unknown>), ...job } } as typeof outer
  return <NextIntlClientProvider locale={locale} timeZone={timeZone} messages={messages}>{children}</NextIntlClientProvider>
}

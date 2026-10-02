"use client"

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "next-themes"
import { useState, type ReactNode } from "react"

import { MuiProvider } from "@/components/mui-provider"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { isApiError } from "@/lib/api/errors"
import { DEFAULT_THEME } from "@/lib/theme/palette"

/** Pages that need a session (proxy.ts redirects there too, before the page loads). */
const SIGNED_IN_AREAS = /^\/(app|admin|assistant)(\/|\?|$)/

function makeClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (isApiError(error) && error.status === 401 && typeof window !== "undefined") {
          const here = window.location.pathname + window.location.search
          if (SIGNED_IN_AREAS.test(here)) {
            // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- full reload drops the previous user's cached data
            window.location.assign(`/login?next=${encodeURIComponent(here)}`)
          }
        }
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: true,
        retry: (count, error) => !(isApiError(error) && error.status < 500) && count < 2,
      },
    },
  })
}

export function Providers({ children, nonce }: { children: ReactNode; nonce?: string }) {
  const [client] = useState(makeClient)
  return (
    <QueryClientProvider client={client}>
      {/* Dark by default, whatever the system setting; light when the user chooses it (owner, 2026-10-02). */}
      <ThemeProvider attribute="class" defaultTheme={DEFAULT_THEME} enableSystem={false} nonce={nonce} disableTransitionOnChange>
        <MuiProvider nonce={nonce}>
          <TooltipProvider delayDuration={200}>
            {children}
            <Toaster richColors closeButton position="bottom-right" />
          </TooltipProvider>
        </MuiProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

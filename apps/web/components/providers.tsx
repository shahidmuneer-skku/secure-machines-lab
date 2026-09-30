"use client"

import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "next-themes"
import { useState, type ReactNode } from "react"

import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { isApiError } from "@/lib/api/errors"

function makeClient() {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (isApiError(error) && error.status === 401 && typeof window !== "undefined") {
          const here = window.location.pathname + window.location.search
          if (here.startsWith("/app") || here.startsWith("/admin")) {
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
      <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} nonce={nonce} disableTransitionOnChange>
        <TooltipProvider delayDuration={200}>
          {children}
          <Toaster richColors closeButton position="bottom-right" />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

"use client"

import { AppRouterCacheProvider } from "@mui/material-nextjs/v16-appRouter"
import { ThemeProvider } from "@mui/material/styles"
import type { ReactNode } from "react"

import { muiTheme } from "@/lib/theme/mui-theme"

/**
 * Material UI for the app (Modernize design, owner 2026-10-02), next to the shadcn components.
 *
 * - Styles go into `@layer mui` (declared before Tailwind's utilities in globals.css), so Tailwind
 *   classes can still adjust MUI components.
 * - next-themes owns light/dark: it sets the `dark` class on <html>, which switches MUI's CSS
 *   variables. MUI's own mode storage and class handling are turned off so the two never disagree.
 */
export function MuiProvider({ children, nonce }: { children: ReactNode; nonce?: string }) {
  return (
    <AppRouterCacheProvider options={{ key: "mui", enableCssLayer: true, nonce }}>
      <ThemeProvider theme={muiTheme} defaultMode="light" storageManager={null} colorSchemeNode={null}
        disableTransitionOnChange>
        {children}
      </ThemeProvider>
    </AppRouterCacheProvider>
  )
}

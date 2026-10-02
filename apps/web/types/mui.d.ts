// The MUI theme uses CSS variables (lib/theme/mui-theme.ts): enables `theme.vars` and the CSS-variables
// ThemeProvider props in the types.
import type {} from "@mui/material/themeCssVarsAugmentation"

declare module "@mui/material/styles" {
  interface CssThemeVariables {
    enabled: true
  }
}

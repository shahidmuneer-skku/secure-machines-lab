"use client"

import { createTheme } from "@mui/material/styles"

import { activeFill, cardShadow, dark, fontFamily, light } from "./palette"

/**
 * Material UI theme after the Modernize template (owner, 2026-10-02).
 *
 * CSS variables with the `.dark` class selector: next-themes switches the class on <html>, and MUI's
 * light and dark variables follow it, so MUI and the shadcn components always share one theme. Mode-
 * specific styles use `theme.applyStyles("dark", …)`, never `theme.palette.mode` (MUI does not manage
 * the mode itself; see MuiProvider).
 */
export const muiTheme = createTheme({
  cssVariables: { colorSchemeSelector: "class", cssVarPrefix: "mui" },
  colorSchemes: {
    light: { palette: { ...light, action: { hover: "#F6F9FC", hoverOpacity: 0.02 } } },
    dark: { palette: { ...dark, action: { hover: "rgba(255,255,255,0.04)", hoverOpacity: 0.04 } } },
  },
  shape: { borderRadius: 7 },
  typography: {
    fontFamily,
    h1: { fontWeight: 700, fontSize: "2.25rem", lineHeight: "2.75rem" },
    h2: { fontWeight: 700, fontSize: "1.875rem", lineHeight: "2.25rem" },
    h3: { fontWeight: 600, fontSize: "1.5rem", lineHeight: "1.75rem" },
    h4: { fontWeight: 600, fontSize: "1.3125rem", lineHeight: "1.6rem" },
    h5: { fontWeight: 600, fontSize: "1.125rem", lineHeight: "1.6rem" },
    h6: { fontWeight: 600, fontSize: "1rem", lineHeight: "1.2rem" },
    button: { textTransform: "none", fontWeight: 600 },
    body1: { fontSize: "0.875rem", lineHeight: "1.334rem" },
    body2: { fontSize: "0.75rem", lineHeight: "1rem" },
    subtitle1: { fontSize: "0.875rem", fontWeight: 400 },
    subtitle2: { fontSize: "0.875rem", fontWeight: 400 },
    overline: { fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.04em", lineHeight: "1.5rem" },
  },
  components: {
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: 7,
          boxShadow: cardShadow,
          backgroundImage: "none",
          ...theme.applyStyles("dark", { boxShadow: "none", border: `1px solid ${theme.vars.palette.divider}` }),
        }),
      },
    },
    MuiCardContent: { styleOverrides: { root: { padding: 30, "&:last-child": { paddingBottom: 30 } } } },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 7, boxShadow: "none" } },
      // Solid primary buttons: white on #426DE8 (4.6:1) in both themes.
      variants: [{
        props: { variant: "contained", color: "primary" },
        style: { backgroundColor: activeFill, color: "#FFFFFF", "&:hover": { backgroundColor: light.primary.dark } },
      }],
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600, borderRadius: 6 } } },
    MuiTableCell: {
      styleOverrides: {
        root: ({ theme }) => ({ borderBottom: `1px solid ${theme.vars.palette.divider}` }),
        head: { fontWeight: 600 },
      },
    },
    MuiTooltip: { styleOverrides: { tooltip: { fontSize: "0.75rem" } } },
    MuiListItemButton: { styleOverrides: { root: { borderRadius: 7 } } },
    MuiAppBar: { defaultProps: { elevation: 0, color: "inherit" } },
  },
})

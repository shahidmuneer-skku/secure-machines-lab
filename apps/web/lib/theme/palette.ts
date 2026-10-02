/**
 * Colours of the Modernize design (owner, 2026-10-02), shared by the MUI theme, the shadcn tokens in
 * globals.css and the charts. Dark is the default theme; light is chosen by the user.
 *
 * The brand blue (#5D87FF) is for fills, icons and charts. Text and white-on-colour fills use the
 * darker "ink" shades so they reach WCAG AA contrast (4.5:1); Modernize's teal and coral are too light
 * for text on white.
 */
/** The theme a visitor gets until they choose one (owner, 2026-10-02: dark). */
export const DEFAULT_THEME: "light" | "dark" = "dark"

export const brand = {
  primary: "#5D87FF",
  secondary: "#49BEFF",
  success: "#13DEB9",
  warning: "#FFAE1F",
  error: "#FA896B",
  info: "#539BFF",
} as const

export const light = {
  primary: { main: "#426DE8", light: "#ECF2FF", dark: "#3557C7", contrastText: "#FFFFFF" },
  secondary: { main: "#0B7FBE", light: "#E8F7FF", dark: "#23AFDB", contrastText: "#FFFFFF" },
  success: { main: "#047A65", light: "#E6FFFA", dark: "#02B3A9", contrastText: "#FFFFFF" },
  info: { main: "#1F6FD1", light: "#EBF3FE", dark: "#1682D4", contrastText: "#FFFFFF" },
  error: { main: "#C93F23", light: "#FDEDE8", dark: "#F3704D", contrastText: "#FFFFFF" },
  warning: { main: "#9A6100", light: "#FEF5E5", dark: "#AE8E59", contrastText: "#FFFFFF" },
  grey: { 100: "#F2F6FA", 200: "#EAEFF4", 300: "#DFE5EF", 400: "#7C8FAC", 500: "#5A6A85", 600: "#2A3547" },
  text: { primary: "#2A3547", secondary: "#5A6A85" },
  divider: "#E5EAEF",
  background: { default: "#F5F8FC", paper: "#FFFFFF" },
} as const

export const dark = {
  primary: { main: "#7DA2FF", light: "#253662", dark: "#5D87FF", contrastText: "#0B1530" },
  secondary: { main: "#49BEFF", light: "#1C455D", dark: "#23AFDB", contrastText: "#06222F" },
  success: { main: "#13DEB9", light: "#1B3C48", dark: "#02B3A9", contrastText: "#04231C" },
  info: { main: "#539BFF", light: "#223662", dark: "#1682D4", contrastText: "#0B1530" },
  error: { main: "#FA896B", light: "#4B313D", dark: "#F3704D", contrastText: "#2B0D05" },
  warning: { main: "#FFAE1F", light: "#4D3A2A", dark: "#AE8E59", contrastText: "#2B1C00" },
  grey: { 100: "#333F55", 200: "#465670", 300: "#7C8FAC", 400: "#DFE5EF", 500: "#EAEFF4", 600: "#F2F6FA" },
  text: { primary: "#EAEFF4", secondary: "#9AA9C2" },
  divider: "#333F55",
  background: { default: "#1E2735", paper: "#2A3447" },
} as const

/** The active sidebar item and solid buttons: white text on this blue reaches 4.6:1 in both themes. */
export const activeFill = "#426DE8"

/** Modernize's card shadow (light theme); dark cards use a border instead. */
export const cardShadow = "rgb(145 158 171 / 30%) 0px 0px 2px 0px, rgb(145 158 171 / 12%) 0px 12px 24px -4px"

export const fontFamily = "var(--font-jakarta), var(--font-noto-kr), Helvetica, Arial, sans-serif"

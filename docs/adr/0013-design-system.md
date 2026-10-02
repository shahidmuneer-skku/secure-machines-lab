# 0013 · Material UI (Modernize) with shadcn/ui, light by default

**Context.** The owner asked (2026-10-02) for a more professional homepage — text was hard to read and
the page did not present the products — and for a dashboard after the Modernize Next.js template, with
a light background by default and a dark theme the user can switch on. The owner's decisions: add
Material UI and use its components; a product-focused homepage that keeps the lab's research, team and
contact content; Modernize blue (#5D87FF) as the brand colour.

**Decision.**

- *Libraries.* Material UI v9 with emotion through `@mui/material-nextjs` (App Router cache, its CSS in
  the `mui` cascade layer, CSP nonce), Tabler icons and ApexCharts as in the template. shadcn/ui stays
  for forms and the pages not rebuilt; its tokens in `globals.css` use the same palette, so both
  libraries look alike. Layer order `theme, base, mui, components, utilities` keeps Tailwind utilities
  above MUI's styles.
- *Theme.* `lib/theme/mui-theme.ts` uses CSS variables (`--mui-*`) with class-based colour schemes.
  next-themes owns the `.dark` class (default light, no system preference, remembered per browser) and
  MUI follows it (`storageManager={null}`, `colorSchemeNode={null}`), so there is one switch and no
  flash. Mode-specific styles use `theme.applyStyles("dark", …)`.
- *Contrast.* #5D87FF is used for fills and icons; text and solid buttons use #426DE8 (white on it
  4.6:1); the success, error and warning inks are darker than the template's to meet WCAG AA, and the
  dark theme's secondary text is #9AA9C2.
- *Charts.* Palettes per theme checked for colour-vision deficiencies (`components/mui/chart.tsx`);
  verdict colours are fixed (authentic teal, manipulated coral, other violet); every chart has a
  legend and a table view or labels.
- *Rebuilt with MUI.* App and admin shell, dashboard, homepage, public navigation and footer, auth
  layout. The previous homepage (its own stylesheet, canvas effects, always dark) is removed.
- *Logo.* `components/brand/logo.tsx` draws a placeholder mark (shield with a check) until an official
  logo file exists; replacing it is a one-file change.

**Consequences.** Two component libraries ship to the browser; MUI is used where the template's look
matters (shell, dashboards, marketing pages) and shadcn/ui where forms already work. New dashboard-like
screens should use MUI and `DashboardCard`; shared colours change in `lib/theme/palette.ts` and
`globals.css` together. Supersedes the homepage note in ADR 0002.

*Update (2026-10-02):* the owner chose dark as the default theme (whatever the system setting); light is
the user's choice from the header toggle. `DEFAULT_THEME` in `lib/theme/palette.ts` sets it for
next-themes, MUI and the pre-hydration fallbacks.

*Update (2026-10-02):* the company logo replaces the placeholder. The owner's shield
(`docs/brand/secure-machine-lab.svg`) is drawn exactly in `components/brand/logo.tsx`; its navy follows
`--logo-ink` (white on the dark theme), the teal stays. The owner kept the name "Secure Machines Lab", so
the wordmark is set in the site font with that name (the source file reads "Secure Machine Lab"), and
the interface keeps Modernize blue. The shield is also the favicon and app icon, the email header
(`public/brand/email-logo.png`, with the name as alt text) and the PDF report header.

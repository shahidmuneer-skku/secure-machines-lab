# 0014 · 3D scan homepage, previous design kept as a backup

**Context.** The owner asked (2026-10-02) to replace the homepage with the "3D scan" design prepared in
`~/templates/3d_landing_page`, migrated as is, and to keep the current homepage as a backup to return to.

**Decision.**

- *Hero.* `components/landing/scan/`: a 3D head undergoing a scroll-driven forensic scan (intro → scan →
  inspect → explain → hand-off to the free upload). three.js through React Three Fiber renders on demand;
  one GSAP ScrollTrigger timeline drives the scene and the HTML panels through a shared controller (no
  per-frame React state). Phones and reduced motion get a manual mode driven by step buttons; without
  WebGL, or until the scene loads, a poster image is shown. All words and controls are HTML. Everything
  shown is an illustrative demonstration, never a detection result.
- *Sections.* Credibility band (partners, publications), product suite, workflow, benefits, research
  with linked publications, final call to action, about and contact. Publication titles and venues were
  corrected and linked to their proceedings; benchmark figures without a source are no longer shown
  (`lib/marketing/publications.ts`).
- *Theme.* The hero is always dark; the rest follows the site theme, with the hero's deep navy palette
  in the dark theme (`.sml-landing` tokens in `globals.css`). The company name stays "Secure Machines Lab".
- *Assets.* The head is the Lee Perry-Smith scan from the three.js examples (CC BY 3.0), credited next
  to the scene (`public/models/face/LICENSE.txt`). `/models` is served like `/images` (proxy matcher).
- *Libraries.* three 0.186.1, @react-three/fiber 9.8.1, gsap 3.15.0 (GSAP's no-charge standard licence),
  pinned to the versions the design was built with; the scene is loaded after hydration only.
- *Backup.* The previous homepage is kept unchanged in `components/landing/legacy/` and served at
  `/landing-legacy` (not indexed); the git tag `landing-modernize` marks the commit before the change.
  To switch back, render `LegacyLandingPage` in `app/(marketing)/page.tsx`.

**Consequences.** The homepage ships three.js only to visitors whose browsers can render it, after the
page is interactive. Partner logo paths are used exactly as the manifest lists them (several file names
are NFD, as committed from macOS). Supersedes the homepage part of ADR 0013.

# 0002 · Next.js App Router, shadcn/ui and a generated API contract

**Context.** The owner asked for the latest Next.js, official UI packages used consistently,
and code that is easy to scale and understand.

**Decision.** Next.js 16 (App Router, `proxy.ts`), React 19, Tailwind v4 with shadcn/ui
components (Radix primitives), TanStack Query for server state, react-hook-form + zod for forms,
next-intl for EN/KO/DE. The API client is `openapi-fetch` typed by `openapi-typescript` from the
schema Django publishes (`packages/contracts`); CI fails when the committed contract is stale.

**Consequences.** Backend changes surface as TypeScript errors instead of runtime bugs. Pages
are client components that fetch through the typed client; the browser talks to the API on the
same origin (nginx in production, a Next rewrite in development), so cookies stay first-party
and no CORS is needed. The homepage from the lab's existing site is kept as-is in its own
namespaced stylesheet.

import Link from "next/link"

import { Eyebrow } from "@/components/sml/eyebrow"
import { Button } from "@/components/ui/button"

/** Full-height message used by the 404 and error boundaries. */
export function StatusPage({ code, eyebrow, title, body, reference, actions }: {
  code: string
  eyebrow: string
  title: string
  body: string
  reference?: string
  actions: React.ReactNode
}) {
  return (
    <main className="flex min-h-[70vh] items-center justify-center px-4 py-16">
      <div className="w-full max-w-lg text-center">
        <p aria-hidden className="font-mono text-6xl font-semibold tracking-tight text-primary/80">{code}</p>
        <Eyebrow className="mt-6 justify-center">{eyebrow}</Eyebrow>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{body}</p>
        {reference && <p className="mt-3 font-mono text-xs text-muted-foreground">{reference}</p>}
        <div className="mt-8 flex flex-wrap justify-center gap-2">{actions}</div>
      </div>
    </main>
  )
}

export function HomeLinks({ home, dashboard }: { home: string; dashboard: string }) {
  return (
    <>
      <Button asChild><Link href="/app">{dashboard}</Link></Button>
      <Button asChild variant="outline"><Link href="/">{home}</Link></Button>
    </>
  )
}

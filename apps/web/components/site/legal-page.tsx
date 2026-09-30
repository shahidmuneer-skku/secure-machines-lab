import { getLocale, getTranslations } from "next-intl/server"

import { Eyebrow } from "@/components/sml/eyebrow"
import type { LegalDoc } from "@/content/legal"

/** Renders a legal document in KO or EN (German readers get the English text with a note). */
export async function LegalPage({ docs }: { docs: Record<"en" | "ko", LegalDoc> }) {
  const locale = await getLocale()
  const t = await getTranslations("legal")
  const doc = locale === "ko" ? docs.ko : docs.en
  return (
    <article className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <Eyebrow>{t("eyebrow")}</Eyebrow>
        <h1 className="text-3xl font-semibold tracking-tight">{doc.title}</h1>
        <p className="text-muted-foreground">{doc.intro}</p>
        {locale === "de" && <p className="rounded-md border border-border bg-muted/40 p-3 text-sm">{t("germanNote")}</p>}
        {locale !== "ko" && <p className="text-xs text-muted-foreground">{t("koreanPrevails")}</p>}
      </header>
      {doc.sections.map((s) => (
        <section key={s.heading} className="space-y-2">
          <h2 className="text-lg font-semibold">{s.heading}</h2>
          {s.body.map((p, i) => <p key={i} className="leading-relaxed text-muted-foreground">{p}</p>)}
        </section>
      ))}
    </article>
  )
}

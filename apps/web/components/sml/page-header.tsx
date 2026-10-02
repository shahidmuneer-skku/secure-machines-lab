import { Eyebrow } from "./eyebrow"

/** Page title banner (Modernize's breadcrumb card): section label, title, description and actions. */
export function PageHeader({ eyebrow, title, description, actions }: {
  eyebrow: string
  index?: number
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <header className="relative mb-6 flex flex-col gap-4 overflow-hidden rounded-[7px] bg-primary-soft px-6 py-6 md:flex-row md:items-center md:justify-between md:px-8">
      <div className="relative z-10 space-y-1.5">
        <Eyebrow className="text-primary">{eyebrow}</Eyebrow>
        <h1 className="text-xl font-bold tracking-tight text-foreground md:text-2xl">{title}</h1>
        {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="relative z-10 flex flex-wrap items-center gap-2">{actions}</div>}
      <svg aria-hidden viewBox="0 0 200 120" className="pointer-events-none absolute -right-6 -top-4 hidden h-40 w-64 text-brand opacity-[0.14] md:block">
        <circle cx="150" cy="40" r="70" fill="currentColor" />
        <circle cx="60" cy="110" r="38" fill="currentColor" />
      </svg>
    </header>
  )
}

import { Eyebrow } from "@/components/sml/eyebrow"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function AuthCard({ eyebrow, title, description, children, footer }: {
  eyebrow: string
  title: React.ReactNode
  description?: React.ReactNode
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <Card className="shadow-[0_24px_48px_-16px_rgb(42_53_71/0.18)] dark:shadow-none">
      <CardHeader className="space-y-2 pt-2 text-center">
        <Eyebrow className="justify-center text-primary">{eyebrow}</Eyebrow>
        <CardTitle className="text-2xl font-bold tracking-tight">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-5">
        {children}
        {footer && <div className="border-t border-border/70 pt-4 text-center text-sm text-muted-foreground">{footer}</div>}
      </CardContent>
    </Card>
  )
}

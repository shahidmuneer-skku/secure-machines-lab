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
    <Card className="border-border/80 bg-card/85 shadow-2xl shadow-black/40 backdrop-blur">
      <CardHeader className="space-y-2">
        <Eyebrow>{eyebrow}</Eyebrow>
        <CardTitle className="text-2xl tracking-tight">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-5">
        {children}
        {footer && <div className="border-t border-border/70 pt-4 text-center text-sm text-muted-foreground">{footer}</div>}
      </CardContent>
    </Card>
  )
}

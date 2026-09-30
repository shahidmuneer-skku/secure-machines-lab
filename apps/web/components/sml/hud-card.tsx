import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

/** Card with the homepage's hairline border + subtle accent on hover. */
export function HudCard({ className, interactive, ...props }: React.ComponentProps<typeof Card> & {
  interactive?: boolean
}) {
  return <Card className={cn("border-border/80 bg-card/80 backdrop-blur-sm", interactive && "hud-card-hover",
    className)} {...props} />
}

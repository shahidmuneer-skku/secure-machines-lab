import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

/** A Modernize card: white with a soft shadow (light), bordered (dark); `interactive` lifts on hover. */
export function HudCard({ className, interactive, ...props }: React.ComponentProps<typeof Card> & {
  interactive?: boolean
}) {
  return <Card className={cn(interactive && "hud-card-hover", className)} {...props} />
}

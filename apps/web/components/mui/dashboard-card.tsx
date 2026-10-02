import Card from "@mui/material/Card"
import CardContent from "@mui/material/CardContent"
import Stack from "@mui/material/Stack"
import Typography from "@mui/material/Typography"
import type { ReactNode } from "react"

/** Modernize's DashboardCard: title, optional subtitle and action, content, optional footer. */
export function DashboardCard({ title, subtitle, action, footer, children, sx }: {
  title?: ReactNode
  subtitle?: ReactNode
  action?: ReactNode
  footer?: ReactNode
  children?: ReactNode
  sx?: object
}) {
  return (
    <Card sx={{ height: "100%", display: "flex", flexDirection: "column", ...sx }}>
      <CardContent sx={{ p: { xs: 2.5, md: 3.75 }, flexGrow: 1, "&:last-child": { pb: footer ? 0 : { xs: 2.5, md: 3.75 } } }}>
        {(title || action) && (
          <Stack direction="row" spacing={2} sx={{ justifyContent: "space-between", alignItems: "flex-start", mb: 3 }}>
            <div>
              {title && <Typography variant="h5" component="h2">{title}</Typography>}
              {subtitle && <Typography variant="subtitle2" sx={{ color: "text.secondary", mt: 0.5 }}>{subtitle}</Typography>}
            </div>
            {action}
          </Stack>
        )}
        {children}
      </CardContent>
      {footer}
    </Card>
  )
}

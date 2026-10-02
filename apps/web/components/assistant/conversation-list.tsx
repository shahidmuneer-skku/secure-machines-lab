"use client"

import Box from "@mui/material/Box"
import Button from "@mui/material/Button"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import IconButton from "@mui/material/IconButton"
import List from "@mui/material/List"
import ListItemButton from "@mui/material/ListItemButton"
import ListItemText from "@mui/material/ListItemText"
import Menu from "@mui/material/Menu"
import MenuItem from "@mui/material/MenuItem"
import Skeleton from "@mui/material/Skeleton"
import TextField from "@mui/material/TextField"
import Typography from "@mui/material/Typography"
import { IconDots, IconLayoutDashboard, IconPencil, IconPlus, IconTrash } from "@tabler/icons-react"
import { useLocale, useTranslations } from "next-intl"
import { useState } from "react"

import { Logo } from "@/components/brand/logo"
import { useConversationActions, useConversations } from "@/hooks/use-assistant"
import { formatRelative } from "@/lib/format"
import type { Conversation } from "@/lib/assistant"

export function ConversationList({ active, onSelect, onNew, onDeleted }: {
  active: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDeleted: (id: string) => void
}) {
  const t = useTranslations("assistant")
  const locale = useLocale()
  const { data, isLoading } = useConversations()
  const { rename, remove } = useConversationActions()
  const [menu, setMenu] = useState<{ anchor: HTMLElement; conv: Conversation } | null>(null)
  const [renaming, setRenaming] = useState<{ conv: Conversation; title: string } | null>(null)
  const [deleting, setDeleting] = useState<Conversation | null>(null)

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ px: 2.5, pt: 2.25, pb: 1.5 }}><Logo href="/assistant" tag={t("title")} /></Box>
      <Box sx={{ px: 2, pb: 1 }}>
        <Button fullWidth variant="contained" startIcon={<IconPlus size={18} />} onClick={onNew}
          sx={{ justifyContent: "flex-start", py: 1.1 }}>{t("newChat")}</Button>
      </Box>
      <Typography component="h2" sx={{ px: 3, pt: 1.5, pb: 0.5, fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.04em",
        textTransform: "uppercase", color: "text.secondary" }}>{t("chats")}</Typography>
      <Box component="nav" aria-label={t("conversations")} sx={{ flex: 1, overflowY: "auto", px: 1.5 }}>
        {isLoading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={44} sx={{ my: 0.75, mx: 0.5 }} />)
        ) : !data?.length ? (
          <Typography variant="body2" sx={{ color: "text.secondary", px: 1.5, py: 1 }}>{t("noChats")}</Typography>
        ) : (
          <List disablePadding>
            {data.map((c) => (
              <ListItemButton key={c.id} selected={c.id === active} onClick={() => onSelect(c.id)}
                aria-current={c.id === active ? "page" : undefined}
                sx={{ borderRadius: "10px", mb: 0.25, pr: 0.5, "&.Mui-selected": { bgcolor: "primary.light" },
                  "&:hover .conv-menu, &.Mui-selected .conv-menu, &:focus-within .conv-menu": { opacity: 1 } }}>
                <ListItemText primary={c.title || t("untitled")} secondary={formatRelative(c.updated_at, locale)}
                  slotProps={{ primary: { noWrap: true, sx: { fontSize: "0.9rem", fontWeight: c.id === active ? 600 : 500 } },
                    secondary: { sx: { fontSize: "0.75rem" } } }} />
                <IconButton className="conv-menu" size="small" aria-label={`${t("menu")}: ${c.title || t("untitled")}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    setMenu({ anchor: e.currentTarget, conv: c })
                  }}
                  sx={{ opacity: { xs: 1, md: 0 }, transition: "opacity .15s" }}><IconDots size={17} /></IconButton>
              </ListItemButton>
            ))}
          </List>
        )}
      </Box>
      <Box sx={{ p: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
        <Button fullWidth component="a" href="/app" startIcon={<IconLayoutDashboard size={18} />}
          sx={{ justifyContent: "flex-start", color: "text.secondary" }}>{t("back")}</Button>
      </Box>

      <Menu anchorEl={menu?.anchor} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem onClick={() => {
          if (menu) setRenaming({ conv: menu.conv, title: menu.conv.title })
          setMenu(null)
        }}><IconPencil size={17} style={{ marginRight: 10 }} />{t("rename")}</MenuItem>
        <MenuItem onClick={() => {
          if (menu) setDeleting(menu.conv)
          setMenu(null)
        }} sx={{ color: "error.main" }}><IconTrash size={17} style={{ marginRight: 10 }} />{t("delete")}</MenuItem>
      </Menu>

      <Dialog open={!!renaming} onClose={() => setRenaming(null)} fullWidth maxWidth="xs">
        <form onSubmit={(e) => {
          e.preventDefault()
          if (renaming) rename.mutate({ id: renaming.conv.id, title: renaming.title.trim().slice(0, 120) })
          setRenaming(null)
        }}>
          <DialogTitle>{t("rename")}</DialogTitle>
          <DialogContent>
            <TextField autoFocus fullWidth value={renaming?.title ?? ""} slotProps={{ htmlInput: { maxLength: 120 } }}
              onChange={(e) => setRenaming((r) => (r ? { ...r, title: e.target.value } : r))} aria-label={t("rename")} sx={{ mt: 1 }} />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRenaming(null)}>{t("cancel")}</Button>
            <Button type="submit" variant="contained">{t("save")}</Button>
          </DialogActions>
        </form>
      </Dialog>

      <Dialog open={!!deleting} onClose={() => setDeleting(null)} maxWidth="xs">
        <DialogTitle>{t("delete")}</DialogTitle>
        <DialogContent><Typography>{t("deleteConfirm")}</Typography></DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleting(null)}>{t("cancel")}</Button>
          <Button color="error" variant="contained" onClick={() => {
            if (deleting) remove.mutate(deleting.id, { onSuccess: () => onDeleted(deleting.id) })
            setDeleting(null)
          }}>{t("delete")}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

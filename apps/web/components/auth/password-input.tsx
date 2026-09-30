"use client"

import { Eye, EyeOff } from "lucide-react"
import { useTranslations } from "next-intl"
import { forwardRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export const PasswordInput = forwardRef<HTMLInputElement, React.ComponentProps<typeof Input>>(
  function PasswordInput(props, ref) {
    const [show, setShow] = useState(false)
    const t = useTranslations("auth")
    return (
      <div className="relative">
        <Input ref={ref} type={show ? "text" : "password"} className="pr-10" {...props} />
        <Button type="button" variant="ghost" size="icon" className="absolute right-0.5 top-1/2 size-8 -translate-y-1/2"
          onClick={() => setShow((s) => !s)} aria-label={show ? t("hidePassword") : t("showPassword")}>
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Button>
      </div>
    )
  },
)

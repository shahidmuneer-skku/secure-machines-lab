"use client"

import { useId, type ReactNode } from "react"
import { Controller, type Control, type ControllerRenderProps, type FieldPath, type FieldValues } from "react-hook-form"

import { Field, FieldContent, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"

/**
 * react-hook-form Controller + shadcn Field (the current shadcn form pattern).
 * Wires label ↔ control ids and aria-invalid/aria-describedby for accessibility.
 */
export function ControlledField<T extends FieldValues, N extends FieldPath<T>>({
  control, name, label, description, orientation = "vertical", children,
}: {
  control: Control<T>
  name: N
  label?: ReactNode
  description?: ReactNode
  orientation?: "vertical" | "horizontal"
  children: (
    field: ControllerRenderProps<T, N> & { id: string; "aria-invalid": boolean; "aria-describedby"?: string },
  ) => ReactNode
}) {
  const id = useId()
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => {
        const describedBy = [description ? `${id}-desc` : null, fieldState.error ? `${id}-err` : null]
          .filter(Boolean).join(" ") || undefined
        const control = children({ ...field, id, "aria-invalid": fieldState.invalid, "aria-describedby": describedBy })
        return (
          <Field orientation={orientation} data-invalid={fieldState.invalid}>
            {orientation === "horizontal" ? (
              <>
                {control}
                <FieldContent>
                  {label && <FieldLabel htmlFor={id} className="font-normal">{label}</FieldLabel>}
                  {description && <FieldDescription id={`${id}-desc`}>{description}</FieldDescription>}
                  {fieldState.error && <FieldError id={`${id}-err`} errors={[fieldState.error]} />}
                </FieldContent>
              </>
            ) : (
              <>
                {label && <FieldLabel htmlFor={id}>{label}</FieldLabel>}
                {control}
                {description && <FieldDescription id={`${id}-desc`}>{description}</FieldDescription>}
                {fieldState.error && <FieldError id={`${id}-err`} errors={[fieldState.error]} />}
              </>
            )}
          </Field>
        )
      }}
    />
  )
}

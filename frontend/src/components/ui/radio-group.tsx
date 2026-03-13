/**
 * RadioGroup - Radio Button Component
 * 
 * Single-select radio buttons for forms.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

/* ============================================
   RADIO GROUP CONTEXT
   ============================================ */

interface RadioGroupContextValue {
  value: string
  onValueChange: (value: string) => void
  name: string
  disabled?: boolean
}

const RadioGroupContext = React.createContext<RadioGroupContextValue | undefined>(undefined)

function useRadioGroupContext() {
  const context = React.useContext(RadioGroupContext)
  if (!context) {
    throw new Error("RadioGroupItem must be used within a RadioGroup")
  }
  return context
}

/* ============================================
   RADIO GROUP ROOT
   ============================================ */

interface RadioGroupProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
  name?: string
  disabled?: boolean
  orientation?: "vertical" | "horizontal"
}

const RadioGroup = React.forwardRef<HTMLDivElement, RadioGroupProps>(
  (
    {
      className,
      value: controlledValue,
      defaultValue = "",
      onValueChange,
      name,
      disabled,
      orientation = "vertical",
      children,
      ...props
    },
    ref
  ) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue)
    const generatedName = React.useId()

    const isControlled = controlledValue !== undefined
    const value = isControlled ? controlledValue : internalValue

    const handleValueChange = (newValue: string) => {
      if (!isControlled) {
        setInternalValue(newValue)
      }
      onValueChange?.(newValue)
    }

    return (
      <RadioGroupContext.Provider
        value={{
          value,
          onValueChange: handleValueChange,
          name: name || generatedName,
          disabled,
        }}
      >
        <div
          ref={ref}
          role="radiogroup"
          className={cn(
            "flex",
            orientation === "vertical" ? "flex-col gap-3" : "flex-row gap-4 flex-wrap",
            className
          )}
          {...props}
        >
          {children}
        </div>
      </RadioGroupContext.Provider>
    )
  }
)
RadioGroup.displayName = "RadioGroup"

/* ============================================
   RADIO GROUP ITEM
   ============================================ */

interface RadioGroupItemProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type" | "onChange"> {
  value: string
  label?: string
  description?: string
}

const RadioGroupItem = React.forwardRef<HTMLInputElement, RadioGroupItemProps>(
  ({ className, value, label, description, id, disabled: itemDisabled, ...props }, ref) => {
    const { value: groupValue, onValueChange, name, disabled: groupDisabled } = useRadioGroupContext()
    const generatedId = React.useId()
    const inputId = id || generatedId
    const isChecked = groupValue === value
    const disabled = itemDisabled || groupDisabled

    return (
      <div className={cn("flex items-center gap-2.5", className)}>
        <div className="relative flex items-center justify-center shrink-0">
          <input
            ref={ref}
            type="radio"
            id={inputId}
            name={name}
            value={value}
            checked={isChecked}
            disabled={disabled}
            onChange={() => onValueChange(value)}
            className="peer sr-only"
            {...props}
          />
          <div
            className={cn(
              "w-[18px] h-[18px] rounded-full border-2 transition-all duration-150",
              "flex items-center justify-center cursor-pointer",
              // Unchecked
              "border-gray-300 bg-white",
              "dark:border-dark-border dark:bg-dark-surface",
              // Hover
              "peer-hover:border-gray-400 dark:peer-hover:border-dark-border",
              // Checked
              "peer-checked:border-eliza-red",
              "dark:peer-checked:border-eliza-red",
              // Focus
              "peer-focus-visible:ring-2 peer-focus-visible:ring-eliza-red peer-focus-visible:ring-offset-2",
              "dark:peer-focus-visible:ring-offset-dark-bg",
              // Disabled
              "peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"
            )}
            onClick={() => !disabled && onValueChange(value)}
          >
            {isChecked && (
              <div className="w-2 h-2 rounded-full bg-eliza-red" />
            )}
          </div>
        </div>
        {(label || description) && (
          <div className="flex-1">
            {label && (
              <label
                htmlFor={inputId}
                className={cn(
                  "text-sm font-medium cursor-pointer leading-none",
                  "text-charcoal dark:text-gray-200",
                  disabled && "opacity-50 cursor-not-allowed"
                )}
              >
                {label}
              </label>
            )}
            {description && (
              <p
                className={cn(
                  "text-sm text-gray-500 dark:text-gray-400 mt-1",
                  disabled && "opacity-50"
                )}
              >
                {description}
              </p>
            )}
          </div>
        )}
      </div>
    )
  }
)
RadioGroupItem.displayName = "RadioGroupItem"

/* ============================================
   RADIO CARD (Alternative styled version)
   ============================================ */

interface RadioCardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onChange"> {
  value: string
  disabled?: boolean
}

const RadioCard = React.forwardRef<HTMLDivElement, RadioCardProps>(
  ({ className, value, disabled: itemDisabled, children, ...props }, ref) => {
    const { value: groupValue, onValueChange, name, disabled: groupDisabled } = useRadioGroupContext()
    const isChecked = groupValue === value
    const disabled = itemDisabled || groupDisabled

    return (
      <div
        ref={ref}
        role="radio"
        aria-checked={isChecked}
        onClick={() => !disabled && onValueChange(value)}
        className={cn(
          "relative p-4 rounded-xl border-2 cursor-pointer transition-all",
          // Unchecked
          "border-gray-200 bg-white",
          "dark:border-dark-border/50 dark:bg-dark-surface",
          // Hover
          !disabled && "hover:border-gray-300 dark:hover:border-dark-border",
          // Checked
          isChecked && "border-eliza-red bg-eliza-red/5 dark:border-eliza-red dark:bg-eliza-red/10",
          // Disabled
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
        {...props}
      >
        <input
          type="radio"
          name={name}
          value={value}
          checked={isChecked}
          disabled={disabled}
          onChange={() => onValueChange(value)}
          className="sr-only"
        />
        {children}
        {isChecked && (
          <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-eliza-red flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-white" />
          </div>
        )}
      </div>
    )
  }
)
RadioCard.displayName = "RadioCard"

export { RadioGroup, RadioGroupItem, RadioCard }
export type { RadioGroupProps, RadioGroupItemProps, RadioCardProps }

/**
 * Checkbox - Form Checkbox Component
 * 
 * A checkbox input for multi-select forms.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { CheckIcon, MinusIcon } from "@heroicons/react/24/solid"
import { cn } from "../../shared/lib/cn"

interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  /** Indeterminate state (partially checked) */
  indeterminate?: boolean
  /** Label text */
  label?: string
  /** Description text below label */
  description?: string
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, indeterminate, label, description, id, disabled, defaultChecked, checked, onChange, ...props }, ref) => {
    const internalRef = React.useRef<HTMLInputElement>(null)
    const generatedId = React.useId()
    const inputId = id || generatedId
    
    // Track checked state for uncontrolled component
    const [internalChecked, setInternalChecked] = React.useState(defaultChecked ?? false)
    const isControlled = checked !== undefined
    const isChecked = isControlled ? checked : internalChecked

    // Combine refs
    const setRefs = React.useCallback(
      (node: HTMLInputElement | null) => {
        // Update internal ref
        (internalRef as React.MutableRefObject<HTMLInputElement | null>).current = node
        // Forward ref
        if (typeof ref === "function") ref(node)
        else if (ref) (ref as React.MutableRefObject<HTMLInputElement | null>).current = node
      },
      [ref]
    )

    React.useEffect(() => {
      if (internalRef.current) {
        internalRef.current.indeterminate = indeterminate ?? false
      }
    }, [indeterminate])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!isControlled) {
        setInternalChecked(e.target.checked)
      }
      onChange?.(e)
    }

    return (
      <div className={cn("flex items-center gap-2.5", className)}>
        <div className="relative flex items-center justify-center shrink-0">
          <input
            ref={setRefs}
            type="checkbox"
            id={inputId}
            disabled={disabled}
            checked={isControlled ? checked : undefined}
            defaultChecked={!isControlled ? defaultChecked : undefined}
            onChange={handleChange}
            className="peer sr-only"
            {...props}
          />
          <div
            className={cn(
              "w-[18px] h-[18px] rounded border-2 transition-all duration-150 flex items-center justify-center",
              "cursor-pointer",
              // Unchecked
              "border-gray-300 bg-white",
              "dark:border-dark-border dark:bg-dark-surface",
              // Hover
              "peer-hover:border-gray-400 dark:peer-hover:border-dark-border",
              // Checked
              "peer-checked:bg-eliza-red peer-checked:border-eliza-red",
              "dark:peer-checked:bg-eliza-red dark:peer-checked:border-eliza-red",
              // Focus
              "peer-focus-visible:ring-2 peer-focus-visible:ring-eliza-red peer-focus-visible:ring-offset-2",
              "dark:peer-focus-visible:ring-offset-dark-bg",
              // Disabled
              "peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"
            )}
            onClick={() => internalRef.current?.click()}
          >
            {(isChecked || indeterminate) && (
              indeterminate ? (
                <MinusIcon className="w-3 h-3 text-white" />
              ) : (
                <CheckIcon className="w-3 h-3 text-white" />
              )
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
Checkbox.displayName = "Checkbox"

export { Checkbox }
export type { CheckboxProps }

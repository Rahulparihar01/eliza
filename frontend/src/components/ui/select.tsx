/**
 * Select - Dropdown Select Component
 * 
 * A form select/dropdown for choosing from options.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { ChevronDownIcon, CheckIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   SELECT CONTEXT
   ============================================ */

interface SelectContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  value: string
  onValueChange: (value: string) => void
  displayValue: string
  setDisplayValue: (value: string) => void
}

const SelectContext = React.createContext<SelectContextValue | undefined>(undefined)

function useSelectContext() {
  const context = React.useContext(SelectContext)
  if (!context) {
    throw new Error("Select components must be used within a Select provider")
  }
  return context
}

/* ============================================
   SELECT ROOT
   ============================================ */

interface SelectProps {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
  placeholder?: string
  disabled?: boolean
  children: React.ReactNode
  className?: string
  /** Optional leading icon rendered inside the trigger */
  icon?: React.ReactNode
}

const Select: React.FC<SelectProps> = ({
  value: controlledValue,
  defaultValue = "",
  onValueChange,
  placeholder = "Select an option",
  disabled,
  children,
  className,
  icon,
}) => {
  const [open, setOpen] = React.useState(false)
  const [internalValue, setInternalValue] = React.useState(defaultValue)
  const [displayValue, setDisplayValue] = React.useState("")
  const containerRef = React.useRef<HTMLDivElement>(null)

  const isControlled = controlledValue !== undefined
  const value = isControlled ? controlledValue : internalValue

  const handleValueChange = (newValue: string) => {
    if (!isControlled) {
      setInternalValue(newValue)
    }
    onValueChange?.(newValue)
    setOpen(false)
  }

  // Close on outside click
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Close on escape
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [])

  return (
    <SelectContext.Provider
      value={{ open, setOpen, value, onValueChange: handleValueChange, displayValue, setDisplayValue }}
    >
      <div ref={containerRef} className={cn("relative", className)}>
        <button
          type="button"
          onClick={() => !disabled && setOpen(!open)}
          disabled={disabled}
          className={cn(
            "flex items-center gap-2 w-full px-3 py-2 text-sm rounded-xl border",
            "bg-white border-gray-200 text-left",
            "dark:bg-dark-surface dark:border-dark-border/50",
            "focus:outline-none focus:ring-2 focus:ring-eliza-red focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            open && "ring-2 ring-eliza-red border-transparent"
          )}
        >
          {icon && (
            <span className="shrink-0 text-gray-400 dark:text-gray-500 [&_svg]:w-4 [&_svg]:h-4">
              {icon}
            </span>
          )}
          <span className={cn(
            "flex-1 truncate",
            value ? "text-charcoal dark:text-gray-100" : "text-gray-400 dark:text-gray-500"
          )}>
            {displayValue || placeholder}
          </span>
          <ChevronDownIcon
            className={cn(
              "w-4 h-4 shrink-0 text-gray-400 transition-transform",
              open && "rotate-180"
            )}
          />
        </button>
        {/* Always render children so SelectOption effects fire on mount
            to initialize displayValue. Hide visually when closed. */}
        <div
          className={cn(
            "absolute z-50 w-full mt-1 py-1 rounded-xl border shadow-lg",
            "bg-white border-gray-200",
            "dark:bg-dark-surface dark:border-dark-border/50",
            "max-h-60 overflow-auto",
            !open && "hidden"
          )}
        >
          {children}
        </div>
      </div>
    </SelectContext.Provider>
  )
}

/* ============================================
   SELECT OPTION
   ============================================ */

interface SelectOptionProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  disabled?: boolean
}

const SelectOption = React.forwardRef<HTMLDivElement, SelectOptionProps>(
  ({ className, value, disabled, children, ...props }, ref) => {
    const { value: selectedValue, onValueChange, setDisplayValue } = useSelectContext()
    const isSelected = selectedValue === value

    // Helper to extract text content from children (handles strings, arrays, and React nodes)
    const getTextContent = (node: React.ReactNode): string => {
      if (typeof node === "string" || typeof node === "number") {
        return String(node)
      }
      if (Array.isArray(node)) {
        return node.map(getTextContent).join("")
      }
      if (React.isValidElement(node) && node.props.children) {
        return getTextContent(node.props.children)
      }
      return ""
    }

    const textContent = getTextContent(children)

    // Update display value when this option is already selected on mount
    React.useEffect(() => {
      if (isSelected && textContent) {
        setDisplayValue(textContent)
      }
    }, [isSelected, textContent, setDisplayValue])

    const handleClick = () => {
      if (disabled) return
      // Set display value synchronously before the dropdown closes
      if (textContent) {
        setDisplayValue(textContent)
      }
      onValueChange(value)
    }

    return (
      <div
        ref={ref}
        role="option"
        aria-selected={isSelected}
        onClick={handleClick}
        className={cn(
          "flex items-center justify-between px-3 py-2 text-sm cursor-pointer",
          "text-charcoal dark:text-gray-200",
          !disabled && "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
          isSelected && "bg-eliza-red/5 text-eliza-red dark:bg-eliza-red/10 dark:text-white",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
        {...props}
      >
        <span>{children}</span>
        {isSelected && <CheckIcon className="w-4 h-4" />}
      </div>
    )
  }
)
SelectOption.displayName = "SelectOption"

/* ============================================
   SELECT GROUP
   ============================================ */

interface SelectGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
}

const SelectGroup = React.forwardRef<HTMLDivElement, SelectGroupProps>(
  ({ className, label, children, ...props }, ref) => (
    <div ref={ref} className={className} {...props}>
      <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        {label}
      </div>
      {children}
    </div>
  )
)
SelectGroup.displayName = "SelectGroup"

export { Select, SelectOption, SelectGroup }
export type { SelectProps, SelectOptionProps, SelectGroupProps }

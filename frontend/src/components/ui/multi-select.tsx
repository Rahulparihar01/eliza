/**
 * MultiSelect - Multi-Select Dropdown Component
 * 
 * A dropdown that allows selecting multiple options.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { ChevronDownIcon, CheckIcon, XMarkIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   MULTI-SELECT CONTEXT
   ============================================ */

interface MultiSelectContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  values: string[]
  onValuesChange: (values: string[]) => void
  displayValues: Map<string, string>
  setDisplayValue: (value: string, label: string) => void
}

const MultiSelectContext = React.createContext<MultiSelectContextValue | undefined>(undefined)

function useMultiSelectContext() {
  const context = React.useContext(MultiSelectContext)
  if (!context) {
    throw new Error("MultiSelect components must be used within a MultiSelect provider")
  }
  return context
}

/* ============================================
   MULTI-SELECT ROOT
   ============================================ */

interface MultiSelectProps {
  values?: string[]
  defaultValues?: string[]
  onValuesChange?: (values: string[]) => void
  placeholder?: string
  disabled?: boolean
  children: React.ReactNode
  className?: string
  /** Maximum items to show before collapsing to "+N more" */
  maxDisplayItems?: number
}

const MultiSelect: React.FC<MultiSelectProps> = ({
  values: controlledValues,
  defaultValues = [],
  onValuesChange,
  placeholder = "Select options",
  disabled,
  children,
  className,
  maxDisplayItems = 3,
}) => {
  const [open, setOpen] = React.useState(false)
  const [internalValues, setInternalValues] = React.useState<string[]>(defaultValues)
  const [displayValues, setDisplayValues] = React.useState<Map<string, string>>(new Map())
  const containerRef = React.useRef<HTMLDivElement>(null)

  const isControlled = controlledValues !== undefined
  const values = isControlled ? controlledValues : internalValues

  const handleValuesChange = (newValues: string[]) => {
    if (!isControlled) {
      setInternalValues(newValues)
    }
    onValuesChange?.(newValues)
  }

  const setDisplayValue = (value: string, label: string) => {
    setDisplayValues(prev => new Map(prev).set(value, label))
  }

  const removeValue = (valueToRemove: string, e: React.MouseEvent) => {
    e.stopPropagation()
    handleValuesChange(values.filter(v => v !== valueToRemove))
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

  const displayedValues = values.slice(0, maxDisplayItems)
  const remainingCount = values.length - maxDisplayItems

  return (
    <MultiSelectContext.Provider
      value={{ open, setOpen, values, onValuesChange: handleValuesChange, displayValues, setDisplayValue }}
    >
      <div ref={containerRef} className={cn("relative", className)}>
        <button
          type="button"
          onClick={() => !disabled && setOpen(!open)}
          disabled={disabled}
          className={cn(
            "flex items-center justify-between w-full min-h-[42px] px-3 py-2 text-sm rounded-xl border",
            "bg-white border-gray-200 text-left",
            "dark:bg-dark-surface dark:border-dark-border/50",
            "focus:outline-none focus:ring-2 focus:ring-eliza-red focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            open && "ring-2 ring-eliza-red border-transparent"
          )}
        >
          <div className="flex-1 flex flex-wrap gap-1.5">
            {values.length === 0 ? (
              <span className="text-gray-400 dark:text-gray-500">{placeholder}</span>
            ) : (
              <>
                {displayedValues.map(value => (
                  <span
                    key={value}
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium",
                      "bg-eliza-red/10 text-eliza-red border border-eliza-red/20",
                      "dark:bg-eliza-red/20 dark:text-white dark:border-eliza-red/30"
                    )}
                  >
                    {displayValues.get(value) || value}
                    <button
                      type="button"
                      onClick={(e) => removeValue(value, e)}
                      className="hover:bg-eliza-red/20 rounded p-0.5 dark:hover:bg-eliza-red/30"
                    >
                      <XMarkIcon className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                {remainingCount > 0 && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-600 dark:bg-dark-surface-2 dark:text-gray-400">
                    +{remainingCount} more
                  </span>
                )}
              </>
            )}
          </div>
          <ChevronDownIcon
            className={cn(
              "w-4 h-4 text-gray-400 transition-transform ml-2 flex-shrink-0",
              open && "rotate-180"
            )}
          />
        </button>
        {open && (
          <div
            className={cn(
              "absolute z-50 w-full mt-1 py-1 rounded-xl border shadow-lg",
              "bg-white border-gray-200",
              "dark:bg-dark-surface dark:border-dark-border/50",
              "max-h-60 overflow-auto"
            )}
          >
            {children}
          </div>
        )}
      </div>
    </MultiSelectContext.Provider>
  )
}

/* ============================================
   MULTI-SELECT OPTION
   ============================================ */

interface MultiSelectOptionProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  disabled?: boolean
}

const MultiSelectOption = React.forwardRef<HTMLDivElement, MultiSelectOptionProps>(
  ({ className, value, disabled, children, ...props }, ref) => {
    const { values, onValuesChange, setDisplayValue } = useMultiSelectContext()
    const isSelected = values.includes(value)

    // Update display value when this option is rendered
    React.useEffect(() => {
      if (typeof children === "string") {
        setDisplayValue(value, children)
      }
    }, [value, children, setDisplayValue])

    const toggleValue = () => {
      if (disabled) return
      if (isSelected) {
        onValuesChange(values.filter(v => v !== value))
      } else {
        onValuesChange([...values, value])
      }
    }

    return (
      <div
        ref={ref}
        role="option"
        aria-selected={isSelected}
        onClick={toggleValue}
        className={cn(
          "flex items-center gap-3 px-3 py-2 text-sm cursor-pointer",
          "text-charcoal dark:text-gray-200",
          !disabled && "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
          isSelected && "bg-eliza-red/5 dark:bg-eliza-red/10",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
        {...props}
      >
        <div
          className={cn(
            "w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0",
            isSelected
              ? "bg-eliza-red border-eliza-red"
              : "border-gray-300 dark:border-dark-border"
          )}
        >
          {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
        </div>
        <span className="flex-1">{children}</span>
      </div>
    )
  }
)
MultiSelectOption.displayName = "MultiSelectOption"

/* ============================================
   MULTI-SELECT GROUP
   ============================================ */

interface MultiSelectGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
}

const MultiSelectGroup = React.forwardRef<HTMLDivElement, MultiSelectGroupProps>(
  ({ className, label, children, ...props }, ref) => (
    <div ref={ref} className={className} {...props}>
      <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        {label}
      </div>
      {children}
    </div>
  )
)
MultiSelectGroup.displayName = "MultiSelectGroup"

/* ============================================
   MULTI-SELECT ACTIONS (Select All / Clear)
   ============================================ */

interface MultiSelectActionsProps {
  allValues: string[]
}

const MultiSelectActions: React.FC<MultiSelectActionsProps> = ({ allValues }) => {
  const { values, onValuesChange } = useMultiSelectContext()
  const allSelected = allValues.every(v => values.includes(v))

  const selectAll = () => {
    const newValues = Array.from(new Set([...values, ...allValues]))
    onValuesChange(newValues)
  }

  const clearAll = () => {
    onValuesChange(values.filter(v => !allValues.includes(v)))
  }

  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-dark-border/30">
      <button
        type="button"
        onClick={selectAll}
        disabled={allSelected}
        className={cn(
          "text-xs font-medium text-eliza-red hover:text-eliza-red-light",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
      >
        Select all
      </button>
      <button
        type="button"
        onClick={clearAll}
        disabled={values.length === 0}
        className={cn(
          "text-xs font-medium text-gray-500 hover:text-gray-700",
          "dark:text-gray-400 dark:hover:text-gray-200",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
      >
        Clear
      </button>
    </div>
  )
}

export { MultiSelect, MultiSelectOption, MultiSelectGroup, MultiSelectActions }
export type { MultiSelectProps, MultiSelectOptionProps, MultiSelectGroupProps }

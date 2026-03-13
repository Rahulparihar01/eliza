/**
 * Accordion - Collapsible Section Component
 * 
 * Expandable/collapsible content sections.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { ChevronDownIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   ACCORDION CONTEXT
   ============================================ */

interface AccordionContextValue {
  type: "single" | "multiple"
  value: string[]
  onValueChange: (value: string[]) => void
}

const AccordionContext = React.createContext<AccordionContextValue | undefined>(undefined)

function useAccordionContext() {
  const context = React.useContext(AccordionContext)
  if (!context) {
    throw new Error("Accordion components must be used within an Accordion")
  }
  return context
}

/* ============================================
   ACCORDION ROOT
   ============================================ */

interface AccordionProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Single or multiple items can be open */
  type?: "single" | "multiple"
  /** Controlled value - array of open item values */
  value?: string[]
  /** Default open items */
  defaultValue?: string[]
  /** Callback when value changes */
  onValueChange?: (value: string[]) => void
  /** Allow collapsing all items (only for single type) */
  collapsible?: boolean
}

const Accordion = React.forwardRef<HTMLDivElement, AccordionProps>(
  (
    {
      className,
      type = "single",
      value: controlledValue,
      defaultValue = [],
      onValueChange,
      collapsible = true,
      children,
      ...props
    },
    ref
  ) => {
    const [internalValue, setInternalValue] = React.useState<string[]>(defaultValue)

    const isControlled = controlledValue !== undefined
    const value = isControlled ? controlledValue : internalValue

    const handleValueChange = (newValue: string[]) => {
      if (!isControlled) {
        setInternalValue(newValue)
      }
      onValueChange?.(newValue)
    }

    return (
      <AccordionContext.Provider value={{ type, value, onValueChange: handleValueChange }}>
        <div
          ref={ref}
          className={cn("divide-y divide-gray-200 dark:divide-dark-border/30", className)}
          {...props}
        >
          {children}
        </div>
      </AccordionContext.Provider>
    )
  }
)
Accordion.displayName = "Accordion"

/* ============================================
   ACCORDION ITEM CONTEXT
   ============================================ */

interface AccordionItemContextValue {
  value: string
  isOpen: boolean
  toggle: () => void
}

const AccordionItemContext = React.createContext<AccordionItemContextValue | undefined>(undefined)

function useAccordionItemContext() {
  const context = React.useContext(AccordionItemContext)
  if (!context) {
    throw new Error("AccordionTrigger/Content must be used within an AccordionItem")
  }
  return context
}

/* ============================================
   ACCORDION ITEM
   ============================================ */

interface AccordionItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  disabled?: boolean
}

const AccordionItem = React.forwardRef<HTMLDivElement, AccordionItemProps>(
  ({ className, value, disabled, children, ...props }, ref) => {
    const { type, value: openValues, onValueChange } = useAccordionContext()
    const isOpen = openValues.includes(value)

    const toggle = () => {
      if (disabled) return

      if (type === "single") {
        onValueChange(isOpen ? [] : [value])
      } else {
        onValueChange(
          isOpen
            ? openValues.filter((v) => v !== value)
            : [...openValues, value]
        )
      }
    }

    return (
      <AccordionItemContext.Provider value={{ value, isOpen, toggle }}>
        <div
          ref={ref}
          data-state={isOpen ? "open" : "closed"}
          className={cn(disabled && "opacity-50", className)}
          {...props}
        >
          {children}
        </div>
      </AccordionItemContext.Provider>
    )
  }
)
AccordionItem.displayName = "AccordionItem"

/* ============================================
   ACCORDION TRIGGER
   ============================================ */

interface AccordionTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode
}

const AccordionTrigger = React.forwardRef<HTMLButtonElement, AccordionTriggerProps>(
  ({ className, icon, children, ...props }, ref) => {
    const { isOpen, toggle } = useAccordionItemContext()

    return (
      <button
        ref={ref}
        type="button"
        onClick={toggle}
        aria-expanded={isOpen}
        className={cn(
          "flex items-center justify-between w-full py-4 text-left",
          "text-sm font-medium text-charcoal dark:text-gray-200",
          "hover:text-eliza-red dark:hover:text-white",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-2",
          "transition-colors",
          className
        )}
        {...props}
      >
        <span className="flex items-center gap-3">
          {icon && <span className="w-5 h-5 flex-shrink-0">{icon}</span>}
          {children}
        </span>
        <ChevronDownIcon
          className={cn(
            "w-5 h-5 text-gray-400 transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </button>
    )
  }
)
AccordionTrigger.displayName = "AccordionTrigger"

/* ============================================
   ACCORDION CONTENT
   ============================================ */

const AccordionContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { isOpen } = useAccordionItemContext()
  const contentRef = React.useRef<HTMLDivElement>(null)
  const [height, setHeight] = React.useState<number | undefined>(undefined)

  React.useEffect(() => {
    if (contentRef.current) {
      setHeight(contentRef.current.scrollHeight)
    }
  }, [children])

  return (
    <div
      ref={ref}
      className={cn(
        "overflow-hidden transition-all duration-200 ease-out",
        className
      )}
      style={{ height: isOpen ? height : 0 }}
      {...props}
    >
      <div ref={contentRef} className="pb-4 text-sm text-gray-600 dark:text-gray-400">
        {children}
      </div>
    </div>
  )
})
AccordionContent.displayName = "AccordionContent"

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
export type { AccordionProps, AccordionItemProps, AccordionTriggerProps }

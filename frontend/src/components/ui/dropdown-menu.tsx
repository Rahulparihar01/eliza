/**
 * DropdownMenu - Action Menu Component
 * 
 * Dropdown menu for actions and navigation.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { ChevronRightIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   DROPDOWN CONTEXT
   ============================================ */

interface DropdownContextValue {
  open: boolean
  setOpen: (open: boolean) => void
}

const DropdownContext = React.createContext<DropdownContextValue | undefined>(undefined)

function useDropdownContext() {
  const context = React.useContext(DropdownContext)
  if (!context) {
    throw new Error("Dropdown components must be used within a DropdownMenu")
  }
  return context
}

/* ============================================
   DROPDOWN MENU ROOT
   ============================================ */

interface DropdownMenuProps {
  children: React.ReactNode
  className?: string
}

const DropdownMenu: React.FC<DropdownMenuProps> = ({ children, className }) => {
  const [open, setOpen] = React.useState(false)
  const containerRef = React.useRef<HTMLDivElement>(null)

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
    <DropdownContext.Provider value={{ open, setOpen }}>
      <div ref={containerRef} className={cn("relative inline-block", className)}>
        {children}
      </div>
    </DropdownContext.Provider>
  )
}

/* ============================================
   DROPDOWN TRIGGER
   ============================================ */

interface DropdownTriggerProps {
  children: React.ReactElement
  asChild?: boolean
}

const DropdownTrigger: React.FC<DropdownTriggerProps> = ({ children, asChild }) => {
  const { open, setOpen } = useDropdownContext()

  if (asChild) {
    return React.cloneElement(children, {
      onClick: (e: React.MouseEvent) => {
        children.props.onClick?.(e)
        setOpen(!open)
      },
      "aria-expanded": open,
      "aria-haspopup": true,
    })
  }

  return (
    <button onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup>
      {children}
    </button>
  )
}

/* ============================================
   DROPDOWN CONTENT
   ============================================ */

interface DropdownContentProps extends React.HTMLAttributes<HTMLDivElement> {
  align?: "start" | "center" | "end"
  side?: "bottom" | "top"
}

const DropdownContent = React.forwardRef<HTMLDivElement, DropdownContentProps>(
  ({ className, align = "start", side = "bottom", children, ...props }, ref) => {
    const { open } = useDropdownContext()

    if (!open) return null

    const alignClasses = {
      start: "left-0",
      center: "left-1/2 -translate-x-1/2",
      end: "right-0",
    }

    const sideClasses = {
      bottom: "top-full mt-1",
      top: "bottom-full mb-1",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "absolute z-50 min-w-[180px] py-1 rounded-xl border shadow-lg",
          "bg-white border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/50",
          alignClasses[align],
          sideClasses[side],
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
DropdownContent.displayName = "DropdownContent"

/* ============================================
   DROPDOWN ITEM
   ============================================ */

interface DropdownItemProps extends React.HTMLAttributes<HTMLDivElement> {
  disabled?: boolean
  destructive?: boolean
  icon?: React.ReactNode
}

const DropdownItem = React.forwardRef<HTMLDivElement, DropdownItemProps>(
  ({ className, disabled, destructive, icon, children, onClick, ...props }, ref) => {
    const { setOpen } = useDropdownContext()

    const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
      if (!disabled) {
        onClick?.(e)
        setOpen(false)
      }
    }

    return (
      <div
        ref={ref}
        role="menuitem"
        onClick={handleClick}
        className={cn(
          "flex items-center gap-2 px-3 py-2 text-sm cursor-pointer",
          "text-charcoal dark:text-gray-200",
          !disabled && !destructive && "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
          destructive && "text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
        {...props}
      >
        {icon && <span className="w-4 h-4 flex-shrink-0">{icon}</span>}
        <span className="flex-1">{children}</span>
      </div>
    )
  }
)
DropdownItem.displayName = "DropdownItem"

/* ============================================
   DROPDOWN LABEL
   ============================================ */

const DropdownLabel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "px-3 py-1.5 text-xs font-semibold uppercase tracking-wider",
      "text-gray-500 dark:text-gray-400",
      className
    )}
    {...props}
  />
))
DropdownLabel.displayName = "DropdownLabel"

/* ============================================
   DROPDOWN SEPARATOR
   ============================================ */

const DropdownSeparator = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("my-1 h-px bg-gray-200 dark:bg-dark-border/30", className)}
    {...props}
  />
))
DropdownSeparator.displayName = "DropdownSeparator"

/* ============================================
   DROPDOWN SUBMENU (Simple version)
   ============================================ */

interface DropdownSubmenuProps {
  label: string
  icon?: React.ReactNode
  children: React.ReactNode
}

const DropdownSubmenu: React.FC<DropdownSubmenuProps> = ({ label, icon, children }) => {
  const [open, setOpen] = React.useState(false)

  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2 text-sm cursor-pointer",
          "text-charcoal dark:text-gray-200",
          "hover:bg-gray-50 dark:hover:bg-dark-surface-2"
        )}
      >
        {icon && <span className="w-4 h-4 flex-shrink-0">{icon}</span>}
        <span className="flex-1">{label}</span>
        <ChevronRightIcon className="w-4 h-4 text-gray-400" />
      </div>
      {open && (
        <div
          className={cn(
            "absolute left-full top-0 ml-1 min-w-[160px] py-1 rounded-xl border shadow-lg",
            "bg-white border-gray-200",
            "dark:bg-dark-surface dark:border-dark-border/50"
          )}
        >
          {children}
        </div>
      )}
    </div>
  )
}

export {
  DropdownMenu,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
  DropdownLabel,
  DropdownSeparator,
  DropdownSubmenu,
}
export type { DropdownMenuProps, DropdownContentProps, DropdownItemProps, DropdownSubmenuProps }

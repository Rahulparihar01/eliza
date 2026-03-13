/**
 * Popover - Floating Content Panel Component
 * 
 * A positioned panel for rich content (not just menu items).
 * Use for notifications, user menus, filters, and other complex popovers.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { XMarkIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   POPOVER CONTEXT
   ============================================ */

interface PopoverContextValue {
  open: boolean
  setOpen: (open: boolean) => void
  close: () => void
}

const PopoverContext = React.createContext<PopoverContextValue | undefined>(undefined)

function usePopoverContext() {
  const context = React.useContext(PopoverContext)
  if (!context) {
    throw new Error("Popover components must be used within a Popover")
  }
  return context
}

/* ============================================
   POPOVER ROOT
   ============================================ */

interface PopoverProps {
  children: React.ReactNode
  /** Controlled open state */
  open?: boolean
  /** Callback when open state changes */
  onOpenChange?: (open: boolean) => void
  /** Default open state (uncontrolled) */
  defaultOpen?: boolean
  className?: string
}

const Popover: React.FC<PopoverProps> = ({ 
  children, 
  open: controlledOpen,
  onOpenChange,
  defaultOpen = false,
  className 
}) => {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen)
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Support both controlled and uncontrolled modes
  const isControlled = controlledOpen !== undefined
  const open = isControlled ? controlledOpen : internalOpen

  const setOpen = React.useCallback((newOpen: boolean) => {
    if (!isControlled) {
      setInternalOpen(newOpen)
    }
    onOpenChange?.(newOpen)
  }, [isControlled, onOpenChange])

  const close = React.useCallback(() => setOpen(false), [setOpen])

  // Close on outside click
  React.useEffect(() => {
    if (!open) return

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [open, setOpen])

  // Close on escape
  React.useEffect(() => {
    if (!open) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [open, setOpen])

  return (
    <PopoverContext.Provider value={{ open, setOpen, close }}>
      <div ref={containerRef} className={cn("relative inline-block", className)}>
        {children}
      </div>
    </PopoverContext.Provider>
  )
}
Popover.displayName = "Popover"

/* ============================================
   POPOVER TRIGGER
   ============================================ */

interface PopoverTriggerProps {
  children: React.ReactElement
  /** Render as child element instead of wrapping in button */
  asChild?: boolean
}

const PopoverTrigger: React.FC<PopoverTriggerProps> = ({ children, asChild }) => {
  const { open, setOpen } = usePopoverContext()

  if (asChild) {
    return React.cloneElement(children, {
      onClick: (e: React.MouseEvent) => {
        children.props.onClick?.(e)
        setOpen(!open)
      },
      "aria-expanded": open,
      "aria-haspopup": "dialog",
    })
  }

  return (
    <button 
      onClick={() => setOpen(!open)} 
      aria-expanded={open} 
      aria-haspopup="dialog"
      type="button"
    >
      {children}
    </button>
  )
}
PopoverTrigger.displayName = "PopoverTrigger"

/* ============================================
   POPOVER CONTENT
   ============================================ */

interface PopoverContentProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Horizontal alignment relative to trigger */
  align?: "start" | "center" | "end"
  /** Which side to position on */
  side?: "top" | "bottom" | "left" | "right"
  /** Offset from trigger in pixels */
  sideOffset?: number
}

const PopoverContent = React.forwardRef<HTMLDivElement, PopoverContentProps>(
  ({ className, align = "center", side = "bottom", sideOffset = 4, children, ...props }, ref) => {
    const { open } = usePopoverContext()
    const [isVisible, setIsVisible] = React.useState(false)
    const [shouldRender, setShouldRender] = React.useState(false)

    // Handle enter/leave transitions
    React.useEffect(() => {
      if (open) {
        setShouldRender(true)
        // Small delay to trigger CSS transition
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            setIsVisible(true)
          })
        })
      } else {
        setIsVisible(false)
        // Wait for exit animation before unmounting
        const timer = setTimeout(() => {
          setShouldRender(false)
        }, 100) // Match the leave duration
        return () => clearTimeout(timer)
      }
    }, [open])

    if (!shouldRender) return null

    const alignClasses = {
      start: "left-0",
      center: "left-1/2 -translate-x-1/2",
      end: "right-0",
    }

    const sideClasses = {
      bottom: `top-full`,
      top: `bottom-full`,
      left: `right-full top-0`,
      right: `left-full top-0`,
    }

    // For left/right positioning, adjust alignment to be vertical
    const getPositionClasses = () => {
      if (side === "left" || side === "right") {
        const verticalAlign = {
          start: "top-0",
          center: "top-1/2 -translate-y-1/2",
          end: "bottom-0",
        }
        return cn(sideClasses[side], verticalAlign[align])
      }
      return cn(sideClasses[side], alignClasses[align])
    }

    return (
      <div
        ref={ref}
        role="dialog"
        className={cn(
          "absolute z-50 min-w-[200px] rounded-xl border shadow-lg overflow-hidden",
          "bg-white border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/50",
          // CSS Transition (like HeadlessUI)
          "transition ease-out duration-100",
          "transform origin-top-right",
          isVisible 
            ? "opacity-100 scale-100" 
            : "opacity-0 scale-95",
          getPositionClasses(),
          className
        )}
        style={{ 
          marginTop: side === "bottom" ? sideOffset : undefined,
          marginBottom: side === "top" ? sideOffset : undefined,
          marginLeft: side === "right" ? sideOffset : undefined,
          marginRight: side === "left" ? sideOffset : undefined,
        }}
        {...props}
      >
        {children}
      </div>
    )
  }
)
PopoverContent.displayName = "PopoverContent"

/* ============================================
   POPOVER CLOSE
   ============================================ */

interface PopoverCloseProps {
  children?: React.ReactNode
  /** Render as child element instead of default button */
  asChild?: boolean
  className?: string
}

const PopoverClose: React.FC<PopoverCloseProps> = ({ children, asChild, className }) => {
  const { close } = usePopoverContext()

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>, {
      onClick: (e: React.MouseEvent) => {
        (children as React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>).props.onClick?.(e)
        close()
      },
    })
  }

  // Default close button
  return (
    <button
      onClick={close}
      className={cn(
        "p-1.5 rounded-lg transition-colors",
        "text-gray-400 hover:text-gray-600 hover:bg-gray-100",
        "dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-dark-surface-2",
        className
      )}
      aria-label="Close"
      type="button"
    >
      {children || <XMarkIcon className="w-4 h-4" />}
    </button>
  )
}
PopoverClose.displayName = "PopoverClose"

/* ============================================
   POPOVER HEADER (Optional helper)
   ============================================ */

interface PopoverHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Show close button */
  showClose?: boolean
}

const PopoverHeader = React.forwardRef<HTMLDivElement, PopoverHeaderProps>(
  ({ className, showClose = true, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center justify-between px-4 py-3 border-b",
          "border-gray-200 dark:border-dark-border/30",
          className
        )}
        {...props}
      >
        <div className="flex-1 font-medium text-charcoal dark:text-white">
          {children}
        </div>
        {showClose && <PopoverClose />}
      </div>
    )
  }
)
PopoverHeader.displayName = "PopoverHeader"

/* ============================================
   POPOVER BODY (Optional helper)
   ============================================ */

const PopoverBody = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("p-4", className)}
    {...props}
  />
))
PopoverBody.displayName = "PopoverBody"

/* ============================================
   POPOVER FOOTER (Optional helper)
   ============================================ */

const PopoverFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "px-4 py-3 border-t",
      "border-gray-200 dark:border-dark-border/30",
      "bg-gray-50 dark:bg-dark-surface-2",
      className
    )}
    {...props}
  />
))
PopoverFooter.displayName = "PopoverFooter"

/* ============================================
   EXPORTS
   ============================================ */

export {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverClose,
  PopoverHeader,
  PopoverBody,
  PopoverFooter,
  usePopoverContext,
}

export type { 
  PopoverProps, 
  PopoverTriggerProps, 
  PopoverContentProps, 
  PopoverCloseProps,
  PopoverHeaderProps,
}

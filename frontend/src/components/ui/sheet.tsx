/**
 * Sheet - Slide-in Panel Component
 * 
 * A slide-in panel from the edge of the screen.
 * Similar to Modal but slides in from a side rather than appearing centered.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { createPortal } from "react-dom"
import { XMarkIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   SHEET CONTEXT
   ============================================ */

interface SheetContextValue {
  open: boolean
  onClose: () => void
}

const SheetContext = React.createContext<SheetContextValue | undefined>(undefined)

function useSheetContext() {
  const context = React.useContext(SheetContext)
  if (!context) {
    throw new Error("Sheet components must be used within a Sheet provider")
  }
  return context
}

/* ============================================
   SHEET ROOT
   ============================================ */

interface SheetProps {
  open: boolean
  onClose: () => void
  children: React.ReactNode
}

const Sheet: React.FC<SheetProps> = ({ open, onClose, children }) => {
  // Handle escape key
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose()
      }
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [open, onClose])

  // Prevent body scroll when sheet is open
  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  if (!open) return null

  return (
    <SheetContext.Provider value={{ open, onClose }}>
      {createPortal(children, document.body)}
    </SheetContext.Provider>
  )
}
Sheet.displayName = "Sheet"

/* ============================================
   SHEET BACKDROP
   ============================================ */

interface SheetBackdropProps extends React.HTMLAttributes<HTMLDivElement> {
  closeOnClick?: boolean
}

const SheetBackdrop = React.forwardRef<HTMLDivElement, SheetBackdropProps>(
  ({ className, closeOnClick = true, ...props }, ref) => {
    const { onClose } = useSheetContext()

    return (
      <div
        ref={ref}
        className={cn(
          "fixed inset-0 z-[60] bg-black/30 backdrop-blur-sm",
          "animate-fade-in",
          className
        )}
        onClick={closeOnClick ? onClose : undefined}
        aria-hidden="true"
        {...props}
      />
    )
  }
)
SheetBackdrop.displayName = "SheetBackdrop"

/* ============================================
   SHEET CONTENT
   ============================================ */

type SheetSide = "left" | "right" | "top" | "bottom"
type SheetSize = "sm" | "md" | "lg" | "xl" | "2xl" | "half" | "full"

interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: SheetSide
  size?: SheetSize
  /** Top offset in pixels (e.g., 48 for header height) */
  topOffset?: number
}

const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, side = "right", size = "md", topOffset = 0, children, ...props }, ref) => {
    const { onClose } = useSheetContext()
    const contentRef = React.useRef<HTMLDivElement>(null)

    // Handle click outside
    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (contentRef.current && !contentRef.current.contains(e.target as Node)) {
          onClose()
        }
      }
      document.addEventListener("mousedown", handleClickOutside)
      return () => document.removeEventListener("mousedown", handleClickOutside)
    }, [onClose])

    const sizeClasses: Record<SheetSide, Record<SheetSize, string>> = {
      right: {
        sm: "max-w-sm w-full",
        md: "max-w-md w-full",
        lg: "max-w-lg w-full",
        xl: "max-w-xl w-full",
        "2xl": "max-w-2xl w-full",
        half: "w-1/2",
        full: "w-full max-w-none",
      },
      left: {
        sm: "max-w-sm w-full",
        md: "max-w-md w-full",
        lg: "max-w-lg w-full",
        xl: "max-w-xl w-full",
        "2xl": "max-w-2xl w-full",
        half: "w-1/2",
        full: "w-full max-w-none",
      },
      top: {
        sm: "max-h-[200px]",
        md: "max-h-[300px]",
        lg: "max-h-[400px]",
        xl: "max-h-[500px]",
        "2xl": "max-h-[600px]",
        half: "h-1/2",
        full: "max-h-[80vh]",
      },
      bottom: {
        sm: "max-h-[200px]",
        md: "max-h-[300px]",
        lg: "max-h-[400px]",
        xl: "max-h-[500px]",
        "2xl": "max-h-[600px]",
        half: "h-1/2",
        full: "max-h-[80vh]",
      },
    }

    const positionClasses: Record<SheetSide, string> = {
      right: "right-0 h-full",
      left: "left-0 h-full",
      top: "top-0 left-0 right-0 w-full",
      bottom: "bottom-0 left-0 right-0 w-full",
    }

    const animationClasses: Record<SheetSide, string> = {
      right: "animate-slide-in-from-right",
      left: "animate-slide-in-from-left",
      top: "animate-slide-in-from-top",
      bottom: "animate-slide-in-from-bottom",
    }

    const borderClasses: Record<SheetSide, string> = {
      right: "border-l",
      left: "border-r",
      top: "border-b",
      bottom: "border-t",
    }

    // Calculate top style for vertical sides
    const topStyle = (side === "right" || side === "left") && topOffset > 0 
      ? { top: `${topOffset}px`, height: `calc(100% - ${topOffset}px)` }
      : { top: 0 }

    return (
      <>
        <SheetBackdrop />
        <div
          ref={(node) => {
            // Merge refs
            if (typeof ref === 'function') ref(node)
            else if (ref) ref.current = node
            ;(contentRef as React.MutableRefObject<HTMLDivElement | null>).current = node
          }}
          role="dialog"
          aria-modal="true"
          className={cn(
            "fixed z-[61] flex flex-col",
            "bg-white shadow-2xl",
            "dark:bg-dark-surface dark:border-dark-border",
            positionClasses[side],
            sizeClasses[side][size],
            animationClasses[side],
            borderClasses[side],
            "border-gray-200 dark:border-dark-border",
            className
          )}
          style={topStyle}
          {...props}
        >
          {children}
        </div>
      </>
    )
  }
)
SheetContent.displayName = "SheetContent"

/* ============================================
   SHEET HEADER
   ============================================ */

interface SheetHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  showCloseButton?: boolean
}

const SheetHeader = React.forwardRef<HTMLDivElement, SheetHeaderProps>(
  ({ className, showCloseButton = true, children, ...props }, ref) => {
    const { onClose } = useSheetContext()

    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center justify-between px-6 py-4 border-b",
          "border-gray-200 dark:border-dark-border",
          "bg-white dark:bg-dark-surface",
          "shrink-0",
          className
        )}
        {...props}
      >
        <div className="flex-1 min-w-0">{children}</div>
        {showCloseButton && (
          <button
            onClick={onClose}
            className={cn(
              "ml-4 p-2 rounded-lg transition-colors shrink-0",
              "text-gray-400 hover:text-gray-600 hover:bg-gray-100",
              "dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-dark-surface-2"
            )}
            aria-label="Close panel"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        )}
      </div>
    )
  }
)
SheetHeader.displayName = "SheetHeader"

/* ============================================
   SHEET TITLE
   ============================================ */

const SheetTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h2
    ref={ref}
    className={cn(
      "font-semibold text-lg text-charcoal dark:text-white",
      className
    )}
    {...props}
  />
))
SheetTitle.displayName = "SheetTitle"

/* ============================================
   SHEET DESCRIPTION
   ============================================ */

const SheetDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      "text-xs text-gray-500 dark:text-gray-400 mt-0.5",
      className
    )}
    {...props}
  />
))
SheetDescription.displayName = "SheetDescription"

/* ============================================
   SHEET BODY
   ============================================ */

const SheetBody = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex-1 overflow-y-auto p-6", className)}
    {...props}
  />
))
SheetBody.displayName = "SheetBody"

/* ============================================
   SHEET FOOTER
   ============================================ */

const SheetFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "px-6 py-3 border-t shrink-0",
      "border-gray-200 dark:border-dark-border",
      "bg-gray-50 dark:bg-dark-surface-2",
      className
    )}
    {...props}
  />
))
SheetFooter.displayName = "SheetFooter"

export {
  Sheet,
  SheetBackdrop,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  useSheetContext,
}
export type { SheetProps, SheetBackdropProps, SheetContentProps, SheetHeaderProps, SheetSide, SheetSize }

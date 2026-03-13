/**
 * Modal - Dialog Component
 * 
 * A modal dialog with backdrop, animations, and accessibility features.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { XMarkIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   MODAL CONTEXT
   ============================================ */

interface ModalContextValue {
  open: boolean
  onClose: () => void
}

const ModalContext = React.createContext<ModalContextValue | undefined>(undefined)

function useModalContext() {
  const context = React.useContext(ModalContext)
  if (!context) {
    throw new Error("Modal components must be used within a Modal provider")
  }
  return context
}

/* ============================================
   MODAL ROOT
   ============================================ */

interface ModalProps {
  open: boolean
  onClose: () => void
  children: React.ReactNode
}

const Modal: React.FC<ModalProps> = ({ open, onClose, children }) => {
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

  // Prevent body scroll when modal is open
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
    <ModalContext.Provider value={{ open, onClose }}>
      {children}
    </ModalContext.Provider>
  )
}
Modal.displayName = "Modal"

/* ============================================
   MODAL BACKDROP
   ============================================ */

interface ModalBackdropProps extends React.HTMLAttributes<HTMLDivElement> {
  closeOnClick?: boolean
}

const ModalBackdrop = React.forwardRef<HTMLDivElement, ModalBackdropProps>(
  ({ className, closeOnClick = true, ...props }, ref) => {
    const { onClose } = useModalContext()

    return (
      <div
        ref={ref}
        className={cn(
          "fixed inset-0 z-[70] bg-black/50 backdrop-blur-sm",
          "animate-in fade-in-0 duration-200",
          className
        )}
        onClick={closeOnClick ? onClose : undefined}
        aria-hidden="true"
        {...props}
      />
    )
  }
)
ModalBackdrop.displayName = "ModalBackdrop"

/* ============================================
   MODAL CONTENT
   ============================================ */

interface ModalContentProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "md" | "lg" | "xl" | "full"
}

const ModalContent = React.forwardRef<HTMLDivElement, ModalContentProps>(
  ({ className, size = "md", children, ...props }, ref) => {
    const sizeClasses = {
      sm: "max-w-sm",
      md: "max-w-md",
      lg: "max-w-lg",
      xl: "max-w-xl",
      full: "max-w-4xl",
    }

    return (
      <>
        <ModalBackdrop />
        <div className="fixed inset-0 z-[71] flex items-center justify-center p-4">
          <div
            ref={ref}
            role="dialog"
            aria-modal="true"
            className={cn(
              "relative w-full bg-white rounded-2xl shadow-xl",
              "dark:bg-dark-surface dark:border dark:border-dark-border/30",
              "animate-in fade-in-0 zoom-in-95 duration-200",
              sizeClasses[size],
              className
            )}
            onClick={(e) => e.stopPropagation()}
            {...props}
          >
            {children}
          </div>
        </div>
      </>
    )
  }
)
ModalContent.displayName = "ModalContent"

/* ============================================
   MODAL HEADER
   ============================================ */

interface ModalHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  showCloseButton?: boolean
}

const ModalHeader = React.forwardRef<HTMLDivElement, ModalHeaderProps>(
  ({ className, showCloseButton = true, children, ...props }, ref) => {
    const { onClose } = useModalContext()

    return (
      <div
        ref={ref}
        className={cn(
          "flex items-start justify-between p-6 pb-0",
          className
        )}
        {...props}
      >
        <div className="flex-1">{children}</div>
        {showCloseButton && (
          <button
            onClick={onClose}
            className={cn(
              "ml-4 p-1.5 rounded-lg transition-colors",
              "text-gray-400 hover:text-gray-600 hover:bg-gray-100",
              "dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-dark-surface-2"
            )}
            aria-label="Close modal"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        )}
      </div>
    )
  }
)
ModalHeader.displayName = "ModalHeader"

/* ============================================
   MODAL TITLE
   ============================================ */

const ModalTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h2
    ref={ref}
    className={cn(
      "font-title text-xl font-normal text-charcoal dark:text-white",
      className
    )}
    {...props}
  />
))
ModalTitle.displayName = "ModalTitle"

/* ============================================
   MODAL DESCRIPTION
   ============================================ */

const ModalDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      "mt-1 text-sm text-gray-500 dark:text-gray-400",
      className
    )}
    {...props}
  />
))
ModalDescription.displayName = "ModalDescription"

/* ============================================
   MODAL BODY
   ============================================ */

const ModalBody = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("p-6", className)}
    {...props}
  />
))
ModalBody.displayName = "ModalBody"

/* ============================================
   MODAL FOOTER
   ============================================ */

const ModalFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex items-center justify-end gap-3 p-6 pt-0",
      className
    )}
    {...props}
  />
))
ModalFooter.displayName = "ModalFooter"

export {
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
}
export type { ModalProps, ModalBackdropProps, ModalContentProps, ModalHeaderProps }

/**
 * Modal Floating Actions
 * 
 * A floating action bar for modals that sits at the bottom-right corner
 * with a subtle gradient backdrop. Creates a more open, workspace-like feel.
 * 
 * Usage:
 * ```tsx
 * <ModalFloatingActions>
 *   <Button variant="outline">Save</Button>
 *   <Button>Save & Run</Button>
 * </ModalFloatingActions>
 * ```
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

interface ModalFloatingActionsProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Position within the modal content area */
  position?: "bottom-right" | "bottom-center" | "bottom-left"
  /** Whether to show the gradient backdrop */
  showGradient?: boolean
  /** Height of the gradient fade area */
  gradientHeight?: "sm" | "md" | "lg"
}

const ModalFloatingActions = React.forwardRef<HTMLDivElement, ModalFloatingActionsProps>(
  (
    {
      className,
      children,
      position = "bottom-right",
      showGradient = true,
      gradientHeight = "md",
      ...props
    },
    ref
  ) => {
    const positionClasses = {
      "bottom-right": "justify-end",
      "bottom-center": "justify-center",
      "bottom-left": "justify-start",
    }

    const gradientHeightClasses = {
      sm: "h-12",
      md: "h-16",
      lg: "h-20",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "absolute bottom-0 left-0 right-0 pointer-events-none",
          "flex items-end p-4",
          positionClasses[position],
          className
        )}
        {...props}
      >
        {/* Gradient backdrop - behind buttons */}
        {showGradient && (
          <div
            className={cn(
              "absolute inset-x-0 bottom-0 z-0",
              gradientHeightClasses[gradientHeight],
              "bg-gradient-to-t",
              "from-white/70 via-white/40 to-transparent",
              "dark:from-dark-surface/70 dark:via-dark-surface/40 dark:to-transparent"
            )}
            aria-hidden="true"
          />
        )}

        {/* Action buttons container - above gradient */}
        <div
          className={cn(
            "relative z-10 pointer-events-auto",
            "flex items-center gap-3"
          )}
        >
          {children}
        </div>
      </div>
    )
  }
)
ModalFloatingActions.displayName = "ModalFloatingActions"

export { ModalFloatingActions }
export type { ModalFloatingActionsProps }

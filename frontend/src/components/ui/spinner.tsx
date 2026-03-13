/**
 * Spinner - Loading Indicator Component
 * 
 * Animated spinner for loading states.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

const spinnerVariants = cva(
  "animate-spin rounded-full border-2 border-current border-t-transparent",
  {
    variants: {
      size: {
        xs: "w-3 h-3",
        sm: "w-4 h-4",
        md: "w-6 h-6",
        lg: "w-8 h-8",
        xl: "w-12 h-12",
      },
      variant: {
        default: "text-gray-400 dark:text-gray-500",
        primary: "text-eliza-red",
        white: "text-white",
        muted: "text-gray-300 dark:text-gray-600",
      },
    },
    defaultVariants: {
      size: "md",
      variant: "default",
    },
  }
)

interface SpinnerProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof spinnerVariants> {
  /** Accessible label */
  label?: string
}

const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ className, size, variant, label = "Loading", ...props }, ref) => (
    <div
      ref={ref}
      role="status"
      aria-label={label}
      className={cn(spinnerVariants({ size, variant }), className)}
      {...props}
    >
      <span className="sr-only">{label}</span>
    </div>
  )
)
Spinner.displayName = "Spinner"

/* ============================================
   LOADING OVERLAY - Full container spinner
   ============================================ */

interface LoadingOverlayProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Loading message */
  message?: string
  /** Spinner size */
  size?: VariantProps<typeof spinnerVariants>["size"]
}

const LoadingOverlay = React.forwardRef<HTMLDivElement, LoadingOverlayProps>(
  ({ className, message, size = "lg", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "absolute inset-0 flex flex-col items-center justify-center",
        "bg-white/80 dark:bg-dark-bg/80 backdrop-blur-sm",
        "z-50",
        className
      )}
      {...props}
    >
      <Spinner size={size} variant="primary" />
      {message && (
        <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">{message}</p>
      )}
    </div>
  )
)
LoadingOverlay.displayName = "LoadingOverlay"

export { Spinner, LoadingOverlay, spinnerVariants }
export type { SpinnerProps, LoadingOverlayProps }

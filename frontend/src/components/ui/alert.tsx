/**
 * Alert - Inline Banner Component
 * 
 * Displays contextual feedback messages.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

const alertVariants = cva(
  "relative flex gap-3 rounded-xl border p-4",
  {
    variants: {
      variant: {
        info: [
          "bg-blue-50 border-blue-200 text-blue-800",
          "dark:bg-blue-950/30 dark:border-blue-800/50 dark:text-blue-300",
        ],
        success: [
          "bg-green-50 border-green-200 text-green-800",
          "dark:bg-green-950/30 dark:border-green-800/50 dark:text-green-300",
        ],
        warning: [
          "bg-amber-50 border-amber-200 text-amber-800",
          "dark:bg-amber-950/30 dark:border-amber-800/50 dark:text-amber-300",
        ],
        error: [
          "bg-red-50 border-red-200 text-red-800",
          "dark:bg-red-950/30 dark:border-red-800/50 dark:text-red-300",
        ],
        neutral: [
          "bg-gray-50 border-gray-200 text-gray-800",
          "dark:bg-dark-surface dark:border-dark-border/50 dark:text-gray-300",
        ],
      },
    },
    defaultVariants: {
      variant: "info",
    },
  }
)

const iconMap = {
  info: InformationCircleIcon,
  success: CheckCircleIcon,
  warning: ExclamationTriangleIcon,
  error: ExclamationCircleIcon,
  neutral: InformationCircleIcon,
}

interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  /** Alert title */
  title?: string
  /** Dismiss callback - shows close button if provided */
  onDismiss?: () => void
  /** Hide the icon */
  hideIcon?: boolean
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "info", title, onDismiss, hideIcon, children, ...props }, ref) => {
    const Icon = iconMap[variant || "info"]

    return (
      <div
        ref={ref}
        role="alert"
        className={cn(alertVariants({ variant }), className)}
        {...props}
      >
        {!hideIcon && (
          <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
        )}
        <div className="flex-1 min-w-0">
          {title && (
            <h4 className="font-medium mb-1">{title}</h4>
          )}
          <div className="text-sm opacity-90">{children}</div>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className={cn(
              "flex-shrink-0 p-1 rounded-lg transition-colors",
              "hover:bg-black/10 dark:hover:bg-white/10"
            )}
            aria-label="Dismiss alert"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        )}
      </div>
    )
  }
)
Alert.displayName = "Alert"

export { Alert, alertVariants }
export type { AlertProps }

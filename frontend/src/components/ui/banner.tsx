/**
 * Banner - Full-Width Contextual Notification Bar
 * 
 * Used for important messages anchored to the layout (not floating like Toast).
 * Examples: login state, tenant view mode, system announcements.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import {
  XMarkIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

/* ============================================
   BANNER VARIANTS
   ============================================ */

const bannerVariants = cva(
  [
    "w-full border-b transition-all duration-300 ease-out",
    "overflow-hidden",
  ],
  {
    variants: {
      variant: {
        info: [
          "bg-blue-50 border-blue-200 text-blue-800",
          "dark:bg-blue-950/50 dark:border-blue-800/50 dark:text-blue-200",
        ],
        success: [
          "bg-green-50 border-green-200 text-green-800",
          "dark:bg-green-950/50 dark:border-green-800/50 dark:text-green-200",
        ],
        warning: [
          "bg-amber-50 border-amber-200 text-amber-800",
          "dark:bg-amber-950/50 dark:border-amber-800/50 dark:text-amber-200",
        ],
        error: [
          "bg-red-50 border-red-200 text-red-800",
          "dark:bg-red-950/50 dark:border-red-800/50 dark:text-red-200",
        ],
        brand: [
          "bg-eliza-red/10 border-eliza-red/20 text-charcoal",
          "dark:bg-eliza-red/20 dark:border-eliza-red/30 dark:text-white",
        ],
        // Admin-specific solid variants
        "tenant-view": [
          "bg-amber-500 border-amber-600 text-amber-950",
        ],
        "cross-tenant": [
          "bg-violet-600 border-violet-700 text-white",
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
  brand: InformationCircleIcon,
  "tenant-view": ExclamationTriangleIcon,
  "cross-tenant": ExclamationTriangleIcon,
}

/* ============================================
   BANNER COMPONENT
   ============================================ */

interface BannerProps extends VariantProps<typeof bannerVariants> {
  /** Custom icon (overrides default variant icon) */
  icon?: React.ReactNode
  /** Optional title (bold) */
  title?: string
  /** Message content (required) */
  message: React.ReactNode
  /** Optional action button */
  action?: {
    label: string
    onClick: () => void
  }
  /** Show dismiss button */
  dismissible?: boolean
  /** Callback when dismissed */
  onDismiss?: () => void
  /** Auto-dismiss after ms (0 = never) */
  autoDismiss?: number
  /** Additional classes */
  className?: string
}

const Banner: React.FC<BannerProps> = ({
  variant = "info",
  icon,
  title,
  message,
  action,
  dismissible = true,
  onDismiss,
  autoDismiss = 0,
  className,
}) => {
  const [isVisible, setIsVisible] = React.useState(true)
  const [isExiting, setIsExiting] = React.useState(false)

  // Auto-dismiss timer
  React.useEffect(() => {
    if (autoDismiss > 0) {
      const timer = setTimeout(() => {
        handleDismiss()
      }, autoDismiss)
      return () => clearTimeout(timer)
    }
  }, [autoDismiss])

  const handleDismiss = () => {
    setIsExiting(true)
    // Wait for animation to complete
    setTimeout(() => {
      setIsVisible(false)
      onDismiss?.()
    }, 300)
  }

  if (!isVisible) return null

  const DefaultIcon = iconMap[variant || "info"]
  const IconToRender = icon || <DefaultIcon className="w-5 h-5 flex-shrink-0" />

  return (
    <div
      className={cn(
        bannerVariants({ variant }),
        isExiting ? "max-h-0 opacity-0" : "max-h-20 opacity-100",
        className
      )}
    >
      <div className="px-4 py-2.5">
        <div className="flex items-center justify-center relative max-w-screen-2xl mx-auto">
          {/* Icon + Content */}
          <div className="flex items-center gap-3">
            {/* Icon container */}
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
              variant === "info" && "bg-blue-100 dark:bg-blue-900/50",
              variant === "success" && "bg-green-100 dark:bg-green-900/50",
              variant === "warning" && "bg-amber-100 dark:bg-amber-900/50",
              variant === "error" && "bg-red-100 dark:bg-red-900/50",
              variant === "brand" && "bg-eliza-red/20 dark:bg-eliza-red/30",
              variant === "tenant-view" && "bg-amber-400",
              variant === "cross-tenant" && "bg-violet-500",
            )}>
              {IconToRender}
            </div>

            {/* Text content */}
            <div className="flex items-center gap-2">
              {title && (
                <>
                  <span className="font-semibold">{title}</span>
                  <span className="opacity-50">|</span>
                </>
              )}
              <span className="text-sm">{message}</span>
            </div>

            {/* Action button */}
            {action && (
              <button
                onClick={action.onClick}
                className={cn(
                  "ml-4 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors",
                  variant === "info" && "bg-blue-100 hover:bg-blue-200 dark:bg-blue-800/50 dark:hover:bg-blue-700/50",
                  variant === "success" && "bg-green-100 hover:bg-green-200 dark:bg-green-800/50 dark:hover:bg-green-700/50",
                  variant === "warning" && "bg-amber-100 hover:bg-amber-200 dark:bg-amber-800/50 dark:hover:bg-amber-700/50",
                  variant === "error" && "bg-red-100 hover:bg-red-200 dark:bg-red-800/50 dark:hover:bg-red-700/50",
                  variant === "brand" && "bg-eliza-red/20 hover:bg-eliza-red/30 dark:bg-eliza-red/30 dark:hover:bg-eliza-red/40",
                  variant === "tenant-view" && "bg-amber-400 hover:bg-amber-300",
                  variant === "cross-tenant" && "bg-violet-500 hover:bg-violet-400",
                )}
              >
                {action.label}
              </button>
            )}
          </div>

          {/* Dismiss button */}
          {dismissible && (
            <button
              onClick={handleDismiss}
              className={cn(
                "absolute right-0 p-1.5 rounded-lg transition-colors",
                "hover:bg-black/10 dark:hover:bg-white/10"
              )}
              aria-label="Dismiss"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
Banner.displayName = "Banner"

/* ============================================
   BANNER CONTAINER (For stacking multiple banners)
   ============================================ */

interface BannerContainerProps {
  children: React.ReactNode
  className?: string
}

const BannerContainer: React.FC<BannerContainerProps> = ({ children, className }) => {
  return (
    <div className={cn("flex flex-col", className)}>
      {children}
    </div>
  )
}
BannerContainer.displayName = "BannerContainer"

/* ============================================
   EXPORTS
   ============================================ */

export { Banner, BannerContainer, bannerVariants }
export type { BannerProps, BannerContainerProps }

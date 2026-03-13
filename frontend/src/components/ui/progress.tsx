/**
 * Progress - Progress Bar Component
 * 
 * Visual indicator for progress and loading states.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

/* ============================================
   PROGRESS BAR
   ============================================ */

const progressVariants = cva(
  "w-full overflow-hidden rounded-full bg-gray-200 dark:bg-dark-surface-2",
  {
    variants: {
      size: {
        sm: "h-1",
        md: "h-2",
        lg: "h-3",
        xl: "h-4",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
)

const progressBarVariants = cva(
  "h-full rounded-full transition-all duration-300 ease-out",
  {
    variants: {
      variant: {
        default: "bg-eliza-red",
        success: "bg-green-500",
        warning: "bg-amber-500",
        info: "bg-blue-500",
        gradient: "bg-gradient-to-r from-eliza-red to-eliza-red-coral",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface ProgressProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof progressVariants>,
    VariantProps<typeof progressBarVariants> {
  /** Progress value (0-100) */
  value?: number
  /** Show percentage label */
  showLabel?: boolean
  /** Indeterminate loading state */
  indeterminate?: boolean
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  (
    {
      className,
      value = 0,
      size,
      variant,
      showLabel,
      indeterminate,
      ...props
    },
    ref
  ) => {
    const clampedValue = Math.min(100, Math.max(0, value))

    return (
      <div className={cn("w-full", className)} {...props}>
        {showLabel && !indeterminate && (
          <div className="flex justify-between mb-1">
            <span className="text-sm text-gray-600 dark:text-gray-400">Progress</span>
            <span className="text-sm font-medium text-charcoal dark:text-gray-200">
              {Math.round(clampedValue)}%
            </span>
          </div>
        )}
        <div ref={ref} className={progressVariants({ size })}>
          <div
            className={cn(
              progressBarVariants({ variant }),
              indeterminate && "animate-progress-indeterminate w-1/3"
            )}
            style={!indeterminate ? { width: `${clampedValue}%` } : undefined}
            role="progressbar"
            aria-valuenow={indeterminate ? undefined : clampedValue}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>
    )
  }
)
Progress.displayName = "Progress"

/* ============================================
   CIRCULAR PROGRESS
   ============================================ */

interface CircularProgressProps extends React.SVGAttributes<SVGSVGElement> {
  /** Progress value (0-100) */
  value?: number
  /** Size in pixels */
  size?: number
  /** Stroke width */
  strokeWidth?: number
  /** Show percentage label */
  showLabel?: boolean
  /** Indeterminate loading state */
  indeterminate?: boolean
  /** Color variant */
  variant?: "default" | "success" | "warning" | "info"
}

const variantColors = {
  default: "stroke-eliza-red",
  success: "stroke-green-500",
  warning: "stroke-amber-500",
  info: "stroke-blue-500",
}

const CircularProgress = React.forwardRef<SVGSVGElement, CircularProgressProps>(
  (
    {
      className,
      value = 0,
      size = 48,
      strokeWidth = 4,
      showLabel,
      indeterminate,
      variant = "default",
      ...props
    },
    ref
  ) => {
    const clampedValue = Math.min(100, Math.max(0, value))
    const radius = (size - strokeWidth) / 2
    const circumference = radius * 2 * Math.PI
    const offset = circumference - (clampedValue / 100) * circumference

    return (
      <div className="relative inline-flex items-center justify-center">
        <svg
          ref={ref}
          width={size}
          height={size}
          className={cn(
            indeterminate && "animate-spin",
            className
          )}
          {...props}
        >
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            className="stroke-gray-200 dark:stroke-dark-surface-2"
          />
          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            className={cn(variantColors[variant], "transition-all duration-300")}
            style={{
              strokeDasharray: circumference,
              strokeDashoffset: indeterminate ? circumference * 0.75 : offset,
              transform: "rotate(-90deg)",
              transformOrigin: "50% 50%",
            }}
          />
        </svg>
        {showLabel && !indeterminate && (
          <span className="absolute text-sm font-medium text-charcoal dark:text-gray-200">
            {Math.round(clampedValue)}%
          </span>
        )}
      </div>
    )
  }
)
CircularProgress.displayName = "CircularProgress"

export { Progress, CircularProgress, progressVariants, progressBarVariants }
export type { ProgressProps, CircularProgressProps }

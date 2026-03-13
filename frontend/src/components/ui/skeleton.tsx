/**
 * Skeleton - Loading Placeholder Component
 * 
 * Animated placeholder for content loading states.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Skeleton shape */
  variant?: "text" | "circular" | "rectangular" | "rounded"
  /** Width (CSS value) */
  width?: string | number
  /** Height (CSS value) */
  height?: string | number
  /** Disable animation */
  static?: boolean
}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, variant = "text", width, height, static: isStatic, style, ...props }, ref) => {
    const variantClasses = {
      text: "rounded h-4",
      circular: "rounded-full",
      rectangular: "rounded-none",
      rounded: "rounded-xl",
    }

    return (
      <div
        ref={ref}
        className={cn(
          "bg-gray-200 dark:bg-dark-surface-2",
          !isStatic && "animate-pulse",
          variantClasses[variant],
          className
        )}
        style={{
          width: typeof width === "number" ? `${width}px` : width,
          height: typeof height === "number" ? `${height}px` : height,
          ...style,
        }}
        {...props}
      />
    )
  }
)
Skeleton.displayName = "Skeleton"

/* ============================================
   SKELETON PRESETS - Common loading patterns
   ============================================ */

/** Avatar skeleton */
const SkeletonAvatar: React.FC<{ size?: "sm" | "md" | "lg" }> = ({ size = "md" }) => {
  const sizes = { sm: 32, md: 40, lg: 48 }
  return <Skeleton variant="circular" width={sizes[size]} height={sizes[size]} />
}

/** Text line skeleton */
const SkeletonText: React.FC<{ lines?: number; lastLineWidth?: string }> = ({
  lines = 3,
  lastLineWidth = "60%",
}) => (
  <div className="space-y-2">
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton
        key={i}
        variant="text"
        width={i === lines - 1 ? lastLineWidth : "100%"}
      />
    ))}
  </div>
)

/** Card skeleton */
const SkeletonCard: React.FC<{ className?: string }> = ({ className }) => (
  <div
    className={cn(
      "p-6 rounded-2xl border border-gray-200 dark:border-dark-border/30",
      "bg-white dark:bg-dark-surface",
      className
    )}
  >
    <div className="flex items-center gap-3 mb-4">
      <SkeletonAvatar />
      <div className="flex-1 space-y-2">
        <Skeleton variant="text" width="40%" />
        <Skeleton variant="text" width="60%" height={12} />
      </div>
    </div>
    <SkeletonText lines={3} />
  </div>
)

/** Table row skeleton */
const SkeletonTableRow: React.FC<{ columns?: number }> = ({ columns = 4 }) => (
  <div className="flex items-center gap-4 py-3">
    {Array.from({ length: columns }).map((_, i) => (
      <Skeleton
        key={i}
        variant="text"
        className="flex-1"
        height={16}
      />
    ))}
  </div>
)

export {
  Skeleton,
  SkeletonAvatar,
  SkeletonText,
  SkeletonCard,
  SkeletonTableRow,
}
export type { SkeletonProps }

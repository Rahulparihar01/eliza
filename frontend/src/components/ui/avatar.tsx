/**
 * Avatar - User Profile Picture Component
 * 
 * Displays user avatar with image or initials fallback.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

const avatarVariants = cva(
  "relative inline-flex items-center justify-center rounded-full overflow-hidden bg-gray-200 dark:bg-dark-surface-2",
  {
    variants: {
      size: {
        xs: "w-6 h-6 text-xs",
        sm: "w-8 h-8 text-sm",
        md: "w-10 h-10 text-base",
        lg: "w-12 h-12 text-lg",
        xl: "w-16 h-16 text-xl",
        "2xl": "w-20 h-20 text-2xl",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
)

interface AvatarProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof avatarVariants> {
  /** Image source URL */
  src?: string | null
  /** Alt text for image */
  alt?: string
  /** Fallback text (usually initials) */
  fallback?: string
  /** Full name to generate initials from */
  name?: string
}

/** Generate initials from a name */
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase()
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** Returns charcoal background for all avatars */
function getColorFromString(_str: string): string {
  return "bg-charcoal"
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, size, src, alt, fallback, name, ...props }, ref) => {
    const [imgError, setImgError] = React.useState(false)

    const initials = fallback || (name ? getInitials(name) : "?")
    const bgColor = "bg-charcoal"
    const showImage = src && !imgError

    return (
      <div
        ref={ref}
        className={cn(
          avatarVariants({ size }),
          !showImage && bgColor,
          className
        )}
        {...props}
      >
        {showImage ? (
          <img
            src={src}
            alt={alt || name || "Avatar"}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <span className="font-medium text-white">{initials}</span>
        )}
      </div>
    )
  }
)
Avatar.displayName = "Avatar"

/* ============================================
   AVATAR GROUP - Stack of avatars
   ============================================ */

interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Maximum avatars to show before +N */
  max?: number
  /** Size of avatars */
  size?: VariantProps<typeof avatarVariants>["size"]
}

const AvatarGroup = React.forwardRef<HTMLDivElement, AvatarGroupProps>(
  ({ className, max = 4, size = "md", children, ...props }, ref) => {
    const childArray = React.Children.toArray(children)
    const excess = childArray.length - max

    return (
      <div
        ref={ref}
        className={cn("flex -space-x-2", className)}
        {...props}
      >
        {childArray.slice(0, max).map((child, index) => (
          <div
            key={index}
            className="ring-2 ring-white dark:ring-dark-bg rounded-full"
          >
            {React.isValidElement(child)
              ? React.cloneElement(child as React.ReactElement<AvatarProps>, { size })
              : child}
          </div>
        ))}
        {excess > 0 && (
          <div
            className={cn(
              avatarVariants({ size }),
              "bg-gray-300 dark:bg-dark-surface-2 ring-2 ring-white dark:ring-dark-bg"
            )}
          >
            <span className="font-medium text-gray-600 dark:text-gray-300">
              +{excess}
            </span>
          </div>
        )}
      </div>
    )
  }
)
AvatarGroup.displayName = "AvatarGroup"

export { Avatar, AvatarGroup, avatarVariants }
export type { AvatarProps, AvatarGroupProps }

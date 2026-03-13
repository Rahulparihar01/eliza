/**
 * Button Component - Editorial OS Design System
 * 
 * Based on shadcn/ui patterns with Eliza Platform customizations.
 * Uses class-variance-authority for variant management.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

const buttonVariants = cva(
  // Base styles
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // Primary - charcoal for main CTA
        default:
          "bg-charcoal text-white hover:bg-charcoal/90 focus-visible:ring-charcoal rounded-full shadow-sm dark:bg-white dark:text-charcoal dark:hover:bg-gray-100",
        // Brand - Eliza Red primary actions (main CTA)
        brand:
          "bg-eliza-red text-white hover:bg-eliza-red-light focus-visible:ring-eliza-red rounded-full shadow-sm",
        // Secondary - subtle actions
        secondary:
          "bg-white border border-gray-200 text-charcoal hover:bg-gray-50 hover:border-gray-300 focus-visible:ring-gray-400 rounded-full dark:bg-dark-surface dark:border-dark-border/50 dark:text-gray-200 dark:hover:bg-dark-surface-2",
        // Ghost - minimal footprint
        ghost:
          "text-charcoal hover:bg-gray-100 hover:text-charcoal focus-visible:ring-gray-400 rounded-lg dark:text-gray-300 dark:hover:bg-dark-surface-2",
        // Destructive outline - for dangerous actions
        destructive:
          "bg-white border border-eliza-red text-eliza-red hover:bg-red-50 focus-visible:ring-eliza-red rounded-full dark:bg-transparent dark:hover:bg-red-950/20",
        // Link - text-only style
        link:
          "text-eliza-red underline-offset-4 hover:underline focus-visible:ring-eliza-red",
        // Outline - bordered variant
        outline:
          "border border-gray-300 bg-transparent text-charcoal hover:bg-gray-50 focus-visible:ring-gray-400 rounded-full dark:border-dark-border/50 dark:text-gray-200 dark:hover:bg-dark-surface",
      },
      size: {
        default: "h-10 px-6 py-2",
        sm: "h-8 px-4 text-xs",
        lg: "h-12 px-8 text-base",
        xl: "h-14 px-10 text-lg",
        icon: "h-10 w-10 rounded-full",
        "icon-sm": "h-8 w-8 rounded-full",
        "icon-lg": "h-12 w-12 rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }

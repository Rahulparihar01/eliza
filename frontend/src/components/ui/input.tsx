/**
 * Input Component - Editorial OS Design System
 * 
 * Clean inputs with 12px radius and subtle borders.
 * 
 * Variants:
 * - default: Standard input with border
 * - ghost: Minimal input with transparent background and subtle bottom border
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

const inputVariants = cva(
  // Base styles
  [
    "flex w-full text-charcoal placeholder:text-gray-400 transition-colors duration-200",
    "focus:outline-none",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "file:border-0 file:bg-transparent file:text-sm file:font-medium",
    "dark:text-gray-100 dark:placeholder:text-gray-500",
  ],
  {
    variants: {
      variant: {
        default: [
          "h-10 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm",
          "focus:border-eliza-red/50 focus:ring-2 focus:ring-eliza-red/20",
          "disabled:bg-gray-50",
          "dark:bg-dark-surface dark:border-dark-border/50",
          "dark:focus:border-eliza-red-light/50 dark:focus:ring-eliza-red-light/20",
        ],
        ghost: [
          "h-auto bg-transparent border-0 border-b border-transparent px-0 py-1.5 text-sm",
          "hover:border-gray-200 dark:hover:border-dark-border/50",
          "focus:border-gray-300 dark:focus:border-dark-border",
          "placeholder:text-gray-400 dark:placeholder:text-gray-500",
        ],
        // Large ghost for titles
        "ghost-lg": [
          "h-auto bg-transparent border-0 border-b border-transparent px-0 py-1 text-xl font-semibold",
          "hover:border-gray-200 dark:hover:border-dark-border/50",
          "focus:border-gray-300 dark:focus:border-dark-border",
          "placeholder:text-gray-400 dark:placeholder:text-gray-500",
        ],
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement>,
    VariantProps<typeof inputVariants> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, variant, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(inputVariants({ variant }), className)}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input, inputVariants }

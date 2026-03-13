/**
 * Textarea Component - Editorial OS Design System
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex min-h-[80px] w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-charcoal placeholder:text-gray-400 transition-colors duration-200",
          "focus:border-eliza-red/50 focus:outline-none focus:ring-2 focus:ring-eliza-red/20",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-gray-50",
          "resize-none",
          "dark:bg-dark-surface dark:border-dark-border/50 dark:text-gray-100 dark:placeholder:text-gray-500",
          "dark:focus:border-eliza-red-light/50 dark:focus:ring-eliza-red-light/20",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }

/**
 * Label Component - Editorial OS Design System
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        "text-sm font-medium text-charcoal leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        "dark:text-gray-200",
        className
      )}
      {...props}
    />
  )
)
Label.displayName = "Label"

export { Label }

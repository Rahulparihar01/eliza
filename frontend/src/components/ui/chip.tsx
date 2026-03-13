/**
 * Chip - Toggleable Pill Component
 * 
 * A selectable chip/pill for feature allocation, tags, filters, etc.
 * Follows the Eliza Forge design system.
 * 
 * States:
 * - Default: Gray border, neutral text
 * - Active: Strong brand border & background (dropdown open, focused)
 * - Complete: Subtle brand border & background with checkmark (has value selected)
 */

import * as React from "react"
import { PlusIcon, XMarkIcon, CheckCircleIcon, ChevronDownIcon } from "@heroicons/react/24/outline"
import { CheckCircleIcon as CheckCircleSolidIcon } from "@heroicons/react/24/solid"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

/* ============================================
   CHIP VARIANTS
   ============================================ */

const chipVariants = cva(
  // Base styles
  [
    "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md",
    "text-xs font-medium transition-all duration-150",
    "cursor-pointer select-none",
    "focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-2",
  ],
  {
    variants: {
      variant: {
        // Default: subtle background, becomes primary when selected
        default: [
          "border",
          // Unselected
          "border-gray-300 bg-transparent text-charcoal",
          "hover:border-gray-400 hover:bg-gray-50",
          // Dark mode unselected
          "dark:border-dark-border/50 dark:text-gray-300",
          "dark:hover:border-dark-border dark:hover:bg-dark-surface-2",
        ],
        // Outline: similar but slightly different hover
        outline: [
          "border",
          "border-gray-200 bg-white text-charcoal",
          "hover:border-gray-300 hover:shadow-sm",
          "dark:border-dark-border/30 dark:bg-dark-surface dark:text-gray-300",
          "dark:hover:border-dark-border/50",
        ],
        // Ghost: no border until selected
        ghost: [
          "border border-transparent",
          "text-gray-600 bg-gray-100",
          "hover:bg-gray-200",
          "dark:text-gray-400 dark:bg-dark-surface-2",
          "dark:hover:bg-dark-border/50",
        ],
        // Pill: rounded-full variant for Linear-style UIs
        pill: [
          "border rounded-full px-4 py-2",
          "border-gray-200 bg-white text-charcoal",
          "hover:border-gray-300",
          "dark:border-dark-border/30 dark:bg-dark-surface dark:text-gray-300",
          "dark:hover:border-dark-border/50",
        ],
      },
      selected: {
        true: "",
        false: "",
      },
      active: {
        true: "",
        false: "",
      },
      complete: {
        true: "",
        false: "",
      },
    },
    compoundVariants: [
      // Default variant - selected state (legacy, maps to red)
      {
        variant: "default",
        selected: true,
        className: [
          "border-eliza-red/50 bg-eliza-red/10 text-eliza-red",
          "hover:border-eliza-red/60 hover:bg-eliza-red/15",
          "dark:border-eliza-red/40 dark:bg-eliza-red/20 dark:text-white",
          "dark:hover:border-eliza-red/50 dark:hover:bg-eliza-red/25",
        ],
      },
      // Outline variant - selected state
      {
        variant: "outline",
        selected: true,
        className: [
          "border-eliza-red/50 bg-eliza-red/5 text-eliza-red shadow-sm",
          "hover:border-eliza-red/60 hover:bg-eliza-red/10",
          "dark:border-eliza-red/40 dark:bg-eliza-red/15 dark:text-white",
          "dark:hover:border-eliza-red/50",
        ],
      },
      // Ghost variant - selected state
      {
        variant: "ghost",
        selected: true,
        className: [
          "border-eliza-red/30 bg-eliza-red/10 text-eliza-red",
          "hover:bg-eliza-red/15",
          "dark:border-eliza-red/30 dark:bg-eliza-red/20 dark:text-white",
        ],
      },
      // Pill variant - selected state
      {
        variant: "pill",
        selected: true,
        className: [
          "border-eliza-red/50 bg-eliza-red/10 text-eliza-red",
          "hover:border-eliza-red/60 hover:bg-eliza-red/15",
          "dark:border-eliza-red/40 dark:bg-eliza-red/20 dark:text-white",
        ],
      },
      // Active state (dropdown open) - all variants - takes priority over default but not complete
      {
        variant: "default",
        active: true,
        complete: false,
        className: [
          "border-eliza-red bg-eliza-red/10 text-eliza-red",
          "dark:border-eliza-red dark:bg-eliza-red/20 dark:text-white",
        ],
      },
      {
        variant: "outline",
        active: true,
        complete: false,
        className: [
          "border-eliza-red bg-eliza-red/10 text-eliza-red",
          "dark:border-eliza-red dark:bg-eliza-red/20 dark:text-white",
        ],
      },
      {
        variant: "pill",
        active: true,
        complete: false,
        className: [
          "border-eliza-red bg-eliza-red/10 text-eliza-red",
          "dark:border-eliza-red dark:bg-eliza-red/20 dark:text-white",
        ],
      },
      // Complete state (has value) - subtle brand styling
      {
        variant: "default",
        complete: true,
        className: [
          "border-eliza-red/30 bg-eliza-red/5 text-eliza-red",
          "hover:border-eliza-red/40 hover:bg-eliza-red/10",
          "dark:border-eliza-red/30 dark:bg-eliza-red/10 dark:text-white",
          "dark:hover:border-eliza-red/40 dark:hover:bg-eliza-red/15",
        ],
      },
      {
        variant: "outline",
        complete: true,
        className: [
          "border-eliza-red/30 bg-eliza-red/5 text-eliza-red",
          "hover:border-eliza-red/40 hover:bg-eliza-red/10",
          "dark:border-eliza-red/30 dark:bg-eliza-red/10 dark:text-white",
        ],
      },
      {
        variant: "pill",
        complete: true,
        className: [
          "border-eliza-red/30 bg-eliza-red/5 text-eliza-red",
          "hover:border-eliza-red/40 hover:bg-eliza-red/10",
          "dark:border-eliza-red/30 dark:bg-eliza-red/10 dark:text-white",
        ],
      },
    ],
    defaultVariants: {
      variant: "default",
      selected: false,
      active: false,
      complete: false,
    },
  }
)

/* ============================================
   CHIP COMPONENT
   ============================================ */

interface ChipProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onChange">,
    VariantProps<typeof chipVariants> {
  /** Whether the chip is selected (legacy - maps to red state) */
  selected?: boolean
  /** Whether the chip is in active/focused state (dropdown open) */
  active?: boolean
  /** Whether the chip has a complete state (has value selected - subtle brand) */
  complete?: boolean
  /** Callback when chip is toggled */
  onToggle?: (selected: boolean) => void
  /** Show icon indicator */
  showIcon?: boolean
  /** Icon position */
  iconPosition?: "left" | "right"
  /** Custom icon when not selected/complete */
  unselectedIcon?: React.ReactNode
  /** Custom icon when selected */
  selectedIcon?: React.ReactNode
  /** Custom icon when complete (defaults to checkmark) */
  completeIcon?: React.ReactNode
  /** Show dropdown chevron */
  showChevron?: boolean
  /** Truncate label with max width */
  maxLabelWidth?: number
}

const Chip = React.forwardRef<HTMLButtonElement, ChipProps>(
  (
    {
      className,
      variant = "default",
      selected = false,
      active = false,
      complete = false,
      onToggle,
      showIcon = true,
      iconPosition = "left",
      unselectedIcon,
      selectedIcon,
      completeIcon,
      showChevron = false,
      maxLabelWidth,
      children,
      onClick,
      ...props
    },
    ref
  ) => {
    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      onToggle?.(!selected)
      onClick?.(e)
    }

    const defaultUnselectedIcon = <PlusIcon className="w-3.5 h-3.5" />
    const defaultSelectedIcon = <XMarkIcon className="w-3.5 h-3.5" />
    const defaultCompleteIcon = <CheckCircleSolidIcon className="w-3.5 h-3.5" />

    // Determine which icon to show based on state
    const icon = complete
      ? (completeIcon ?? defaultCompleteIcon)
      : selected
        ? (selectedIcon ?? defaultSelectedIcon)
        : (unselectedIcon ?? defaultUnselectedIcon)

    return (
      <button
        ref={ref}
        type="button"
        role="checkbox"
        aria-checked={selected || complete}
        aria-expanded={active}
        className={cn(chipVariants({ variant, selected, active, complete }), className)}
        onClick={handleClick}
        {...props}
      >
        {showIcon && iconPosition === "left" && icon}
        <span 
          className={cn("truncate", maxLabelWidth && `max-w-[${maxLabelWidth}px]`)}
          style={maxLabelWidth ? { maxWidth: maxLabelWidth } : undefined}
        >
          {children}
        </span>
        {showIcon && iconPosition === "right" && icon}
        {showChevron && (
          <ChevronDownIcon 
            className={cn(
              "w-3 h-3 transition-transform",
              active && "rotate-180"
            )} 
          />
        )}
      </button>
    )
  }
)
Chip.displayName = "Chip"

/* ============================================
   CHIP GROUP - Container for multiple chips
   ============================================ */

interface ChipGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Label for the group */
  label?: string
}

const ChipGroup = React.forwardRef<HTMLDivElement, ChipGroupProps>(
  ({ className, label, children, ...props }, ref) => (
    <div ref={ref} className={cn("space-y-3", className)} {...props}>
      {label && (
        <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {label}
        </h4>
      )}
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  )
)
ChipGroup.displayName = "ChipGroup"

export { Chip, ChipGroup, chipVariants }
export type { ChipProps, ChipGroupProps }

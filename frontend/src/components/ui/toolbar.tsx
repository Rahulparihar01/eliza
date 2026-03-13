/**
 * Toolbar - Top Application Bar Component
 * 
 * A consistent top toolbar that contains the tenant switcher
 * and other global actions.
 * 
 * Features:
 * - Multi-tenant switcher as first element
 * - Right-side actions (theme, notifications, user menu)
 * - Consistent height and styling
 * 
 * Note: This is a layout component. The tenant switcher itself
 * uses DS primitives (Button, DropdownMenu, etc.)
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"
import { Button } from "./button"
import { Tooltip } from "./tooltip"

/* ============================================
   Types
   ============================================ */

interface ToolbarProps extends React.HTMLAttributes<HTMLElement> {
  /** Content for the left section (e.g., tenant switcher - first element) */
  leftContent?: React.ReactNode
  /** Content for the center section (optional) */
  centerContent?: React.ReactNode
  /** Content for the right section (e.g., theme toggle, notifications, user menu) */
  rightContent?: React.ReactNode
  /** Whether the toolbar is sticky */
  sticky?: boolean
}

interface ToolbarSectionProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Alignment: 'left', 'center', or 'right' */
  align?: 'left' | 'center' | 'right'
}

interface ToolbarDividerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Orientation: 'vertical' (default) or 'horizontal' */
  orientation?: 'vertical' | 'horizontal'
}

interface ToolbarItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Icon to display */
  icon?: React.ReactNode
  /** Whether this is the active item */
  isActive?: boolean
  /** Show as a badge with count */
  badge?: number | string
  /** Tooltip text */
  tooltip?: string
}

/* ============================================
   Toolbar Container
   ============================================ */

const Toolbar = React.forwardRef<HTMLElement, ToolbarProps>(
  ({ className, leftContent, centerContent, rightContent, sticky = true, children, ...props }, ref) => {
    return (
      <header
        ref={ref}
        className={cn(
          "h-12 flex items-center justify-between px-4",
          "bg-white dark:bg-dark-surface border-b border-gray-200 dark:border-dark-border/30",
          sticky && "sticky top-0 z-40",
          className
        )}
        {...props}
      >
        {/* Left section - Tenant switcher (first element) */}
        <div className="flex items-center gap-4">
          {leftContent}
        </div>

        {/* Center content (optional) */}
        {(centerContent || children) && (
          <div className="flex-1 flex items-center justify-center">
            {centerContent || children}
          </div>
        )}

        {/* Spacer if no center content */}
        {!centerContent && !children && <div className="flex-1" />}

        {/* Right section */}
        <div className="flex items-center gap-2">
          {rightContent}
        </div>
      </header>
    )
  }
)
Toolbar.displayName = "Toolbar"

/* ============================================
   Toolbar Section (for grouping items)
   ============================================ */

const ToolbarSection = React.forwardRef<HTMLDivElement, ToolbarSectionProps>(
  ({ className, align = 'left', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center gap-2",
          align === 'center' && "justify-center",
          align === 'right' && "justify-end",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
ToolbarSection.displayName = "ToolbarSection"

/* ============================================
   Toolbar Divider
   ============================================ */

const ToolbarDivider = React.forwardRef<HTMLDivElement, ToolbarDividerProps>(
  ({ className, orientation = 'vertical', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "bg-border",
          orientation === 'vertical' ? "w-px h-6 mx-2" : "h-px w-full my-2",
          className
        )}
        {...props}
      />
    )
  }
)
ToolbarDivider.displayName = "ToolbarDivider"

/* ============================================
   Toolbar Item (Icon button using DS Button)
   ============================================ */

const ToolbarItem = React.forwardRef<HTMLButtonElement, ToolbarItemProps>(
  ({ className, icon, isActive, badge, tooltip, children, ...props }, ref) => {
    const buttonElement = (
      <div className="relative">
        <Button
          ref={ref}
          variant="ghost"
          size="sm"
          className={cn(
            "relative p-2 h-auto",
            isActive && "text-eliza-red bg-eliza-red/10",
            className
          )}
          {...props}
        >
          {icon}
          {children}
        </Button>
        
        {/* Badge */}
        {badge !== undefined && badge !== 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-eliza-red text-white text-[10px] font-semibold rounded-full flex items-center justify-center pointer-events-none">
            {typeof badge === 'number' && badge > 99 ? '99+' : badge}
          </span>
        )}
      </div>
    )

    if (tooltip) {
      return (
        <Tooltip content={tooltip} position="bottom">
          {buttonElement}
        </Tooltip>
      )
    }

    return buttonElement
  }
)
ToolbarItem.displayName = "ToolbarItem"

/* ============================================
   Toolbar Text Button (using DS Button)
   ============================================ */

interface ToolbarTextButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode
}

const ToolbarTextButton = React.forwardRef<HTMLButtonElement, ToolbarTextButtonProps>(
  ({ className, icon, children, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="ghost"
        size="sm"
        className={cn(
          "gap-2 text-xs font-medium",
          className
        )}
        {...props}
      >
        {icon}
        {children}
      </Button>
    )
  }
)
ToolbarTextButton.displayName = "ToolbarTextButton"

/* ============================================
   Exports
   ============================================ */

export {
  Toolbar,
  ToolbarSection,
  ToolbarDivider,
  ToolbarItem,
  ToolbarTextButton,
}

export type {
  ToolbarProps,
  ToolbarSectionProps,
  ToolbarItemProps,
}

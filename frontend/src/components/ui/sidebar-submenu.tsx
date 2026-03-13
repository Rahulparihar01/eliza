/**
 * SidebarSubmenu - Simple Submenu Sidebar
 * 
 * A sidebar variant for contextual/workspace navigation within sub-apps.
 * Features a simple back button to return to main navigation.
 * Non-collapsible by design - keeps the UI simple.
 * 
 * Features:
 * - Back button header (matches toolbar height)
 * - Section title
 * - Simple list navigation items
 * - Footer with version
 * - Keyboard support (Escape to go back)
 */

import * as React from "react"
import { NavLink } from "react-router-dom"
import { ArrowLeftIcon, Bars3Icon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"
import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarSection,
  SidebarFooter,
} from "./sidebar"

/* ============================================
   Types
   ============================================ */

export interface SubmenuItem {
  /** Display label */
  label: string
  /** Navigation path */
  path: string
  /** Optional icon */
  icon?: React.ComponentType<{ className?: string }>
  /** Optional badge (count or text) */
  badge?: string | number
  /** Whether the item is disabled */
  disabled?: boolean
  /** Whether the item is coming soon (shows disabled with "Coming Soon" badge) */
  comingSoon?: boolean
  /** Section header (renders as a header instead of a link) */
  sectionHeader?: boolean
  /** Required permissions - user needs ANY of these to see the item */
  requiredPermissions?: string[]
}

interface SidebarSubmenuProps {
  /** Section title displayed below the header */
  title: string
  /** Navigation items */
  items: SubmenuItem[]
  /** Callback when back button is clicked */
  onBack: () => void
  /** Whether the submenu is visible */
  isVisible: boolean
  /** Callback when hamburger menu is clicked (toggle sidebar) */
  onToggle?: () => void
  /** Additional className */
  className?: string
  /** Show footer with version */
  showFooter?: boolean
}

interface SubmenuNavItemProps extends React.HTMLAttributes<HTMLElement> {
  /** Item configuration */
  item: SubmenuItem
}

/* ============================================
   SubmenuNavItem - Navigation Link
   ============================================ */

const SubmenuNavItem = React.forwardRef<HTMLAnchorElement, SubmenuNavItemProps>(
  ({ className, item, ...props }, ref) => {
    const ItemIcon = item.icon

    // Disabled state
    if (item.disabled) {
      return (
        <div
          className={cn(
            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm",
            "text-gray-400 dark:text-gray-500 cursor-not-allowed",
            className
          )}
          {...props}
        >
          {ItemIcon && <ItemIcon className="w-5 h-5 flex-shrink-0" />}
          <span className="flex-1 truncate">{item.label}</span>
          {item.badge && (
            <span className="text-xs bg-gray-100 dark:bg-dark-surface-2 px-1.5 py-0.5 rounded">
              {item.badge}
            </span>
          )}
        </div>
      )
    }

    // Active link
    return (
      <NavLink
        ref={ref}
        to={item.path}
        end={item.path.split('/').length <= 4}
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium",
            "transition-colors duration-150",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
            isActive
              ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20"
              : "text-charcoal dark:text-gray-300",
            className
          )
        }
        {...props}
      >
        {({ isActive }) => (
          <>
            {ItemIcon && (
              <ItemIcon
                className={cn(
                  "w-5 h-5 flex-shrink-0",
                  isActive ? "text-eliza-red" : "text-gray-500 dark:text-gray-400"
                )}
              />
            )}
            <span className="flex-1 truncate">{item.label}</span>
            {item.badge && (
              <span
                className={cn(
                  "flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold",
                  "bg-eliza-red text-white"
                )}
              >
                {item.badge}
              </span>
            )}
          </>
        )}
      </NavLink>
    )
  }
)
SubmenuNavItem.displayName = "SubmenuNavItem"

/* ============================================
   SidebarSubmenu - Complete Component
   ============================================ */

export function SidebarSubmenu({
  title,
  items,
  onBack,
  isVisible,
  onToggle,
  className,
  showFooter = true,
}: SidebarSubmenuProps) {
  // Handle escape key to close
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isVisible) {
        onBack()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isVisible, onBack])

  return (
    <Sidebar
      mode={isVisible ? 'expanded' : 'hidden'}
      expandedWidth={240}
      className={cn(
        "relative !w-full !min-w-full",
        // Slide in from right when appearing (drilling in)
        !isVisible && "!translate-x-4",
        className
      )}
    >
      {/* Header with Hamburger Menu - matches toolbar height (h-12) */}
      <SidebarHeader className={cn(
        "h-12 px-3",
        "flex items-center"
      )}>
        <button
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onToggle?.()
          }}
          className={cn(
            "flex items-center justify-center w-8 h-8 rounded-lg",
            "text-gray-600 dark:text-gray-300",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
            "transition-colors duration-150",
            "focus:outline-none focus:ring-2 focus:ring-eliza-red focus:ring-offset-1"
          )}
          title="Toggle sidebar"
          aria-label="Toggle sidebar"
        >
          <Bars3Icon className="w-5 h-5" />
        </button>
      </SidebarHeader>

      {/* Navigation Content */}
      <SidebarContent>
        {/* Back Button - first item below header */}
        <div className="px-3 mb-2">
          <button
            onClick={onBack}
            className={cn(
              "flex items-center gap-2 w-full px-2 py-2 rounded-lg",
              "text-gray-600 dark:text-gray-300",
              "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
              "transition-colors duration-150",
              "focus:outline-none focus:ring-2 focus:ring-eliza-red focus:ring-offset-1"
            )}
            title="Go back to main menu"
            aria-label="Go back to main menu"
          >
            <ArrowLeftIcon className="w-4 h-4" />
            <span className="text-sm font-medium">Back</span>
          </button>
        </div>

        <SidebarSection title={title.toUpperCase()}>
          {items.map((item) => (
            <SubmenuNavItem key={item.path} item={item} />
          ))}
        </SidebarSection>
      </SidebarContent>

      {/* Footer */}
      {showFooter && (
        <SidebarFooter className="border-t border-gray-100 dark:border-dark-border/30">
          <div className="flex items-center gap-1.5 px-1 text-[10px] text-gray-400 dark:text-gray-500">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full flex-shrink-0" />
            Eliza Forge v1.0
          </div>
        </SidebarFooter>
      )}
    </Sidebar>
  )
}

/* ============================================
   Exports
   ============================================ */

export { SubmenuNavItem }
export type { SidebarSubmenuProps, SubmenuNavItemProps }

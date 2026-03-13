/**
 * Breadcrumb - Navigation Trail Component
 * 
 * Shows the user's current location in the app hierarchy.
 */

import * as React from "react"
import { ChevronRightIcon, HomeIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   BREADCRUMB CONTAINER
   ============================================ */

interface BreadcrumbProps extends React.HTMLAttributes<HTMLElement> {
  /** Separator between items */
  separator?: React.ReactNode
  /** Show home icon as first item */
  showHome?: boolean
  /** Home href */
  homeHref?: string
}

const Breadcrumb = React.forwardRef<HTMLElement, BreadcrumbProps>(
  ({ className, separator, showHome = false, homeHref = "/", children, ...props }, ref) => {
    const items = React.Children.toArray(children)
    
    return (
      <nav
        ref={ref}
        aria-label="Breadcrumb"
        className={cn("flex items-center", className)}
        {...props}
      >
        <ol className="flex items-center gap-1.5">
          {showHome && (
            <>
              <li>
                <a
                  href={homeHref}
                  className={cn(
                    "flex items-center justify-center w-6 h-6 rounded",
                    "text-gray-400 hover:text-gray-600",
                    "dark:text-gray-500 dark:hover:text-gray-300",
                    "transition-colors"
                  )}
                >
                  <HomeIcon className="w-4 h-4" />
                </a>
              </li>
              <li aria-hidden="true" className="text-gray-300 dark:text-gray-600">
                {separator || <ChevronRightIcon className="w-4 h-4" />}
              </li>
            </>
          )}
          {items.map((child, index) => (
            <React.Fragment key={index}>
              <li className="flex items-center">{child}</li>
              {index < items.length - 1 && (
                <li aria-hidden="true" className="text-gray-300 dark:text-gray-600">
                  {separator || <ChevronRightIcon className="w-4 h-4" />}
                </li>
              )}
            </React.Fragment>
          ))}
        </ol>
      </nav>
    )
  }
)
Breadcrumb.displayName = "Breadcrumb"

/* ============================================
   BREADCRUMB ITEM
   ============================================ */

interface BreadcrumbItemProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Link href (omit for current page) */
  href?: string
  /** Is this the current/active page */
  isCurrent?: boolean
  /** Custom icon */
  icon?: React.ReactNode
}

const BreadcrumbItem = React.forwardRef<HTMLSpanElement, BreadcrumbItemProps>(
  ({ className, href, isCurrent = false, icon, children, ...props }, ref) => {
    const content = (
      <>
        {icon && <span className="mr-1.5">{icon}</span>}
        {children}
      </>
    )

    if (href && !isCurrent) {
      return (
        <span ref={ref} {...props}>
          <a
            href={href}
            className={cn(
              "flex items-center text-sm font-medium",
              "text-gray-500 hover:text-gray-700",
              "dark:text-gray-400 dark:hover:text-gray-200",
              "transition-colors",
              className
            )}
          >
            {content}
          </a>
        </span>
      )
    }

    return (
      <span
        ref={ref}
        aria-current={isCurrent ? "page" : undefined}
        className={cn(
          "flex items-center text-sm font-medium",
          isCurrent
            ? "text-charcoal dark:text-white"
            : "text-gray-500 dark:text-gray-400",
          className
        )}
        {...props}
      >
        {content}
      </span>
    )
  }
)
BreadcrumbItem.displayName = "BreadcrumbItem"

/* ============================================
   BREADCRUMB ELLIPSIS (for collapsed items)
   ============================================ */

interface BreadcrumbEllipsisProps extends React.HTMLAttributes<HTMLSpanElement> {}

const BreadcrumbEllipsis = React.forwardRef<HTMLSpanElement, BreadcrumbEllipsisProps>(
  ({ className, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          "flex items-center justify-center w-6 h-6",
          "text-gray-400 dark:text-gray-500",
          "cursor-default",
          className
        )}
        {...props}
      >
        <span className="tracking-widest">...</span>
      </span>
    )
  }
)
BreadcrumbEllipsis.displayName = "BreadcrumbEllipsis"

/* ============================================
   EXPORTS
   ============================================ */

export { Breadcrumb, BreadcrumbItem, BreadcrumbEllipsis }
export type { BreadcrumbProps, BreadcrumbItemProps, BreadcrumbEllipsisProps }

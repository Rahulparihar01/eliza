/**
 * Pagination - Page Navigation Component
 * 
 * Navigate through paginated content.
 */

import * as React from "react"
import { ChevronLeftIcon, ChevronRightIcon, ChevronDoubleLeftIcon, ChevronDoubleRightIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   PAGINATION
   ============================================ */

interface PaginationProps extends React.HTMLAttributes<HTMLElement> {
  /** Current page (1-indexed) */
  page: number
  /** Total number of pages */
  totalPages: number
  /** Callback when page changes */
  onPageChange: (page: number) => void
  /** Number of page buttons to show */
  siblingCount?: number
  /** Show first/last buttons */
  showFirstLast?: boolean
  /** Show previous/next buttons */
  showPrevNext?: boolean
  /** Size variant */
  size?: "sm" | "md" | "lg"
}

const Pagination = React.forwardRef<HTMLElement, PaginationProps>(
  ({ 
    className, 
    page, 
    totalPages, 
    onPageChange, 
    siblingCount = 1,
    showFirstLast = true,
    showPrevNext = true,
    size = "md",
    ...props 
  }, ref) => {
    // Generate page numbers to display
    const getPageNumbers = () => {
      const pages: (number | 'ellipsis')[] = []
      
      // Always show first page
      pages.push(1)
      
      // Calculate range around current page
      const leftSibling = Math.max(2, page - siblingCount)
      const rightSibling = Math.min(totalPages - 1, page + siblingCount)
      
      // Add ellipsis after first page if needed
      if (leftSibling > 2) {
        pages.push('ellipsis')
      }
      
      // Add pages around current
      for (let i = leftSibling; i <= rightSibling; i++) {
        if (i !== 1 && i !== totalPages) {
          pages.push(i)
        }
      }
      
      // Add ellipsis before last page if needed
      if (rightSibling < totalPages - 1) {
        pages.push('ellipsis')
      }
      
      // Always show last page if more than 1 page
      if (totalPages > 1) {
        pages.push(totalPages)
      }
      
      return pages
    }

    const pages = getPageNumbers()
    
    const sizeClasses = {
      sm: "h-7 w-7 text-xs rounded-full",
      md: "h-9 w-9 text-sm rounded-full",
      lg: "h-11 w-11 text-base rounded-full",
    }

    const iconSizes = {
      sm: "w-3 h-3",
      md: "w-4 h-4",
      lg: "w-5 h-5",
    }

    return (
      <nav
        ref={ref}
        aria-label="Pagination"
        className={cn("flex items-center gap-1", className)}
        {...props}
      >
        {/* First page button */}
        {showFirstLast && (
          <button
            onClick={() => onPageChange(1)}
            disabled={page === 1}
            className={cn(
              "flex items-center justify-center",
              "border border-gray-200 dark:border-dark-border/50",
              "bg-white dark:bg-dark-surface",
              "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-dark-surface",
              "text-gray-500 dark:text-gray-400",
              "transition-colors",
              sizeClasses[size]
            )}
            aria-label="First page"
          >
            <ChevronDoubleLeftIcon className={iconSizes[size]} />
          </button>
        )}

        {/* Previous page button */}
        {showPrevNext && (
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            className={cn(
              "flex items-center justify-center",
              "border border-gray-200 dark:border-dark-border/50",
              "bg-white dark:bg-dark-surface",
              "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-dark-surface",
              "text-gray-500 dark:text-gray-400",
              "transition-colors",
              sizeClasses[size]
            )}
            aria-label="Previous page"
          >
            <ChevronLeftIcon className={iconSizes[size]} />
          </button>
        )}

        {/* Page numbers */}
        {pages.map((p, index) => (
          p === 'ellipsis' ? (
            <span
              key={`ellipsis-${index}`}
              className={cn(
                "flex items-center justify-center",
                "text-gray-400 dark:text-gray-500",
                sizeClasses[size]
              )}
            >
              ...
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              aria-current={page === p ? "page" : undefined}
              className={cn(
                "flex items-center justify-center font-medium",
                "transition-colors",
                sizeClasses[size],
                page === p
                  ? "bg-eliza-red text-white border border-eliza-red"
                  : "border border-gray-200 dark:border-dark-border/50 bg-white dark:bg-dark-surface hover:bg-gray-50 dark:hover:bg-dark-surface-2 text-gray-700 dark:text-gray-300"
              )}
            >
              {p}
            </button>
          )
        ))}

        {/* Next page button */}
        {showPrevNext && (
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page === totalPages}
            className={cn(
              "flex items-center justify-center",
              "border border-gray-200 dark:border-dark-border/50",
              "bg-white dark:bg-dark-surface",
              "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-dark-surface",
              "text-gray-500 dark:text-gray-400",
              "transition-colors",
              sizeClasses[size]
            )}
            aria-label="Next page"
          >
            <ChevronRightIcon className={iconSizes[size]} />
          </button>
        )}

        {/* Last page button */}
        {showFirstLast && (
          <button
            onClick={() => onPageChange(totalPages)}
            disabled={page === totalPages}
            className={cn(
              "flex items-center justify-center",
              "border border-gray-200 dark:border-dark-border/50",
              "bg-white dark:bg-dark-surface",
              "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-dark-surface",
              "text-gray-500 dark:text-gray-400",
              "transition-colors",
              sizeClasses[size]
            )}
            aria-label="Last page"
          >
            <ChevronDoubleRightIcon className={iconSizes[size]} />
          </button>
        )}
      </nav>
    )
  }
)
Pagination.displayName = "Pagination"

/* ============================================
   SIMPLE PAGINATION (Prev/Next only)
   ============================================ */

interface SimplePaginationProps extends React.HTMLAttributes<HTMLElement> {
  /** Current page (1-indexed) */
  page: number
  /** Total number of pages */
  totalPages: number
  /** Callback when page changes */
  onPageChange: (page: number) => void
  /** Show page info text */
  showPageInfo?: boolean
}

const SimplePagination = React.forwardRef<HTMLElement, SimplePaginationProps>(
  ({ className, page, totalPages, onPageChange, showPageInfo = true, ...props }, ref) => {
    return (
      <nav
        ref={ref}
        aria-label="Pagination"
        className={cn("flex items-center justify-between gap-4", className)}
        {...props}
      >
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1}
          className={cn(
            "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium",
            "border border-gray-200 dark:border-dark-border/50",
            "bg-white dark:bg-dark-surface",
            "text-gray-600 dark:text-gray-300",
            "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-colors"
          )}
        >
          <ChevronLeftIcon className="w-4 h-4" />
          Previous
        </button>

        {showPageInfo && (
          <span className="text-sm text-gray-500 dark:text-gray-400">
            Page {page} of {totalPages}
          </span>
        )}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page === totalPages}
          className={cn(
            "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium",
            "border border-gray-200 dark:border-dark-border/50",
            "bg-white dark:bg-dark-surface",
            "text-gray-600 dark:text-gray-300",
            "hover:bg-gray-50 dark:hover:bg-dark-surface-2",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "transition-colors"
          )}
        >
          Next
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </nav>
    )
  }
)
SimplePagination.displayName = "SimplePagination"

/* ============================================
   EXPORTS
   ============================================ */

export { Pagination, SimplePagination }
export type { PaginationProps, SimplePaginationProps }

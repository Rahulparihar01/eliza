/**
 * InlineCitation - Clickable Citation Badge Component
 * 
 * A small, interactive badge that displays a citation number.
 * When clicked, opens the source PDF in the CanvasPanel.
 * 
 * Part of the Eliza Forge Design System.
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"
import { Tooltip } from "./tooltip"

/* ============================================
   INLINE CITATION
   ============================================ */

export interface InlineCitationProps extends React.HTMLAttributes<HTMLButtonElement> {
  /** Citation number (e.g., 1, 2, 3) */
  number: number
  /** Document ID for PDF loading */
  docId?: string
  /** Page number or range (e.g., "168" or "168-170") */
  pageNumber?: string
  /** Text to highlight in PDF */
  highlightText?: string
  /** Section/title for the source */
  sectionTitle?: string
  /** Custom tooltip text (defaults to "Source [number]") */
  tooltip?: string
  /** Size variant */
  size?: "sm" | "md"
  /** Whether the citation is interactive (clickable) */
  interactive?: boolean
  /** Callback when clicked */
  onClick?: () => void
}

const InlineCitation = React.forwardRef<HTMLButtonElement, InlineCitationProps>(
  (
    {
      className,
      number,
      docId,
      pageNumber,
      highlightText,
      sectionTitle,
      tooltip,
      size = "sm",
      interactive = true,
      onClick,
      ...props
    },
    ref
  ) => {
    // Build tooltip content
    const tooltipContent = React.useMemo(() => {
      if (tooltip) return tooltip
      
      const parts: string[] = [`Source ${number}`]
      if (docId) parts.push(`Doc ${docId}`)
      if (pageNumber) parts.push(`Page ${pageNumber}`)
      if (sectionTitle) parts.push(sectionTitle.length > 50 ? sectionTitle.slice(0, 50) + "..." : sectionTitle)
      
      return parts.join(" • ")
    }, [tooltip, number, docId, pageNumber, sectionTitle])

    const sizeClasses = {
      sm: "min-w-[1.25rem] h-5 px-1 text-[10px]",
      md: "min-w-[1.5rem] h-6 px-1.5 text-xs",
    }

    const badge = (
      <button
        ref={ref}
        type="button"
        onClick={interactive ? onClick : undefined}
        disabled={!interactive}
        className={cn(
          // Base styles
          "inline-flex items-center justify-center font-bold rounded-full mx-0.5 align-middle",
          "transition-all duration-150",
          // Size
          sizeClasses[size],
          // Light mode - subtle gray
          "bg-gray-200 text-gray-600 border border-gray-300",
          // Dark mode
          "dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600",
          // Interactive states
          interactive && [
            "cursor-pointer",
            "hover:bg-gray-300 hover:border-gray-400 hover:text-gray-700",
            "dark:hover:bg-gray-600 dark:hover:border-gray-500 dark:hover:text-gray-200",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-1",
            "active:scale-95",
          ],
          // Non-interactive
          !interactive && "cursor-default",
          className
        )}
        aria-label={`Citation ${number}${docId ? `, Document ${docId}` : ""}`}
        {...props}
      >
        {number}
      </button>
    )

    // Wrap with tooltip if interactive
    if (interactive) {
      return (
        <Tooltip content={tooltipContent} position="top">
          {badge}
        </Tooltip>
      )
    }

    return badge
  }
)
InlineCitation.displayName = "InlineCitation"

/* ============================================
   CITATION GROUP (for multiple inline citations)
   ============================================ */

export interface CitationGroupProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode
}

/**
 * CitationGroup - Wrapper for multiple adjacent citations
 * Provides proper spacing and alignment
 */
const CitationGroup = React.forwardRef<HTMLSpanElement, CitationGroupProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center gap-0.5",
          className
        )}
        {...props}
      >
        {children}
      </span>
    )
  }
)
CitationGroup.displayName = "CitationGroup"

export { InlineCitation, CitationGroup }

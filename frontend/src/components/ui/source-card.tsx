/**
 * SourceCard - Individual Source Display Component
 * 
 * Displays a single source with full metadata including:
 * - Citation index badge
 * - Document ID, page range, chunk ID badges
 * - Section title/path
 * - Show PDF and Validate Citation action buttons
 * - Validation results display
 * 
 * Part of the Eliza Forge Design System.
 */

import * as React from "react"
import { DocumentTextIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"
import { Button } from "./button"
import { Badge } from "./badge"
import { Spinner } from "./spinner"

/* ============================================
   TYPES
   ============================================ */

export type CitationVerdict = "pass" | "fail" | "unsure" | "error" | "unavailable" | string

export interface CitationValidationResult {
  verdict: CitationVerdict
  score?: number | null
  method?: string
  evidence?: string | null
  reason?: string | null
}

export interface CitationValidationState {
  status: "idle" | "loading" | "success" | "error"
  result?: CitationValidationResult
  error?: string
}

/* ============================================
   SOURCE CARD
   ============================================ */

export interface SourceCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Source index number */
  index: number
  /** Document ID */
  docId?: string
  /** Page range (e.g., "168-168" or "259-260") */
  pages?: string
  /** Chunk ID (will be truncated to 8 chars) */
  chunkId?: string
  /** Section title/path */
  sectionTitle?: string
  /** Callback for Show PDF button */
  onShowPdf?: () => void
  /** Callback for Validate Citation button */
  onValidate?: () => void
  /** Current validation state */
  validationState?: CitationValidationState
  /** Whether Show PDF button should be shown */
  showPdfButton?: boolean
  /** Whether Validate button should be shown */
  showValidateButton?: boolean
}

const SourceCard = React.forwardRef<HTMLDivElement, SourceCardProps>(
  (
    {
      className,
      index,
      docId,
      pages,
      chunkId,
      sectionTitle,
      onShowPdf,
      onValidate,
      validationState,
      showPdfButton = true,
      showValidateButton = true,
      ...props
    },
    ref
  ) => {
    const truncatedChunkId = chunkId?.slice(0, 8)
    const isValidating = validationState?.status === "loading"
    const hasValidation = validationState?.status === "success"
    const validationError = validationState?.status === "error"

    const verdict = validationState?.result?.verdict
    const score = validationState?.result?.score
    const reason = validationState?.result?.reason
    const evidence = validationState?.result?.evidence

    return (
      <div
        ref={ref}
        className={cn(
          // Container
          "flex items-start gap-3 p-4 rounded-xl border",
          // Light mode
          "bg-white border-gray-200",
          // Dark mode
          "dark:bg-dark-surface dark:border-dark-border",
          // Hover
          "hover:shadow-sm transition-all",
          className
        )}
        {...props}
      >
        {/* Index Badge */}
        <span className={cn(
          "flex-shrink-0 w-7 h-7 flex items-center justify-center",
          "text-xs font-bold rounded-full",
          "bg-gray-200 text-gray-600 border border-gray-300",
          "dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
        )}>
          {index}
        </span>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-2">
          {/* Metadata Badges Row */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              {docId && (
                <button
                  type="button"
                  onClick={onShowPdf}
                  className={cn(
                    "px-2 py-1 text-xs rounded-md border transition-colors",
                    "bg-gray-100 text-gray-600 border-gray-200/50",
                    "dark:bg-dark-surface-2 dark:text-gray-400 dark:border-dark-border/50",
                    "hover:bg-eliza-red/10 hover:text-eliza-red hover:border-eliza-red/30",
                    "dark:hover:bg-eliza-red/20 dark:hover:text-eliza-red-light",
                    "cursor-pointer"
                  )}
                  title="Click to preview PDF"
                >
                  Doc {docId}
                </button>
              )}
              {pages && (
                <button
                  type="button"
                  onClick={onShowPdf}
                  className={cn(
                    "px-2 py-1 text-xs rounded-md border transition-colors",
                    "bg-gray-100 text-gray-600 border-gray-200/50",
                    "dark:bg-dark-surface-2 dark:text-gray-400 dark:border-dark-border/50",
                    "hover:bg-eliza-red/10 hover:text-eliza-red hover:border-eliza-red/30",
                    "dark:hover:bg-eliza-red/20 dark:hover:text-eliza-red-light",
                    "cursor-pointer"
                  )}
                  title="Click to preview this page"
                >
                  Pages {pages}
                </button>
              )}
              {truncatedChunkId && (
                <span className={cn(
                  "px-2 py-1 text-[10px] font-mono rounded-md border",
                  "bg-gray-100 text-gray-500 border-gray-200/50",
                  "dark:bg-dark-surface-2 dark:text-gray-500 dark:border-dark-border/50"
                )}>
                  #{truncatedChunkId}
                </span>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              {showPdfButton && docId && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onShowPdf}
                  className="text-xs h-7 px-2"
                >
                  <DocumentTextIcon className="w-3.5 h-3.5 mr-1" />
                  Show PDF
                </Button>
              )}
              {showValidateButton && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={onValidate}
                  disabled={isValidating}
                  className="text-xs h-7 px-2"
                >
                  {isValidating ? (
                    <>
                      <Spinner size="xs" className="mr-1" />
                      Validating...
                    </>
                  ) : (
                    "Validate citation"
                  )}
                </Button>
              )}
            </div>
          </div>

          {/* Section Title */}
          {sectionTitle && (
            <p className="text-sm text-charcoal dark:text-gray-200 leading-relaxed break-words">
              {sectionTitle}
            </p>
          )}

          {/* Validation Results */}
          {hasValidation && verdict && (
            <div className="mt-2 space-y-1.5 overflow-hidden">
              <div className="flex items-center gap-2">
                <VerdictBadge verdict={verdict} />
                {typeof score === "number" && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {(score * 100).toFixed(1)}%
                  </span>
                )}
              </div>
              {reason && (
                <p className="text-xs text-gray-500 dark:text-gray-400 break-words">
                  {reason}
                </p>
              )}
              {evidence && (
                <p
                  className="text-xs text-gray-400 dark:text-gray-500 italic break-words line-clamp-2"
                  title={evidence}
                >
                  "{evidence}"
                </p>
              )}
            </div>
          )}

          {/* Validation Error */}
          {validationError && (
            <p className="mt-2 text-xs text-red-500 dark:text-red-400">
              {validationState?.error || "Citation validation failed"}
            </p>
          )}
        </div>
      </div>
    )
  }
)
SourceCard.displayName = "SourceCard"

/* ============================================
   VERDICT BADGE
   ============================================ */

interface VerdictBadgeProps {
  verdict: CitationVerdict
}

function VerdictBadge({ verdict }: VerdictBadgeProps) {
  const config: Record<string, { label: string; className: string }> = {
    pass: {
      label: "PASS",
      className: "border-emerald-500/40 text-emerald-600 dark:text-emerald-400",
    },
    fail: {
      label: "FAIL",
      className: "border-red-500/40 text-red-600 dark:text-red-400",
    },
    unsure: {
      label: "UNSURE",
      className: "border-amber-500/40 text-amber-600 dark:text-amber-400",
    },
    unavailable: {
      label: "UNAVAILABLE",
      className: "border-gray-500/40 text-gray-500 dark:text-gray-400",
    },
    error: {
      label: "ERROR",
      className: "border-gray-500/40 text-gray-600 dark:text-gray-400",
    },
  }

  const fallback = { label: verdict.toUpperCase(), className: "border-gray-500/40 text-gray-600 dark:text-gray-400" }
  const { label, className } = config[verdict] ?? fallback

  return (
    <span
      className={cn(
        "px-2 py-0.5 rounded-full border text-[10px] uppercase tracking-wide font-medium",
        className
      )}
    >
      {label}
    </span>
  )
}

export { SourceCard, VerdictBadge }

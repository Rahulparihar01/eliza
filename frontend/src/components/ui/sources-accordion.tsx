/**
 * SourcesAccordion - Collapsible Sources Section Component
 * 
 * A collapsible section for displaying RAG/document sources with full metadata.
 * Uses the DS Accordion internally and renders SourceCard for each source.
 * 
 * Part of the Eliza Forge Design System.
 */

import * as React from "react"
import { DocumentTextIcon, ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"
import { SourceCard, type CitationValidationResult, type CitationValidationState } from "./source-card"

/* ============================================
   TYPES
   ============================================ */

export interface Source {
  /** Source index (1-based) */
  index: number
  /** Document ID */
  docId: string
  /** Page range */
  pages: string
  /** Chunk ID */
  chunkId: string
  /** Section title/path */
  sectionTitle: string
  /** Raw citation string (for parsing if needed) */
  rawCitation?: string
  /** Chunk text for PDF highlighting */
  highlightText?: string
}

export interface SourcesAccordionProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Array of sources to display */
  sources: Source[]
  /** Callback to open PDF in canvas */
  onShowPdf?: (docId: string, pageNumber: string, highlightText?: string) => void
  /** Callback to validate citation - should return validation result */
  onValidateCitation?: (index: number) => Promise<CitationValidationResult>
  /** Question ID for validation API (passed to validation function) */
  questionId?: string
  /** Default expanded state */
  defaultExpanded?: boolean
  /** Whether to show the Show PDF button on each card */
  showPdfButtons?: boolean
  /** Whether to show the Validate button on each card */
  showValidateButtons?: boolean
}

/* ============================================
   SOURCES ACCORDION
   ============================================ */

const SourcesAccordion = React.forwardRef<HTMLDivElement, SourcesAccordionProps>(
  (
    {
      className,
      sources,
      onShowPdf,
      onValidateCitation,
      questionId,
      defaultExpanded = false,
      showPdfButtons = true,
      showValidateButtons = true,
      ...props
    },
    ref
  ) => {
    const [isExpanded, setIsExpanded] = React.useState(defaultExpanded)
    const [validationStates, setValidationStates] = React.useState<Record<number, CitationValidationState>>({})

    // Handle validation for a source
    const handleValidate = React.useCallback(async (index: number) => {
      if (!onValidateCitation) return

      // Set loading state
      setValidationStates(prev => ({
        ...prev,
        [index]: { status: "loading" },
      }))

      try {
        const result = await onValidateCitation(index)
        setValidationStates(prev => ({
          ...prev,
          [index]: { status: "success", result },
        }))
      } catch (error) {
        setValidationStates(prev => ({
          ...prev,
          [index]: {
            status: "error",
            error: error instanceof Error ? error.message : "Validation failed",
          },
        }))
      }
    }, [onValidateCitation])

    if (sources.length === 0) {
      return null
    }

    return (
      <div
        ref={ref}
        className={cn("mt-5", className)}
        {...props}
      >
        {/* Accordion Trigger */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className={cn(
            "flex items-center gap-2 text-sm px-3 py-2 rounded-lg transition-colors",
            "text-gray-500 dark:text-gray-400",
            "hover:text-charcoal dark:hover:text-gray-200",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-2"
          )}
          aria-expanded={isExpanded}
          aria-controls="sources-content"
        >
          {isExpanded ? (
            <ChevronDownIcon className="w-4 h-4" />
          ) : (
            <ChevronRightIcon className="w-4 h-4" />
          )}
          <DocumentTextIcon className="w-4 h-4" />
          <span className="font-medium">Sources</span>
          <span className={cn(
            "inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5",
            "text-xs font-medium rounded-full",
            "bg-eliza-red/10 text-eliza-red",
            "dark:bg-eliza-red/20 dark:text-eliza-red-light"
          )}>
            {sources.length}
          </span>
        </button>

        {/* Accordion Content */}
        <div
          id="sources-content"
          className={cn(
            "overflow-hidden transition-all duration-200 ease-out",
            isExpanded ? "opacity-100" : "opacity-0 h-0"
          )}
          style={{
            maxHeight: isExpanded ? `${sources.length * 200}px` : 0,
          }}
        >
          <div className="mt-3 space-y-2 ml-3">
            {sources.map((source) => (
              <SourceCard
                key={source.index}
                index={source.index}
                docId={source.docId}
                pages={source.pages}
                chunkId={source.chunkId}
                sectionTitle={source.sectionTitle}
                onShowPdf={() => onShowPdf?.(source.docId, source.pages || "1", source.highlightText || source.sectionTitle)}
                onValidate={() => handleValidate(source.index)}
                validationState={validationStates[source.index]}
                showPdfButton={showPdfButtons && !!source.docId}
                showValidateButton={showValidateButtons && (!!questionId || !!onValidateCitation)}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }
)
SourcesAccordion.displayName = "SourcesAccordion"

/* ============================================
   PARSE CITATION HELPER
   ============================================ */

/**
 * Parse a raw citation string into structured source data
 * Expected format: "doc:815 pages:168-168 chunk:844ff052 section:815 Derivatives..."
 */
export function parseCitation(citation: string): Omit<Source, "index"> {
  const docMatch = citation.match(/doc:(\d+)/)
  const pagesMatch = citation.match(/pages:([^\s]+)/)
  const chunkMatch = citation.match(/chunk:([^\s]+)/)
  const sectionMatch = citation.match(/section:(.+)$/)

  return {
    docId: docMatch?.[1] || "",
    pages: pagesMatch?.[1] || "",
    chunkId: chunkMatch?.[1] || "",
    sectionTitle: sectionMatch?.[1] || citation,
    rawCitation: citation,
  }
}

/**
 * Parse sources from a summary text with "Sources:" section
 * Returns the main content and parsed sources array
 */
export function parseSourcesFromSummary(summary: string): {
  mainContent: string
  sources: Source[]
} {
  // Look for "Sources:" section at the end
  const sourcesMatch = summary.match(/\n\nSources:\n([\s\S]*?)$/)

  if (!sourcesMatch) {
    return { mainContent: summary, sources: [] }
  }

  const mainContent = summary.slice(0, sourcesMatch.index).trim()
  const sourcesText = sourcesMatch[1]

  // Parse individual sources
  const sourceLines = sourcesText.split("\n").filter((line) => line.trim())
  const sources: Source[] = []

  for (const line of sourceLines) {
    const match = line.match(/^\[(\d+)\]\s*(.+)$/)
    if (match) {
      const index = parseInt(match[1], 10)
      const parsed = parseCitation(match[2].trim())
      sources.push({
        index,
        ...parsed,
      })
    }
  }

  return { mainContent, sources }
}

/**
 * Build Source objects from native RAG retrieved chunks.
 *
 * Native RAG chunks use a different schema than FASB citation strings.
 * This normalises them into the same Source type used throughout the UI.
 */
export function buildSourcesFromChunks(
  chunks: Array<{
    document_id?: string | number
    document_name?: string
    chunk_index?: number
    text?: string
    content?: string
    score?: number
    similarity?: number
    section_title?: string
    page_number?: number | null
    metadata?: Record<string, unknown>
  }>
): Source[] {
  return chunks.map((chunk, idx) => {
    const index = idx + 1
    const docId = String(chunk.document_id ?? "")
    const page = chunk.page_number
    const pages = page ? `${page}-${page}` : ""
    const chunkId =
      (chunk.metadata?.chunk_id as string) ??
      (chunk.chunk_index != null ? String(chunk.chunk_index) : "")
    const sectionTitle = chunk.section_title || chunk.document_name || ""

    const rawCitation = `doc:${docId} pages:${pages || "1-1"} chunk:${chunkId} section:${sectionTitle}`
    const highlightText = chunk.text || chunk.content || ""

    return { index, docId, pages, chunkId, sectionTitle, rawCitation, highlightText }
  })
}

export { SourcesAccordion }
export type { CitationValidationResult, CitationValidationState }

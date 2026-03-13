/**
 * PdfCanvasViewer - PDF Viewer for CanvasPanel
 * 
 * A PDF viewer component designed to render inside the CanvasPanel.
 * Supports PDF.js with text highlighting and iframe fallback.
 * Provides header actions to the CanvasPanel via context.
 * 
 * Part of the Eliza Forge Design System.
 */

import * as React from "react"
import { lazy, Suspense } from "react"
import { 
  ArrowTopRightOnSquareIcon,
} from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"
import { Switch } from "./switch"
import { Spinner } from "./spinner"
import { Label } from "./label"
import { useChat } from "./chat"

// Lazy load PDF viewer to reduce initial bundle size
const PdfPageViewer = lazy(() => import("../shared/PdfPageViewer"))

/* ============================================
   CONSTANTS
   ============================================ */

const RAG_EVAL_API_BASE = typeof window !== "undefined" && window.location.port === "3000"
  ? "http://localhost:5001/api/v1/rag-eval"
  : "/api/v1/rag-eval"

const RAGFLOW_API_BASE = typeof window !== "undefined" && window.location.port === "3000"
  ? "http://localhost:5001/v1/ragflow"
  : "/v1/ragflow"

/* ============================================
   PDF CANVAS VIEWER
   ============================================ */

export interface PdfCanvasViewerProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onError'> {
  /** Document ID */
  docId: string
  /** Page number or range (e.g., "168" or "168-170") */
  pageNumber: string
  /** Text to highlight in PDF */
  highlightText?: string
  /** PDF endpoint: "fasb" uses legacy rag-eval, "generic" uses ragflow documents endpoint */
  pdfEndpoint?: "fasb" | "generic"
  /** Callback when PDF loads */
  onLoad?: () => void
  /** Callback on error */
  onError?: (error: Error) => void
}

const PdfCanvasViewer = React.forwardRef<HTMLDivElement, PdfCanvasViewerProps>(
  (
    {
      className,
      docId,
      pageNumber,
      highlightText,
      pdfEndpoint = "fasb",
      onLoad,
      onError,
      ...props
    },
    ref
  ) => {
    const [isLoading, setIsLoading] = React.useState(true)
    const [usePdfJs, setUsePdfJs] = React.useState(true)
    const [pdfJsError, setPdfJsError] = React.useState<string | null>(null)
    
    // Get context to set header actions
    const { setCanvasHeaderActions } = useChat()

    // Get auth token
    const token = typeof localStorage !== "undefined" ? localStorage.getItem("auth_token") : null

    // Parse page number (handle ranges like "70-72" by taking first page)
    const page = React.useMemo(() => {
      if (pageNumber.includes("-")) {
        return parseInt(pageNumber.split("-")[0], 10)
      }
      return parseInt(pageNumber, 10)
    }, [pageNumber])

    // Build PDF URL with token as query param - route to correct endpoint
    const pdfUrl = React.useMemo(() => {
      const baseUrl = pdfEndpoint === "generic"
        ? `${RAGFLOW_API_BASE}/documents/${docId}/pdf`
        : `${RAG_EVAL_API_BASE}/pdf/${docId}`
      const params = new URLSearchParams()
      if (token) params.set("token", token)
      params.set("page", String(page))
      return `${baseUrl}?${params.toString()}#page=${page}`
    }, [docId, token, page, pdfEndpoint])

    // URL for PDF.js (without hash)
    const pdfJsUrl = pdfUrl.split("#")[0]

    // URL for new tab (without page hash)
    const newTabUrl = React.useMemo(() => {
      const baseUrl = pdfEndpoint === "generic"
        ? `${RAGFLOW_API_BASE}/documents/${docId}/pdf`
        : `${RAG_EVAL_API_BASE}/pdf/${docId}`
      const params = new URLSearchParams()
      if (token) params.set("token", token)
      return `${baseUrl}?${params.toString()}`
    }, [docId, token, pdfEndpoint])

    const handleLoad = () => {
      setIsLoading(false)
      onLoad?.()
    }

    const handlePdfJsError = (err: Error) => {
      setPdfJsError(err.message)
      setUsePdfJs(false)
      setIsLoading(true)
      onError?.(err)
    }
    
    // Set header actions for CanvasPanel
    React.useEffect(() => {
      setCanvasHeaderActions(
        <div className="flex items-center gap-2">
          <Switch
            id="pdf-highlighting"
            checked={usePdfJs}
            onCheckedChange={(checked) => {
              setUsePdfJs(checked)
              setPdfJsError(null)
              setIsLoading(true)
            }}
            className="h-5 w-9"
          />
          <Label 
            htmlFor="pdf-highlighting" 
            className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap"
          >
            Highlighting
          </Label>
        </div>
      )
      
      // Cleanup on unmount
      return () => {
        setCanvasHeaderActions(null)
      }
    }, [usePdfJs, setCanvasHeaderActions])

    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col h-full w-full overflow-hidden",
          "bg-white dark:bg-dark-surface",
          className
        )}
        {...props}
      >
        {/* Search Hint (iframe mode only) */}
        {!usePdfJs && highlightText && (
          <div className={cn(
            "px-4 py-2 shrink-0 border-b",
            "bg-blue-50 dark:bg-blue-900/20",
            "border-blue-200 dark:border-blue-800/30"
          )}>
            <p className="text-xs text-blue-800 dark:text-blue-300">
              <span className="font-medium">Tip:</span> Use Ctrl+F to search for:{" "}
              "{highlightText.length > 60 ? highlightText.slice(0, 60) + "..." : highlightText}"
            </p>
          </div>
        )}

        {/* PDF.js Error Message */}
        {usePdfJs && pdfJsError && (
          <div className={cn(
            "px-4 py-2 shrink-0 border-b",
            "bg-red-50 dark:bg-red-900/20",
            "border-red-200 dark:border-red-800/30"
          )}>
            <p className="text-xs text-red-800 dark:text-red-300">
              <span className="font-medium">PDF.js failed:</span> {pdfJsError}. Switching to iframe mode.
            </p>
          </div>
        )}

        {/* PDF Viewer */}
        <div className="flex-1 relative min-h-0 overflow-hidden">
          {/* Loading Overlay */}
          {isLoading && (
            <div className={cn(
              "absolute inset-0 flex flex-col items-center justify-center z-10",
              "bg-white dark:bg-dark-surface"
            )}>
              <div className="relative">
                <Spinner size="lg" />
              </div>
              <p className="mt-4 text-sm text-gray-500 dark:text-gray-400 animate-pulse">
                Loading PDF...
              </p>
            </div>
          )}

          {usePdfJs && !pdfJsError ? (
            /* PDF.js viewer with highlighting */
            <Suspense
              fallback={
                <div className={cn(
                  "absolute inset-0 flex flex-col items-center justify-center",
                  "bg-white dark:bg-dark-surface"
                )}>
                  <Spinner size="lg" />
                  <p className="mt-4 text-sm text-gray-500 dark:text-gray-400 animate-pulse">
                    Loading PDF.js...
                  </p>
                </div>
              }
            >
              <PdfPageViewer
                pdfUrl={pdfJsUrl}
                pageNumber={page}
                highlightText={highlightText}
                pageWindow={0}
                className="absolute inset-0"
                onLoad={handleLoad}
                onError={handlePdfJsError}
              />
            </Suspense>
          ) : (
            /* Iframe viewer (fallback) */
            <iframe
              src={pdfUrl}
              className="absolute inset-0 w-full h-full border-0"
              title={`PDF Document ${docId} - Page ${page}`}
              onLoad={handleLoad}
            />
          )}
        </div>

        {/* Footer */}
        <div className={cn(
          "flex items-center justify-between px-4 py-2 shrink-0 border-t",
          "bg-gray-50 dark:bg-dark-surface-2",
          "border-gray-200 dark:border-dark-border/50"
        )}>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {usePdfJs ? "PDF.js viewer (highlighting enabled)" : "Native PDF viewer"}
          </p>
          <a
            href={newTabUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "text-xs flex items-center gap-1 transition-colors",
              "text-eliza-red hover:text-eliza-red-light hover:underline"
            )}
          >
            Open in new tab
            <ArrowTopRightOnSquareIcon className="w-3 h-3" />
          </a>
        </div>
      </div>
    )
  }
)
PdfCanvasViewer.displayName = "PdfCanvasViewer"

export { PdfCanvasViewer }

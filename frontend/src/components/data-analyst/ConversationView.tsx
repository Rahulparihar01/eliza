/**
 * Conversation View Component
 * Chat-style interface where questions and data results flow naturally in the conversation
 * 
 * Migrated to use Eliza Forge Design System components
 */
import React, { useState, useEffect, useRef, useMemo, useCallback, lazy, Suspense } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  useSubmitQuestionV1DataAnalystQuestionsPost,
  useListQuestionsV1DataAnalystQuestionsGet,
  useGetAnalysisResultV1DataAnalystQuestionsQuestionIdResultGet,
  useClarifyQuestionV1DataAnalystQuestionsQuestionIdClarifyPost,
  useGetConversationV1DataAnalystConversationsConversationIdGet,
  useUpdateConversationTitleV1DataAnalystConversationsConversationIdTitlePatch,
} from '../../generated/data-analyst/data-analyst';
import { DataSourceType } from '../../generated/models';
import { AXIOS_INSTANCE } from '../../services/api-client';
import DataTable from './DataTable';
import ChartDisplay from './ChartDisplay';
import { 
  SparklesIcon,
  ChartBarIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  DocumentTextIcon,
  HandThumbUpIcon,
  HandThumbDownIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { Highlight, themes, type RenderProps, type Token } from 'prism-react-renderer';
import { useToasts } from '../../stores/useToasts';

// DS Components
import {
  ChatContainer,
  ChatMessagesPane,
  ChatScrollArea,
  ChatInputArea,
  MessageBubble,
  MessageContent,
  ThinkingIndicator,
  CanvasPanel,
  ArtifactButton,
  useChat,
  type ExecutionStep,
} from '../ui/chat';
import { PromptBar } from '../ui/prompt-bar';
import { Alert } from '../ui/alert';
import { InlineCitation } from '../ui/inline-citation';
import { 
  SourcesAccordion, 
  parseSourcesFromSummary as parseSourcesFromSummaryDS,
  parseCitation as parseCitationDS,
  type Source,
  type CitationValidationResult,
} from '../ui/sources-accordion';
import { PdfCanvasViewer } from '../ui/pdf-canvas-viewer';
import { ChartCanvasViewer } from '../ui/chart-canvas-viewer';

// Lazy load PDF viewer to reduce initial bundle size
const PdfPageViewer = lazy(() => import('../shared/PdfPageViewer'));

const RAG_EVAL_API_BASE = window.location.port === '3000'
  ? 'http://localhost:5001/api/v1/rag-eval'
  : '/api/v1/rag-eval';

// PDF Preview Popup Component - uses iframe (reliable) with optional PDF.js (experimental)
function PdfPreviewPopup({ 
  docId, 
  pageNumber,
  highlightText,
  onClose 
}: { 
  docId: string; 
  pageNumber: string;
  highlightText?: string;
  onClose: () => void;
}) {
  const token = localStorage.getItem('auth_token');
  const [isLoading, setIsLoading] = useState(true);
  const [usePdfJs, setUsePdfJs] = useState(true);
  const [pdfJsError, setPdfJsError] = useState<string | null>(null);
  
  // Parse page number (handle ranges like "70-72" by taking first page)
  const page = pageNumber.includes('-') 
    ? parseInt(pageNumber.split('-')[0], 10) 
    : parseInt(pageNumber, 10);
  
  // Build PDF URL with token as query param
  const pdfUrl = `${RAG_EVAL_API_BASE}/pdf/${docId}?token=${encodeURIComponent(token || '')}&page=${page}#page=${page}`;
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="relative bg-surface rounded-2xl shadow-2xl border border-border overflow-hidden max-w-5xl w-full h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-2 shrink-0">
          <div className="flex items-center gap-3">
            <DocumentTextIcon className="w-5 h-5 text-brand" />
            <div>
              <h3 className="text-sm font-semibold text-text">Document {docId}</h3>
              <p className="text-xs text-muted">Page {pageNumber}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Toggle for PDF.js mode */}
            <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
              <input
                type="checkbox"
                checked={usePdfJs}
                onChange={(e) => {
                  setUsePdfJs(e.target.checked);
                  setPdfJsError(null);
                  setIsLoading(true);
                }}
                className="w-3 h-3 rounded border-border"
              />
              Highlighting
            </label>
            <button
              onClick={onClose}
              className="p-2 text-muted hover:text-text hover:bg-surface-2 rounded-lg transition-colors"
              title="Close preview"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
        
        {/* Search hint when using iframe */}
        {!usePdfJs && highlightText && (
          <div className="px-4 py-2 bg-blue-50 border-b border-blue-200 shrink-0">
            <p className="text-xs text-blue-800">
              <span className="font-medium">Tip:</span> Use Ctrl+F to search for: "{highlightText.length > 60 ? highlightText.slice(0, 60) + '...' : highlightText}"
            </p>
          </div>
        )}
        
        {/* PDF.js error message */}
        {usePdfJs && pdfJsError && (
          <div className="px-4 py-2 bg-red-50 border-b border-red-200 shrink-0">
            <p className="text-xs text-red-800">
              <span className="font-medium">PDF.js failed:</span> {pdfJsError}. Switching to iframe mode.
            </p>
          </div>
        )}
        
        {/* PDF Viewer */}
        <div className="flex-1 relative min-h-0 overflow-hidden">
          {/* Loading overlay */}
          {isLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface z-10">
              <div className="relative">
                <div className="w-12 h-12 rounded-full border-4 border-border border-t-brand animate-spin" />
                <DocumentTextIcon className="w-5 h-5 text-brand absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
              </div>
              <p className="mt-4 text-sm text-muted animate-pulse">Loading PDF...</p>
            </div>
          )}
          
          {usePdfJs && !pdfJsError ? (
            /* PDF.js viewer with highlighting (experimental) */
            <Suspense fallback={
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface">
                <div className="relative">
                  <div className="w-12 h-12 rounded-full border-4 border-border border-t-brand animate-spin" />
                </div>
                <p className="mt-4 text-sm text-muted animate-pulse">Loading PDF.js...</p>
              </div>
            }>
              <PdfPageViewer
                pdfUrl={pdfUrl.split('#')[0]} // Remove hash for PDF.js
                pageNumber={page}
                highlightText={highlightText}
                className="absolute inset-0"
                onLoad={() => setIsLoading(false)}
                onError={(err) => {
                  setPdfJsError(err.message);
                  setUsePdfJs(false);
                  setIsLoading(true);
                }}
              />
            </Suspense>
          ) : (
            /* Iframe viewer (reliable) */
            <iframe
              src={pdfUrl}
              className="absolute inset-0 w-full h-full border-0"
              title={`PDF Document ${docId} - Page ${page}`}
              onLoad={() => setIsLoading(false)}
            />
          )}
        </div>
        
        {/* Footer with actions */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-surface-2 shrink-0">
          <p className="text-xs text-muted">
            {usePdfJs ? 'PDF.js viewer (highlighting enabled)' : 'Native PDF viewer'}
          </p>
          <a
            href={`${RAG_EVAL_API_BASE}/pdf/${docId}?token=${encodeURIComponent(token || '')}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-brand hover:underline flex items-center gap-1"
          >
            Open in new tab
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}

// Simple loading spinner component
function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };
  return (
    <div className={`${sizeClasses[size]} animate-spin rounded-full border-2 border-gray-300 border-t-brand`} />
  );
}

// Local execution step interface for tracking progress (different from DS ExecutionStep)
interface LocalExecutionStepType {
  id: string;
  stageName: string;
  message: string;
  timestamp: Date;
  isComplete: boolean;
  isFailed?: boolean;
  order: number; // Order for sorting steps
}

// Canonical order of processing stages - used to display steps in correct order regardless of SSE arrival order
const STAGE_ORDER: Record<string, number> = {
  'Question Submission': 0,
  'Processing': 1,
  'Flow': 2,
  'Intent Detection': 3,
  'Domain Validation': 4,
  'Clarification Check': 5,
  'Query Generation': 6,
  'SQL Generation': 7,
  'Query Execution': 8,
  'RAG Search': 9,
  'Document Retrieval': 10,
  'Answer Generation': 11,
  'Response Synthesis': 12,
  'Completion': 99,
};

// Get order for a stage, defaulting to a high number for unknown stages
const getStageOrder = (stageName: string): number => {
  // Check for exact match
  if (STAGE_ORDER[stageName] !== undefined) {
    return STAGE_ORDER[stageName];
  }
  // Check for partial match (stage name might be a substring)
  for (const [key, order] of Object.entries(STAGE_ORDER)) {
    if (stageName.toLowerCase().includes(key.toLowerCase()) || 
        key.toLowerCase().includes(stageName.toLowerCase())) {
      return order;
    }
  }
  // Unknown stage - put at end but before Completion
  return 50;
};

// CitationValidationResult and CitationValidationState are now imported from sources-accordion

/**
 * MarkdownContent - Rich markdown renderer using react-markdown
 * Supports: headers, tables, code blocks, lists, bold, italic, links, and citations
 * Uses design tokens for proper light/dark mode support
 */
function MarkdownContent({ content }: { content: string }) {
  if (!content) return null;
  
  // Pre-process content to convert [n] citations to a special format that won't be consumed by markdown
  const processedContent = content.replace(/\[(\d+)\]/g, '⟦$1⟧');
  
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Headers - using text-text for proper theme support
        h1: ({ node, children, ...props }) => (
          <h1 className="text-xl font-bold text-text mb-4 mt-6 first:mt-0 border-b border-border pb-2" {...props}>
            {children}
          </h1>
        ),
        h2: ({ node, children, ...props }) => (
          <h2 className="text-lg font-semibold text-text mb-3 mt-5 first:mt-0" {...props}>
            {children}
          </h2>
        ),
        h3: ({ node, children, ...props }) => (
          <h3 className="text-base font-semibold text-text mb-2 mt-4 first:mt-0" {...props}>
            {children}
          </h3>
        ),
        h4: ({ node, children, ...props }) => (
          <h4 className="text-sm font-semibold text-text mb-2 mt-3 first:mt-0" {...props}>
            {children}
          </h4>
        ),
        
        // Paragraphs
        p: ({ node, children, ...props }) => (
          <p className="mb-3 last:mb-0 leading-relaxed text-text" {...props}>
            {renderCitations(children)}
          </p>
        ),
        
        // Lists
        ul: ({ node, ...props }) => (
          <ul className="list-disc list-outside ml-5 space-y-1.5 my-3 text-text" {...props} />
        ),
        ol: ({ node, ...props }) => (
          <ol className="list-decimal list-outside ml-5 space-y-1.5 my-3 text-text" {...props} />
        ),
        li: ({ node, children, ...props }) => (
          <li className="leading-relaxed text-text" {...props}>
            {renderCitations(children)}
          </li>
        ),
        
        // Code
        code: ({ node, className, children, ...props }) => {
          const isInline = !className;
          if (isInline) {
            return (
              <code className="px-1.5 py-0.5 bg-surface-2 rounded text-sm font-mono text-brand" {...props}>
                {children}
              </code>
            );
          }
          // Block code
          return (
            <code className={`${className} block text-text`} {...props}>
              {children}
            </code>
          );
        },
        pre: ({ node, ...props }) => (
          <pre className="bg-surface-2 rounded-lg p-4 overflow-x-auto my-4 text-sm text-text" {...props} />
        ),
        
        // Tables (for FASB accounting data)
        table: ({ node, ...props }) => (
          <div className="overflow-x-auto my-4">
            <table className="min-w-full border-collapse border border-border rounded-lg overflow-hidden" {...props} />
          </div>
        ),
        thead: ({ node, ...props }) => (
          <thead className="bg-surface-2" {...props} />
        ),
        tbody: ({ node, ...props }) => (
          <tbody className="divide-y divide-border" {...props} />
        ),
        tr: ({ node, ...props }) => (
          <tr className="hover:bg-surface-2/50 transition-colors" {...props} />
        ),
        th: ({ node, ...props }) => (
          <th className="px-4 py-2 text-left text-sm font-semibold text-text border-b border-border" {...props} />
        ),
        td: ({ node, ...props }) => (
          <td className="px-4 py-2 text-sm text-muted" {...props} />
        ),
        
        // Links
        a: ({ node, children, ...props }) => (
          <a className="text-brand hover:text-brand-hover underline underline-offset-2" target="_blank" rel="noopener noreferrer" {...props}>
            {children}
          </a>
        ),
        
        // Blockquotes (for FASB standard excerpts)
        blockquote: ({ node, ...props }) => (
          <blockquote className="border-l-4 border-brand/50 pl-4 py-2 my-4 bg-brand/5 rounded-r-lg italic text-muted" {...props} />
        ),
        
        // Horizontal rule
        hr: ({ node, ...props }) => (
          <hr className="my-6 border-border" {...props} />
        ),
        
        // Strong and emphasis
        strong: ({ node, ...props }) => (
          <strong className="font-semibold text-text" {...props} />
        ),
        em: ({ node, ...props }) => (
          <em className="italic text-text" {...props} />
        ),
      }}
    >
      {processedContent}
    </Markdown>
  );
}

/**
 * Context for passing source data to inline citations
 */
const SourceMapContext = React.createContext<{
  sourceMap: Map<number, Source>;
  onCitationClick?: (source: Source) => void;
}>({ sourceMap: new Map() });

/**
 * Helper to render citation markers ⟦n⟧ back to styled InlineCitation components
 * This allows citations to work within react-markdown rendered content
 */
function renderCitations(children: React.ReactNode): React.ReactNode {
  if (typeof children === 'string') {
    const parts: React.ReactNode[] = [];
    const regex = /⟦(\d+)⟧/g;
    let lastIndex = 0;
    let match;
    let key = 0;
    
    while ((match = regex.exec(children)) !== null) {
      if (match.index > lastIndex) {
        parts.push(children.slice(lastIndex, match.index));
      }
      const citationNumber = parseInt(match[1], 10);
      parts.push(
        <CitationBadge key={key++} number={citationNumber} />
      );
      lastIndex = match.index + match[0].length;
    }
    
    if (lastIndex < children.length) {
      parts.push(children.slice(lastIndex));
    }
    
    return parts.length > 0 ? parts : children;
  }
  
  // Handle arrays of children
  if (Array.isArray(children)) {
    return children.map((child, idx) => (
      <React.Fragment key={idx}>{renderCitations(child)}</React.Fragment>
    ));
  }
  
  // Return other node types as-is
  return children;
}

/**
 * Individual citation badge that uses context for source data
 */
function CitationBadge({ number }: { number: number }) {
  const { sourceMap, onCitationClick } = React.useContext(SourceMapContext);
  const source = sourceMap.get(number);
  
  return (
    <InlineCitation
      number={number}
      docId={source?.docId}
      pageNumber={source?.pages}
      sectionTitle={source?.sectionTitle}
      interactive={!!source && !!onCitationClick}
      onClick={() => source && onCitationClick?.(source)}
    />
  );
}

// parseSourcesFromSummary and parseCitation are now imported from sources-accordion as DS functions

// Execution Steps Panel component
function ExecutionStepsPanel({ 
  steps, 
  currentStep, 
  isProcessing 
}: { 
  steps: LocalExecutionStepType[]; 
  currentStep: string | null;
  isProcessing: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  
  // Auto-collapse after completion (with a delay)
  useEffect(() => {
    if (!isProcessing && steps.length > 0) {
      const timer = setTimeout(() => setExpanded(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [isProcessing, steps.length]);
  
  if (steps.length === 0 && !isProcessing) return null;
  
  return (
    <div className="p-4 bg-surface-2/50 border border-border rounded-lg">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between mb-3"
      >
        <div className="flex items-center gap-2">
          {isProcessing ? (
            <div className="w-2 h-2 bg-brand rounded-full animate-pulse" />
          ) : (
            <div className="w-2 h-2 bg-green-500 rounded-full" />
          )}
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
            {isProcessing ? 'Execution Progress' : 'Completed Steps'}
          </span>
          <span className="text-xs text-muted/60">({steps.length})</span>
        </div>
        {expanded ? (
          <ChevronDownIcon className="w-4 h-4 text-muted" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-muted" />
        )}
      </button>
      
      {expanded && (
        <>
          {steps.length === 0 ? (
            <div className="flex items-center gap-3 text-sm text-muted">
              <LoadingSpinner size="sm" />
              <span>Initializing analysis...</span>
            </div>
          ) : (
            <div className="space-y-2">
              {steps.map((step) => (
                <div 
                  key={step.id} 
                  className={`flex items-start gap-3 text-sm ${
                    step.isComplete ? 'text-muted' : 'text-text'
                  }`}
                >
                  {/* Step indicator - Radio button style */}
                  <div className="flex-shrink-0 mt-0.5">
                    {step.isComplete ? (
                      <div className="w-5 h-5 rounded-full bg-green-500/20 border-2 border-green-500/50 flex items-center justify-center">
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
                      </div>
                    ) : currentStep === step.stageName ? (
                      <div className="w-5 h-5 rounded-full bg-brand/20 border-2 border-brand/50 flex items-center justify-center">
                        <div className="w-2.5 h-2.5 rounded-full bg-brand animate-pulse" />
                      </div>
                    ) : (
                      <div className="w-5 h-5 rounded-full bg-surface-3/50 border-2 border-border flex items-center justify-center">
                        <div className="w-2 h-2 rounded-full bg-muted/50" />
                      </div>
                    )}
                  </div>
                  
                  {/* Step content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${step.isComplete ? 'text-muted' : 'text-text'}`}>
                        {step.stageName}
                      </span>
                      {step.isComplete && (
                        <span className="text-xs text-green-500">✓</span>
                      )}
                    </div>
                    <p className={`text-xs mt-0.5 ${step.isComplete ? 'text-muted/60' : 'text-muted'}`}>
                      {step.message}
                    </p>
                  </div>
                </div>
              ))}
              
              {/* Current activity indicator */}
              {isProcessing && currentStep && (
                <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
                  <LoadingSpinner size="sm" />
                  <span className="text-xs text-brand">
                    Working on: {currentStep}
                  </span>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Component to render answer with markdown and collapsible sources
function MarkdownAnswerWithSources({ summary, questionId }: { summary: string; questionId?: string }) {
  const token = localStorage.getItem('auth_token');
  
  // Use DS parsing functions
  const { mainContent, sources: rawSources } = useMemo(() => parseSourcesFromSummaryDS(summary), [summary]);
  
  // Convert to Source type with proper parsing
  const sources: Source[] = useMemo(() => {
    return rawSources.map(source => ({
      ...source,
    }));
  }, [rawSources]);
  
  // Create a source map for inline citations
  const sourceMap = useMemo(() => {
    const map = new Map<number, Source>();
    sources.forEach(source => map.set(source.index, source));
    return map;
  }, [sources]);
  
  // Get chat context for opening PDF in canvas (using DS useChat hook)
  const chatContext = useChatContext();
  
  // Handle opening PDF in canvas panel
  const handleShowPdf = useCallback((docId: string, pageNumber: string, highlightText?: string) => {
    if (chatContext) {
      chatContext.setCanvasTitle(`Document ${docId} - Page ${pageNumber}`);
      chatContext.setCanvasContent(
        <PdfCanvasViewer
          docId={docId}
          pageNumber={pageNumber}
          highlightText={highlightText}
        />
      );
      chatContext.setCanvasOpen(true);
    }
  }, [chatContext]);
  
  // Handle citation click (from inline citation)
  const handleCitationClick = useCallback((source: Source) => {
    if (source.docId && source.pages) {
      handleShowPdf(source.docId, source.pages, source.sectionTitle);
    }
  }, [handleShowPdf]);

  // Handle validation API call
  const handleValidateCitation = useCallback(async (citationIndex: number): Promise<CitationValidationResult> => {
    if (!questionId || !token) {
      throw new Error('Not authenticated');
    }

    const response = await fetch(`${RAG_EVAL_API_BASE}/citations/validate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        question_id: questionId,
        citation_index: citationIndex,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Validation failed (${response.status})`);
    }

    const data = await response.json();
    return data.result;
  }, [questionId, token]);
  
  return (
    <SourceMapContext.Provider value={{ sourceMap, onCitationClick: handleCitationClick }}>
      <div className="space-y-4">
        {/* Main answer with markdown rendering */}
        <div className="prose prose-sm max-w-none">
          <MarkdownContent content={mainContent} />
        </div>
        
        {/* Sources section - DS SourcesAccordion */}
        {sources.length > 0 && (
          <SourcesAccordion
            sources={sources}
            questionId={questionId}
            onShowPdf={handleShowPdf}
            onValidateCitation={handleValidateCitation}
            showValidateButtons={!!questionId}
          />
        )}
      </div>
    </SourceMapContext.Provider>
  );
}

/**
 * Custom hook to safely access chat context (returns null if not in provider)
 */
function useChatContext() {
  try {
    return useChat();
  } catch {
    return null;
  }
}

interface ConversationViewProps {
  conversationId: string | null;
  dataSourceType: DataSourceType;
  /** Optional header content (e.g., domain pill) to render above messages */
  headerContent?: React.ReactNode;
}

/* ============================================
   Canvas Code Block - For displaying code in canvas
   ============================================ */

interface CanvasCodeBlockProps {
  code: string;
  language: string;
}

function CanvasCodeBlock({ code, language }: CanvasCodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Map language names to Prism language identifiers
  const prismLanguage = language.toLowerCase() === 'sql' ? 'sql' : language.toLowerCase();

  return (
    <div className="h-full flex flex-col rounded-lg border border-gray-200 dark:border-dark-border/50 overflow-hidden">
      {/* Header with language and copy button */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-dark-surface-2 border-b border-gray-200 dark:border-dark-border/50">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {language}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-1 text-xs rounded hover:bg-gray-200 dark:hover:bg-dark-surface-3 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-white transition-colors"
          title="Copy to clipboard"
        >
          {copied ? (
            <>
              <CheckIcon className="w-4 h-4 text-green-500" />
              <span className="text-green-500">Copied!</span>
            </>
          ) : (
            <>
              <ClipboardDocumentIcon className="w-4 h-4" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      
      {/* Code content with Prism syntax highlighting */}
      <div className="flex-1 overflow-auto bg-gray-50 dark:bg-dark-surface">
        {/* Light mode */}
        <div className="dark:hidden h-full">
          <Highlight
            theme={themes.vsLight}
            code={code.trim()}
            language={prismLanguage}
          >
            {({ style, tokens, getLineProps, getTokenProps }: RenderProps) => (
              <pre 
                className="text-sm font-mono p-4 m-0 overflow-auto h-full"
                style={{ ...style, background: 'transparent' }}
              >
                {tokens.map((line: Token[], i: number) => (
                  <div key={i} {...getLineProps({ line })}>
                    {line.map((token: Token, key: number) => (
                      <span key={key} {...getTokenProps({ token })} />
                    ))}
                  </div>
                ))}
              </pre>
            )}
          </Highlight>
        </div>
        {/* Dark mode */}
        <div className="hidden dark:block h-full">
          <Highlight
            theme={themes.vsDark}
            code={code.trim()}
            language={prismLanguage}
          >
            {({ style, tokens, getLineProps, getTokenProps }: RenderProps) => (
              <pre 
                className="text-sm font-mono p-4 m-0 overflow-auto h-full"
                style={{ ...style, background: 'transparent' }}
              >
                {tokens.map((line: Token[], i: number) => (
                  <div key={i} {...getLineProps({ line })}>
                    {line.map((token: Token, key: number) => (
                      <span key={key} {...getTokenProps({ token })} />
                    ))}
                  </div>
                ))}
              </pre>
            )}
          </Highlight>
        </div>
      </div>
    </div>
  );
}

export default function ConversationView({
  conversationId,
  dataSourceType,
  headerContent,
}: ConversationViewProps) {
  const [message, setMessage] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const { mutate: submitQuestion, isPending } = useSubmitQuestionV1DataAnalystQuestionsPost();
  
  // Fetch conversation details
  const { data: conversationData, refetch: refetchConversation } = useGetConversationV1DataAnalystConversationsConversationIdGet(
    conversationId || '',
    {
      query: {
        enabled: !!conversationId,
      },
    }
  );
  
  // Update title mutation
  const { mutate: updateTitle, isPending: isUpdatingTitle } = useUpdateConversationTitleV1DataAnalystConversationsConversationIdTitlePatch();
  
  // Fetch messages for this conversation
  const { data: messagesData } = useListQuestionsV1DataAnalystQuestionsGet({
    data_source_type: dataSourceType,
    conversation_id: conversationId || undefined,
    page: 1,
    page_size: 100,
  }, {
    query: {
      refetchInterval: 3000,
      enabled: !!conversationId,
    },
  });

  // Sort messages chronologically (oldest first, newest last)
  const messages = [...(messagesData?.questions || [])].sort((a, b) => 
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  // Scroll to bottom when new messages are added
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messagesData?.questions]);
  
  // Focus input when editing starts
  useEffect(() => {
    if (isEditingTitle && titleInputRef.current) {
      titleInputRef.current.focus();
      titleInputRef.current.select();
    }
  }, [isEditingTitle]);

  // Handle submit from PromptBar
  const handlePromptSubmit = (value: string) => {
    if (!value.trim() || isPending || !conversationId) return;

    submitQuestion(
      {
        data: {
          data_source_type: dataSourceType,
          question: value.trim(),
          conversation_id: conversationId,
        },
      },
      {
        onSuccess: () => {
          setMessage('');
        },
        onError: (error) => {
          console.error('Failed to submit question:', error);
        },
      }
    );
  };
  
  const handleStartEdit = () => {
    const currentTitle = conversationData?.title || `Conversation ${conversationId?.slice(-6)}`;
    setEditedTitle(currentTitle);
    setIsEditingTitle(true);
  };
  
  const handleSaveTitle = () => {
    if (!conversationId || !editedTitle.trim()) {
      setIsEditingTitle(false);
      return;
    }
    
    updateTitle(
      {
        conversationId,
        data: { title: editedTitle.trim() },
      },
      {
        onSuccess: () => {
          refetchConversation();
          setIsEditingTitle(false);
        },
        onError: (error) => {
          console.error('Failed to update title:', error);
        },
      }
    );
  };
  
  const handleCancelEdit = () => {
    setIsEditingTitle(false);
    setEditedTitle('');
  };
  
  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveTitle();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  };

  // No conversation yet - show loading state while creating
  if (!conversationId) {
    return (
      <ChatContainer className="bg-gray-50 dark:bg-dark-bg">
        <ChatMessagesPane>
          {/* Header Content */}
          {headerContent && (
            <div className="absolute top-0 left-0 right-0 z-20 px-4 py-3 pointer-events-none">
              <div className="pointer-events-auto inline-block">
                {headerContent}
              </div>
            </div>
          )}
          
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <div className="animate-pulse">
                <SparklesIcon className="w-12 h-12 mb-4 mx-auto text-eliza-red/30" />
              </div>
              <p className="text-sm text-charcoal dark:text-gray-100">Starting new conversation...</p>
            </div>
          </div>
        </ChatMessagesPane>
      </ChatContainer>
    );
  }
  
  const conversationTitle = conversationData?.title || `Conversation ${conversationId.slice(-6)}`;

  return (
    <ChatContainer className="bg-gray-50 dark:bg-dark-bg">
      <ChatMessagesPane>
        {/* Header Content (e.g., Domain Pill) - absolute positioned, transparent, messages scroll under */}
        {headerContent && (
          <div className="absolute top-0 left-0 right-0 z-20 px-4 py-3 pointer-events-none">
            <div className="pointer-events-auto inline-block">
              {headerContent}
            </div>
          </div>
        )}
        
        {/* Messages - Chat Style - add top padding when header exists so first message isn't hidden */}
        <ChatScrollArea>
          {/* Spacer for header when it exists */}
          {headerContent && <div className="h-14 flex-shrink-0" />}
          
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center max-w-md">
                <SparklesIcon className="w-12 h-12 mb-4 mx-auto opacity-20" />
                <p className="text-sm mb-2 text-charcoal dark:text-gray-100">Start your conversation with Eliza</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Ask questions about your data, and I'll provide insights, charts, and detailed analysis to help you understand the patterns and trends.</p>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <ConversationMessage key={msg.question_id} message={msg} dataSourceType={dataSourceType} />
            ))
          )}
          <div ref={chatEndRef} />
        </ChatScrollArea>

        {/* Message Input - DS PromptBar */}
        <ChatInputArea>
          <PromptBar
            value={message}
            onChange={setMessage}
            onSubmit={handlePromptSubmit}
            placeholder="Ask a question about your data..."
            loading={isPending}
            disabled={!conversationId}
          />
        </ChatInputArea>
      </ChatMessagesPane>
      
      {/* Canvas Panel for artifacts */}
      <CanvasPanel />
    </ChatContainer>
  );
}

// Individual message component with inline results
function ConversationMessage({ message, dataSourceType }: { message: any; dataSourceType: DataSourceType }) {
  const [executionSteps, setExecutionSteps] = React.useState<LocalExecutionStepType[]>([]);
  const [currentStep, setCurrentStep] = React.useState<string | null>(null);
  const [clarificationResponse, setClarificationResponse] = React.useState('');
  
  // Clarification mutation
  const { mutate: submitClarification, isPending: isClarifying } = useClarifyQuestionV1DataAnalystQuestionsQuestionIdClarifyPost();
  
  // Fetch results if completed
  const { data: resultData } = useGetAnalysisResultV1DataAnalystQuestionsQuestionIdResultGet(
    message.question_id,
    {
      query: {
        enabled: message.status === 'completed',
      },
    }
  );
  

  // Connect to SSE for real-time status updates
  // Note: Fast queries may complete before SSE can connect - see AI_CHAT_MIGRATION_PLAN.md for details
  React.useEffect(() => {
    if (message.status === 'processing') {
      // Get auth token for SSE (EventSource doesn't support custom headers)
      const token = localStorage.getItem('auth_token');
      if (!token) {
        console.error('No auth token found for SSE connection');
        return;
      }

      // Get API base URL for SSE connection
      const apiUrl = (AXIOS_INSTANCE.defaults.baseURL || process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
      const sseUrl = `${apiUrl}/v1/data-analyst/questions/${message.question_id}/stream?token=${encodeURIComponent(token)}`;
      const eventSource = new EventSource(sseUrl);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Track execution steps - check multiple possible field names
          const stageName = data.stage_name || data.stage || data.step_name || data.step;
          const userMessage = data.user_message || data.message || data.description;
          
          if (stageName) {
            const stepId = `${stageName}-${data.event_type || 'update'}`;
            
            setExecutionSteps(prev => {
              // Check if this is a completion event for an existing step
              const isCompleted = data.event_type?.includes('completed') || 
                                  data.event_type?.includes('finished') ||
                                  data.status === 'completed' ||
                                  data.progress_percentage >= 100;
              
              // Find existing step with same stage
              const existingIndex = prev.findIndex(s => s.stageName === stageName);
              
              let newSteps: LocalExecutionStepType[];
              
              if (existingIndex >= 0) {
                // Update existing step
                newSteps = [...prev];
                newSteps[existingIndex] = {
                  ...newSteps[existingIndex],
                  message: userMessage || newSteps[existingIndex].message,
                  isComplete: isCompleted || newSteps[existingIndex].isComplete,
                };
              } else {
                // Add new step with order
                newSteps = [...prev, {
                  id: stepId,
                  stageName: stageName,
                  message: userMessage || stageName,
                  timestamp: new Date(),
                  isComplete: isCompleted,
                  order: getStageOrder(stageName),
                }];
              }
              
              // Sort by order to ensure consistent display regardless of SSE arrival order
              return newSteps.sort((a, b) => a.order - b.order);
            });
            
            // Update current step indicator (use for label)
            if (!data.event_type?.includes('completed') && data.status !== 'completed') {
              setCurrentStep(userMessage || stageName);
            }
          }
        } catch (error) {
          console.error('Error parsing SSE event:', error);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
      };

      return () => {
        eventSource.close();
      };
    }
  }, [message.question_id, message.status]);
  
  // Clear execution steps when message is no longer processing
  React.useEffect(() => {
    if (message.status !== 'processing') {
      // Mark all steps as complete when done
      setExecutionSteps(prev => prev.map(step => ({ ...step, isComplete: true })));
      setCurrentStep(null);
    }
  }, [message.status]);

  // Convert local execution steps to DS ExecutionStep format
  // Steps before the current active step should be shown as completed
  const currentStepOrder = executionSteps.find(s => 
    currentStep?.includes(s.stageName) || s.stageName.includes(currentStep || '')
  )?.order ?? -1;
  
  const dsExecutionSteps: ExecutionStep[] = executionSteps.map(step => {
    // Determine status based on order relative to current step
    let status: 'pending' | 'active' | 'completed' | 'failed' = 'pending';
    
    if (step.isFailed) {
      status = 'failed';
    } else if (step.isComplete) {
      status = 'completed';
    } else if (step.order < currentStepOrder) {
      // Steps before the current step should show as completed
      status = 'completed';
    } else if (step.order === currentStepOrder || currentStep?.includes(step.stageName)) {
      status = 'active';
    }
    
    return {
      id: step.id,
      label: step.stageName,
      status,
      description: step.message,
      timestamp: step.timestamp,
    };
  });

  return (
    <div className="space-y-4">
      {/* User Question - DS MessageBubble */}
      <MessageBubble role="user" showAvatar={false}>
        <MessageContent>
          <p>{message.original_question}</p>
        </MessageContent>
      </MessageBubble>

      {/* Assistant Response - DS MessageBubble */}
      <MessageBubble role="assistant" showAvatar>
        <div className="space-y-4">
          
          {/* Processing State - DS ThinkingIndicator */}
          {message.status === 'processing' && (
            <ThinkingIndicator
              label={currentStep || "Analyzing..."}
              steps={dsExecutionSteps}
              stepsDefaultExpanded={true}
              hideAvatar={true}
            />
          )}

          {/* Clarification Needed State - DS Alert */}
          {message.status === 'clarification_needed' && message.clarification_prompt && (
            <div className="space-y-4">
              <Alert variant="warning" title="I need a bit more information:">
                {message.clarification_prompt}
              </Alert>
              
              {/* Clarification Input - using PromptBar */}
              <PromptBar
                value={clarificationResponse}
                onChange={setClarificationResponse}
                onSubmit={(value) => {
                  if (!value.trim() || isClarifying) return;
                  submitClarification(
                    {
                      questionId: message.question_id,
                      data: { clarification_response: value.trim() },
                    },
                    {
                      onSuccess: () => setClarificationResponse(''),
                      onError: (error) => console.error('Failed to submit clarification:', error),
                    }
                  );
                }}
                placeholder="Type your response..."
                loading={isClarifying}
              />
            </div>
          )}

          {/* Clarified State - DS Alert */}
          {message.status === 'clarified' && (
            <Alert variant="success" title="Clarification received">
              Your clarification has been processed. See the follow-up message below for the answer.
            </Alert>
          )}

          {/* Failed State - DS Alert */}
          {message.status === 'failed' && (
            <Alert variant="error">
              {message.sql_error || "I encountered an error processing your question. Please try rephrasing it or ask a different question."}
            </Alert>
          )}

          {/* Completed - Show Results Inline with DS Components */}
          {message.status === 'completed' && resultData && (
            <CompletedResults
              resultData={resultData}
              dataSourceType={message.data_source_type}
              originalQuestion={message.original_question}
            />
          )}
        </div>
      </MessageBubble>
    </div>
  );
}

// Separate component to avoid TypeScript inference issues
function CompletedResults({
  resultData,
  dataSourceType,
  originalQuestion,
}: {
  resultData: any;
  dataSourceType?: string;
  originalQuestion?: string;
}) {
  const [feedbackState, setFeedbackState] = useState<null | 'up' | 'down'>(null);
  const [feedbackText, setFeedbackText] = useState<string>('');
  const [isSendingFeedback, setIsSendingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const pushToast = useToasts((s) => s.push);

  const domain: string | undefined = dataSourceType || resultData?.data_source_type || resultData?.domain;
  const question: string | undefined =
    originalQuestion || resultData?.original_question || resultData?.question;
  const summary: string | undefined = resultData?.result_metadata?.summary;

  // Check if this is a RAG-based data source (FASB, knowledge_base) - these don't have structured row data
  const isRagDataSource = domain?.toLowerCase() === 'fasb' || domain?.toLowerCase() === 'knowledge_base';

  const PROMPTS_API_BASE = window.location.port === '3000'
    ? 'http://localhost:5001/api/v1/prompts'
    : '/api/v1/prompts';

  const submitFeedback = async (ratingNumeric: number, commentOverride?: string) => {
    if (!domain) return;
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    setIsSendingFeedback(true);
    setFeedbackError(null);
    try {
      const comment = (commentOverride ?? feedbackText ?? '').trim() || 'No additional comment';
      const payload = {
        environment: 'prod',
        rating_numeric: ratingNumeric,
        comment: [
          comment,
          question ? `\n\nQuestion:\n${question}` : '',
          summary ? `\n\nAnswer summary:\n${summary}` : '',
        ].join(''),
        target_components: ['answer_synthesis_prompt', 'system_prompt'],
      };

      const res = await fetch(`${PROMPTS_API_BASE}/domains/${encodeURIComponent(domain)}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setFeedbackText('');
      pushToast({ kind: 'success', message: 'Feedback sent', duration: 2500 });
    } catch (e: any) {
      setFeedbackError(e?.message || 'Failed to send feedback');
      pushToast({ kind: 'error', message: 'Failed to send feedback', duration: 6000 });
    } finally {
      setIsSendingFeedback(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Natural Language Response - using MarkdownAnswerWithSources for rich formatting */}
      {resultData.result_metadata?.summary && typeof resultData.result_metadata.summary === 'string' && (
        <MessageContent>
          <MarkdownAnswerWithSources 
            summary={resultData.result_metadata.summary} 
            questionId={resultData.question_id}
          />
        </MessageContent>
      )}

      {/* Quick feedback (prod) */}
      {domain && (
        <div className="flex items-center gap-3 pt-1">
          <span className="text-xs text-muted">Was this helpful?</span>
          <button
            type="button"
            disabled={isSendingFeedback}
            onClick={() => {
              setFeedbackState('up');
              void submitFeedback(1, '👍 Helpful');
            }}
            className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded border ${
              feedbackState === 'up' ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600' : 'border-border text-muted hover:text-text hover:bg-surface-2'
            }`}
          >
            <HandThumbUpIcon className="w-4 h-4" />
            Yes
          </button>
          <button
            type="button"
            disabled={isSendingFeedback}
            onClick={() => setFeedbackState('down')}
            className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded border ${
              feedbackState === 'down' ? 'bg-red-500/10 border-red-500/30 text-red-600' : 'border-border text-muted hover:text-text hover:bg-surface-2'
            }`}
          >
            <HandThumbDownIcon className="w-4 h-4" />
            No
          </button>
          {isSendingFeedback && <span className="text-xs text-muted">Sending…</span>}
        </div>
      )}

      {feedbackState === 'down' && domain && (
        <div className="space-y-2">
          <textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="What was wrong? (this becomes prod feedback for the current prompts)"
            className="w-full min-h-[80px] px-3 py-2 border border-border rounded-lg text-text bg-surface-2 text-sm"
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={isSendingFeedback}
              onClick={() => void submitFeedback(-1)}
              className="btn-secondary text-sm"
            >
              Send feedback
            </button>
            {feedbackError && <span className="text-xs text-red-500">{feedbackError}</span>}
          </div>
        </div>
      )}
      
      {/* No Data Found - DS Alert */}
      {resultData.result_metadata?.no_data && (
        <>
          {resultData.result_metadata?.key_findings && Array.isArray(resultData.result_metadata.key_findings) && resultData.result_metadata.key_findings.length > 0 && (
            <Alert variant="info" title="Available Data:">
              <ul className="space-y-1">
                {resultData.result_metadata.key_findings.map((finding: string, idx: number) => (
                  <li key={idx}>• {finding}</li>
                ))}
              </ul>
            </Alert>
          )}
          
          {resultData.result_metadata?.recommendations && Array.isArray(resultData.result_metadata.recommendations) && resultData.result_metadata.recommendations.length > 0 && (
            <Alert variant="info" title="Suggestions:">
              <ul className="space-y-1">
                {resultData.result_metadata.recommendations.map((rec: string, idx: number) => (
                  <li key={idx}>• {rec}</li>
                ))}
              </ul>
            </Alert>
          )}
        </>
      )}
      
      {/* Error state - DS Alert */}
      {!resultData.result_metadata?.summary && !resultData.result_metadata?.no_data && (
        <Alert variant="warning">
          Insights are being processed. If this message persists, please try your question again.
        </Alert>
      )}

      {/* Key Metrics - DS styling */}
      {resultData.result_metadata?.statistics && (
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(resultData.result_metadata.statistics).slice(0, 3).map(([col, stat]: [string, any]) => {
            if (stat?.type === 'numeric') {
              return (
                <div key={col} className="p-4 bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border/30">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">{col}</p>
                  <p className="text-2xl font-semibold text-charcoal dark:text-gray-100">{stat.mean?.toFixed(2) || 'N/A'}</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Range: {stat.min?.toFixed(2)} – {stat.max?.toFixed(2)}
                  </p>
                </div>
              );
            }
            return null;
          })}
        </div>
      )}

      {/* Charts - Opens in Canvas Panel */}
      {resultData.result_metadata?.chart_suggestions && 
       Array.isArray(resultData.result_metadata.chart_suggestions) && 
       resultData.result_metadata.chart_suggestions.length > 0 &&
       resultData.result_data && 
       (resultData.result_data as { rows?: any[] }).rows && 
       (resultData.result_data as { rows: any[] }).rows.length > 1 && (
        <div className="flex gap-3 flex-wrap">
          {resultData.result_metadata.chart_suggestions.map((suggestion: any, idx: number) => {
            const chartType = suggestion.chart_type || suggestion.type || 'bar';
            const chartTitle = suggestion.title || `${chartType.charAt(0).toUpperCase() + chartType.slice(1)} Chart`;
            const dataPoints = (resultData.result_data as { rows: any[] }).rows.length;
            
            return (
              <ArtifactButton
                key={idx}
                artifactType="chart"
                title={chartTitle}
                description={`${dataPoints} data points`}
                canvasContent={
                  <ChartCanvasViewer
                    suggestion={suggestion}
                    data={resultData.result_data as { columns: string[]; rows: any[][] }}
                    title={chartTitle}
                  />
                }
              />
            );
          })}
        </div>
      )}

      {/* Artifact Buttons - DS ArtifactButton for SQL + Data */}
      {/* Note: View Raw Data is hidden for RAG data sources (FASB) since they don't have structured row data */}
      {((!isRagDataSource && resultData.result_data) || resultData.result_metadata?.sql) && (
        <div className="flex gap-3 flex-wrap">
          {/* View Raw Data - Opens in Canvas (SQL-based sources only) */}
          {!isRagDataSource && resultData.result_data && ((resultData.result_data as { row_count?: number })?.row_count ?? 0) > 0 && (
            <ArtifactButton
              artifactType="document"
              title="View Raw Data"
              description={`${(resultData.result_data as { row_count?: number })?.row_count || 0} rows`}
              canvasContent={
                <div className="h-full w-full min-w-0 flex flex-col overflow-hidden p-4">
                  <DataTable data={resultData.result_data as { columns: string[]; rows: any[][]; row_count: number }} />
                </div>
              }
            />
          )}
          
          {/* View SQL Query - Opens in Canvas */}
          {resultData.result_metadata?.sql && typeof resultData.result_metadata.sql === 'string' && (
            <ArtifactButton
              artifactType="code"
              title="View SQL Query"
              description="Generated query"
              canvasContent={
                <div className="h-full w-full p-4">
                  <CanvasCodeBlock 
                    code={resultData.result_metadata.sql}
                    language="SQL"
                  />
                </div>
              }
            />
          )}
        </div>
      )}
    </div>
  );
}


/**
 * Minimal PDF.js viewer optimized for citation highlighting
 * - Renders only pages around the target (±2 pages for fast loading)
 * - Text layer for selection and highlighting
 * - Lazy loads PDF.js
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

// Configure worker - use jsdelivr CDN for pdfjs-dist 3.x (stable, well-supported)
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';

interface PdfPageViewerProps {
  pdfUrl: string;
  pageNumber: number;
  highlightText?: string;
  className?: string;
  pageWindow?: number; // Number of pages before/after target (default: 2)
  onLoad?: () => void;
  onError?: (error: Error) => void;
}

// Check if an error is a cancellation or worker destruction (expected during unmount)
function isExpectedCleanupError(err: unknown): boolean {
  if (err && typeof err === 'object') {
    const error = err as { name?: string; message?: string };
    const message = error.message?.toLowerCase() || '';
    const name = error.name || '';
    
    return name === 'RenderingCancelledException' || 
           message.includes('rendering cancelled') ||
           message.includes('cancelled') ||
           message.includes('worker was destroyed') ||
           message.includes('transport destroyed') ||
           message.includes('destroyed');
  }
  return false;
}

interface TextItem {
  str: string;
  transform: number[];
  width: number;
  height: number;
}

interface RenderedPage {
  pageNum: number;
  canvas: HTMLCanvasElement;
  textLayer: HTMLDivElement;
}

export default function PdfPageViewer({
  pdfUrl,
  pageNumber,
  highlightText,
  className = '',
  pageWindow = 2,
  onLoad,
  onError,
}: PdfPageViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pagesContainerRef = useRef<HTMLDivElement>(null);
  const targetPageRef = useRef<HTMLDivElement | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const [renderedPages, setRenderedPages] = useState<number[]>([]);
  const pdfDocRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null);

  // Normalize text for matching: lowercase, collapse whitespace, strip punctuation
  const normalizeText = useCallback((text: string): string => {
    return text
      .toLowerCase()
      .replace(/[\s\n\r]+/g, ' ')
      .replace(/[^\w\s]/g, '')
      .trim();
  }, []);

  /**
   * Build a character-offset map from the text layer spans, then find the
   * best-matching region of the concatenated page text against the chunk text
   * using n-gram overlap scoring on a sliding window.
   */
  const highlightMatches = useCallback((textLayer: HTMLDivElement, searchText: string): boolean => {
    if (!searchText || searchText.length < 10) return false;

    const spans = Array.from(textLayer.querySelectorAll('span'));
    if (spans.length === 0) return false;

    // 1. Build concatenated page text + char→span mapping
    const normalizedChunk = normalizeText(searchText);
    const chunkWords = normalizedChunk.split(' ').filter(w => w.length > 0);
    if (chunkWords.length === 0) return false;

    // Build a set of n-grams (bigrams + trigrams) from the chunk for fast lookup
    const chunkBigrams = new Set<string>();
    const chunkTrigrams = new Set<string>();
    for (let i = 0; i < chunkWords.length - 1; i++) {
      chunkBigrams.add(chunkWords[i] + ' ' + chunkWords[i + 1]);
      if (i < chunkWords.length - 2) {
        chunkTrigrams.add(chunkWords[i] + ' ' + chunkWords[i + 1] + ' ' + chunkWords[i + 2]);
      }
    }
    const chunkWordSet = new Set(chunkWords);

    // 2. For each span, compute how well its text matches the chunk
    interface SpanScore {
      span: HTMLSpanElement;
      score: number;
      words: string[];
    }
    const spanScores: SpanScore[] = [];

    // Build rolling window of words across spans for bigram/trigram matching
    const allSpanWords: { word: string; spanIdx: number }[] = [];
    spans.forEach((span, sIdx) => {
      const words = normalizeText(span.textContent || '').split(' ').filter(w => w.length > 0);
      words.forEach(w => allSpanWords.push({ word: w, spanIdx: sIdx }));
      spanScores.push({ span: span as HTMLSpanElement, score: 0, words });
    });

    // Score each word by checking if it appears in chunk
    for (const entry of allSpanWords) {
      if (chunkWordSet.has(entry.word)) {
        spanScores[entry.spanIdx].score += 1;
      }
    }

    // Bonus: score bigrams across adjacent span words
    for (let i = 0; i < allSpanWords.length - 1; i++) {
      const bigram = allSpanWords[i].word + ' ' + allSpanWords[i + 1].word;
      if (chunkBigrams.has(bigram)) {
        spanScores[allSpanWords[i].spanIdx].score += 2;
        spanScores[allSpanWords[i + 1].spanIdx].score += 2;
      }
    }
    for (let i = 0; i < allSpanWords.length - 2; i++) {
      const trigram = allSpanWords[i].word + ' ' + allSpanWords[i + 1].word + ' ' + allSpanWords[i + 2].word;
      if (chunkTrigrams.has(trigram)) {
        spanScores[allSpanWords[i].spanIdx].score += 3;
        spanScores[allSpanWords[i + 1].spanIdx].score += 3;
        spanScores[allSpanWords[i + 2].spanIdx].score += 3;
      }
    }

    // 3. Normalize scores by word count and find the best contiguous window
    const maxWordCount = Math.max(...spanScores.map(s => s.words.length), 1);
    spanScores.forEach(s => {
      if (s.words.length > 0) {
        s.score = s.score / Math.max(s.words.length, 1);
      }
    });

    // Find the best contiguous window of spans that covers roughly the chunk length
    const targetSpanCount = Math.min(
      Math.max(Math.ceil(chunkWords.length / 3), 3),
      spans.length
    );

    let bestStart = 0;
    let bestScore = -1;

    for (let start = 0; start <= spanScores.length - targetSpanCount; start++) {
      let windowScore = 0;
      for (let j = start; j < start + targetSpanCount; j++) {
        windowScore += spanScores[j].score;
      }
      if (windowScore > bestScore) {
        bestScore = windowScore;
        bestStart = start;
      }
    }

    // Threshold: require meaningful overlap (at least 20% average score)
    const avgScore = bestScore / targetSpanCount;
    if (avgScore < 0.2) return false;

    // 4. Highlight the best window
    const highlightStyle = 'background-color: rgba(255, 220, 100, 0.55); border-radius: 2px; padding: 1px 0;';
    for (let i = bestStart; i < bestStart + targetSpanCount && i < spanScores.length; i++) {
      if (spanScores[i].score > 0) {
        spanScores[i].span.style.cssText += highlightStyle;
      }
    }

    return true;
  }, [normalizeText]);

  // Render a single page
  const renderSinglePage = useCallback(async (
    pdfDoc: pdfjsLib.PDFDocumentProxy,
    pageNum: number,
    containerWidth: number,
    isTargetPage: boolean
  ): Promise<HTMLDivElement> => {
    const page = await pdfDoc.getPage(pageNum);
    
    // Calculate scale to fit container
    const viewport = page.getViewport({ scale: 1 });
    const fitScale = Math.min((containerWidth - 32) / viewport.width, 1.8);
    const scaledViewport = page.getViewport({ scale: fitScale });

    // Create page container
    const pageContainer = document.createElement('div');
    pageContainer.className = 'relative mb-4';
    pageContainer.setAttribute('data-page', pageNum.toString());

    // Page number label
    const pageLabel = document.createElement('div');
    pageLabel.className = 'text-xs text-center text-muted mb-2 sticky top-0 bg-gray-100 py-1 z-10';
    pageLabel.textContent = `Page ${pageNum}`;
    if (isTargetPage) {
      pageLabel.className += ' font-semibold text-brand';
      pageLabel.textContent += ' (cited)';
    }
    pageContainer.appendChild(pageLabel);

    // Canvas wrapper with shadow
    const canvasWrapper = document.createElement('div');
    canvasWrapper.className = 'relative shadow-lg mx-auto';
    canvasWrapper.style.width = `${scaledViewport.width}px`;

    // Create canvas
    const canvas = document.createElement('canvas');
    canvas.width = scaledViewport.width;
    canvas.height = scaledViewport.height;
    canvas.style.width = `${scaledViewport.width}px`;
    canvas.style.height = `${scaledViewport.height}px`;
    canvas.className = 'block';

    // Create text layer
    const textLayer = document.createElement('div');
    textLayer.className = 'absolute top-0 left-0 overflow-hidden';
    textLayer.style.width = `${scaledViewport.width}px`;
    textLayer.style.height = `${scaledViewport.height}px`;
    textLayer.style.mixBlendMode = 'multiply';
    textLayer.style.pointerEvents = 'auto';

    canvasWrapper.appendChild(canvas);
    canvasWrapper.appendChild(textLayer);
    pageContainer.appendChild(canvasWrapper);

    // Render canvas
    const ctx = canvas.getContext('2d');
    if (ctx) {
      await page.render({
        canvasContext: ctx,
        viewport: scaledViewport,
      }).promise;
    }

    // Render text layer
    const textContent = await page.getTextContent();
    textContent.items.forEach((item) => {
      const textItem = item as TextItem;
      if (!textItem.str) return;

      const span = document.createElement('span');
      span.textContent = textItem.str;
      
      const tx = textItem.transform[4] * fitScale;
      const ty = scaledViewport.height - (textItem.transform[5] * fitScale);
      const fontSize = Math.sqrt(
        textItem.transform[0] * textItem.transform[0] +
        textItem.transform[1] * textItem.transform[1]
      ) * fitScale;

      span.style.cssText = `
        position: absolute;
        left: ${tx}px;
        top: ${ty - fontSize}px;
        font-size: ${fontSize}px;
        font-family: sans-serif;
        color: transparent;
        white-space: pre;
        pointer-events: all;
        cursor: text;
      `;

      textLayer.appendChild(span);
    });

    return pageContainer;
  }, []);

  // Track if component is mounted
  const isMountedRef = useRef(true);
  const loadingTaskRef = useRef<pdfjsLib.PDFDocumentLoadingTask | null>(null);

  // Render PDF pages
  const renderPages = useCallback(async () => {
    // Check refs are available
    if (!containerRef.current || !pagesContainerRef.current) {
      return;
    }

    // Get container width before any async operations
    const containerWidth = containerRef.current.clientWidth;
    if (!containerWidth || containerWidth <= 0) {
      // Container not yet sized, retry after a short delay
      setTimeout(() => {
        if (isMountedRef.current) {
          renderPages();
        }
      }, 100);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Cancel any existing loading task
      if (loadingTaskRef.current) {
        loadingTaskRef.current.destroy();
        loadingTaskRef.current = null;
      }

      // Load PDF document
      const loadingTask = pdfjsLib.getDocument({
        url: pdfUrl,
        cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
        cMapPacked: true,
      });
      loadingTaskRef.current = loadingTask;

      const pdfDoc = await loadingTask.promise;
      
      // Check if still mounted after async operation
      if (!isMountedRef.current) {
        pdfDoc.destroy();
        return;
      }

      pdfDocRef.current = pdfDoc;
      setTotalPages(pdfDoc.numPages);

      // Calculate page range (target ± pageWindow)
      const targetPage = Math.min(Math.max(1, pageNumber), pdfDoc.numPages);
      const startPage = Math.max(1, targetPage - pageWindow);
      const endPage = Math.min(pdfDoc.numPages, targetPage + pageWindow);

      // Re-check refs after async
      if (!pagesContainerRef.current || !isMountedRef.current) {
        return;
      }

      const pagesContainer = pagesContainerRef.current;
      pagesContainer.innerHTML = '';

      const pageNums: number[] = [];
      let targetPageElement: HTMLDivElement | null = null;

      // Render each page in range
      for (let pageNum = startPage; pageNum <= endPage; pageNum++) {
        // Check if still mounted before each page render
        if (!isMountedRef.current || !pagesContainerRef.current) {
          return;
        }

        const isTargetPage = pageNum === targetPage;
        const pageElement = await renderSinglePage(pdfDoc, pageNum, containerWidth, isTargetPage);
        
        // Check again after async render
        if (!isMountedRef.current || !pagesContainerRef.current) {
          return;
        }

        pagesContainerRef.current.appendChild(pageElement);
        pageNums.push(pageNum);

        if (isTargetPage) {
          targetPageElement = pageElement;
          targetPageRef.current = pageElement;
        }
      }

      if (!isMountedRef.current) return;

      setRenderedPages(pageNums);

      // Highlight text on target page
      if (highlightText && targetPageElement) {
        const textLayer = targetPageElement.querySelector('div[style*="mix-blend-mode"]') as HTMLDivElement;
        if (textLayer) {
          setTimeout(() => {
            if (isMountedRef.current) {
              highlightMatches(textLayer, highlightText);
            }
          }, 100);
        }
      }

      // Scroll to target page
      if (targetPageElement) {
        setTimeout(() => {
          if (isMountedRef.current) {
            targetPageElement?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }, 200);
      }

      setIsLoading(false);
      onLoad?.();

    } catch (err) {
      // Ignore expected cleanup errors (cancellation, worker destroyed, etc.)
      if (isExpectedCleanupError(err)) {
        // Silently ignore - this is expected during unmount or rapid re-renders
        return;
      }
      
      // Only update state if still mounted
      if (isMountedRef.current) {
        console.error('PDF render error:', err);
        setError(err instanceof Error ? err.message : 'Failed to load PDF');
        setIsLoading(false);
        onError?.(err instanceof Error ? err : new Error('Failed to load PDF'));
      }
    }
  }, [pdfUrl, pageNumber, pageWindow, highlightText, renderSinglePage, highlightMatches, onLoad, onError]);

  // Set mounted ref on mount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Render on mount and when props change
  useEffect(() => {
    // Small delay to ensure container is ready (helps with StrictMode double-mount)
    const timeoutId = setTimeout(() => {
      if (isMountedRef.current) {
        renderPages();
      }
    }, 50);

    return () => {
      clearTimeout(timeoutId);
      
      // Cancel any pending loading task (wrapped in try-catch as it might already be destroyed)
      if (loadingTaskRef.current) {
        try {
          loadingTaskRef.current.destroy();
        } catch {
          // Ignore - already destroyed
        }
        loadingTaskRef.current = null;
      }
      // Destroy PDF document (wrapped in try-catch)
      if (pdfDocRef.current) {
        try {
          pdfDocRef.current.destroy();
        } catch {
          // Ignore - already destroyed
        }
        pdfDocRef.current = null;
      }
    };
  }, [renderPages]);

  return (
    <div 
      ref={containerRef} 
      className={`relative overflow-auto bg-gray-100 ${className}`}
    >
      {/* Loading state */}
      {isLoading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface z-20">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-4 border-border border-t-brand animate-spin" />
          </div>
          <p className="mt-4 text-sm text-muted animate-pulse">Loading pages...</p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-surface z-20">
          <p className="text-sm text-red-500">{error}</p>
          <button
            onClick={renderPages}
            className="mt-2 px-4 py-2 text-sm bg-brand text-white rounded hover:bg-brand/90"
          >
            Retry
          </button>
        </div>
      )}

      {/* Page info */}
      {!isLoading && !error && totalPages > 0 && (
        <div className="sticky top-0 z-30 bg-gray-200/90 backdrop-blur-sm px-4 py-2 text-xs text-center text-muted border-b border-gray-300">
          Showing pages {renderedPages[0]}-{renderedPages[renderedPages.length - 1]} of {totalPages}
          {renderedPages.length < totalPages && (
            <span className="ml-2 text-brand">(use "Open in new tab" for full document)</span>
          )}
        </div>
      )}

      {/* Pages container */}
      <div ref={pagesContainerRef} className="p-4" />
    </div>
  );
}

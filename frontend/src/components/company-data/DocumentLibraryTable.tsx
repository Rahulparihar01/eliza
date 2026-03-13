import React, { useMemo } from 'react';
import {
  ArrowUpTrayIcon,
  CheckCircleIcon,
  ClockIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  InboxStackIcon,
  SparklesIcon,
  TagIcon,
} from '@heroicons/react/24/outline';
import type { KeyboardEvent } from 'react';
import type { DocumentInfo } from '../../generated/models/documentInfo';
import { Tooltip } from '../common/Tooltip';

interface DocumentLibraryListProps {
  recentDocuments: DocumentInfo[];
  documents: DocumentInfo[];
  isLoading: boolean;
  isRecentLoading: boolean;
  totalDocuments: number;
  displayTotal: number;
  page: number;
  pageSize: number;
  onPageChange?: (page: number) => void;
  onRequestUpload?: () => void;
  selectedDocumentId?: number | null;
  onSelectDocument?: (document: DocumentInfo) => void;
}

export function formatFileSize(bytes: number | undefined | null) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export function formatDateTime(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelativeTime(dateString: string) {
  const date = new Date(dateString);
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  if (Number.isNaN(diffMinutes)) {
    return '-';
  }
  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return <CheckCircleIcon className="w-4 h-4 text-ai-success" />;
    case 'processing':
    case 'uploaded':
      return <ClockIcon className="w-4 h-4 text-ai-warning animate-pulse" />;
    case 'failed':
      return <ExclamationTriangleIcon className="w-4 h-4 text-ai-danger" />;
    default:
      return <DocumentTextIcon className="w-4 h-4 text-muted" />;
  }
}

function buildTooltipContent(document: DocumentInfo) {
  const metadata = (document.document_metadata ?? {}) as Record<string, unknown>;
  const dataset = document.company_hr_dataset ?? (metadata['company_hr_dataset'] as string | undefined);
  const dataSource = metadata['data_source_type'] as string | undefined;
  const chunkStrategy = document.chunking_strategy;
  const qaRag = document.qa_rag_enabled ? 'Enabled' : 'Disabled';

  const rows: Array<[string, string | number | undefined]> = [
    ['Status', document.status],
    ['Dataset', dataset || 'Default'],
    ['Source', dataSource || '-'],
    ['Chunks', document.total_chunks ?? 0],
    ['Duplicates', document.duplicate_chunks_count ?? 0],
    ['QA-RAG', qaRag],
    ['Uploaded', formatDateTime(document.created_at)],
    ['Chunking', chunkStrategy],
  ];

  if (document.quality_score !== null && document.quality_score !== undefined) {
    rows.push(['Quality', `${(document.quality_score * 100).toFixed(0)}%`]);
  }

  return (
    <div className="space-y-1">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-start gap-3">
          <span className="text-gray-300 text-xs uppercase tracking-wide">{label}</span>
          <span className="text-white text-sm font-medium break-all">{value ?? '-'}</span>
        </div>
      ))}
    </div>
  );
}

interface DocumentListItemProps {
  document: DocumentInfo;
  recent?: boolean;
  selected?: boolean;
  onSelect?: (document: DocumentInfo) => void;
}

function DocumentListItem({
  document,
  recent,
  selected,
  onSelect,
}: DocumentListItemProps) {
  const metadata = (document.document_metadata ?? {}) as Record<string, unknown>;
  const dataset = document.company_hr_dataset ?? (metadata['company_hr_dataset'] as string | undefined);
  const dataSource = metadata['data_source_type'] as string | undefined;

  const metadataPreview = [
    {
      icon: <InboxStackIcon className="w-3.5 h-3.5 text-muted" />,
      label: 'Size',
      value: formatFileSize(document.file_size),
    },
    {
      icon: <SparklesIcon className="w-3.5 h-3.5 text-muted" />,
      label: 'Quality',
      value:
        document.quality_score !== null && document.quality_score !== undefined
          ? `${(document.quality_score * 100).toFixed(0)}%`
          : '—',
    },
    {
      icon: <ClockIcon className="w-3.5 h-3.5 text-muted" />,
      label: 'Uploaded',
      value: formatRelativeTime(document.created_at),
    },
    {
      icon: <DocumentTextIcon className="w-3.5 h-3.5 text-muted" />,
      label: 'Type',
      value: document.mime_type || 'Unknown',
    },
  ];

  const tooltipContent = buildTooltipContent(document);
  const handleSelect = () => {
    if (onSelect) {
      onSelect(document);
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!onSelect) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(document);
    }
  };

  const classes = [
    'relative overflow-hidden px-4 py-3 text-left transition-all rounded-xl mx-2 my-1',
    recent ? 'bg-eliza-red/5' : 'bg-white dark:bg-dark-surface',
    selected
      ? 'ring-1 ring-eliza-red/40 bg-eliza-red/10'
      : 'hover:bg-gray-50 dark:hover:bg-dark-surface-2',
    onSelect ? 'cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red/50' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={onSelect ? handleSelect : undefined}
      onKeyDown={onSelect ? handleKeyDown : undefined}
      aria-selected={selected}
      data-selected={selected ? 'true' : undefined}
      className={classes}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="flex-shrink-0 mt-1">{getStatusIcon(document.status)}</div>
        <div className="flex-1 min-w-0">
            <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-3 items-start">
                <div className="min-w-0">
                  <div className="flex items-center flex-wrap gap-2 min-w-0">
                    <span className="ui-item-title block truncate text-sm font-medium text-charcoal dark:text-gray-100">
                      {document.original_filename || document.filename}
                    </span>
                    {dataset && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 dark:bg-dark-surface-2 border border-gray-200/50 dark:border-dark-border/50 px-2 py-0.5 text-[10px] font-medium text-gray-500 dark:text-gray-400">
                        <TagIcon className="w-3 h-3" />
                        {dataset}
                      </span>
                    )}
                    {dataSource && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 dark:bg-dark-surface-2 border border-gray-200/50 dark:border-dark-border/50 px-2 py-0.5 text-[10px] font-medium text-gray-500 dark:text-gray-400">
                        {dataSource}
                      </span>
                    )}
                    {recent && (
                      <span className="inline-flex items-center rounded-full bg-eliza-red/10 text-eliza-red border border-eliza-red/20 text-[10px] font-semibold px-2 py-0.5">
                        New
                      </span>
                    )}
                  </div>
                </div>
                <Tooltip
                  position="top-right"
                  content={tooltipContent}
                  className="col-start-2 justify-self-end inline-flex flex-shrink-0"
                >
                  <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                    {metadataPreview.map((item) => (
                      <span key={item.label} className="inline-flex items-center gap-1">
                        {item.icon}
                        <span className="text-charcoal dark:text-gray-100 font-semibold">{item.value}</span>
                      </span>
                    ))}
                  </div>
                </Tooltip>
              </div>
        </div>
      </div>
    </div>
  );
}

function DocumentSkeleton({ count, recent }: { count: number; recent?: boolean }) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={`skeleton-${recent ? 'recent' : 'regular'}-${index}`}
          className={`px-4 py-3 mx-2 my-1 rounded-xl ${recent ? 'bg-eliza-red/5' : 'bg-white dark:bg-dark-surface'}`}
        >
          <div className="flex items-center gap-3 animate-pulse">
            <div className="w-4 h-4 rounded-full bg-gray-100 dark:bg-dark-surface-2" />
            <div className="flex-1 min-w-0 space-y-2">
              <div className="h-4 bg-gray-100 dark:bg-dark-surface-2 rounded-lg w-2/3" />
              <div className="h-3 bg-gray-100 dark:bg-dark-surface-2 rounded-lg w-1/3" />
            </div>
            <div className="flex gap-2">
              <div className="h-3 bg-gray-100 dark:bg-dark-surface-2 rounded-lg w-12" />
              <div className="h-3 bg-gray-100 dark:bg-dark-surface-2 rounded-lg w-10" />
            </div>
          </div>
        </div>
      ))}
    </>
  );
}

function ListSectionLabel({
  title,
  count,
  className,
}: {
  title: string;
  count?: number;
  className?: string;
}) {
  const baseClasses =
    'flex items-center justify-between gap-2 min-w-0 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500/70 dark:text-gray-400/70';
  return (
    <div className={className ? `${baseClasses} ${className}` : baseClasses}>
      <span className="truncate">{title}</span>
      {typeof count !== 'undefined' && count !== null && (
        <span className="inline-flex items-center justify-center rounded-full bg-gray-100 dark:bg-dark-surface-2 border border-gray-200/50 dark:border-dark-border/50 text-[10px] font-medium text-gray-500 dark:text-gray-400 px-2 py-0.5">
          {count}
        </span>
      )}
    </div>
  );
}

export default function DocumentLibraryList({
  recentDocuments,
  documents,
  isLoading,
  isRecentLoading,
  totalDocuments,
  displayTotal,
  page,
  pageSize,
  onPageChange,
  onRequestUpload,
  selectedDocumentId,
  onSelectDocument,
}: DocumentLibraryListProps) {
  const hasRecent = recentDocuments.length > 0;
  const showSkeleton = isLoading && documents.length === 0;
  const showRecentSkeleton = isRecentLoading && recentDocuments.length === 0;
  const isEmpty = !showSkeleton && !showRecentSkeleton && !hasRecent && documents.length === 0;

  const pageCount = useMemo(() => {
    if (totalDocuments === 0) return 1;
    return Math.max(1, Math.ceil(totalDocuments / pageSize));
  }, [pageSize, totalDocuments]);

  const canGoPrev = page > 1;
  const canGoNext = page < pageCount;

  return (
    <div className="flex flex-col h-full min-h-[360px] bg-gray-50 dark:bg-dark-bg">
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain scroll-slim ios-momentum">
        <div className="py-2">
          {!showSkeleton && !showRecentSkeleton && hasRecent && (
            <ListSectionLabel title="Recent uploads" count={recentDocuments.length} />
          )}

          {showRecentSkeleton && <DocumentSkeleton count={3} recent />}

          {!showRecentSkeleton &&
            recentDocuments.map((document) => (
              <DocumentListItem
                key={`recent-${document.id}`}
                document={document}
                recent
                selected={document.id === selectedDocumentId}
                onSelect={onSelectDocument}
              />
            ))}

          {!showSkeleton && (documents.length > 0 || hasRecent) && (
            <ListSectionLabel title="All documents" count={displayTotal} />
          )}

          {showSkeleton && <DocumentSkeleton count={5} />}

          {!showSkeleton &&
            documents.map((document) => (
              <DocumentListItem
                key={`doc-${document.id}`}
                document={document}
                selected={document.id === selectedDocumentId}
                onSelect={onSelectDocument}
              />
            ))}

          {isEmpty && (
            <div className="px-6 py-16 text-center space-y-4">
              <div className="p-4 rounded-2xl bg-gray-100 dark:bg-dark-surface-2 inline-block">
                <DocumentTextIcon className="w-10 h-10 text-gray-400 dark:text-gray-500" />
              </div>
              <div>
                <p className="text-sm text-gray-500 dark:text-gray-400">No documents found</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Upload your first document to get started</p>
              </div>
              {onRequestUpload && (
                <button
                  onClick={onRequestUpload}
                  className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-eliza-red hover:bg-eliza-red-light rounded-full transition-colors"
                >
                  <ArrowUpTrayIcon className="w-4 h-4" />
                  Upload document
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {pageCount > 1 && documents.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-200/30 dark:border-dark-border/30 bg-gray-50 dark:bg-dark-bg flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Page {page} of {pageCount}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => onPageChange?.(page - 1)}
              disabled={!canGoPrev}
              className="px-3 py-1.5 text-xs font-medium bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 rounded-full hover:bg-gray-50 dark:hover:bg-dark-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange?.(page + 1)}
              disabled={!canGoNext}
              className="px-3 py-1.5 text-xs font-medium bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 rounded-full hover:bg-gray-50 dark:hover:bg-dark-surface-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

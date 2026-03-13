import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  EyeIcon,
  TagIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { MouseEvent } from 'react';
import type { DocumentInfo } from '../../generated/models/documentInfo';
import { Tooltip } from '../common/Tooltip';
import {
  formatDateTime,
  formatFileSize,
  formatRelativeTime,
  getStatusIcon,
} from './DocumentLibraryTable';

interface DocumentDetailPaneProps {
  document: DocumentInfo;
  onDownload?: (document: DocumentInfo) => void;
  onRetry?: (document: DocumentInfo) => void;
  onDelete?: (document: DocumentInfo) => void;
  onView?: (document: DocumentInfo) => void;
  retryIsPending?: boolean;
  deleteIsPending?: boolean;
}

const STATUS_STYLES: Record<string, { label: string; classes: string }> = {
  completed: { label: 'Completed', classes: 'bg-green-500/10 text-green-500' },
  processing: { label: 'Processing', classes: 'bg-amber-500/10 text-amber-500' },
  uploaded: { label: 'Queued', classes: 'bg-amber-500/10 text-amber-500' },
  failed: { label: 'Failed', classes: 'bg-red-500/10 text-red-500' },
  default: { label: 'Unknown', classes: 'bg-white dark:bg-dark-surface text-charcoal dark:text-gray-100' },
};

const formatNumber = (value: number | null | undefined) => {
  if (value === null || value === undefined) {
    return '—';
  }
  return value.toLocaleString();
};

const prettifyLabel = (label: string) =>
  label
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => (word ? word[0]?.toUpperCase() + word.slice(1) : ''))
    .join(' ');

const formatMetadataValue = (value: unknown) => {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value.toString();
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return String(value);
  }
};

export function DocumentDetailPane({
  document,
  onDownload,
  onRetry,
  onDelete,
  onView,
  retryIsPending,
  deleteIsPending,
}: DocumentDetailPaneProps) {
  const metadata = (document.document_metadata ?? {}) as Record<string, unknown>;
  const dataset = document.company_hr_dataset ?? (metadata['company_hr_dataset'] as string | undefined);
  const dataSource = metadata['data_source_type'] as string | undefined;
  const statusStyle = STATUS_STYLES[document.status] ?? STATUS_STYLES.default;

  const metadataEntries = Object.entries(metadata).filter(([key, value]) => {
    if (key === 'company_hr_dataset' || key === 'data_source_type') {
      return false;
    }
    if (value === null || value === undefined) {
      return false;
    }
    if (typeof value === 'string' && value.trim().length === 0) {
      return false;
    }
    return true;
  });

  const createActionHandler = (
    callback?: (doc: DocumentInfo) => void
  ) =>
    (event: MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      callback?.(document);
    };

  const infoGrid: Array<{ label: string; value: string }> = [
    { label: 'File size', value: formatFileSize(document.file_size) },
    { label: 'File type', value: document.mime_type || '—' },
    { label: 'Chunking strategy', value: document.chunking_strategy || '—' },
    { label: 'QA RAG', value: document.qa_rag_enabled ? 'Enabled' : 'Disabled' },
    { label: 'Total chunks', value: formatNumber(document.total_chunks) },
    { label: 'Duplicate chunks', value: formatNumber(document.duplicate_chunks_count) },
    { label: 'QA pairs generated', value: formatNumber(document.qa_pairs_generated) },
    { label: 'Total characters', value: formatNumber(document.total_characters) },
    {
      label: 'Quality score',
      value:
        document.quality_score !== null && document.quality_score !== undefined
          ? `${(document.quality_score * 100).toFixed(0)}%`
          : '—',
    },
    { label: 'Customer', value: document.customer_id || '—' },
  ];

  const uploadedAt = formatDateTime(document.created_at);
  const uploadedRelative = formatRelativeTime(document.created_at);
  const processedAt = document.processing_completed_at ? formatDateTime(document.processing_completed_at) : '—';

  return (
    <div className="flex flex-col min-h-0 bg-white dark:bg-dark-surface">
      {/* Header */}
      <div className="px-6 py-5 border-b border-gray-200/30 dark:border-dark-border/30">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-eliza-red/10">
                <DocumentTextIcon className="w-4 h-4 text-eliza-red" />
              </div>
              <span className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Document Details</span>
            </div>
            <h2 className="text-lg font-semibold text-charcoal dark:text-gray-100 leading-snug break-words">
              {document.original_filename || document.filename}
            </h2>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="px-2 py-1 rounded-lg bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-xs text-gray-500 dark:text-gray-400">
                ID: <code className="text-[10px] font-mono text-charcoal dark:text-gray-100">{document.id}</code>
              </span>
              {dataset && (
                <span className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-lg bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-gray-500 dark:text-gray-400">
                  <TagIcon className="w-3 h-3" />
                  {dataset}
                </span>
              )}
              {dataSource && (
                <span className="px-2 py-1 rounded-lg bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-[10px] text-gray-500 dark:text-gray-400">
                  {dataSource}
                </span>
              )}
            </div>
          </div>
          <div
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${statusStyle.classes}`}
          >
            {getStatusIcon(document.status)}
            <span>{statusStyle.label}</span>
          </div>
        </div>
        
        {/* Timestamps */}
        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
          <span>
            Uploaded {uploadedAt}
            <span className="text-gray-400 dark:text-gray-500"> · {uploadedRelative}</span>
          </span>
          {document.processing_completed_at && (
            <>
              <span className="text-gray-400/30 dark:text-gray-500/30">•</span>
              <span>Processed {processedAt}</span>
            </>
          )}
        </div>
        
        {/* Action Buttons */}
        {(onView || onDownload || onRetry || onDelete) && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {onView && (
              <button
                type="button"
                onClick={createActionHandler(onView)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
              >
                <EyeIcon className="w-3.5 h-3.5" />
                Preview
              </button>
            )}
            {onDownload && (
              <button
                type="button"
                onClick={createActionHandler(onDownload)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
              >
                <ArrowDownTrayIcon className="w-3.5 h-3.5" />
                Download
              </button>
            )}
            {onRetry && document.status === 'failed' && (
              <button
                type="button"
                onClick={createActionHandler(onRetry)}
                disabled={retryIsPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-500 hover:bg-amber-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ArrowPathIcon className={`w-3.5 h-3.5 ${retryIsPending ? 'animate-spin' : ''}`} />
                Retry
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={createActionHandler(onDelete)}
                disabled={deleteIsPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-red-500/10 border border-red-500/30 text-red-500 hover:bg-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <TrashIcon className="w-3.5 h-3.5" />
                Delete
              </button>
            )}
          </div>
        )}
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 min-h-0 overflow-y-auto overscroll-y-auto scroll-slim ios-momentum">
        <div className="px-6 py-5 space-y-6">
          {/* Summary Section */}
          <section className="space-y-4">
            <SectionTitle title="Summary" description="Key properties and processing metrics" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {infoGrid.map((item) => (
                <InfoItem key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
          </section>

          {/* Timestamps Section */}
          <section className="space-y-4">
            <SectionTitle title="Timestamps" description="Lifecycle events" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <InfoItem label="Uploaded" value={uploadedAt} hint={uploadedRelative} />
              <InfoItem label="Processing completed" value={processedAt} />
            </div>
          </section>

          {/* Metadata Section */}
          <section className="space-y-4">
            <SectionTitle title="Metadata" description="Additional attributes" />
            {metadataEntries.length === 0 ? (
              <p className="text-sm text-gray-500/70 dark:text-gray-400/70">No additional metadata captured for this document.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {metadataEntries.map(([key, value]) => {
                  const formatted = formatMetadataValue(value);
                  const isMultiline = typeof formatted === 'string' && formatted.includes('\n');
                  return (
                    <div key={key} className={`p-3 rounded-xl bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 ${isMultiline ? 'sm:col-span-2' : ''}`}>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block mb-1">
                        {prettifyLabel(key)}
                      </span>
                      {isMultiline ? (
                        <pre className="text-xs text-charcoal dark:text-gray-100 whitespace-pre-wrap break-words font-mono leading-relaxed">
                          {formatted}
                        </pre>
                      ) : (
                        <span className="text-sm text-charcoal dark:text-gray-100 break-words">{formatted}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

interface SectionTitleProps {
  title: string;
  description?: string;
}

function SectionTitle({ title, description }: SectionTitleProps) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-charcoal dark:text-gray-100">{title}</p>
      {description && <p className="text-[10px] text-gray-400 dark:text-gray-500">{description}</p>}
    </div>
  );
}

interface InfoItemProps {
  label: string;
  value: string;
  hint?: string;
}

function InfoItem({ label, value, hint }: InfoItemProps) {
  return (
    <div className="p-3 rounded-xl bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 block mb-1">{label}</span>
      <span className="text-sm text-charcoal dark:text-gray-100 break-words">{value}</span>
      {hint && <span className="text-[10px] text-gray-400 dark:text-gray-500 block mt-0.5">{hint}</span>}
    </div>
  );
}

export default DocumentDetailPane;

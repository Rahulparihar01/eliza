import React, { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ChartBarIcon,
  CheckCircleIcon,
  ClockIcon,
  DocumentTextIcon,
  EllipsisHorizontalIcon,
  ExclamationTriangleIcon,
  FunnelIcon,
  InboxStackIcon,
  MagnifyingGlassIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { Dialog, Menu, Transition } from '@headlessui/react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Layout } from '../../components/layout/Layout';
import {
  DocumentUploadPanel,
  type DocumentUploadSurfaceHandle,
} from '../../components/company-data/DocumentUploadModal';
import DocumentLibraryList from '../../components/company-data/DocumentLibraryTable';
import DocumentDetailPane from '../../components/company-data/DocumentDetailPane';
import { useToasts } from '../../stores/useToasts';
import { Tooltip } from '../../components/common/Tooltip';
import {
  useDeleteDocumentV1DocumentsDocumentIdDelete,
  useListDocumentsV1DocumentsGet,
  useRetryDocumentProcessingV1DocumentsDocumentIdRetryPost,
  useGetDocumentStatsV1DocumentsStatsGet,
} from '../../generated/documents/documents';
import { queryKeys } from '../../lib/query-keys';
import type { DocumentInfo } from '../../generated/models/documentInfo';
import type { DocumentStatus } from '../../generated/models/documentStatus';
import { AXIOS_INSTANCE } from '../../services/api-client';

const STATUS_FILTERS: Array<{ value: 'all' | DocumentStatus; label: string }> = [
  { value: 'all', label: 'All status' },
  { value: 'completed', label: 'Completed' },
  { value: 'processing', label: 'Processing' },
  { value: 'failed', label: 'Failed' },
  { value: 'uploaded', label: 'Queued' },
];

const SORT_OPTIONS: Array<{ value: 'created_at' | 'filename' | 'file_size'; label: string }> = [
  { value: 'created_at', label: 'Uploaded' },
  { value: 'filename', label: 'Name' },
  { value: 'file_size', label: 'Size' },
];

const MIN_LIST_WIDTH = 280;
const MAX_LIST_WIDTH = 960;
const MIN_DETAIL_WIDTH = 320;

const formatCount = (value: number | undefined | null) => {
  if (value === null || value === undefined) {
    return '0';
  }
  return value.toLocaleString();
};

export default function KnowledgeBase() {
  const { push: addToast } = useToasts();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const uploadPanelRef = useRef<DocumentUploadSurfaceHandle>(null);
  const [uploadPanelOpen, setUploadPanelOpen] = useState(false);
  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('7d');
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<'all' | DocumentStatus>('all');
  const [sourceFilter, setSourceFilter] = useState<'all' | string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'created_at' | 'filename' | 'file_size'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    isOpen: boolean;
    document: DocumentInfo | null;
  }>({ isOpen: false, document: null });

  const splitRef = useRef<HTMLDivElement>(null);
  const [listWidth, setListWidth] = useState(520);
  const [isDraggingDivider, setIsDraggingDivider] = useState(false);
  const [isDividerHovered, setIsDividerHovered] = useState(false);

  const clamp = useCallback((value: number, min: number, max: number) => Math.min(Math.max(value, min), max), []);

  const { data: stats, isLoading: statsLoading } = useGetDocumentStatsV1DocumentsStatsGet(
    { range: timeRange },
    {
      query: {
        queryKey: queryKeys.companyData.stats(timeRange),
        staleTime: 30000,
      },
    }
  );

  const twentyFourHoursAgo = useMemo(
    () => new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    []
  );

  const { data: recentData, isLoading: recentLoading } = useListDocumentsV1DocumentsGet(
    {
      limit: 100,
      created_after: twentyFourHoursAgo,
      sort: '-created_at',
    },
    {
      query: {
        queryKey: queryKeys.companyData.recentUploads(),
        staleTime: 2000,
      },
    }
  );

  const sortParam = useMemo(() => (sortOrder === 'desc' ? `-${sortBy}` : sortBy), [sortBy, sortOrder]);

  const { data: documentsResponse, isLoading: documentsLoading } = useListDocumentsV1DocumentsGet(
    {
      ...(statusFilter !== 'all' ? { status: statusFilter as DocumentStatus } : {}),
      limit: pageSize,
      offset: (page - 1) * pageSize,
      sort: sortParam,
    },
    {
      query: {
        queryKey: queryKeys.documents.list({ status: statusFilter, sort: sortBy, order: sortOrder, page }),
        staleTime: 30000,
      },
    }
  );

  const documents = useMemo(() => documentsResponse?.documents ?? [], [documentsResponse?.documents]);
  const totalDocuments = documentsResponse?.total ?? 0;
  const recentUploads = useMemo(() => recentData?.documents ?? [], [recentData?.documents]);

  const normalizedSearch = useMemo(() => searchQuery.trim().toLowerCase(), [searchQuery]);

  const matchesFilters = useCallback(
    (doc: DocumentInfo) => {
      if (statusFilter !== 'all' && doc.status !== statusFilter) {
        return false;
      }

      if (sourceFilter !== 'all') {
        const metadata = (doc.document_metadata ?? {}) as Record<string, unknown>;
        const dataSource = metadata['data_source_type'];
        if (dataSource !== sourceFilter) {
          return false;
        }
      }

      if (!normalizedSearch) {
        return true;
      }

      const haystack = `${doc.original_filename ?? ''} ${doc.filename ?? ''}`.toLowerCase();
      return haystack.includes(normalizedSearch);
    },
    [normalizedSearch, sourceFilter, statusFilter]
  );

  const filteredRecent = useMemo(
    () => recentUploads.filter(matchesFilters),
    [recentUploads, matchesFilters]
  );

  const filteredDocuments = useMemo(
    () => documents.filter(matchesFilters),
    [documents, matchesFilters]
  );

  const recentIds = useMemo(
    () => new Set(filteredRecent.map((doc) => doc.id)),
    [filteredRecent]
  );

  const regularDocuments = useMemo(
    () => filteredDocuments.filter((doc) => !recentIds.has(doc.id)),
    [filteredDocuments, recentIds]
  );

  const orderedDocuments = useMemo(
    () => [...filteredRecent, ...regularDocuments],
    [filteredRecent, regularDocuments]
  );

  useEffect(() => {
    if (orderedDocuments.length === 0) {
      if (selectedDocumentId !== null) {
        setSelectedDocumentId(null);
      }
      return;
    }
    if (selectedDocumentId === null || !orderedDocuments.some((doc) => doc.id === selectedDocumentId)) {
      setSelectedDocumentId(orderedDocuments[0].id);
    }
  }, [orderedDocuments, selectedDocumentId]);

  const selectedDocument = useMemo(
    () => orderedDocuments.find((doc) => doc.id === selectedDocumentId) ?? null,
    [orderedDocuments, selectedDocumentId]
  );

  const availableSources = useMemo(() => {
    const sourceSet = new Set<string>();
    [...recentUploads, ...documents].forEach((doc) => {
      const metadata = (doc.document_metadata ?? {}) as Record<string, unknown>;
      const dataSource = metadata['data_source_type'];
      if (typeof dataSource === 'string' && dataSource.trim().length > 0) {
        sourceSet.add(dataSource);
      }
    });
    return Array.from(sourceSet).sort();
  }, [recentUploads, documents]);

  const displayTotal = filteredRecent.length + regularDocuments.length;

  const handleSelectDocument = useCallback((doc: DocumentInfo) => {
    setSelectedDocumentId(doc.id);
  }, []);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setPage(1);
  };

  const handleStatusChange = (value: 'all' | DocumentStatus) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleSourceChange = (value: 'all' | string) => {
    setSourceFilter(value);
    setPage(1);
  };

  const handleSortChange = (field: 'created_at' | 'filename' | 'file_size') => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const handleView = (doc: DocumentInfo) => {
    setSelectedDocumentId(doc.id);
    addToast({
      kind: 'info',
      message: `Preview for ${doc.original_filename || doc.filename} coming soon.`,
      duration: 4000,
    });
  };

  const handleRetry = (doc: DocumentInfo) => {
    retryDocument({ documentId: doc.id });
  };

  const handlePageChange = (nextPage: number) => {
    const maxPage = Math.max(1, Math.ceil(totalDocuments / pageSize));
    if (nextPage < 1 || nextPage > maxPage) {
      return;
    }
    setPage(nextPage);
  };

  useLayoutEffect(() => {
    const container = splitRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    if (rect.width <= 0) return;
    const maxAllowed = Math.max(MIN_LIST_WIDTH, rect.width - MIN_DETAIL_WIDTH);
    setListWidth((current) => clamp(current, MIN_LIST_WIDTH, Math.min(MAX_LIST_WIDTH, maxAllowed)));
  }, [clamp, orderedDocuments.length, uploadPanelOpen]);

  useEffect(() => {
    const handleResize = () => {
      const container = splitRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      if (rect.width <= 0) return;
      const maxAllowed = Math.max(MIN_LIST_WIDTH, rect.width - MIN_DETAIL_WIDTH);
      setListWidth((current) => clamp(current, MIN_LIST_WIDTH, Math.min(MAX_LIST_WIDTH, maxAllowed)));
    };

    window.addEventListener('resize', handleResize);
    handleResize();
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [clamp]);

  useEffect(() => {
    if (!isDraggingDivider) {
      return;
    }

    const handlePointerMove = (event: PointerEvent) => {
      const container = splitRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const proposed = event.clientX - rect.left;
      const maxAllowed = Math.max(MIN_LIST_WIDTH, rect.width - MIN_DETAIL_WIDTH);
      const width = clamp(proposed, MIN_LIST_WIDTH, Math.min(MAX_LIST_WIDTH, maxAllowed));
      setListWidth(width);
    };

    const handlePointerUp = () => {
      setIsDraggingDivider(false);
      setIsDividerHovered(false);
    };

    const body = document.body;
    const previousUserSelect = body ? body.style.userSelect : '';
    if (body) {
      body.style.userSelect = 'none';
    }

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
    document.addEventListener('pointercancel', handlePointerUp);

    return () => {
      if (body) {
        body.style.userSelect = previousUserSelect;
      }
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
      document.removeEventListener('pointercancel', handlePointerUp);
    };
  }, [clamp, isDraggingDivider]);

  const handleDividerPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) {
      return;
    }
    event.preventDefault();
    setIsDividerHovered(true);
    setIsDraggingDivider(true);
  };

  const handleToggleUploadPanel = () => {
    if (uploadPanelOpen) {
      uploadPanelRef.current?.requestClose();
    } else {
      setUploadPanelOpen(true);
    }
  };

  const handleUploadPanelClose = () => {
    setUploadPanelOpen(false);
  };

  const handleUploadComplete = (uploadId?: string) => {
    if (uploadId) {
      setSelectedDocumentId(null);
    }
    queryClient.invalidateQueries({ queryKey: queryKeys.companyData.recentUploads() });
    queryClient.invalidateQueries({ queryKey: queryKeys.documents.lists() });
    queryClient.invalidateQueries({ queryKey: queryKeys.companyData.stats(timeRange) });
  };

  const { mutate: deleteDocument, isPending: deleteIsPending } = useDeleteDocumentV1DocumentsDocumentIdDelete({
    mutation: {
      onMutate: async (variables) => {
        const documentId = variables.documentId;
        await queryClient.cancelQueries({ queryKey: queryKeys.documents.lists() });
        const queryKey = queryKeys.documents.list({ status: statusFilter, sort: sortBy, order: sortOrder, page });
        const previousDocuments = queryClient.getQueryData(queryKey);
        queryClient.setQueryData(queryKey, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            documents: old.documents.filter((doc: DocumentInfo) => doc.id !== documentId),
            total: Math.max(0, (old.total || 0) - 1),
          };
        });
        return { previousDocuments, queryKey };
      },
      onSuccess: () => {
        addToast({
          kind: 'success',
          message: 'Document has been successfully deleted.',
          duration: 5000,
        });
        setDeleteConfirmation({ isOpen: false, document: null });
        queryClient.invalidateQueries({ queryKey: queryKeys.documents.lists() });
        queryClient.invalidateQueries({ queryKey: queryKeys.companyData.recentUploads() });
      },
      onError: (error: any, _variables, context: any) => {
        if (context?.previousDocuments && context?.queryKey) {
          queryClient.setQueryData(context.queryKey, context.previousDocuments);
        }
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Failed to delete document. Please try again.',
          duration: 8000,
        });
      },
    },
  });

  const { mutate: retryDocument, isPending: retryIsPending } = useRetryDocumentProcessingV1DocumentsDocumentIdRetryPost({
    mutation: {
      onSuccess: () => {
        addToast({
          kind: 'success',
          message: 'Document is being reprocessed. Please wait...',
          duration: 5000,
        });
        queryClient.invalidateQueries({ queryKey: queryKeys.documents.lists() });
        queryClient.invalidateQueries({ queryKey: queryKeys.companyData.recentUploads() });
      },
      onError: (error: any) => {
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Failed to retry document processing. Please try again.',
          duration: 8000,
        });
      },
    },
  });

  const handleDeleteRequest = (doc: DocumentInfo) => {
    setDeleteConfirmation({ isOpen: true, document: doc });
  };

  const confirmDelete = () => {
    if (!deleteConfirmation.document) return;
    deleteDocument({ documentId: deleteConfirmation.document.id });
  };

  const cancelDelete = () => {
    if (deleteIsPending) return;
    setDeleteConfirmation({ isOpen: false, document: null });
  };

  const handleDownload = async (doc: DocumentInfo) => {
    try {
      const response = await AXIOS_INSTANCE.get(`/v1/documents/${doc.id}/download`, {
        responseType: 'blob',
      });
      const blob = response.data as Blob;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = doc.original_filename || doc.filename || `document-${doc.id}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      addToast({
        kind: 'success',
        message: `Downloading ${doc.original_filename || doc.filename}`,
        duration: 3000,
      });
    } catch (error: any) {
      console.error('Download failed', error);
      addToast({
        kind: 'error',
        message: 'Failed to download document. Please try again.',
        duration: 8000,
      });
    }
  };

  const storageUsageLabel = useMemo(() => {
    if (statsLoading) {
      return '…';
    }
    const usedMb = stats?.storage_used_mb || 0;
    return `${usedMb.toFixed(1)} MB`;
  }, [stats?.storage_used_mb, statsLoading]);

  const hasActiveFilters = useMemo(
    () => timeRange !== '7d' || statusFilter !== 'all' || sourceFilter !== 'all',
    [statusFilter, sourceFilter, timeRange]
  );

  const metricItems = useMemo(
    () => [
      {
        key: 'total-documents',
        icon: DocumentTextIcon,
        iconClass: 'text-brand',
        value: statsLoading ? '…' : formatCount(stats?.total_documents),
        description: 'Total documents ingested',
      },
      {
        key: 'processing-documents',
        icon: ClockIcon,
        iconClass: 'text-ai-warning',
        value: statsLoading ? '…' : formatCount(stats?.processing_documents),
        description: 'Documents currently processing',
      },
      {
        key: 'completed-documents',
        icon: CheckCircleIcon,
        iconClass: 'text-ai-success',
        value: statsLoading ? '…' : formatCount(stats?.completed_documents),
        description: 'Documents successfully processed',
      },
      {
        key: 'total-chunks',
        icon: ChartBarIcon,
        iconClass: 'text-ai-info',
        value: statsLoading ? '…' : formatCount(stats?.total_chunks),
        description: 'Total data chunks generated',
      },
    ],
    [stats?.completed_documents, stats?.processing_documents, stats?.total_chunks, stats?.total_documents, statsLoading]
  );

  const quickActions = useMemo(
    () => [
      {
        label: 'Upload documents',
        onSelect: () => setUploadPanelOpen(true),
      },
      {
        label: 'Search knowledge base',
        onSelect: () => navigate('/search'),
      },
      {
        label: 'Refresh stats',
        onSelect: () => {
          queryClient.invalidateQueries({ queryKey: queryKeys.companyData.stats(timeRange) });
        },
      },
    ],
    [navigate, queryClient, timeRange]
  );

  return (
    <Layout>
      <div className="h-full flex flex-col px-0 overflow-hidden bg-gray-50 dark:bg-dark-bg">
        {/* Clean Header */}
        <div className="relative z-30 px-4 py-3 bg-white dark:bg-dark-surface border-b border-gray-200/30 dark:border-dark-border/30">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Title */}
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-eliza-red/10">
                <DocumentTextIcon className="w-5 h-5 text-eliza-red" />
              </div>
              <div>
                <h1 className="text-base font-semibold text-charcoal dark:text-gray-100">Knowledge Base</h1>
                <p className="text-xs text-gray-500 dark:text-gray-400">Manage documents and knowledge ingestion</p>
              </div>
            </div>

            {/* Center: Quick Stats */}
            <div className="hidden lg:flex items-center gap-3">
              {metricItems.map((metric) => (
                <Tooltip key={metric.key} content={metric.description}>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50">
                    <metric.icon className={`w-4 h-4 ${metric.iconClass}`} />
                    <span className="text-sm font-medium text-charcoal dark:text-gray-100">{metric.value}</span>
                  </div>
                </Tooltip>
              ))}
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              {/* Filter Button */}
              <Menu as="div" className="relative">
                <Menu.Button
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    hasActiveFilters 
                      ? 'bg-eliza-red/10 text-eliza-red border border-eliza-red/30' 
                      : 'bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-dark-surface-2'
                  }`}
                >
                  <FunnelIcon className="w-3.5 h-3.5" />
                  <span>Filter</span>
                  {hasActiveFilters && <span className="w-1.5 h-1.5 rounded-full bg-eliza-red" />}
                </Menu.Button>
                <Transition
                  as={Fragment}
                  enter="transition ease-out duration-100"
                  enterFrom="transform opacity-0 scale-95"
                  enterTo="transform opacity-100 scale-100"
                  leave="transition ease-in duration-75"
                  leaveFrom="transform opacity-100 scale-100"
                  leaveTo="transform opacity-0 scale-95"
                >
                  <Menu.Items className="absolute right-0 mt-2 w-72 origin-top-right rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface shadow-lg focus:outline-none z-60 p-4 space-y-4">
                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Time range</p>
                      <select
                        value={timeRange}
                        onChange={(e) => setTimeRange(e.target.value as '24h' | '7d' | '30d')}
                        className="w-full rounded-lg border border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2 px-3 py-2 text-sm text-charcoal dark:text-gray-100 focus:border-eliza-red/50 focus:outline-none focus:ring-2 focus:ring-eliza-red/20"
                      >
                        <option value="24h">Last 24 hours</option>
                        <option value="7d">Last 7 days</option>
                        <option value="30d">Last 30 days</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Status</p>
                      <select
                        value={statusFilter}
                        onChange={(e) => handleStatusChange(e.target.value as 'all' | DocumentStatus)}
                        className="w-full rounded-lg border border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2 px-3 py-2 text-sm text-charcoal dark:text-gray-100 focus:border-eliza-red/50 focus:outline-none focus:ring-2 focus:ring-eliza-red/20"
                      >
                        {STATUS_FILTERS.map((filter) => (
                          <option key={filter.value} value={filter.value}>
                            {filter.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Source</p>
                      <select
                        value={sourceFilter}
                        onChange={(e) => handleSourceChange(e.target.value)}
                        className="w-full rounded-lg border border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2 px-3 py-2 text-sm text-charcoal dark:text-gray-100 focus:border-eliza-red/50 focus:outline-none focus:ring-2 focus:ring-eliza-red/20"
                      >
                        <option value="all">All sources</option>
                        {availableSources.map((source) => (
                          <option key={source} value={source}>
                            {source}
                          </option>
                        ))}
                      </select>
                    </div>
                    <Menu.Item>
                      {({ close }) => (
                        <button
                          type="button"
                          onClick={() => {
                            setTimeRange('7d');
                            setStatusFilter('all');
                            setSourceFilter('all');
                            close();
                          }}
                          className="text-xs font-medium text-eliza-red hover:text-eliza-red-light transition-colors"
                        >
                          Reset all filters
                        </button>
                      )}
                    </Menu.Item>
                  </Menu.Items>
                </Transition>
              </Menu>

              {/* Storage indicator */}
              <Tooltip content={`Storage: ${storageUsageLabel} of ~1 GB`}>
                <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-xs text-gray-500 dark:text-gray-400">
                  <InboxStackIcon className="w-3.5 h-3.5" />
                  <span>{storageUsageLabel}</span>
                </div>
              </Tooltip>

              {/* Upload Button */}
              <button
                onClick={handleToggleUploadPanel}
                className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                  uploadPanelOpen 
                    ? 'bg-eliza-red text-white' 
                    : 'bg-eliza-red text-white hover:bg-eliza-red-light'
                }`}
                aria-expanded={uploadPanelOpen}
              >
                {uploadPanelOpen ? 'Close' : 'Upload'}
              </button>

              {/* Quick Actions */}
              <Menu as="div" className="relative">
                <Menu.Button className="p-2 rounded-full text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors">
                  <EllipsisHorizontalIcon className="w-5 h-5" />
                  <span className="sr-only">Quick actions</span>
                </Menu.Button>
                <Transition
                  as={Fragment}
                  enter="transition ease-out duration-100"
                  enterFrom="transform opacity-0 scale-95"
                  enterTo="transform opacity-100 scale-100"
                  leave="transition ease-in duration-75"
                  leaveFrom="transform opacity-100 scale-100"
                  leaveTo="transform opacity-0 scale-95"
                >
                  <Menu.Items className="absolute right-0 mt-2 w-48 origin-top-right rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface shadow-lg focus:outline-none z-50 py-1">
                    {quickActions.map((action) => (
                      <Menu.Item key={action.label}>
                        {({ active }) => (
                          <button
                            type="button"
                            onClick={action.onSelect}
                            className={`w-full px-4 py-2 text-left text-sm transition-colors ${
                              active ? 'bg-gray-50 dark:bg-dark-surface-2 text-charcoal dark:text-gray-100' : 'text-gray-500 dark:text-gray-400'
                            }`}
                          >
                            {action.label}
                          </button>
                        )}
                      </Menu.Item>
                    ))}
                  </Menu.Items>
                </Transition>
              </Menu>
            </div>
          </div>
        </div>

        {uploadPanelOpen && (
          <div className="bg-white dark:bg-dark-surface px-3 py-3">
            <DocumentUploadPanel
              ref={uploadPanelRef}
              onClose={handleUploadPanelClose}
              onUploadStart={handleUploadComplete}
            />
          </div>
        )}


        {/* Search & Sort Bar */}
        <div className="px-4 py-3 bg-white dark:bg-dark-surface">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
              <input
                type="text"
                aria-label="Search documents"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 rounded-xl text-charcoal dark:text-gray-100 text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-eliza-red/30 focus:border-eliza-red/50 transition-all"
              />
            </div>
            
            {/* Sort Options */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mr-2">Sort by</span>
              {SORT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSortChange(option.value)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    sortBy === option.value
                      ? 'bg-eliza-red/10 text-eliza-red border border-eliza-red/30'
                      : 'bg-white dark:bg-dark-surface border border-gray-200/50 dark:border-dark-border/50 text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-gray-100 hover:bg-gray-50 dark:hover:bg-dark-surface-2'
                  }`}
                >
                  {option.label}
                  {sortBy === option.value && (
                    <span className="ml-1 text-[10px]">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 min-h-0 bg-gray-50 dark:bg-dark-bg">
          <div ref={splitRef} className="flex h-full min-h-0 overflow-hidden">
            {/* Document List */}
            <div
              className="flex flex-col h-full min-h-0 border-r border-gray-200/30 dark:border-dark-border/30"
              style={{ width: `${listWidth}px`, minWidth: `${MIN_LIST_WIDTH}px`, maxWidth: `${MAX_LIST_WIDTH}px` }}
            >
              <DocumentLibraryList
                recentDocuments={filteredRecent}
                documents={regularDocuments}
                isLoading={documentsLoading}
                isRecentLoading={recentLoading}
                totalDocuments={totalDocuments}
                displayTotal={displayTotal}
                page={page}
                pageSize={pageSize}
                onPageChange={handlePageChange}
                onRequestUpload={() => setUploadPanelOpen(true)}
                selectedDocumentId={selectedDocumentId}
                onSelectDocument={handleSelectDocument}
              />
            </div>
            
            {/* Resizable Divider */}
            <div
              className="relative w-0"
              role="separator"
              aria-orientation="vertical"
              aria-label="Resize document detail pane"
            >
              <div
                className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize z-10"
                onPointerDown={handleDividerPointerDown}
                onPointerEnter={() => setIsDividerHovered(true)}
                onPointerLeave={() => setIsDividerHovered(false)}
                aria-hidden="true"
              >
                <div
                  className={`absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 transition-colors rounded-full ${
                    isDraggingDivider ? 'bg-eliza-red/50' : isDividerHovered ? 'bg-eliza-red/30' : 'bg-transparent'
                  }`}
                />
              </div>
            </div>
            
            {/* Document Detail Pane */}
            <div
              className="flex-1 min-h-0 flex overflow-hidden bg-white dark:bg-dark-surface"
              style={{ minWidth: `${MIN_DETAIL_WIDTH}px` }}
            >
              {selectedDocument ? (
                <div className="flex-1 min-h-0 overflow-y-auto overscroll-y-auto scroll-slim ios-momentum">
                  <DocumentDetailPane
                    document={selectedDocument}
                    onDownload={handleDownload}
                    onRetry={handleRetry}
                    onDelete={handleDeleteRequest}
                    onView={handleView}
                    retryIsPending={retryIsPending}
                    deleteIsPending={deleteIsPending}
                  />
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center text-center p-8 bg-white dark:bg-dark-surface">
                  <div className="p-4 rounded-2xl bg-gray-100 dark:bg-dark-surface-2 mb-4">
                    <DocumentTextIcon className="w-8 h-8 text-gray-400 dark:text-gray-500" />
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Select a document to view details</p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Click on any document from the list</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <Transition appear show={deleteConfirmation.isOpen} as={Fragment}>
          <Dialog as="div" className="relative z-50" onClose={cancelDelete}>
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0"
              enterTo="opacity-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <div className="fixed inset-0 bg-black/60" />
            </Transition.Child>

            <div className="fixed inset-0 overflow-y-auto">
              <div className="flex min-h-full items-center justify-center p-4 text-center">
                <Transition.Child
                  as={Fragment}
                  enter="ease-out duration-300"
                  enterFrom="opacity-0 scale-95"
                  enterTo="opacity-100 scale-100"
                  leave="ease-in duration-200"
                  leaveFrom="opacity-100 scale-100"
                  leaveTo="opacity-0 scale-95"
                >
                  <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg bg-white dark:bg-dark-surface border border-gray-200/60 dark:border-dark-border/60 shadow-xl transition-all text-left">
                    <div className="flex items-center justify-between p-6 border-b border-gray-200/60 dark:border-dark-border/60">
                      <div className="flex items-center gap-3">
                        <div className="flex-shrink-0 flex items-center justify-center h-10 w-10 rounded-full bg-red-500/10">
                          <ExclamationTriangleIcon className="h-6 w-6 text-red-500" />
                        </div>
                        <Dialog.Title as="h3" className="text-lg font-semibold text-charcoal dark:text-gray-100">
                          Confirm Delete
                        </Dialog.Title>
                      </div>
                      <button
                        type="button"
                        onClick={cancelDelete}
                        className="text-gray-500 dark:text-gray-400 hover:text-charcoal dark:hover:text-gray-100 transition-colors"
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </button>
                    </div>

                    <div className="p-6 space-y-3">
                      <Dialog.Description as="p" className="text-gray-500 dark:text-gray-400">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-charcoal dark:text-gray-100">
                          "{deleteConfirmation.document?.original_filename ?? deleteConfirmation.document?.filename}"
                        </span>
                        ?
                      </Dialog.Description>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        This action can be undone by an administrator.
                      </p>
                    </div>

                    <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
                      <button
                        type="button"
                        onClick={cancelDelete}
                        className="px-4 py-2 text-sm font-medium text-charcoal dark:text-gray-100 hover:bg-white dark:hover:bg-dark-surface rounded-md border border-gray-200/60 dark:border-dark-border/60 transition-colors"
                        disabled={deleteIsPending}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={confirmDelete}
                        disabled={deleteIsPending}
                        className="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        {deleteIsPending ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                            <span>Deleting…</span>
                          </>
                        ) : (
                          <>
                            <TrashIcon className="h-4 w-4" />
                            <span>Delete</span>
                          </>
                        )}
                      </button>
                    </div>
                  </Dialog.Panel>
                </Transition.Child>
              </div>
            </div>
          </Dialog>
        </Transition>
      </div>
    </Layout>
  );
}

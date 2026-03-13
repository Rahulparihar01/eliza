/*
 * Company Data Overview Page
 * Consolidated experience with inline uploader and BI-style document list
 */

import React, {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Dialog, Menu, Transition } from '@headlessui/react';
import {
  DocumentTextIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ClockIcon,
  ArrowUpTrayIcon,
  EllipsisHorizontalIcon,
  InboxStackIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
  TrashIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/outline';
import { useNavigate } from 'react-router-dom';
import {
  useGetDocumentStatsV1DocumentsStatsGet,
  useListDocumentsV1DocumentsGet,
  useDeleteDocumentV1DocumentsDocumentIdDelete,
  useRetryDocumentProcessingV1DocumentsDocumentIdRetryPost,
} from '../../generated/documents/documents';
import type { DocumentInfo } from '../../generated/models/documentInfo';
import type { DocumentStatus } from '../../generated/models/documentStatus';
import {
  DocumentUploadPanel,
  type DocumentUploadSurfaceHandle,
} from '../../components/company-data/DocumentUploadModal';
import DocumentDetailPane from '../../components/company-data/DocumentDetailPane';
import DocumentLibraryList from '../../components/company-data/DocumentLibraryTable';
import { queryKeys } from '../../lib/query-keys';
import { useDocumentUploadStream } from '../../hooks/useDocumentUploadStream';
import { Tooltip } from '../../components/common/Tooltip';
import { useToasts } from '../../stores/useToasts';
import { AXIOS_INSTANCE, getSettingsApi } from '../../services/api-client';
import { useQuery, useMutation } from '@tanstack/react-query';

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

function formatFileSize(bytes: number) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export default function CompanyDataOverview() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { push: addToast } = useToasts();

  const [timeRange, setTimeRange] = useState<'24h' | '7d' | '30d'>('7d');
  const [uploadPanelOpen, setUploadPanelOpen] = useState(false);
  const uploadPanelRef = useRef<DocumentUploadSurfaceHandle>(null);
  const [activeUploadId, setActiveUploadId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | DocumentStatus>('all');
  const [sourceFilter, setSourceFilter] = useState<'all' | string>('all');
  const [sortBy, setSortBy] = useState<'created_at' | 'filename' | 'file_size'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    isOpen: boolean;
    document: DocumentInfo | null;
  }>({ isOpen: false, document: null });
  const pageSize = 20;

  // Vector Search Settings state
  const [showSearchSettings, setShowSearchSettings] = useState(false);
  const [editThreshold, setEditThreshold] = useState('0.5');
  const [editLimit, setEditLimit] = useState('10');

  const { data: stats, isLoading: statsLoading } = useGetDocumentStatsV1DocumentsStatsGet(
    { range: timeRange },
    {
      query: {
        queryKey: queryKeys.companyData.stats(timeRange),
        staleTime: 30000,
      },
    }
  );

  // Fetch vector search settings
  const { data: vectorSearchData } = useQuery({
    queryKey: ['settings', 'vector-search'],
    queryFn: async () => {
      const response = await getSettingsApi().get('/v1/settings/vector-search/config');
      return response.data;
    },
  });

  // Mutation to update vector search settings
  const updateVectorSearch = useMutation({
    mutationFn: async (data: { similarity_threshold?: number; result_limit?: number }) => {
      const response = await getSettingsApi().put('/v1/settings/vector-search/config', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'vector-search'] });
      addToast({
        kind: 'success',
        message: 'Search settings updated successfully',
      });
      setShowSearchSettings(false);
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to update search settings',
      });
    },
  });

  const vectorSearchConfig = vectorSearchData || { similarity_threshold: 0.5, result_limit: 10 };

  const twentyFourHoursAgo = useMemo(
    () => new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    []
  );

  const { data: recentData, isLoading: uploadsLoading } = useListDocumentsV1DocumentsGet(
    {
      limit: 100,
      created_after: twentyFourHoursAgo,
      sort: '-created_at',
    },
    {
      query: {
        queryKey: queryKeys.companyData.recentUploads(),
        staleTime: 2000,
        refetchInterval: activeUploadId ? 2000 : 5000,
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
        queryKey: queryKeys.documents.list({
          status: statusFilter,
          sort: sortBy,
          order: sortOrder,
          page,
        }),
        staleTime: 30000,
      },
    }
  );

  const documents = useMemo(() => documentsResponse?.documents ?? [], [documentsResponse?.documents]);
  const totalDocuments = documentsResponse?.total ?? 0;
  const recentUploads = useMemo(() => recentData?.documents ?? [], [recentData?.documents]);

  useEffect(() => {
    if (activeUploadId && recentUploads.length > 0) {
      const hasActiveUploads = recentUploads.some(
        (doc) => doc.status !== 'completed' && doc.status !== 'failed'
      );

      if (!hasActiveUploads) {
        const timer = setTimeout(() => {
          setActiveUploadId(null);
        }, 3000);
        return () => clearTimeout(timer);
      }
    }
  }, [recentUploads, activeUploadId]);

  const { latestStatus, completion, failure } = useDocumentUploadStream(activeUploadId);

  useEffect(() => {
    if (latestStatus || completion || failure) {
      queryClient.invalidateQueries({ queryKey: queryKeys.companyData.recentUploads() });
      queryClient.invalidateQueries({ queryKey: queryKeys.companyData.stats(timeRange) });

      if (completion || failure) {
        setActiveUploadId(null);
      }
    }
  }, [latestStatus, completion, failure, queryClient, timeRange]);

  const handleUploadComplete = (uploadId?: string) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.companyData.recentUploads() });
    queryClient.invalidateQueries({ queryKey: queryKeys.companyData.stats(timeRange) });
    if (uploadId) {
      setActiveUploadId(uploadId);
    }
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

  const openUploadPanel = () => setUploadPanelOpen(true);

  const storageUsedBytes = useMemo(
    () => (stats?.storage_used_mb || 0) * 1024 * 1024,
    [stats?.storage_used_mb]
  );

  const storageUsagePercent = useMemo(() => {
    const usedMb = stats?.storage_used_mb || 0;
    return Math.min((usedMb / 1000) * 100, 100);
  }, [stats?.storage_used_mb]);

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

    const exists = selectedDocumentId !== null && orderedDocuments.some((doc) => doc.id === selectedDocumentId);
    if (!exists) {
      setSelectedDocumentId(orderedDocuments[0].id);
    }
  }, [orderedDocuments, selectedDocumentId]);

  const selectedDocument = useMemo(
    () => orderedDocuments.find((doc) => doc.id === selectedDocumentId) ?? null,
    [orderedDocuments, selectedDocumentId]
  );

  const displayTotal = filteredRecent.length + regularDocuments.length;

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

  const quickActions = useMemo(
    () => [
      {
        label: 'Upload documents',
        onSelect: () => setUploadPanelOpen(true),
      },
      {
        label: 'Search settings',
        onSelect: () => {
          setEditThreshold(String(vectorSearchConfig.similarity_threshold));
          setEditLimit(String(vectorSearchConfig.result_limit));
          setShowSearchSettings(true);
        },
      },
      {
        label: 'Refresh stats',
        onSelect: () => queryClient.invalidateQueries({ queryKey: queryKeys.companyData.stats(timeRange) }),
      },
    ],
    [queryClient, timeRange, vectorSearchConfig]
  );

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

  const handleSelectDocument = useCallback((doc: DocumentInfo) => {
    setSelectedDocumentId(doc.id);
  }, []);

  const handlePageChange = (nextPage: number) => {
    const maxPage = Math.max(1, Math.ceil(totalDocuments / pageSize));
    if (nextPage < 1 || nextPage > maxPage) {
      return;
    }
    setPage(nextPage);
  };

  const { mutate: deleteDocument, isPending: deleteIsPending } = useDeleteDocumentV1DocumentsDocumentIdDelete({
    mutation: {
      onMutate: async (variables) => {
        const documentId = variables.documentId;
        await queryClient.cancelQueries({ queryKey: queryKeys.documents.lists() });

        const queryKey = queryKeys.documents.list({
          status: statusFilter,
          sort: sortBy,
          order: sortOrder,
          page,
        });
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

  const handleView = (doc: DocumentInfo) => {
    addToast({
      kind: 'info',
      message: `Preview for ${doc.original_filename || doc.filename} coming soon.`,
      duration: 4000,
    });
  };

  const handleRetry = (doc: DocumentInfo) => {
    retryDocument({ documentId: doc.id });
  };

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

  return (
    <div className="h-full flex flex-col space-y-6 overflow-hidden">
      <div className="relative z-10 bg-surface-2">
        <div className="flex items-center justify-between h-12 px-4 border-b border-border/60">
          <div className="flex items-center gap-2 text-sm font-semibold text-text">
            <DocumentTextIcon className="w-4 h-4 text-brand" />
            <span>Company Data</span>
            <Tooltip
              position="top"
              content="Manage document ingestion, processing status, and storage usage"
            >
              <span className="text-muted cursor-help">ⓘ</span>
            </Tooltip>
          </div>
          <div className="flex items-center gap-3">
            <Tooltip
              content={`Storage usage: ${
                statsLoading ? 'Loading…' : formatFileSize(storageUsedBytes)
              } of ~1 GB`}
            >
              <div className="flex items-center gap-2 text-xs text-muted bg-surface rounded-lg border border-border/70 px-3 py-1.5">
                <InboxStackIcon className="w-4 h-4 text-brand" />
                <div className="flex items-center gap-2">
                  <span className="font-medium text-text">
                    {statsLoading ? '…' : formatFileSize(storageUsedBytes)}
                  </span>
                  <div className="w-16 h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand transition-all"
                      style={{ width: `${storageUsagePercent}%` }}
                    />
                  </div>
                </div>
              </div>
            </Tooltip>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value as '24h' | '7d' | '30d')}
              className="px-3 py-2 border border-border rounded-lg bg-surface text-text text-xs focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
            >
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </select>
            <Menu as="div" className="relative">
              <Menu.Button className="p-2 rounded-full border border-border text-muted hover:text-text hover:bg-surface focus:outline-none focus:ring-2 focus:ring-brand">
                <EllipsisHorizontalIcon className="w-5 h-5" />
                <span className="sr-only">Open quick actions</span>
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
                <Menu.Items className="absolute right-0 mt-2 w-48 origin-top-right rounded-lg border border-border bg-surface shadow-2 focus:outline-none z-40">
                  <div className="py-1">
                    {quickActions.map((action) => (
                      <Menu.Item key={action.label}>
                        {({ active }) => (
                          <button
                            type="button"
                            onClick={action.onSelect}
                            className={`w-full px-4 py-2 text-left text-sm ${
                              active ? 'bg-surface-2 text-text' : 'text-muted'
                            }`}
                          >
                            {action.label}
                          </button>
                        )}
                      </Menu.Item>
                    ))}
                  </div>
                </Menu.Items>
              </Transition>
            </Menu>
            <button
              onClick={handleToggleUploadPanel}
              className={`inline-flex items-center gap-2 rounded-lg border border-transparent px-4 py-2 text-xs font-semibold transition-colors ${
                uploadPanelOpen
                  ? 'bg-brand text-on-brand'
                  : 'bg-brand text-on-brand hover:bg-brand-hover'
              }`}
              aria-expanded={uploadPanelOpen}
            >
              <ArrowUpTrayIcon className="w-4 h-4" />
              {uploadPanelOpen ? 'Hide uploader' : 'Upload data'}
            </button>
          </div>
        </div>
        {uploadPanelOpen && (
          <div className="px-4 py-4 border-b border-border/60">
            <DocumentUploadPanel
              ref={uploadPanelRef}
              onClose={handleUploadPanelClose}
              onUploadStart={handleUploadComplete}
            />
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface border border-border rounded-lg p-4">
          <div className="flex items-center">
            <div className="p-2 bg-brand-soft rounded-lg">
              <DocumentTextIcon className="w-6 h-6 text-brand" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-muted">Total Documents</p>
              <p className="text-2xl font-bold text-text">
                {statsLoading ? '…' : stats?.total_documents || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface border border-border rounded-lg p-4">
          <div className="flex items-center">
            <div className="p-2 bg-ai-warning-soft rounded-lg">
              <ClockIcon className="w-6 h-6 text-ai-warning" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-muted">Processing</p>
              <p className="text-2xl font-bold text-text">
                {statsLoading ? '…' : stats?.processing_documents || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface border border-border rounded-lg p-4">
          <div className="flex items-center">
            <div className="p-2 bg-ai-success-soft rounded-lg">
              <CheckCircleIcon className="w-6 h-6 text-ai-success" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-muted">Completed</p>
              <p className="text-2xl font-bold text-text">
                {statsLoading ? '…' : stats?.completed_documents || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-surface border border-border rounded-lg p-4">
          <div className="flex items-center">
            <div className="p-2 bg-ai-info-soft rounded-lg">
              <ChartBarIcon className="w-6 h-6 text-ai-info" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-muted">Total Chunks</p>
              <p className="text-2xl font-bold text-text">
                {statsLoading ? '…' : stats?.total_chunks || 0}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-surface px-4 py-4 space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative flex-1 min-w-[220px]">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-border rounded-lg bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => handleStatusChange(e.target.value as 'all' | DocumentStatus)}
              className="px-3 py-2 border border-border rounded-lg bg-surface text-text text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
            >
              {STATUS_FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </select>
            <select
              value={sourceFilter}
              onChange={(e) => handleSourceChange(e.target.value)}
              className="px-3 py-2 border border-border rounded-lg bg-surface text-text text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
            >
              <option value="all">All sources</option>
              {availableSources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-1 text-xs text-muted">
              {SORT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSortChange(option.value)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                    sortBy === option.value
                      ? 'border-brand bg-brand-soft text-brand'
                      : 'border-border hover:bg-surface-2'
                  }`}
                >
                  {option.label}
                  {sortBy === option.value && <span className="ml-1">{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col xl:flex-row gap-6 min-h-0">
        <div className="flex-1 min-h-[360px]">
          <DocumentLibraryList
            recentDocuments={filteredRecent}
            documents={regularDocuments}
            isLoading={documentsLoading}
            isRecentLoading={uploadsLoading}
            totalDocuments={totalDocuments}
            displayTotal={displayTotal}
            page={page}
            pageSize={pageSize}
            onPageChange={handlePageChange}
            onRequestUpload={openUploadPanel}
            selectedDocumentId={selectedDocumentId}
            onSelectDocument={handleSelectDocument}
          />
        </div>
        <div className="mt-6 xl:mt-0 xl:w-[360px] xl:flex-shrink-0">
          {selectedDocument ? (
            <DocumentDetailPane
              document={selectedDocument}
              onDownload={handleDownload}
              onRetry={handleRetry}
              onDelete={handleDeleteRequest}
              onView={handleView}
              retryIsPending={retryIsPending}
              deleteIsPending={deleteIsPending}
            />
          ) : (
            <div className="hidden xl:flex items-center justify-center min-h-[360px] text-sm text-muted border border-border/60 bg-surface-2">
              Select a document to view details
            </div>
          )}
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
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg bg-surface border border-border shadow-xl transition-all text-left">
                  <div className="flex items-center justify-between p-6 border-b border-border">
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0 flex items-center justify-center h-10 w-10 rounded-full bg-ai-danger-soft">
                        <ExclamationTriangleIcon className="h-6 w-6 text-ai-danger" />
                      </div>
                      <Dialog.Title as="h3" className="text-lg font-semibold text-text">
                        Confirm Delete
                      </Dialog.Title>
                    </div>
                    <button
                      type="button"
                      onClick={cancelDelete}
                      className="text-muted hover:text-text transition-colors"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="p-6 space-y-3">
                    <Dialog.Description as="p" className="text-muted">
                      Are you sure you want to delete{' '}
                      <span className="font-medium text-text">
                        “{deleteConfirmation.document?.original_filename ?? deleteConfirmation.document?.filename}”
                      </span>
                      ?
                    </Dialog.Description>
                    <p className="text-xs text-muted">
                      This action can be undone by an administrator.
                    </p>
                  </div>

                  <div className="flex items-center justify-end gap-3 p-6 border-t border-border bg-surface-2">
                    <button
                      type="button"
                      onClick={cancelDelete}
                      className="px-4 py-2 text-sm font-medium text-text hover:bg-surface rounded-md border border-border transition-colors"
                      disabled={deleteIsPending}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={confirmDelete}
                      disabled={deleteIsPending}
                      className="px-4 py-2 text-sm font-medium text-white bg-ai-danger hover:bg-ai-danger-hover rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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

      {/* Vector Search Settings Modal */}
      <Transition appear show={showSearchSettings} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setShowSearchSettings(false)}>
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
                <Dialog.Panel className="w-full max-w-lg transform overflow-hidden rounded-lg bg-surface border border-border shadow-xl transition-all text-left">
                  <div className="flex items-center justify-between p-6 border-b border-border">
                    <div className="flex items-center gap-3">
                      <div className="flex-shrink-0 flex items-center justify-center h-10 w-10 rounded-full bg-brand/10">
                        <AdjustmentsHorizontalIcon className="h-5 w-5 text-brand" />
                      </div>
                      <div>
                        <Dialog.Title as="h3" className="text-lg font-semibold text-text">
                          Search Settings
                        </Dialog.Title>
                        <p className="text-sm text-muted">Configure document search parameters</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowSearchSettings(false)}
                      className="text-muted hover:text-text transition-colors"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="p-6 space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Similarity Threshold
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.05"
                        value={editThreshold}
                        onChange={(e) => setEditThreshold(e.target.value)}
                        className="block w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-text focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent text-sm"
                      />
                      <p className="mt-1 text-xs text-muted">
                        Lower values = more results (less strict). Range: 0.0-1.0
                      </p>
                      <div className="mt-2 flex items-center gap-2 text-xs">
                        <span className="text-muted">Quick:</span>
                        <button
                          type="button"
                          onClick={() => setEditThreshold('0.3')}
                          className="px-2 py-1 bg-surface-2 border border-border rounded hover:bg-brand hover:text-on-brand hover:border-brand transition-colors"
                        >
                          0.3 Broad
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditThreshold('0.5')}
                          className="px-2 py-1 bg-surface-2 border border-border rounded hover:bg-brand hover:text-on-brand hover:border-brand transition-colors"
                        >
                          0.5 Balanced
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditThreshold('0.7')}
                          className="px-2 py-1 bg-surface-2 border border-border rounded hover:bg-brand hover:text-on-brand hover:border-brand transition-colors"
                        >
                          0.7 Strict
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Result Limit (k)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        step="1"
                        value={editLimit}
                        onChange={(e) => setEditLimit(e.target.value)}
                        className="block w-full rounded-lg border border-border bg-surface-2 px-3 py-2 text-text focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent text-sm"
                      />
                      <p className="mt-1 text-xs text-muted">
                        Maximum number of document chunks to return. Range: 1-100
                      </p>
                      <div className="mt-2 flex items-center gap-2 text-xs">
                        <span className="text-muted">Quick:</span>
                        <button
                          type="button"
                          onClick={() => setEditLimit('5')}
                          className="px-2 py-1 bg-surface-2 border border-border rounded hover:bg-brand hover:text-on-brand hover:border-brand transition-colors"
                        >
                          5 Fast
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditLimit('10')}
                          className="px-2 py-1 bg-surface-2 border border-border rounded hover:bg-brand hover:text-on-brand hover:border-brand transition-colors"
                        >
                          10 Balanced
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditLimit('20')}
                          className="px-2 py-1 bg-surface-2 border border-border rounded hover:bg-brand hover:text-on-brand hover:border-brand transition-colors"
                        >
                          20 Comprehensive
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-3 p-6 border-t border-border bg-surface-2">
                    <button
                      type="button"
                      onClick={() => setShowSearchSettings(false)}
                      className="px-4 py-2 text-sm font-medium text-text hover:bg-surface rounded-lg border border-border transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const threshold = parseFloat(editThreshold);
                        const limit = parseInt(editLimit, 10);
                        
                        if (isNaN(threshold) || threshold < 0 || threshold > 1) {
                          addToast({ kind: 'error', message: 'Threshold must be between 0.0 and 1.0' });
                          return;
                        }
                        if (isNaN(limit) || limit < 1 || limit > 100) {
                          addToast({ kind: 'error', message: 'Result limit must be between 1 and 100' });
                          return;
                        }
                        
                        updateVectorSearch.mutate({ similarity_threshold: threshold, result_limit: limit });
                      }}
                      disabled={updateVectorSearch.isPending}
                      className="px-4 py-2 text-sm font-medium text-on-brand bg-brand hover:bg-brand-hover rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                      {updateVectorSearch.isPending ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-on-brand border-t-transparent" />
                          <span>Saving…</span>
                        </>
                      ) : (
                        <span>Save Settings</span>
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
  );
}

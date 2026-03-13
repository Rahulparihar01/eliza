/**
 * WorkspaceDetailPage - RAG Workspace Detail View
 * 
 * Mirrors RAGFlow's dataset detail page with document table,
 * upload, and parsing controls.
 * 
 * Migrated to Eliza Design System (Feb 2026)
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeftIcon,
  CloudArrowUpIcon,
  DocumentTextIcon,
  PlusIcon,
  PlayIcon,
  TrashIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { Layout } from '../../components/layout/Layout';
import {
  Button,
  Badge,
  Spinner,
  DataTable,
  Input,
  type Column,
} from '../../components/ui';
import { useToasts } from '../../stores/useToasts';
import { isSectionItemPathEnabled } from '../../components/navigation/sectionConfigs';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

interface RAGFlowDocument {
  id: number;
  original_filename: string;
  file_size: number;
  mime_type: string;
  status: 'pending' | 'parsing' | 'completed' | 'failed';
  progress: number;
  chunk_count: number;
  token_count: number;
  processing_error?: string;
  created_at: string;
}

interface KnowledgeBaseSummary {
  id: number;
  name: string;
  status: string;
  document_count: number;
  chunk_count: number;
  is_active: boolean;
  description?: string;
  parser_type?: string;
  source_type?: string;
}

interface RAGFlowWorkspace {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  icon: string;
  color: string;
  status: string;
  document_count: number;
  chunk_count: number;
  total_tokens: number;
  template_name?: string;
  template_display_name?: string;
  knowledge_base_count?: number;
  knowledge_bases?: KnowledgeBaseSummary[];
  workspace_config?: Record<string, unknown> | null;
}

interface WorkspaceDetailPayload {
  workspace: RAGFlowWorkspace;
  knowledge_bases: KnowledgeBaseSummary[];
}

function isFasbWorkspaceConfig(workspace: Partial<RAGFlowWorkspace> | null | undefined): boolean {
  if (!workspace) return false;
  const domainName = String(workspace.name || '').trim().toLowerCase();
  const config =
    workspace.workspace_config && typeof workspace.workspace_config === 'object'
      ? (workspace.workspace_config as Record<string, unknown>)
      : {};
  const backendType = String(config.backend_type || '').trim().toLowerCase();
  const opensearchIndex = String(config.opensearch_index || '').trim().toLowerCase();

  return (
    domainName === 'fasb' ||
    backendType === 'opensearch_fasb' ||
    opensearchIndex.startsWith('fasb')
  );
}

// Format file size
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Status badge component using DS Badge
function StatusBadge({ status, progress }: { status: string; progress?: number }) {
  const pct = progress || 0;
  
  switch (status) {
    case 'completed':
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircleIcon className="w-3 h-3" />
          Success
        </Badge>
      );
    case 'parsing':
      return (
        <div className="inline-flex items-center gap-2 px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
          <ArrowPathIcon className="w-3 h-3 animate-spin" />
          <div className="w-16 h-1.5 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500 transition-all duration-500 ease-out" 
              style={{ width: `${Math.max(pct, 5)}%` }}
            />
          </div>
          <span className="min-w-[2rem] text-right">{pct}%</span>
        </div>
      );
    case 'failed':
      return (
        <Badge variant="danger" className="gap-1">
          <ExclamationCircleIcon className="w-3 h-3" />
          Failed
        </Badge>
      );
    case 'pending':
    default:
      return (
        <Badge variant="warning" className="gap-1">
          <PlayIcon className="w-3 h-3" />
          Queued
        </Badge>
      );
  }
}

export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [workspace, setWorkspace] = useState<RAGFlowWorkspace | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseSummary[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<RAGFlowDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isSyncingStats, setIsSyncingStats] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [showCreateKbModal, setShowCreateKbModal] = useState(false);
  const [isCreatingKb, setIsCreatingKb] = useState(false);
  const [kbName, setKbName] = useState('');
  const [kbDescription, setKbDescription] = useState('');
  const [kbSourceType, setKbSourceType] = useState<'elasticsearch' | 's3' | 'local_directory'>('s3');
  const [kbSourceValue, setKbSourceValue] = useState('');
  const [kbParserType, setKbParserType] = useState<'naive' | 'deepdoc' | 'gpt-4o' | 'docling' | 'custom-vlm'>('naive');
  const [kbCustomModel, setKbCustomModel] = useState('deepseek-ocr2@OpenAI-API-Compatible');
  const isTelemetryEnabled = isSectionItemPathEnabled('/telemetry');

  // RAG & AI settings (embedding + inference model)
  const [ragSettings, setRagSettings] = useState<{
    embedding_provider: string;
    embedding_model: string;
    available_embedding_providers: string[];
    default_llm_model?: string | null;
  } | null>(null);
  const [promptTemplate, setPromptTemplate] = useState<{ model: string } | null>(null);
  const [ragChatModels, setRagChatModels] = useState<Array<{ id: string; name: string; provider: string }>>([]);
  const [savingChatModel, setSavingChatModel] = useState(false);

  const fetchWorkspaceWithFallback = useCallback(async (): Promise<WorkspaceDetailPayload | null> => {
    if (!workspaceId) {
      return null;
    }

    const res = await fetch(`${API_BASE}/v1/workspaces/${workspaceId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.ok) {
      const data = await res.json();
      const workspace = data.workspace || data;
      const knowledgeBases: KnowledgeBaseSummary[] = data.knowledge_bases || workspace.knowledge_bases || [];
      return { workspace, knowledge_bases: knowledgeBases };
    }

    const legacyRes = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!legacyRes.ok) {
      return null;
    }

    const legacyData = await legacyRes.json();
    const workspace = legacyData.workspace || legacyData;
    const knowledgeBases: KnowledgeBaseSummary[] = legacyData.knowledge_bases || workspace.knowledge_bases || [];
    return { workspace, knowledge_bases: knowledgeBases };
  }, [workspaceId, token]);

  const syncWorkspaceStats = useCallback(
    async (silent = false): Promise<boolean> => {
      if (!workspaceId) return false;
      if (!silent) setIsSyncingStats(true);

      try {
        const res = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}/sync-stats`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok && !silent) {
          const err = await res.json().catch(() => ({}));
          addToast({ kind: 'error', message: err.detail || 'Failed to sync stats' });
        }
        return res.ok;
      } catch (e) {
        if (!silent) {
          addToast({ kind: 'error', message: 'Failed to sync stats' });
        }
        return false;
      } finally {
        if (!silent) setIsSyncingStats(false);
      }
    },
    [workspaceId, token, addToast]
  );

  // Fetch workspace and documents
  const fetchData = useCallback(async () => {
    if (!workspaceId) return;

    try {
      const loadedWorkspace = await fetchWorkspaceWithFallback();
      if (!loadedWorkspace) {
        addToast({ kind: 'error', message: 'Workspace not found' });
        navigate('/workspaces');
        return;
      }

      const nextWorkspace = loadedWorkspace.workspace;
      const nextKnowledgeBases = loadedWorkspace.knowledge_bases || [];
      setWorkspace(nextWorkspace);
      setKnowledgeBases(nextKnowledgeBases);

      const nextSelectedKbId = selectedKnowledgeBaseId && nextKnowledgeBases.some((kb) => kb.id === selectedKnowledgeBaseId)
        ? selectedKnowledgeBaseId
        : (nextKnowledgeBases[0]?.id ?? null);
      setSelectedKnowledgeBaseId(nextSelectedKbId);

      const docsUrl = new URL(`${API_BASE}/v1/ragflow/domains/${workspaceId}/documents`, window.location.origin);
      if (nextSelectedKbId) {
        docsUrl.searchParams.set('knowledge_base_id', String(nextSelectedKbId));
      }
      const docsRes = await fetch(docsUrl.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (docsRes.ok) {
        const data = await docsRes.json();
        setDocuments(data.documents || []);
      }

      // RAG & AI settings (embedding + inference model options)
      const [ragRes, templateRes, forRagRes] = await Promise.all([
        fetch(`${API_BASE}/v1/config/rag-settings`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/v1/workspaces/${workspaceId}/prompt-template`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/v1/models/for-rag`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (ragRes.ok) {
        const data = await ragRes.json();
        setRagSettings(data);
      }
      if (templateRes.ok) {
        const data = await templateRes.json();
        setPromptTemplate({ model: data.model });
      }
      if (forRagRes.ok) {
        const data = await forRagRes.json();
        setRagChatModels(data.models || []);
      }
    } catch (e) {
      console.error('Failed to fetch data:', e);
      addToast({ kind: 'error', message: 'Failed to load workspace' });
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, token, navigate, addToast, fetchWorkspaceWithFallback, selectedKnowledgeBaseId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const selectedKnowledgeBase =
    selectedKnowledgeBaseId != null
      ? (knowledgeBases.find((kb) => kb.id === selectedKnowledgeBaseId) ?? null)
      : null;
  const selectedKnowledgeBaseSyncing =
    selectedKnowledgeBase != null
      ? ['pending', 'indexing'].includes(String(selectedKnowledgeBase.status || '').toLowerCase())
      : false;

  // Poll for updates while docs parse OR KB sync/indexing is active.
  useEffect(() => {
    const hasActiveDocProcessing = documents.some((d) => d.status === 'parsing' || d.status === 'pending');
    if (!hasActiveDocProcessing && !selectedKnowledgeBaseSyncing) return;

    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [documents, fetchData, selectedKnowledgeBaseSyncing]);

  const isFasbWorkspace = isFasbWorkspaceConfig(workspace);

  const handleChatModelChange = async (modelId: string) => {
    if (!workspaceId || !token) return;
    setSavingChatModel(true);
    try {
      const putRes = await fetch(`${API_BASE}/v1/workspaces/${workspaceId}/prompt-template`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ model: modelId }),
      });
      if (!putRes.ok) throw new Error('Failed to save');
      const updated = await putRes.json();
      setPromptTemplate({ model: updated.model });
      addToast({ kind: 'success', message: 'Chat model updated' });
    } catch (e) {
      addToast({ kind: 'error', message: e instanceof Error ? e.message : 'Failed to update chat model' });
    } finally {
      setSavingChatModel(false);
    }
  };

  // Handle file upload
  const handleFileUpload = async (files: FileList) => {
    if (!files.length) return;
    if (!selectedKnowledgeBaseId) {
      addToast({
        kind: 'warning',
        message: 'Create and select a knowledge base before uploading files.',
      });
      return;
    }

    setIsUploading(true);
    let successCount = 0;
    let failCount = 0;
    const failureReasons: string[] = [];

    for (const file of Array.from(files)) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('knowledge_base_id', String(selectedKnowledgeBaseId));

        const res = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}/documents`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });

        if (res.ok) {
          successCount++;
        } else {
          failCount++;
          const error = await res.json().catch(() => ({}));
          const detail = typeof error?.detail === 'string' ? error.detail : `Upload failed (${res.status})`;
          failureReasons.push(`${file.name}: ${detail}`);
          console.error(`Upload failed for ${file.name}:`, error);
        }
      } catch (e) {
        failCount++;
        failureReasons.push(`${file.name}: ${e instanceof Error ? e.message : 'Unexpected upload error'}`);
        console.error(`Upload error for ${file.name}:`, e);
      }
    }

    setIsUploading(false);

    if (successCount > 0) {
      addToast({ kind: 'success', message: `Uploaded ${successCount} file(s)` });
    }
    if (failCount > 0) {
      addToast({
        kind: 'error',
        message:
          failureReasons.length > 0
            ? `${failCount} file(s) failed. ${failureReasons[0]}`
            : `${failCount} file(s) failed to upload`,
      });
    }

    fetchData();
  };

  const handleCreateKnowledgeBase = async () => {
    const trimmedName = kbName.trim();
    if (!trimmedName) {
      addToast({ kind: 'error', message: 'Knowledge base name is required' });
      return;
    }
    if (kbSourceType === 's3' && !kbSourceValue.trim()) {
      addToast({ kind: 'error', message: 'S3 bucket path is required for S3 knowledge bases' });
      return;
    }

    const sourceConfig: Record<string, unknown> = {};
    if (kbSourceValue.trim()) {
      if (kbSourceType === 'local_directory') {
        sourceConfig.path = kbSourceValue.trim();
      } else if (kbSourceType === 's3') {
        sourceConfig.prefix = kbSourceValue.trim();
      } else if (kbSourceType === 'elasticsearch') {
        sourceConfig.index_name = kbSourceValue.trim();
      }
    }

    const parserConfig: Record<string, unknown> = {};
    if (kbParserType === 'custom-vlm' && kbCustomModel.trim()) {
      parserConfig.custom_vlm_model = kbCustomModel.trim();
    }

    const payload: Record<string, unknown> = {
      name: trimmedName,
      description: kbDescription.trim() || undefined,
      parser_type: kbParserType,
      parser_config: Object.keys(parserConfig).length ? parserConfig : undefined,
      source_type: kbSourceType,
      source_config: Object.keys(sourceConfig).length ? sourceConfig : undefined,
      storage_backend: 'tenant_default',
      chunk_token_count: 512,
      similarity_threshold: 20,
      top_k: 5,
    };

    setIsCreatingKb(true);
    try {
      const res = await fetch(`${API_BASE}/v1/workspaces/${workspaceId}/knowledge-bases`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to create knowledge base');
      }
      const createdKb = await res.json();
      const createdSummary: KnowledgeBaseSummary = {
        id: createdKb.id,
        name: createdKb.name,
        status: createdKb.status || 'pending',
        document_count: createdKb.document_count ?? 0,
        chunk_count: createdKb.chunk_count ?? 0,
        is_active: createdKb.is_active ?? true,
        description: createdKb.description,
        parser_type: createdKb.parser_type,
        source_type: createdKb.source_type,
      };
      setKnowledgeBases((prev) => [createdSummary, ...prev.filter((kb) => kb.id !== createdSummary.id)]);
      addToast({
        kind: 'success',
        message:
          kbSourceType === 's3'
            ? 'Knowledge base created. Initial S3 sync started.'
            : 'Knowledge base created',
      });
      setShowCreateKbModal(false);
      setKbName('');
      setKbDescription('');
      setKbSourceType('s3');
      setKbSourceValue('');
      setKbParserType('naive');
      setKbCustomModel('deepseek-ocr2@OpenAI-API-Compatible');
      setDocuments([]);
      setSelectedKnowledgeBaseId(createdKb.id);
    } catch (e) {
      addToast({
        kind: 'error',
        message: e instanceof Error ? e.message : 'Failed to create knowledge base',
      });
    } finally {
      setIsCreatingKb(false);
    }
  };

  // Delete document
  const handleDeleteDocument = async (docId: number) => {
    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}/documents/${docId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        addToast({ kind: 'success', message: 'Document deleted' });
        fetchData();
      } else {
        addToast({ kind: 'error', message: 'Failed to delete document' });
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to delete document' });
    }
  };

  // Start parsing
  const handleStartParsing = async () => {
    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}/parse`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        addToast({ kind: 'success', message: 'Parsing started! Progress will update automatically.' });
        fetchData();
      } else {
        const error = await res.json();
        addToast({ kind: 'error', message: error.detail || 'Failed to start parsing' });
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to start parsing' });
    }
  };

  const handleSyncStats = async () => {
    const ok = await syncWorkspaceStats(false);
    if (ok) {
      addToast({ kind: 'success', message: 'Workspace stats synced' });
      await fetchData();
    }
  };

  const handleRetryIngestion = async () => {
    if (!workspaceId) return;
    setIsRetrying(true);
    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}/retry-ingestion`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const result = await res.json();
        addToast({
          kind: 'success',
          message: result.documents_queued > 0
            ? `Reprocessing ${result.documents_queued} document(s)...`
            : 'No documents to retry.',
        });
        fetchData();
      } else {
        const err = await res.json().catch(() => ({}));
        addToast({ kind: 'error', message: err.detail || 'Failed to retry ingestion' });
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to retry ingestion' });
    } finally {
      setIsRetrying(false);
    }
  };

  // Check if chat is available
  const canChat =
    isFasbWorkspace ||
    knowledgeBases.some((kb) => kb.chunk_count > 0) ||
    ((workspace?.chunk_count || 0) > 0);
  const hasPendingDocs = documents.some(d => d.status === 'pending');
  const hasParsingDocs = documents.some(d => d.status === 'parsing');
  const hasFailedDocs = documents.some(d => d.status === 'failed');
  const hasRetryableDocs = hasFailedDocs || hasParsingDocs || hasPendingDocs;
  const showSyncBanner = hasParsingDocs || selectedKnowledgeBaseSyncing;

  // DataTable columns
  const columns: Column<RAGFlowDocument>[] = [
    {
      id: 'original_filename',
      header: 'File Name',
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <DocumentTextIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-charcoal dark:text-white truncate">
              {row.original_filename}
            </p>
            {row.processing_error && row.status === 'failed' && (
              <p className="text-xs text-red-500 truncate" title={row.processing_error}>
                {row.processing_error}
              </p>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'file_size',
      header: 'Size',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {formatFileSize(row.file_size)}
        </span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: ({ row }) => <StatusBadge status={row.status} progress={row.progress} />,
    },
    {
      id: 'chunk_count',
      header: 'Chunks',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {row.chunk_count || '-'}
        </span>
      ),
    },
    {
      id: 'token_count',
      header: 'Tokens',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {row.token_count || '-'}
        </span>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      align: 'right',
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handleDeleteDocument(row.id)}
          className="text-gray-400 hover:text-red-500"
        >
          <TrashIcon className="w-4 h-4" />
        </Button>
      ),
    },
  ];

  // Build description string with stats
  const statsDescription = workspace ? [
    `${workspace.document_count || 0} files`,
    `${workspace.chunk_count || 0} chunks`,
    `${workspace.total_tokens || 0} tokens`,
    workspace.knowledge_base_count !== undefined && workspace.knowledge_base_count > 0 
      ? `${workspace.knowledge_base_count} knowledge base${workspace.knowledge_base_count !== 1 ? 's' : ''}`
      : null,
  ].filter(Boolean).join(' · ') : undefined;

  if (isLoading) {
    return (
      <Layout>
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading workspace...</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="flex-1 flex flex-col h-full bg-gray-50 dark:bg-dark-bg overflow-hidden">
        {/* Sub-toolbar with back button and title */}
        <div className="flex-shrink-0 bg-white dark:bg-dark-surface border-b border-gray-200 dark:border-dark-border px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={() => navigate('/workspaces')}>
                <ArrowLeftIcon className="w-4 h-4" />
              </Button>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="font-medium text-charcoal dark:text-white">
                    {workspace?.display_name || workspace?.name || 'Workspace'}
                  </h1>
                  {workspace?.template_display_name && (
                    <Badge variant="brand">{workspace.template_display_name}</Badge>
                  )}
                  {isFasbWorkspace && (
                    <Badge variant="warning">OpenSearch-backed</Badge>
                  )}
                </div>
                {statsDescription && (
                  <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                    {statsDescription}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <>
                <select
                  value={selectedKnowledgeBaseId ?? ''}
                  onChange={(e) => setSelectedKnowledgeBaseId(e.target.value ? Number(e.target.value) : null)}
                  className="h-8 rounded-md border border-gray-200 bg-white px-2 text-xs text-gray-700 dark:border-dark-border dark:bg-dark-surface-2 dark:text-gray-200"
                >
                  {knowledgeBases.length === 0 ? (
                    <option value="">No knowledge bases</option>
                  ) : (
                    knowledgeBases.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name} ({kb.document_count} docs)
                      </option>
                    ))
                  )}
                </select>
                <Button size="sm" onClick={() => setShowCreateKbModal(true)}>
                  <PlusIcon className="w-4 h-4 mr-2" />
                  Create Knowledge Base
                </Button>
              </>
              {hasPendingDocs && (
                <Button variant="outline" size="sm" onClick={handleStartParsing}>
                  <PlayIcon className="w-4 h-4 mr-2" />
                  Start Parsing
                </Button>
              )}
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  onChange={(e) => e.target.files && handleFileUpload(e.target.files)}
                  className="hidden"
                  accept=".pdf,.doc,.docx,.txt,.md,.xlsx,.pptx,.html"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading || !selectedKnowledgeBaseId}
                >
                  {isUploading ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : (
                    <CloudArrowUpIcon className="w-4 h-4 mr-2" />
                  )}
                  Upload Documents
                </Button>
              </>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRetryIngestion}
                disabled={isRetrying || !hasRetryableDocs}
                title={hasRetryableDocs ? 'Re-process failed, stuck, and pending documents' : 'No documents need reprocessing'}
              >
                {isRetrying ? (
                  <Spinner size="sm" className="mr-2" />
                ) : (
                  <ArrowPathIcon className="w-4 h-4 mr-2" />
                )}
                Sync
              </Button>
              {isFasbWorkspace && (
                <Button variant="outline" size="sm" onClick={handleSyncStats} disabled={isSyncingStats}>
                  {isSyncingStats ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : (
                    <ArrowPathIcon className="w-4 h-4 mr-2" />
                  )}
                  Sync Stats
                </Button>
              )}
              {workspace && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (!isTelemetryEnabled) {
                      addToast({
                        kind: 'warning',
                        message: 'Function is disabled, contact an admin for help.',
                      });
                      return;
                    }
                    navigate(`/telemetry?workspaceId=${workspace.id}`);
                  }}
                >
                  <ChartBarIcon className="w-4 h-4 mr-2" />
                  Telemetry
                </Button>
              )}
              {canChat && workspace && (
                <Button variant="secondary" size="sm" onClick={() => navigate(`/chat/${workspace.id}`)}>
                  <ChatBubbleLeftRightIcon className="w-4 h-4 mr-2" />
                  Chat
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* RAG & AI settings: embedding (read-only) + chat model (Bedrock optional) */}
          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 dark:border-dark-border dark:bg-dark-surface">
            <h3 className="text-sm font-semibold text-charcoal dark:text-white mb-3">RAG & AI settings</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Embedding (vector store)</label>
                <p className="text-sm text-charcoal dark:text-white">
                  {ragSettings ? (
                    <>
                      <span className="font-medium capitalize">{ragSettings.embedding_provider}</span>
                      {' · '}
                      <span className="text-gray-600 dark:text-gray-300">{ragSettings.embedding_model}</span>
                    </>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Chat model (inference)</label>
                <div className="flex items-center gap-2">
                  <select
                    value={promptTemplate?.model ?? ''}
                    onChange={(e) => handleChatModelChange(e.target.value)}
                    disabled={savingChatModel || ragChatModels.length === 0}
                    className="h-9 min-w-[200px] rounded-md border border-gray-200 bg-white px-3 text-sm text-charcoal dark:border-dark-border dark:bg-dark-surface dark:text-white"
                  >
                    {ragChatModels.length === 0 ? (
                      <option value="">Loading…</option>
                    ) : (
                      <>
                        {promptTemplate?.model && !ragChatModels.some((m) => m.id === promptTemplate?.model) && (
                          <option value={promptTemplate.model}>{promptTemplate.model}</option>
                        )}
                        {ragChatModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.provider === 'bedrock' ? `Bedrock: ${m.name}` : `${m.name} (${m.provider})`}
                          </option>
                        ))}
                      </>
                    )}
                  </select>
                  {savingChatModel && <Spinner size="sm" />}
                </div>
              </div>
            </div>
          </div>

          {knowledgeBases.length > 0 && (
            <div className="mb-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {knowledgeBases.map((kb) => {
                const selected = selectedKnowledgeBaseId === kb.id;
                return (
                  <button
                    key={kb.id}
                    onClick={() => setSelectedKnowledgeBaseId(kb.id)}
                    className={`rounded-lg border p-3 text-left transition ${
                      selected
                        ? 'border-eliza-red bg-eliza-red/5 dark:border-eliza-red dark:bg-eliza-red/10'
                        : 'border-gray-200 bg-white hover:border-gray-300 dark:border-dark-border dark:bg-dark-surface'
                    }`}
                  >
                    <p className="text-sm font-semibold text-charcoal dark:text-white">{kb.name}</p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {kb.document_count} docs • {kb.chunk_count} chunks
                    </p>
                    {kb.source_type && (
                      <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">Source: {kb.source_type}</p>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* Parsing indicator */}
          {showSyncBanner && (
            <div className="mb-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-blue-700 dark:text-blue-300">
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
                {hasParsingDocs
                  ? 'Documents are being parsed. This page auto-refreshes.'
                  : 'Knowledge base sync is running. Documents will appear here shortly.'}
              </div>
            </div>
          )}

          {/* Documents Table */}
          {documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <DocumentTextIcon className="w-12 h-12 text-gray-300 dark:text-gray-600 mb-4" />
              <h3 className="text-lg font-semibold text-charcoal dark:text-white mb-2">
                No documents yet
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                {selectedKnowledgeBaseId
                  ? 'Upload documents to build this knowledge base.'
                  : 'Create a knowledge base first, then upload documents.'}
              </p>
              <>
                {!selectedKnowledgeBaseId ? (
                  <Button onClick={() => setShowCreateKbModal(true)}>
                    <PlusIcon className="w-4 h-4 mr-2" />
                    Create Knowledge Base
                  </Button>
                ) : (
                  <Button onClick={() => fileInputRef.current?.click()}>
                    <CloudArrowUpIcon className="w-4 h-4 mr-2" />
                    Upload Documents
                  </Button>
                )}
              </>
            </div>
          ) : (
            <DataTable
              columns={columns}
              data={documents}
              getRowId={(doc) => doc.id.toString()}
            />
          )}
        </div>
      </div>

      {showCreateKbModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowCreateKbModal(false)} />
          <div className="relative w-full max-w-xl rounded-xl border border-gray-200 bg-white p-6 shadow-xl dark:border-dark-border dark:bg-dark-surface">
            <h2 className="text-lg font-semibold text-charcoal dark:text-white">Create Knowledge Base</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Configure source, parser, and defaults for this workspace knowledge base.
            </p>

            <div className="mt-5 space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-charcoal dark:text-white">Name</label>
                <Input value={kbName} onChange={(e) => setKbName(e.target.value)} placeholder="Policy Docs" />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-charcoal dark:text-white">Description</label>
                <Input
                  value={kbDescription}
                  onChange={(e) => setKbDescription(e.target.value)}
                  placeholder="Optional description"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-charcoal dark:text-white">Source</label>
                  <select
                    value={kbSourceType}
                    onChange={(e) => setKbSourceType(e.target.value as 'elasticsearch' | 's3' | 'local_directory')}
                    className="h-10 w-full rounded-md border border-gray-200 bg-white px-3 text-sm text-gray-700 dark:border-dark-border dark:bg-dark-surface-2 dark:text-gray-200"
                  >
                    <option value="elasticsearch">Elasticsearch</option>
                    <option value="s3">S3</option>
                    <option value="local_directory">Local Directory (virtual path)</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-sm font-medium text-charcoal dark:text-white">Parser</label>
                  <select
                    value={kbParserType}
                    onChange={(e) =>
                      setKbParserType(e.target.value as 'naive' | 'deepdoc' | 'gpt-4o' | 'docling' | 'custom-vlm')
                    }
                    className="h-10 w-full rounded-md border border-gray-200 bg-white px-3 text-sm text-gray-700 dark:border-dark-border dark:bg-dark-surface-2 dark:text-gray-200"
                  >
                    <option value="naive">naive</option>
                    <option value="deepdoc">deepdoc</option>
                    <option value="gpt-4o">gpt-4o</option>
                    <option value="docling">docling</option>
                    <option value="custom-vlm">custom-vlm</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-charcoal dark:text-white">
                  {kbSourceType === 'elasticsearch'
                    ? 'Elasticsearch Index (optional)'
                    : kbSourceType === 's3'
                      ? 'S3 Bucket Path (required)'
                      : 'Virtual Local Path (optional)'}
                </label>
                <Input
                  value={kbSourceValue}
                  onChange={(e) => setKbSourceValue(e.target.value)}
                  placeholder={
                    kbSourceType === 'elasticsearch'
                      ? 'workspace_docs_index'
                      : kbSourceType === 's3'
                        ? 's3://tenant-documents/customers/acme/workspace-1/'
                        : '/imports/legal/'
                  }
                />
              </div>

              {kbParserType === 'custom-vlm' && (
                <div>
                  <label className="mb-1 block text-sm font-medium text-charcoal dark:text-white">
                    Custom VLM Model
                  </label>
                  <Input
                    value={kbCustomModel}
                    onChange={(e) => setKbCustomModel(e.target.value)}
                    placeholder="deepseek-ocr2@OpenAI-API-Compatible"
                  />
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowCreateKbModal(false)} disabled={isCreatingKb}>
                Cancel
              </Button>
              <Button
                onClick={handleCreateKnowledgeBase}
                disabled={isCreatingKb || (kbSourceType === 's3' && !kbSourceValue.trim())}
              >
                {isCreatingKb ? <Spinner size="sm" className="mr-2" /> : <PlusIcon className="mr-2 h-4 w-4" />}
                Create Knowledge Base
              </Button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

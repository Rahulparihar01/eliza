import React, { useState, useEffect, useCallback } from 'react';
import { useToasts } from '../../stores/useToasts';
import Layout from '../../components/layout/Layout';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Badge,
  Spinner,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  Label,
  Input,
  Textarea,
  Select,
  SelectOption,
  Checkbox,
} from '../../components/ui';
import {
  DocumentTextIcon,
  PlusIcon,
  CheckCircleIcon,
  ClockIcon,
  ArchiveBoxIcon,
  SparklesIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { useRAGWorkspaces } from '../../hooks/useRAGDomains';
import { WorkspaceSelector } from '../../components/common/RAGDomainSelector';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');
const LANGFUSE_UI_URL =
  process.env.REACT_APP_LANGFUSE_URL ||
  process.env.REACT_APP_LANGFUSE_PUBLIC_URL ||
  'http://localhost:3060';
const LANGFUSE_PROJECT_ID = process.env.REACT_APP_LANGFUSE_PROJECT_ID || 'eliza-platform';

// Types
interface PromptSummary {
  id: number;
  domain: string;
  prompt_type: string;
  name: string;
  version: number;
  is_active: boolean;
  status: string;
  usage_count: number;
  avg_quality_score?: number;
  gepa_job_id?: number;
  created_at: string;
  updated_at: string;
}

interface PromptDetail extends PromptSummary {
  description?: string;
  content: string;
  variables?: string[];
  created_by_user_id?: number;
  last_modified_by_user_id?: number;
  gepa_variant_id?: number;
}

interface DomainStats {
  domain: string;
  total_versions: number;
  active_count: number;
  draft_count: number;
  archived_count: number;
  gepa_optimized_count: number;
  total_usage: number;
  prompt_types: string[];
}

const PROMPT_TYPES = [
  { value: 'system', label: 'System Prompt', description: 'Main system instructions' },
  { value: 'query_rewrite', label: 'Query Rewrite', description: 'Query transformation prompt' },
  { value: 'retrieval', label: 'Retrieval', description: 'Retrieval instructions' },
  { value: 'synthesis', label: 'Answer Synthesis', description: 'Answer generation prompt' },
  { value: 'evaluation', label: 'Evaluation', description: 'Evaluation criteria' },
  { value: 'custom', label: 'Custom', description: 'User-defined prompt' },
];

export default function PromptManagementPage() {
  const token = localStorage.getItem('auth_token');
  const { push } = useToasts();

  // RAG Workspaces
  const {
    workspaces,
    selectedWorkspace,
    selectedWorkspaceId,
    setSelectedWorkspaceId,
    isLoading: isLoadingWorkspaces,
    error: workspacesError,
    refresh: refreshWorkspaces,
  } = useRAGWorkspaces({ autoSelect: true });
  
  // Get current workspace name for API calls
  const currentWorkspaceName = selectedWorkspace?.name || '';

  // State
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<PromptDetail | null>(null);
  const [domainStats, setDomainStats] = useState<DomainStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    domain: '',
    prompt_type: 'system',
    name: '',
    content: '',
    description: '',
    is_active: false,
  });

  const openLangfusePrompts = useCallback(() => {
    const promptsUrl = `${LANGFUSE_UI_URL.replace(/\/$/, '')}/project/${LANGFUSE_PROJECT_ID}/prompts`;
    window.open(promptsUrl, '_blank', 'noopener,noreferrer');
  }, []);
  // Fetch prompts for domain
  const fetchPrompts = useCallback(async (domain: string) => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE}/api/v1/prompts/templates?domain=${domain}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setPrompts(data.prompts || []);
      }
    } catch (e) {
      console.error('Failed to fetch prompts:', e);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // Fetch domain stats
  const fetchDomainStats = useCallback(async (domain: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/prompts/domains/${domain}/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setDomainStats(data);
      }
    } catch (e) {
      console.error('Failed to fetch domain stats:', e);
    }
  }, [token]);

  // Fetch prompt detail
  const fetchPromptDetail = async (promptId: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/prompts/templates/${promptId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedPrompt(data);
      }
    } catch (e) {
      console.error('Failed to fetch prompt detail:', e);
    }
  };

  // Create prompt
  const createPrompt = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/prompts/templates`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          domain: currentWorkspaceName || selectedDomain,
          prompt_type: formData.prompt_type,
          name: formData.name,
          content: formData.content,
          description: formData.description,
          is_active: formData.is_active,
        }),
      });

      if (res.ok) {
        push({ kind: 'success', message: 'Prompt created successfully' });
        setShowCreateModal(false);
        resetForm();
        if (selectedDomain) {
          fetchPrompts(selectedDomain);
          fetchDomainStats(selectedDomain);
        }
      } else {
        const error = await res.json();
        push({ kind: 'error', message: error.detail || 'Failed to create prompt' });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to create prompt' });
    }
  };

  // Activate prompt
  const activatePrompt = async (promptId: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/prompts/templates/${promptId}/activate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        push({ kind: 'success', message: 'Prompt activated' });
        if (selectedDomain) fetchPrompts(selectedDomain);
        if (selectedPrompt?.id === promptId) fetchPromptDetail(promptId);
      } else {
        const error = await res.json();
        push({ kind: 'error', message: error.detail || 'Failed to activate prompt' });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to activate prompt' });
    }
  };

  // Archive prompt
  const archivePrompt = async (promptId: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/prompts/templates/${promptId}/archive`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        push({ kind: 'success', message: 'Prompt archived' });
        if (selectedDomain) fetchPrompts(selectedDomain);
        setSelectedPrompt(null);
      } else {
        const error = await res.json();
        push({ kind: 'error', message: error.detail || 'Failed to archive prompt' });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to archive prompt' });
    }
  };

  const resetForm = () => {
    setFormData({
      domain: '',
      prompt_type: 'system',
      name: '',
      content: '',
      description: '',
      is_active: false,
    });
  };

  // Sync selected prompt domain with workspace
  useEffect(() => {
    if (currentWorkspaceName && currentWorkspaceName !== selectedDomain) {
      setSelectedDomain(currentWorkspaceName);
    }
  }, [currentWorkspaceName, selectedDomain]);

  useEffect(() => {
    if (selectedDomain) {
      fetchPrompts(selectedDomain);
      fetchDomainStats(selectedDomain);
    }
  }, [selectedDomain, fetchPrompts, fetchDomainStats]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircleIcon className="h-4 w-4 text-emerald-500" />;
      case 'draft':
        return <ClockIcon className="h-4 w-4 text-yellow-500" />;
      case 'archived':
        return <ArchiveBoxIcon className="h-4 w-4 text-gray-500" />;
      default:
        return <DocumentTextIcon className="h-4 w-4 text-gray-400 dark:text-gray-500" />;
    }
  };

  const getPromptTypeLabel = (type: string) => {
    return PROMPT_TYPES.find(t => t.value === type)?.label || type;
  };

  // Group prompts by type
  const promptsByType = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.prompt_type]) acc[prompt.prompt_type] = [];
    acc[prompt.prompt_type].push(prompt);
    return acc;
  }, {} as Record<string, PromptSummary[]>);

  return (
    <Layout>
      <Page layout="full-width">
      <PageHeader
        title="Prompt Management"
        description="Manage and version prompts for workspaces"
        actions={
          <Button
            variant="default"
            onClick={() => {
              setFormData({ ...formData, domain: currentWorkspaceName || '' });
              setShowCreateModal(true);
            }}
            disabled={!selectedWorkspace}
          >
            <PlusIcon className="h-4 w-4" />
            New Prompt
          </Button>
        }
      />

      <PageBody fill padded={false}>
        {/* Workspace bar - matches Evals/GEPA pattern */}
        <div className="flex items-center gap-4 px-6 py-2 h-[52px] border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400 whitespace-nowrap">Workspace</span>
            <WorkspaceSelector
              workspaces={workspaces}
              selectedWorkspaceId={selectedWorkspaceId}
              onSelect={(id) => {
                setSelectedWorkspaceId(id);
                setSelectedPrompt(null);
              }}
              isLoading={isLoadingWorkspaces}
              error={workspacesError}
              onRefresh={refreshWorkspaces}
              placeholder="Select workspace"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={openLangfusePrompts}
            >
              <ChartBarIcon className="h-4 w-4" />
              Langfuse Prompts
            </Button>
            {selectedWorkspace && (
              <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                {selectedWorkspace.document_count} docs &middot; {selectedWorkspace.chunk_count} chunks
              </span>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel - Prompts by Type */}
          <div className="w-80 border-r border-gray-200 dark:border-dark-border flex flex-col bg-white dark:bg-dark-surface shrink-0">
            <div className="p-3 border-b border-gray-200 dark:border-dark-border">
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100">
                Prompts {selectedDomain && <span className="text-gray-500 dark:text-gray-400">- {selectedDomain}</span>}
              </h3>
            </div>

            <div className="flex-1 overflow-y-auto p-3">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Spinner size="sm" />
                </div>
              ) : (
                PROMPT_TYPES.map(({ value, label }) => {
                  const typePrompts = promptsByType[value] || [];
                  const activePrompt = typePrompts.find(p => p.is_active);

                  return (
                    <div key={value} className="mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{label}</span>
                        {activePrompt && (
                          <span className="text-xs text-emerald-500">v{activePrompt.version} active</span>
                        )}
                      </div>

                      {typePrompts.length > 0 ? (
                        <div className="space-y-1">
                          {typePrompts.slice(0, 5).map((prompt) => (
                            <button
                              key={prompt.id}
                              onClick={() => fetchPromptDetail(prompt.id)}
                              className={`w-full text-left p-2 rounded-lg border transition-colors ${
                                selectedPrompt?.id === prompt.id
                                  ? 'bg-eliza-red/10 border-eliza-red/30'
                                  : 'bg-gray-50 dark:bg-dark-surface-2 border-transparent hover:border-gray-200 dark:hover:border-dark-border'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                {getStatusIcon(prompt.status)}
                                <span className="text-sm text-charcoal dark:text-gray-100 truncate flex-1">
                                  {prompt.name}
                                </span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">v{prompt.version}</span>
                              </div>
                              {prompt.gepa_job_id && (
                                <div className="flex items-center gap-1 mt-1">
                                  <SparklesIcon className="h-3 w-3 text-eliza-red" />
                                  <span className="text-xs text-eliza-red">GEPA optimized</span>
                                </div>
                              )}
                            </button>
                          ))}
                          {typePrompts.length > 5 && (
                            <Button variant="ghost" size="sm" className="text-xs">
                              +{typePrompts.length - 5} more versions
                            </Button>
                          )}
                        </div>
                      ) : (
                        <div className="text-xs text-gray-500 dark:text-gray-400 italic p-2 bg-gray-50 dark:bg-dark-surface-2 rounded">
                          No prompt configured
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Workspace Stats */}
            {domainStats && (
              <div className="p-3 border-t border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Active:</span>
                    <span className="ml-1 text-emerald-500 font-medium">{domainStats.active_count}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Drafts:</span>
                    <span className="ml-1 text-yellow-500 font-medium">{domainStats.draft_count}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Total:</span>
                    <span className="ml-1 text-charcoal dark:text-gray-100 font-medium">{domainStats.total_versions}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">GEPA:</span>
                    <span className="ml-1 text-eliza-red font-medium">{domainStats.gepa_optimized_count}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - Prompt Detail */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-dark-surface">
            {selectedPrompt ? (
              <>
                {/* Detail Header */}
                <div className="p-4 border-b border-gray-200 dark:border-dark-border">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(selectedPrompt.status)}
                      <div>
                        <h2 className="text-lg font-medium text-charcoal dark:text-gray-100">{selectedPrompt.name}</h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {getPromptTypeLabel(selectedPrompt.prompt_type)} &bull; Version {selectedPrompt.version}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!selectedPrompt.is_active && selectedPrompt.status !== 'archived' && (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => activatePrompt(selectedPrompt.id)}
                        >
                          <CheckCircleIcon className="h-4 w-4" />
                          Activate
                        </Button>
                      )}
                      {selectedPrompt.status !== 'archived' && !selectedPrompt.is_active && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => archivePrompt(selectedPrompt.id)}
                        >
                          <ArchiveBoxIcon className="h-4 w-4" />
                          Archive
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Badges */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge
                      variant={
                        selectedPrompt.status === 'active' ? 'success'
                        : selectedPrompt.status === 'draft' ? 'warning'
                        : selectedPrompt.status === 'testing' ? 'info'
                        : 'default'
                      }
                    >
                      {selectedPrompt.status}
                    </Badge>
                    {selectedPrompt.gepa_job_id && (
                      <Badge variant="brand">
                        GEPA Job #{selectedPrompt.gepa_job_id}
                      </Badge>
                    )}
                    {selectedPrompt.avg_quality_score && (
                      <Badge variant="success">
                        Quality: {selectedPrompt.avg_quality_score}%
                      </Badge>
                    )}
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      Used {selectedPrompt.usage_count} times
                    </span>
                  </div>
                </div>

                {/* Description */}
                {selectedPrompt.description && (
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
                    <p className="text-sm text-gray-500 dark:text-gray-400">{selectedPrompt.description}</p>
                  </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4">
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Prompt Content</h3>
                  <pre className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-4 text-sm text-charcoal dark:text-gray-100 whitespace-pre-wrap font-mono overflow-x-auto">
                    {selectedPrompt.content}
                  </pre>

                  {/* Variables */}
                  {selectedPrompt.variables && selectedPrompt.variables.length > 0 && (
                    <div className="mt-4">
                      <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Template Variables</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedPrompt.variables.map((v) => (
                          <span key={v} className="px-2 py-1 bg-gray-100 dark:bg-dark-surface-2 rounded text-xs text-gray-500 dark:text-gray-400 font-mono">
                            {`{{${v}}}`}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata */}
                  <div className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                    <p>Created: {new Date(selectedPrompt.created_at).toLocaleString()}</p>
                    <p>Updated: {new Date(selectedPrompt.updated_at).toLocaleString()}</p>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <DocumentTextIcon className="h-12 w-12 mx-auto mb-3 text-gray-400 dark:text-gray-500" />
                  <p className="text-sm text-charcoal dark:text-gray-100">Select a prompt to view details</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Create Prompt Sheet */}
        <Sheet open={showCreateModal} onClose={() => { setShowCreateModal(false); resetForm(); }}>
          <SheetContent side="right" size="2xl">
            <SheetHeader>
              <div>
                <SheetTitle>New Prompt</SheetTitle>
                <SheetDescription>Create a new prompt version for {currentWorkspaceName || 'your workspace'}</SheetDescription>
              </div>
            </SheetHeader>
            <SheetBody className="space-y-5">
              <div>
                <Label className="mb-2 block">Prompt Type</Label>
                <Select
                  value={formData.prompt_type}
                  onValueChange={(v) => setFormData({ ...formData, prompt_type: v })}
                >
                  {PROMPT_TYPES.map((t) => (
                    <SelectOption key={t.value} value={t.value}>{t.label}</SelectOption>
                  ))}
                </Select>
              </div>

              <div>
                <Label className="mb-2 block">Name</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., FASB System Prompt v1"
                />
              </div>

              <div>
                <Label className="mb-2 block">Description</Label>
                <Input
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Optional description"
                />
              </div>

              <div>
                <Label className="mb-2 block">Content</Label>
                <Textarea
                  value={formData.content}
                  onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                  placeholder="Enter your prompt here..."
                  rows={14}
                  className="font-mono text-sm"
                />
              </div>

              <Checkbox
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                label="Activate immediately"
                description="Replaces current active version for this prompt type"
              />
            </SheetBody>
            <SheetFooter className="flex items-center gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => { setShowCreateModal(false); resetForm(); }}>
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={createPrompt}
                disabled={!formData.name || !formData.content}
              >
                <PlusIcon className="h-4 w-4" />
                Create Prompt
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </PageBody>
      </Page>
    </Layout>
  );
}

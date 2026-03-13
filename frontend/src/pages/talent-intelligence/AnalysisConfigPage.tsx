/**
 * Talent Search Page (formerly Analysis Configuration)
 * 
 * Clean, Linear-style interface for managing talent analysis configurations.
 * Main page shows a table of saved configurations.
 * "New Analysis" opens a modal for creating/editing configurations.
 * 
 * MIGRATED TO DS (Jan 2026):
 * - Page, PageHeader, PageBody (layout)
 * - DataTable with expandable rows
 * - Button, Badge, Alert, Spinner, Progress
 * - Modal components for cancel confirmation
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  PlusIcon,
  PlayIcon,
  PencilIcon,
  TrashIcon,
  CheckCircleIcon,
  ClockIcon,
  DocumentTextIcon,
  DocumentDuplicateIcon,
  ArrowPathIcon,
  XCircleIcon,
  StopIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';
import NewAnalysisModal from '../../components/talent-intelligence/NewAnalysisModal';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Badge,
  Alert,
  Spinner,
  Progress,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  DataTable,
  DataTableActions,
  DataTableActionButton,
} from '../../components/ui';
import type { Column } from '../../components/ui';

// Types
interface AnalysisConfig {
  id?: number;  // Optional for new/copied configs
  name: string;
  description?: string;
  blueprint_id?: number;
  blueprint_name?: string;
  company_dna_id?: number;
  company_dna_name?: string;
  job_description?: string;
  selected_job_id?: string;
  candidate_source_id?: number;
  candidate_source_name?: string;
  department_ids?: number[];
  ideal_candidate_details?: string;
  market_search_limit?: number;
  last_run_at?: string;
  last_analysis_id?: string;
  last_run_status?: string;
  last_run_error?: string;
  run_count?: number;
  created_by_user_id?: number;
  created_by_username?: string;
  created_at?: string;
  updated_at?: string;
}

interface AnalysisStage {
  stage: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  message?: string;
}

interface AnalysisRun {
  analysis_id: string;
  config_id: number;
  status: string;
  error_message?: string;
  current_stage?: string;
  progress_percentage: number;
  stages: AnalysisStage[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
  candidate_count: number;
}

// Run Details Panel Component (Expanded Row Content)
function RunDetailsPanel({ 
  run, 
}: { 
  run: AnalysisRun | null; 
}) {
  if (!run) {
    return (
      <div className="text-center py-6 text-sm text-gray-500 dark:text-gray-400">
        No run details available yet
      </div>
    );
  }

  const getStageIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case 'running':
        return <ArrowPathIcon className="w-5 h-5 text-eliza-red animate-spin" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-red-500" />;
      case 'cancelled':
        return <StopIcon className="w-5 h-5 text-amber-500" />;
      default:
        return <div className="w-5 h-5 rounded-full border-2 border-gray-200 dark:border-dark-border" />;
    }
  };

  const getProgressVariant = () => {
    if (run.status === 'failed') return 'warning';
    if (run.status === 'completed') return 'success';
    return 'default';
  };

  return (
    <div className="w-full">
      {/* Error/Cancelled Banner */}
      {run.status === 'cancelled' && (
        <Alert variant="warning" className="mb-4">
          <div>
            <p className="font-medium">Analysis Cancelled</p>
            <p className="text-sm opacity-80 mt-1">
              This analysis was cancelled by the user
            </p>
          </div>
        </Alert>
      )}
      {run.status === 'failed' && run.error_message && (
        <Alert variant="error" className="mb-4">
          <div>
            <p className="font-medium">Analysis Failed</p>
            <p className="text-sm opacity-80 mt-1 font-mono break-all">
              {run.error_message}
            </p>
          </div>
        </Alert>
      )}

      {/* Main Content - Three columns */}
      <div className="flex gap-6">
        {/* Left: Progress bar and Stages (aligned together) */}
        <div className="flex-1 space-y-3">
          {/* Progress bar */}
          <div className="flex flex-col justify-center h-full">
            <Progress
              value={run.progress_percentage}
              size="lg"
              variant={getProgressVariant()}
              showLabel
            />

            {/* Stage List - aligned under progress bar */}
            <div className="grid grid-cols-7 gap-2 mt-4">
              {run.stages.map((stage, index) => (
                <div 
                  key={index}
                  className={`flex flex-col items-center p-3 rounded-lg ${
                    stage.status === 'running' ? 'bg-eliza-red/10 border border-eliza-red/30' :
                    stage.status === 'completed' ? 'bg-green-50 dark:bg-green-900/20' :
                    stage.status === 'cancelled' ? 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800' :
                    stage.status === 'failed' ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800' :
                    'bg-gray-50 dark:bg-dark-surface-2'
                  }`}
                >
                  {getStageIcon(stage.status)}
                  <span className="text-[13px] text-center text-gray-500 dark:text-gray-400 mt-2 leading-tight">
                    {stage.stage.replace('Stage ', '').replace(': ', '\n')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center: Candidates count */}
        {run.candidate_count > 0 && (
          <div className="flex-shrink-0 flex flex-col items-center justify-center px-4 border-l border-r border-gray-200 dark:border-dark-border">
            <span className="text-xs text-gray-500 dark:text-gray-400">Candidates</span>
            <p className="text-2xl font-bold text-charcoal dark:text-gray-100">{run.candidate_count}</p>
          </div>
        )}

        {/* Right: Metadata & Actions */}
        <div className="w-56 flex-shrink-0 space-y-3">
          <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1.5">
            <div className="flex justify-between">
              <span>Analysis ID:</span>
              <span className="font-mono text-charcoal dark:text-gray-100">{run.analysis_id.slice(0, 16)}...</span>
            </div>
            {run.started_at && (
              <div className="flex justify-between">
                <span>Started:</span>
                <span className="text-charcoal dark:text-gray-100">{new Date(run.started_at).toLocaleDateString()}</span>
              </div>
            )}
            {run.completed_at && (
              <div className="flex justify-between">
                <span>Completed:</span>
                <span className="text-charcoal dark:text-gray-100">{new Date(run.completed_at).toLocaleDateString()}</span>
              </div>
            )}
          </div>

          {/* Actions */}
          {run.status === 'completed' && (
            <div className="flex flex-col gap-2 pt-2">
              <Button size="sm" asChild>
                <a href={`/talent/outreach?analysis_id=${run.analysis_id}`}>
                  View Candidates
                </a>
              </Button>
              <Button variant="secondary" size="sm" asChild>
                <a href={`/talent/history?analysis_id=${run.analysis_id}`}>
                  View Full Report
                </a>
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Status Badge Helper
function getStatusBadge(status?: string, error?: string) {
  if (!status) return null;
  
  switch (status) {
    case 'completed':
      return (
        <Badge variant="success" className="inline-flex items-center gap-1">
          <CheckCircleIcon className="w-3 h-3" />
          Completed
        </Badge>
      );
    case 'processing':
    case 'pending':
      return (
        <Badge variant="info" className="inline-flex items-center gap-1">
          <ArrowPathIcon className="w-3 h-3 animate-spin" />
          Running
        </Badge>
      );
    case 'cancelled':
      return (
        <Badge variant="warning" className="inline-flex items-center gap-1">
          <StopIcon className="w-3 h-3" />
          Cancelled
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="danger" className="inline-flex items-center gap-1" title={error}>
          <XCircleIcon className="w-3 h-3" />
          Failed
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary">
          {status}
        </Badge>
      );
  }
}

export default function AnalysisConfigPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [configs, setConfigs] = useState<AnalysisConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AnalysisConfig | null>(null);
  const [expandedConfigId, setExpandedConfigId] = useState<number | null>(null);
  const [runDetails, setRunDetails] = useState<AnalysisRun | null>(null);
  const [runningAnalysisId, setRunningAnalysisId] = useState<number | null>(null);
  
  // Cancel modal state
  const [cancelModalConfig, setCancelModalConfig] = useState<AnalysisConfig | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Check for ?new=true query param to auto-open the modal
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setShowModal(true);
      setEditingConfig(null);
      // Clear the query param so it doesn't re-trigger on navigation
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Define callbacks first (before useEffects that depend on them)
  const loadConfigs = useCallback(async (showLoading: boolean = true) => {
    try {
      // Only show loading indicator on initial load, not on background refreshes
      if (showLoading) {
        setIsLoading(true);
      }
      const response = await AXIOS_INSTANCE.get('/api/v1/talent/analysis-configs');
      setConfigs(response.data.configs || []);
    } catch (err: any) {
      console.error('Failed to load configs:', err);
      setConfigs([]);
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }, []);

  const loadRunDetails = useCallback(async (configId: number) => {
    try {
      // Never show loading indicator - just update data in background for smooth UX
      const response = await AXIOS_INSTANCE.get(`/api/v1/talent/analysis-configs/${configId}/latest-run`);
      setRunDetails(response.data);
    } catch (err: any) {
      console.error('Failed to load run details:', err);
      // Don't clear run details on error - keep showing last known state
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  // Poll for status updates when an analysis is running
  useEffect(() => {
    if (!runningAnalysisId) return;
    
    const pollInterval = setInterval(async () => {
      // Use background refresh (showLoading=false) to avoid blinky UX
      await loadConfigs(false);
      // Also refresh run details if expanded
      if (expandedConfigId === runningAnalysisId) {
        loadRunDetails(runningAnalysisId);
      }
      const config = configs.find(c => c.id === runningAnalysisId);
      if (config?.last_run_status === 'completed' || config?.last_run_status === 'failed' || config?.last_run_status === 'cancelled') {
        setRunningAnalysisId(null);
        // Expand to show results/errors
        setExpandedConfigId(runningAnalysisId);
        loadRunDetails(runningAnalysisId);
      }
    }, 3000);
    
    return () => clearInterval(pollInterval);
  }, [runningAnalysisId, configs, expandedConfigId, loadRunDetails, loadConfigs]);
  
  // Also poll run details when expanded and analysis is in progress
  useEffect(() => {
    if (!expandedConfigId) return;
    
    const config = configs.find(c => c.id === expandedConfigId);
    // Only poll if analysis is still running (not completed, failed, or cancelled)
    if (!config?.last_run_status || config.last_run_status === 'completed' || config.last_run_status === 'failed' || config.last_run_status === 'cancelled') {
      return;
    }
    
    const pollInterval = setInterval(() => {
      loadRunDetails(expandedConfigId);
    }, 3000);
    
    return () => clearInterval(pollInterval);
  }, [expandedConfigId, configs, loadRunDetails]);

  const handleNewAnalysis = () => {
    setEditingConfig(null);
    setShowModal(true);
  };

  const handleEdit = (config: AnalysisConfig) => {
    setEditingConfig(config);
    setShowModal(true);
  };

  const handleCopy = (config: AnalysisConfig) => {
    // Create a copy of the config without the id, and with a new name
    const copiedConfig: AnalysisConfig = {
      // Copy all configuration fields
      name: `${config.name} (1)`,
      description: config.description,
      blueprint_id: config.blueprint_id,
      blueprint_name: config.blueprint_name,
      company_dna_id: config.company_dna_id,
      company_dna_name: config.company_dna_name,
      job_description: config.job_description,
      selected_job_id: config.selected_job_id,
      candidate_source_id: config.candidate_source_id,
      candidate_source_name: config.candidate_source_name,
      department_ids: config.department_ids,
      ideal_candidate_details: config.ideal_candidate_details,
      market_search_limit: config.market_search_limit,
      // Don't copy: id, run_count, last_run_*, created_at, updated_at
    };
    setEditingConfig(copiedConfig);
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this analysis configuration?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/talent/analysis-configs/${id}`);
      setConfigs(prev => prev.filter(c => c.id !== id));
      if (expandedConfigId === id) {
        setExpandedConfigId(null);
        setRunDetails(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete configuration');
    }
  };

  const handleRunAnalysis = async (config: AnalysisConfig) => {
    if (!config.id) return; // Guard for unsaved configs
    
    const configId = config.id; // Capture for type narrowing
    
    try {
      setError(null);
      const response = await AXIOS_INSTANCE.post(`/api/v1/talent/analysis-configs/${configId}/run`);
      
      // Update local state to show running
      setConfigs(prev => prev.map(c => 
        c.id === configId 
          ? { ...c, last_run_status: 'processing', last_analysis_id: response.data.analysis_id }
          : c
      ));
      
      // Start polling and expand to show progress
      setRunningAnalysisId(configId);
      setExpandedConfigId(configId);
      
      // Load initial run details
      setTimeout(() => loadRunDetails(configId), 1000);
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to start analysis';
      setError(errorMessage);
      
      // Also update the config to show the error
      setConfigs(prev => prev.map(c => 
        c.id === configId 
          ? { ...c, last_run_status: 'failed', last_run_error: errorMessage }
          : c
      ));
    }
  };

  const handleCancelClick = (config: AnalysisConfig) => {
    setCancelModalConfig(config);
  };

  const handleCancelConfirm = async () => {
    if (!cancelModalConfig?.id) return;
    
    const configId = cancelModalConfig.id;
    
    try {
      setIsCancelling(true);
      await AXIOS_INSTANCE.post(`/api/v1/talent/analysis-configs/${configId}/cancel`);
      
      // Update local state to show cancelled
      setConfigs(prev => prev.map(c => 
        c.id === configId 
          ? { ...c, last_run_status: 'failed', last_run_error: 'Cancelled by user' }
          : c
      ));
      
      // Stop polling
      if (runningAnalysisId === configId) {
        setRunningAnalysisId(null);
      }
      
      // Refresh run details if expanded
      if (expandedConfigId === configId) {
        loadRunDetails(configId);
      }
      
      setCancelModalConfig(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel analysis');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleCancelModalClose = () => {
    if (!isCancelling) {
      setCancelModalConfig(null);
    }
  };

  const handleModalClose = () => {
    setShowModal(false);
    setEditingConfig(null);
  };

  const handleModalSave = async (shouldRun: boolean) => {
    await loadConfigs();
    setShowModal(false);
    setEditingConfig(null);
    
    if (shouldRun) {
      // Don't redirect - show progress in-page
      // The modal will have already triggered the run
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // DataTable columns
  const columns: Column<AnalysisConfig>[] = [
    {
      id: 'name',
      header: 'Configuration',
      cell: ({ row }) => (
        <div>
          <div className="font-medium text-sm text-charcoal dark:text-gray-100">{row.name}</div>
          {row.description && (
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate max-w-md">
              {row.description}
            </div>
          )}
        </div>
      ),
    },
    {
      id: 'created_by',
      header: 'Created By',
      cell: ({ row }) => (
        row.created_by_username ? (
          <span className="text-sm text-charcoal dark:text-gray-100">{row.created_by_username}</span>
        ) : (
          <span className="text-sm text-gray-500 dark:text-gray-400">—</span>
        )
      ),
    },
    {
      id: 'blueprint',
      header: 'Blueprint',
      cell: ({ row }) => (
        row.blueprint_name ? (
          <span className="inline-flex items-center gap-1 text-sm text-charcoal dark:text-gray-100">
            <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
            {row.blueprint_name}
          </span>
        ) : (
          <span className="text-sm text-gray-500 dark:text-gray-400">—</span>
        )
      ),
    },
    {
      id: 'company_dna',
      header: 'Company DNA',
      cell: ({ row }) => (
        row.company_dna_name ? (
          <span className="inline-flex items-center gap-1 text-sm text-charcoal dark:text-gray-100">
            <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
            {row.company_dna_name}
          </span>
        ) : (
          <span className="text-sm text-gray-500 dark:text-gray-400">—</span>
        )
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: ({ row }) => getStatusBadge(row.last_run_status, row.last_run_error),
    },
    {
      id: 'last_run',
      header: 'Last Run',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {row.last_run_at ? (
            <span className="inline-flex items-center gap-1">
              <ClockIcon className="w-3.5 h-3.5" />
              {formatDate(row.last_run_at)}
            </span>
          ) : (
            '—'
          )}
        </span>
      ),
    },
    {
      id: 'run_count',
      header: 'Runs',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">{row.run_count ?? 0}</span>
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      cell: ({ row }) => (
        <DataTableActions>
          {/* Run or Cancel button based on status */}
          {row.last_run_status === 'processing' ? (
            <DataTableActionButton
              icon={<StopIcon className="w-4 h-4" />}
              label="Cancel Analysis"
              onClick={() => handleCancelClick(row)}
              variant="danger"
            />
          ) : (
            <DataTableActionButton
              icon={<PlayIcon className="w-4 h-4" />}
              label="Run Analysis"
              onClick={() => handleRunAnalysis(row)}
            />
          )}
          <DataTableActionButton
            icon={<PencilIcon className="w-4 h-4" />}
            label="Edit"
            onClick={() => handleEdit(row)}
          />
          <DataTableActionButton
            icon={<DocumentDuplicateIcon className="w-4 h-4" />}
            label="Duplicate"
            onClick={() => handleCopy(row)}
          />
          <DataTableActionButton
            icon={<TrashIcon className="w-4 h-4" />}
            label="Delete"
            onClick={() => row.id && handleDelete(row.id)}
            variant="danger"
          />
        </DataTableActions>
      ),
    },
  ];

  // Expanded row IDs for DataTable
  const expandedRows = expandedConfigId ? new Set([expandedConfigId]) : new Set<number>();

  const handleExpandedChange = (ids: Set<string | number>) => {
    const idArray = Array.from(ids);
    if (idArray.length === 0) {
      setExpandedConfigId(null);
      setRunDetails(null);
    } else {
      const newId = Number(idArray[0]);
      setExpandedConfigId(newId);
      loadRunDetails(newId);
    }
  };

  // Only allow expansion if the config has a last_analysis_id
  const getRowId = (row: AnalysisConfig) => row.id ?? 0;

  // Header actions
  const headerActions = (
    <Button onClick={handleNewAnalysis}>
      <PlusIcon className="w-4 h-4" />
      New Analysis
    </Button>
  );

  // Loading state
  if (isLoading) {
    return (
      <Page maxWidth="2xl">
        <PageHeader
          title="Talent Search Templates"
          description="Define search criteria and scoring profiles for candidate evaluation"
          actions={headerActions}
          bordered
        />
        <PageBody>
          <div className="flex items-center justify-center h-64">
            <Spinner size="lg" />
          </div>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="2xl">
      <PageHeader
        title="Talent Search Templates"
        description="Define search criteria and scoring profiles for candidate evaluation"
        actions={headerActions}
        bordered
      />
      <PageBody>
        {/* Error Banner */}
        {error && (
          <div className="mb-4">
            <Alert variant="error" onDismiss={() => setError(null)}>
              {error}
            </Alert>
          </div>
        )}

        {/* Data Table or Empty State */}
        {configs.length === 0 ? (
          <div className="text-center py-16">
            <DocumentTextIcon className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-4" />
            <h3 className="text-base font-medium text-charcoal dark:text-gray-100">
              No configurations yet
            </h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Create your first analysis configuration to get started
            </p>
            <Button className="mt-4" onClick={handleNewAnalysis}>
              <PlusIcon className="w-4 h-4" />
              New Analysis
            </Button>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={configs}
            getRowId={getRowId}
            loading={isLoading}
            emptyMessage="No configurations yet"
            emptyIcon={<DocumentTextIcon className="w-12 h-12" />}
            expandable
            expandedRows={expandedRows}
            onExpandedChange={handleExpandedChange}
            allowMultipleExpanded={false}
            renderExpandedRow={(row) => {
              // Only render if this row has a last_analysis_id
              if (!row.last_analysis_id) {
                return (
                  <div className="text-center py-4 text-sm text-gray-500 dark:text-gray-400">
                    No analysis has been run yet for this configuration.
                  </div>
                );
              }
              return <RunDetailsPanel run={runDetails} />;
            }}
            hoverable
          />
        )}
      </PageBody>

      {/* Cancel Confirmation Modal - DS Components */}
      <Modal open={!!cancelModalConfig} onClose={handleCancelModalClose}>
        <ModalBackdrop />
        <ModalContent size="md">
          <ModalHeader>
            <ModalTitle>Cancel Analysis</ModalTitle>
            <ModalDescription>This action cannot be undone</ModalDescription>
          </ModalHeader>
          <ModalBody>
            <p className="text-sm text-charcoal dark:text-gray-100">
              Are you sure you want to cancel the analysis for{' '}
              <span className="font-medium">"{cancelModalConfig?.name}"</span>?
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              The analysis will be stopped and marked as cancelled. Any partial results will be discarded.
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={handleCancelModalClose} disabled={isCancelling}>
              Go Back
            </Button>
            <Button variant="destructive" onClick={handleCancelConfirm} disabled={isCancelling}>
              {isCancelling && <Spinner size="sm" />}
              {isCancelling ? 'Cancelling...' : 'Yes, Cancel'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* New/Edit Analysis Modal (not migrated yet - phase 2) */}
      {showModal && (
        <NewAnalysisModal
          config={editingConfig}
          onClose={handleModalClose}
          onSave={handleModalSave}
        />
      )}
    </Page>
  );
}

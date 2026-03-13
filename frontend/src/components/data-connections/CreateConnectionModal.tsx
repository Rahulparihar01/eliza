/**
 * Create Connection Modal
 * 
 * Modern, clean modal for creating new data connector configurations.
 * Follows the same design patterns as the New Analysis modal.
 */

import React, { useEffect, useState, Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CurrencyDollarIcon,
  InformationCircleIcon,
  LinkIcon,
  CloudIcon,
  FolderIcon,
  BuildingOfficeIcon,
} from '@heroicons/react/24/outline';
import { ConnectorType, SyncMode } from '../../generated/connectors/connectors';
import {
  useCreateConnectorConfigurationApiConnectorsConfigurationsPost as useCreateConnector,
  useTestConnectionApiConnectorsTestConnectionPost as useTestConnection,
  useEstimateSyncCostApiConnectorsEstimateCostPost as useEstimateCost,
} from '../../generated/data-connectors/data-connectors';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../lib/query-keys';
import { useToasts } from '../../stores/useToasts';
import { Tooltip } from '../common/Tooltip';

interface CreateConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultConnectorType?: string;
}

interface ConnectionFormData {
  connector_name: string;
  connector_type: string;
  api_key: string;
  search_query: Record<string, any>;
  sync_config?: Record<string, any>;
  sync_mode: SyncMode;
  sync_schedule?: string;
  description?: string;
}

const CONNECTOR_OPTIONS = [
  {
    value: ConnectorType.PEOPLE_DATA_LABS,
    label: 'People Data Labs',
    description: 'Professional profile and company data',
    icon: CloudIcon,
    available: true,
  },
  {
    value: ConnectorType.GREENHOUSE,
    label: 'Greenhouse',
    description: 'ATS candidate and job data',
    icon: BuildingOfficeIcon,
    available: true,
  },
  {
    value: ConnectorType.HUBSPOT,
    label: 'HubSpot',
    description: 'CRM contacts, companies, and deals',
    icon: BuildingOfficeIcon,
    available: true,
  },
  {
    value: ConnectorType.FATHOM,
    label: 'Fathom',
    description: 'Meeting transcripts and summaries',
    icon: LinkIcon,
    available: true,
  },
  {
    value: ConnectorType.FILESYSTEM,
    label: 'File System',
    description: 'Local directory scanning',
    icon: FolderIcon,
    available: true,
  },
];

const PDL_QUERY_TEMPLATES = {
  empty: {},
  software_engineers: {
    job_title: ['software engineer', 'backend engineer', 'frontend engineer'],
    location_name: 'United States',
  },
  senior_leaders: {
    job_title_role: 'executive',
    job_title_levels: ['director', 'vp', 'c-suite'],
  },
};

export function CreateConnectionModal({ isOpen, onClose, defaultConnectorType }: CreateConnectionModalProps) {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  const resolvedConnectorType = defaultConnectorType ?? ConnectorType.PEOPLE_DATA_LABS;

  // Form state
  const [formData, setFormData] = useState<ConnectionFormData>({
    connector_name: '',
    connector_type: resolvedConnectorType,
    api_key: '',
    search_query: {},
    sync_config: resolvedConnectorType === ConnectorType.FILESYSTEM
      ? { directory_path: '', file_extensions: ['.pdf', '.docx', '.txt'], recursive: false }
      : {},
    sync_mode: SyncMode.FULL_REFRESH,
    sync_schedule: undefined,
    description: '',
  });

  const [queryJson, setQueryJson] = useState('{}');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [costEstimate, setCostEstimate] = useState<any>(null);

  // Mutations
  const { mutate: createConnector, isPending: isCreating } = useCreateConnector({
    mutation: {
      onSuccess: () => {
        addToast({ kind: 'success', message: 'Connection created successfully!' });
        queryClient.invalidateQueries({ queryKey: queryKeys.connectors.lists() });
        handleClose();
      },
      onError: (error: any) => {
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Failed to create connection.',
        });
      },
    },
  });

  const { mutate: testConnection, isPending: isTesting } = useTestConnection({
    mutation: {
      onSuccess: (data) => {
        setTestResult({ success: data.success, message: data.message });
        addToast({
          kind: data.success ? 'success' : 'error',
          message: data.message,
        });
      },
      onError: (error: any) => {
        setTestResult({ success: false, message: 'Connection test failed' });
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Connection test failed.',
        });
      },
    },
  });

  const { mutate: estimateCost, isPending: isEstimating } = useEstimateCost({
    mutation: {
      onSuccess: (data: any) => {
        setCostEstimate(data);
        addToast({
          kind: 'info',
          message: `Estimated ${data.estimated_record_count} records (~$${data.estimated_cost.toFixed(2)})`,
        });
      },
      onError: (error: any) => {
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Cost estimation failed.',
        });
      },
    },
  });

  useEffect(() => {
    if (isOpen) {
      setFormData((prev) => ({
        ...prev,
        connector_type: resolvedConnectorType,
        sync_config: resolvedConnectorType === ConnectorType.FILESYSTEM
          ? { directory_path: '', file_extensions: ['.pdf', '.docx', '.txt'], recursive: false }
          : {},
      }));
    }
  }, [isOpen, resolvedConnectorType]);

  const handleClose = () => {
    setFormData({
      connector_name: '',
      connector_type: resolvedConnectorType,
      api_key: '',
      search_query: {},
      sync_config: resolvedConnectorType === ConnectorType.FILESYSTEM
        ? { directory_path: '', file_extensions: ['.pdf', '.docx', '.txt'], recursive: false }
        : {},
      sync_mode: SyncMode.FULL_REFRESH,
      sync_schedule: undefined,
      description: '',
    });
    setQueryJson('{}');
    setTestResult(null);
    setCostEstimate(null);
    onClose();
  };

  const handleTestConnection = () => {
    testConnection({
      data: {
        connector_type: formData.connector_type,
        credentials: { api_key: formData.api_key },
      },
    });
  };

  const handleEstimateCost = () => {
    try {
      const query = JSON.parse(queryJson);
      estimateCost({
        data: {
          connector_type: formData.connector_type,
          credentials: { api_key: formData.api_key },
          sync_config: query,
        },
      });
    } catch {
      addToast({ kind: 'error', message: 'Invalid JSON in search query' });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validate based on connector type
    if (formData.connector_type === ConnectorType.FILESYSTEM) {
      if (!formData.connector_name || !formData.sync_config?.directory_path) {
        addToast({ kind: 'error', message: 'Please fill in all required fields.' });
        return;
      }
      createConnector({
        data: {
          connector_name: formData.connector_name,
          connector_type: formData.connector_type,
          credentials: {},
          sync_config: formData.sync_config,
          sync_mode: formData.sync_mode,
          description: formData.description,
          sync_schedule: formData.sync_schedule,
        },
      });
    } else if (formData.connector_type === ConnectorType.GREENHOUSE) {
      if (!formData.connector_name || !formData.api_key) {
        addToast({ kind: 'error', message: 'Please fill in all required fields.' });
        return;
      }
      createConnector({
        data: {
          connector_name: formData.connector_name,
          connector_type: formData.connector_type,
          credentials: { api_key: formData.api_key },
          sync_config: {
            max_candidates: formData.sync_config?.max_candidates || 50,
            job_ids: formData.sync_config?.job_ids || '',
          },
          sync_mode: formData.sync_mode,
          description: formData.description,
          sync_schedule: formData.sync_schedule,
        },
      });
    } else if (
      formData.connector_type === ConnectorType.HUBSPOT ||
      formData.connector_type === ConnectorType.FATHOM
    ) {
      if (!formData.connector_name || !formData.api_key) {
        addToast({ kind: 'error', message: 'Please fill in all required fields.' });
        return;
      }
      createConnector({
        data: {
          connector_name: formData.connector_name,
          connector_type: formData.connector_type,
          credentials: { api_key: formData.api_key },
          sync_config: {},
          sync_mode: formData.sync_mode,
          description: formData.description,
          sync_schedule: formData.sync_schedule,
        },
      });
    } else {
      if (!formData.connector_name || !formData.api_key) {
        addToast({ kind: 'error', message: 'Please fill in all required fields.' });
        return;
      }
      try {
        const query = JSON.parse(queryJson);
        createConnector({
          data: {
            connector_name: formData.connector_name,
            connector_type: formData.connector_type,
            credentials: { api_key: formData.api_key },
            sync_config: { search_query: query },  // PDL expects "search_query" not "query"
            sync_mode: formData.sync_mode,
            description: formData.description,
            sync_schedule: formData.sync_schedule,
          },
        });
      } catch {
        addToast({ kind: 'error', message: 'Invalid JSON in search query' });
      }
    }
  };

  const applyQueryTemplate = (templateKey: keyof typeof PDL_QUERY_TEMPLATES) => {
    const template = PDL_QUERY_TEMPLATES[templateKey];
    setQueryJson(JSON.stringify(template, null, 2));
    setFormData({ ...formData, search_query: template });
  };

  const selectedConnector = CONNECTOR_OPTIONS.find(c => c.value === formData.connector_type);

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-2xl bg-surface border border-border shadow-2xl transition-all">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-border">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10">
                      <LinkIcon className="h-5 w-5 text-brand" />
                    </div>
                    <div>
                      <Dialog.Title className="text-lg font-semibold text-text">
                        New Connection
                      </Dialog.Title>
                      <p className="text-xs text-muted">Configure a new data source</p>
                    </div>
                  </div>
                  <button
                    onClick={handleClose}
                    className="p-2 hover:bg-surface-2 rounded-lg transition-colors text-muted hover:text-text"
                  >
                    <XMarkIcon className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleSubmit}>
                  <div className="px-6 py-5 space-y-5 max-h-[calc(100vh-220px)] overflow-y-auto">
                    {/* Connector Type Selection */}
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Connector Type
                      </label>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {CONNECTOR_OPTIONS.map((option) => {
                          const Icon = option.icon;
                          const isSelected = formData.connector_type === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setFormData({ 
                                ...formData, 
                                connector_type: option.value,
                                sync_config: option.value === ConnectorType.FILESYSTEM
                                  ? { directory_path: '', file_extensions: ['.pdf', '.docx', '.txt'], recursive: false }
                                  : {},
                              })}
                              disabled={!option.available}
                              className={`
                                p-4 rounded-xl border-2 text-left transition-all duration-200
                                ${isSelected 
                                  ? 'border-brand bg-brand/5' 
                                  : 'border-border hover:border-brand/50 hover:bg-surface-2'
                                }
                                ${!option.available && 'opacity-50 cursor-not-allowed'}
                              `}
                            >
                              <Icon className={`h-6 w-6 mb-2 ${isSelected ? 'text-brand' : 'text-muted'}`} />
                              <p className={`text-sm font-medium ${isSelected ? 'text-brand' : 'text-text'}`}>
                                {option.label}
                              </p>
                              <p className="text-xs text-muted mt-0.5">{option.description}</p>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Connection Name */}
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Connection Name <span className="text-error">*</span>
                      </label>
                      <input
                        type="text"
                        value={formData.connector_name}
                        onChange={(e) => setFormData({ ...formData, connector_name: e.target.value })}
                        placeholder={`e.g., ${selectedConnector?.label || 'My'} Production Connection`}
                        className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                        required
                      />
                    </div>

                    {/* Filesystem-specific fields */}
                    {formData.connector_type === ConnectorType.FILESYSTEM && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Directory Path <span className="text-error">*</span>
                          </label>
                          <input
                            type="text"
                            value={formData.sync_config?.directory_path || ''}
                            onChange={(e) => setFormData({
                              ...formData,
                              sync_config: { ...formData.sync_config, directory_path: e.target.value },
                            })}
                            placeholder="/path/to/files"
                            className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                            required
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            File Extensions
                          </label>
                          <input
                            type="text"
                            value={formData.sync_config?.file_extensions?.join(', ') || ''}
                            onChange={(e) => {
                              const extensions = e.target.value.split(',').map((ext) => ext.trim()).filter((ext) => ext);
                              setFormData({
                                ...formData,
                                sync_config: { ...formData.sync_config, file_extensions: extensions },
                              });
                            }}
                            placeholder=".pdf, .docx, .txt"
                            className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                          />
                          <p className="mt-1.5 text-xs text-muted">Comma-separated list of file extensions to scan</p>
                        </div>

                        <label className="flex items-center gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={formData.sync_config?.recursive || false}
                            onChange={(e) => setFormData({
                              ...formData,
                              sync_config: { ...formData.sync_config, recursive: e.target.checked },
                            })}
                            className="h-4 w-4 rounded border-border text-brand focus:ring-2 focus:ring-brand/50"
                          />
                          <span className="text-sm text-text">Scan subdirectories recursively</span>
                        </label>
                      </>
                    )}

                    {/* Greenhouse specific fields */}
                    {formData.connector_type === ConnectorType.GREENHOUSE && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Harvest API Key <span className="text-error">*</span>
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="password"
                              value={formData.api_key}
                              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                              placeholder="Enter your Greenhouse Harvest API key"
                              className="flex-1 px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                              required
                            />
                            <button
                              type="button"
                              onClick={handleTestConnection}
                              disabled={!formData.api_key || isTesting}
                              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border bg-surface-2 text-text border-border hover:bg-surface-3 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isTesting ? <ArrowPathIcon className="w-4 h-4 animate-spin" /> : <CheckCircleIcon className="w-4 h-4" />}
                              Test
                            </button>
                          </div>
                          <p className="mt-1.5 text-xs text-muted">
                            Get your API key from Greenhouse: Configure → Dev Center → API Credential Management
                          </p>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-text mb-2">
                              Max Candidates
                            </label>
                            <input
                              type="number"
                              min="1"
                              max="1000"
                              value={formData.sync_config?.max_candidates || 50}
                              onChange={(e) => setFormData({
                                ...formData,
                                sync_config: { ...formData.sync_config, max_candidates: parseInt(e.target.value) || 50 },
                              })}
                              className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-text mb-2">
                              Job IDs <span className="text-xs text-muted">(optional)</span>
                            </label>
                            <input
                              type="text"
                              value={formData.sync_config?.job_ids || ''}
                              onChange={(e) => setFormData({
                                ...formData,
                                sync_config: { ...formData.sync_config, job_ids: e.target.value },
                              })}
                              placeholder="123, 456, 789"
                              className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                            />
                          </div>
                        </div>
                      </>
                    )}

                    {(formData.connector_type === ConnectorType.HUBSPOT ||
                      formData.connector_type === ConnectorType.FATHOM) && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            API Key <span className="text-error">*</span>
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="password"
                              value={formData.api_key}
                              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                              placeholder={
                                formData.connector_type === ConnectorType.HUBSPOT
                                  ? 'Enter your HubSpot private app token'
                                  : 'Enter your Fathom API key'
                              }
                              className="flex-1 px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                              required
                            />
                            <button
                              type="button"
                              onClick={handleTestConnection}
                              disabled={!formData.api_key || isTesting}
                              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border bg-surface-2 text-text border-border hover:bg-surface-3 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isTesting ? <ArrowPathIcon className="w-4 h-4 animate-spin" /> : <CheckCircleIcon className="w-4 h-4" />}
                              Test
                            </button>
                          </div>
                          {testResult && (
                            <div className={`mt-2 p-3 rounded-xl flex items-start gap-2 text-sm ${
                              testResult.success ? 'bg-success/10 text-success' : 'bg-error/10 text-error'
                            }`}>
                              {testResult.success ? <CheckCircleIcon className="w-5 h-5 flex-shrink-0" /> : <ExclamationCircleIcon className="w-5 h-5 flex-shrink-0" />}
                              <span>{testResult.message}</span>
                            </div>
                          )}
                        </div>
                      </>
                    )}

                    {/* People Data Labs specific fields */}
                    {formData.connector_type === ConnectorType.PEOPLE_DATA_LABS && (
                      <>
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            API Key <span className="text-error">*</span>
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="password"
                              value={formData.api_key}
                              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                              placeholder="Enter your PDL API key"
                              className="flex-1 px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                              required
                            />
                            <button
                              type="button"
                              onClick={handleTestConnection}
                              disabled={!formData.api_key || isTesting}
                              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border bg-surface-2 text-text border-border hover:bg-surface-3 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isTesting ? <ArrowPathIcon className="w-4 h-4 animate-spin" /> : <CheckCircleIcon className="w-4 h-4" />}
                              Test
                            </button>
                          </div>
                          {testResult && (
                            <div className={`mt-2 p-3 rounded-xl flex items-start gap-2 text-sm ${
                              testResult.success ? 'bg-success/10 text-success' : 'bg-error/10 text-error'
                            }`}>
                              {testResult.success ? <CheckCircleIcon className="w-5 h-5 flex-shrink-0" /> : <ExclamationCircleIcon className="w-5 h-5 flex-shrink-0" />}
                              <span>{testResult.message}</span>
                            </div>
                          )}
                        </div>

                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-text flex items-center gap-1">
                              Search Query (JSON)
                              <Tooltip content="PDL API search query in JSON format" position="top">
                                <InformationCircleIcon className="w-4 h-4 text-muted" />
                              </Tooltip>
                            </label>
                            <div className="flex gap-2">
                              {Object.keys(PDL_QUERY_TEMPLATES).map((key) => (
                                <button
                                  key={key}
                                  type="button"
                                  onClick={() => applyQueryTemplate(key as keyof typeof PDL_QUERY_TEMPLATES)}
                                  className="text-xs text-brand hover:text-brand-strong hover:underline"
                                >
                                  {key === 'empty' ? 'Clear' : key.replace(/_/g, ' ')}
                                </button>
                              ))}
                            </div>
                          </div>
                          <textarea
                            value={queryJson}
                            onChange={(e) => setQueryJson(e.target.value)}
                            placeholder='{"job_title": ["software engineer"], "location_name": "United States"}'
                            className="w-full px-4 py-3 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors resize-none font-mono"
                            rows={5}
                          />
                          <div className="mt-2 flex items-center gap-3">
                            <button
                              type="button"
                              onClick={handleEstimateCost}
                              disabled={!formData.api_key || !queryJson || isEstimating}
                              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 border bg-surface-2 text-muted border-border hover:bg-surface-3 hover:text-text disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isEstimating ? <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" /> : <CurrencyDollarIcon className="w-3.5 h-3.5" />}
                              Estimate Cost
                            </button>
                            {costEstimate && (
                              <span className="text-xs text-muted">
                                ~{costEstimate.estimated_record_count} records • ${costEstimate.estimated_cost.toFixed(2)}
                              </span>
                            )}
                          </div>
                        </div>
                      </>
                    )}

                    {/* Sync Mode */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-text mb-2">
                          Sync Mode
                        </label>
                        <select
                          value={formData.sync_mode}
                          onChange={(e) => setFormData({ ...formData, sync_mode: e.target.value as SyncMode })}
                          className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors appearance-none bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw2IDZMMTEgMSIgc3Ryb2tlPSIjOEIzQTUyIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==')] bg-[length:12px] bg-[position:right_1rem_center] bg-no-repeat pr-10"
                        >
                          <option value={SyncMode.FULL_REFRESH}>Full Refresh</option>
                          <option value={SyncMode.INCREMENTAL}>Incremental</option>
                        </select>
                      </div>

                      {formData.connector_type !== ConnectorType.FILESYSTEM && (
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Schedule <span className="text-xs text-muted">(optional)</span>
                          </label>
                          <input
                            type="text"
                            value={formData.sync_schedule || ''}
                            onChange={(e) => setFormData({ ...formData, sync_schedule: e.target.value })}
                            placeholder="e.g., 0 2 * * *"
                            className="w-full px-4 py-2.5 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors"
                          />
                        </div>
                      )}
                    </div>

                    {/* Description */}
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Description <span className="text-xs text-muted">(optional)</span>
                      </label>
                      <textarea
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        placeholder="Describe the purpose of this connection"
                        className="w-full px-4 py-3 border border-border rounded-xl bg-surface text-text text-sm placeholder-muted focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand transition-colors resize-none"
                        rows={2}
                      />
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-surface-2/50">
                    <button
                      type="button"
                      onClick={handleClose}
                      className="px-4 py-2 text-sm font-medium rounded-xl transition-all duration-200 border bg-surface text-muted border-border hover:bg-surface-2 hover:text-text"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={
                        isCreating ||
                        !formData.connector_name ||
                        (formData.connector_type === ConnectorType.PEOPLE_DATA_LABS && !formData.api_key) ||
                        (formData.connector_type === ConnectorType.GREENHOUSE && !formData.api_key) ||
                        (formData.connector_type === ConnectorType.HUBSPOT && !formData.api_key) ||
                        (formData.connector_type === ConnectorType.FATHOM && !formData.api_key) ||
                        (formData.connector_type === ConnectorType.FILESYSTEM && !formData.sync_config?.directory_path)
                      }
                      className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-xl transition-all duration-200 bg-brand text-on-brand hover:bg-brand-strong disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isCreating && <ArrowPathIcon className="w-4 h-4 animate-spin" />}
                      {isCreating ? 'Creating...' : 'Create Connection'}
                    </button>
                  </div>
                </form>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

/**
 * Connection Detail View
 * 
 * Detailed view of a data connector with sync history, statistics, and logs
 */

import React, { useState, Fragment } from 'react';
import { Dialog, Transition, Tab } from '@headlessui/react';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  PlayIcon,
  PencilIcon,
  TrashIcon,
  ChartBarIcon,
  DocumentTextIcon,
  CloudArrowUpIcon,
} from '@heroicons/react/24/outline';
import {
  useGetConnector,
  useListSyncRuns,
  useGetConnectorStatistics,
  useGetSyncTelemetry,
  useTriggerSync,
  useDeleteConnector,
  type ConnectorConfiguration,
} from '../../generated/connectors/connectors';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../lib/query-keys';
import { useToasts } from '../../stores/useToasts';
import { format } from 'date-fns';
import { formatConnectorActivityTime, formatRelativeApiTime, parseApiDate } from './dateUtils';

interface ConnectionDetailViewProps {
  isOpen: boolean;
  connectorId: number | null;
  onClose: () => void;
  onEdit?: (connector: ConnectorConfiguration) => void;
}

const STATUS_COLORS = {
  completed: 'text-success bg-success/10',
  failed: 'text-error bg-error/10',
  running: 'text-primary bg-primary/10',
  pending: 'text-muted bg-surface-3',
  cancelled: 'text-warning bg-warning/10',
};

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(' ');
}

export function ConnectionDetailView({
  isOpen,
  connectorId,
  onClose,
  onEdit,
}: ConnectionDetailViewProps) {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();
  const [selectedTab, setSelectedTab] = useState(0);

  // Fetch connector details
  const { data: connector, isLoading: isLoadingConnector } = useGetConnector(
    connectorId?.toString() || '',
    {
      query: {
        enabled: !!connectorId && isOpen,
        staleTime: 5000,
        refetchInterval: selectedTab === 1 ? 5000 : 30000, // Refresh sync history more frequently
      },
    }
  );

  // Fetch sync history
  const { data: syncHistory, isLoading: isLoadingSyncHistory } = useListSyncRuns(
    {
      connector_id: connectorId?.toString(),
    },
    {
      query: {
        enabled: !!connectorId && isOpen && selectedTab === 1,
        staleTime: 5000,
        refetchInterval: 5000,
      },
    }
  );

  // Fetch statistics
  const { data: statistics, isLoading: isLoadingStats } = useGetConnectorStatistics(
    connectorId?.toString() || '',
    {
      query: {
        enabled: !!connectorId && isOpen && selectedTab === 2,
        staleTime: 10000,
      },
    }
  );

  // Fetch telemetry
  const { data: telemetry, isLoading: isLoadingTelemetry } = useGetSyncTelemetry(
    connectorId?.toString() || '',
    {},
    {
      query: {
        enabled: !!connectorId && isOpen && selectedTab === 3,
        staleTime: 5000,
        refetchInterval: 5000,
      },
    }
  );

  // Mutations
  const { mutate: triggerSync, isPending: isSyncing } = useTriggerSync(connectorId?.toString() || '0', {
    mutation: {
      onSuccess: () => {
        addToast({
          kind: 'success',
          message: 'Sync started successfully!',
        });
        queryClient.invalidateQueries({ queryKey: queryKeys.connectors.detail(connectorId!) });
        queryClient.invalidateQueries({
          queryKey: queryKeys.connectors.syncHistory(connectorId!),
        });
      },
      onError: (error: any) => {
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Failed to start sync.',
        });
      },
    },
  });

  const { mutate: deleteConnector, isPending: isDeleting } = useDeleteConnector({
    mutation: {
      onSuccess: () => {
        addToast({
          kind: 'success',
          message: 'Connection deleted successfully!',
        });
        queryClient.invalidateQueries({ queryKey: queryKeys.connectors.lists() });
        onClose();
      },
      onError: (error: any) => {
        addToast({
          kind: 'error',
          message: error?.response?.data?.detail || 'Failed to delete connection.',
        });
      },
    },
  });

  const handleTriggerSync = () => {
    if (!connector) return;
    triggerSync({
      sync_mode: connector.sync_mode,
    });
  };

  const handleDelete = () => {
    if (!connector) return;
    if (window.confirm(`Are you sure you want to delete "${connector.connector_name}"?`)) {
      deleteConnector(connector.id.toString());
    }
  };

  const handleEdit = () => {
    if (connector && onEdit) {
      onEdit(connector);
      onClose();
    }
  };

  if (!connectorId) return null;

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-5xl transform overflow-hidden rounded-2xl bg-surface text-left align-middle shadow-xl transition-all">
                {isLoadingConnector ? (
                  <div className="p-12 flex items-center justify-center">
                    <ArrowPathIcon className="w-8 h-8 animate-spin text-primary" />
                  </div>
                ) : connector ? (
                  <>
                    {/* Header */}
                    <div className="bg-surface-2 px-6 py-4 border-b border-border">
                      <div className="flex items-start justify-between">
                        <div>
                          <Dialog.Title className="text-2xl font-bold text-foreground">
                            {connector.connector_name}
                          </Dialog.Title>
                          <p className="text-sm text-muted mt-1">
                            {connector.connector_type.replace('_', ' ').toUpperCase()} •{' '}
                            {connector.is_enabled ? (
                              <span className="text-success">Enabled</span>
                            ) : (
                              <span className="text-muted-2">Disabled</span>
                            )}{' '}
                            • Last updated {formatConnectorActivityTime(connector)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={handleTriggerSync}
                            disabled={isSyncing}
                            className="btn-primary btn-sm"
                          >
                            {isSyncing ? (
                              <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                              <PlayIcon className="w-4 h-4 mr-2" />
                            )}
                            Sync Now
                          </button>
                          <button onClick={handleEdit} className="btn-secondary btn-sm">
                            <PencilIcon className="w-4 h-4 mr-2" />
                            Edit
                          </button>
                          <button
                            onClick={handleDelete}
                            disabled={isDeleting}
                            className="btn-secondary btn-sm text-error hover:bg-error/10"
                          >
                            <TrashIcon className="w-4 h-4 mr-2" />
                            Delete
                          </button>
                          <button
                            onClick={onClose}
                            className="p-2 hover:bg-surface-3 rounded-lg transition-colors"
                          >
                            <XMarkIcon className="w-5 h-5 text-muted-2" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Tabs */}
                    <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
                      <Tab.List className="flex space-x-1 bg-surface-2 px-6 border-b border-border">
                        {['Overview', 'Sync History', 'Statistics', 'Logs'].map((tab) => (
                          <Tab
                            key={tab}
                            className={({ selected }) =>
                              classNames(
                                'px-4 py-3 text-sm font-medium transition-colors',
                                'focus:outline-none',
                                selected
                                  ? 'text-primary border-b-2 border-primary'
                                  : 'text-muted-2 hover:text-foreground hover:bg-surface-3'
                              )
                            }
                          >
                            {tab}
                          </Tab>
                        ))}
                      </Tab.List>

                      <Tab.Panels className="p-6 max-h-[600px] overflow-y-auto">
                        {/* Overview Tab */}
                        <Tab.Panel>
                          <div className="space-y-6">
                            <div className="grid grid-cols-2 gap-6">
                              <div>
                                <h3 className="text-sm font-medium text-muted mb-2">
                                  Connection Details
                                </h3>
                                <dl className="space-y-3">
                                  <div>
                                    <dt className="text-xs text-muted-2">Type</dt>
                                    <dd className="text-sm text-foreground capitalize">
                                      {connector.connector_type.replace('_', ' ')}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="text-xs text-muted-2">Sync Mode</dt>
                                    <dd className="text-sm text-foreground capitalize">
                                      {connector.sync_mode.replace('_', ' ')}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt className="text-xs text-muted-2">Created</dt>
                                    <dd className="text-sm text-foreground">
                                      {(() => {
                                        const createdAt = parseApiDate(connector.created_at);
                                        return createdAt ? format(createdAt, 'MMM d, yyyy HH:mm') : '—';
                                      })()}
                                    </dd>
                                  </div>
                                </dl>
                              </div>

                              <div>
                                <h3 className="text-sm font-medium text-muted mb-2">
                                  Configuration
                                </h3>
                                <pre className="text-xs bg-surface-3 p-3 rounded overflow-x-auto">
                                  {JSON.stringify(connector.sync_config, null, 2)}
                                </pre>
                              </div>
                            </div>

                            {connector.description && (
                              <div>
                                <h3 className="text-sm font-medium text-muted mb-2">Description</h3>
                                <p className="text-sm text-foreground">{connector.description}</p>
                              </div>
                            )}
                          </div>
                        </Tab.Panel>

                        {/* Sync History Tab */}
                        <Tab.Panel>
                          {isLoadingSyncHistory ? (
                            <div className="flex items-center justify-center py-12">
                              <ArrowPathIcon className="w-6 h-6 animate-spin text-primary" />
                            </div>
                          ) : syncHistory && syncHistory.sync_runs && syncHistory.sync_runs.length > 0 ? (
                            <div className="space-y-3">
                              {syncHistory.sync_runs.map((run: any) => (
                                <div
                                  key={run.id}
                                  className="p-4 bg-surface-2 rounded-lg border border-border"
                                >
                                  <div className="flex items-start justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                      <span
                                        className={`px-2 py-1 rounded text-xs font-medium ${
                                          STATUS_COLORS[run.status as keyof typeof STATUS_COLORS] ||
                                          'text-muted bg-surface-3'
                                        }`}
                                      >
                                        {run.status}
                                      </span>
                                      <span className="text-sm text-muted-2">
                                        {formatRelativeApiTime(run.started_at)}
                                      </span>
                                    </div>
                                    <div className="text-right">
                                      <div className="text-sm text-foreground">
                                        {run.records_loaded || 0} records
                                      </div>
                                      {run.completed_at && (
                                        <div className="text-xs text-muted-2">
                                          {(() => {
                                            const startedAt = parseApiDate(run.started_at);
                                            const completedAt = parseApiDate(run.completed_at);
                                            if (!startedAt || !completedAt) {
                                              return null;
                                            }
                                            const seconds = Math.round(
                                              (completedAt.getTime() - startedAt.getTime()) / 1000
                                            );
                                            return <>Duration: {seconds}s</>;
                                          })()}
                                        </div>
                                      )}
                                    </div>
                                  </div>

                                  <div className="grid grid-cols-4 gap-4 text-xs">
                                    <div>
                                      <div className="text-muted-2">Extracted</div>
                                      <div className="text-foreground">{run.records_extracted || 0}</div>
                                    </div>
                                    <div>
                                      <div className="text-muted-2">Loaded</div>
                                      <div className="text-foreground">{run.records_loaded || 0}</div>
                                    </div>
                                    <div>
                                      <div className="text-muted-2">Skipped</div>
                                      <div className="text-foreground">{run.records_skipped || 0}</div>
                                    </div>
                                    <div>
                                      <div className="text-muted-2">Errors</div>
                                      <div className="text-error">{run.error_count || 0}</div>
                                    </div>
                                  </div>

                                  {run.error_message && (
                                    <div className="mt-3 p-2 bg-error/10 rounded text-xs text-error">
                                      {run.error_message}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                              <ClockIcon className="w-12 h-12 text-muted-2 mb-3" />
                              <p className="text-muted">No sync history yet</p>
                              <p className="text-sm text-muted-2 mt-1">
                                Trigger a sync to see history here
                              </p>
                            </div>
                          )}
                        </Tab.Panel>

                        {/* Statistics Tab */}
                        <Tab.Panel>
                          {isLoadingStats ? (
                            <div className="flex items-center justify-center py-12">
                              <ArrowPathIcon className="w-6 h-6 animate-spin text-primary" />
                            </div>
                          ) : statistics ? (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                              <div className="p-4 bg-surface-2 rounded-lg border border-border">
                                <ChartBarIcon className="w-8 h-8 text-primary mb-2" />
                                <div className="text-2xl font-bold text-foreground">
                                  {statistics.total_sync_runs || 0}
                                </div>
                                <div className="text-sm text-muted">Total Syncs</div>
                              </div>
                              <div className="p-4 bg-surface-2 rounded-lg border border-border">
                                <CheckCircleIcon className="w-8 h-8 text-success mb-2" />
                                <div className="text-2xl font-bold text-foreground">
                                  {statistics.successful_sync_runs || 0}
                                </div>
                                <div className="text-sm text-muted">Successful</div>
                              </div>
                              <div className="p-4 bg-surface-2 rounded-lg border border-border">
                                <ExclamationCircleIcon className="w-8 h-8 text-error mb-2" />
                                <div className="text-2xl font-bold text-foreground">
                                  {statistics.failed_sync_runs || 0}
                                </div>
                                <div className="text-sm text-muted">Failed</div>
                              </div>
                              <div className="p-4 bg-surface-2 rounded-lg border border-border">
                                <CloudArrowUpIcon className="w-8 h-8 text-info mb-2" />
                                <div className="text-2xl font-bold text-foreground">
                                  {statistics.total_records_ingested?.toLocaleString() || 0}
                                </div>
                                <div className="text-sm text-muted">Records Ingested</div>
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                              <ChartBarIcon className="w-12 h-12 text-muted-2 mb-3" />
                              <p className="text-muted">No statistics available</p>
                            </div>
                          )}
                        </Tab.Panel>

                        {/* Logs Tab */}
                        <Tab.Panel>
                          {isLoadingTelemetry ? (
                            <div className="flex items-center justify-center py-12">
                              <ArrowPathIcon className="w-6 h-6 animate-spin text-primary" />
                            </div>
                          ) : telemetry && telemetry.events && telemetry.events.length > 0 ? (
                            <div className="space-y-2">
                              {telemetry.events.map((event: any) => (
                                <div
                                  key={event.id}
                                  className="p-3 bg-surface-2 rounded border border-border font-mono text-xs"
                                >
                                  <div className="flex items-start justify-between mb-1">
                                    <span className="text-primary">{event.event_type}</span>
                                    <span className="text-muted-2">
                                      {format(new Date(event.timestamp), 'MMM d, HH:mm:ss')}
                                    </span>
                                  </div>
                                  {event.user_message && (
                                    <div className="text-foreground">{event.user_message}</div>
                                  )}
                                  {event.progress_percentage !== null && (
                                    <div className="text-muted-2">
                                      Progress: {event.progress_percentage}%
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                              <DocumentTextIcon className="w-12 h-12 text-muted-2 mb-3" />
                              <p className="text-muted">No logs available</p>
                            </div>
                          )}
                        </Tab.Panel>
                      </Tab.Panels>
                    </Tab.Group>
                  </>
                ) : (
                  <div className="p-12 text-center">
                    <ExclamationCircleIcon className="w-12 h-12 text-error mx-auto mb-3" />
                    <p className="text-muted">Connection not found</p>
                  </div>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

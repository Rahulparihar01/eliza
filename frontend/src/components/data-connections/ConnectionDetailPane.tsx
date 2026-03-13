/**
 * Connection Detail Pane
 * 
 * Shows detailed information about a selected data connection.
 * Follows the same design patterns as the candidate detail pane.
 */

import React, { useMemo } from 'react';
import {
  ArrowPathIcon,
  ChartBarIcon,
  CheckCircleIcon,
  ClockIcon,
  CloudArrowUpIcon,
  ExclamationCircleIcon,
  LinkIcon,
  PlayIcon,
  TrashIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';
import {
  useGetConnector,
  useListSyncRuns,
  useGetConnectorStatistics,
  useTriggerSync,
  useDeleteConnector,
} from '../../generated/connectors/connectors';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../../lib/query-keys';
import { useToasts } from '../../stores/useToasts';
import { CONNECTOR_TYPE_LABELS } from './ConnectionsListView';
import { cn } from '../../shared/lib/cn';
import { format } from 'date-fns';
import {
  formatConnectorActivityTime,
  formatRelativeApiTime,
  parseApiDate,
} from './dateUtils';

interface ConnectionDetailPaneProps {
  connectorId: string | null;
  onDeleted?: () => void;
}

const RUN_STATUS_STYLES: Record<string, string> = {
  completed: 'bg-green-500/10 text-green-500',
  failed: 'bg-red-500/10 text-red-500',
  running: 'bg-eliza-red/10 text-eliza-red',
  pending: 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400',
  cancelled: 'bg-amber-500/10 text-amber-500',
};

export function ConnectionDetailPane({ connectorId, onDeleted }: ConnectionDetailPaneProps) {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  const connectorKey = connectorId || '';

  const { data: connector, isLoading: isConnectorLoading } = useGetConnector(connectorKey, {
    query: {
      enabled: !!connectorId,
      staleTime: 15000,
      refetchInterval: 30000,
    },
  });

  const { data: syncHistoryData, isLoading: isSyncHistoryLoading } = useListSyncRuns(
    { connector_id: connectorKey || undefined },
    { query: { enabled: !!connectorId, staleTime: 10000 } }
  );

  const { data: statistics, isLoading: isStatisticsLoading } = useGetConnectorStatistics(connectorKey, {
    query: { enabled: !!connectorId, staleTime: 20000 },
  });

  const { mutate: triggerSync, isPending: isSyncing } = useTriggerSync(connectorId ?? '', {
    mutation: {
      onSuccess: () => {
        addToast({ kind: 'success', message: 'Sync started successfully!' });
        if (connectorId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.connectors.detail(connectorId) });
          queryClient.invalidateQueries({ queryKey: queryKeys.connectors.syncHistory(connectorId) });
          queryClient.invalidateQueries({ queryKey: queryKeys.connectors.statistics(connectorId) });
        }
      },
      onError: (error: any) => {
        addToast({ kind: 'error', message: error?.response?.data?.detail || 'Failed to start sync.' });
      },
    },
  });

  const { mutate: deleteConnector, isPending: isDeleting } = useDeleteConnector({
    mutation: {
      onSuccess: () => {
        addToast({ kind: 'success', message: 'Connection deleted successfully!' });
        if (connectorId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.connectors.lists() });
        }
        onDeleted?.();
      },
      onError: (error: any) => {
        addToast({ kind: 'error', message: error?.response?.data?.detail || 'Failed to delete connection.' });
      },
    },
  });

  const recentRuns = useMemo(() => {
    const runs = syncHistoryData?.sync_runs ?? [];
    return runs.slice(0, 5);
  }, [syncHistoryData]);

  const totalSyncRuns = statistics?.total_sync_runs ?? 0;
  const successfulSyncs = statistics?.successful_sync_runs ?? 0;
  const failedSyncs = statistics?.failed_sync_runs ?? 0;
  const recordsIngested = statistics?.total_records_ingested ?? 0;
  const createdAt = parseApiDate(connector?.created_at);

  const handleTriggerSync = () => {
    if (!connector) return;
    triggerSync({ sync_mode: connector.sync_mode });
  };

  const handleDelete = () => {
    if (!connector) return;
    if (window.confirm(`Delete connection "${connector.connector_name}"? This action cannot be undone.`)) {
      deleteConnector(connector.id.toString());
    }
  };

  // Empty state
  if (!connectorId) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-dark-surface-2 mb-4">
          <LinkIcon className="h-8 w-8 text-gray-400 dark:text-gray-500" />
        </div>
        <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Select a connection</h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-xs">
          Choose a connection from the list to view details and manage syncs.
        </p>
      </div>
    );
  }

  // Loading state
  if (isConnectorLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-eliza-red mb-3" />
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading connection details…</p>
      </div>
    );
  }

  // Error state
  if (!connector) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/10 mb-4">
          <ExclamationCircleIcon className="h-8 w-8 text-red-500" />
        </div>
        <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Connection not found</h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-xs">
          This connection may have been deleted or is no longer available.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-5 border-b border-gray-200 dark:border-dark-border">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-eliza-red/10">
              <LinkIcon className="h-6 w-6 text-eliza-red" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-charcoal dark:text-gray-100 truncate">
                {connector.connector_name}
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <span className="px-2 py-0.5 rounded-md bg-gray-100 dark:bg-dark-surface-2 text-xs font-medium">
                  {CONNECTOR_TYPE_LABELS[connector.connector_type] || connector.connector_type}
                </span>
                <span>•</span>
                <span>Updated {formatConnectorActivityTime(connector)}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-col items-end gap-3 flex-shrink-0">
            <span className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium',
              connector.is_enabled ? 'bg-green-500/10 text-green-500' : 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400'
            )}>
              {connector.is_enabled ? <CheckCircleIcon className="h-3.5 w-3.5" /> : <ClockIcon className="h-3.5 w-3.5" />}
              {connector.is_enabled ? 'Active' : 'Inactive'}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={handleTriggerSync}
                disabled={isSyncing}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 bg-eliza-red text-white hover:bg-eliza-red-light disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSyncing ? <ArrowPathIcon className="h-3.5 w-3.5 animate-spin" /> : <PlayIcon className="h-3.5 w-3.5" />}
                Sync Now
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border bg-gray-50 dark:bg-dark-surface-2 text-red-500 border-gray-200 dark:border-dark-border hover:bg-red-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <TrashIcon className="h-3.5 w-3.5" />
                {isDeleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Metrics */}
          <section>
            <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4 flex items-center gap-2">
              <ChartBarIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
              Key Metrics
            </h3>
            {isStatisticsLoading ? (
              <div className="flex items-center justify-center py-8">
                <ArrowPathIcon className="h-5 w-5 animate-spin text-eliza-red" />
              </div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard icon={<ChartBarIcon className="h-5 w-5" />} label="Total Syncs" value={totalSyncRuns} color="brand" />
                <MetricCard icon={<CheckCircleIcon className="h-5 w-5" />} label="Successful" value={successfulSyncs} color="success" />
                <MetricCard icon={<ExclamationCircleIcon className="h-5 w-5" />} label="Failed" value={failedSyncs} color="error" />
                <MetricCard icon={<CloudArrowUpIcon className="h-5 w-5" />} label="Records" value={recordsIngested} color="info" />
              </div>
            )}
          </section>

          {/* Recent Sync Runs */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 flex items-center gap-2">
                <ArrowPathIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                Recent Sync Runs
              </h3>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {isSyncHistoryLoading ? 'Loading…' : `${recentRuns.length} of ${(syncHistoryData?.sync_runs?.length ?? 0)} shown`}
              </span>
            </div>

            {isSyncHistoryLoading ? (
              <div className="flex items-center justify-center py-8">
                <ArrowPathIcon className="h-5 w-5 animate-spin text-eliza-red" />
              </div>
            ) : recentRuns.length === 0 ? (
              <div className="text-center py-8 px-4 border border-dashed border-gray-200 dark:border-dark-border rounded-xl">
                <p className="text-sm text-gray-500 dark:text-gray-400">No sync runs yet. Click "Sync Now" to start.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {recentRuns.map((run: any) => {
                  const statusStyle = RUN_STATUS_STYLES[run.status] || 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400';
                  const startedAt = parseApiDate(run.started_at);
                  const completedAt = parseApiDate(run.completed_at);
                  const durationSeconds = startedAt && completedAt
                    ? Math.round((completedAt.getTime() - startedAt.getTime()) / 1000)
                    : null;

                  return (
                    <div key={run.id} className="p-4 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium uppercase', statusStyle)}>
                          {run.status}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {formatRelativeApiTime(run.started_at)}
                        </span>
                      </div>

                      <div className="grid grid-cols-4 gap-4 text-xs">
                        <div>
                          <p className="text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Extracted</p>
                          <p className="text-charcoal dark:text-gray-100 font-medium">{(run.records_extracted || 0).toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Loaded</p>
                          <p className="text-charcoal dark:text-gray-100 font-medium">{(run.records_loaded || 0).toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Skipped</p>
                          <p className="text-charcoal dark:text-gray-100 font-medium">{(run.records_skipped || 0).toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">Errors</p>
                          <p className={cn('font-medium', run.error_count > 0 ? 'text-red-500' : 'text-charcoal dark:text-gray-100')}>
                            {(run.error_count || 0).toLocaleString()}
                          </p>
                        </div>
                      </div>

                      {durationSeconds !== null && (
                        <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
                          Duration: {durationSeconds}s • Mode: {run.sync_mode?.replace(/_/g, ' ') || '—'}
                        </p>
                      )}

                      {run.error_message && (
                        <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-500">
                          {run.error_message}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Connection Details */}
          <section>
            <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4 flex items-center gap-2">
              <Cog6ToothIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
              Connection Details
            </h3>
            <div className="rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
              <dl className="divide-y divide-gray-200 dark:divide-dark-border">
                <DetailRow label="Type" value={CONNECTOR_TYPE_LABELS[connector.connector_type] || connector.connector_type} />
                <DetailRow label="Sync Mode" value={connector.sync_mode?.replace(/_/g, ' ') || '—'} />
                <DetailRow label="Created" value={createdAt ? format(createdAt, 'MMM d, yyyy HH:mm') : '—'} />
                {connector.sync_schedule && (
                  <DetailRow label="Schedule" value={connector.sync_schedule} />
                )}
              </dl>
            </div>
          </section>

          {/* Description */}
          {connector.description && (
            <section>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Description</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">{connector.description}</p>
            </section>
          )}

          {/* Configuration */}
          <section>
            <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Configuration</h3>
            <pre className="p-4 rounded-xl bg-gray-50 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border text-xs text-gray-500 dark:text-gray-400 overflow-x-auto font-mono">
              {JSON.stringify(connector.sync_config, null, 2)}
            </pre>
          </section>
        </div>
      </div>
    </div>
  );
}

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: 'brand' | 'success' | 'error' | 'info';
}

function MetricCard({ icon, label, value, color }: MetricCardProps) {
  const colorClasses = {
    brand: 'bg-eliza-red/10 text-eliza-red',
    success: 'bg-green-500/10 text-green-500',
    error: 'bg-red-500/10 text-red-500',
    info: 'bg-blue-500/10 text-blue-500',
  };

  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
      <div className={cn('inline-flex h-10 w-10 items-center justify-center rounded-lg mb-3', colorClasses[color])}>
        {icon}
      </div>
      <p className="text-2xl font-semibold text-charcoal dark:text-gray-100">{value.toLocaleString()}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 uppercase tracking-wide">{label}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <dt className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</dt>
      <dd className="text-sm text-charcoal dark:text-gray-100 font-medium">{value}</dd>
    </div>
  );
}

export default ConnectionDetailPane;

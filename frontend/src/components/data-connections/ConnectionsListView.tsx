/**
 * Connections List View
 * 
 * Displays a filterable, searchable list of data connections.
 * Follows the same design patterns as the Search Results candidate list.
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowPathIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  LinkIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';
import {
  useListConnectors,
  type ConnectorConfiguration,
  type ConnectorType,
} from '../../generated/connectors/connectors';
import { cn } from '../../shared/lib/cn';
import { Button } from '../ui';
import { formatConnectorActivityTime, getConnectorActivityDate } from './dateUtils';

interface ConnectionsListViewProps {
  onCreateNew: () => void;
  onSelectConnection: (connection: ConnectorConfiguration | null) => void;
  selectedConnectionId: string | null;
  className?: string;
}

export const CONNECTOR_TYPE_LABELS: Record<string, string> = {
  people_data_labs: 'People Data Labs',
  salesforce: 'Salesforce',
  hubspot: 'HubSpot',
  fathom: 'Fathom',
  greenhouse: 'Greenhouse',
  filesystem: 'File System',
  custom: 'Custom',
};

type StatusFilter = 'all' | 'enabled' | 'disabled';
type TypeFilter = 'all' | ConnectorType;

export function ConnectionsListView({
  onCreateNew,
  onSelectConnection,
  selectedConnectionId,
  className,
}: ConnectionsListViewProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: connectorsResponse, isLoading } = useListConnectors(
    {
      ...(statusFilter !== 'all' ? { is_enabled: statusFilter === 'enabled' } : {}),
      ...(typeFilter !== 'all' ? { connector_type: typeFilter } : {}),
    },
    {
      query: {
        staleTime: 15000,
        refetchInterval: 30000,
      },
    }
  );

  const connectors = connectorsResponse?.connectors ?? [];

  const filteredConnectors = useMemo(() => {
    const searched = searchQuery
      ? connectors.filter((connector) => {
          const query = searchQuery.toLowerCase();
          return (
            connector.connector_name.toLowerCase().includes(query) ||
            connector.connector_type.toLowerCase().includes(query)
          );
        })
      : connectors;

    return [...searched].sort((a, b) => {
      const aUpdated = getConnectorActivityDate(a)?.getTime() ?? 0;
      const bUpdated = getConnectorActivityDate(b)?.getTime() ?? 0;
      return bUpdated - aUpdated;
    });
  }, [connectors, searchQuery]);

  useEffect(() => {
    if (filteredConnectors.length === 0) {
      if (selectedConnectionId !== null) {
        onSelectConnection(null);
      }
      return;
    }

    const selectedExists = filteredConnectors.some(
      (connector) => connector.connector_id === selectedConnectionId
    );

    if (!selectedExists) {
      onSelectConnection(filteredConnectors[0]);
    }
  }, [filteredConnectors, onSelectConnection, selectedConnectionId]);

  const totalCount = connectors.length;
  const filteredCount = filteredConnectors.length;

  return (
    <div className={cn('h-full flex flex-col min-h-0', className)}>
      {/* List Header */}
      <div className="flex-shrink-0 px-4 py-4 border-b border-gray-200 dark:border-dark-border">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-charcoal dark:text-gray-100">Connections</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {filteredCount} of {totalCount} sources
            </p>
          </div>
          <button
            onClick={onCreateNew}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border bg-gray-50 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:bg-gray-100 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-gray-100"
          >
            <PlusIcon className="h-3.5 w-3.5" />
            Add
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search connections..."
            className="w-full h-9 pl-9 pr-3 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface text-charcoal dark:text-gray-100 text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red transition-colors"
          />
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500 dark:text-gray-400" />
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-3.5 w-3.5 text-gray-500 dark:text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="h-8 px-2 pr-7 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface text-charcoal dark:text-gray-100 text-xs focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red transition-colors appearance-none bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw2IDZMMTEgMSIgc3Ryb2tlPSIjOEIzQTUyIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==')] bg-[length:10px] bg-[position:right_0.5rem_center] bg-no-repeat"
          >
            <option value="all">All Status</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
            className="h-8 px-2 pr-7 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface text-charcoal dark:text-gray-100 text-xs focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red transition-colors appearance-none bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw2IDZMMTEgMSIgc3Ryb2tlPSIjOEIzQTUyIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==')] bg-[length:10px] bg-[position:right_0.5rem_center] bg-no-repeat"
          >
            <option value="all">All Types</option>
            <option value="people_data_labs">People Data Labs</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="filesystem">File System</option>
            <option value="salesforce">Salesforce</option>
            <option value="hubspot">HubSpot</option>
            <option value="fathom">Fathom</option>
          </select>
        </div>
      </div>

      {/* Connections List */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {isLoading ? (
          <div className="flex h-48 items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-center">
              <ArrowPathIcon className="h-6 w-6 animate-spin text-eliza-red" />
              <p className="text-sm text-gray-500 dark:text-gray-400">Loading connections…</p>
            </div>
          </div>
        ) : filteredConnectors.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center px-6 text-center">
            {connectors.length === 0 && !searchQuery && statusFilter === 'all' && typeFilter === 'all' ? (
              <>
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-dark-surface-2 mb-4">
                  <LinkIcon className="h-8 w-8 text-gray-400 dark:text-gray-500" />
                </div>
                <h3 className="text-base font-medium text-charcoal dark:text-gray-100">No connections yet</h3>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-xs">
                  Connect your first data source to begin ingesting talent data.
                </p>
                <Button onClick={onCreateNew} className="mt-4">
                  <PlusIcon className="h-4 w-4" />
                  Create Connection
                </Button>
              </>
            ) : (
              <>
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-dark-surface-2 mb-4">
                  <ExclamationCircleIcon className="h-8 w-8 text-gray-400 dark:text-gray-500" />
                </div>
                <h3 className="text-base font-medium text-charcoal dark:text-gray-100">No matches found</h3>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-xs">
                  Try adjusting your search or filters.
                </p>
                <button
                  onClick={() => {
                    setSearchQuery('');
                    setStatusFilter('all');
                    setTypeFilter('all');
                  }}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-full transition-all duration-200 border bg-gray-50 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:bg-gray-100 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-gray-100"
                >
                  Clear filters
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {filteredConnectors.map((connector) => {
              const isActive = connector.connector_id === selectedConnectionId;

              return (
                <button
                  key={connector.id}
                  type="button"
                  onClick={() => onSelectConnection(connector)}
                  className={cn(
                    'w-full text-left px-4 py-3 rounded-lg transition-all duration-150',
                    isActive
                      ? 'bg-eliza-red/10 border border-eliza-red/30'
                      : 'hover:bg-gray-50 dark:hover:bg-dark-surface-2 border border-transparent'
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg',
                      isActive ? 'bg-eliza-red/20 text-eliza-red' : 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400'
                    )}>
                      <LinkIcon className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className={cn(
                          'text-sm font-medium truncate',
                          isActive ? 'text-eliza-red' : 'text-charcoal dark:text-gray-100'
                        )}>
                          {connector.connector_name}
                        </p>
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium flex-shrink-0',
                            connector.is_enabled
                              ? 'bg-green-500/10 text-green-500'
                              : 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400'
                          )}
                        >
                          {connector.is_enabled ? (
                            <CheckCircleIcon className="h-3 w-3" />
                          ) : (
                            <ClockIcon className="h-3 w-3" />
                          )}
                          {connector.is_enabled ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                        <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-surface-2 text-[10px] font-medium">
                          {CONNECTOR_TYPE_LABELS[connector.connector_type] || connector.connector_type}
                        </span>
                        <span>•</span>
                        <span>
                          {formatConnectorActivityTime(connector)}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConnectionsListView;

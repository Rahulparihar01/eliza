/**
 * Data Source Selector Component
 * 
 * Allows selection of a data connector (filesystem, HR system, etc.) that contains
 * applicant resumes to be analyzed.
 */

import React from 'react';
import {
  FolderIcon,
  DocumentIcon,
  CheckCircleIcon,
  ArrowLeftIcon,
  BuildingOfficeIcon,
} from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/20/solid';
import LoadingSpinner from '../common/LoadingSpinner';
import { useListConnectorConfigurationsApiConnectorsConfigurationsGet } from '../../generated/data-connectors/data-connectors';

interface DataSourceSelectorProps {
  selectedConnectorId: string | null;
  onConnectorSelect: (connectorId: string | null) => void;
  onContinue: (connectorId: string) => void;
  onBack: () => void;
}

export function DataSourceSelector({
  selectedConnectorId,
  onConnectorSelect,
  onContinue,
  onBack,
}: DataSourceSelectorProps) {
  const { data: connectorsData, isLoading } = useListConnectorConfigurationsApiConnectorsConfigurationsGet({
    is_enabled: true  // Only show enabled connectors
  });

  const connectors = connectorsData?.connectors || [];
  
  // Filter for filesystem connectors (or other HR-related connectors)
  const applicantSources = connectors.filter(
    (conn) => conn.connector_type === 'filesystem' || conn.connector_type === 'greenhouse'
  );

  const canContinue = selectedConnectorId !== null;

  // Toggle selection - click to select, click again to deselect
  const handleConnectorClick = (connectorId: string) => {
    if (selectedConnectorId === connectorId) {
      // Deselect if clicking the same connector
      onConnectorSelect(null);
    } else {
      // Select new connector
      onConnectorSelect(connectorId);
    }
  };

  return (
    <div className="space-y-4">
      {/* Connector List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : applicantSources.length === 0 ? (
        <div className="text-center py-12 text-muted-2 bg-surface-2 rounded-lg border border-border">
          <FolderIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="font-medium">No data sources configured</p>
          <p className="text-sm mt-1">
            Set up a filesystem connector or HR system integration in Data Connections
          </p>
          <a
            href="/data-connections"
            className="inline-block mt-4 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-strong transition-colors"
          >
            Go to Data Connections
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {applicantSources.map((connector) => {
            const isSelected = selectedConnectorId === connector.connector_id;
            const isFilesystem = connector.connector_type === 'filesystem';

            return (
              <button
                key={connector.connector_id}
                onClick={() => handleConnectorClick(connector.connector_id)}
                className={`w-full p-5 rounded-lg border-2 transition-all text-left ${
                  isSelected
                    ? 'border-brand bg-brand/5'
                    : 'border-border bg-surface hover:border-muted-2'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div
                    className={`flex-shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center ${
                      isSelected
                        ? 'border-brand bg-brand'
                        : 'border-border bg-surface'
                    }`}
                  >
                    {isSelected && <CheckIcon className="w-4 h-4 text-white" />}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {isFilesystem ? (
                        <FolderIcon className="w-5 h-5 text-brand" />
                      ) : connector.connector_type === 'greenhouse' ? (
                        <BuildingOfficeIcon className="w-5 h-5 text-brand" />
                      ) : (
                        <DocumentIcon className="w-5 h-5 text-brand" />
                      )}
                      <h4 className="font-semibold text-text">{connector.connector_name}</h4>
                      {connector.is_enabled && (
                        <span className="px-2 py-0.5 bg-success/10 text-success text-xs rounded-full">
                          Active
                        </span>
                      )}
                    </div>

                    {connector.description && (
                      <p className="text-sm text-muted-2 mb-2">{connector.description}</p>
                    )}

                    <div className="flex items-center gap-4 text-xs text-muted-2">
                      <span className="capitalize">{connector.connector_type}</span>
                      {connector.last_sync_at && (
                        <span>
                          Last sync: {new Date(connector.last_sync_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>

                    {/* Show preview info if available */}
                    {isFilesystem && connector.sync_config && (
                      <div className="mt-2 p-2 bg-surface-2 rounded text-xs text-muted-2">
                        <div className="flex items-center gap-2">
                          <DocumentIcon className="w-4 h-4" />
                          <span>
                            {(connector.sync_config as any).directory_path || 'Local filesystem'}
                          </span>
                        </div>
                      </div>
                    )}
                    {connector.connector_type === 'greenhouse' && connector.sync_config && (
                      <div className="mt-2 p-2 bg-surface-2 rounded text-xs text-muted-2">
                        <div className="flex items-center gap-2">
                          <BuildingOfficeIcon className="w-4 h-4" />
                          <span>
                            Greenhouse ATS
                            {(connector.sync_config as any).max_candidates && 
                              ` • Up to ${(connector.sync_config as any).max_candidates} candidates`}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-border">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 text-muted-2 hover:text-text transition-colors"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          <span>Back</span>
        </button>

        <div className="flex items-center gap-4">
          {selectedConnectorId && (
            <>
              <div className="flex items-center gap-2 text-sm text-muted-2">
                <CheckCircleIcon className="w-5 h-5 text-success" />
                <span>Data source selected</span>
              </div>
              <button
                onClick={() => onConnectorSelect(null)}
                className="px-4 py-2 text-sm text-muted-2 hover:text-text transition-colors"
              >
                Clear Selection
              </button>
            </>
          )}
          <button
            onClick={() => selectedConnectorId && onContinue(selectedConnectorId)}
            disabled={!canContinue}
            className={`px-6 py-2 rounded-lg font-medium transition-colors ${
              canContinue
                ? 'bg-brand text-white hover:bg-brand-strong'
                : 'bg-surface-3 text-muted-2 cursor-not-allowed'
            }`}
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}


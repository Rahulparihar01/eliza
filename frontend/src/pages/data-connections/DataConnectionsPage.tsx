/**
 * Data Connections Page
 * 
 * Manage external data source connections with a clean, modern interface.
 * Follows the same design patterns as Search Results and Talent Configuration pages.
 */

import React, { useState } from 'react';
import { 
  PlusIcon, 
  LinkIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { ConnectionsListView } from '../../components/data-connections/ConnectionsListView';
import { CreateConnectionModal } from '../../components/data-connections/CreateConnectionModal';
import { ConnectionDetailPane } from '../../components/data-connections/ConnectionDetailPane';
import { type ConnectorConfiguration } from '../../generated/connectors/connectors';
import { useGetAvailableConnectorTypesApiConnectorsTypesGet } from '../../generated/data-connectors/data-connectors';
import { ReadableDropdown, type ReadableDropdownOption } from '../../components/common/ReadableDropdown';
import { Button } from '../../components/ui';

interface NewConnectionMenuProps {
  onSelect: (type: string) => void;
}

function NewConnectionMenu({ onSelect }: NewConnectionMenuProps) {
  const { data: connectorTypesData, isLoading } = useGetAvailableConnectorTypesApiConnectorsTypesGet();
  const allConnectors = connectorTypesData?.connector_types || [];
  
  // Only show available connectors (hide "coming soon" ones)
  const availableConnectors = allConnectors.filter(c => c.available);

  const dropdownOptions: ReadableDropdownOption[] = availableConnectors.map((connector) => ({
    key: connector.type,
    label: connector.name,
    description: connector.description,
    onClick: () => onSelect(connector.type),
  }));

  return (
    <ReadableDropdown
      trigger={
        <Button disabled={isLoading}>
          <PlusIcon className="h-4 w-4" />
          New Connection
          <ChevronDownIcon className="h-3.5 w-3.5" />
        </Button>
      }
      options={dropdownOptions}
      align="right"
      disabled={isLoading}
    />
  );
}

export function DataConnectionsPage() {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createConnectorType, setCreateConnectorType] = useState<string>('people_data_labs');

  const openCreateModal = (type: string = 'people_data_labs') => {
    setCreateConnectorType(type);
    setShowCreateModal(true);
  };

  const handleSelectConnection = (connection: ConnectorConfiguration | null) => {
    setSelectedConnectionId(connection ? connection.connector_id : null);
  };

  const handleConnectorDeleted = () => {
    setSelectedConnectionId(null);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-gray-50 dark:bg-dark-bg">
      {/* Page Header */}
      <div className="flex-shrink-0 border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
        <div className="px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-eliza-red/10">
                <LinkIcon className="h-6 w-6 text-eliza-red" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-charcoal dark:text-gray-100">Data Connections</h1>
                <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                  Connect and manage external data sources for talent intelligence
                </p>
              </div>
            </div>
            <NewConnectionMenu onSelect={openCreateModal} />
          </div>
        </div>
      </div>

      {/* Main Content - Split Pane Layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Panel - Connections List */}
        <div className="w-[380px] flex-shrink-0 border-r border-gray-200 dark:border-dark-border overflow-hidden flex flex-col bg-white dark:bg-dark-surface">
          <ConnectionsListView
            className="flex-1 min-h-0"
            onCreateNew={() => openCreateModal('people_data_labs')}
            onSelectConnection={handleSelectConnection}
            selectedConnectionId={selectedConnectionId}
          />
        </div>

        {/* Right Panel - Connection Details */}
        <div className="flex-1 min-h-0 overflow-hidden bg-white dark:bg-dark-surface">
          <ConnectionDetailPane 
            connectorId={selectedConnectionId} 
            onDeleted={handleConnectorDeleted} 
          />
        </div>
      </div>

      {/* Create Connection Modal */}
      <CreateConnectionModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        defaultConnectorType={createConnectorType}
      />
    </div>
  );
}

export default DataConnectionsPage;

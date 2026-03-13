/**
 * Workspace Selector - Dropdown to select from available RAG workspaces.
 * Uses the DS Select component for consistent styling.
 * Used in Evals, GEPA Optimizer, and Prompt Management pages.
 */

import React from 'react';
import { CircleStackIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { RAGWorkspace } from '../../hooks/useRAGDomains';
import { Select, SelectOption } from '../ui/select';
import { Button } from '../ui/button';

interface WorkspaceSelectorProps {
  workspaces: RAGWorkspace[];
  selectedWorkspaceId: number | null;
  onSelect: (workspaceId: number | null) => void;
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  showAllOption?: boolean;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

const STATUS_DOT_COLORS: Record<string, string> = {
  ready: 'bg-emerald-500',
  indexing: 'bg-yellow-500',
  pending: 'bg-gray-500',
  failed: 'bg-red-500',
};

const STATUS_COLORS: Record<string, string> = {
  ready: 'text-emerald-500',
  indexing: 'text-yellow-500',
  pending: 'text-gray-500',
  failed: 'text-red-500',
};

export function WorkspaceSelector({
  workspaces,
  selectedWorkspaceId,
  onSelect,
  isLoading = false,
  error = null,
  onRefresh,
  showAllOption = false,
  placeholder = 'Select a workspace',
  className = '',
  disabled = false,
}: WorkspaceSelectorProps) {
  const selectedWorkspace = workspaces.find(w => w.id === selectedWorkspaceId);

  if (error) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className="flex items-center gap-2 px-3 py-2 border border-red-500/30 rounded-xl bg-red-500/5 text-red-400 text-sm">
          <CircleStackIcon className="h-4 w-4" />
          <span>{error}</span>
        </div>
        {onRefresh && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRefresh}
            title="Retry"
          >
            <ArrowPathIcon className="h-4 w-4" />
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Select
        value={selectedWorkspaceId?.toString() ?? ''}
        onValueChange={(value) => {
          onSelect(value === '' ? null : parseInt(value));
        }}
        placeholder={placeholder}
        disabled={disabled || isLoading}
        icon={<CircleStackIcon />}
        className="w-[280px]"
      >
        {showAllOption && (
          <SelectOption value="">All Workspaces</SelectOption>
        )}
        {workspaces.map((workspace) => (
          <SelectOption key={workspace.id} value={workspace.id.toString()}>
            {workspace.display_name} ({workspace.document_count} docs)
          </SelectOption>
        ))}
      </Select>

      {/* Status indicator */}
      {selectedWorkspace && (
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${STATUS_DOT_COLORS[selectedWorkspace.status]}`} />
          <span className={`text-xs ${STATUS_COLORS[selectedWorkspace.status]}`}>
            {selectedWorkspace.status}
          </span>
        </div>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <ArrowPathIcon className="h-4 w-4 text-gray-400 dark:text-gray-500 animate-spin" />
      )}

      {/* Refresh button */}
      {onRefresh && !isLoading && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onRefresh}
          title="Refresh workspaces"
          className="h-7 w-7"
        >
          <ArrowPathIcon className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

// Backwards compatibility alias
export const RAGDomainSelector = WorkspaceSelector;
export default WorkspaceSelector;

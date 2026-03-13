/**
 * WorkspacesPage - RAG Workspaces Management
 * 
 * Mirrors RAGFlow's dataset management UI.
 * Lists workspaces, allows creation, and links to workspace detail view.
 * 
 * Migrated to Eliza Design System (Feb 2026)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PlusIcon,
  FolderIcon,
  DocumentTextIcon,
  MagnifyingGlassIcon,
  EllipsisHorizontalIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { Layout } from '../../components/layout/Layout';
import {
  Page,
  PageHeader,
  PageBody,
  Card,
  CardContent,
  Button,
  Input,
  Spinner,
  DropdownMenu,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
} from '../../components/ui';
import { cn } from '../../shared/lib/cn';
import { useToasts } from '../../stores/useToasts';
import CreateWorkspaceWizard from './CreateWorkspaceWizard';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

interface RAGFlowWorkspace {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  icon: string;
  color: string;
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  document_count: number;
  chunk_count: number;
  total_tokens: number;
  created_at: string;
}

// Color mapping for workspace icons - supports both hex values and named colors
const COLOR_MAP: Record<string, string> = {
  violet: '#8b5cf6',
  emerald: '#10b981',
  blue: '#3b82f6',
  orange: '#f97316',
  pink: '#ec4899',
  cyan: '#06b6d4',
  red: '#ef4444',
  yellow: '#eab308',
  lime: '#84cc16',
  indigo: '#6366f1',
};

// Helper to get the background color (handles both hex and named colors)
function getWorkspaceColor(color: string): string {
  // If it's already a hex color, use it directly
  if (color.startsWith('#')) {
    return color;
  }
  // Otherwise, look up the named color
  return COLOR_MAP[color] || '#6b7280'; // gray-500 fallback
}

function WorkspaceCard({ 
  workspace, 
  onClick, 
  onDelete 
}: { 
  workspace: RAGFlowWorkspace; 
  onClick: () => void;
  onDelete: () => void;
}) {
  const bgColor = getWorkspaceColor(workspace.color);

  return (
    <Card 
      className="cursor-pointer hover:shadow-md transition-shadow group"
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div 
            className="w-10 h-10 rounded-lg flex items-center justify-center text-white"
            style={{ backgroundColor: bgColor }}
          >
            <FolderIcon className="w-5 h-5" />
          </div>
          <DropdownMenu>
            <DropdownTrigger asChild>
              <button
                onClick={(e) => e.stopPropagation()}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-dark-surface-2 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <EllipsisHorizontalIcon className="w-5 h-5 text-gray-400" />
              </button>
            </DropdownTrigger>
            <DropdownContent align="end">
              <DropdownItem
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
                className="text-red-600 focus:text-red-600 focus:bg-red-50 dark:focus:bg-red-900/20"
              >
                <TrashIcon className="w-4 h-4 mr-2" />
                Delete
              </DropdownItem>
            </DropdownContent>
          </DropdownMenu>
        </div>
        <h3 className="font-semibold text-charcoal dark:text-white mb-1 truncate">
          {workspace.display_name || workspace.name}
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 line-clamp-2 h-10">
          {workspace.description || 'No description'}
        </p>
        <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1">
            <DocumentTextIcon className="w-3.5 h-3.5" />
            {workspace.document_count} files
          </span>
          <span>{workspace.chunk_count} chunks</span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function WorkspacesPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();

  const [workspaces, setWorkspaces] = useState<RAGFlowWorkspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setWorkspaces(data.domains || []);
      }
    } catch (e) {
      console.error('Failed to fetch workspaces:', e);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  const handleDeleteWorkspace = async (workspaceId: number) => {
    if (!window.confirm('Delete this workspace and all its documents?')) return;

    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains/${workspaceId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        addToast({ kind: 'success', message: 'Workspace deleted' });
        fetchWorkspaces();
      } else {
        addToast({ kind: 'error', message: 'Failed to delete workspace' });
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to delete workspace' });
    }
  };

  const handleWorkspaceCreated = () => {
    setShowCreateModal(false);
    fetchWorkspaces();
  };

  const filteredWorkspaces = workspaces.filter(w => 
    w.display_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    w.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Layout>
      <Page maxWidth="2xl">
        <PageHeader
          title="Workspaces"
          description="Create and manage document collections for RAG chat"
          actions={
            <Button onClick={() => setShowCreateModal(true)}>
              <PlusIcon className="w-4 h-4 mr-2" />
              Create Workspace
            </Button>
          }
        />
        <PageBody>
          {/* Search */}
          <div className="mb-6">
            <div className="relative max-w-md">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search workspaces..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {/* Content */}
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <Spinner size="lg" />
              <p className="text-sm text-gray-500 dark:text-gray-400">Loading workspaces...</p>
            </div>
          ) : filteredWorkspaces.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <FolderIcon className="w-12 h-12 text-gray-300 dark:text-gray-600 mb-4" />
              <h3 className="text-lg font-semibold text-charcoal dark:text-white mb-2">
                {searchQuery ? 'No workspaces found' : 'No workspaces yet'}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                {searchQuery ? 'Try a different search term' : 'Create your first workspace to get started'}
              </p>
              {!searchQuery && (
                <Button onClick={() => setShowCreateModal(true)}>
                  Create Workspace
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredWorkspaces.map((workspace) => (
                <WorkspaceCard
                  key={workspace.id}
                  workspace={workspace}
                  onClick={() => navigate(`/workspaces/${workspace.id}`)}
                  onDelete={() => handleDeleteWorkspace(workspace.id)}
                />
              ))}
            </div>
          )}
        </PageBody>
      </Page>

      {/* Create Workspace Wizard */}
      {showCreateModal && (
        <CreateWorkspaceWizard
          onClose={() => setShowCreateModal(false)}
          onCreated={handleWorkspaceCreated}
        />
      )}
    </Layout>
  );
}

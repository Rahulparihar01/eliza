/**
 * Hook to fetch and manage RAG workspaces.
 * Used across Evals, GEPA Optimizer, and Prompt Management pages.
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

export interface RAGWorkspace {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  parser_type: string;
  document_count: number;
  chunk_count: number;
  is_active: boolean;
  created_at: string;
}

// Backwards compatibility alias
export type RAGDomain = RAGWorkspace;

interface UseRAGWorkspacesOptions {
  /** Auto-select first workspace on load */
  autoSelect?: boolean;
  /** Filter to only ready workspaces */
  readyOnly?: boolean;
}

interface UseRAGWorkspacesReturn {
  workspaces: RAGWorkspace[];
  selectedWorkspace: RAGWorkspace | null;
  selectedWorkspaceId: number | null;
  setSelectedWorkspaceId: (id: number | null) => void;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const STORAGE_KEY = 'ai_console_selected_workspace_id';

/** Read the persisted workspace ID from localStorage (scoped to AI Console). */
function getPersistedWorkspaceId(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw !== null) {
      const parsed = Number(raw);
      return Number.isFinite(parsed) ? parsed : null;
    }
  } catch {
    // localStorage may be unavailable
  }
  return null;
}

/** Persist the selected workspace ID to localStorage. */
function persistWorkspaceId(id: number | null) {
  try {
    if (id !== null) {
      localStorage.setItem(STORAGE_KEY, String(id));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // localStorage may be unavailable
  }
}

export function useRAGWorkspaces(options: UseRAGWorkspacesOptions = {}): UseRAGWorkspacesReturn {
  const { autoSelect = true, readyOnly = false } = options;
  const token = localStorage.getItem('auth_token');

  const [workspaces, setWorkspaces] = useState<RAGWorkspace[]>([]);
  const [selectedWorkspaceId, _setSelectedWorkspaceId] = useState<number | null>(getPersistedWorkspaceId);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Wrap setter to also persist to localStorage
  const setSelectedWorkspaceId = useCallback((id: number | null) => {
    _setSelectedWorkspaceId(id);
    persistWorkspaceId(id);
  }, []);

  const fetchWorkspaces = useCallback(async () => {
    if (!token) {
      setError('Not authenticated');
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const res = await fetch(`${API_BASE}/v1/ragflow/domains`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to fetch workspaces (${res.status})`);
      }

      const data = await res.json();
      let workspaceList: RAGWorkspace[] = data.domains || data || [];

      // Filter if needed
      if (readyOnly) {
        workspaceList = workspaceList.filter(w => w.status === 'ready');
      }

      setWorkspaces(workspaceList);

      // Validate persisted selection still exists in the workspace list
      const persistedId = getPersistedWorkspaceId();
      const persistedStillValid = persistedId !== null && workspaceList.some(w => w.id === persistedId);

      if (persistedStillValid) {
        // Restore persisted selection (may differ from current state if another tab changed it)
        _setSelectedWorkspaceId(persistedId);
      } else if (autoSelect && workspaceList.length > 0) {
        // Auto-select first workspace if no valid persisted selection
        const firstId = workspaceList[0].id;
        _setSelectedWorkspaceId(firstId);
        persistWorkspaceId(firstId);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to fetch workspaces';
      setError(message);
      console.error('useRAGWorkspaces error:', e);
    } finally {
      setIsLoading(false);
    }
  }, [token, autoSelect, readyOnly]);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  const selectedWorkspace = workspaces.find(w => w.id === selectedWorkspaceId) || null;

  return {
    workspaces,
    selectedWorkspace,
    selectedWorkspaceId,
    setSelectedWorkspaceId,
    isLoading,
    error,
    refresh: fetchWorkspaces,
  };
}

// Backwards compatibility alias
export const useRAGDomains = useRAGWorkspaces;
export default useRAGWorkspaces;

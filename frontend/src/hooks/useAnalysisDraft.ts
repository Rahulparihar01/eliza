/**
 * useAnalysisDraft
 * 
 * Manages draft state persistence for the analysis modal.
 * Automatically saves to localStorage on changes and restores on mount.
 * 
 * Usage:
 * ```tsx
 * const { draft, updateDraft, clearDraft, isDirty, lastSaved } = useAnalysisDraft(configId);
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { debounce } from '../shared/lib/debounce';

// Draft state interface - mirrors the modal form state
export interface AnalysisDraft {
  // Basic info
  name: string;
  description: string;
  
  // Limits
  marketSearchLimit: number;
  maxCandidateFetch: number;
  
  // ATS
  selectedConnector: number | null;
  selectedConnectorName: string;
  
  // Blueprint
  blueprintId: number | null;
  blueprintName: string;
  linkedInUrl: string;
  
  // Company DNA
  dnaId: number | null;
  dnaName: string;
  newDnaCompany: string;
  newDnaRole: string;
  newDnaTimeWindow: number;
  newDnaEmployeeLimit: number;
  
  // Job Description
  jobDescriptionMode: 'select' | 'upload' | 'paste';
  jobDescriptionText: string;
  selectedJob: { id: string; title: string } | null;
  
  // Candidate Source
  candidateSourceMode: 'ats' | 'upload';
  searchMarket: boolean;
  searchAts: boolean;
  
  // Ideal Candidate
  idealMustHaves: string;
  idealNiceToHaves: string;
  idealDealbreakers: string;
  idealPersonalityTraits: string;
  idealHiringManagerNotes: string;
  
  // Metadata
  lastModified: number;
}

// Default empty draft
const DEFAULT_DRAFT: AnalysisDraft = {
  name: '',
  description: '',
  marketSearchLimit: 50,
  maxCandidateFetch: 100,
  selectedConnector: null,
  selectedConnectorName: '',
  blueprintId: null,
  blueprintName: '',
  linkedInUrl: '',
  dnaId: null,
  dnaName: '',
  newDnaCompany: '',
  newDnaRole: '',
  newDnaTimeWindow: 24,
  newDnaEmployeeLimit: 50,
  jobDescriptionMode: 'paste',
  jobDescriptionText: '',
  selectedJob: null,
  candidateSourceMode: 'ats',
  searchMarket: true,
  searchAts: false,
  idealMustHaves: '',
  idealNiceToHaves: '',
  idealDealbreakers: '',
  idealPersonalityTraits: '',
  idealHiringManagerNotes: '',
  lastModified: Date.now(),
};

// Get storage key for a config
function getStorageKey(configId?: number): string {
  return configId ? `analysis-draft-${configId}` : 'analysis-draft-new';
}

// Load draft from localStorage
function loadDraft(configId?: number): AnalysisDraft | null {
  try {
    const key = getStorageKey(configId);
    const stored = localStorage.getItem(key);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Validate it has the expected structure
      if (parsed && typeof parsed.name === 'string') {
        return parsed as AnalysisDraft;
      }
    }
  } catch (e) {
    console.warn('Failed to load draft from localStorage:', e);
  }
  return null;
}

// Save draft to localStorage
function saveDraft(draft: AnalysisDraft, configId?: number): void {
  try {
    const key = getStorageKey(configId);
    localStorage.setItem(key, JSON.stringify(draft));
  } catch (e) {
    console.warn('Failed to save draft to localStorage:', e);
  }
}

// Clear draft from localStorage
function removeDraft(configId?: number): void {
  try {
    const key = getStorageKey(configId);
    localStorage.removeItem(key);
  } catch (e) {
    console.warn('Failed to remove draft from localStorage:', e);
  }
}

interface UseAnalysisDraftOptions {
  /** Config ID (undefined for new analysis) */
  configId?: number;
  /** Debounce delay for auto-save (ms) */
  debounceMs?: number;
  /** Whether to auto-load draft on mount */
  autoLoad?: boolean;
}

interface UseAnalysisDraftReturn {
  /** Current draft state */
  draft: AnalysisDraft;
  /** Update draft fields (partial update) */
  updateDraft: (updates: Partial<AnalysisDraft>) => void;
  /** Clear draft from storage and reset to defaults */
  clearDraft: () => void;
  /** Whether draft has unsaved changes since last save */
  isDirty: boolean;
  /** Timestamp of last save (null if never saved) */
  lastSaved: number | null;
  /** Whether draft was loaded from storage on mount */
  wasRestored: boolean;
  /** Force save immediately (bypasses debounce) */
  forceSave: () => void;
}

export function useAnalysisDraft(
  options: UseAnalysisDraftOptions = {}
): UseAnalysisDraftReturn {
  const { configId, debounceMs = 500, autoLoad = true } = options;
  
  // Track if we restored from storage
  const [wasRestored, setWasRestored] = useState(false);
  
  // Initialize draft state
  const [draft, setDraft] = useState<AnalysisDraft>(() => {
    if (autoLoad) {
      const stored = loadDraft(configId);
      if (stored) {
        setWasRestored(true);
        return stored;
      }
    }
    return { ...DEFAULT_DRAFT, lastModified: Date.now() };
  });
  
  // Track dirty state
  const [isDirty, setIsDirty] = useState(false);
  const [lastSaved, setLastSaved] = useState<number | null>(null);
  
  // Ref for debounced save
  const draftRef = useRef(draft);
  draftRef.current = draft;
  
  // Debounced save function
  const debouncedSave = useCallback(
    debounce(() => {
      saveDraft(draftRef.current, configId);
      setLastSaved(Date.now());
      setIsDirty(false);
    }, debounceMs),
    [configId, debounceMs]
  );
  
  // Update draft
  const updateDraft = useCallback((updates: Partial<AnalysisDraft>) => {
    setDraft(prev => {
      const updated = {
        ...prev,
        ...updates,
        lastModified: Date.now(),
      };
      return updated;
    });
    setIsDirty(true);
    debouncedSave();
  }, [debouncedSave]);
  
  // Clear draft
  const clearDraft = useCallback(() => {
    removeDraft(configId);
    setDraft({ ...DEFAULT_DRAFT, lastModified: Date.now() });
    setIsDirty(false);
    setLastSaved(null);
    setWasRestored(false);
  }, [configId]);
  
  // Force save
  const forceSave = useCallback(() => {
    saveDraft(draftRef.current, configId);
    setLastSaved(Date.now());
    setIsDirty(false);
  }, [configId]);
  
  // Load draft on configId change
  useEffect(() => {
    if (autoLoad) {
      const stored = loadDraft(configId);
      if (stored) {
        setDraft(stored);
        setWasRestored(true);
        setLastSaved(stored.lastModified);
      } else {
        setDraft({ ...DEFAULT_DRAFT, lastModified: Date.now() });
        setWasRestored(false);
        setLastSaved(null);
      }
      setIsDirty(false);
    }
  }, [configId, autoLoad]);
  
  return {
    draft,
    updateDraft,
    clearDraft,
    isDirty,
    lastSaved,
    wasRestored,
    forceSave,
  };
}

export default useAnalysisDraft;

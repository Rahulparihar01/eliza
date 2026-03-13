/**
 * Selection Store - Zustand
 * Manages cross-pane selection state
 */

import { create } from 'zustand';

interface SelectionState {
  // State
  ids: string[];
  
  // Actions
  set: (ids: string[]) => void;
  add: (id: string) => void;
  remove: (id: string) => void;
  toggle: (id: string) => void;
  clear: () => void;
  
  // Helpers
  isSelected: (id: string) => boolean;
  hasSelection: () => boolean;
  count: () => number;
}

export const useSelection = create<SelectionState>((set, get) => ({
  // Initial state
  ids: [],
  
  // Actions
  set: (ids) => set({ ids }),
  
  add: (id) => set((state) => ({
    ids: state.ids.includes(id) ? state.ids : [...state.ids, id]
  })),
  
  remove: (id) => set((state) => ({
    ids: state.ids.filter(existingId => existingId !== id)
  })),
  
  toggle: (id) => set((state) => ({
    ids: state.ids.includes(id)
      ? state.ids.filter(existingId => existingId !== id)
      : [...state.ids, id]
  })),
  
  clear: () => set({ ids: [] }),
  
  // Helpers
  isSelected: (id) => get().ids.includes(id),
  hasSelection: () => get().ids.length > 0,
  count: () => get().ids.length
}));

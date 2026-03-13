/**
 * UI Store - Zustand
 * Manages global UI state (layout, theme, panels)
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  // Layout state
  leftCollapsed: boolean;
  rightOpen: boolean;
  rightWidth: number; // px
  theme: 'light' | 'dark' | 'system';
  
  // Actions
  set: (partial: Partial<UIState>) => void;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  setRightWidth: (width: number) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useUI = create<UIState>()(
  persist(
    (set, get) => ({
      // Initial state
      leftCollapsed: false,
      rightOpen: false,
      rightWidth: 400,
      theme: 'system',
      
      // Actions
      set: (partial) => set((state) => ({ ...state, ...partial })),
      
      toggleLeftPanel: () => set((state) => ({ 
        leftCollapsed: !state.leftCollapsed 
      })),
      
      toggleRightPanel: () => set((state) => ({ 
        rightOpen: !state.rightOpen 
      })),
      
      setRightWidth: (width) => set({ rightWidth: width }),
      
      setTheme: (theme) => set({ theme })
    }),
    {
      name: 'ui-storage-v1',
      partialize: (state) => ({
        leftCollapsed: state.leftCollapsed,
        rightWidth: state.rightWidth,
        theme: state.theme
      })
    }
  )
);

/**
 * Theme Store - Zustand
 * 
 * Manages tenant-specific brand theme (colors).
 * Theme is loaded on app init and applied as CSS custom properties.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ============================================================================
// Types
// ============================================================================

export interface ThemeColors {
  primary: string;
  primaryLight: string;
  accent: string;
  text: string;
}

interface ThemeState {
  // Theme data
  colors: ThemeColors;
  preset: string | null;
  
  // Loading state
  isLoading: boolean;
  error: string | null;
  isInitialized: boolean;
  
  // Actions
  setColors: (colors: ThemeColors, preset?: string | null) => void;
  loadTheme: () => Promise<void>;
  saveTheme: (colors: ThemeColors, preset?: string | null) => Promise<void>;
  resetToDefault: () => void;
  resetTheme: () => void;
  applyTheme: (colors: ThemeColors) => void;
}

// ============================================================================
// Constants
// ============================================================================

export const DEFAULT_THEME: ThemeColors = {
  primary: '#c9506b',
  primaryLight: '#e8a598',
  accent: '#f5c4a1',
  text: '#5c4a5a',
};

export const THEME_PRESETS: Record<string, ThemeColors> = {
  'eliza-forge': { primary: '#c9506b', primaryLight: '#e8a598', accent: '#f5c4a1', text: '#5c4a5a' },
  'ocean-blue': { primary: '#0369a1', primaryLight: '#38bdf8', accent: '#06b6d4', text: '#334155' },
  'forest-green': { primary: '#15803d', primaryLight: '#4ade80', accent: '#84cc16', text: '#374151' },
  'royal-purple': { primary: '#7c3aed', primaryLight: '#a78bfa', accent: '#c084fc', text: '#374151' },
};

// ============================================================================
// Utilities
// ============================================================================

/**
 * Convert hex color to RGB values for CSS custom properties.
 * CSS custom properties use RGB values for alpha compositing.
 */
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return '201 80 107'; // fallback (eliza-red)
  return `${parseInt(result[1], 16)} ${parseInt(result[2], 16)} ${parseInt(result[3], 16)}`;
}

/**
 * Apply theme colors to CSS custom properties.
 */
function applyThemeToCss(colors: ThemeColors): void {
  const root = document.documentElement;
  root.style.setProperty('--color-primary', hexToRgb(colors.primary));
  root.style.setProperty('--color-primary-light', hexToRgb(colors.primaryLight));
  root.style.setProperty('--color-accent', hexToRgb(colors.accent));
  root.style.setProperty('--color-text', hexToRgb(colors.text));
}

// ============================================================================
// Store
// ============================================================================

export const useTheme = create<ThemeState>()(
  persist(
    (set, get) => ({
      // Initial state
      colors: DEFAULT_THEME,
      preset: 'eliza-forge',
      isLoading: false,
      error: null,
      isInitialized: false,

      // Set colors locally and apply to CSS
      setColors: (colors, preset = null) => {
        set({ colors, preset });
        get().applyTheme(colors);
      },

      // Load theme from API
      loadTheme: async () => {
        // Skip if already initialized (use cached value)
        if (get().isInitialized) {
          get().applyTheme(get().colors);
          return;
        }

        const token = localStorage.getItem('auth_token');
        if (!token) {
          // Not authenticated - apply default theme
          get().applyTheme(DEFAULT_THEME);
          return;
        }

        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch('/api/v1/tenant-settings/theme', {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
          
          if (response.ok) {
            const data = await response.json();
            const colors: ThemeColors = {
              primary: data.primary,
              primaryLight: data.primaryLight,
              accent: data.accent,
              text: data.text,
            };
            set({ 
              colors, 
              preset: data.preset, 
              isLoading: false,
              isInitialized: true 
            });
            get().applyTheme(colors);
          } else {
            // API error - use cached or default
            set({ isLoading: false, isInitialized: true });
            get().applyTheme(get().colors);
          }
        } catch (error) {
          console.warn('Failed to load theme, using default:', error);
          set({ 
            error: 'Failed to load theme', 
            isLoading: false,
            isInitialized: true 
          });
          get().applyTheme(get().colors);
        }
      },

      // Save theme to API
      saveTheme: async (colors, preset = null) => {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          throw new Error('Not authenticated');
        }

        set({ isLoading: true, error: null });
        
        try {
          const response = await fetch('/api/v1/tenant-settings/theme', {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({
              primary: colors.primary,
              primaryLight: colors.primaryLight,
              accent: colors.accent,
              text: colors.text,
              preset,
            }),
          });
          
          if (response.ok) {
            set({ colors, preset, isLoading: false });
            get().applyTheme(colors);
          } else {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to save theme');
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Failed to save theme';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // Reset to default Eliza Forge theme
      resetToDefault: () => {
        set({ colors: DEFAULT_THEME, preset: 'eliza-forge' });
        get().applyTheme(DEFAULT_THEME);
      },

      // Clear theme state (used on logout/login to avoid cross-tenant leakage)
      resetTheme: () => {
        set({
          colors: DEFAULT_THEME,
          preset: 'eliza-forge',
          isLoading: false,
          error: null,
          isInitialized: false,
        });
        get().applyTheme(DEFAULT_THEME);
      },

      // Apply theme colors to CSS custom properties
      applyTheme: (colors) => {
        applyThemeToCss(colors);
      },
    }),
    {
      name: 'eliza-theme',
      // Only persist colors and preset, NOT isInitialized
      // This ensures theme is fetched from API on each page load after auth
      partialize: (state) => ({ 
        colors: state.colors, 
        preset: state.preset,
      }),
    }
  )
);

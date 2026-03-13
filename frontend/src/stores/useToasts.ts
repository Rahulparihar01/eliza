/**
 * Toast Store - Zustand
 * Manages ephemeral notifications
 * 
 * Compatible with DS Toast components.
 * Uses 'kind' internally for backwards compatibility.
 * The ToastWrapper in App.tsx maps 'kind' to 'variant' for DS ToastContainer.
 */

import { create } from 'zustand';

export interface Toast {
  id: string;
  kind: 'success' | 'error' | 'info' | 'warning';
  message: string;
  title?: string;
  duration?: number; // ms, defaults to 6000
}

interface ToastState {
  // State
  toasts: Toast[];
  
  // Actions
  push: (toast: Omit<Toast, 'id'>) => void;
  dismiss: (id: string) => void;
  clear: () => void;
}

export const useToasts = create<ToastState>((set) => ({
  // Initial state
  toasts: [],
  
  // Actions
  push: (toast) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast: Toast = {
      ...toast,
      id,
      duration: toast.duration ?? 6000
    };
    
    set((state) => ({
      toasts: [...state.toasts, newToast]
    }));
    
    // Note: Auto-dismiss is handled by the DS ToastContainer component
  },
  
  dismiss: (id) => set((state) => ({
    toasts: state.toasts.filter(toast => toast.id !== id)
  })),
  
  clear: () => set({ toasts: [] }),
}));

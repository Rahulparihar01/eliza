/**
 * Notifications Store - Zustand
 * Manages system notifications and alerts
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  timestamp: string;
  actionUrl?: string;
  actionLabel?: string;
}

interface NotificationState {
  // State
  notifications: Notification[];
  unreadCount: number;
  isOpen: boolean;
  
  // Actions
  addNotification: (notification: Omit<Notification, 'id' | 'read' | 'timestamp'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
  togglePanel: () => void;
  setOpen: (open: boolean) => void;
}

export const useNotifications = create<NotificationState>()(
  persist(
    (set, get) => ({
      // Initial state
      notifications: [],
      unreadCount: 0,
      isOpen: false,
      
      // Actions
      addNotification: (notification) => {
        const id = Math.random().toString(36).substring(2, 9);
        const newNotification: Notification = {
          ...notification,
          id,
          read: false,
          timestamp: new Date().toISOString()
        };
        
        set((state) => ({
          notifications: [newNotification, ...state.notifications],
          unreadCount: state.unreadCount + 1
        }));
      },
      
      markAsRead: (id) => set((state) => ({
        notifications: state.notifications.map(n => 
          n.id === id ? { ...n, read: true } : n
        ),
        unreadCount: Math.max(0, state.unreadCount - (
          state.notifications.find(n => n.id === id && !n.read) ? 1 : 0
        ))
      })),
      
      markAllAsRead: () => set((state) => ({
        notifications: state.notifications.map(n => ({ ...n, read: true })),
        unreadCount: 0
      })),
      
      removeNotification: (id) => set((state) => {
        const notification = state.notifications.find(n => n.id === id);
        return {
          notifications: state.notifications.filter(n => n.id !== id),
          unreadCount: notification && !notification.read 
            ? Math.max(0, state.unreadCount - 1) 
            : state.unreadCount
        };
      }),
      
      clearAll: () => set({
        notifications: [],
        unreadCount: 0
      }),
      
      togglePanel: () => set((state) => ({
        isOpen: !state.isOpen
      })),
      
      setOpen: (open) => set({ isOpen: open })
    }),
    {
      name: 'notifications-storage-v1',
      partialize: (state) => ({
        notifications: state.notifications,
        unreadCount: state.unreadCount
      })
    }
  )
);

// Helper function to add common notification types
export const notificationHelpers = {
  success: (title: string, message: string, actionUrl?: string, actionLabel?: string) => {
    useNotifications.getState().addNotification({
      title,
      message,
      type: 'success',
      actionUrl,
      actionLabel
    });
  },
  
  error: (title: string, message: string, actionUrl?: string, actionLabel?: string) => {
    useNotifications.getState().addNotification({
      title,
      message,
      type: 'error',
      actionUrl,
      actionLabel
    });
  },
  
  warning: (title: string, message: string, actionUrl?: string, actionLabel?: string) => {
    useNotifications.getState().addNotification({
      title,
      message,
      type: 'warning',
      actionUrl,
      actionLabel
    });
  },
  
  info: (title: string, message: string, actionUrl?: string, actionLabel?: string) => {
    useNotifications.getState().addNotification({
      title,
      message,
      type: 'info',
      actionUrl,
      actionLabel
    });
  }
};

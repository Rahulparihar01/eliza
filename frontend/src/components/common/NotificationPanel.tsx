/**
 * Notification Panel Component
 * Displays system notifications in a dropdown panel
 * 
 * Uses DS Popover for positioning and styling.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  InformationCircleIcon,
  EyeIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useNotifications, Notification } from '../../stores/useNotifications';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  Badge,
  Button,
} from '../ui';
import { XMarkIcon as XMarkIconClose } from '@heroicons/react/24/outline';

/* ============================================
   NOTIFICATION ITEM
   ============================================ */

interface NotificationItemProps {
  notification: Notification;
  onMarkAsRead: (id: string) => void;
  onRemove: (id: string) => void;
}

function NotificationItem({ notification, onMarkAsRead, onRemove }: NotificationItemProps) {
  const getIcon = () => {
    switch (notification.type) {
      case 'success':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case 'warning':
        return <ExclamationTriangleIcon className="w-5 h-5 text-amber-500" />;
      case 'error':
        return <XCircleIcon className="w-5 h-5 text-red-500" />;
      case 'info':
      default:
        return <InformationCircleIcon className="w-5 h-5 text-blue-500" />;
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={`
      p-4 border-b border-gray-200 dark:border-dark-border/30 
      hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors
      ${!notification.read ? 'bg-eliza-red/5 dark:bg-eliza-red/10' : ''}
    `}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {getIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className={`text-sm font-medium ${!notification.read ? 'text-charcoal dark:text-white' : 'text-gray-500 dark:text-gray-400'}`}>
                {notification.title}
              </p>
              <p className={`text-sm mt-1 ${!notification.read ? 'text-charcoal dark:text-gray-200' : 'text-gray-400 dark:text-gray-500'}`}>
                {notification.message}
              </p>
              
              {notification.actionUrl && notification.actionLabel && (
                <Link
                  to={notification.actionUrl}
                  className="inline-flex items-center mt-2 text-xs font-medium text-eliza-red hover:text-eliza-red-light"
                  onClick={() => onMarkAsRead(notification.id)}
                >
                  {notification.actionLabel}
                </Link>
              )}
            </div>
            
            <div className="flex items-center gap-1 ml-2">
              {!notification.read && (
                <button
                  onClick={() => onMarkAsRead(notification.id)}
                  className="p-1 text-gray-400 hover:text-charcoal dark:hover:text-white rounded transition-colors"
                  title="Mark as read"
                >
                  <EyeIcon className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={() => onRemove(notification.id)}
                className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
                title="Remove notification"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
          
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
            {formatTime(notification.timestamp)}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ============================================
   NOTIFICATION PANEL (Content Only)
   ============================================ */

interface NotificationPanelContentProps {
  onClose?: () => void;
}

export function NotificationPanelContent({ onClose }: NotificationPanelContentProps) {
  const notifications = useNotifications(s => s.notifications);
  const markAsRead = useNotifications(s => s.markAsRead);
  const markAllAsRead = useNotifications(s => s.markAllAsRead);
  const removeNotification = useNotifications(s => s.removeNotification);
  const clearAll = useNotifications(s => s.clearAll);
  const unreadCount = useNotifications(s => s.unreadCount);

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-border/30">
        <div className="flex items-center gap-2 font-medium text-charcoal dark:text-white">
          <span>Notifications</span>
          {unreadCount > 0 && (
            <Badge variant="brand">{unreadCount}</Badge>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-dark-surface-2"
            aria-label="Close"
          >
            <XMarkIconClose className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Actions Bar - Only show when there are notifications */}
      {notifications.length > 0 && (
        <div className="flex items-center justify-end gap-3 px-4 py-2 border-b border-gray-200 dark:border-dark-border/30 bg-gray-50 dark:bg-dark-surface-2">
          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              className="text-xs text-eliza-red hover:text-eliza-red-light font-medium"
            >
              Mark all read
            </button>
          )}
          <button
            onClick={clearAll}
            className="text-xs text-gray-500 hover:text-red-500 dark:text-gray-400 dark:hover:text-red-400 font-medium"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Content */}
      <div className="max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="p-8 text-center">
            <InformationCircleIcon className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-400 dark:text-gray-500">No notifications</p>
          </div>
        ) : (
          notifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onMarkAsRead={markAsRead}
              onRemove={removeNotification}
            />
          ))
        )}
      </div>
    </>
  );
}

/* ============================================
   FULL NOTIFICATION POPOVER (With Trigger)
   
   Use this when you want the complete popover.
   The trigger should be passed as children.
   ============================================ */

interface NotificationPopoverProps {
  children: React.ReactElement;
}

export function NotificationPopover({ children }: NotificationPopoverProps) {
  const unreadCount = useNotifications(s => s.unreadCount);

  return (
    <Popover>
      <PopoverTrigger asChild>
        {children}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96">
        <NotificationPanelContent />
      </PopoverContent>
    </Popover>
  );
}

/* ============================================
   LEGACY INTERFACE (For backwards compatibility)
   
   This maintains the old API where isOpen/onClose
   are controlled externally.
   ============================================ */

interface NotificationPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function NotificationPanel({ isOpen, onClose }: NotificationPanelProps) {
  const [isVisible, setIsVisible] = React.useState(false);
  const [shouldRender, setShouldRender] = React.useState(false);

  React.useEffect(() => {
    if (isOpen) {
      setShouldRender(true);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsVisible(true);
        });
      });
    } else {
      setIsVisible(false);
      const timer = setTimeout(() => {
        setShouldRender(false);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  if (!shouldRender) return null;

  return (
    <div 
      className={`
        absolute right-0 mt-2 w-96 z-50 rounded-xl border shadow-lg overflow-hidden 
        bg-white dark:bg-dark-surface border-gray-200 dark:border-dark-border/50
        transition ease-out duration-100 transform origin-top-right
        ${isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}
      `}
    >
      <NotificationPanelContent onClose={onClose} />
    </div>
  );
}

/**
 * Header Component - Eliza Forge
 * 
 * Main header bar using DS Toolbar components.
 * Features tenant switcher, theme toggle, notifications, and user menu.
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  BellIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  ChatBubbleLeftRightIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline';
import { SunIcon, MoonIcon } from '@heroicons/react/24/outline';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '../ui/popover';
import { useAuth } from '../../contexts/AuthContext';
import { useAuth as useAuthStore } from '../../stores/useAuth';
import { useNotifications, notificationHelpers } from '../../stores/useNotifications';
import NotificationPanel from '../common/NotificationPanel';
import FeedbackPanel from '../common/FeedbackPanel';
import { useUI } from '../../stores/useUI';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Toolbar,
  ToolbarSection,
  ToolbarDivider,
  ToolbarItem,
  ToolbarTextButton,
} from '../ui/toolbar';
import { TenantSwitcher, type Tenant } from '../ui/tenant-switcher';
import { Avatar } from '../ui/avatar';

interface HeaderProps {
  onMenuToggle?: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
  const { user, logout } = useAuth();
  const setUser = useAuthStore(s => s.setUser);
  const unreadCount = useNotifications(s => s.unreadCount);
  const isNotificationOpen = useNotifications(s => s.isOpen);
  const toggleNotifications = useNotifications(s => s.togglePanel);
  const setNotificationOpen = useNotifications(s => s.setOpen);
  const notificationRef = useRef<HTMLDivElement>(null);
  const theme = useUI(s => s.theme);
  const setTheme = useUI(s => s.setTheme);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [switching, setSwitching] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  // Convert tenant memberships to DS Tenant format
  const tenants: Tenant[] = useMemo(() => {
    if (!user?.tenant_memberships?.length) {
      // Single tenant mode - just show current tenant
      return [{
        id: user?.customer_id || 'default',
        name: user?.customer_name || 'Organization',
        slug: user?.customer_id || 'default',
        isDefault: true,
      }];
    }
    return user.tenant_memberships.map(m => ({
      id: m.customer_id,
      name: m.customer_name,
      slug: m.customer_id,
      isDefault: m.is_default,
    }));
  }, [user?.tenant_memberships, user?.customer_id, user?.customer_name]);

  const currentTenant: Tenant = useMemo(() => {
    if (user?.tenant_memberships?.length) {
      const found = user.tenant_memberships.find(m => m.customer_id === user.customer_id);
      if (found) {
        return {
          id: found.customer_id,
          name: found.customer_name,
          slug: found.customer_id,
          isDefault: found.is_default,
        };
      }
    }
    return {
      id: user?.customer_id || 'default',
      name: user?.customer_name || 'Organization',
      slug: user?.customer_id || 'default',
      isDefault: true,
    };
  }, [user?.tenant_memberships, user?.customer_id, user?.customer_name]);

  const handleTenantChange = async (tenant: Tenant) => {
    if (tenant.id === user?.customer_id || switching) return;

    setSwitching(true);
    try {
      const response = await AXIOS_INSTANCE.post('/v1/auth/switch-tenant', {
        customer_id: tenant.id
      });

      const { access_token, refresh_token, user: newUserProfile } = response.data;

      // Update tokens (API client reads auth_token)
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      localStorage.removeItem('access_token');

      // Update user state
      setUser(newUserProfile);

      // Reload the page to reset all state
      window.location.reload();
    } catch (err) {
      console.error('Failed to switch tenant:', err);
    } finally {
      setSwitching(false);
    }
  };

  const handleSetDefault = async (tenant: Tenant) => {
    try {
      await AXIOS_INSTANCE.put('/v1/auth/default-tenant', {
        customer_id: tenant.id
      });

      // Update local state to reflect new default
      if (user?.tenant_memberships) {
        const updatedMemberships = user.tenant_memberships.map(m => ({
          ...m,
          is_default: m.customer_id === tenant.id
        }));
        setUser({
          ...user,
          tenant_memberships: updatedMemberships
        });
      }
    } catch (err) {
      console.error('Failed to set default tenant:', err);
    }
  };

  // Close notification panel when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setNotificationOpen(false);
      }
    }

    if (isNotificationOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isNotificationOpen, setNotificationOpen]);

  // Initialize sample notifications for demo (only once)
  useEffect(() => {
    const hasInitialized = localStorage.getItem('notifications-demo-initialized');
    if (!hasInitialized && user) {
      notificationHelpers.success(
        'Welcome to Eliza Forge',
        `Welcome back, ${user.first_name || user.full_name}! Your dashboard is ready.`,
        '/admin/dashboard',
        'View Dashboard'
      );

      notificationHelpers.info(
        'System Update Available',
        'A new system update is available with enhanced security features.',
        '/admin/system',
        'View Details'
      );

      notificationHelpers.warning(
        'User Management Access',
        'You now have access to user management features. Review user permissions regularly.',
        '/admin/users',
        'Manage Users'
      );

      localStorage.setItem('notifications-demo-initialized', 'true');
    }
  }, [user]);

  // Simple 2-state theme toggle (light/dark)
  const isDark = theme === 'dark';
  
  const toggleTheme = () => {
    setTheme(isDark ? 'light' : 'dark');
  };

  return (
    <Toolbar
      leftContent={
        <TenantSwitcher
          tenants={tenants}
          currentTenant={currentTenant}
          onTenantChange={handleTenantChange}
          onSetDefault={handleSetDefault}
        />
      }
      rightContent={
        <ToolbarSection>
          {/* Theme Toggle */}
          <ToolbarItem
            icon={isDark ? <SunIcon className="h-5 w-5" /> : <MoonIcon className="h-5 w-5" />}
            onClick={toggleTheme}
            tooltip={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle theme"
          />

          {/* Notifications */}
          <div className="relative" ref={notificationRef}>
            <ToolbarItem
              icon={<BellIcon className="h-5 w-5" />}
              onClick={toggleNotifications}
              badge={unreadCount > 0 ? unreadCount : undefined}
              tooltip="Notifications"
              aria-label="Notifications"
            />
            <NotificationPanel
              isOpen={isNotificationOpen}
              onClose={() => setNotificationOpen(false)}
            />
          </div>

          <ToolbarDivider />

          {/* Help / Feedback */}
          <ToolbarTextButton
            icon={<ChatBubbleLeftRightIcon className="h-4 w-4" />}
            onClick={() => setIsFeedbackOpen(true)}
            title="Platform Help & Feedback"
          >
            <span className="hidden md:inline">Help / Feedback</span>
          </ToolbarTextButton>

          {/* Feedback Panel */}
          <FeedbackPanel
            isOpen={isFeedbackOpen}
            onClose={() => setIsFeedbackOpen(false)}
          />

          {/* User Menu */}
          <Popover>
            <PopoverTrigger asChild>
              <button
                className="cursor-pointer flex items-center gap-1 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors"
              >
                <Avatar
                  size="sm"
                  name={user?.full_name || user?.first_name || 'User'}
                  className="ring-2 ring-white dark:ring-dark-surface"
                />
                <ChevronDownIcon className="h-3 w-3 text-gray-500 dark:text-gray-400" />
              </button>
            </PopoverTrigger>

            <PopoverContent align="end" sideOffset={8} className="w-56 p-0">
              {/* User Info */}
              <div className="p-3 border-b border-gray-200 dark:border-dark-border/30">
                <div className="text-sm font-medium text-charcoal dark:text-white">
                  {user?.full_name}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {user?.email}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Role: {user?.primary_role || 'No role assigned'}
                </div>
              </div>

              {/* Menu Items */}
              <div className="py-1">
                <Link
                  to="/profile"
                  className="flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-white transition-colors"
                >
                  <UserCircleIcon className="h-4 w-4 mr-3" />
                  Profile Settings
                </Link>

                <Link
                  to="/settings"
                  className="flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-white transition-colors"
                >
                  <Cog6ToothIcon className="h-4 w-4 mr-3" />
                  Settings
                </Link>
              </div>

              {/* Sign Out */}
              <div className="py-1 border-t border-gray-200 dark:border-dark-border/30">
                <button
                  onClick={handleLogout}
                  className="flex items-center w-full px-3 py-2 text-sm text-left text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-white transition-colors"
                >
                  <ArrowRightOnRectangleIcon className="h-4 w-4 mr-3" />
                  Sign Out
                </button>
              </div>
            </PopoverContent>
          </Popover>
        </ToolbarSection>
      }
    />
  );
}

export default Header;

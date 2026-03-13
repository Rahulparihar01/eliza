/**
 * Admin Layout Component
 * 3-pane layout for admin portal following Linear design system
 */

import React from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { 
  HomeIcon, 
  UsersIcon, 
  DocumentTextIcon, 
  CpuChipIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  Bars3Icon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { useUI } from '../../stores/useUI';
import { useAuth } from '../../stores/useAuth';

interface AdminLayoutProps {
  children?: React.ReactNode;
}

const navigation = [
  { name: 'Dashboard', href: '/admin/dashboard', icon: HomeIcon, permission: 'documents:read' },
  { name: 'Users', href: '/admin/users', icon: UsersIcon, permission: 'users:read' },
  { name: 'Documents', href: '/admin/documents', icon: DocumentTextIcon, permission: 'documents:read' },
  { name: 'AI Models', href: '/admin/ai-models', icon: CpuChipIcon, permission: 'models:read' },
  { name: 'Analytics', href: '/admin/analytics', icon: ChartBarIcon, permission: 'analytics:read' },
  { name: 'System', href: '/admin/system', icon: Cog6ToothIcon, permission: 'system:health' },
];

export default function AdminLayout({ children }: AdminLayoutProps) {
  const location = useLocation();
  const leftCollapsed = useUI(s => s.leftCollapsed);
  const rightOpen = useUI(s => s.rightOpen);
  const rightWidth = useUI(s => s.rightWidth);
  const toggleLeftPanel = useUI(s => s.toggleLeftPanel);
  const hasPermission = useAuth(s => s.hasPermission);
  const isLoading = useAuth(s => s.isLoading);
  const user = useAuth(s => s.user);

  // Filter navigation based on permissions
  // Wait for auth to load before filtering to prevent race conditions
  const filteredNavigation = isLoading || !user
    ? []
    : navigation.filter(item =>
        !item.permission || hasPermission(item.permission)
      );

  return (
    <div className="h-screen bg-bg flex overflow-hidden">
      {/* Left Sidebar */}
      <div className={`
        bg-surface border-r border-border flex-shrink-0 transition-all duration-200
        ${leftCollapsed ? 'w-16' : 'w-64'}
      `}>
        {/* Header */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-border">
          {!leftCollapsed && (
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-brand rounded-lg flex items-center justify-center">
                <span className="text-on-brand font-bold text-sm">AI</span>
              </div>
              <div>
                <h1 className="text-sm font-semibold text-text">Admin Portal</h1>
                <p className="text-xs text-muted">AI Enablement Platform</p>
              </div>
            </div>
          )}
          <button
            onClick={toggleLeftPanel}
            className="p-2 rounded-lg hover:bg-surface-2 transition-colors"
          >
            {leftCollapsed ? (
              <Bars3Icon className="w-5 h-5 text-muted" />
            ) : (
              <XMarkIcon className="w-5 h-5 text-muted" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {filteredNavigation.map((item) => {
            const isActive = location.pathname.startsWith(item.href);
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={`
                  group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors
                  ${isActive 
                    ? 'bg-brand-soft text-brand-strong' 
                    : 'text-muted hover:text-text hover:bg-surface-2'
                  }
                `}
              >
                <item.icon className={`
                  flex-shrink-0 w-5 h-5 transition-colors
                  ${isActive ? 'text-brand-strong' : 'text-muted-2 group-hover:text-text'}
                  ${leftCollapsed ? 'mr-0' : 'mr-3'}
                `} />
                {!leftCollapsed && item.name}
              </NavLink>
            );
          })}
        </nav>

        {/* User Info */}
        {!leftCollapsed && user && (
          <div className="p-4 border-t border-border">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-brand-soft rounded-full flex items-center justify-center">
                <span className="text-brand-strong font-medium text-sm">
                  {user.full_name?.charAt(0) || user.first_name?.charAt(0) || 'U'}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text truncate">
                  {user.full_name || user.first_name}
                </p>
                <p className="text-xs text-muted truncate">
                  {user.primary_role || 'Admin'}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Center Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {children || <Outlet />}
        </div>

        {/* Right Panel */}
        {rightOpen && (
          <div
            className="bg-surface border-l border-border flex-shrink-0 overflow-y-auto w-var"
            style={{ ['--w' as any]: typeof rightWidth === 'number' ? `${rightWidth}px` : String(rightWidth) }}
          >
            <div className="p-6">
              <h3 className="text-lg font-semibold text-text mb-4">Details</h3>
              <p className="text-muted">Select an item to view details</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

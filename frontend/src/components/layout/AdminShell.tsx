/**
 * AdminShell Component
 * 
 * Unified layout wrapper for admin pages.
 * Combines breadcrumbs, header, and content area.
 * 
 * Note: Sub-navigation is now handled by the contextual sidebar panel
 * (SidebarContextPanel) which appears when a section is activated.
 * The subNavItems prop is deprecated but kept for backward compatibility.
 * 
 * Migrated to DS tokens (Jan 2026).
 * 
 * Usage:
 * <AdminShell
 *   title="Tenant Management"
 *   subtitle="Create and manage customer organizations"
 *   icon={BuildingOfficeIcon}
 *   breadcrumbs={[
 *     { label: 'Platform Admin', path: '/platform-admin/tenants' },
 *     { label: 'Tenant Management' },
 *   ]}
 *   actions={<Button>+ Create Tenant</Button>}
 * >
 *   {content}
 * </AdminShell>
 */

import React from 'react';
import { Breadcrumbs, BreadcrumbItem } from '../common/Breadcrumbs';
import { SubNav, SubNavItem } from './SubNav';

interface AdminShellProps {
  // Header
  title: string;
  subtitle?: string;
  icon?: React.ComponentType<{ className?: string }>;
  
  // Navigation
  breadcrumbs: BreadcrumbItem[];
  /** @deprecated Sub-navigation is now handled by contextual sidebar. This prop is kept for backward compatibility. */
  subNavItems?: SubNavItem[];
  /** Whether to show the legacy inline SubNav (default: false for new contextual nav) */
  showInlineSubNav?: boolean;
  
  // Actions (buttons in header)
  actions?: React.ReactNode;
  
  // Content
  children: React.ReactNode;
  
  // Optional styling
  className?: string;
  contentClassName?: string;
}

export function AdminShell({
  title,
  subtitle,
  icon: IconComponent,
  breadcrumbs,
  subNavItems = [],
  showInlineSubNav = false,
  actions,
  children,
  className = '',
  contentClassName = '',
}: AdminShellProps) {
  // Determine if we should show the inline SubNav
  // By default, we don't (since contextual sidebar handles it)
  const shouldShowSubNav = showInlineSubNav && subNavItems.length > 0;

  return (
    <div className={`h-full flex flex-col overflow-hidden bg-gray-50 dark:bg-dark-bg ${className}`}>
      {/* Breadcrumbs */}
      <div className="flex-shrink-0 px-6 pt-4">
        <Breadcrumbs items={breadcrumbs} className="mb-4" />
      </div>

      {/* Header */}
      <div className="flex-shrink-0 px-6 pb-4 border-b border-gray-200 dark:border-dark-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Icon */}
            {IconComponent && (
              <div className="p-3 bg-eliza-red/10 rounded-xl">
                <IconComponent className="w-6 h-6 text-eliza-red" />
              </div>
            )}
            
            {/* Title & Subtitle */}
            <div>
              <h1 className="font-title text-h1 text-charcoal dark:text-gray-100">{title}</h1>
              {subtitle && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{subtitle}</p>
              )}
            </div>
          </div>

          {/* Actions */}
          {actions && (
            <div className="flex items-center gap-3">
              {actions}
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {shouldShowSubNav ? (
        // Legacy layout with inline SubNav
        <div className="flex-1 flex overflow-hidden min-h-0">
          <SubNav items={subNavItems} />
          <div className={`flex-1 overflow-y-auto p-6 scrollbar-stable ${contentClassName}`}>
            {children}
          </div>
        </div>
      ) : (
        // New layout - full width content (sub-nav is in contextual sidebar)
        <div className={`flex-1 overflow-y-auto p-6 scrollbar-stable ${contentClassName}`}>
          {children}
        </div>
      )}
    </div>
  );
}

export default AdminShell;

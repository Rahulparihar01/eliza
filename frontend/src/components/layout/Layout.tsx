/**
 * Main Layout Component - Eliza Forge
 * 
 * Three-pane layout: Header + Navigation + Main Content + Optional Right Panel
 * Following the Linear-style design system from UX specification.
 * 
 * Uses AppSidebar for unified navigation with animated content switching.
 */

import React, { useState, useEffect, useCallback, ReactNode } from 'react';
import Header from './Header';
import AppSidebar from './AppSidebar';
import TenantViewBanner from './TenantViewBanner';
import LoginBanner from './LoginBanner';
import MultiTenantWelcome from './MultiTenantWelcome';
import DeactivatedTenantBanner from './DeactivatedTenantBanner';
import { useAuth } from '../../stores/useAuth';
import type { SidebarMode } from '../ui/sidebar';

const SIDEBAR_MODE_KEY = 'app_sidebar_mode';

function getPersistedSidebarMode(): SidebarMode {
  try {
    const raw = localStorage.getItem(SIDEBAR_MODE_KEY);
    if (raw === 'collapsed' || raw === 'expanded') return raw;
  } catch {
    // localStorage may be unavailable
  }
  return 'expanded';
}

function persistSidebarMode(mode: SidebarMode) {
  try {
    localStorage.setItem(SIDEBAR_MODE_KEY, mode);
  } catch {
    // localStorage may be unavailable
  }
}

interface LayoutProps {
  children: ReactNode;
  rightPanel?: ReactNode;
  showRightPanel?: boolean;
  pageTitle?: string;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  /** Override sidebar mode */
  sidebarModeOverride?: SidebarMode;
  /** @deprecated Use sidebarModeOverride instead */
  sidebarCollapsedOverride?: boolean;
}

export function Layout({
  children,
  rightPanel,
  showRightPanel = false,
  pageTitle,
  breadcrumbs = [],
  sidebarModeOverride,
  sidebarCollapsedOverride,
}: LayoutProps) {
  const [sidebarMode, _setSidebarMode] = useState<SidebarMode>(getPersistedSidebarMode);
  const [tenantDeactivated, setTenantDeactivated] = useState<{
    tenantName: string;
    deactivatedAt?: string;
    message?: string;
  } | null>(null);
  const { user } = useAuth();

  // Wrap setter to also persist to localStorage
  const setSidebarMode = useCallback((mode: SidebarMode) => {
    _setSidebarMode(mode);
    persistSidebarMode(mode);
  }, []);

  // Determine current sidebar mode (override takes precedence)
  const currentSidebarMode: SidebarMode = sidebarModeOverride 
    ?? (sidebarCollapsedOverride !== undefined 
      ? (sidebarCollapsedOverride ? 'collapsed' : 'expanded')
      : sidebarMode);

  // Simple toggle - always the same behavior
  const toggleSidebar = () => {
    const newMode = sidebarMode === 'expanded' ? 'collapsed' : 'expanded';
    setSidebarMode(newMode);
  };

  // Listen for tenant deactivation events
  useEffect(() => {
    // Check if there's stored deactivation info on mount
    const storedDeactivation = localStorage.getItem('tenant_deactivated');
    if (storedDeactivation) {
      try {
        setTenantDeactivated(JSON.parse(storedDeactivation));
      } catch {
        // Ignore parsing errors
      }
    }

    // Listen for new deactivation events
    const handleTenantDeactivated = (event: CustomEvent) => {
      setTenantDeactivated({
        tenantName: event.detail.tenant_name,
        deactivatedAt: event.detail.deactivated_at,
        message: event.detail.message
      });
    };

    window.addEventListener('tenant-deactivated', handleTenantDeactivated as EventListener);
    
    return () => {
      window.removeEventListener('tenant-deactivated', handleTenantDeactivated as EventListener);
    };
  }, []);

  // Handle switching tenant when deactivated
  const handleSwitchTenant = () => {
    // Clear the deactivation state and info
    localStorage.removeItem('tenant_deactivated');
    setTenantDeactivated(null);
    // The tenant switcher will be in the header, user can use it
    window.location.reload();
  };

  // If tenant is deactivated, show the full-screen banner
  if (tenantDeactivated) {
    return (
      <DeactivatedTenantBanner
        tenantName={tenantDeactivated.tenantName}
        deactivatedAt={tenantDeactivated.deactivatedAt}
        hasOtherTenants={user?.has_multiple_tenants}
        onSwitchTenant={handleSwitchTenant}
      />
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-dark-bg overflow-hidden">
      {/* Tenant View Banner - Shows when platform admin is viewing as tenant */}
      <TenantViewBanner />
      
      {/* Login Banner - Shows after login, auto-dismisses after 3 seconds */}
      <LoginBanner />
      
      {/* Multi-Tenant Welcome Popup - Shows for first-time multi-tenant users */}
      <MultiTenantWelcome />
      
      {/* Main Layout: Sidebar + (Toolbar + Content) - Gemini-style */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* AppSidebar - Unified navigation with animated content switching */}
        <AppSidebar
          mode={currentSidebarMode}
          onToggle={toggleSidebar}
          onModeChange={setSidebarMode}
        />
        
        {/* Right Column: Toolbar + Content */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
          {/* Header/Toolbar - only spans content area */}
          <Header onMenuToggle={toggleSidebar} />
          
          {/* Main Content */}
          <main className="flex-1 flex flex-col overflow-hidden min-w-0 bg-gray-50 dark:bg-dark-bg">
          {/* Page Header */}
          {(pageTitle || breadcrumbs.length > 0) && (
            <div className="px-6 py-3">
              {/* Breadcrumbs */}
              {breadcrumbs.length > 0 && (
                <nav className="flex mb-1" aria-label="Breadcrumb">
                  <ol className="flex items-center space-x-2">
                    {breadcrumbs.map((crumb, index) => (
                      <li key={index} className="flex items-center">
                        {index > 0 && (
                          <svg
                            className="flex-shrink-0 h-4 w-4 text-muted-2 mx-2"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                          >
                            <path
                              fillRule="evenodd"
                              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        )}
                        {crumb.path ? (
                          <a
                            href={crumb.path}
                            className="text-sm text-muted hover:text-text transition-colors duration-fast"
                          >
                            {crumb.label}
                          </a>
                        ) : (
                          <span className="text-sm text-text font-medium">
                            {crumb.label}
                          </span>
                        )}
                      </li>
                    ))}
                  </ol>
                </nav>
              )}
              
              {/* Page Title */}
              {pageTitle && (
                <h1 className="text-2xl font-semibold text-text">
                  {pageTitle}
                </h1>
              )}
            </div>
          )}
          
          {/* Page Content */}
          <div className="flex-1 overflow-hidden min-h-0 min-w-0">
            <div className={`flex h-full min-h-0 min-w-0 overflow-hidden ${showRightPanel ? '' : ''}`}>
              {/* Main content area */}
              <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
                {children}
              </div>

              {/* Right Panel */}
              {showRightPanel && rightPanel && (
                <div className="w-80 bg-surface-2 border-l border-border p-6 overflow-y-auto">
                  {rightPanel}
                </div>
              )}
            </div>
          </div>
        </main>
        
        </div>
      </div>
    </div>
  );
}

// Specialized layout components for common patterns

interface DashboardLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function DashboardLayout({ children, title, subtitle, actions }: DashboardLayoutProps) {
  return (
    <Layout>
      <div className="space-y-6">
        {/* Dashboard Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-text">{title}</h1>
            {subtitle && (
              <p className="text-muted mt-1">{subtitle}</p>
            )}
          </div>
          {actions && (
            <div className="flex items-center space-x-3">
              {actions}
            </div>
          )}
        </div>
        
        {/* Dashboard Content */}
        {children}
      </div>
    </Layout>
  );
}

interface FormLayoutProps {
  children: ReactNode;
  title: string;
  description?: string;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  actions?: ReactNode;
}

export function FormLayout({ children, title, description, breadcrumbs, actions }: FormLayoutProps) {
  return (
    <Layout pageTitle={title} breadcrumbs={breadcrumbs}>
      <div className="max-w-4xl mx-auto">
        {/* Form Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-text">{title}</h1>
          {description && (
            <p className="text-muted mt-2">{description}</p>
          )}
        </div>
        
        {/* Form Content */}
        <div className="bg-surface rounded-lg border border-border p-6">
          {children}
        </div>
        
        {/* Form Actions */}
        {actions && (
          <div className="mt-6 flex justify-end space-x-3">
            {actions}
          </div>
        )}
      </div>
    </Layout>
  );
}

interface DetailLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
  breadcrumbs?: Array<{ label: string; path?: string }>;
  actions?: ReactNode;
  rightPanel?: ReactNode;
  tabs?: Array<{ label: string; value: string; current: boolean }>;
  onTabChange?: (tab: string) => void;
}

export function DetailLayout({ 
  children, 
  title, 
  subtitle, 
  breadcrumbs, 
  actions, 
  rightPanel,
  tabs,
  onTabChange
}: DetailLayoutProps) {
  return (
    <Layout 
      breadcrumbs={breadcrumbs}
      rightPanel={rightPanel}
      showRightPanel={!!rightPanel}
    >
      <div className="space-y-6">
        {/* Detail Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-text">{title}</h1>
            {subtitle && (
              <p className="text-muted mt-1">{subtitle}</p>
            )}
          </div>
          {actions && (
            <div className="flex items-center space-x-3">
              {actions}
            </div>
          )}
        </div>
        
        {/* Tabs */}
        {tabs && tabs.length > 0 && (
          <div className="border-b border-border">
            <nav className="-mb-px flex space-x-8">
              {tabs.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => onTabChange?.(tab.value)}
                  className={`
                    py-2 px-1 border-b-2 font-medium text-sm transition-colors duration-fast
                    ${tab.current
                      ? 'border-brand text-brand'
                      : 'border-transparent text-muted hover:text-text hover:border-border-strong'
                    }
                  `}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        )}
        
        {/* Detail Content */}
        {children}
      </div>
    </Layout>
  );
}

export default Layout;

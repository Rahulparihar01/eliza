/**
 * AppSidebar - Main Application Sidebar
 * 
 * The unified sidebar for the entire application.
 * Uses DS primitives with animated content switching.
 * 
 * Features:
 * - Single sidebar with consistent hamburger toggle
 * - Animated content swap when drilling into sections
 * - Collapse/expand behavior works in all contexts
 * - Back button is content (not header)
 */

import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  Bars3Icon,
  Cog6ToothIcon,
  BuildingOffice2Icon,
  CommandLineIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarContentSwitch,
  type SidebarMode,
} from '../ui';
import { useNavigation, type ActiveSection } from '../../contexts/NavigationContext';
import { useAuth } from '../../contexts/AuthContext';
import { MainNavContent } from '../navigation/MainNavContent';
import { SectionNavContent } from '../navigation/SectionNavContent';
import { getSectionConfig } from '../navigation/sectionConfigs';
import { cn } from '../../shared/lib/cn';
import { isFrontendPageEnabled } from '../../shared/lib/applets';

/* ============================================
   Types
   ============================================ */

interface AppSidebarProps {
  /** Initial sidebar mode */
  defaultMode?: SidebarMode;
  /** Callback when mode changes */
  onModeChange?: (mode: SidebarMode) => void;
  /** External mode control (for Layout integration) */
  mode?: SidebarMode;
  /** External toggle callback (for Header integration) */
  onToggle?: () => void;
}

/* ============================================
   Admin Nav Item Component
   ============================================ */

interface AdminNavItemProps {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  contextualSection: ActiveSection;
  collapsed: boolean;
}

function AdminNavItem({ label, path, icon: IconComponent, contextualSection, collapsed }: AdminNavItemProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { activeSection, setActiveSection } = useNavigation();

  const isSectionActive = activeSection === contextualSection;
  const isActive = isSectionActive || location.pathname.startsWith(path);

  const handleClick = () => {
    setActiveSection(contextualSection);
    
    // Navigate to the first item in the section's submenu
    // Use a small delay to allow the sidebar animation to start first
    const sectionConfig = getSectionConfig(contextualSection);
    if (sectionConfig && sectionConfig.items.length > 0) {
      // Find the first navigable item (skip headers, disabled, coming-soon, and applet-gated items)
      const firstNavigableItem = sectionConfig.items.find(
        item => !item.sectionHeader && !item.disabled && !item.comingSoon
          && (!item.pageKey || isFrontendPageEnabled(item.pageKey))
      );
      if (firstNavigableItem) {
        // Delay navigation slightly to let animation begin
        setTimeout(() => {
          navigate(firstNavigableItem.path);
        }, 50);
      }
    }
  };

  return (
    <button
      onClick={handleClick}
      className={cn(
        "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium",
        "transition-colors duration-150",
        "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
        isActive
          ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20"
          : "text-charcoal dark:text-gray-300",
        collapsed && "justify-center px-2"
      )}
      title={collapsed ? label : undefined}
    >
      <IconComponent className={cn(
        "h-5 w-5 flex-shrink-0",
        isActive ? "text-eliza-red" : "text-gray-500 dark:text-gray-400"
      )} />
      {!collapsed && (
        <>
          <span className="flex-1 text-left truncate">{label}</span>
          <ChevronRightIcon className={cn(
            "h-4 w-4",
            isActive ? "text-eliza-red" : "text-gray-400"
          )} />
        </>
      )}
    </button>
  );
}

/* ============================================
   AppSidebar Component
   ============================================ */

export function AppSidebar({
  defaultMode = 'expanded',
  onModeChange,
  mode: controlledMode,
  onToggle: externalToggle,
}: AppSidebarProps) {
  // Internal state (used when not controlled)
  const [internalMode, setInternalMode] = useState<SidebarMode>(defaultMode);
  
  // Use controlled mode if provided, otherwise internal
  const mode = controlledMode ?? internalMode;
  const collapsed = mode === 'collapsed';

  // Navigation context
  const { activeSection, clearSection } = useNavigation();
  
  // Auth for permission checks
  const { hasAnyPermission } = useAuth();
  
  // Check admin permissions
  const hasAdminSettingsAccess = hasAnyPermission(['admin:settings:read', 'connections:read', 'users:read', 'platform:admin']);
  const hasPlatformSettingsAccess = hasAnyPermission(['platform:admin']);
  const hasAiConsoleAccess =
    isFrontendPageEnabled('evals') &&
    hasAnyPermission(['ai_console:access', 'evals:read', 'platform:admin']);
  const hasAnyAdminAccess = hasAdminSettingsAccess || hasPlatformSettingsAccess || hasAiConsoleAccess;

  // Track previous section for animation direction
  const prevSectionRef = useRef<string | null>(null);
  
  // Calculate direction based on transition type
  // This needs to be computed BEFORE the render, not in an effect
  const animationDirection: 'forward' | 'backward' = (() => {
    const prevSection = prevSectionRef.current;
    if (activeSection && !prevSection) {
      // Drilling into a section (main -> section)
      return 'forward';
    } else if (!activeSection && prevSection) {
      // Going back to main nav (section -> main)
      return 'backward';
    }
    // Default or same state
    return 'forward';
  })();

  // Update ref after direction is calculated
  useEffect(() => {
    prevSectionRef.current = activeSection;
  }, [activeSection]);

  // Toggle sidebar mode
  const handleToggle = () => {
    if (externalToggle) {
      externalToggle();
    } else {
      const newMode = mode === 'expanded' ? 'collapsed' : 'expanded';
      setInternalMode(newMode);
      onModeChange?.(newMode);
    }
  };

  // Handle back navigation
  const handleBack = () => {
    clearSection();
  };

  return (
    <Sidebar
      mode={mode}
      collapsedWidth={64}
      expandedWidth={240}
    >
      {/* Header with Hamburger Toggle */}
      <SidebarHeader
        className={cn(
          "h-12 px-3 flex items-center",
          collapsed && "px-2 justify-center"
        )}
      >
        <button
          onClick={handleToggle}
          className={cn(
            "flex items-center justify-center",
            "w-8 h-8 rounded-lg",
            "text-gray-500 dark:text-gray-400",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
            "transition-colors duration-150",
            "focus:outline-none focus:ring-2 focus:ring-eliza-red focus:ring-offset-1"
          )}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <Bars3Icon className="h-5 w-5" />
        </button>
      </SidebarHeader>

      {/* Navigation Content with Animated Switching */}
      <SidebarContent>
        <SidebarContentSwitch
          activeKey={activeSection || 'main'}
          direction={animationDirection}
          duration={250}
        >
          {activeSection ? (
            <SectionNavContent
              section={activeSection}
              onBack={handleBack}
              collapsed={collapsed}
            />
          ) : (
            <MainNavContent collapsed={collapsed} />
          )}
        </SidebarContentSwitch>
      </SidebarContent>

      {/* Admin Section in Footer - only show when on main nav */}
      {!activeSection && hasAnyAdminAccess && (
        <SidebarFooter
          collapsed={collapsed}
          className="!p-0 border-t border-gray-100 dark:border-dark-border/30"
        >
          {/* ADMIN label */}
          {!collapsed && (
            <div className="px-4 pt-3 pb-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                Admin
              </span>
            </div>
          )}
          
          {/* Admin items */}
          <div className={cn("px-2 pb-2 space-y-0.5", collapsed && "pt-2")}>
            {hasAiConsoleAccess && (
              <AdminNavItem
                label="AI Console"
                path="/evals"
                icon={CommandLineIcon}
                contextualSection="ai-console"
                collapsed={collapsed}
              />
            )}
            {hasAdminSettingsAccess && (
              <AdminNavItem
                label="Admin Settings"
                path="/admin/settings"
                icon={Cog6ToothIcon}
                contextualSection="admin-settings"
                collapsed={collapsed}
              />
            )}
            {hasPlatformSettingsAccess && (
              <AdminNavItem
                label="Platform Settings"
                path="/platform-admin"
                icon={BuildingOffice2Icon}
                contextualSection="platform-settings"
                collapsed={collapsed}
              />
            )}
          </div>
        </SidebarFooter>
      )}
    </Sidebar>
  );
}

export default AppSidebar;

/**
 * Section Configurations for Contextual Sidebar Navigation
 * 
 * Defines the sections that have contextual sub-navigation panels.
 * When a user clicks on these sections, the sidebar content switches
 * to show the sub-items with a back button.
 */

import {
  Cog6ToothIcon,
  BuildingOffice2Icon,
  UsersIcon,
  CpuChipIcon,
  EnvelopeIcon,
  ClockIcon,
  ShieldCheckIcon,
  ChartBarIcon,
  LinkIcon,
  UserGroupIcon,
  MagnifyingGlassIcon,
  ClipboardDocumentListIcon,
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  PhoneIcon,
  SwatchIcon,
  BeakerIcon,
  CommandLineIcon,
  AdjustmentsHorizontalIcon,
  CircleStackIcon,
  ServerStackIcon,
} from '@heroicons/react/24/outline';
import type { ContextPanelItem } from '../ui/sidebar-context-panel';
import type { ActiveSection } from '../../contexts/NavigationContext';
import { isFrontendPageEnabled } from '../../shared/lib/applets';

/* ============================================
   Section Configuration Type
   ============================================ */

export type SectionNavItem = ContextPanelItem & {
  /** Optional modular page key for applet/page-level visibility gating */
  pageKey?: string;
}

export interface SectionConfig {
  /** Section identifier (matches ActiveSection type) */
  id: ActiveSection
  /** Display title */
  title: string
  /** Section icon */
  icon: React.ComponentType<{ className?: string }>
  /** Base path that activates this section */
  basePath: string
  /** Sub-navigation items */
  items: SectionNavItem[]
}

/* ============================================
   AI Recruiter Section
   ============================================ */

export const aiRecruiterConfig: SectionConfig = {
  id: 'ai-recruiter',
  title: 'AI Recruiter',
  icon: UserGroupIcon,
  basePath: '/talent',
  items: [
    {
      label: 'Search Templates',
      path: '/talent/analysis-config',
      icon: MagnifyingGlassIcon,
      pageKey: 'talent-intelligence',
    },
    {
      label: 'Search Results',
      path: '/talent/outreach',
      icon: UserGroupIcon,
      pageKey: 'talent-intelligence',
    },
    {
      label: 'Email Templates',
      path: '/talent/email-templates',
      icon: EnvelopeIcon,
      pageKey: 'talent-intelligence',
    },
    {
      label: 'Blueprints & DNA',
      path: '/talent/configuration',
      icon: SparklesIcon,
      pageKey: 'talent-intelligence',
    },
    {
      label: 'Search History',
      path: '/talent/history',
      icon: ClipboardDocumentListIcon,
      pageKey: 'talent-intelligence',
    },
    // Coming Soon section
    {
      label: 'COMING SOON',
      path: '#coming-soon',
      sectionHeader: true,
    },
    {
      label: 'Reference Checks',
      path: '/reference-checks',
      icon: PhoneIcon,
      comingSoon: true,
      pageKey: 'reference-checks',
    },
  ],
};

/* ============================================
   Chat Section (formerly Business Intelligence)
   ============================================ */

export const chatConfig: SectionConfig = {
  id: 'chat',
  title: 'Chat',
  icon: ChatBubbleLeftRightIcon,
  basePath: '/chat',
  items: [
    {
      label: 'New Chat',
      path: '/chat',
      icon: ChatBubbleLeftRightIcon,
    },
    // Conversations are shown dynamically in the sidebar
  ],
};

/* ============================================
   Admin Settings Section (Tenant Admin)
   ============================================ */

export const adminSettingsConfig: SectionConfig = {
  id: 'admin-settings',
  title: 'Admin Settings',
  icon: Cog6ToothIcon,
  basePath: '/admin',
  items: [
    {
      label: 'Data Connections',
      path: '/data-connections',
      icon: LinkIcon,
      pageKey: 'data-connections',
    },
    {
      label: 'Users & Roles',
      path: '/tenant-admin/users',
      icon: UsersIcon,
    },
    {
      label: 'AI Providers',
      path: '/admin/settings',
      icon: CpuChipIcon,
    },
    {
      label: 'Adoption Settings',
      path: '/admin/adoption-settings',
      icon: ChartBarIcon,
      pageKey: 'adoption',
    },
    {
      label: 'Job Scheduler',
      path: '/admin/jobs',
      icon: ClockIcon,
      requiredPermissions: ['adoption:manage_jobs', 'platform:admin'],
      pageKey: 'adoption',
    },
    {
      label: 'Theme',
      path: '/tenant-admin/theme',
      icon: SwatchIcon,
    },
    {
      label: 'SSO',
      path: '/tenant-admin/sso',
      icon: ShieldCheckIcon,
      // Intentionally ungated by applet page keys: SSO is platform core.
    },
    {
      label: 'Storage',
      path: '/tenant-admin/storage',
      icon: CircleStackIcon,
      pageKey: 'storage-settings',
    },
    {
      label: 'MCP Servers',
      path: '/admin/mcp-servers',
      icon: ServerStackIcon,
    },
  ],
};

/* ============================================
   AI Console Section
   MLOps tools: Evals, GEPA Optimizer, Prompt Management
   ============================================ */

export const aiConsoleConfig: SectionConfig = {
  id: 'ai-console',
  title: 'AI Console',
  icon: CommandLineIcon,
  basePath: '/ai-console',
  items: [
    {
      label: 'RAG Evaluations',
      path: '/evals',
      icon: BeakerIcon,
      requiredPermissions: ['ai_console:access', 'platform:admin'],
      pageKey: 'evals',
    },
    {
      label: 'Telemetry',
      path: '/telemetry',
      icon: ChartBarIcon,
      requiredPermissions: ['ai_console:access', 'platform:admin'],
      pageKey: 'telemetry',
    },
    {
      label: 'GEPA Optimizer',
      path: '/gepa-optimizer',
      icon: SparklesIcon,
      requiredPermissions: ['ai_console:access', 'platform:admin'],
      pageKey: 'gepa-optimizer',
    },
    {
      label: 'Prompt Management',
      path: '/prompt-management',
      icon: AdjustmentsHorizontalIcon,
      requiredPermissions: ['ai_console:access', 'platform:admin'],
      pageKey: 'prompt-management',
    },
    {
      label: 'Tiny Model Studio',
      path: '/ai-console/tiny-model-studio',
      icon: CpuChipIcon,
      requiredPermissions: ['ai_console:access', 'platform:admin'],
      pageKey: 'tiny-model-studio',
    },
  ],
};

/* ============================================
   Platform Settings Section (Platform Admin)
   Includes Tenant Management items
   ============================================ */

export const platformSettingsConfig: SectionConfig = {
  id: 'platform-settings',
  title: 'Platform Settings',
  icon: BuildingOffice2Icon,
  basePath: '/platform-admin',
  items: [
    {
      label: 'Admin Management',
      path: '/platform-admin/admins',
      icon: UsersIcon,
    },
    {
      label: 'AI Providers',
      path: '/platform-admin/providers',
      icon: CpuChipIcon,
    },
    {
      label: 'Email Integration',
      path: '/platform-admin/email',
      icon: EnvelopeIcon,
    },
    {
      label: 'Job Scheduler',
      path: '/platform-admin/jobs',
      icon: ClockIcon,
    },
    {
      label: 'SSO Policy',
      path: '/platform-admin/sso-policy',
      icon: ShieldCheckIcon,
      // Intentionally ungated by applet page keys: SSO is platform core.
    },
    {
      label: 'Tenant Management',
      path: '/platform-admin/tenants',
      icon: BuildingOffice2Icon,
    },
    {
      label: 'Feature Allocation',
      path: '/platform-admin/features',
      icon: ShieldCheckIcon,
    },
    {
      label: 'Adoption Access',
      path: '/platform-admin/adoption',
      icon: ChartBarIcon,
      pageKey: 'adoption',
    },
  ],
};

/* ============================================
   All Sections Map
   ============================================ */

export const sectionConfigs: Record<NonNullable<ActiveSection>, SectionConfig> = {
  'ai-recruiter': aiRecruiterConfig,
  'chat': chatConfig,
  'ai-console': aiConsoleConfig,
  'admin-settings': adminSettingsConfig,
  'platform-settings': platformSettingsConfig,
};

/* ============================================
   Helper Functions
   ============================================ */

/**
 * Get section config by ID
 */
export function getSectionConfig(sectionId: ActiveSection): SectionConfig | null {
  if (!sectionId) return null;
  return sectionConfigs[sectionId] || null;
}

function pathMatchesItem(itemPath: string, currentPath: string): boolean {
  return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
}

function isItemPathEnabled(item: SectionNavItem): boolean {
  if (!item.path || item.path.startsWith('#')) return false;
  if (item.sectionHeader || item.comingSoon || item.disabled) return false;
  if (item.pageKey && !isFrontendPageEnabled(item.pageKey)) return false;
  return true;
}

export function isSectionItemPathEnabled(path: string): boolean {
  for (const config of Object.values(sectionConfigs)) {
    for (const item of config.items) {
      if (!item.path || item.path.startsWith('#')) continue;
      if (pathMatchesItem(item.path, path)) {
        return isItemPathEnabled(item);
      }
    }
  }
  return false;
}

/**
 * Get section ID from current path
 */
export function getSectionFromPath(path: string): ActiveSection {
  // Legacy BI paths remain mapped to chat section.
  if (path.startsWith('/data-analyst') || path.startsWith('/business-intelligence')) {
    return 'chat';
  }

  // Prefer explicit submenu item matches with applet/page-aware enablement.
  for (const [sectionId, config] of Object.entries(sectionConfigs) as [NonNullable<ActiveSection>, SectionConfig][]) {
    for (const item of config.items) {
      if (!item.path || item.path.startsWith('#')) continue;
      if (!pathMatchesItem(item.path, path)) continue;
      if (!isItemPathEnabled(item)) return null;
      return sectionId;
    }
  }

  // Fallback: section base path (only if section has at least one enabled item).
  for (const [sectionId, config] of Object.entries(sectionConfigs) as [NonNullable<ActiveSection>, SectionConfig][]) {
    if (!path.startsWith(config.basePath)) continue;
    const hasEnabledItems = config.items.some(isItemPathEnabled);
    if (hasEnabledItems) return sectionId;
    return null;
  }

  return null;
}

/**
 * Check if a path belongs to a contextual section
 */
export function isContextualPath(path: string): boolean {
  return getSectionFromPath(path) !== null;
}

/**
 * Get all section IDs that have contextual navigation
 */
export function getContextualSectionIds(): NonNullable<ActiveSection>[] {
  return Object.keys(sectionConfigs) as NonNullable<ActiveSection>[];
}

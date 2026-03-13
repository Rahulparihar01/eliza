/**
 * Platform Admin Navigation Configuration
 * 
 * Defines the sub-navigation items for each platform admin section.
 */

import {
  BuildingOffice2Icon,
  ClockIcon,
  ShieldCheckIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  UsersIcon,
  CpuChipIcon,
  EnvelopeIcon,
} from '@heroicons/react/24/outline';
import { SubNavItem } from '../layout/SubNav';

/**
 * Platform Admin Sub-Nav
 * All paths are now flat under /platform-admin/ (no nested subpaths)
 */
export const platformAdminSubNav: SubNavItem[] = [
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
  },
];

/**
 * Legacy exports for backwards compatibility
 * @deprecated Use platformAdminSubNav instead
 */
export const tenantManagementSubNav: SubNavItem[] = platformAdminSubNav;
export const platformSettingsSubNav: SubNavItem[] = platformAdminSubNav;

/**
 * Get the appropriate sub-nav items based on current path
 */
export function getSubNavForPath(path: string): SubNavItem[] {
  if (path.startsWith('/platform-admin/')) {
    return platformAdminSubNav;
  }
  return [];
}

/**
 * Section metadata for AdminShell
 */
export const sectionMetadata = {
  tenants: {
    title: 'Tenant Management',
    subtitle: 'Create and manage customer organizations',
    icon: BuildingOffice2Icon,
  },
  settings: {
    title: 'Platform Settings',
    subtitle: 'Configure platform-wide integrations and access',
    icon: Cog6ToothIcon,
  },
};

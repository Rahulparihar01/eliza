/**
 * Tenant View Banner Component
 * 
 * Displays a prominent banner when platform admins are:
 * 1. Viewing the app as a specific tenant (orange/amber)
 * 2. Viewing all tenants with cross-tenant access (purple/violet)
 * 
 * Critical for security awareness - admins should always know
 * when they're operating outside their normal tenant context.
 * 
 * Uses DS Banner component with tenant-view and cross-tenant variants.
 */

import React from 'react';
import { EyeIcon, GlobeAltIcon } from '@heroicons/react/24/outline';
import { useAuth } from '../../stores/useAuth';
import { Banner } from '../ui';

export function TenantViewBanner() {
  const { 
    viewingAsTenant, 
    crossTenantAccess, 
    clearTenantView,
    isPlatformAdmin 
  } = useAuth();

  // Only show for platform admins with active tenant view
  if (!isPlatformAdmin() || (!viewingAsTenant && !crossTenantAccess)) {
    return null;
  }

  // Cross-tenant access banner (purple/violet theme)
  if (crossTenantAccess) {
    return (
      <Banner
        variant="cross-tenant"
        icon={<GlobeAltIcon className="w-5 h-5" />}
        title="Cross-Tenant Access Mode"
        message={
          <>
            You are viewing data from <strong>ALL TENANTS</strong>. 
            This mode is for reporting and compliance only.
          </>
        }
        action={{
          label: "Exit Cross-Tenant Mode",
          onClick: clearTenantView,
        }}
        dismissible={false}
      />
    );
  }

  // Viewing as specific tenant banner (amber/orange theme)
  if (viewingAsTenant) {
    return (
      <Banner
        variant="tenant-view"
        icon={<EyeIcon className="w-5 h-5" />}
        title="Viewing As Tenant"
        message={
          <>
            You are viewing the application as{' '}
            <strong className="bg-amber-400/50 px-1.5 py-0.5 rounded">
              {viewingAsTenant.tenantName}
            </strong>
            . All data shown belongs to this tenant.
          </>
        }
        action={{
          label: "Exit View Mode",
          onClick: clearTenantView,
        }}
        dismissible={false}
      />
    );
  }

  return null;
}

export default TenantViewBanner;


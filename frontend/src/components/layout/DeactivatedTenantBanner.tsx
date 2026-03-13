/**
 * Deactivated Tenant Banner Component
 * 
 * Shows a prominent banner when a user's tenant has been deactivated.
 * This covers the entire screen to prevent access to any functionality.
 */

import React from 'react';
import { ExclamationTriangleIcon, EnvelopeIcon, PhoneIcon } from '@heroicons/react/24/outline';

interface DeactivatedTenantBannerProps {
  tenantName: string;
  deactivatedAt?: string;
  onSwitchTenant?: () => void;
  hasOtherTenants?: boolean;
}

export function DeactivatedTenantBanner({
  tenantName,
  deactivatedAt,
  onSwitchTenant,
  hasOtherTenants = false
}: DeactivatedTenantBannerProps) {
  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg">
      <div className="max-w-lg mx-4">
        {/* Icon and Main Message */}
        <div className="text-center mb-8">
          <div className="mx-auto w-20 h-20 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-6">
            <ExclamationTriangleIcon className="w-10 h-10 text-red-600 dark:text-red-400" />
          </div>
          
          <h1 className="text-2xl font-bold text-text mb-2">
            Organization Deactivated
          </h1>
          
          <p className="text-lg text-muted">
            Access to <span className="font-semibold text-text">{tenantName}</span> has been suspended.
          </p>
          
          {deactivatedAt && (
            <p className="text-sm text-muted mt-2">
              Deactivated on {formatDate(deactivatedAt)}
            </p>
          )}
        </div>

        {/* Info Box */}
        <div className="bg-surface border border-border rounded-xl p-6 mb-6">
          <h2 className="font-semibold text-text mb-3">What does this mean?</h2>
          <ul className="space-y-2 text-muted text-sm">
            <li className="flex items-start gap-2">
              <span className="text-red-500 mt-0.5">•</span>
              <span>Your organization's access to Eliza Forge has been temporarily suspended.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-500 mt-0.5">•</span>
              <span>All data remains secure and will be available once access is restored.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-red-500 mt-0.5">•</span>
              <span>This may be due to billing, compliance, or administrative reasons.</span>
            </li>
          </ul>
        </div>

        {/* Contact Section */}
        <div className="bg-surface border border-border rounded-xl p-6 mb-6">
          <h2 className="font-semibold text-text mb-3">Need help?</h2>
          <p className="text-muted text-sm mb-4">
            Contact your Eliza representative or platform administrator to restore access.
          </p>
          
          <div className="flex flex-col gap-3">
            <a
              href="mailto:support@eliza.ai"
              className="flex items-center gap-3 px-4 py-3 bg-surface-2 hover:bg-surface-3 rounded-lg transition-colors text-text"
            >
              <EnvelopeIcon className="w-5 h-5 text-brand" />
              <span>support@eliza.ai</span>
            </a>
            <a
              href="tel:+1-555-ELIZA"
              className="flex items-center gap-3 px-4 py-3 bg-surface-2 hover:bg-surface-3 rounded-lg transition-colors text-text"
            >
              <PhoneIcon className="w-5 h-5 text-brand" />
              <span>Contact Support</span>
            </a>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3">
          {hasOtherTenants && onSwitchTenant && (
            <button
              onClick={onSwitchTenant}
              className="w-full py-3 px-4 bg-brand text-on-brand font-medium rounded-lg hover:bg-brand/90 transition-colors"
            >
              Switch to Another Organization
            </button>
          )}
          
          <button
            onClick={() => {
              // Clear auth and redirect to login
              localStorage.removeItem('token');
              localStorage.removeItem('user');
              window.location.href = '/login';
            }}
            className="w-full py-3 px-4 bg-surface-2 text-text font-medium rounded-lg hover:bg-surface-3 border border-border transition-colors"
          >
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}

export default DeactivatedTenantBanner;


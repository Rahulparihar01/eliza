import React from 'react';
import { Badge } from '../../../components/ui';
import type { DomainResponse, LoginMode, ProviderResponse } from './types';
import { LOGIN_MODE_LABELS } from './constants';
import {
  ShieldCheckIcon,
  GlobeAltIcon,
  KeyIcon,
} from '@heroicons/react/24/outline';

export type SsoTabKey = 'policy' | 'domains' | 'providers';

interface SsoStatusBarProps {
  loginMode: LoginMode;
  providers: ProviderResponse[];
  domains: DomainResponse[];
  onTabChange: (tab: SsoTabKey) => void;
}

function policyVariant(mode: LoginMode): 'secondary' | 'info' | 'brand' {
  if (mode === 'sso_enforced') return 'brand';
  if (mode === 'sso_optional') return 'info';
  return 'secondary';
}

export function SsoStatusBar({
  loginMode,
  providers,
  domains,
  onTabChange,
}: SsoStatusBarProps) {
  const verifiedCount = domains.filter((d) => d.status === 'verified').length;
  const enabledProviders = providers.filter((p) => p.is_enabled);
  const testedProviders = enabledProviders.filter((p) => p.last_test_status === 'success');

  const domainVariant =
    domains.length === 0 ? 'secondary' : verifiedCount > 0 ? 'success' : 'warning';

  const providerVariant =
    providers.length === 0
      ? 'secondary'
      : enabledProviders.length === 0
        ? 'warning'
        : testedProviders.length === enabledProviders.length
          ? 'success'
          : 'warning';

  const domainValue =
    domains.length === 0
      ? '0'
      : verifiedCount > 0
        ? `${verifiedCount}/${domains.length}`
        : `${domains.length}`;

  const providerValue =
    providers.length === 0 ? '0' : `${enabledProviders.length}`;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <button
        type="button"
        onClick={() => onTabChange('policy')}
        className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-4 text-left transition-all hover:border-gray-300 dark:hover:border-dark-border/80"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
            <ShieldCheckIcon className="w-5 h-5 text-blue-500" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-charcoal dark:text-gray-100 truncate">
              {LOGIN_MODE_LABELS[loginMode]}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Login Policy</div>
          </div>
        </div>
      </button>

      <button
        type="button"
        onClick={() => onTabChange('domains')}
        className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-4 text-left transition-all hover:border-gray-300 dark:hover:border-dark-border/80"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center">
            <GlobeAltIcon className="w-5 h-5 text-amber-500" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="text-2xl font-semibold text-charcoal dark:text-gray-100">{domainValue}</div>
              <Badge variant={domainVariant}>
                {domains.length === 0 ? 'none' : verifiedCount > 0 ? 'verified' : 'pending'}
              </Badge>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Verified Domains</div>
          </div>
        </div>
      </button>

      <button
        type="button"
        onClick={() => onTabChange('providers')}
        className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-4 text-left transition-all hover:border-gray-300 dark:hover:border-dark-border/80"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-emerald-500/10 rounded-lg flex items-center justify-center">
            <KeyIcon className="w-5 h-5 text-emerald-500" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="text-2xl font-semibold text-charcoal dark:text-gray-100">{providerValue}</div>
              <Badge variant={providerVariant}>
                {providers.length === 0
                  ? 'none'
                  : enabledProviders.length === 0
                    ? 'disabled'
                    : testedProviders.length === enabledProviders.length
                      ? 'active'
                      : 'untested'}
              </Badge>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">SSO Providers</div>
          </div>
        </div>
      </button>
    </div>
  );
}

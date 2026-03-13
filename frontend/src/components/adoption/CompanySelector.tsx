/**
 * Company Selector Component for Adoption Dashboard
 * 
 * Allows filtering adoption data by company.
 * Migrated to Eliza Forge Design System.
 */

import React from 'react';
import { ChevronDownIcon, BuildingOffice2Icon, CheckIcon } from '@heroicons/react/24/outline';
import { CompanyOverview } from '../../hooks/useAdoption';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';

interface CompanySelectorProps {
  companies: CompanyOverview[];
  selectedCompanyId: string | 'all';
  onSelect: (companyId: string | 'all') => void;
  loading?: boolean;
}

export function CompanySelector({
  companies,
  selectedCompanyId,
  onSelect,
  loading = false,
}: CompanySelectorProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedCompany = companies.find((c) => c.company_id === selectedCompanyId);
  const displayText = selectedCompanyId === 'all' 
    ? 'All Companies' 
    : selectedCompany?.company_name || selectedCompanyId;

  if (loading) {
    return (
      <Skeleton variant="rounded" width={200} height={40} />
    );
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 text-sm bg-white dark:bg-dark-surface border rounded-xl transition-all min-w-[200px] ${
          isOpen 
            ? 'border-transparent ring-2 ring-eliza-red' 
            : 'border-gray-200 dark:border-dark-border/50 hover:border-gray-300 dark:hover:border-dark-border'
        }`}
      >
        <BuildingOffice2Icon className="h-4 w-4 text-gray-400 dark:text-gray-500" />
        <span className="flex-1 text-left text-charcoal dark:text-gray-100 font-medium truncate">
          {displayText}
        </span>
        <ChevronDownIcon className={`h-4 w-4 text-gray-400 dark:text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border/50 rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="max-h-80 overflow-y-auto">
            {/* All Companies Option */}
            <button
              onClick={() => {
                onSelect('all');
                setIsOpen(false);
              }}
              className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors ${
                selectedCompanyId === 'all' ? 'bg-eliza-red/5' : ''
              }`}
            >
              <div className="w-8 h-8 bg-eliza-red/10 rounded-lg flex items-center justify-center">
                <BuildingOffice2Icon className="h-4 w-4 text-eliza-red" />
              </div>
              <div className="flex-1 text-left">
                <div className="font-medium text-charcoal dark:text-gray-100">All Companies</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">{companies.length} companies</div>
              </div>
              {selectedCompanyId === 'all' && (
                <CheckIcon className="h-5 w-5 text-eliza-red" />
              )}
            </button>

            <div className="border-t border-gray-200 dark:border-dark-border/30" />

            {/* Individual Companies */}
            {companies.map((company) => (
              <button
                key={company.company_id}
                onClick={() => {
                  onSelect(company.company_id);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors ${
                  selectedCompanyId === company.company_id ? 'bg-eliza-red/5' : ''
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                  company.is_own_tenant ? 'bg-green-500/10' : 'bg-blue-500/10'
                }`}>
                  <BuildingOffice2Icon className={`h-4 w-4 ${
                    company.is_own_tenant ? 'text-green-600 dark:text-green-400' : 'text-blue-600 dark:text-blue-400'
                  }`} />
                </div>
                <div className="flex-1 text-left">
                  <div className="font-medium text-charcoal dark:text-gray-100 flex items-center gap-2">
                    {company.company_name}
                    {company.is_own_tenant && (
                      <Badge variant="success" className="text-xs">Your Tenant</Badge>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {company.has_adoption_enabled ? (
                      company.last_sync_at ? (
                        `Last sync: ${new Date(company.last_sync_at).toLocaleDateString()}`
                      ) : (
                        'Enabled, no sync yet'
                      )
                    ) : (
                      'Not configured'
                    )}
                  </div>
                </div>
                {selectedCompanyId === company.company_id && (
                  <CheckIcon className="h-5 w-5 text-eliza-red" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default CompanySelector;


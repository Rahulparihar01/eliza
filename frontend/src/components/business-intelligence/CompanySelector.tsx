/**
 * Company Selector Component
 * Allows users to select which company's data to analyze
 * Shows only companies the user has permission to access
 */

import React, { useEffect } from 'react';
import { BuildingOfficeIcon, CheckIcon } from '@heroicons/react/24/outline';
import { useQuery } from '@tanstack/react-query';
import { getCompaniesApi } from '../../services/api-client';
import { queryKeys } from '../../lib/query-keys';

interface CompanySelectorProps {
  value: string | null;
  onChange: (companyId: string | null) => void;
  showDefault?: boolean;
  className?: string;
}

export default function CompanySelector({ 
  value, 
  onChange, 
  showDefault = true,
  className = '' 
}: CompanySelectorProps) {
  // Fetch accessible companies
  const { data: companiesData, isLoading } = useQuery({
    queryKey: queryKeys.companies.accessible(),
    queryFn: async () => {
      const response = await getCompaniesApi().get('/v1/companies/accessible');
      return response.data;
    },
    staleTime: 60000, // Cache for 1 minute
  });

  // Fetch default company setting
  const { data: defaultCompanyData } = useQuery({
    queryKey: queryKeys.settings.defaultCompany(),
    queryFn: async () => {
      const response = await getCompaniesApi().get('/v1/settings/default/company_hr_dataset');
      return response.data;
    },
    staleTime: 300000, // Cache for 5 minutes
  });

  const companies = companiesData?.companies || [];
  const defaultCompany = defaultCompanyData?.value || null;

  // Set default company on mount if no value selected
  useEffect(() => {
    if (!value && defaultCompany && showDefault) {
      onChange(defaultCompany);
    }
  }, [defaultCompany, value, onChange, showDefault]);

  if (isLoading) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <BuildingOfficeIcon className="h-5 w-5 text-gray-400" />
        <span className="text-sm text-gray-500">Loading companies...</span>
      </div>
    );
  }

  if (companies.length === 0) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <BuildingOfficeIcon className="h-5 w-5 text-gray-400" />
        <span className="text-sm text-gray-500">No companies available</span>
      </div>
    );
  }

  // If only one company, show it as read-only
  if (companies.length === 1) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <BuildingOfficeIcon className="h-5 w-5 text-blue-500" />
        <span className="text-sm font-medium text-gray-900">
          {companies[0].company_id}
        </span>
        <span className="text-xs text-gray-500">
          ({companies[0].employee_count} employees)
        </span>
      </div>
    );
  }

  const selectedCompany = companies.find((c: any) => c.company_id === value);

  return (
    <div className={`space-y-2 ${className}`}>
      <label className="block text-sm font-medium text-gray-700">
        <BuildingOfficeIcon className="inline h-4 w-4 mr-1" />
        Select Company
      </label>
      
      <div className="relative">
        <select
          value={value || ''}
          onChange={(e) => onChange(e.target.value || null)}
          className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 pl-3 pr-10"
        >
          {showDefault && defaultCompany && (
            <option value="">
              {defaultCompany} (default)
            </option>
          )}
          {companies.map((company: any) => (
            <option key={company.company_id} value={company.company_id}>
              {company.company_id} ({company.employee_count} employees)
            </option>
          ))}
        </select>
        
        {selectedCompany && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
            <CheckIcon className="h-5 w-5 text-green-500" />
          </div>
        )}
      </div>

      {/* Info text */}
      <p className="text-xs text-gray-500">
        {value 
          ? `Analyzing data from ${value}` 
          : defaultCompany 
            ? `Using default company: ${defaultCompany}`
            : 'Select a company to analyze'
        }
      </p>

      {/* Company details */}
      {selectedCompany && (
        <div className="mt-2 p-3 bg-blue-50 rounded-md">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-blue-900">{selectedCompany.company_id}</span>
            <span className="text-blue-700">{selectedCompany.employee_count} employees</span>
          </div>
          <div className="mt-1 text-xs text-blue-600">
            {selectedCompany.can_access ? (
              <span className="flex items-center">
                <CheckIcon className="h-3 w-3 mr-1" />
                You have access to this company's data
              </span>
            ) : (
              <span className="text-red-600">Access restricted</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


/**
 * Greenhouse Query Configuration Component
 * 
 * Allows users to configure Greenhouse API search parameters and test queries
 * to see how many candidates match before running the full analysis.
 * 
 * Supports filtering by:
 * - Department (includes all subordinate departments)
 * - Specific jobs
 * - Application status
 * - Date range
 * 
 * Based on Greenhouse Harvest API: https://developers.greenhouse.io/harvest.html
 */

import React, { useState } from 'react';
import {
  BuildingOfficeIcon,
  FunnelIcon,
  CheckCircleIcon,
  XCircleIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import LoadingSpinner from '../common/LoadingSpinner';
import { AXIOS_INSTANCE } from '../../services/api-client';

export interface GreenhouseQueryParams {
  department_id?: number;       // Department ID (includes subordinates)
  job_ids?: string;             // Comma-separated job IDs (e.g., "123,456")
  application_status?: 'active' | 'rejected' | 'hired' | '';
  created_after?: string;       // ISO date string (e.g., "2024-01-01")
  max_candidates?: number;      // Maximum candidates to fetch (1-1000)
}

interface Department {
  id: number;
  name: string;
  parent_id: number | null;
  child_ids: number[];
  external_id?: string;
}

interface Job {
  id: number;
  name: string;
  status: string;
  departments: string[];
  department_ids: number[];
  offices: string[];
}

interface GreenhouseQueryConfigProps {
  connectorId: string;
  initialParams?: GreenhouseQueryParams;
  onParamsChange: (params: GreenhouseQueryParams) => void;
  onContinue: () => void;
  onBack: () => void;
}

export function GreenhouseQueryConfig({
  connectorId,
  initialParams = {},
  onParamsChange,
  onContinue,
  onBack,
}: GreenhouseQueryConfigProps) {
  const [params, setParams] = useState<GreenhouseQueryParams>({
    department_id: initialParams.department_id,
    job_ids: initialParams.job_ids || '',
    application_status: initialParams.application_status || '',
    created_after: initialParams.created_after || '',
    max_candidates: initialParams.max_candidates || 50,
  });

  const [testResult, setTestResult] = useState<{
    success: boolean;
    job_count?: number;
    candidate_count?: number;
    message?: string;
  } | null>(null);

  const [isTesting, setIsTesting] = useState(false);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [availableJobs, setAvailableJobs] = useState<Job[]>([]);
  const [filteredJobs, setFilteredJobs] = useState<Job[]>([]);
  const [isLoadingDepartments, setIsLoadingDepartments] = useState(false);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [filterMode, setFilterMode] = useState<'department' | 'job'>('department');

  // Load departments and jobs when component mounts
  React.useEffect(() => {
    loadDepartments();
    loadAvailableJobs();
  }, [connectorId]);

  // Update filtered jobs when department changes
  React.useEffect(() => {
    if (params.department_id && availableJobs.length > 0) {
      // Get subordinate department IDs
      const subordinateIds = getSubordinateDepartmentIds(params.department_id);
      // Filter jobs that belong to any of these departments
      const filtered = availableJobs.filter(job => 
        job.department_ids.some(deptId => subordinateIds.includes(deptId))
      );
      setFilteredJobs(filtered);
    } else {
      setFilteredJobs(availableJobs);
    }
  }, [params.department_id, availableJobs]);

  const loadDepartments = async () => {
    setIsLoadingDepartments(true);
    try {
      const response = await AXIOS_INSTANCE.get(
        `/api/connectors/greenhouse/departments?connector_id=${connectorId}`
      );
      setDepartments(response.data);
    } catch (error) {
      console.error('Failed to load departments:', error);
    } finally {
      setIsLoadingDepartments(false);
    }
  };

  const loadAvailableJobs = async () => {
    setIsLoadingJobs(true);
    try {
      const response = await AXIOS_INSTANCE.get(
        `/api/connectors/greenhouse/jobs?connector_id=${connectorId}`
      );
      setAvailableJobs(response.data);
      setFilteredJobs(response.data);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setIsLoadingJobs(false);
    }
  };

  const getSubordinateDepartmentIds = (parentId: number): number[] => {
    const result = [parentId];
    const findChildren = (id: number) => {
      const dept = departments.find(d => d.id === id);
      if (dept && dept.child_ids) {
        for (const childId of dept.child_ids) {
          result.push(childId);
          findChildren(childId);
        }
      }
    };
    findChildren(parentId);
    return result;
  };

  const buildDepartmentTree = (): Department[] => {
    // Return only root departments (no parent)
    return departments.filter(d => !d.parent_id);
  };

  const getChildDepartments = (parentId: number): Department[] => {
    return departments.filter(d => d.parent_id === parentId);
  };

  const handleParamChange = <K extends keyof GreenhouseQueryParams>(
    key: K,
    value: GreenhouseQueryParams[K]
  ) => {
    const newParams = { ...params, [key]: value };
    
    // Clear job selection when department changes
    if (key === 'department_id') {
      newParams.job_ids = '';
    }
    
    setParams(newParams);
    onParamsChange(newParams);
    // Clear test result when params change
    setTestResult(null);
  };

  const handleTestQuery = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const response = await AXIOS_INSTANCE.post('/api/connectors/greenhouse/test-query', {
        connector_id: connectorId,
        query_params: params,
      });

      const result = response.data;
      setTestResult({
        success: true,
        job_count: result.job_count,
        candidate_count: result.candidate_count,
        message: result.message,
      });
    } catch (error: any) {
      console.error('Test query failed:', error);
      
      let errorMessage = 'Failed to test query. Please try again.';
      
      if (error?.response?.status === 401) {
        errorMessage = error?.response?.data?.detail || 
          '❌ Invalid Greenhouse API Key. Please go to Data Connections and verify your API key is correct.';
      } else if (error?.response?.status === 403) {
        errorMessage = error?.response?.data?.detail || 
          '⚠️ API Key Missing Permissions. Your Greenhouse API key needs read access to Jobs and Candidates.';
      } else if (error?.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error?.message) {
        errorMessage = error.message;
      }
      
      setTestResult({
        success: false,
        message: errorMessage,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const canContinue = testResult?.success && (testResult.candidate_count || 0) > 0;

  // Recursive department tree component
  const DepartmentNode = ({ dept, level = 0 }: { dept: Department; level?: number }) => {
    const [isExpanded, setIsExpanded] = useState(true);
    const children = getChildDepartments(dept.id);
    const hasChildren = children.length > 0;
    const isSelected = params.department_id === dept.id;
    const jobCount = availableJobs.filter(j => j.department_ids.includes(dept.id)).length;

    return (
      <div className="select-none">
        <div
          className={`
            flex items-center gap-2 py-2 px-3 rounded-lg cursor-pointer transition-colors
            ${isSelected 
              ? 'bg-brand/20 text-brand border border-brand/30' 
              : 'hover:bg-surface-2'
            }
          `}
          style={{ marginLeft: level * 16 }}
          onClick={() => handleParamChange('department_id', isSelected ? undefined : dept.id)}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
              className="p-0.5 hover:bg-surface-3 rounded"
            >
              {isExpanded ? (
                <ChevronDownIcon className="w-4 h-4 text-muted" />
              ) : (
                <ChevronRightIcon className="w-4 h-4 text-muted" />
              )}
            </button>
          ) : (
            <div className="w-5" />
          )}
          <BuildingOfficeIcon className="w-4 h-4 text-muted flex-shrink-0" />
          <span className="flex-1 text-sm font-medium">{dept.name}</span>
          {jobCount > 0 && (
            <span className="text-xs text-muted bg-surface-3 px-2 py-0.5 rounded-full">
              {jobCount} job{jobCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        {hasChildren && isExpanded && (
          <div>
            {children.map(child => (
              <DepartmentNode key={child.id} dept={child} level={level + 1} />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <FunnelIcon className="w-6 h-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-foreground mb-2">
            Configure Greenhouse Search
          </h2>
          <p className="text-sm text-muted">
            Filter candidates by department or specific jobs. Test your query to see how many
            candidates match before running the full analysis.
          </p>
        </div>
      </div>

      {/* Filter Mode Toggle */}
      <div className="bg-surface rounded-lg border border-border p-4">
        <div className="flex items-center gap-4 mb-4">
          <span className="text-sm font-medium text-text">Filter by:</span>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setFilterMode('department');
                handleParamChange('job_ids', '');
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterMode === 'department'
                  ? 'bg-brand text-on-brand'
                  : 'bg-surface-2 text-muted hover:bg-surface-3'
              }`}
            >
              Department
            </button>
            <button
              onClick={() => {
                setFilterMode('job');
                handleParamChange('department_id', undefined);
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterMode === 'job'
                  ? 'bg-brand text-on-brand'
                  : 'bg-surface-2 text-muted hover:bg-surface-3'
              }`}
            >
              Specific Jobs
            </button>
          </div>
        </div>

        {filterMode === 'department' ? (
          <div>
            <p className="text-xs text-muted mb-3">
              Select a department to include all jobs in that department and its sub-departments.
            </p>
            {isLoadingDepartments ? (
              <div className="flex items-center gap-2 text-muted text-sm py-4">
                <LoadingSpinner size="sm" />
                <span>Loading departments...</span>
              </div>
            ) : departments.length > 0 ? (
              <div className="max-h-64 overflow-y-auto border border-border rounded-lg p-2 bg-bg">
                {buildDepartmentTree().map(dept => (
                  <DepartmentNode key={dept.id} dept={dept} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted py-4">No departments found.</p>
            )}
            {params.department_id && (
              <div className="mt-3 p-3 bg-brand/10 rounded-lg">
                <p className="text-sm text-brand">
                  <strong>Selected:</strong> {departments.find(d => d.id === params.department_id)?.name}
                  <br />
                  <span className="text-xs">
                    Includes {getSubordinateDepartmentIds(params.department_id).length} department(s) 
                    and {filteredJobs.length} job(s)
                  </span>
                </p>
              </div>
            )}
          </div>
        ) : (
          <div>
            <p className="text-xs text-muted mb-3">
              Select specific jobs to include in the search.
            </p>
            {isLoadingJobs ? (
              <div className="flex items-center gap-2 text-muted text-sm py-4">
                <LoadingSpinner size="sm" />
                <span>Loading jobs...</span>
              </div>
            ) : availableJobs.length > 0 ? (
              <div className="space-y-2">
                <select
                  multiple
                  className="w-full px-4 py-2 border border-border rounded-lg bg-bg text-text focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent h-40"
                  value={params.job_ids?.split(',').filter(Boolean) || []}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, option => option.value);
                    handleParamChange('job_ids', selected.join(','));
                  }}
                >
                  {availableJobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.name} • {job.departments.join(', ') || 'No department'}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted">
                  Hold Cmd/Ctrl to select multiple jobs. Leave empty to search all jobs.
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted py-4">No open jobs found.</p>
            )}
          </div>
        )}
      </div>

      {/* Additional Filters */}
      <div className="bg-surface rounded-lg border border-border p-6 space-y-6">
        <h3 className="text-sm font-semibold text-text">Additional Filters</h3>
        
        {/* Application Status */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Application Status
          </label>
          <select
            value={params.application_status || ''}
            onChange={(e) => handleParamChange('application_status', e.target.value as any)}
            className="w-full px-4 py-2 border border-border rounded-lg bg-bg text-text focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="rejected">Rejected</option>
            <option value="hired">Hired</option>
          </select>
          <p className="mt-1 text-xs text-muted">
            Filter candidates by their current application status
          </p>
        </div>

        {/* Date Range */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Created After (Optional)
          </label>
          <input
            type="date"
            value={params.created_after || ''}
            onChange={(e) => handleParamChange('created_after', e.target.value)}
            className="w-full px-4 py-2 border border-border rounded-lg bg-bg text-text focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
          />
          <p className="mt-1 text-xs text-muted">
            Only include candidates created after this date
          </p>
        </div>

        {/* Max Candidates */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Maximum Candidates
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="1"
              max="1000"
              step="10"
              value={params.max_candidates || 50}
              onChange={(e) => handleParamChange('max_candidates', parseInt(e.target.value))}
              className="flex-1"
            />
            <span className="text-sm font-medium text-text w-16 text-right">
              {params.max_candidates}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted">
            Maximum number of candidates to fetch (1-1000). Higher numbers increase processing time.
          </p>
        </div>
      </div>

      {/* Test Query Button */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleTestQuery}
          disabled={isTesting}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-info text-white hover:bg-info/80 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isTesting ? (
            <>
              <LoadingSpinner size="sm" />
              <span>Testing Query...</span>
            </>
          ) : (
            <>
              <MagnifyingGlassIcon className="w-4 h-4" />
              <span>Test Query</span>
            </>
          )}
        </button>

        <div className="text-sm text-muted">
          See how many candidates match your filters before running analysis
        </div>
      </div>

      {/* Test Results */}
      {testResult && (
        <div
          className={`p-4 rounded-lg border ${
            testResult.success
              ? 'bg-success/10 border-success/30'
              : 'bg-error/10 border-error/30'
          }`}
        >
          <div className="flex items-start gap-3">
            {testResult.success ? (
              <CheckCircleIcon className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
            ) : (
              <XCircleIcon className="w-5 h-5 text-error flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className="font-medium text-foreground mb-1">
                {testResult.success ? 'Query Test Successful' : 'Query Test Failed'}
              </p>
              {testResult.success && (
                <div className="space-y-1 text-sm text-muted">
                  <p>
                    <span className="font-semibold text-foreground">{testResult.job_count || 0}</span>{' '}
                    jobs found
                  </p>
                  <p>
                    <span className="font-semibold text-foreground">{testResult.candidate_count || 0}</span>{' '}
                    candidates match your filters
                  </p>
                  {(testResult.candidate_count || 0) > 0 && (
                    <p className="mt-2 text-success">
                      ✓ Ready to run analysis on these candidates
                    </p>
                  )}
                  {(testResult.candidate_count || 0) === 0 && (
                    <p className="mt-2 text-warning">
                      ⚠️ No candidates found. Try adjusting your filters.
                    </p>
                  )}
                </div>
              )}
              {testResult.message && !testResult.success && (
                <div className="space-y-2">
                  <p className="text-sm text-error leading-relaxed whitespace-pre-line">
                    {testResult.message}
                  </p>
                  {testResult.message.includes('Invalid Greenhouse API Key') && (
                    <a
                      href="/data-connections"
                      className="inline-flex items-center gap-1 text-sm text-brand hover:text-brand-strong underline"
                    >
                      → Go to Data Connections to update API key
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-end gap-3">
        <button
          onClick={onBack}
          className="px-5 py-2.5 rounded-lg border border-border text-text hover:bg-surface-2 transition-colors text-sm font-medium"
        >
          Back
        </button>
        <button
          onClick={onContinue}
          disabled={!canContinue}
          className="px-6 py-2.5 rounded-lg bg-brand text-on-brand hover:bg-brand-hover transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {canContinue ? 'Continue to Analysis' : 'Test Query First'}
        </button>
      </div>
    </div>
  );
}

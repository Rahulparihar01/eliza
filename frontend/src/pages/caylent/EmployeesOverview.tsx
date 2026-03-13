/**
 * Caylent Employees Overview Page
 * 
 * Executive dashboard for viewing HR data summaries and insights
 * Following the Linear-style design system from UX specification.
 */

import React, { useState } from 'react';
import { Layout } from '../../components/layout/Layout';
import {
  UsersIcon,
  BriefcaseIcon,
  AcademicCapIcon,
  ChartBarIcon,
  TableCellsIcon,
  ArrowTrendingUpIcon,
  BuildingOfficeIcon,
  MapPinIcon,
  XMarkIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import {
  useGetEmployeeOverviewSummaryV1HrSummariesEmployeeOverviewGet,
  useGetSkillsCompetenciesSummaryV1HrSummariesSkillsCompetenciesGet,
  useGetPerformanceDevelopmentSummaryV1HrSummariesPerformanceDevelopmentGet,
  useGetHrTablesListV1HrTablesGet,
} from '../../generated/hr/hr';
import { AXIOS_INSTANCE } from '../../services/api-client';

export default function EmployeesOverview() {
  const [activeView, setActiveView] = useState<'overview' | 'skills' | 'performance' | 'tables'>('overview');
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  // Fetch data from API
  const { data: employeeOverview, isLoading: isLoadingOverview } = useGetEmployeeOverviewSummaryV1HrSummariesEmployeeOverviewGet({ customer_id: 'caylent' });
  const { data: skillsData, isLoading: isLoadingSkills } = useGetSkillsCompetenciesSummaryV1HrSummariesSkillsCompetenciesGet({ customer_id: 'caylent' });
  const { data: performanceData, isLoading: isLoadingPerformance } = useGetPerformanceDevelopmentSummaryV1HrSummariesPerformanceDevelopmentGet({ customer_id: 'caylent' });
  const { data: tablesData, isLoading: isLoadingTables } = useGetHrTablesListV1HrTablesGet({ customer_id: 'caylent' });

  return (
    <Layout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-text">Caylent Employees</h1>
            <p className="text-muted mt-1">
              Executive insights into your workforce data
            </p>
          </div>
        </div>

        {/* View Tabs */}
        <div className="border-b border-border">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveView('overview')}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeView === 'overview'
                  ? 'border-brand text-brand'
                  : 'border-transparent text-muted hover:text-text hover:border-border-strong'
                }
              `}
            >
              <div className="flex items-center space-x-2">
                <UsersIcon className="h-5 w-5" />
                <span>Employee Overview</span>
              </div>
            </button>
            
            <button
              onClick={() => setActiveView('skills')}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeView === 'skills'
                  ? 'border-brand text-brand'
                  : 'border-transparent text-muted hover:text-text hover:border-border-strong'
                }
              `}
            >
              <div className="flex items-center space-x-2">
                <AcademicCapIcon className="h-5 w-5" />
                <span>Skills & Competencies</span>
              </div>
            </button>
            
            <button
              onClick={() => setActiveView('performance')}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeView === 'performance'
                  ? 'border-brand text-brand'
                  : 'border-transparent text-muted hover:text-text hover:border-border-strong'
                }
              `}
            >
              <div className="flex items-center space-x-2">
                <ChartBarIcon className="h-5 w-5" />
                <span>Performance & Development</span>
              </div>
            </button>
            
            <button
              onClick={() => setActiveView('tables')}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeView === 'tables'
                  ? 'border-brand text-brand'
                  : 'border-transparent text-muted hover:text-text hover:border-border-strong'
                }
              `}
            >
              <div className="flex items-center space-x-2">
                <TableCellsIcon className="h-5 w-5" />
                <span>All HR Tables</span>
              </div>
            </button>
          </nav>
        </div>

        {/* View Content */}
        <div className="mt-6">
          {activeView === 'overview' && <EmployeeOverviewView data={employeeOverview} isLoading={isLoadingOverview} />}
          {activeView === 'skills' && <SkillsCompetenciesView data={skillsData} isLoading={isLoadingSkills} />}
          {activeView === 'performance' && <PerformanceDevelopmentView data={performanceData} isLoading={isLoadingPerformance} />}
          {activeView === 'tables' && <AllTablesView data={tablesData} isLoading={isLoadingTables} onTableClick={setSelectedTable} />}
        </div>
      </div>

      {/* Table Detail Modal */}
      {selectedTable && (
        <TableDetailModal
          tableName={selectedTable}
          onClose={() => setSelectedTable(null)}
        />
      )}
    </Layout>
  );
}

// ============================================================================
// Employee Overview View
// ============================================================================

interface EmployeeOverviewViewProps {
  data: any;
  isLoading: boolean;
}

function EmployeeOverviewView({ data, isLoading }: EmployeeOverviewViewProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">Loading employee data...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">No employee data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Total Employees"
          value={data.total_employees?.toString() || '0'}
          icon={<UsersIcon className="h-6 w-6 text-brand" />}
        />
        <KPICard
          title="Active Employees"
          value={data.active_employees?.toString() || '0'}
          icon={<BriefcaseIcon className="h-6 w-6 text-ai-success" />}
        />
        <KPICard
          title="Departments"
          value={data.total_departments?.toString() || '0'}
          icon={<BuildingOfficeIcon className="h-6 w-6 text-ai-purple" />}
        />
        <KPICard
          title="Avg Tenure"
          value={data.avg_tenure_years?.toFixed(1) || '0'}
          icon={<ArrowTrendingUpIcon className="h-6 w-6 text-ai-teal" />}
          suffix=" years"
        />
      </div>

      {/* Employment Status Breakdown */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Employment Type</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard label="Full-Time" value={data.full_time_employees?.toString() || '0'} color="bg-ai-success" />
          <StatusCard label="Part-Time" value={data.part_time_employees?.toString() || '0'} color="bg-ai-info" />
          <StatusCard label="Contractors" value={data.contractor_employees?.toString() || '0'} color="bg-ai-warning" />
        </div>
      </div>

      {/* Work Location Breakdown */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Work Location</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard label="Office" value={data.office_employees?.toString() || '0'} color="bg-dept-engineering" />
          <StatusCard label="Remote" value={data.remote_employees?.toString() || '0'} color="bg-dept-sales" />
          <StatusCard label="Hybrid" value={data.hybrid_employees?.toString() || '0'} color="bg-dept-marketing" />
        </div>
      </div>

      {/* Department Breakdown */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Employees by Department</h3>
        <div className="space-y-3">
          {data.department_breakdown?.map((dept: any) => (
            <div key={dept.department_id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <span className="text-text font-medium">{dept.department_name}</span>
              <span className="text-muted">{dept.employee_count} employees</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Skills & Competencies View
// ============================================================================

interface SkillsCompetenciesViewProps {
  data: any;
  isLoading: boolean;
}

function SkillsCompetenciesView({ data, isLoading }: SkillsCompetenciesViewProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">Loading skills data...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">No skills data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Total Skills"
          value={data.total_skills?.toString() || '0'}
          icon={<AcademicCapIcon className="h-6 w-6 text-brand" />}
        />
        <KPICard
          title="Skill Assignments"
          value={data.total_skill_assignments?.toString() || '0'}
          icon={<ChartBarIcon className="h-6 w-6 text-ai-success" />}
        />
        <KPICard
          title="Expert Level"
          value={data.expert_level_skills?.toString() || '0'}
          icon={<ArrowTrendingUpIcon className="h-6 w-6 text-ai-purple" />}
        />
        <KPICard
          title="Avg Experience"
          value={data.avg_years_experience?.toFixed(1) || '0'}
          icon={<BriefcaseIcon className="h-6 w-6 text-ai-teal" />}
          suffix=" years"
        />
      </div>

      {/* Proficiency Distribution */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Proficiency Level Distribution</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatusCard label="Expert" value={data.expert_level_skills?.toString() || '0'} color="bg-ai-success" />
          <StatusCard label="Advanced" value={data.advanced_level_skills?.toString() || '0'} color="bg-ai-info" />
          <StatusCard label="Intermediate" value={data.intermediate_level_skills?.toString() || '0'} color="bg-ai-warning" />
          <StatusCard label="Beginner" value={data.beginner_level_skills?.toString() || '0'} color="bg-muted" />
        </div>
      </div>

      {/* Skills by Category */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Skills by Category</h3>
        <div className="space-y-3">
          {data.category_breakdown?.map((category: any) => (
            <div key={category.category} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <span className="text-text font-medium">{category.category}</span>
              <span className="text-muted">{category.skill_count} skills</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Performance & Development View
// ============================================================================

interface PerformanceDevelopmentViewProps {
  data: any;
  isLoading: boolean;
}

function PerformanceDevelopmentView({ data, isLoading }: PerformanceDevelopmentViewProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">Loading performance data...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">No performance data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KPICard
          title="Avg Rating"
          value={data.avg_performance_rating?.toFixed(1) || '0'}
          icon={<ChartBarIcon className="h-6 w-6 text-brand" />}
          suffix="/5.0"
        />
        <KPICard
          title="Ready for Promotion"
          value={data.promotion_ready_employees?.toString() || '0'}
          icon={<ArrowTrendingUpIcon className="h-6 w-6 text-ai-success" />}
        />
        <KPICard
          title="Training Completed"
          value={data.completed_trainings?.toString() || '0'}
          icon={<AcademicCapIcon className="h-6 w-6 text-ai-purple" />}
        />
        <KPICard
          title="Goals Achievement"
          value={data.avg_goals_achievement_rate?.toFixed(0) || '0'}
          icon={<BriefcaseIcon className="h-6 w-6 text-ai-teal" />}
          suffix="%"
        />
      </div>

      {/* Promotion Readiness */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Promotion Readiness</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard label="Ready Now" value={data.promotion_ready_employees?.toString() || '0'} color="bg-ai-success" />
          <StatusCard label="Ready in 6 Months" value={data.promotion_ready_6_months?.toString() || '0'} color="bg-ai-info" />
          <StatusCard label="Ready in 12 Months" value={data.promotion_ready_12_months?.toString() || '0'} color="bg-ai-warning" />
        </div>
      </div>

      {/* Training Status */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Training Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StatusCard label="Completed" value={data.completed_trainings?.toString() || '0'} color="bg-ai-success" />
          <StatusCard label="In Progress" value={data.in_progress_trainings?.toString() || '0'} color="bg-ai-info" />
          <StatusCard label="Enrolled" value={data.enrolled_trainings?.toString() || '0'} color="bg-ai-warning" />
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// All Tables View
// ============================================================================

interface AllTablesViewProps {
  data: any;
  isLoading: boolean;
  onTableClick: (tableName: string) => void;
}

function AllTablesView({ data, isLoading, onTableClick }: AllTablesViewProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">Loading tables data...</div>
      </div>
    );
  }

  if (!data || !data.tables) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted">No tables data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-surface border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text mb-4">Available HR Tables</h3>
        <p className="text-muted text-sm mb-4">
          Browse all HR data tables in the system ({data.tables.length} tables)
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.tables.map((table: any) => (
            <button
              key={table.table_name}
              onClick={() => onTableClick(table.table_name)}
              className="bg-background border border-border rounded-lg p-4 hover:border-brand hover:shadow-md transition-all text-left w-full"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="text-text font-medium mb-1">{table.display_name || table.table_name}</h4>
                  <p className="text-muted text-sm mb-2">{table.description}</p>
                  <div className="flex items-center space-x-4 text-xs text-muted">
                    <span>{table.record_count} rows</span>
                  </div>
                </div>
                <TableCellsIcon className="h-5 w-5 text-brand flex-shrink-0 ml-2" />
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Reusable Components
// ============================================================================

interface KPICardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: { value: string; direction: 'up' | 'down' };
  suffix?: string;
}

function KPICard({ title, value, icon, trend, suffix = '' }: KPICardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-muted">{title}</span>
        {icon}
      </div>
      <div className="flex items-baseline space-x-2">
        <span className="text-3xl font-semibold text-text">{value}{suffix}</span>
        {trend && (
          <span className={`text-sm font-medium ${trend.direction === 'up' ? 'text-ai-success' : 'text-ai-danger'}`}>
            {trend.value}
          </span>
        )}
      </div>
    </div>
  );
}

interface StatusCardProps {
  label: string;
  value: string | number;
  color: string;
}

function StatusCard({ label, value, color }: StatusCardProps) {
  return (
    <div className="flex items-center space-x-3 p-4 bg-surface-2 rounded-lg">
      <div className={`w-3 h-3 rounded-full ${color}`} />
      <div className="flex-1">
        <p className="text-sm text-muted">{label}</p>
        <p className="text-lg font-semibold text-text">{value}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Table Detail Modal
// ============================================================================

interface TableDetailModalProps {
  tableName: string;
  onClose: () => void;
}

function TableDetailModal({ tableName, onClose }: TableDetailModalProps) {
  const [tableData, setTableData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const pageSize = 50;

  // Fetch table data
  React.useEffect(() => {
    const fetchTableData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await AXIOS_INSTANCE.get(
          `/v1/hr/tables/${tableName}/data`,
          {
            params: {
              customer_id: 'caylent',
              limit: pageSize,
              offset: currentPage * pageSize,
            },
          }
        );
        setTableData(response.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load table data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchTableData();
  }, [tableName, currentPage]);

  const totalPages = tableData ? Math.ceil(tableData.total_count / pageSize) : 0;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-lg shadow-xl max-w-7xl w-full max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div>
            <h2 className="text-xl font-semibold text-text">{tableName}</h2>
            {tableData && (
              <p className="text-sm text-muted mt-1">
                {tableData.total_count} total records
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-2 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-muted" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-auto p-6">
          {isLoading && (
            <div className="flex items-center justify-center h-64">
              <div className="text-muted">Loading table data...</div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-64">
              <div className="text-ai-danger">{error}</div>
            </div>
          )}

          {tableData && !isLoading && !error && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-surface-2">
                  <tr>
                    {tableData.columns.map((column: string) => (
                      <th
                        key={column}
                        className="px-4 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider whitespace-nowrap"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-background divide-y divide-border">
                  {tableData.data.map((row: any, rowIndex: number) => (
                    <tr key={rowIndex} className="hover:bg-surface-2 transition-colors">
                      {tableData.columns.map((column: string) => (
                        <td
                          key={column}
                          className="px-4 py-3 text-sm text-text whitespace-nowrap"
                        >
                          {row[column] !== null && row[column] !== undefined
                            ? String(row[column])
                            : '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal Footer with Pagination */}
        {tableData && !isLoading && !error && totalPages > 1 && (
          <div className="flex items-center justify-between p-6 border-t border-border">
            <div className="text-sm text-muted">
              Showing {currentPage * pageSize + 1} to{' '}
              {Math.min((currentPage + 1) * pageSize, tableData.total_count)} of{' '}
              {tableData.total_count} records
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0}
                className="p-2 hover:bg-surface-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeftIcon className="h-5 w-5 text-muted" />
              </button>
              <span className="text-sm text-text">
                Page {currentPage + 1} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
                disabled={currentPage >= totalPages - 1}
                className="p-2 hover:bg-surface-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRightIcon className="h-5 w-5 text-muted" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


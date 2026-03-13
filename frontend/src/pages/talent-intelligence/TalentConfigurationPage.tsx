/**
 * Talent Configuration Page
 * 
 * Unified configuration for:
 * - Career Blueprints (reusable candidate patterns from look-alikes)
 * - Company DNA (organizational hiring patterns by company + role)
 * 
 * Migrated to DS components (Jan 2026).
 */

import React, { useState, useEffect } from 'react';
import {
  FingerPrintIcon,
  BuildingOfficeIcon,
  PlusIcon,
  TrashIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  UserGroupIcon,
  BeakerIcon,
  AcademicCapIcon,
} from '@heroicons/react/24/outline';
import {
  Page,
  PageHeader,
  PageBody,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Badge,
  Spinner,
  Alert,
  Button,
  SectionHeader,
  DataTable,
  DataTableActions,
  DataTableActionButton,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  Input,
  Label,
  Select,
  SelectOption,
  Progress,
} from '../../components/ui';
import type { Column } from '../../components/ui';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Types
interface CareerBlueprint {
  id: number;
  customer_id: string;
  name: string;
  description?: string;
  role_category?: string;
  source_linkedin_urls: string[];
  source_profile_count: number;
  skill_profile?: {
    core_skills?: string[];
    common_skills?: string[];
    skill_frequencies?: Record<string, number>;
  };
  experience_profile?: {
    avg_years?: number;
    min_years?: number;
    max_years?: number;
    avg_role_count?: number;
  };
  company_progression?: {
    common_companies?: string[];
    industries?: string[];
  };
  role_progression?: {
    common_titles?: string[];
    pattern?: string;
  };
  scoring_weights?: Record<string, number>;
  is_active: boolean;
  usage_count: number;
  last_used_at?: string;
  created_at?: string;
  updated_at?: string;
}

interface CompanyDNA {
  id: number;
  customer_id: string;
  company_name: string;
  role_category: string;
  time_window_months: number;
  employee_count_analyzed: number;
  workforce_dna?: {
    avg_experience_years?: number;
    experience_distribution?: Record<string, number>;
    skill_profile?: {
      core_skills?: string[];
      skill_frequencies?: Record<string, number>;
    };
    common_backgrounds?: {
      faang_alumni_rate?: number;
      consulting_background_rate?: number;
      common_previous_companies?: [string, number][];
    };
  };
  culture_indicators?: {
    pace?: string;
    technical_depth?: string;
    remote_friendly?: boolean;
  };
  success_patterns?: {
    common_previous_companies?: string[];
    common_previous_roles?: string[];
  };
  hiring_preferences?: Record<string, any>;
  is_active: boolean;
  is_default: boolean;
  last_analyzed_at?: string;
  created_at?: string;
}

interface RoleCategory {
  id: string;
  name: string;
  description: string;
}

type TabType = 'blueprints' | 'company-dna';

export default function TalentConfigurationPage() {
  const [activeTab, setActiveTab] = useState<TabType>('blueprints');
  const [blueprints, setBlueprints] = useState<CareerBlueprint[]>([]);
  const [companyDNA, setCompanyDNA] = useState<CompanyDNA[]>([]);
  const [roleCategories, setRoleCategories] = useState<RoleCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal states
  const [showBlueprintDetail, setShowBlueprintDetail] = useState<CareerBlueprint | null>(null);
  const [showDNADetail, setShowDNADetail] = useState<CompanyDNA | null>(null);
  const [showCreateDNA, setShowCreateDNA] = useState(false);
  const [isCreatingDNA, setIsCreatingDNA] = useState(false);
  
  // Create DNA form
  const [newDNAForm, setNewDNAForm] = useState({
    company_name: '',
    role_category: 'engineering',
    time_window_months: 24,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const [blueprintsRes, dnaRes, categoriesRes] = await Promise.all([
        AXIOS_INSTANCE.get('/api/v1/talent-config/blueprints'),
        AXIOS_INSTANCE.get('/api/v1/talent-config/company-dna'),
        AXIOS_INSTANCE.get('/api/v1/talent-config/role-categories'),
      ]);
      
      setBlueprints(blueprintsRes.data.blueprints || []);
      
      setCompanyDNA(dnaRes.data.profiles || []);
      setRoleCategories(categoriesRes.data.categories || []);
    } catch (err: any) {
      console.error('Failed to load configuration:', err);
      setError(err.response?.data?.detail || 'Failed to load configuration');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteBlueprint = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this blueprint?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/talent-config/blueprints/${id}`);
      setBlueprints(prev => prev.filter(b => b.id !== id));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete blueprint');
    }
  };

  const handleDeleteDNA = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this DNA profile?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/talent-config/company-dna/${id}`);
      setCompanyDNA(prev => prev.filter(d => d.id !== id));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete DNA profile');
    }
  };

  const handleCreateDNA = async () => {
    if (!newDNAForm.company_name.trim()) {
      setError('Company name is required');
      return;
    }
    
    setIsCreatingDNA(true);
    setError(null);
    
    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/talent-config/company-dna', newDNAForm);
      setCompanyDNA(prev => [response.data, ...prev]);
      setShowCreateDNA(false);
      setNewDNAForm({ company_name: '', role_category: 'engineering', time_window_months: 24 });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create DNA profile');
    } finally {
      setIsCreatingDNA(false);
    }
  };

  const handleRefreshDNA = async (dna: CompanyDNA) => {
    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/talent-config/company-dna', {
        company_name: dna.company_name,
        role_category: dna.role_category,
        time_window_months: dna.time_window_months,
      });
      setCompanyDNA(prev => prev.map(d => d.id === dna.id ? response.data : d));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to refresh DNA profile');
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // Loading state with DS Spinner
  if (isLoading) {
    return (
      <Page layout="centered" maxWidth="2xl">
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" />
        </div>
      </Page>
    );
  }

  return (
    <Page layout="centered" maxWidth="2xl">
      <PageHeader
        title="Talent Configuration"
        description="Manage career blueprints and company DNA profiles for intelligent candidate matching"
      />
      
      <PageBody>
        {/* Error Banner - DS Alert */}
        {error && (
          <div className="mb-6">
            <Alert variant="error" onDismiss={() => setError(null)}>
              {error}
            </Alert>
          </div>
        )}

        {/* DS Tabs */}
        <Tabs defaultValue="blueprints" value={activeTab} onValueChange={(v) => setActiveTab(v as TabType)}>
          <TabsList className="mb-6">
            <TabsTrigger value="blueprints">
              <FingerPrintIcon className="w-4 h-4 mr-2" />
              Career Blueprints
              <Badge variant="default" className="ml-2">
                {blueprints.length}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="company-dna">
              <BuildingOfficeIcon className="w-4 h-4 mr-2" />
              Company DNA
              <Badge variant="default" className="ml-2">
                {companyDNA.length}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="blueprints">
            <BlueprintsSection
              blueprints={blueprints}
              onView={setShowBlueprintDetail}
              onDelete={handleDeleteBlueprint}
              formatDate={formatDate}
            />
          </TabsContent>

          <TabsContent value="company-dna">
            <CompanyDNASection
              profiles={companyDNA}
              roleCategories={roleCategories}
              onView={setShowDNADetail}
              onDelete={handleDeleteDNA}
              onRefresh={handleRefreshDNA}
              onCreate={() => setShowCreateDNA(true)}
              formatDate={formatDate}
            />
          </TabsContent>
        </Tabs>
      </PageBody>

      {/* Blueprint Detail Modal */}
      {showBlueprintDetail && (
        <BlueprintDetailModal
          blueprint={showBlueprintDetail}
          onClose={() => setShowBlueprintDetail(null)}
        />
      )}

      {/* DNA Detail Modal */}
      {showDNADetail && (
        <DNADetailModal
          dna={showDNADetail}
          onClose={() => setShowDNADetail(null)}
        />
      )}

      {/* Create DNA Modal */}
      {showCreateDNA && (
        <CreateDNAModal
          form={newDNAForm}
          roleCategories={roleCategories}
          isCreating={isCreatingDNA}
          onChange={setNewDNAForm}
          onCreate={handleCreateDNA}
          onClose={() => setShowCreateDNA(false)}
        />
      )}
    </Page>
  );
}

// Blueprints Section - Uses DS DataTable
function BlueprintsSection({
  blueprints,
  onView,
  onDelete,
}: {
  blueprints: CareerBlueprint[];
  onView: (b: CareerBlueprint) => void;
  onDelete: (id: number) => void;
  formatDate: (d?: string) => string;
}) {
  // DataTable columns definition
  const columns: Column<CareerBlueprint>[] = [
    {
      id: 'name',
      header: 'Blueprint',
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-eliza-red/10 flex items-center justify-center">
            <FingerPrintIcon className="w-4 h-4 text-eliza-red" />
          </div>
          <div>
            <div className="font-medium text-sm text-charcoal dark:text-gray-100">{row.name}</div>
            {row.description && (
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-xs">
                {row.description}
              </div>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'role_category',
      header: 'Role Category',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400 capitalize">
          {row.role_category || '—'}
        </span>
      ),
    },
    {
      id: 'profiles',
      header: 'Profiles',
      cell: ({ row }) => (
        <div className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
          <UserGroupIcon className="w-4 h-4" />
          {row.source_profile_count}
        </div>
      ),
    },
    {
      id: 'skills',
      header: 'Core Skills',
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {(row.skill_profile?.core_skills || []).slice(0, 3).map((skill) => (
            <Badge key={skill} variant="default">
              {skill}
            </Badge>
          ))}
          {(row.skill_profile?.core_skills?.length || 0) > 3 && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              +{(row.skill_profile?.core_skills?.length || 0) - 3}
            </span>
          )}
        </div>
      ),
    },
    {
      id: 'usage',
      header: 'Usage',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {row.usage_count} uses
        </span>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: ({ row }) => (
        row.is_active ? (
          <Badge variant="success">
            <CheckCircleIcon className="w-3 h-3 mr-1" />
            Active
          </Badge>
        ) : (
          <Badge variant="default">
            <XCircleIcon className="w-3 h-3 mr-1" />
            Inactive
          </Badge>
        )
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      cell: ({ row }) => (
        <DataTableActions>
          <DataTableActionButton
            icon={<TrashIcon className="w-4 h-4" />}
            label="Delete Blueprint"
            onClick={() => onDelete(row.id)}
            variant="danger"
          />
        </DataTableActions>
      ),
    },
  ];

  // Empty state with DS colors
  if (blueprints.length === 0) {
    return (
      <div className="text-center py-16">
        <FingerPrintIcon className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
        <h3 className="mt-4 text-lg font-medium text-charcoal dark:text-gray-100">No Career Blueprints</h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
          Career blueprints are created during the talent analysis flow when you provide 
          LinkedIn profiles of ideal candidates.
        </p>
      </div>
    );
  }

  return (
    <DataTable
      columns={columns}
      data={blueprints}
      getRowId={(row) => row.id}
      onRowClick={onView}
    />
  );
}

// Company DNA Section - Uses DS DataTable
function CompanyDNASection({
  profiles,
  onView,
  onDelete,
  onRefresh,
  onCreate,
  formatDate,
}: {
  profiles: CompanyDNA[];
  roleCategories: RoleCategory[];
  onView: (d: CompanyDNA) => void;
  onDelete: (id: number) => void;
  onRefresh: (d: CompanyDNA) => void;
  onCreate: () => void;
  formatDate: (d?: string) => string;
}) {
  // DataTable columns definition
  const columns: Column<CompanyDNA>[] = [
    {
      id: 'company',
      header: 'Company / Role',
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-dark-surface-2 flex items-center justify-center">
            <BuildingOfficeIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          </div>
          <div>
            <div className="font-medium text-sm text-charcoal dark:text-gray-100 capitalize">{row.company_name}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">{row.role_category}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'employees',
      header: 'Employees Analyzed',
      cell: ({ row }) => (
        <div className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
          <UserGroupIcon className="w-4 h-4" />
          {row.employee_count_analyzed}
        </div>
      ),
    },
    {
      id: 'experience',
      header: 'Avg Experience',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {row.workforce_dna?.avg_experience_years?.toFixed(1) || '—'} years
        </span>
      ),
    },
    {
      id: 'skills',
      header: 'Core Skills',
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {(row.workforce_dna?.skill_profile?.core_skills || []).slice(0, 3).map((skill) => (
            <Badge key={skill} variant="default">
              {skill}
            </Badge>
          ))}
          {(row.workforce_dna?.skill_profile?.core_skills?.length || 0) > 3 && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              +{(row.workforce_dna?.skill_profile?.core_skills?.length || 0) - 3}
            </span>
          )}
        </div>
      ),
    },
    {
      id: 'last_analyzed',
      header: 'Last Analyzed',
      cell: ({ row }) => (
        <div className="flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
          <ClockIcon className="w-4 h-4" />
          {formatDate(row.last_analyzed_at)}
        </div>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: ({ row }) => (
        row.is_active ? (
          <Badge variant="success">
            <CheckCircleIcon className="w-3 h-3 mr-1" />
            Active
          </Badge>
        ) : (
          <Badge variant="default">
            <XCircleIcon className="w-3 h-3 mr-1" />
            Inactive
          </Badge>
        )
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      cell: ({ row }) => (
        <DataTableActions>
          <DataTableActionButton
            icon={<ArrowPathIcon className="w-4 h-4" />}
            label="Refresh DNA"
            onClick={() => onRefresh(row)}
          />
          <DataTableActionButton
            icon={<TrashIcon className="w-4 h-4" />}
            label="Delete"
            onClick={() => onDelete(row.id)}
            variant="danger"
          />
        </DataTableActions>
      ),
    },
  ];

  return (
    <div>
      {/* DS SectionHeader with Create Button */}
      <SectionHeader
        title="Company DNA Profiles"
        description="Organizational hiring patterns scoped by company and role category"
        actions={
          <Button onClick={onCreate}>
            <PlusIcon className="w-4 h-4 mr-2" />
            Create DNA Profile
          </Button>
        }
        className="mb-6"
      />

      {/* Empty state with DS colors */}
      {profiles.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-200 dark:border-dark-border rounded-lg">
          <BuildingOfficeIcon className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500" />
          <h3 className="mt-4 text-lg font-medium text-charcoal dark:text-gray-100">No Company DNA Profiles</h3>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto">
            Create a DNA profile to analyze workforce patterns and improve candidate matching.
          </p>
          <Button onClick={onCreate} className="mt-6">
            <PlusIcon className="w-4 h-4 mr-2" />
            Create First Profile
          </Button>
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={profiles}
          getRowId={(row) => row.id}
          onRowClick={onView}
        />
      )}
    </div>
  );
}

// Blueprint Detail Modal - DS Modal components
function BlueprintDetailModal({
  blueprint,
  onClose,
}: {
  blueprint: CareerBlueprint;
  onClose: () => void;
}) {
  return (
    <Modal open onClose={onClose}>
      <ModalBackdrop />
      <ModalContent size="lg">
        <ModalHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-eliza-red/10 flex items-center justify-center">
              <FingerPrintIcon className="w-5 h-5 text-eliza-red" />
            </div>
            <div>
              <ModalTitle>{blueprint.name}</ModalTitle>
              <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">{blueprint.role_category || 'General'}</p>
            </div>
          </div>
        </ModalHeader>

        <ModalBody className="space-y-6">
          {blueprint.description && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{blueprint.description}</p>
          )}

          {/* Source Profiles */}
          <div>
            <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2 flex items-center gap-2">
              <UserGroupIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
              Source Profiles ({blueprint.source_profile_count})
            </h3>
            <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
              {blueprint.source_linkedin_urls.slice(0, 5).map((url, i) => (
                <div key={i} className="truncate">{url}</div>
              ))}
              {blueprint.source_linkedin_urls.length > 5 && (
                <div>+{blueprint.source_linkedin_urls.length - 5} more</div>
              )}
            </div>
          </div>

          {/* Skill Profile */}
          {blueprint.skill_profile && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2 flex items-center gap-2">
                <BeakerIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                Skill Profile
              </h3>
              <div className="space-y-2">
                <div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">Core Skills:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {blueprint.skill_profile.core_skills?.map((skill) => (
                      <Badge key={skill} variant="brand">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
                {blueprint.skill_profile.common_skills && blueprint.skill_profile.common_skills.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500 dark:text-gray-400">Common Skills:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {blueprint.skill_profile.common_skills.map((skill) => (
                        <Badge key={skill} variant="default">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Experience Profile */}
          {blueprint.experience_profile && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2 flex items-center gap-2">
                <AcademicCapIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                Experience Profile
              </h3>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Average:</span>
                  <span className="ml-2 text-charcoal dark:text-gray-100">{blueprint.experience_profile.avg_years?.toFixed(1)} years</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Range:</span>
                  <span className="ml-2 text-charcoal dark:text-gray-100">
                    {blueprint.experience_profile.min_years}–{blueprint.experience_profile.max_years} years
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Avg Roles:</span>
                  <span className="ml-2 text-charcoal dark:text-gray-100">{blueprint.experience_profile.avg_role_count?.toFixed(1)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Role Progression */}
          {blueprint.role_progression && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Career Progression</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">{blueprint.role_progression.pattern}</p>
              {blueprint.role_progression.common_titles && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {blueprint.role_progression.common_titles.slice(0, 5).map((title) => (
                    <Badge key={title} variant="default">
                      {title}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Company Progression */}
          {blueprint.company_progression?.common_companies && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Common Companies</h3>
              <div className="flex flex-wrap gap-1">
                {blueprint.company_progression.common_companies.slice(0, 10).map((company) => (
                  <Badge key={company} variant="default" className="capitalize">
                    {company}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Scoring Weights */}
          {blueprint.scoring_weights && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Scoring Weights</h3>
              <div className="space-y-3">
                {Object.entries(blueprint.scoring_weights).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-xs text-gray-500 dark:text-gray-400 capitalize w-32">{key.replace(/_/g, ' ')}</span>
                    <Progress value={(value as number) * 100} className="flex-1" />
                    <span className="text-xs text-gray-500 dark:text-gray-400 w-12 text-right">
                      {((value as number) * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}

// DNA Detail Modal - DS Modal components
function DNADetailModal({
  dna,
  onClose,
}: {
  dna: CompanyDNA;
  onClose: () => void;
}) {
  return (
    <Modal open onClose={onClose}>
      <ModalBackdrop />
      <ModalContent size="lg">
        <ModalHeader>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-dark-surface-2 flex items-center justify-center">
              <BuildingOfficeIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            </div>
            <div>
              <ModalTitle className="capitalize">{dna.company_name}</ModalTitle>
              <p className="text-sm text-gray-500 dark:text-gray-400 capitalize">{dna.role_category} • {dna.employee_count_analyzed} employees</p>
            </div>
          </div>
        </ModalHeader>

        <ModalBody className="space-y-6">
          {/* Workforce DNA */}
          {dna.workforce_dna && (
            <>
              <div>
                <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Experience Distribution</h3>
                <div className="grid grid-cols-4 gap-3">
                  {/* Fixed order: 0-2, 3-5, 6-10, 10+ */}
                  {['0-2', '3-5', '6-10', '10+'].map((range) => {
                    const pct = dna.workforce_dna?.experience_distribution?.[range] || 0;
                    return (
                      <div key={range} className="text-center">
                        <div className="text-lg font-semibold text-charcoal dark:text-gray-100">{((pct as number) * 100).toFixed(0)}%</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{range} yrs</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {dna.workforce_dna.skill_profile?.core_skills && (
                <div>
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Core Skills</h3>
                  <div className="flex flex-wrap gap-1">
                    {dna.workforce_dna.skill_profile.core_skills.map((skill) => (
                      <Badge key={skill} variant="success">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {dna.workforce_dna.common_backgrounds && (
                <div>
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Background Patterns</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">FAANG Alumni:</span>
                      <span className="ml-2 text-charcoal dark:text-gray-100">
                        {((dna.workforce_dna.common_backgrounds.faang_alumni_rate || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Consulting Background:</span>
                      <span className="ml-2 text-charcoal dark:text-gray-100">
                        {((dna.workforce_dna.common_backgrounds.consulting_background_rate || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Culture Indicators */}
          {dna.culture_indicators && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Culture Indicators</h3>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Pace:</span>
                  <span className="ml-2 text-charcoal dark:text-gray-100 capitalize">{dna.culture_indicators.pace}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Technical Depth:</span>
                  <span className="ml-2 text-charcoal dark:text-gray-100 capitalize">{dna.culture_indicators.technical_depth}</span>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Remote Friendly:</span>
                  <span className="ml-2 text-charcoal dark:text-gray-100">{dna.culture_indicators.remote_friendly ? 'Yes' : 'No'}</span>
                </div>
              </div>
            </div>
          )}

          {/* Success Patterns */}
          {dna.success_patterns?.common_previous_companies && (
            <div>
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Common Previous Companies</h3>
              <div className="flex flex-wrap gap-1">
                {dna.success_patterns.common_previous_companies.slice(0, 10).map((company) => (
                  <Badge key={company} variant="default" className="capitalize">
                    {company}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}

// DNA form type
interface DNAFormData {
  company_name: string;
  role_category: string;
  time_window_months: number;
}

// Create DNA Modal - DS Modal and form components
function CreateDNAModal({
  form,
  roleCategories,
  isCreating,
  onChange,
  onCreate,
  onClose,
}: {
  form: DNAFormData;
  roleCategories: RoleCategory[];
  isCreating: boolean;
  onChange: (form: DNAFormData) => void;
  onCreate: () => void;
  onClose: () => void;
}) {
  return (
    <Modal open onClose={onClose}>
      <ModalBackdrop />
      <ModalContent size="sm">
        <ModalHeader>
          <ModalTitle>Create Company DNA Profile</ModalTitle>
        </ModalHeader>

        <ModalBody className="space-y-4">
          <div>
            <Label htmlFor="company_name" className="mb-1">Company Name</Label>
            <Input
              id="company_name"
              type="text"
              value={form.company_name}
              onChange={(e) => onChange({ ...form, company_name: e.target.value })}
              placeholder="e.g., caylent"
            />
          </div>

          <div>
            <Label htmlFor="role_category" className="mb-1">Role Category</Label>
            <Select
              value={form.role_category}
              onValueChange={(value) => onChange({ ...form, role_category: value })}
            >
              {roleCategories.map((cat) => (
                <SelectOption key={cat.id} value={cat.id}>
                  {cat.name}
                </SelectOption>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="time_window" className="mb-1">Time Window (months)</Label>
            <Input
              id="time_window"
              type="number"
              value={form.time_window_months}
              onChange={(e) => onChange({ ...form, time_window_months: parseInt(e.target.value) || 24 })}
              min={1}
              max={120}
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Only analyze employees from the last N months</p>
          </div>
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={onCreate}
            disabled={isCreating || !form.company_name.trim()}
          >
            {isCreating && <Spinner size="sm" className="mr-2" />}
            Create Profile
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}






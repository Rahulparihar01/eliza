/**
 * New Analysis Modal
 * 
 * Linear-style modal for creating/editing talent analysis configurations.
 * Features pill buttons with attached dropdowns.
 * LinkedIn enrichment and Company DNA creation appear inline in the main content area.
 * ATS connection drives job description and candidate source options.
 * 
 * Uses Eliza Forge Design System components.
 */

import React, { useState, useEffect } from 'react';
import {
  XMarkIcon,
  CheckIcon,
  ChevronDownIcon,
  PlusIcon,
  SparklesIcon,
  BuildingOfficeIcon,
  DocumentTextIcon,
  ServerStackIcon,
  UserIcon,
  UsersIcon,
  LinkIcon,
  ArrowPathIcon,
  TrashIcon,
  ClockIcon,
  CloudArrowUpIcon,
  BriefcaseIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/solid';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { cn } from '../../shared/lib/cn';

// Design System Components
import {
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  ModalFloatingActions,
  SliderInput,
  Button,
  Alert,
  Spinner,
  Input,
  Textarea,
  Label,
  Checkbox,
  Select,
  SelectOption,
  Chip,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverBody,
  Tabs,
  TabsList,
  TabsTrigger,
} from '../ui';

// Analysis Modal Components
import { AnalysisModalSidebar } from './AnalysisModalSidebar';
import { AnalysisSection, ANALYSIS_SECTIONS, getSectionConfig, REQUIRED_SECTIONS, areRequiredSectionsComplete } from './analysisConfig';

// Types
interface AnalysisConfig {
  id?: number;
  name: string;
  description?: string;
  blueprint_id?: number;
  blueprint_name?: string;
  company_dna_id?: number;
  company_dna_name?: string;
  job_description?: string;
  selected_job_id?: string;  // Backend returns as string
  candidate_source_id?: number;
  candidate_source_name?: string;
  department_ids?: number[];
  candidate_source_mode?: 'ats' | 'upload';
  uploaded_resume_files?: string[];
  ideal_candidate_details?: string;
  market_search_limit?: number;
  max_candidate_fetch?: number;
  include_historical_candidates?: boolean;
  historical_lookback_days?: number;
}

interface Blueprint {
  id: number;
  name: string;
  role_category?: string;
}

interface CompanyDNA {
  id: number;
  company_name: string;
  role_category: string;
}

interface ATSConnection {
  id: number;
  connector_id: string;
  connector_type: string;
  connector_name: string;
  name?: string;  // fallback
  provider_type?: string;
  description?: string;
  is_enabled: boolean;
  is_healthy: boolean;
}

interface ATSJob {
  id: number;
  name: string;
  department?: string;
  status?: string;
}

interface ATSDepartment {
  id: number;
  name: string;
  candidateCount?: number;  // Number of open positions/candidates in this department
}

interface LinkedInProfile {
  url: string;
  status: 'pending' | 'enriching' | 'enriched' | 'error';
  name?: string;
  title?: string;
  company?: string;
  skills?: string[];
  experience?: number;
  cached?: boolean;
  error?: string;
  enrichedData?: any;
}

interface Props {
  config: AnalysisConfig | null;
  onClose: () => void;
  onSave: (shouldRun: boolean) => void;
}

type ActiveDropdown = 'ats' | 'blueprint' | 'dna' | 'job' | 'candidate-source' | 'search-limit' | 'ats-limit' | 'dna-employee-limit' | null;
// ActiveSection is now imported from analysisConfig.ts
type JobDescriptionMode = 'select' | 'upload' | 'paste';
type CandidateSourceMode = 'ats' | 'upload';

interface UploadedResume {
  file: File;
  name: string;
  status: 'pending' | 'uploading' | 'uploaded' | 'error';
  error?: string;
}

const ROLE_CATEGORIES = [
  { value: 'engineering', label: 'Engineering' },
  { value: 'product', label: 'Product' },
  { value: 'design', label: 'Design' },
  { value: 'data', label: 'Data & Analytics' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'sales', label: 'Sales' },
  { value: 'operations', label: 'Operations' },
  { value: 'finance', label: 'Finance' },
  { value: 'hr', label: 'Human Resources' },
  { value: 'other', label: 'Other' },
];

const TIME_WINDOWS = [
  { value: 12, label: '1 year' },
  { value: 24, label: '2 years' },
  { value: 36, label: '3 years' },
  { value: 60, label: '5 years' },
];

export default function NewAnalysisModal({ config, onClose, onSave }: Props) {
  // Form state
  const [name, setName] = useState(config?.name || '');
  const [description, setDescription] = useState(config?.description || '');
  const [blueprintId, setBlueprintId] = useState<number | undefined>(config?.blueprint_id);
  const [blueprintName, setBlueprintName] = useState(config?.blueprint_name || '');
  const [dnaId, setDnaId] = useState<number | undefined>(config?.company_dna_id);
  const [dnaName, setDnaName] = useState(config?.company_dna_name || '');
  const [jobDescription, setJobDescription] = useState(config?.job_description || '');
  const [selectedJobId, setSelectedJobId] = useState<number | undefined>(
    config?.selected_job_id ? parseInt(config.selected_job_id, 10) : undefined
  );
  const [selectedJobName, setSelectedJobName] = useState('');
  
  // Ideal Candidate structured fields
  const parseIdealDetails = (details: string | undefined) => {
    if (!details) return { mustHaves: '', niceToHaves: '', dealbreakers: '', personalityTraits: '', hiringManagerNotes: '' };
    try {
      return JSON.parse(details);
    } catch {
      // Legacy: treat as free-form notes
      return { mustHaves: '', niceToHaves: '', dealbreakers: '', personalityTraits: '', hiringManagerNotes: details };
    }
  };
  const initialIdeal = parseIdealDetails(config?.ideal_candidate_details);
  const [idealMustHaves, setIdealMustHaves] = useState(initialIdeal.mustHaves || '');
  const [idealNiceToHaves, setIdealNiceToHaves] = useState(initialIdeal.niceToHaves || '');
  const [idealDealbreakers, setIdealDealbreakers] = useState(initialIdeal.dealbreakers || '');
  const [idealPersonalityTraits, setIdealPersonalityTraits] = useState(initialIdeal.personalityTraits || '');
  const [idealHiringManagerNotes, setIdealHiringManagerNotes] = useState(initialIdeal.hiringManagerNotes || '');
  
  // Compute serialized ideal details for saving
  const getSerializedIdealDetails = () => {
    const details = {
      mustHaves: idealMustHaves.trim(),
      niceToHaves: idealNiceToHaves.trim(),
      dealbreakers: idealDealbreakers.trim(),
      personalityTraits: idealPersonalityTraits.trim(),
      hiringManagerNotes: idealHiringManagerNotes.trim(),
    };
    // Only return if at least one field has content
    if (Object.values(details).some(v => v)) {
      return JSON.stringify(details);
    }
    return undefined;
  };

  // ATS Connection state
  const [atsConnectionId, setAtsConnectionId] = useState<number | undefined>(config?.candidate_source_id);
  const [atsConnectionName, setAtsConnectionName] = useState(config?.candidate_source_name || '');
  const [atsConnections, setAtsConnections] = useState<ATSConnection[]>([]);
  const [atsJobs, setAtsJobs] = useState<ATSJob[]>([]);
  const [atsDepartments, setAtsDepartments] = useState<ATSDepartment[]>([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState(false);
  const [isLoadingDepartments, setIsLoadingDepartments] = useState(false);
  const [jobSearchQuery, setJobSearchQuery] = useState('');

  // Candidate Source state (department selection or resume upload)
  const [candidateSourceMode, setCandidateSourceMode] = useState<CandidateSourceMode>(config?.candidate_source_mode || 'ats');
  const [selectedDepartmentIds, setSelectedDepartmentIds] = useState<number[]>(config?.department_ids || []);
  const [selectedDepartmentNames, setSelectedDepartmentNames] = useState<string[]>([]);
  const [uploadedResumes, setUploadedResumes] = useState<UploadedResume[]>(
    // Initialize from existing config if available
    (config?.uploaded_resume_files || []).map(name => ({
      file: null as any, // File object not available for existing uploads
      name,
      status: 'uploaded' as const,
    }))
  );
  const [isUploadingResumes, setIsUploadingResumes] = useState(false);
  
  // Market Search Limit
  const [marketSearchLimit, setMarketSearchLimit] = useState<number>(config?.market_search_limit || 50);
  
  // Max Candidate Fetch (from ATS)
  const [maxCandidateFetch, setMaxCandidateFetch] = useState<number>(config?.max_candidate_fetch || 100);
  
  // Historical Candidates (from closed jobs)
  const [includeHistoricalCandidates, setIncludeHistoricalCandidates] = useState<boolean>(config?.include_historical_candidates || false);
  const [historicalLookbackDays, setHistoricalLookbackDays] = useState<number>(config?.historical_lookback_days || 365);

  // UI state
  const [activeDropdown, setActiveDropdown] = useState<ActiveDropdown>(null);
  // Default to 'analysis-setup' for new analyses, null for editing existing
  const [activeSection, setActiveSection] = useState<AnalysisSection | null>(
    config?.id ? null : 'analysis-setup'
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobDescriptionMode, setJobDescriptionMode] = useState<JobDescriptionMode>('select');
  const [isUploadingFile, setIsUploadingFile] = useState(false);

  // Blueprint and DNA section modes (select existing vs create new)
  const [blueprintMode, setBlueprintMode] = useState<'select' | 'create'>(config?.blueprint_id ? 'select' : 'create');
  const [dnaMode, setDnaMode] = useState<'select' | 'create'>(config?.company_dna_id ? 'select' : 'create');

  // Data for dropdowns
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [dnaProfiles, setDnaProfiles] = useState<CompanyDNA[]>([]);

  // LinkedIn enrichment state (for creating new blueprints inline)
  const [newBlueprintName, setNewBlueprintName] = useState('');
  const [linkedInProfiles, setLinkedInProfiles] = useState<LinkedInProfile[]>([]);
  const [newLinkedInUrl, setNewLinkedInUrl] = useState('');
  const [isCreatingBlueprint, setIsCreatingBlueprint] = useState(false);

  // Company DNA creation state
  const [newDnaCompany, setNewDnaCompany] = useState('');
  const [newDnaRole, setNewDnaRole] = useState('');  // Department or role type (free text)
  const [newDnaTimeWindow, setNewDnaTimeWindow] = useState(24);
  const [newDnaEmployeeLimit, setNewDnaEmployeeLimit] = useState(50);  // PDL fetch limit
  const [isCreatingDna, setIsCreatingDna] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState<{
    isOpen: boolean;
    id: number;
    label: string;
    type: 'dna' | 'blueprint';
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [createdDnaResult, setCreatedDnaResult] = useState<{
    id: number;
    company_name: string;
    role_category: string;
    employee_count_analyzed: number;
    workforce_dna?: {
      top_skills?: string[];
      experience_distribution?: Record<string, number>;
      common_backgrounds?: string[];
    };
    culture_indicators?: {
      technical_depth?: string;
      company_pace?: string;
      remote_friendly?: boolean;
    };
    success_patterns?: {
      common_previous_companies?: string[];
      common_previous_roles?: string[];
    };
  } | null>(null);

  useEffect(() => {
    loadDropdownData();
  }, []);

  // Load jobs and departments when ATS connection or historical settings change
  useEffect(() => {
    if (atsConnectionId && atsConnections.length > 0) {
      console.log('Loading jobs for connection:', atsConnectionId, 'from connections:', atsConnections);
      loadATSJobs(atsConnectionId);
      loadATSDepartments(atsConnectionId);
    } else {
      setAtsJobs([]);
      setAtsDepartments([]);
    }
  }, [atsConnectionId, atsConnections, includeHistoricalCandidates, historicalLookbackDays]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (activeDropdown) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [activeDropdown]);

  const loadDropdownData = async () => {
    try {
      const [blueprintsRes, dnaRes, connectionsRes] = await Promise.all([
        AXIOS_INSTANCE.get('/api/v1/talent-config/blueprints').catch(() => ({ data: { blueprints: [] } })),
        AXIOS_INSTANCE.get('/api/v1/talent-config/company-dna').catch(() => ({ data: { profiles: [] } })),
        AXIOS_INSTANCE.get('/api/connectors/configurations?is_enabled=true').catch(() => ({ data: [] })),
      ]);

      setBlueprints(blueprintsRes.data.blueprints || []);
      setDnaProfiles(dnaRes.data.profiles || []);
      
      // API returns { connectors: [...] } or direct array
      const allConnections = connectionsRes.data?.connectors || 
                            (Array.isArray(connectionsRes.data) ? connectionsRes.data : []);
      console.log('All connections loaded:', allConnections);
      const greenhouseConnections = allConnections.filter(
        (c: any) => c.connector_type === 'greenhouse' || c.provider_type === 'greenhouse'
      );
      console.log('Greenhouse connections:', greenhouseConnections);
      setAtsConnections(greenhouseConnections);
    } catch (err) {
      console.error('Failed to load dropdown data:', err);
    }
  };

  const loadATSJobs = async (connectionId: number) => {
    setIsLoadingJobs(true);
    try {
      // Find the connector_id (string) for this connection
      const connection = atsConnections.find(c => c.id === connectionId);
      const connectorId = connection?.connector_id;
      
      if (!connectorId) {
        console.error('No connector_id found for connection:', connectionId);
        setAtsJobs([]);
        return;
      }

      // Fetch jobs from Greenhouse API
      console.log('Loading jobs for connector:', connectorId);
      const response = await AXIOS_INSTANCE.get(`/api/connectors/greenhouse/jobs?connector_id=${connectorId}`).catch((err) => {
        console.error('Failed to fetch jobs:', err);
        return null;
      });
      
      console.log('Jobs response:', response?.data);
      
      if (response?.data && Array.isArray(response.data)) {
        // Map to our expected format
        // Note: API returns departments as array of strings, not objects
        const jobs = response.data.map((job: any) => ({
          id: job.id,
          name: job.name || job.title,
          department: Array.isArray(job.departments) 
            ? (typeof job.departments[0] === 'string' ? job.departments[0] : job.departments[0]?.name)
            : job.department,
          status: job.status,
        }));
        console.log('Mapped jobs:', jobs);
        setAtsJobs(jobs);
      } else {
        console.log('No jobs array in response');
        setAtsJobs([]);
      }
    } catch (err) {
      console.error('Failed to load ATS jobs:', err);
      setAtsJobs([]);
    } finally {
      setIsLoadingJobs(false);
    }
  };

  const loadATSDepartments = async (connectionId: number) => {
    setIsLoadingDepartments(true);
    try {
      // Find the connector_id (string) for this connection
      const connection = atsConnections.find(c => c.id === connectionId);
      const connectorId = connection?.connector_id;
      
      if (!connectorId) {
        console.error('No connector_id found for connection:', connectionId);
        setAtsDepartments([]);
        return;
      }

      // Fetch departments with candidate counts from Greenhouse API
      // Use historicalLookbackDays to filter which closed jobs to include in the count
      const lookbackDays = includeHistoricalCandidates ? historicalLookbackDays : 365;
      console.log('Loading departments with candidate counts for connector:', connectorId, 'lookback:', lookbackDays);
      const response = await AXIOS_INSTANCE.get(
        `/api/connectors/greenhouse/departments-with-counts?connector_id=${connectorId}&closed_job_lookback_days=${lookbackDays}`
      ).catch((err) => {
        console.error('Failed to fetch departments with counts:', err);
        return null;
      });
      
      console.log('Departments response:', response?.data);
      
      if (response?.data && Array.isArray(response.data)) {
        // Map to our expected format - backend already includes candidate_count and sorts
        const departments = response.data.map((dept: any) => ({
          id: dept.id,
          name: dept.name,
          parent_id: dept.parent_id,
          candidateCount: dept.candidate_count || 0,
        }));
        setAtsDepartments(departments);
      } else {
        // Fallback: fetch basic departments without counts
        const fallbackResponse = await AXIOS_INSTANCE.get(`/api/connectors/greenhouse/departments?connector_id=${connectorId}`).catch(() => null);
        if (fallbackResponse?.data && Array.isArray(fallbackResponse.data)) {
          const departments = fallbackResponse.data.map((dept: any) => ({
            id: dept.id,
            name: dept.name,
            parent_id: dept.parent_id,
            candidateCount: undefined, // Unknown
          }));
          setAtsDepartments(departments);
        } else {
          setAtsDepartments([]);
        }
      }
    } catch (err) {
      console.error('Failed to load ATS departments:', err);
      setAtsDepartments([]);
    } finally {
      setIsLoadingDepartments(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingFile(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Upload and extract text from the PDF
      const response = await AXIOS_INSTANCE.post('/api/document-parsing/parse', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.text) {
        setJobDescription(response.data.text);
        setJobDescriptionMode('paste'); // Switch to paste mode to show the extracted text
      }
    } catch (err: any) {
      const errorData = err.response?.data?.detail;
      if (typeof errorData === 'string') {
        setError(errorData);
      } else {
        setError('Failed to extract text from file');
      }
    } finally {
      setIsUploadingFile(false);
    }
  };

  const handleSave = async (shouldRun: boolean) => {
    if (!name.trim()) {
      setError('Analysis name is required');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      // Get uploaded resume file names
      const uploadedResumeNames = candidateSourceMode === 'upload' 
        ? uploadedResumes.filter(r => r.status === 'uploaded').map(r => r.name)
        : undefined;

      const payload = {
        name: name.trim(),
        description: description.trim() || undefined,
        blueprint_id: blueprintId,
        company_dna_id: dnaId,
        job_description: jobDescription.trim() || undefined,
        job_id: selectedJobId ? String(selectedJobId) : undefined,
        candidate_source_id: candidateSourceMode === 'ats' ? atsConnectionId : undefined,
        department_ids: candidateSourceMode === 'ats' && selectedDepartmentIds.length > 0 ? selectedDepartmentIds : undefined,
        candidate_source_mode: candidateSourceMode,
        uploaded_resume_files: uploadedResumeNames,
        ideal_candidate_details: getSerializedIdealDetails(),
        market_search_limit: marketSearchLimit,
        max_candidate_fetch: maxCandidateFetch,
        include_historical_candidates: includeHistoricalCandidates,
        historical_lookback_days: historicalLookbackDays,
      };

      if (config?.id) {
        await AXIOS_INSTANCE.put(`/api/v1/talent/analysis-configs/${config.id}`, payload);
        if (shouldRun) {
          await AXIOS_INSTANCE.post(`/api/v1/talent/analysis-configs/${config.id}/run`);
        }
      } else {
        const response = await AXIOS_INSTANCE.post('/api/v1/talent/analysis-configs', payload);
        if (shouldRun && response.data.id) {
          await AXIOS_INSTANCE.post(`/api/v1/talent/analysis-configs/${response.data.id}/run`);
        }
      }

      onSave(shouldRun);
    } catch (err: any) {
      const errorData = err.response?.data?.detail;
      if (Array.isArray(errorData)) {
        const messages = errorData.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        setError(messages || 'Validation failed');
      } else if (typeof errorData === 'string') {
        setError(errorData);
      } else {
        setError('Failed to save configuration');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const toggleDropdown = (dropdown: ActiveDropdown, e: React.MouseEvent) => {
    e.stopPropagation();
    setActiveDropdown(activeDropdown === dropdown ? null : dropdown);
  };

  const toggleSection = (section: AnalysisSection) => {
    setActiveSection(activeSection === section ? null : section);
    setActiveDropdown(null);
  };

  // LinkedIn enrichment handlers
  const handleAddLinkedInUrl = async () => {
    const url = newLinkedInUrl.trim();
    if (!url) return;

    let normalizedUrl = url;
    if (!url.startsWith('http')) {
      normalizedUrl = 'https://' + url;
    }
    if (!normalizedUrl.includes('linkedin.com')) {
      normalizedUrl = 'https://linkedin.com/in/' + url;
    }

    if (linkedInProfiles.some(p => p.url === normalizedUrl)) {
      return;
    }

    const newProfile: LinkedInProfile = {
      url: normalizedUrl,
      status: 'enriching',
    };

    setLinkedInProfiles(prev => [...prev, newProfile]);
    setNewLinkedInUrl('');

    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/linkedin/enrich', {
        linkedin_url: normalizedUrl,
      });

      if (response.data.found) {
        setLinkedInProfiles(prev => prev.map(p =>
          p.url === normalizedUrl
            ? {
                ...p,
                status: 'enriched' as const,
                name: response.data.full_name,
                title: response.data.job_title,
                company: response.data.job_company_name,
                skills: response.data.skills?.slice(0, 10) || [],
                experience: response.data.inferred_years_experience,
                cached: response.data.cached || false,
                enrichedData: response.data,
              }
            : p
        ));
      } else {
        setLinkedInProfiles(prev => prev.map(p =>
          p.url === normalizedUrl
            ? { ...p, status: 'error' as const, error: response.data.error_message || 'Profile not found' }
            : p
        ));
      }
    } catch (err: any) {
      setLinkedInProfiles(prev => prev.map(p =>
        p.url === normalizedUrl
          ? { ...p, status: 'error' as const, error: err?.response?.data?.detail || 'Enrichment failed' }
          : p
      ));
    }
  };

  const handleRemoveProfile = (url: string) => {
    setLinkedInProfiles(prev => prev.filter(p => p.url !== url));
  };

  const handleCreateBlueprint = async () => {
    if (!newBlueprintName.trim()) {
      setError('Blueprint name is required');
      return;
    }

    const enrichedProfilesData = linkedInProfiles
      .filter(p => p.status === 'enriched' && p.enrichedData);

    if (enrichedProfilesData.length === 0) {
      setError('At least one enriched profile is required');
      return;
    }

    const linkedinUrls = enrichedProfilesData.map(p => p.url);
    const enrichedProfiles = enrichedProfilesData.map(p => p.enrichedData);

    setIsCreatingBlueprint(true);
    setError(null);

    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/talent-config/blueprints', {
        name: newBlueprintName.trim(),
        linkedin_urls: linkedinUrls,
        enriched_profiles: enrichedProfiles,
      });

      setBlueprintId(response.data.id);
      setBlueprintName(response.data.name);
      await loadDropdownData();
      setNewBlueprintName('');
      setLinkedInProfiles([]);
      setActiveSection(null);
    } catch (err: any) {
      const errorData = err.response?.data?.detail;
      if (Array.isArray(errorData)) {
        const messages = errorData.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        setError(messages || 'Validation failed');
      } else if (typeof errorData === 'string') {
        setError(errorData);
      } else {
        setError('Failed to create blueprint');
      }
    } finally {
      setIsCreatingBlueprint(false);
    }
  };

  const handleCreateDna = async () => {
    if (!newDnaCompany.trim()) {
      setError('Company name is required');
      return;
    }

    setIsCreatingDna(true);
    setError(null);
    setCreatedDnaResult(null);

    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/talent-config/company-dna', {
        company_name: newDnaCompany.trim(),
        role_category: newDnaRole || 'all',
        time_window_months: newDnaTimeWindow,
        employee_fetch_limit: newDnaEmployeeLimit,
      });

      // Store the full result to display
      setCreatedDnaResult(response.data);
      setDnaId(response.data.id);
      setDnaName(`${response.data.company_name} - ${response.data.role_category}`);
      await loadDropdownData();
      // Don't clear the form or close the section - let user see the results
    } catch (err: any) {
      const errorData = err.response?.data?.detail;
      if (Array.isArray(errorData)) {
        const messages = errorData.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        setError(messages || 'Validation failed');
      } else if (typeof errorData === 'string') {
        setError(errorData);
      } else {
        setError('Failed to create Company DNA');
      }
    } finally {
      setIsCreatingDna(false);
    }
  };

  const handleResetDnaForm = () => {
    setNewDnaCompany('');
    setNewDnaRole('');
    setNewDnaTimeWindow(24);
    setNewDnaEmployeeLimit(50);
    setCreatedDnaResult(null);
  };

  const handleDeleteDna = (id: number, label: string) => {
    // Show confirmation modal instead of browser confirm
    setDeleteConfirmation({ isOpen: true, id, label, type: 'dna' });
  };

  const handleConfirmDelete = async () => {
    if (!deleteConfirmation) return;
    
    setIsDeleting(true);
    try {
      if (deleteConfirmation.type === 'dna') {
        await AXIOS_INSTANCE.delete(`/api/v1/talent-config/company-dna/${deleteConfirmation.id}`);
        // If the deleted DNA was selected, clear the selection
        if (dnaId === deleteConfirmation.id) {
          setDnaId(undefined);
          setDnaName('');
        }
      } else if (deleteConfirmation.type === 'blueprint') {
        await AXIOS_INSTANCE.delete(`/api/v1/talent-config/blueprints/${deleteConfirmation.id}`);
        // If the deleted blueprint was selected, clear the selection
        if (blueprintId === deleteConfirmation.id) {
          setBlueprintId(undefined);
          setBlueprintName('');
        }
      }
      // Refresh the list
      await loadDropdownData();
      setDeleteConfirmation(null);
    } catch (err: any) {
      console.error('Failed to delete:', err);
      setError(`Failed to delete "${deleteConfirmation.label}"`);
    } finally {
      setIsDeleting(false);
    }
  };

  // Check completion status
  const isAtsComplete = !!atsConnectionId;
  const isBlueprintComplete = !!blueprintId;
  const isDnaComplete = !!dnaId;
  const isJobDescriptionComplete = !!jobDescription.trim() || !!selectedJobId;
  const isCandidateSourceComplete = candidateSourceMode === 'ats' 
    ? selectedDepartmentIds.length > 0 
    : uploadedResumes.filter(r => r.status === 'uploaded').length > 0;
  const isIdealCandidateComplete = !!(idealMustHaves.trim() || idealNiceToHaves.trim() || idealDealbreakers.trim() || idealPersonalityTraits.trim() || idealHiringManagerNotes.trim());

  // Analysis Setup is complete when name is entered
  const isAnalysisSetupComplete = name.trim().length > 0;

  // Completion state record for sidebar
  const completionState: Record<AnalysisSection, boolean> = {
    'analysis-setup': isAnalysisSetupComplete,
    'ats-connection': isAtsComplete,
    'career-blueprint': isBlueprintComplete,
    'company-dna': isDnaComplete,
    'job-description': isJobDescriptionComplete,
    'candidate-source': isCandidateSourceComplete,
    'ideal-candidate': isIdealCandidateComplete,
  };

  // Check if all required sections are complete for "Save & Run"
  const canRun = name.trim().length > 0 && areRequiredSectionsComplete(completionState);

  const enrichedCount = linkedInProfiles.filter(p => p.status === 'enriched').length;
  const canCreateBlueprint = enrichedCount > 0 && newBlueprintName.trim();
  const canCreateDna = newDnaCompany.trim();

  return (
    <Modal open={true} onClose={onClose}>
      <ModalContent size="full" className="max-w-6xl h-[85vh] max-h-[700px] overflow-hidden flex flex-col relative">
        {/* Header - Static title + close button */}
        <ModalHeader showCloseButton={false} className="border-b border-gray-200 dark:border-dark-border pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <SparklesIcon className="w-5 h-5 text-eliza-red flex-shrink-0" />
              <ModalTitle className="font-title">{config?.id ? 'Edit Analysis' : 'Create New Analysis'}</ModalTitle>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:text-gray-300 dark:hover:bg-dark-surface-2 transition-colors"
                aria-label="Close"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        </ModalHeader>

        {/* Content - Two Column Layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Sidebar */}
          <AnalysisModalSidebar
            activeSection={activeSection}
            onSectionChange={setActiveSection}
            completionState={completionState}
          />

          {/* Content Area */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-gray-50 dark:bg-dark-bg relative">
            <ModalBody className="flex-1 overflow-y-auto px-6 py-5 pb-24">
          {/* Legacy Pill Buttons - Hidden, navigation now via sidebar */}
          {/* TODO: Move selection functionality into section content areas */}
          <div className="hidden">
          {/* ATS Connection Row */}
          <div className="mb-3">
            <div className="relative inline-block">
              <Chip
                variant="outline"
                unselectedIcon={<ServerStackIcon className="w-3.5 h-3.5" />}
                completeIcon={<ServerStackIcon className="w-3.5 h-3.5" />}
                complete={isAtsComplete}
                active={activeDropdown === 'ats'}
                showChevron
                onClick={(e) => toggleDropdown('ats', e)}
              >
                {atsConnectionName || 'ATS Connection'}
              </Chip>
              {activeDropdown === 'ats' && (
                <AttachedDropdown
                  items={atsConnections.map(c => ({ id: c.id, label: c.connector_name || c.name || 'Unnamed', sublabel: 'Greenhouse' }))}
                  selectedId={atsConnectionId}
                  onSelect={(id, label) => {
                    setAtsConnectionId(id);
                    setAtsConnectionName(label);
                    setActiveDropdown(null);
                    // Clear job selection when ATS changes
                    setSelectedJobId(undefined);
                    setSelectedJobName('');
                  }}
                  onClear={() => {
                    setAtsConnectionId(undefined);
                    setAtsConnectionName('');
                    setSelectedJobId(undefined);
                    setSelectedJobName('');
                    setActiveDropdown(null);
                  }}
                  onCreateNew={() => window.open('/data-connections', '_blank')}
                  emptyMessage="No ATS connections configured"
                />
              )}
            </div>
            {!isAtsComplete && (
              <span className="ml-3 text-xs text-gray-500 dark:text-gray-400">Select an ATS connection to enable job selection</span>
            )}
          </div>

          {/* Pill Buttons Row */}
          <div className="flex flex-wrap gap-2 mb-4">
            {/* Blueprint Pill */}
            <div className="relative">
              <Chip
                variant="outline"
                unselectedIcon={<SparklesIcon className="w-3.5 h-3.5" />}
                completeIcon={<SparklesIcon className="w-3.5 h-3.5" />}
                complete={isBlueprintComplete}
                active={activeDropdown === 'blueprint' || activeSection === 'career-blueprint'}
                showChevron
                onClick={(e) => {
                  if (activeSection === 'career-blueprint') {
                    setActiveSection(null);
                  } else {
                    toggleDropdown('blueprint', e);
                  }
                }}
              >
                {blueprintName || 'Career Blueprint'}
              </Chip>
              {activeDropdown === 'blueprint' && (
                <AttachedDropdown
                  items={blueprints.map(b => ({ id: b.id, label: b.name, sublabel: b.role_category }))}
                  selectedId={blueprintId}
                  onSelect={(id, label) => {
                    setBlueprintId(id);
                    setBlueprintName(label);
                    setActiveDropdown(null);
                    setActiveSection(null);
                  }}
                  onClear={() => {
                    setBlueprintId(undefined);
                    setBlueprintName('');
                    setActiveDropdown(null);
                  }}
                  onCreateNew={() => {
                    setActiveDropdown(null);
                    setActiveSection('career-blueprint');
                  }}
                />
              )}
            </div>

            {/* DNA Pill */}
            <div className="relative">
              <Chip
                variant="outline"
                unselectedIcon={<BuildingOfficeIcon className="w-3.5 h-3.5" />}
                completeIcon={<BuildingOfficeIcon className="w-3.5 h-3.5" />}
                complete={isDnaComplete}
                active={activeDropdown === 'dna' || activeSection === 'company-dna'}
                showChevron
                onClick={(e) => {
                  if (activeSection === 'company-dna') {
                    setActiveSection(null);
                  } else {
                    toggleDropdown('dna', e);
                  }
                }}
              >
                {dnaName || 'Company DNA'}
              </Chip>
              {activeDropdown === 'dna' && (
                <AttachedDropdown
                  items={dnaProfiles.map(d => ({
                    id: d.id,
                    label: `${d.company_name} - ${d.role_category}`,
                    sublabel: d.role_category
                  }))}
                  selectedId={dnaId}
                  onSelect={(id, label) => {
                    setDnaId(id);
                    setDnaName(label);
                    setActiveDropdown(null);
                    setActiveSection(null);
                  }}
                  onClear={() => {
                    setDnaId(undefined);
                    setDnaName('');
                    setActiveDropdown(null);
                  }}
                  onDelete={handleDeleteDna}
                  onCreateNew={() => {
                    setActiveDropdown(null);
                    setActiveSection('company-dna');
                  }}
                />
              )}
            </div>

            {/* Job Description Pill */}
            <div className="relative">
              <Chip
                variant="outline"
                unselectedIcon={<DocumentTextIcon className="w-3.5 h-3.5" />}
                completeIcon={<DocumentTextIcon className="w-3.5 h-3.5" />}
                complete={isJobDescriptionComplete}
                active={activeDropdown === 'job' || activeSection === 'job-description'}
                showChevron
                onClick={(e) => {
                  if (activeSection === 'job-description') {
                    setActiveSection(null);
                  } else if (isAtsComplete && atsJobs.length > 0) {
                    toggleDropdown('job', e);
                  } else {
                    setActiveSection('job-description');
                  }
                }}
              >
                {selectedJobName || (jobDescription ? 'Job Description ✓' : 'Job Description')}
              </Chip>
              {activeDropdown === 'job' && (
                <AttachedDropdown
                  items={atsJobs.map(j => ({ id: j.id, label: j.name, sublabel: j.department || j.status }))}
                  selectedId={selectedJobId}
                  onSelect={async (id, label) => {
                    setSelectedJobId(id);
                    setSelectedJobName(label);
                    setActiveDropdown(null);
                    // Optionally fetch job description from ATS
                    try {
                      const response = await AXIOS_INSTANCE.get(`/api/connectors/${atsConnectionId}/jobs/${id}`);
                      if (response.data?.description) {
                        setJobDescription(response.data.description);
                      }
                    } catch (err) {
                      console.error('Failed to fetch job description:', err);
                    }
                  }}
                  onClear={() => {
                    setSelectedJobId(undefined);
                    setSelectedJobName('');
                    setJobDescription('');
                    setActiveDropdown(null);
                  }}
                  onCreateNew={() => {
                    setActiveDropdown(null);
                    setActiveSection('job-description');
                  }}
                  createNewLabel="Enter manually"
                  emptyMessage={isLoadingJobs ? 'Loading jobs...' : 'No open jobs found'}
                  alignRight
                />
              )}
            </div>

            {/* Candidate Source Pill */}
            <div className="relative">
              <Chip
                variant="outline"
                unselectedIcon={<BriefcaseIcon className="w-3.5 h-3.5" />}
                completeIcon={<BriefcaseIcon className="w-3.5 h-3.5" />}
                complete={isCandidateSourceComplete}
                active={activeDropdown === 'candidate-source' || activeSection === 'candidate-source'}
                showChevron
                onClick={(e) => {
                  if (activeSection === 'candidate-source') {
                    setActiveSection(null);
                  } else {
                    setActiveSection('candidate-source');
                  }
                }}
              >
                {candidateSourceMode === 'upload' && uploadedResumes.length > 0
                  ? `${uploadedResumes.filter(r => r.status === 'uploaded').length} resume${uploadedResumes.filter(r => r.status === 'uploaded').length !== 1 ? 's' : ''} uploaded`
                  : selectedDepartmentNames.length > 0 
                    ? `${selectedDepartmentNames.length} dept${selectedDepartmentNames.length > 1 ? 's' : ''} selected`
                    : 'Candidate Source'}
              </Chip>
              {activeDropdown === 'candidate-source' && (
                <DepartmentDropdown
                  departments={atsDepartments}
                  selectedIds={selectedDepartmentIds}
                  isLoading={isLoadingDepartments}
                  onToggle={(id, name) => {
                    if (selectedDepartmentIds.includes(id)) {
                      setSelectedDepartmentIds(prev => prev.filter(d => d !== id));
                      setSelectedDepartmentNames(prev => prev.filter(n => n !== name));
                    } else {
                      setSelectedDepartmentIds(prev => [...prev, id]);
                      setSelectedDepartmentNames(prev => [...prev, name]);
                    }
                  }}
                  onSelectAll={() => {
                    setSelectedDepartmentIds(atsDepartments.map(d => d.id));
                    setSelectedDepartmentNames(atsDepartments.map(d => d.name));
                  }}
                  onClearAll={() => {
                    setSelectedDepartmentIds([]);
                    setSelectedDepartmentNames([]);
                  }}
                  onClose={() => setActiveDropdown(null)}
                />
              )}
            </div>

            {/* Ideal Candidate Pill */}
            <Chip
              variant="outline"
              unselectedIcon={<UserIcon className="w-3.5 h-3.5" />}
              completeIcon={<UserIcon className="w-3.5 h-3.5" />}
              complete={isIdealCandidateComplete}
              active={activeSection === 'ideal-candidate'}
              showChevron
              onClick={() => toggleSection('ideal-candidate')}
            >
              Ideal Candidate
            </Chip>

            {/* Market Search Limit Pill */}
            <Popover>
              <PopoverTrigger asChild>
                <Chip
                  variant="outline"
                  complete={true}
                  active={activeDropdown === 'search-limit'}
                  showChevron
                  showIcon={false}
                  onClick={(e) => toggleDropdown('search-limit', e)}
                >
                  <MagnifyingGlassIcon className="w-3.5 h-3.5" />
                  {marketSearchLimit} market
                </Chip>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-48">
                <PopoverBody className="space-y-2">
                  <Label className="text-xs">Market Search Limit</Label>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={marketSearchLimit}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val)) {
                        setMarketSearchLimit(val);
                      } else if (e.target.value === '') {
                        setMarketSearchLimit(1);
                      }
                    }}
                    onBlur={(e) => {
                      const val = parseInt(e.target.value) || 50;
                      setMarketSearchLimit(Math.min(100, Math.max(1, val)));
                    }}
                    className="h-8"
                    autoFocus
                  />
                  <p className="text-xs text-gray-400 dark:text-gray-500">PDL candidates to search (1-100)</p>
                  <Button
                    size="sm"
                    onClick={() => setActiveDropdown(null)}
                    className="w-full"
                  >
                    Done
                  </Button>
                </PopoverBody>
              </PopoverContent>
            </Popover>

            {/* Max ATS Candidate Fetch Pill */}
            <Popover>
              <PopoverTrigger asChild>
                <Chip
                  variant="outline"
                  complete={true}
                  active={activeDropdown === 'ats-limit'}
                  showChevron
                  showIcon={false}
                  onClick={(e) => toggleDropdown('ats-limit', e)}
                >
                  <UsersIcon className="w-3.5 h-3.5" />
                  {maxCandidateFetch} ATS
                </Chip>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-48">
                <PopoverBody className="space-y-2">
                  <Label className="text-xs">ATS Candidate Limit</Label>
                  <Input
                    type="number"
                    min={1}
                    max={500}
                    value={maxCandidateFetch}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val)) {
                        setMaxCandidateFetch(val);
                      } else if (e.target.value === '') {
                        setMaxCandidateFetch(1);
                      }
                    }}
                    onBlur={(e) => {
                      const val = parseInt(e.target.value) || 100;
                      setMaxCandidateFetch(Math.min(500, Math.max(1, val)));
                    }}
                    className="h-8"
                    autoFocus
                  />
                  <p className="text-xs text-gray-400 dark:text-gray-500">Max applicants from ATS (1-500)</p>
                  <Button
                    size="sm"
                    onClick={() => setActiveDropdown(null)}
                    className="w-full"
                  >
                    Done
                  </Button>
                </PopoverBody>
              </PopoverContent>
            </Popover>
          </div>
          </div>
          {/* End Legacy Pill Buttons */}

          {/* Expanded Content Area */}
          <div className="flex-1">
            {/* Analysis Setup Section */}
            {activeSection === 'analysis-setup' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Analysis Setup</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Configure the name, description, and search limits for your analysis</p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['analysis-setup'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['analysis-setup'] ? 'bg-green-500' : 'bg-amber-500'}`} />
                    {completionState['analysis-setup'] ? 'Saved' : 'Unsaved Changes'}
                  </span>
                </div>

                {/* Name and Description */}
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium text-charcoal dark:text-gray-100">
                      Analysis Name <span className="text-gray-400">*</span>
                    </Label>
                    <Input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g., Senior Backend Engineer Search"
                      autoFocus
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-sm font-medium text-charcoal dark:text-gray-100">
                      Description
                    </Label>
                    <Textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Brief description of this analysis..."
                      rows={2}
                    />
                  </div>
                </div>

                {/* Divider */}
                <div className="h-px bg-gray-200 dark:bg-dark-border" />

                {/* Search Limits */}
                <div className="space-y-6">
                  <div>
                    <h4 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-1">Search Limits</h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Control how many candidates to search from each source</p>
                  </div>

                  <SliderInput
                    label="Market Search Limit"
                    description="Max candidates to search from external talent market (PDL)"
                    value={marketSearchLimit}
                    onChange={setMarketSearchLimit}
                    min={1}
                    max={100}
                    step={10}
                  />

                  <SliderInput
                    label="ATS Pipeline Limit"
                    description="Max candidates to fetch from your connected ATS"
                    value={maxCandidateFetch}
                    onChange={setMaxCandidateFetch}
                    min={1}
                    max={500}
                    step={25}
                  />
                </div>
              </div>
            )}

            {/* ATS Connection Section */}
            {activeSection === 'ats-connection' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">ATS Connection</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Connect your ATS to import job postings and sync candidate data automatically</p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['ats-connection'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['ats-connection'] ? 'bg-green-500' : 'bg-gray-400'}`} />
                    {completionState['ats-connection'] ? 'Connected' : 'Optional'}
                  </span>
                </div>

                {/* ATS Connection Selection */}
                <div className="space-y-3">
                  <Label className="text-sm font-medium">Select ATS Connection</Label>
                  {atsConnections.length === 0 ? (
                    <div className="text-center py-8 border border-dashed border-gray-300 dark:border-dark-border rounded-xl">
                      <ServerStackIcon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
                      <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">No ATS connections configured</p>
                      <Button variant="outline" size="sm" onClick={() => window.open('/data-connections', '_blank')}>
                        <PlusIcon className="w-4 h-4 mr-1.5" />
                        Add Connection
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {atsConnections.map((connection) => (
                        <button
                          key={connection.id}
                          type="button"
                          onClick={() => {
                            setAtsConnectionId(connection.id);
                            setAtsConnectionName(connection.connector_name || connection.name || 'Unnamed');
                          }}
                          className={cn(
                            'w-full flex items-center gap-3 p-3 rounded-xl border transition-colors text-left',
                            atsConnectionId === connection.id
                              ? 'border-eliza-red bg-eliza-red/5 dark:bg-eliza-red/10'
                              : 'border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-dark-border/70'
                          )}
                        >
                          <ServerStackIcon className={cn(
                            'w-5 h-5',
                            atsConnectionId === connection.id ? 'text-eliza-red' : 'text-gray-400'
                          )} />
                          <div className="flex-1">
                            <p className={cn(
                              'text-sm font-medium',
                              atsConnectionId === connection.id ? 'text-eliza-red' : 'text-charcoal dark:text-gray-100'
                            )}>
                              {connection.connector_name || connection.name || 'Unnamed'}
                            </p>
                            <p className="text-xs text-gray-500">Greenhouse</p>
                          </div>
                          {atsConnectionId === connection.id && (
                            <CheckIcon className="w-5 h-5 text-eliza-red" />
                          )}
                        </button>
                      ))}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full"
                        onClick={() => window.open('/data-connections', '_blank')}
                      >
                        <PlusIcon className="w-4 h-4 mr-1.5" />
                        Add New Connection
                      </Button>
                    </div>
                  )}
                </div>

                {atsConnectionId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-gray-500"
                    onClick={() => {
                      setAtsConnectionId(undefined);
                      setAtsConnectionName('');
                      setSelectedJobId(undefined);
                      setSelectedJobName('');
                    }}
                  >
                    Clear selection
                  </Button>
                )}
              </div>
            )}

            {/* Blueprint Creation (LinkedIn Enrichment) */}
            {activeSection === 'career-blueprint' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Career Blueprint</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                      {blueprintMode === 'select' 
                        ? 'Select an existing blueprint to use for candidate matching' 
                        : 'Add 2-5 LinkedIn profiles of people in similar roles to capture your ideal candidate profile'}
                    </p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['career-blueprint'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['career-blueprint'] ? 'bg-green-500' : 'bg-gray-400'}`} />
                    {completionState['career-blueprint'] ? 'Selected' : 'Optional'}
                  </span>
                </div>

                {/* Mode Selector */}
                <Tabs value={blueprintMode} onValueChange={(v) => setBlueprintMode(v as 'select' | 'create')} defaultValue="create">
                  <TabsList variant="underline">
                    <TabsTrigger value="select" variant="underline">
                      <CheckCircleIcon className="w-4 h-4 mr-1.5" />
                      Select Existing
                    </TabsTrigger>
                    <TabsTrigger value="create" variant="underline">
                      <PlusIcon className="w-4 h-4 mr-1.5" />
                      Create New
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                {/* Select Existing Mode */}
                {blueprintMode === 'select' && (
                  <>
                    {blueprints.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                        <SparklesIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p className="font-medium text-charcoal dark:text-gray-100 mb-1">No Blueprints Available</p>
                        <p>Create a new blueprint to get started</p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => setBlueprintMode('create')}
                        >
                          <PlusIcon className="w-3.5 h-3.5 mr-1.5" />
                          Create Blueprint
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {blueprints.map((blueprint) => (
                          <div
                            key={blueprint.id}
                            onClick={() => {
                              setBlueprintId(blueprint.id);
                              setBlueprintName(blueprint.name);
                            }}
                            className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                              blueprintId === blueprint.id
                                ? 'border-eliza-red bg-eliza-red/5 dark:bg-eliza-red/10'
                                : 'border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-gray-600 bg-white dark:bg-dark-surface'
                            }`}
                          >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                              blueprintId === blueprint.id
                                ? 'bg-eliza-red text-white'
                                : 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400'
                            }`}>
                              <SparklesIcon className="w-4 h-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-charcoal dark:text-gray-100 truncate">{blueprint.name}</p>
                              <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{blueprint.role_category || 'No role category'}</p>
                            </div>
                            {blueprintId === blueprint.id && (
                              <CheckCircleIcon className="w-5 h-5 text-eliza-red flex-shrink-0" />
                            )}
                          </div>
                        ))}

                        {blueprintId && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-gray-500"
                            onClick={() => {
                              setBlueprintId(undefined);
                              setBlueprintName('');
                            }}
                          >
                            Clear selection
                          </Button>
                        )}
                      </div>
                    )}
                  </>
                )}

                {/* Create New Mode */}
                {blueprintMode === 'create' && (
                  <>
                    <Input
                      type="text"
                      value={newBlueprintName}
                      onChange={(e) => setNewBlueprintName(e.target.value)}
                      placeholder="Blueprint name (e.g., Senior Backend Engineers)"
                      autoFocus
                    />

                    <div className="flex gap-2">
                      <div className="flex-1 relative">
                        <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 z-10" />
                        <Input
                          type="text"
                          value={newLinkedInUrl}
                          onChange={(e) => setNewLinkedInUrl(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleAddLinkedInUrl()}
                          placeholder="Add LinkedIn URL..."
                          className="pl-9"
                        />
                      </div>
                      <Button
                        variant="outline"
                        onClick={handleAddLinkedInUrl}
                        disabled={!newLinkedInUrl.trim()}
                      >
                        Add
                      </Button>
                    </div>

                    {linkedInProfiles.length > 0 && (
                      <div className="space-y-1.5 max-h-[180px] overflow-y-auto">
                        {linkedInProfiles.map((profile) => (
                          <div
                            key={profile.url}
                            className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border rounded-xl text-sm"
                          >
                            <div className="flex-shrink-0">
                              {profile.status === 'enriching' && (
                                <Spinner size="xs" variant="primary" />
                              )}
                              {profile.status === 'enriched' && (
                                <CheckCircleIcon className="w-4 h-4 text-green-500" />
                              )}
                              {profile.status === 'error' && (
                                <ExclamationCircleIcon className="w-4 h-4 text-red-500" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              {profile.status === 'enriched' ? (
                                <span className="text-charcoal dark:text-gray-100 truncate block">
                                  {profile.name} <span className="text-gray-500 dark:text-gray-400">· {profile.title}</span>
                                </span>
                              ) : profile.status === 'error' ? (
                                <span className="text-red-500 truncate block">{profile.error}</span>
                              ) : (
                                <span className="text-gray-500 dark:text-gray-400 truncate block">{profile.url}</span>
                              )}
                            </div>
                            {profile.cached && (
                              <span className="text-[10px] text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface px-1.5 py-0.5 rounded">cached</span>
                            )}
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => handleRemoveProfile(profile.url)}
                              className="text-gray-400 hover:text-red-500"
                            >
                              <TrashIcon className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}

                    <Button
                      onClick={handleCreateBlueprint}
                      disabled={!canCreateBlueprint || isCreatingBlueprint}
                      className="w-full"
                    >
                      {isCreatingBlueprint && <Spinner size="xs" variant="white" className="mr-2" />}
                      {isCreatingBlueprint ? 'Creating...' : `Create Blueprint${enrichedCount > 0 ? ` (${enrichedCount} profiles)` : ''}`}
                    </Button>
                  </>
                )}
              </div>
            )}

            {/* Company DNA Creation */}
            {activeSection === 'company-dna' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Company DNA</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                      {dnaMode === 'select' 
                        ? 'Select an existing DNA profile to use for candidate matching' 
                        : 'Search for employees at a company to build a DNA profile for better candidate matching'}
                    </p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['company-dna'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['company-dna'] ? 'bg-green-500' : 'bg-gray-400'}`} />
                    {completionState['company-dna'] ? 'Selected' : 'Optional'}
                  </span>
                </div>

                {/* Mode Selector */}
                <Tabs value={dnaMode} onValueChange={(v) => setDnaMode(v as 'select' | 'create')} defaultValue="create">
                  <TabsList variant="underline">
                    <TabsTrigger value="select" variant="underline">
                      <CheckCircleIcon className="w-4 h-4 mr-1.5" />
                      Select Existing
                    </TabsTrigger>
                    <TabsTrigger value="create" variant="underline">
                      <PlusIcon className="w-4 h-4 mr-1.5" />
                      Create New
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                {/* Select Existing Mode */}
                {dnaMode === 'select' && (
                  <>
                    {dnaProfiles.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                        <BuildingOfficeIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p className="font-medium text-charcoal dark:text-gray-100 mb-1">No DNA Profiles Available</p>
                        <p>Create a new Company DNA profile to get started</p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => setDnaMode('create')}
                        >
                          <PlusIcon className="w-3.5 h-3.5 mr-1.5" />
                          Create DNA Profile
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {dnaProfiles.map((dna) => (
                          <div
                            key={dna.id}
                            onClick={() => {
                              setDnaId(dna.id);
                              setDnaName(`${dna.company_name} - ${dna.role_category}`);
                            }}
                            className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                              dnaId === dna.id
                                ? 'border-eliza-red bg-eliza-red/5 dark:bg-eliza-red/10'
                                : 'border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-gray-600 bg-white dark:bg-dark-surface'
                            }`}
                          >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                              dnaId === dna.id
                                ? 'bg-eliza-red text-white'
                                : 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400'
                            }`}>
                              <BuildingOfficeIcon className="w-4 h-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-charcoal dark:text-gray-100 truncate">{dna.company_name}</p>
                              <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{dna.role_category || 'All departments'}</p>
                            </div>
                            {dnaId === dna.id && (
                              <CheckCircleIcon className="w-5 h-5 text-eliza-red flex-shrink-0" />
                            )}
                          </div>
                        ))}

                        {dnaId && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-gray-500"
                            onClick={() => {
                              setDnaId(undefined);
                              setDnaName('');
                            }}
                          >
                            Clear selection
                          </Button>
                        )}
                      </div>
                    )}
                  </>
                )}

                {/* Create New Mode */}
                {dnaMode === 'create' && (
                  <>
                    {/* Show Results if DNA was created */}
                    {createdDnaResult ? (
                  <div className="space-y-4">
                    {/* Success Header */}
                    <Alert variant="success" hideIcon className="flex items-center gap-3">
                      <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-charcoal dark:text-gray-100">
                          {createdDnaResult.company_name} - {createdDnaResult.role_category}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          Analyzed {createdDnaResult.employee_count_analyzed} employee{createdDnaResult.employee_count_analyzed !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </Alert>

                    {createdDnaResult.employee_count_analyzed > 0 ? (
                      <div className="grid grid-cols-2 gap-4">
                        {/* Top Skills */}
                        {createdDnaResult.workforce_dna?.top_skills && createdDnaResult.workforce_dna.top_skills.length > 0 && (
                          <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-xl">
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Top Skills</h4>
                            <div className="flex flex-wrap gap-1">
                              {createdDnaResult.workforce_dna.top_skills.slice(0, 8).map((skill, idx) => (
                                <span key={idx} className="px-2 py-0.5 text-xs bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20 rounded-full">
                                  {skill}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Experience Distribution */}
                        {createdDnaResult.workforce_dna?.experience_distribution && (
                          <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-xl">
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Experience Levels</h4>
                            <div className="space-y-1">
                              {['0-2', '3-5', '6-10', '10+'].map(range => {
                                const pct = createdDnaResult.workforce_dna?.experience_distribution?.[range] || 0;
                                return pct > 0 ? (
                                  <div key={range} className="flex items-center gap-2 text-xs">
                                    <span className="w-10 text-gray-500 dark:text-gray-400">{range}yr</span>
                                    <div className="flex-1 h-1.5 bg-gray-200 dark:bg-dark-border rounded-full overflow-hidden">
                                      <div 
                                        className="h-full bg-eliza-red rounded-full" 
                                        style={{ width: `${Math.min(pct, 100)}%` }}
                                      />
                                    </div>
                                    <span className="w-8 text-right text-gray-500 dark:text-gray-400">{pct}%</span>
                                  </div>
                                ) : null;
                              })}
                            </div>
                          </div>
                        )}

                        {/* Culture Indicators */}
                        {createdDnaResult.culture_indicators && (
                          <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-xl">
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Culture Signals</h4>
                            <div className="space-y-1 text-xs">
                              {createdDnaResult.culture_indicators.technical_depth && (
                                <div className="flex justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">Technical Depth</span>
                                  <span className="text-charcoal dark:text-gray-100 capitalize">{createdDnaResult.culture_indicators.technical_depth}</span>
                                </div>
                              )}
                              {createdDnaResult.culture_indicators.company_pace && (
                                <div className="flex justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">Pace</span>
                                  <span className="text-charcoal dark:text-gray-100 capitalize">{createdDnaResult.culture_indicators.company_pace}</span>
                                </div>
                              )}
                              {createdDnaResult.culture_indicators.remote_friendly !== undefined && (
                                <div className="flex justify-between">
                                  <span className="text-gray-500 dark:text-gray-400">Remote Friendly</span>
                                  <span className="text-charcoal dark:text-gray-100">{createdDnaResult.culture_indicators.remote_friendly ? 'Yes' : 'No'}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Common Backgrounds */}
                        {createdDnaResult.success_patterns?.common_previous_companies && createdDnaResult.success_patterns.common_previous_companies.length > 0 && (
                          <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-xl">
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Common Backgrounds</h4>
                            <div className="flex flex-wrap gap-1">
                              {createdDnaResult.success_patterns.common_previous_companies.slice(0, 6).map((company, idx) => (
                                <span key={idx} className="px-2 py-0.5 text-xs bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-full text-gray-500 dark:text-gray-400">
                                  {company}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <Alert variant="warning" hideIcon>
                        <p className="text-sm">
                          No employees found matching your criteria. Try:
                        </p>
                        <ul className="mt-2 text-xs text-gray-500 dark:text-gray-400 space-y-1">
                          <li>• Using a different company name spelling</li>
                          <li>• Broadening the role type (or leaving it empty)</li>
                          <li>• Increasing the employee search limit</li>
                        </ul>
                      </Alert>
                    )}

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={() => {
                          handleResetDnaForm();
                        }}
                      >
                        Create Another
                      </Button>
                      <Button
                        className="flex-1"
                        onClick={() => {
                          handleResetDnaForm();
                          setActiveSection(null);
                        }}
                      >
                        Done
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* Creation Form */
                  <>
                    <div>
                      <Label className="block text-xs mb-1.5">Company Name</Label>
                      <div className="relative">
                        <BuildingOfficeIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 z-10" />
                        <Input
                          type="text"
                          value={newDnaCompany}
                          onChange={(e) => setNewDnaCompany(e.target.value)}
                          placeholder="e.g., Caylent, Google, Amazon"
                          className="pl-9"
                          autoFocus
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="block text-xs mb-1.5">Department or Role Type</Label>
                        <Select value={newDnaRole} onValueChange={setNewDnaRole} placeholder="All Departments">
                          <SelectOption value="">All Departments</SelectOption>
                          <SelectOption value="engineering">Engineering</SelectOption>
                          <SelectOption value="product">Product</SelectOption>
                          <SelectOption value="design">Design</SelectOption>
                          <SelectOption value="data">Data & Analytics</SelectOption>
                          <SelectOption value="sales">Sales</SelectOption>
                          <SelectOption value="marketing">Marketing</SelectOption>
                          <SelectOption value="customer success">Customer Success</SelectOption>
                          <SelectOption value="operations">Operations</SelectOption>
                          <SelectOption value="finance">Finance</SelectOption>
                          <SelectOption value="hr">Human Resources</SelectOption>
                          <SelectOption value="legal">Legal</SelectOption>
                          <SelectOption value="executive">Executive</SelectOption>
                        </Select>
                      </div>
                      <div>
                        <Label className="block text-xs mb-1.5">Analysis Window</Label>
                        <Select value={String(newDnaTimeWindow)} onValueChange={(val) => setNewDnaTimeWindow(Number(val))}>
                          {TIME_WINDOWS.map(tw => (
                            <SelectOption key={tw.value} value={String(tw.value)}>{tw.label}</SelectOption>
                          ))}
                        </Select>
                      </div>
                    </div>

                    {/* Employee Search Limit - Standard Input */}
                    <div className="space-y-1.5">
                      <Label className="text-sm font-medium text-charcoal dark:text-gray-100">
                        Employee Search Limit
                      </Label>
                      <div className="flex items-center gap-3">
                        <Input
                          type="number"
                          min={5}
                          max={100}
                          value={newDnaEmployeeLimit}
                          onChange={(e) => {
                            const val = parseInt(e.target.value);
                            if (!isNaN(val)) {
                              setNewDnaEmployeeLimit(val);
                            } else if (e.target.value === '') {
                              setNewDnaEmployeeLimit(5);
                            }
                          }}
                          onBlur={(e) => {
                            const val = parseInt(e.target.value) || 50;
                            setNewDnaEmployeeLimit(Math.min(100, Math.max(5, val)));
                          }}
                          className="w-24"
                        />
                        <span className="text-sm text-gray-500 dark:text-gray-400">employees</span>
                      </div>
                      <p className="text-xs text-gray-400 dark:text-gray-500">Maximum employees to analyze (5-100)</p>
                    </div>

                    <Alert variant="info" hideIcon className="text-xs">
                      This will search for up to <span className="font-medium">{newDnaEmployeeLimit}</span> employees at{' '}
                      <span className="font-medium">{newDnaCompany || 'the company'}</span>{' '}
                      {newDnaRole ? (
                        <>in <span className="font-medium capitalize">{newDnaRole}</span></>
                      ) : (
                        <>across <span className="font-medium">all departments</span></>
                      )}{' '}
                      who have been there within the past <span className="font-medium">{TIME_WINDOWS.find(t => t.value === newDnaTimeWindow)?.label}</span>.
                    </Alert>

                    {/* Loading State */}
                    {isCreatingDna && (
                      <div className="p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-xl">
                        <div className="flex items-center gap-3">
                          <Spinner size="md" variant="primary" />
                          <div>
                            <p className="text-sm font-medium text-charcoal dark:text-gray-100">Searching for employees...</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">This may take a moment while we query our data sources</p>
                          </div>
                        </div>
                      </div>
                    )}

                    <Button
                      onClick={handleCreateDna}
                      disabled={!canCreateDna || isCreatingDna}
                      className="w-full"
                    >
                      {isCreatingDna && <Spinner size="xs" variant="white" className="mr-2" />}
                      {isCreatingDna ? 'Searching employees...' : 'Create Company DNA'}
                    </Button>
                      </>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Job Description Form */}
            {activeSection === 'job-description' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Job Description</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Provide the job requirements to match candidates against</p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['job-description'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['job-description'] ? 'bg-green-500' : 'bg-amber-500'}`} />
                    {completionState['job-description'] ? 'Saved' : 'Required'}
                  </span>
                </div>

                {/* Mode Selector */}
                <Tabs value={jobDescriptionMode} onValueChange={(v) => setJobDescriptionMode(v as JobDescriptionMode)} defaultValue="select">
                  <TabsList variant="underline">
                    <TabsTrigger value="select" variant="underline">
                      <BriefcaseIcon className="w-4 h-4 mr-1.5" />
                      Select from ATS
                    </TabsTrigger>
                    <TabsTrigger value="upload" variant="underline">
                      <CloudArrowUpIcon className="w-4 h-4 mr-1.5" />
                      Upload PDF
                    </TabsTrigger>
                    <TabsTrigger value="paste" variant="underline">
                      <DocumentTextIcon className="w-4 h-4 mr-1.5" />
                      Paste Text
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                {/* Select from ATS */}
                {jobDescriptionMode === 'select' && (
                  <div className="space-y-3">
                    {!isAtsComplete ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                        <ServerStackIcon className="w-8 h-8 mx-auto mb-3 opacity-50" />
                        <p className="font-medium text-charcoal dark:text-gray-100 mb-1">No ATS Connection Selected</p>
                        <p>Select an ATS connection above to browse open positions</p>
                      </div>
                    ) : isLoadingJobs ? (
                      <div className="flex items-center justify-center py-8 text-gray-500 dark:text-gray-400">
                        <Spinner size="sm" variant="primary" className="mr-2" />
                        Loading open positions...
                      </div>
                    ) : atsJobs.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                        <BriefcaseIcon className="w-8 h-8 mx-auto mb-3 opacity-50" />
                        <p className="font-medium text-charcoal dark:text-gray-100 mb-1">No Open Positions Found</p>
                        <p>No open positions were found in your ATS. Try refreshing or check your ATS configuration.</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {/* Search Input */}
                        <div className="relative">
                          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 z-10" />
                          <Input
                            type="text"
                            value={jobSearchQuery}
                            onChange={(e) => setJobSearchQuery(e.target.value)}
                            placeholder="Search positions..."
                            className="pl-9"
                          />
                          {jobSearchQuery && (
                            <button
                              onClick={() => setJobSearchQuery('')}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
                            >
                              <XMarkIcon className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                        
                        {/* Filtered Jobs List */}
                        <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
                          {(() => {
                            const filteredJobs = atsJobs.filter(job => {
                              if (!jobSearchQuery.trim()) return true;
                              const query = jobSearchQuery.toLowerCase();
                              return (
                                job.name?.toLowerCase().includes(query) ||
                                job.department?.toLowerCase().includes(query)
                              );
                            });
                            
                            if (filteredJobs.length === 0) {
                              return (
                                <div className="text-center py-4 text-gray-500 dark:text-gray-400 text-sm">
                                  No positions match "{jobSearchQuery}"
                                </div>
                              );
                            }
                            
                            return filteredJobs.map((job) => (
                              <button
                                key={job.id}
                                onClick={async () => {
                                  setSelectedJobId(job.id);
                                  setSelectedJobName(job.name);
                                  try {
                                    const response = await AXIOS_INSTANCE.get(`/api/connectors/${atsConnectionId}/jobs/${job.id}`);
                                    if (response.data?.description) {
                                      setJobDescription(response.data.description);
                                    }
                                  } catch (err) {
                                    console.error('Failed to fetch job description:', err);
                                  }
                                }}
                                className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-xl border transition-colors ${
                                  selectedJobId === job.id
                                    ? 'bg-eliza-red/10 border-eliza-red text-charcoal dark:text-gray-100'
                                    : 'bg-gray-50 dark:bg-dark-surface-2 border-gray-200 dark:border-dark-border text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-surface hover:text-charcoal dark:hover:text-gray-100'
                                }`}
                              >
                                <div className="flex items-center gap-2">
                                  <BriefcaseIcon className="w-4 h-4" />
                                  <span>{job.name}</span>
                                </div>
                                {job.department && (
                                  <span className="text-xs text-gray-500 dark:text-gray-400">{job.department}</span>
                                )}
                                {selectedJobId === job.id && (
                                  <CheckIcon className="w-4 h-4 text-eliza-red" />
                                )}
                              </button>
                            ));
                          })()}
                        </div>
                        
                        {/* Results count */}
                        <div className="text-xs text-gray-500 dark:text-gray-400 text-right">
                          {jobSearchQuery ? (
                            <>Showing {atsJobs.filter(j => j.name?.toLowerCase().includes(jobSearchQuery.toLowerCase()) || j.department?.toLowerCase().includes(jobSearchQuery.toLowerCase())).length} of {atsJobs.length} positions</>
                          ) : (
                            <>{atsJobs.length} open positions</>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Upload PDF */}
                {jobDescriptionMode === 'upload' && (
                  <div className="space-y-3">
                    <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-300 dark:border-dark-border rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors">
                      <div className="flex flex-col items-center justify-center pt-5 pb-6">
                        {isUploadingFile ? (
                          <Spinner size="lg" variant="primary" className="mb-2" />
                        ) : (
                          <CloudArrowUpIcon className="w-8 h-8 text-gray-400 dark:text-gray-500 mb-2" />
                        )}
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {isUploadingFile ? 'Extracting text...' : 'Click to upload a job description PDF'}
                        </p>
                      </div>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx,.txt"
                        onChange={handleFileUpload}
                        className="hidden"
                        disabled={isUploadingFile}
                      />
                    </label>
                    {jobDescription && (
                      <p className="text-xs text-green-500 flex items-center gap-1">
                        <CheckCircleIcon className="w-4 h-4" />
                        Job description extracted successfully
                      </p>
                    )}
                  </div>
                )}

                {/* Paste Text */}
                {jobDescriptionMode === 'paste' && (
                  <Textarea
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    placeholder="Paste the job description here..."
                    className="h-48"
                    autoFocus
                  />
                )}
              </div>
            )}

            {/* Candidate Source Details (Department Selection or Resume Upload) */}
            {activeSection === 'candidate-source' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Candidate Source</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Choose where to find candidates for this role</p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['candidate-source'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['candidate-source'] ? 'bg-green-500' : 'bg-amber-500'}`} />
                    {completionState['candidate-source'] ? 'Saved' : 'Required'}
                  </span>
                </div>

                {/* Mode Selector */}
                <Tabs value={candidateSourceMode} onValueChange={(v) => setCandidateSourceMode(v as CandidateSourceMode)} defaultValue="ats">
                  <TabsList variant="underline">
                    <TabsTrigger value="ats" variant="underline">
                      <ServerStackIcon className="w-4 h-4 mr-1.5" />
                      From ATS
                    </TabsTrigger>
                    <TabsTrigger value="upload" variant="underline">
                      <CloudArrowUpIcon className="w-4 h-4 mr-1.5" />
                      Upload Resumes
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                {/* ATS Mode - Department Selection */}
                {candidateSourceMode === 'ats' && (
                  <>
                    {!isAtsComplete ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                        <ServerStackIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p className="font-medium text-charcoal dark:text-gray-100 mb-1">No ATS Connection Selected</p>
                        <p>Select an ATS connection above to browse departments, or switch to "Upload Resumes" mode</p>
                      </div>
                    ) : isLoadingDepartments ? (
                      <div className="flex items-center justify-center py-8 text-gray-500 dark:text-gray-400">
                        <Spinner size="sm" variant="primary" className="mr-2" />
                        Loading departments...
                      </div>
                    ) : atsDepartments.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                        No departments found in your ATS
                      </div>
                    ) : (
                      <>
                        {/* Historical Candidates Toggle - AT TOP so counts reflect this setting */}
                        <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border rounded-xl">
                          <Checkbox
                            checked={includeHistoricalCandidates}
                            onChange={(e) => setIncludeHistoricalCandidates(e.target.checked)}
                            label="Include candidates from closed positions"
                            description="Also count candidates who applied to jobs that have since been filled or closed"
                          />
                          
                          {/* Lookback Period */}
                          {includeHistoricalCandidates && (
                            <div className="mt-3 ml-7 flex items-center gap-2">
                              <ClockIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                              <span className="text-xs text-gray-500 dark:text-gray-400">Closed within</span>
                              <Select 
                                value={String(historicalLookbackDays)} 
                                onValueChange={(val) => setHistoricalLookbackDays(Number(val))}
                                className="w-auto"
                              >
                                <SelectOption value="90">3 months</SelectOption>
                                <SelectOption value="180">6 months</SelectOption>
                                <SelectOption value="270">9 months</SelectOption>
                                <SelectOption value="365">12 months (1 year)</SelectOption>
                                <SelectOption value="456">15 months</SelectOption>
                                <SelectOption value="548">18 months</SelectOption>
                                <SelectOption value="639">21 months</SelectOption>
                                <SelectOption value="730">24 months (2 years)</SelectOption>
                                <SelectOption value="821">27 months</SelectOption>
                                <SelectOption value="913">30 months</SelectOption>
                                <SelectOption value="1004">33 months</SelectOption>
                                <SelectOption value="1095">36 months (3 years)</SelectOption>
                              </Select>
                            </div>
                          )}
                        </div>

                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          Select which departments' candidates to include in this analysis.
                        </p>

                        {/* Quick Actions */}
                        <div className="flex gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedDepartmentIds(atsDepartments.map(d => d.id));
                              setSelectedDepartmentNames(atsDepartments.map(d => d.name));
                            }}
                            className="text-xs"
                          >
                            Select all
                          </Button>
                          <span className="text-gray-400 dark:text-gray-500">·</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedDepartmentIds([]);
                              setSelectedDepartmentNames([]);
                            }}
                            className="text-xs"
                          >
                            Clear all
                          </Button>
                        </div>

                        {/* Department List */}
                        <div className="space-y-1.5 max-h-[240px] overflow-y-auto">
                          {atsDepartments.map((dept) => {
                            const isSelected = selectedDepartmentIds.includes(dept.id);
                            return (
                              <button
                                key={dept.id}
                                onClick={() => {
                                  if (isSelected) {
                                    setSelectedDepartmentIds(prev => prev.filter(d => d !== dept.id));
                                    setSelectedDepartmentNames(prev => prev.filter(n => n !== dept.name));
                                  } else {
                                    setSelectedDepartmentIds(prev => [...prev, dept.id]);
                                    setSelectedDepartmentNames(prev => [...prev, dept.name]);
                                  }
                                }}
                                className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-xl border transition-colors ${
                                  isSelected
                                    ? 'bg-eliza-red/10 border-eliza-red text-charcoal dark:text-gray-100'
                                    : 'bg-gray-50 dark:bg-dark-surface-2 border-gray-200 dark:border-dark-border text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-dark-surface hover:text-charcoal dark:hover:text-gray-100'
                                }`}
                              >
                                <div className="flex items-center gap-2">
                                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                                    isSelected ? 'bg-eliza-red border-eliza-red' : 'border-gray-300 dark:border-dark-border'
                                  }`}>
                                    {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                                  </div>
                                  <span>{dept.name}</span>
                                </div>
                                {dept.candidateCount !== undefined && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-dark-surface text-gray-500 dark:text-gray-400">
                                    {dept.candidateCount} candidate{dept.candidateCount !== 1 ? 's' : ''}
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>

                        {/* Selection Summary */}
                        {selectedDepartmentIds.length > 0 && (
                          <Alert variant="info" hideIcon className="text-xs">
                            <span className="font-medium">{selectedDepartmentIds.length}</span> department{selectedDepartmentIds.length !== 1 ? 's' : ''} selected
                          </Alert>
                        )}
                      </>
                    )}
                  </>
                )}

                {/* Upload Mode - Resume Upload */}
                {candidateSourceMode === 'upload' && (
                  <div className="space-y-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Upload resume files to analyze. Supported formats: PDF, DOC, DOCX.
                    </p>

                    {/* Upload Area */}
                    <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-300 dark:border-dark-border rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors">
                      <div className="flex flex-col items-center justify-center pt-5 pb-6">
                        {isUploadingResumes ? (
                          <Spinner size="lg" variant="primary" className="mb-2" />
                        ) : (
                          <CloudArrowUpIcon className="w-8 h-8 text-gray-400 dark:text-gray-500 mb-2" />
                        )}
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {isUploadingResumes ? 'Uploading resumes...' : 'Click to upload resumes (PDF, DOC, DOCX)'}
                        </p>
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                          You can select multiple files
                        </p>
                      </div>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx"
                        multiple
                        onChange={async (e) => {
                          const files = e.target.files;
                          if (!files || files.length === 0) return;

                          setIsUploadingResumes(true);
                          
                          // Add files to state with pending status
                          const newResumes: UploadedResume[] = Array.from(files).map(file => ({
                            file,
                            name: file.name,
                            status: 'uploading' as const,
                          }));
                          
                          setUploadedResumes(prev => [...prev, ...newResumes]);

                          // Upload each file
                          for (const resume of newResumes) {
                            try {
                              const formData = new FormData();
                              formData.append('file', resume.file);

                              await AXIOS_INSTANCE.post('/api/document-parsing/upload-resume', formData, {
                                headers: { 'Content-Type': 'multipart/form-data' },
                              });

                              setUploadedResumes(prev => prev.map(r => 
                                r.name === resume.name ? { ...r, status: 'uploaded' as const } : r
                              ));
                            } catch (err: any) {
                              setUploadedResumes(prev => prev.map(r => 
                                r.name === resume.name 
                                  ? { ...r, status: 'error' as const, error: err.response?.data?.detail || 'Upload failed' } 
                                  : r
                              ));
                            }
                          }

                          setIsUploadingResumes(false);
                          e.target.value = ''; // Reset input
                        }}
                        className="hidden"
                        disabled={isUploadingResumes}
                      />
                    </label>

                    {/* Uploaded Resumes List */}
                    {uploadedResumes.length > 0 && (
                      <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
                        {uploadedResumes.map((resume, idx) => (
                          <div
                            key={`${resume.name}-${idx}`}
                            className={`flex items-center justify-between px-3 py-2 text-sm rounded-xl border ${
                              resume.status === 'uploaded' 
                                ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800/50' 
                                : resume.status === 'error'
                                  ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800/50'
                                  : 'bg-white dark:bg-dark-surface border-gray-200 dark:border-dark-border'
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              {resume.status === 'uploading' && (
                                <Spinner size="xs" variant="primary" />
                              )}
                              {resume.status === 'uploaded' && (
                                <CheckCircleIcon className="w-4 h-4 text-green-500 flex-shrink-0" />
                              )}
                              {resume.status === 'error' && (
                                <ExclamationCircleIcon className="w-4 h-4 text-red-500 flex-shrink-0" />
                              )}
                              <span className="truncate text-charcoal dark:text-gray-100">{resume.name}</span>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              onClick={() => setUploadedResumes(prev => prev.filter((_, i) => i !== idx))}
                              className="text-gray-400 hover:text-red-500 ml-2"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Upload Summary */}
                    {uploadedResumes.length > 0 && (
                      <Alert variant="info" hideIcon className="text-xs">
                        <span className="font-medium">
                          {uploadedResumes.filter(r => r.status === 'uploaded').length}
                        </span> of {uploadedResumes.length} resume{uploadedResumes.length !== 1 ? 's' : ''} uploaded successfully
                      </Alert>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Ideal Candidate Form */}
            {activeSection === 'ideal-candidate' && (
              <div className="animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-medium text-charcoal dark:text-gray-100">Ideal Candidate</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Brief us like you would a headhunter</p>
                  </div>
                  <span className={`text-xs flex items-center gap-1.5 px-2 py-0.5 rounded-full flex-shrink-0 ${
                    completionState['ideal-candidate'] 
                      ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
                      : 'text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${completionState['ideal-candidate'] ? 'bg-green-500' : 'bg-gray-400'}`} />
                    {completionState['ideal-candidate'] ? 'Saved' : 'Optional'}
                  </span>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  {/* Must Haves */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Must-Haves</Label>
                    <Textarea
                      value={idealMustHaves}
                      onChange={(e) => setIdealMustHaves(e.target.value)}
                      placeholder="Non-negotiable requirements...&#10;e.g., 5+ years Python, production ML systems, AWS certified"
                      className="h-24"
                    />
                  </div>
                  
                  {/* Nice to Haves */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Nice-to-Haves</Label>
                    <Textarea
                      value={idealNiceToHaves}
                      onChange={(e) => setIdealNiceToHaves(e.target.value)}
                      placeholder="Preferred but not required...&#10;e.g., startup experience, open source contributions, PhD"
                      className="h-24"
                    />
                  </div>
                  
                  {/* Dealbreakers */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Dealbreakers</Label>
                    <Textarea
                      value={idealDealbreakers}
                      onChange={(e) => setIdealDealbreakers(e.target.value)}
                      placeholder="Automatic disqualifiers...&#10;e.g., job hoppers (<1yr tenure), no remote experience"
                      className="h-24"
                    />
                  </div>
                  
                  {/* Personality & Culture Fit */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">Personality & Culture Fit</Label>
                    <Textarea
                      value={idealPersonalityTraits}
                      onChange={(e) => setIdealPersonalityTraits(e.target.value)}
                      placeholder="Soft skills & cultural traits...&#10;e.g., strong communicator, self-starter, thrives in ambiguity"
                      className="h-24"
                    />
                  </div>
                  
                  {/* Hiring Manager Notes - Full Width */}
                  <div className="col-span-2 space-y-1.5">
                    <Label className="text-xs">Hiring Manager Notes</Label>
                    <Textarea
                      value={idealHiringManagerNotes}
                      onChange={(e) => setIdealHiringManagerNotes(e.target.value)}
                      placeholder="Any additional context for the search...&#10;e.g., 'We've had great success with ex-Stripe engineers. The team is small and scrappy, so someone who needs a lot of structure won't thrive. Bonus if they've worked on payment systems or fraud detection.'"
                      className="h-20"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Empty State */}
            {!activeSection && (
              <div className="flex items-center justify-center h-56 text-gray-400 dark:text-gray-500 text-sm">
                Select a configuration option above
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <Alert variant="error" onDismiss={() => setError(null)} className="mt-4">
              {error}
            </Alert>
          )}
            </ModalBody>

            {/* Floating Actions - inside content area only */}
            <ModalFloatingActions gradientHeight="lg">
              <Button
                variant="outline"
                onClick={() => handleSave(false)}
                disabled={isSaving || !name.trim()}
              >
                Save Draft
              </Button>
              <Button
                onClick={() => handleSave(true)}
                disabled={isSaving || !canRun}
              >
                {isSaving && <Spinner size="xs" variant="white" className="mr-2" />}
                {isSaving ? 'Saving...' : 'Save & Run'}
              </Button>
            </ModalFloatingActions>
          </div>
        </div>
      </ModalContent>

      {/* Delete Confirmation Modal */}
      <Modal open={!!deleteConfirmation} onClose={() => setDeleteConfirmation(null)}>
        <ModalContent size="md">
          <ModalHeader showCloseButton={false}>
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-50 dark:bg-red-900/30 flex items-center justify-center">
                <TrashIcon className="w-5 h-5 text-red-500" />
              </div>
              <div className="flex-1">
                <ModalTitle>
                  Delete {deleteConfirmation?.type === 'dna' ? 'Company DNA' : 'Blueprint'}?
                </ModalTitle>
                <ModalDescription>
                  Are you sure you want to delete <span className="font-medium text-charcoal dark:text-white">"{deleteConfirmation?.label}"</span>? 
                  This action cannot be undone.
                </ModalDescription>
              </div>
            </div>
          </ModalHeader>
          
          <ModalFooter>
            <Button
              variant="ghost"
              onClick={() => setDeleteConfirmation(null)}
              disabled={isDeleting}
            >
              Go back
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={isDeleting}
            >
              {isDeleting && <Spinner size="xs" variant="white" className="mr-2" />}
              {isDeleting ? 'Deleting...' : 'Yes, delete'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Modal>
  );
}

// Attached Dropdown Component (uses DS colors)
function AttachedDropdown({
  items,
  selectedId,
  onSelect,
  onCreateNew,
  onClear,
  onDelete,
  emptyMessage = 'No items available',
  createNewLabel = 'Create new',
  searchPlaceholder = 'Search...',
  alignRight = false,
}: {
  items: { id: number; label: string; sublabel?: string }[];
  selectedId?: number;
  onSelect: (id: number, label: string) => void;
  onCreateNew: () => void;
  onClear?: () => void;
  onDelete?: (id: number, label: string) => void;
  emptyMessage?: string;
  createNewLabel?: string;
  searchPlaceholder?: string;
  alignRight?: boolean;
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredItemId, setHoveredItemId] = useState<number | null>(null);
  
  // Filter items based on search
  const filteredItems = items.filter(item => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      item.label?.toLowerCase().includes(query) ||
      item.sublabel?.toLowerCase().includes(query)
    );
  });

  // Calculate width based on longest label
  const maxLabelLength = Math.max(
    ...items.map(i => (i.label?.length || 0) + (i.sublabel?.length || 0)),
    20 // minimum
  );
  const dynamicWidth = Math.min(Math.max(280, maxLabelLength * 8 + 80), 500);

  return (
    <div
      className={`absolute top-full mt-1 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-2xl z-[100] overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150 ${alignRight ? 'right-0' : 'left-0'}`}
      style={{ width: `${dynamicWidth}px`, minWidth: '280px', maxWidth: '500px' }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Search Input */}
      <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full pl-8 pr-2 py-1.5 text-xs bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg text-charcoal dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-eliza-red focus:ring-1 focus:ring-eliza-red/20"
            autoFocus
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
            >
              <XMarkIcon className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
      
      <div className="max-h-60 overflow-y-auto bg-white dark:bg-dark-surface">
        {/* Create New Option */}
        <button
          onClick={onCreateNew}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-eliza-red hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          {createNewLabel}
        </button>

        {/* Clear Selection Option - only show if something is selected */}
        {selectedId && onClear && (
          <button
            onClick={onClear}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-500/80 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-500 transition-colors border-b border-gray-200 dark:border-dark-border"
          >
            <XMarkIcon className="w-4 h-4" />
            Clear selection
          </button>
        )}

        {filteredItems.length === 0 ? (
          <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400 text-center">
            {searchQuery ? `No results for "${searchQuery}"` : emptyMessage}
          </div>
        ) : (
          filteredItems.map((item, index) => (
            <div
              key={item.id}
              className={`
                w-full flex items-center justify-between px-3 py-2 text-sm transition-colors relative group
                ${selectedId === item.id
                  ? 'bg-eliza-red/10 text-charcoal dark:text-gray-100'
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-gray-100'
                }
              `}
              onMouseEnter={() => setHoveredItemId(item.id)}
              onMouseLeave={() => setHoveredItemId(null)}
            >
              <button
                onClick={() => onSelect(item.id, item.label)}
                className="flex items-center gap-2 min-w-0 flex-1 text-left"
              >
                <span className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                  {selectedId === item.id && <CheckIcon className="w-4 h-4 text-eliza-red" />}
                </span>
                <span className="truncate">{item.label}</span>
              </button>
              <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                {/* Show sublabel or delete button on hover */}
                {onDelete && hoveredItemId === item.id ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(item.id, item.label);
                    }}
                    className="p-1 text-red-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                    title="Delete"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                ) : (
                  <span className="text-xs text-gray-400 dark:text-gray-500">{item.sublabel || (index + 1)}</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      
      {/* Results count */}
      {searchQuery && filteredItems.length > 0 && (
        <div className="px-3 py-1.5 border-t border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2 text-[10px] text-gray-500 dark:text-gray-400">
          {filteredItems.length} of {items.length} results
        </div>
      )}
    </div>
  );
}

// Department Dropdown Component (multi-select, uses DS colors)
function DepartmentDropdown({
  departments,
  selectedIds,
  isLoading,
  onToggle,
  onSelectAll,
  onClearAll,
  onClose,
}: {
  departments: ATSDepartment[];
  selectedIds: number[];
  isLoading: boolean;
  onToggle: (id: number, name: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  onClose: () => void;
}) {
  const [searchQuery, setSearchQuery] = useState('');
  
  // Filter departments based on search
  const filteredDepartments = departments.filter(dept => {
    if (!searchQuery.trim()) return true;
    return dept.name?.toLowerCase().includes(searchQuery.toLowerCase());
  });

  // Calculate width based on longest department name + badge width
  const maxNameLength = Math.max(
    ...departments.map(d => d.name?.length || 0),
    20 // minimum
  );
  // Add extra space for the position count badge
  const dynamicWidth = Math.min(Math.max(340, maxNameLength * 8 + 140), 550);

  return (
    <div
      className="absolute top-full right-0 mt-1 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-2xl z-[100] overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150"
      style={{ width: `${dynamicWidth}px`, minWidth: '280px', maxWidth: '500px' }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Search Input */}
      <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search departments..."
            className="w-full pl-8 pr-2 py-1.5 text-xs bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg text-charcoal dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-eliza-red focus:ring-1 focus:ring-eliza-red/20"
            autoFocus
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300"
            >
              <XMarkIcon className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
      
      <div className="px-3 py-1.5 border-b border-gray-200 dark:border-dark-border flex items-center justify-between bg-gray-50 dark:bg-dark-surface-2">
        <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Select departments</span>
        <div className="flex gap-2">
          <button onClick={onSelectAll} className="text-[10px] text-eliza-red hover:underline">All</button>
          <button onClick={onClearAll} className="text-[10px] text-eliza-red hover:underline">None</button>
        </div>
      </div>
      <div className="max-h-52 overflow-y-auto bg-white dark:bg-dark-surface">
        {isLoading ? (
          <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400 text-center flex items-center justify-center gap-2">
            <Spinner size="xs" variant="primary" />
            Loading...
          </div>
        ) : filteredDepartments.length === 0 ? (
          <div className="px-3 py-4 text-sm text-gray-500 dark:text-gray-400 text-center">
            {searchQuery ? `No results for "${searchQuery}"` : 'No departments found'}
          </div>
        ) : (
          filteredDepartments.map((dept) => {
            const isSelected = selectedIds.includes(dept.id);
            return (
              <button
                key={dept.id}
                onClick={() => onToggle(dept.id, dept.name)}
                className={`
                  w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors
                  ${isSelected
                    ? 'bg-eliza-red/10 text-charcoal dark:text-gray-100'
                    : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-surface-2 hover:text-charcoal dark:hover:text-gray-100'
                  }
                `}
              >
                <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                  isSelected ? 'bg-eliza-red border-eliza-red' : 'border-gray-300 dark:border-dark-border bg-white dark:bg-dark-surface'
                }`}>
                  {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                </div>
                <span className="truncate flex-1 text-left">{dept.name}</span>
                {dept.candidateCount !== undefined && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full flex-shrink-0 ${
                    dept.candidateCount > 0 
                      ? 'bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20' 
                      : 'bg-gray-100 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400'
                  }`}>
                    {dept.candidateCount} {dept.candidateCount === 1 ? 'candidate' : 'candidates'}
                  </span>
                )}
              </button>
            );
          })
        )}
      </div>
      
      {/* Footer with count */}
      <div className="px-3 py-1.5 border-t border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2 flex items-center justify-between">
        <span className="text-[10px] text-gray-500 dark:text-gray-400">
          {selectedIds.length} selected
        </span>
        {searchQuery && filteredDepartments.length > 0 && (
          <span className="text-[10px] text-gray-500 dark:text-gray-400">
            {filteredDepartments.length} of {departments.length}
          </span>
        )}
      </div>
    </div>
  );
}

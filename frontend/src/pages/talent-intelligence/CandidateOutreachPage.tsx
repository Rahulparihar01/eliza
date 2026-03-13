/**
 * Search Results Page (formerly Candidate Outreach)
 * 
 * Allows hiring managers to:
 * - Review top scored candidates from completed analyses
 * - Preview and customize pre-written emails
 * - Send outreach emails to candidates
 * - Track outreach status
 * - Filter and manage candidate list
 * - Provide feedback on recommendations
 */

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import {
  EnvelopeIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  UserGroupIcon,
  BriefcaseIcon,
  PhoneIcon,
  MapPinIcon,
  CheckIcon,
  XMarkIcon,
  PaperAirplaneIcon,
  PencilIcon,
  BuildingOfficeIcon,
  FunnelIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  CalendarIcon,
  AdjustmentsHorizontalIcon,
  SparklesIcon,
  ChartBarIcon,
  UsersIcon,
  HandThumbUpIcon,
  PlusIcon,
  DocumentTextIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarSolid } from '@heroicons/react/24/solid';
import { AXIOS_INSTANCE } from '../../services/api-client';
import CandidateFeedbackModal from '../../components/talent-intelligence/CandidateFeedbackModal';

// DS Components
import { 
  Button, 
  Spinner, 
  Alert, 
  Chip, 
  Input, 
  Badge, 
  DateRangePicker, 
  Page, 
  PageHeader,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  Label,
  Textarea,
  SliderInput,
  type DateRange 
} from '../../components/ui';

// Analysis Config interface for filter dropdown
interface AnalysisConfigOption {
  id: number;
  name: string;
  last_analysis_id: string | null;
  last_run_at: string | null;
}

// Score dimension filters
interface ScoreFilters {
  skill_alignment: number;
  experience_fit: number;
  trajectory_match: number;
  company_background: number;
  organizational_fit: number;
  overall: number;
}

// Filter Chip Component - wraps DS Chip with filter-specific props
const FilterChip: React.FC<{
  icon: React.ReactNode;
  label: string;
  isActive: boolean;
  hasValue: boolean;
  onClick: (e: React.MouseEvent) => void;
}> = ({ icon, label, isActive, hasValue, onClick }) => (
  <Chip
    variant="pill"
    active={isActive}
    complete={hasValue && !isActive}
    showIcon={true}
    iconPosition="left"
    unselectedIcon={icon}
    selectedIcon={icon}
    completeIcon={icon}
    showChevron={true}
    maxLabelWidth={120}
    onClick={onClick}
  >
    {label}
  </Chip>
);

interface ScoredCandidate {
  id: string;
  score_id: number;  // The candidate_analysis_score.id for feedback
  analysis_id: string;
  analysis_name: string;
  analysis_date: string;
  name: string;
  email: string | null;
  phone: string | null;
  linkedin: string | null;
  location: string | null;
  current_title: string | null;
  current_company: string | null;
  score: number;
  rank: number;
  source: 'applicant' | 'previous_candidate' | 'market';
  highlights: string[];
  score_breakdown: any;
  confidence: number | null;
  outreach_status: 'pending' | 'scheduled' | 'sent' | 'rejected';
  greenhouse_id: number | null;
  greenhouse_profile_url: string | null;
  has_feedback?: boolean;  // Track if user has already provided feedback
}

interface CandidateWithEmail extends ScoredCandidate {
  prewrittenEmail: {
    subject: string;
    body: string;
  };
  scheduledFor?: string;
  _needsDefaultEmail?: boolean; // Internal flag to track if email needs generation
}

export default function CandidateOutreachPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const analysisIdParam = searchParams.get('analysis_id');
  
  const [candidates, setCandidates] = useState<CandidateWithEmail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'pending' | 'scheduled' | 'sent' | 'rejected'>('all');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'applicant' | 'previous_candidate' | 'market'>('all');
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateWithEmail | null>(null);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [isEditingEmail, setIsEditingEmail] = useState(false);
  const [emailSubject, setEmailSubject] = useState('');
  const [emailBody, setEmailBody] = useState('');
  
  // Template Selection State
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [showTemplatePickerDropdown, setShowTemplatePickerDropdown] = useState(false);
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [generatingEmail, setGeneratingEmail] = useState(false);
  const [selectedTemplateName, setSelectedTemplateName] = useState<string | null>(null);
  
  // Greenhouse profile lookup state
  const [loadingGreenhouseUrl, setLoadingGreenhouseUrl] = useState<string | null>(null);
  const [greenhouseNotFoundError, setGreenhouseNotFoundError] = useState<string | null>(null);

  // Advanced Filter State
  const [analysisConfigs, setAnalysisConfigs] = useState<AnalysisConfigOption[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [dateFilter, setDateFilter] = useState<DateRange>({ from: null, to: null });
  const [scoreFilters, setScoreFilters] = useState<ScoreFilters>({
    skill_alignment: 0,
    experience_fit: 0,
    trajectory_match: 0,
    company_background: 0,
    organizational_fit: 0,
    overall: 0,
  });
  const [activeFilterDropdown, setActiveFilterDropdown] = useState<string | null>(null);
  const [analysisSearchTerm, setAnalysisSearchTerm] = useState('');
  const filterRef = useRef<HTMLDivElement>(null);
  
  // Feedback Modal State
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  
  // Score details collapsed state (starts collapsed to focus on email)
  const [isScoreDetailsExpanded, setIsScoreDetailsExpanded] = useState(false);
  
  // Add to ATS State
  const [addingToATS, setAddingToATS] = useState<string | null>(null);
  const [addToATSResult, setAddToATSResult] = useState<{ success: boolean; message: string; greenhouseId?: number } | null>(null);
  const [showAddToATSConfirm, setShowAddToATSConfirm] = useState(false);
  const [feedbackCandidate, setFeedbackCandidate] = useState<CandidateWithEmail | null>(null);

  // Greenhouse maildrop address for email tracking/telemetry
  const GREENHOUSE_MAILDROP = 'maildrop@lily.greenhouse.io';
  
  // Company info for email templates (should come from settings in future)
  const COMPANY_NAME = 'Caylent';
  const SENDER_NAME = 'Hiring Team';
  const SENDER_TITLE = 'Talent Acquisition';

  // Load candidates and configs on mount
  useEffect(() => {
    loadScoredCandidates();
    loadEmailTemplates();
    loadAnalysisConfigs();
  }, [analysisIdParam]);

  // Sync selectedConfigId with URL analysis_id parameter
  // This ensures the filter dropdown shows the correct config when navigating from templates page
  useEffect(() => {
    if (analysisIdParam && analysisConfigs.length > 0) {
      // Find the config that has this analysis_id as its last_analysis_id
      const matchingConfig = analysisConfigs.find(
        cfg => cfg.last_analysis_id === analysisIdParam
      );
      if (matchingConfig) {
        setSelectedConfigId(matchingConfig.id);
      }
    } else if (!analysisIdParam) {
      // Clear the config filter if no analysis_id in URL
      setSelectedConfigId(null);
    }
  }, [analysisIdParam, analysisConfigs]);

  // Click outside handler for filter dropdowns
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
        setActiveFilterDropdown(null);
      }
    };
    if (activeFilterDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [activeFilterDropdown]);

  // Click outside handler for template picker dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('[data-template-picker]')) {
        setShowTemplatePickerDropdown(false);
      }
    };
    if (showTemplatePickerDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showTemplatePickerDropdown]);

  // Load analysis configs for filter dropdown
  const loadAnalysisConfigs = async () => {
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/talent/analysis-configs');
      setAnalysisConfigs(response.data.configs || []);
    } catch (err) {
      console.error('Failed to load analysis configs:', err);
    }
  };

  // Toggle filter dropdown
  const toggleFilterDropdown = (dropdown: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActiveFilterDropdown(activeFilterDropdown === dropdown ? null : dropdown);
  };

  // Format dimension name: skill_alignment -> Skill Alignment
  const formatDimensionName = (name: string): string => {
    return name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  // Get dimension score for a candidate
  const getDimensionScore = (candidate: CandidateWithEmail, dimension: string): number => {
    const dimensions = candidate.score_breakdown?.dimensions || [];
    const dim = dimensions.find((d: any) => d.dimension === dimension);
    return dim?.score || 0;
  };

  // Check if any advanced filters are active
  const hasActiveFilters = (): boolean => {
    return (
      selectedConfigId !== null ||
      sourceFilter !== 'all' ||
      dateFilter.from !== null ||
      dateFilter.to !== null ||
      scoreFilters.overall > 0 ||
      scoreFilters.skill_alignment > 0 ||
      scoreFilters.experience_fit > 0 ||
      scoreFilters.trajectory_match > 0 ||
      scoreFilters.company_background > 0 ||
      scoreFilters.organizational_fit > 0
    );
  };

  // Clear all filters
  const clearAllFilters = () => {
    setSelectedConfigId(null);
    setDateFilter({ from: null, to: null });
    setScoreFilters({
      skill_alignment: 0,
      experience_fit: 0,
      trajectory_match: 0,
      company_background: 0,
      organizational_fit: 0,
      overall: 0,
    });
    setSourceFilter('all');
    setSelectedFilter('all');
  };

  // Normalize source values from API to match our filter options
  const normalizeSource = (source: string | undefined | null): 'applicant' | 'previous_candidate' | 'market' => {
    if (!source) return 'market'; // Default to market if no source
    const normalized = source.toLowerCase().trim();
    
    // Handle various API formats
    if (normalized === 'applicant' || normalized === 'ats' || normalized === 'greenhouse') {
      return 'applicant';
    }
    if (normalized === 'previous_candidate' || normalized === 'previous' || normalized === 'historical') {
      return 'previous_candidate';
    }
    // Default to market for PDL, market, or unknown sources
    return 'market';
  };

  const loadScoredCandidates = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (analysisIdParam) {
        params.append('analysis_id', analysisIdParam);
      }
      params.append('page_size', '50');
      // auto_generate_emails=true (default) will generate emails using the default template
      // for any candidates that don't have one yet
      params.append('auto_generate_emails', 'true');
      
      // Use the new v2 API endpoint that queries normalized tables
      // The backend will auto-generate emails using the default template
      const response = await AXIOS_INSTANCE.get(`/api/v1/outreach/v2/candidates?${params.toString()}`);
      
      // Transform from v2 format (nested candidate + score) to CandidateWithEmail format
      const candidatesWithEmail: CandidateWithEmail[] = response.data.candidates.map((item: any, idx: number) => {
        const candidate = item.candidate;
        const score = item.score;
        
        // Build the flattened candidate object
        // Try to get the config name from the score data or look it up
        const configName = score.config_name || item.config_name || `Analysis ${score.analysis_id.slice(0, 8)}`;
        
        const flatCandidate: ScoredCandidate = {
          id: String(candidate.id),
          score_id: score.id,  // candidate_analysis_score.id for feedback
          analysis_id: score.analysis_id,
          analysis_name: configName,
          analysis_date: score.scored_at ? new Date(score.scored_at).toLocaleDateString() : '',
          name: candidate.full_name || candidate.email?.split('@')[0] || `Candidate ${idx + 1}`,
          email: candidate.email,
          phone: candidate.phone,
          linkedin: candidate.linkedin_url,
          location: candidate.location,
          current_title: candidate.current_title,
          current_company: candidate.current_company,
          score: score.overall_score,
          rank: score.rank_overall || idx + 1,
          source: normalizeSource(score.source),
          highlights: score.score_breakdown?.dimensions
            ?.filter((d: any) => d.score >= 70)
            ?.slice(0, 4)
            ?.map((d: any) => `${d.dimension}: ${d.score.toFixed(0)}`) || [],
          score_breakdown: score.score_breakdown,
          confidence: score.confidence,
          outreach_status: (score.outreach_status || 'pending') as 'pending' | 'scheduled' | 'sent' | 'rejected',
          greenhouse_id: candidate.greenhouse_id,
          greenhouse_profile_url: item.greenhouse_profile_url,
          has_feedback: score.has_feedback || false,
        };
        
        // Check if this candidate has a generated email from the default template
        const hasGeneratedEmail = score.generated_email_subject && score.generated_email_body;
        
        return {
          ...flatCandidate,
          prewrittenEmail: {
            // Use generated email if available, otherwise use fallback
            subject: score.generated_email_subject || `Opportunity at ${COMPANY_NAME} - ${flatCandidate.current_title || 'Exciting Role'}`,
            body: score.generated_email_body || generateDefaultEmail(flatCandidate),
          },
          // Track if no template was available (for UI indicator)
          _needsDefaultEmail: !hasGeneratedEmail,
        };
      });
      
      setCandidates(candidatesWithEmail);
    } catch (err: any) {
      console.error('Failed to load candidates:', err);
      setError(err?.response?.data?.detail || 'Failed to load candidates. Run an analysis to populate candidate data.');
    } finally {
      setLoading(false);
    }
  };

  const generateDefaultEmail = (candidate: ScoredCandidate): string => {
    const firstName = candidate.name.split(' ')[0];
    const hasCompany = candidate.current_company && candidate.current_company.trim() !== '';
    const hasTitle = candidate.current_title && candidate.current_title.trim() !== '';
    
    let backgroundLine = '';
    if (hasCompany && hasTitle) {
      backgroundLine = ` as ${candidate.current_title} at ${candidate.current_company}`;
    } else if (hasCompany) {
      backgroundLine = ` at ${candidate.current_company}`;
    } else if (hasTitle) {
      backgroundLine = ` as ${candidate.current_title}`;
    }

    return `Hi ${firstName},

I came across your profile and was impressed by your background${backgroundLine}. We have an exciting opportunity at ${COMPANY_NAME} that I think would be a great fit for your skills and experience.

I'd love to schedule a brief call to discuss this further. Would you be available for a 15-minute conversation this week?

Best regards,
${SENDER_NAME}
${SENDER_TITLE} at ${COMPANY_NAME}`;
  };
  
  // Fetch Greenhouse profile URL for a candidate
  const fetchGreenhouseProfileUrl = async (candidate: CandidateWithEmail) => {
    if (loadingGreenhouseUrl === candidate.id) return;
    
    setLoadingGreenhouseUrl(candidate.id);
    setGreenhouseNotFoundError(null);
    
    try {
      const response = await AXIOS_INSTANCE.post('/api/v1/outreach/greenhouse/profile-url', {
        candidate_email: candidate.email,
      });
      
      if (response.data.found && (response.data.greenhouse_profile_url || response.data.greenhouse_candidate_id)) {
        const greenhouseId = response.data.greenhouse_candidate_id;
        const greenhouseUrl = response.data.greenhouse_profile_url || (greenhouseId ? `https://app4.greenhouse.io/people/${greenhouseId}` : null);
        
        // Update candidate with Greenhouse profile URL and ID
        setCandidates((prev) =>
          prev.map((c) =>
            c.id === candidate.id
              ? {
                  ...c,
                  greenhouse_id: greenhouseId,
                  greenhouse_profile_url: greenhouseUrl,
                }
              : c
          )
        );
        
        // Update selected candidate if it's the same one
        if (selectedCandidate?.id === candidate.id) {
          setSelectedCandidate({
            ...selectedCandidate,
            greenhouse_id: greenhouseId,
            greenhouse_profile_url: greenhouseUrl,
          });
        }
      } else {
        setGreenhouseNotFoundError(`Candidate not found in Greenhouse. They may not have applied yet.`);
      }
    } catch (error: any) {
      console.error('Failed to fetch Greenhouse profile URL:', error);
      setGreenhouseNotFoundError(`Unable to search Greenhouse. Please check your connector configuration.`);
    } finally {
      setLoadingGreenhouseUrl(null);
    }
  };

  const loadEmailTemplates = async () => {
    setLoadingTemplates(true);
    
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/email-templates');
      setAvailableTemplates(response.data.templates || []);
    } catch (error) {
      console.error('Failed to load templates:', error);
    } finally {
      setLoadingTemplates(false);
    }
  };
  
  // Add market candidate to ATS (Greenhouse)
  const handleAddToATS = async (candidate: CandidateWithEmail) => {
    if (!candidate.analysis_id) {
      setAddToATSResult({ success: false, message: 'No analysis ID available for this candidate' });
      return;
    }
    
    setAddingToATS(candidate.id);
    setAddToATSResult(null);
    
    try {
      // Get the ATS connector ID from analysis configs
      const configResponse = await AXIOS_INSTANCE.get('/api/v1/talent/analysis-configs');
      const configs = configResponse.data?.configs || configResponse.data || [];
      
      // Find the config that ran this analysis
      const matchingConfig = configs.find((c: any) => c.last_analysis_id === candidate.analysis_id);
      
      if (!matchingConfig?.ats_connection_id) {
        setAddToATSResult({ success: false, message: 'No ATS connection found for this analysis. Please ensure the analysis was configured with an ATS connection.' });
        setAddingToATS(null);
        return;
      }
      
      const response = await AXIOS_INSTANCE.post('/api/v1/outreach/v2/candidates/add-to-ats', {
        candidate_id: parseInt(candidate.id),
        analysis_id: candidate.analysis_id,
        connector_id: matchingConfig.ats_connection_id,
      });
      
      if (response.data.success) {
        // Update the candidate in state with the new greenhouse_id
        const greenhouseId = response.data.greenhouse_candidate_id;
        const greenhouseUrl = response.data.greenhouse_profile_url;
        
        setCandidates((prev) =>
          prev.map((c) =>
            c.id === candidate.id
              ? {
                  ...c,
                  greenhouse_id: greenhouseId,
                  greenhouse_profile_url: greenhouseUrl,
                  source: 'applicant' as const, // They're now in the ATS
                }
              : c
          )
        );
        
        // Update selected candidate if it's the same one
        if (selectedCandidate?.id === candidate.id) {
          setSelectedCandidate({
            ...selectedCandidate,
            greenhouse_id: greenhouseId,
            greenhouse_profile_url: greenhouseUrl,
            source: 'applicant' as const,
          });
        }
        
        setAddToATSResult({
          success: true,
          message: `Successfully added ${candidate.name} to Greenhouse!`,
          greenhouseId,
        });
      } else {
        setAddToATSResult({
          success: false,
          message: response.data.error || response.data.message || 'Failed to add candidate to ATS',
        });
      }
    } catch (error: any) {
      console.error('Failed to add candidate to ATS:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to add candidate to ATS';
      setAddToATSResult({ success: false, message: errorMessage });
    } finally {
      setAddingToATS(null);
      setShowAddToATSConfirm(false);
    }
  };

  const handleApplyTemplate = async (templateId: number) => {
    if (!selectedCandidate) return;
    
    setGeneratingEmail(true);
    setShowTemplateSelector(false);
    
    try {
      // Build comprehensive candidate data for email generation
      // The backend uses these fields for variable substitution:
      // - full_name, first_name, name -> {{candidate_name}}, {{candidate_first_name}}
      // - job_title, role_title, current_title -> {{job_title}}, {{role_title}}
      // - job_company_name, current_company -> {{company_name}}, {{current_company}}
      // - location_name, location -> {{location}}
      // - skills -> {{skill}}, {{skills}}
      const candidateData = {
        id: selectedCandidate.id,
        full_name: selectedCandidate.name,
        name: selectedCandidate.name,
        first_name: selectedCandidate.name.split(' ')[0],
        email: selectedCandidate.email,
        location_name: selectedCandidate.location,
        location: selectedCandidate.location,
        job_title: selectedCandidate.current_title,
        role_title: selectedCandidate.current_title,
        current_title: selectedCandidate.current_title,
        job_company_name: selectedCandidate.current_company,
        current_company: selectedCandidate.current_company,
        // Extract skills from score breakdown if available
        skills: selectedCandidate.score_breakdown?.dimensions
          ?.filter((d: any) => d.dimension === 'skill_alignment')
          ?.flatMap((d: any) => d.evidence || [])
          ?.slice(0, 5) || [],
      };
      
      const response = await AXIOS_INSTANCE.post('/api/v1/email-templates/generate', {
        template_id: templateId,
        candidate_data: candidateData,
        force_regenerate: true,
      });
      
      setEmailSubject(response.data.subject);
      setEmailBody(response.data.body);
      
      setCandidates(prev => prev.map(c => 
        c.id === selectedCandidate.id 
          ? { ...c, prewrittenEmail: { subject: response.data.subject, body: response.data.body } }
          : c
      ));
      
      // Save the generated email to the new normalized tables
      try {
        await AXIOS_INSTANCE.post('/api/v1/outreach/v2/candidates/save-email', {
          candidate_id: parseInt(selectedCandidate.id),
          analysis_id: selectedCandidate.analysis_id,
          email_template_id: templateId,
          subject: response.data.subject,
          body: response.data.body,
        });
      } catch (saveError) {
        console.warn('Could not save email to candidate record:', saveError);
        // Don't fail the whole operation if save fails
      }
      
      window.alert('✅ Email generated from template!');
    } catch (error: any) {
      console.error('Failed to generate email:', error);
      const errorMsg = error?.response?.data?.detail || 'Failed to generate email';
      window.alert(`❌ ${errorMsg}`);
    } finally {
      setGeneratingEmail(false);
    }
  };

  // Filter candidates with all filter criteria
  const filteredCandidates = candidates.filter((c) => {
    // Status filter
    if (selectedFilter !== 'all' && c.outreach_status !== selectedFilter) return false;
    
    // Source filter
    if (sourceFilter !== 'all' && c.source !== sourceFilter) return false;
    
    // Analysis config filter
    if (selectedConfigId !== null) {
      const config = analysisConfigs.find(cfg => cfg.id === selectedConfigId);
      if (config && config.last_analysis_id && c.analysis_id !== config.last_analysis_id) {
        return false;
      }
    }
    
    // Date filter
    if (dateFilter.from) {
      const candidateDate = new Date(c.analysis_date);
      if (candidateDate < dateFilter.from) return false;
    }
    if (dateFilter.to) {
      const candidateDate = new Date(c.analysis_date);
      const endDate = new Date(dateFilter.to);
      endDate.setHours(23, 59, 59, 999); // Include entire end day
      if (candidateDate > endDate) return false;
    }
    
    // Overall score filter
    if (scoreFilters.overall > 0 && c.score < scoreFilters.overall) return false;
    
    // Dimension score filters
    if (scoreFilters.skill_alignment > 0 && getDimensionScore(c, 'skill_alignment') < scoreFilters.skill_alignment) return false;
    if (scoreFilters.experience_fit > 0 && getDimensionScore(c, 'experience_fit') < scoreFilters.experience_fit) return false;
    if (scoreFilters.trajectory_match > 0 && getDimensionScore(c, 'trajectory_match') < scoreFilters.trajectory_match) return false;
    if (scoreFilters.company_background > 0 && getDimensionScore(c, 'company_background') < scoreFilters.company_background) return false;
    if (scoreFilters.organizational_fit > 0 && getDimensionScore(c, 'organizational_fit') < scoreFilters.organizational_fit) return false;
    
    return true;
  });

  // Statistics
  const stats = {
    total: candidates.length,
    pending: candidates.filter((c) => c.outreach_status === 'pending').length,
    scheduled: candidates.filter((c) => c.outreach_status === 'scheduled').length,
    sent: candidates.filter((c) => c.outreach_status === 'sent').length,
    rejected: candidates.filter((c) => c.outreach_status === 'rejected').length,
    applicants: candidates.filter((c) => c.source === 'applicant').length,
    previous: candidates.filter((c) => c.source === 'previous_candidate').length,
    market: candidates.filter((c) => c.source === 'market').length,
  };

  // Get the default template for a candidate's source type
  const getDefaultTemplateForSource = (source: 'applicant' | 'previous_candidate' | 'market'): { name: string; isDefault: boolean } | null => {
    // Map candidate source to template category
    const categoryMap: Record<string, string> = {
      'applicant': 'applicant_followup',
      'previous_candidate': 'previous_candidate',
      'market': 'market_outreach',
    };
    
    const targetCategory = categoryMap[source];
    
    // Find the default template for this category
    const defaultTemplate = availableTemplates.find(
      t => t.category === targetCategory && t.is_default
    );
    
    if (defaultTemplate) {
      return { name: defaultTemplate.name, isDefault: true };
    }
    
    // Fallback: try to find any default template from related categories
    const fallbackCategories = ['applicant_followup', 'market_outreach', 'previous_candidate'];
    const anyDefault = availableTemplates.find(t => fallbackCategories.includes(t.category) && t.is_default);
    if (anyDefault) {
      return { name: anyDefault.name, isDefault: true };
    }
    
    return null;
  };

  const handleSelectCandidate = (candidate: CandidateWithEmail) => {
    setSelectedCandidate(candidate);
    setEmailSubject(candidate.prewrittenEmail.subject);
    setEmailBody(candidate.prewrittenEmail.body);
    setShowEmailModal(false);
    setIsEditingEmail(false);
    setGreenhouseNotFoundError(null);
    
    // Set the template name based on candidate source (unless already manually selected)
    if (!selectedTemplateName) {
      const defaultTemplate = getDefaultTemplateForSource(candidate.source);
      if (defaultTemplate) {
        setSelectedTemplateName(defaultTemplate.name);
      } else {
        setSelectedTemplateName(null); // Will show "No template selected"
      }
    }
    
    // Auto-fetch Greenhouse profile URL if not already loaded and candidate has email
    if (!candidate.greenhouse_profile_url && candidate.email && candidate.source === 'applicant') {
      fetchGreenhouseProfileUrl(candidate);
    }
  };

  const handleOpenEmailModal = () => {
    if (selectedCandidate) {
      setEmailSubject(selectedCandidate.prewrittenEmail.subject);
      setEmailBody(selectedCandidate.prewrittenEmail.body);
      setShowEmailModal(true);
    }
  };

  const handleSaveEmailChanges = () => {
    if (selectedCandidate) {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === selectedCandidate.id
            ? { ...c, prewrittenEmail: { subject: emailSubject, body: emailBody } }
            : c
        )
      );
      setSelectedCandidate({
        ...selectedCandidate,
        prewrittenEmail: { subject: emailSubject, body: emailBody },
      });
      setShowEmailModal(false);
    }
  };

  const handleSendEmail = async (candidateId: string) => {
    if (!selectedCandidate) return;
    
    const emailTo = encodeURIComponent(selectedCandidate.email || '');
    const emailCc = encodeURIComponent(GREENHOUSE_MAILDROP);
    const emailSubjectEncoded = encodeURIComponent(selectedCandidate.prewrittenEmail.subject);
    const emailBodyEncoded = encodeURIComponent(selectedCandidate.prewrittenEmail.body);
    
    // Use the Gmail compose URL format that works with authentication
    // The /u/0/ ensures it uses the primary account and authuser=0 handles multi-account scenarios
    const gmailComposeUrl = `https://mail.google.com/mail/u/0/?view=cm&fs=1&tf=1&to=${emailTo}&cc=${emailCc}&su=${emailSubjectEncoded}&body=${emailBodyEncoded}`;
    
    window.open(gmailComposeUrl, '_blank');
    
    // Update status in the new normalized tables
    try {
      await AXIOS_INSTANCE.post('/api/v1/outreach/v2/candidates/update-status', {
        candidate_id: parseInt(candidateId),
        analysis_id: selectedCandidate.analysis_id,
        status: 'sent',
      });
    } catch (error) {
      console.warn('Could not update outreach status:', error);
    }
    
    setCandidates((prev) =>
      prev.map((c) =>
        c.id === candidateId ? { ...c, outreach_status: 'sent' as const } : c
      )
    );
    
    window.alert(`✅ Gmail compose window opened for ${selectedCandidate.name}!\n\n📧 Greenhouse maildrop added to CC for tracking.`);
  };

  const handleScheduleEmail = (candidateId: string) => {
    const scheduledTime = window.prompt('Enter send time (e.g., "2025-10-24 10:00 AM PST"):');
    if (scheduledTime) {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candidateId
            ? { ...c, outreach_status: 'scheduled' as const, scheduledFor: scheduledTime }
            : c
        )
      );
      window.alert(`📅 Email scheduled for ${scheduledTime}`);
    }
  };

  const handleRejectCandidate = async (candidateId: string) => {
    if (window.confirm('Are you sure you want to reject this candidate match?')) {
      // Update status in the new normalized tables
      try {
        await AXIOS_INSTANCE.post('/api/v1/outreach/v2/candidates/update-status', {
          candidate_id: parseInt(candidateId),
          analysis_id: selectedCandidate?.analysis_id,
          status: 'rejected',
        });
      } catch (error) {
        console.warn('Could not update outreach status:', error);
      }
      
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candidateId ? { ...c, outreach_status: 'rejected' as const } : c
        )
      );
      setSelectedCandidate(null);
    }
  };

  if (loading) {
    return (
      <Page layout="full-width">
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center">
            <Spinner size="lg" className="mx-auto mb-4" />
            <p className="text-gray-500 dark:text-gray-400">Loading scored candidates...</p>
          </div>
        </div>
      </Page>
    );
  }

  if (error) {
    return (
      <Page layout="full-width">
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center max-w-md">
            <XCircleIcon className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-charcoal dark:text-gray-100 mb-2">Failed to Load Candidates</h2>
            <p className="text-gray-500 dark:text-gray-400 mb-4">{error}</p>
            <Button onClick={loadScoredCandidates}>
              Try Again
            </Button>
          </div>
        </div>
      </Page>
    );
  }

  if (candidates.length === 0) {
    return (
      <Page layout="full-width">
        <div className="flex flex-1 items-center justify-center">
          <div className="text-center max-w-md">
            <UserGroupIcon className="w-16 h-16 text-gray-400 dark:text-gray-500 mx-auto mb-4 opacity-50" />
            <h2 className="text-lg font-semibold text-charcoal dark:text-gray-100 mb-2">No Scored Candidates</h2>
            <p className="text-gray-500 dark:text-gray-400 mb-4">
              Run a talent analysis to score candidates and see them here for outreach.
            </p>
            <Button onClick={() => navigate('/talent/analysis-config?new=true')}>
              Start New Analysis
            </Button>
          </div>
        </div>
      </Page>
    );
  }

  return (
    <>
      <Page layout="full-width">
        {/* Page Header */}
        <PageHeader
          title="Search Results"
          description={`${stats.total} scored candidates from ${new Set(candidates.map(c => c.analysis_id)).size} analyses`}
          actions={
            <Button
              variant="outline"
              onClick={loadScoredCandidates}
              title="Refresh candidates"
            >
              <ArrowPathIcon className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          }
        />

        {/* Filter Bar */}
        <div ref={filterRef} className="flex-shrink-0 px-8 py-3 border-b border-gray-200 dark:border-dark-border">
          <div className="flex items-center gap-3">
            <FunnelIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
            <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider flex-shrink-0">Filters</span>
            
            <div className="flex items-center gap-2 flex-wrap flex-1">
                {/* Analysis Config Filter with Search */}
                <div className="relative">
                  <FilterChip
                    icon={<SparklesIcon className="w-3.5 h-3.5" />}
                    label={selectedConfigId ? (analysisConfigs.find(c => c.id === selectedConfigId)?.name || 'Analysis') : 'Analysis'}
                    isActive={activeFilterDropdown === 'config'}
                    hasValue={selectedConfigId !== null}
                    onClick={(e) => { 
                      toggleFilterDropdown('config', e);
                      if (activeFilterDropdown !== 'config') setAnalysisSearchTerm('');
                    }}
                  />
                  {activeFilterDropdown === 'config' && (
                    <div className="absolute top-full left-0 mt-1 w-80 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-xl z-50 overflow-hidden">
                      {/* Search Input */}
                      <div className="p-2 border-b border-gray-200 dark:border-dark-border">
                        <div className="relative">
                          <Input
                            type="text"
                            placeholder="Search analyses..."
                            value={analysisSearchTerm}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAnalysisSearchTerm(e.target.value)}
                            className="pl-8"
                            autoFocus
                          />
                          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500 absolute left-2.5 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                          </svg>
                        </div>
                      </div>
                      <div className="max-h-56 overflow-y-auto">
                        {/* All Analyses Option */}
                        {(!analysisSearchTerm || 'all analyses'.includes(analysisSearchTerm.toLowerCase())) && (
                          <button
                            onClick={() => { setSelectedConfigId(null); setActiveFilterDropdown(null); setAnalysisSearchTerm(''); }}
                            className={`w-full px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors ${selectedConfigId === null ? 'bg-eliza-red/10' : ''}`}
                          >
                            <div className={`text-sm font-medium ${selectedConfigId === null ? 'text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}>
                              All Analyses
                            </div>
                            <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                              <span>{analysisConfigs.length} analyses</span>
                              <span>·</span>
                              <span>{candidates.length} results</span>
                            </div>
                          </button>
                        )}
                        {/* Filtered Configs */}
                        {analysisConfigs
                          .filter(config => 
                            !analysisSearchTerm || 
                            config.name.toLowerCase().includes(analysisSearchTerm.toLowerCase())
                          )
                          .map((config) => {
                            const candidateCount = candidates.filter(c => c.analysis_name === config.name).length;
                            
                            return (
                              <button
                                key={config.id}
                                onClick={() => { setSelectedConfigId(config.id); setActiveFilterDropdown(null); setAnalysisSearchTerm(''); }}
                                className={`w-full px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors ${selectedConfigId === config.id ? 'bg-eliza-red/10' : ''}`}
                              >
                                <div className={`text-sm font-medium truncate ${selectedConfigId === config.id ? 'text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}>
                                  {config.name}
                                </div>
                                <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                                  {config.last_run_at && (
                                    <span>{new Date(config.last_run_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                                  )}
                                  <span>·</span>
                                  <span>{candidateCount} results</span>
                                </div>
                              </button>
                            );
                          })}
                        {/* No Results */}
                        {analysisSearchTerm && analysisConfigs.filter(c => c.name.toLowerCase().includes(analysisSearchTerm.toLowerCase())).length === 0 && (
                          <div className="px-3 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
                            No analyses match "{analysisSearchTerm}"
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Date Filter */}
                <DateRangePicker
                  value={dateFilter}
                  onChange={setDateFilter}
                  placeholder="Date"
                  className="flex-shrink-0"
                />

                {/* Candidate Type Filter */}
                <div className="relative">
                  <FilterChip
                    icon={<UsersIcon className="w-3.5 h-3.5" />}
                    label={
                      sourceFilter === 'all' ? 'Candidate Type' : 
                      sourceFilter === 'applicant' ? 'Applicants' : 
                      sourceFilter === 'previous_candidate' ? 'Previous Candidates' :
                      'Market Candidates'
                    }
                    isActive={activeFilterDropdown === 'source'}
                    hasValue={sourceFilter !== 'all'}
                    onClick={(e) => toggleFilterDropdown('source', e)}
                  />
                  {activeFilterDropdown === 'source' && (
                    <div className="absolute top-full left-0 mt-1 w-56 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-xl z-50 overflow-hidden">
                      <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border">
                        <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Candidate Type</span>
                      </div>
                      <button
                        onClick={() => { setSourceFilter('all'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${sourceFilter === 'all' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <span>All Types</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.total}</span>
                      </button>
                      <button
                        onClick={() => { setSourceFilter('applicant'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${sourceFilter === 'applicant' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <DocumentTextIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                          <span>Applicants</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.applicants}</span>
                      </button>
                      <button
                        onClick={() => { setSourceFilter('previous_candidate'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${sourceFilter === 'previous_candidate' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <ArrowPathIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                          <span>Previous Candidates</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.previous || 0}</span>
                      </button>
                      <button
                        onClick={() => { setSourceFilter('market'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${sourceFilter === 'market' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <GlobeAltIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                          <span>Market Candidates</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.market}</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Overall Score Filter */}
                <div className="relative">
                  <FilterChip
                    icon={<ChartBarIcon className="w-3.5 h-3.5" />}
                    label={scoreFilters.overall > 0 ? `Score ≥${scoreFilters.overall}` : 'Overall Score'}
                    isActive={activeFilterDropdown === 'overall'}
                    hasValue={scoreFilters.overall > 0}
                    onClick={(e) => toggleFilterDropdown('overall', e)}
                  />
                  {activeFilterDropdown === 'overall' && (
                    <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-xl z-50 overflow-hidden">
                      <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border">
                        <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Overall Score</span>
                      </div>
                      <div className="p-3">
                        <SliderInput
                          label="Minimum Score"
                          value={scoreFilters.overall}
                          onChange={(value) => setScoreFilters(prev => ({ ...prev, overall: value }))}
                          min={0}
                          max={100}
                          step={5}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Score Dimensions Filter */}
                <div className="relative">
                  <FilterChip
                    icon={<AdjustmentsHorizontalIcon className="w-3.5 h-3.5" />}
                    label={
                      Object.entries(scoreFilters).filter(([k, v]) => k !== 'overall' && v > 0).length > 0
                        ? `${Object.entries(scoreFilters).filter(([k, v]) => k !== 'overall' && v > 0).length} dimensions`
                        : 'Dimensions'
                    }
                    isActive={activeFilterDropdown === 'dimensions'}
                    hasValue={Object.entries(scoreFilters).filter(([k, v]) => k !== 'overall' && v > 0).length > 0}
                    onClick={(e) => toggleFilterDropdown('dimensions', e)}
                  />
                  {activeFilterDropdown === 'dimensions' && (
                    <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-xl z-[100] overflow-hidden">
                      <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border">
                        <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Dimension Scores</span>
                      </div>
                      <div className="p-3 space-y-4">
                        <SliderInput
                          label="Skill Alignment"
                          value={scoreFilters.skill_alignment}
                          onChange={(value) => setScoreFilters(prev => ({ ...prev, skill_alignment: value }))}
                          min={0}
                          max={100}
                          step={5}
                        />
                        <SliderInput
                          label="Experience Fit"
                          value={scoreFilters.experience_fit}
                          onChange={(value) => setScoreFilters(prev => ({ ...prev, experience_fit: value }))}
                          min={0}
                          max={100}
                          step={5}
                        />
                        <SliderInput
                          label="Trajectory Match"
                          value={scoreFilters.trajectory_match}
                          onChange={(value) => setScoreFilters(prev => ({ ...prev, trajectory_match: value }))}
                          min={0}
                          max={100}
                          step={5}
                        />
                        <SliderInput
                          label="Company Background"
                          value={scoreFilters.company_background}
                          onChange={(value) => setScoreFilters(prev => ({ ...prev, company_background: value }))}
                          min={0}
                          max={100}
                          step={5}
                        />
                        <SliderInput
                          label="Organizational Fit"
                          value={scoreFilters.organizational_fit}
                          onChange={(value) => setScoreFilters(prev => ({ ...prev, organizational_fit: value }))}
                          min={0}
                          max={100}
                          step={5}
                        />
                        
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setScoreFilters(prev => ({
                            ...prev,
                            skill_alignment: 0,
                            experience_fit: 0,
                            trajectory_match: 0,
                            company_background: 0,
                            organizational_fit: 0,
                          }))}
                          className="w-full text-xs"
                        >
                          Reset dimensions
                        </Button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Email Status Filter */}
                <div className="relative">
                  <FilterChip
                    icon={<EnvelopeIcon className="w-3.5 h-3.5" />}
                    label={
                      selectedFilter === 'all' ? 'Email Status' :
                      selectedFilter === 'pending' ? `Pending (${stats.pending})` :
                      selectedFilter === 'scheduled' ? `Scheduled (${stats.scheduled})` :
                      selectedFilter === 'sent' ? `Sent (${stats.sent})` :
                      `Skipped (${stats.rejected})`
                    }
                    isActive={activeFilterDropdown === 'status'}
                    hasValue={selectedFilter !== 'all'}
                    onClick={(e) => toggleFilterDropdown('status', e)}
                  />
                  {activeFilterDropdown === 'status' && (
                    <div className="absolute top-full left-0 mt-1 w-56 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-xl z-50 overflow-hidden">
                      <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border">
                        <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Email Status</span>
                      </div>
                      <button
                        onClick={() => { setSelectedFilter('all'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${selectedFilter === 'all' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <span>All Statuses</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.total}</span>
                      </button>
                      <button
                        onClick={() => { setSelectedFilter('pending'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${selectedFilter === 'pending' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <ClockIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                          <span>Pending</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.pending}</span>
                      </button>
                      <button
                        onClick={() => { setSelectedFilter('scheduled'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${selectedFilter === 'scheduled' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <CalendarIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                          <span>Scheduled</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.scheduled}</span>
                      </button>
                      <button
                        onClick={() => { setSelectedFilter('sent'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${selectedFilter === 'sent' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <CheckCircleIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                          <span>Sent</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.sent}</span>
                      </button>
                      <button
                        onClick={() => { setSelectedFilter('rejected'); setActiveFilterDropdown(null); }}
                        className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between ${selectedFilter === 'rejected' ? 'bg-eliza-red/10 text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}
                      >
                        <div className="flex items-center gap-2">
                          <XCircleIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                          <span>Skipped</span>
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">{stats.rejected}</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            
            {/* Clear all button */}
            {hasActiveFilters() && (
              <Button
                variant="link"
                size="sm"
                onClick={clearAllFilters}
                className="flex-shrink-0 text-xs"
              >
                Clear all
              </Button>
            )}
          </div>
          
          {/* Active filter count */}
          {hasActiveFilters() && (
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Showing {filteredCandidates.length} of {candidates.length} candidates
            </div>
          )}
        </div>

        {/* Main Content - Split Panels */}
        <div className="flex flex-1 min-h-0">
          {/* Left: Candidate List */}
          <div className="w-2/5 flex flex-col border-r border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
            {/* Candidate List */}
            <div className="flex-1 overflow-y-auto">
              {filteredCandidates.length === 0 ? (
              <div className="flex-1 flex items-center justify-center p-8">
                <div className="text-center">
                  <UserGroupIcon className="w-12 h-12 mx-auto mb-3 text-gray-400 dark:text-gray-500 opacity-50" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">No candidates match the current filters</p>
                </div>
              </div>
            ) : (
              filteredCandidates.map((candidate, index) => (
                <button
                  key={`${candidate.id}-${candidate.analysis_id}-${index}`}
                  onClick={() => handleSelectCandidate(candidate)}
                  className={`w-full px-6 py-3 border-b border-gray-200 dark:border-dark-border text-left hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors ${
                    selectedCandidate?.id === candidate.id ? 'bg-gray-50 dark:bg-dark-surface-2 border-l-2 border-l-eliza-red' : ''
                  }`}
                >
                  {/* Row 1: Rank pill, Name, Source badge, Score */}
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      {/* Rank pill */}
                      <Badge variant="secondary" className="flex-shrink-0">
                        #{candidate.rank}
                      </Badge>
                      {/* Name */}
                      <span className="font-medium text-charcoal dark:text-gray-100 truncate">{candidate.name}</span>
                      {/* Source badge */}
                      <Badge 
                        variant="outline"
                        className={`flex-shrink-0 ${
                          candidate.source === 'market'
                            ? 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800'
                            : candidate.source === 'previous_candidate'
                            ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800'
                            : 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-400 dark:border-sky-800'
                        }`}
                      >
                        {candidate.source === 'market' ? 'Market' : 
                         candidate.source === 'previous_candidate' ? 'Previous' : 
                         'Applicant'}
                      </Badge>
                      {!candidate.email && (
                        <Badge variant="warning" className="flex-shrink-0">
                          No email
                        </Badge>
                      )}
                    </div>
                    {/* Overall score */}
                    <span className="text-base font-bold text-green-600 dark:text-green-400 flex-shrink-0">{candidate.score}</span>
                  </div>

                  {/* Row 2: Title/Company and Location */}
                  <div className="flex items-center gap-4 mt-1.5 text-[11px] text-gray-500 dark:text-gray-400">
                    {(candidate.current_title || candidate.current_company) && (
                      <span className="flex items-center gap-1 truncate">
                        <BriefcaseIcon className="w-3 h-3 flex-shrink-0" />
                        <span className="truncate">{candidate.current_title}{candidate.current_company && ` @ ${candidate.current_company}`}</span>
                      </span>
                    )}
                    {candidate.location && (
                      <span className="flex items-center gap-1 flex-shrink-0">
                        <MapPinIcon className="w-3 h-3" />
                        {candidate.location}
                      </span>
                    )}
                  </div>

                  {/* Row 3: Dimension scores as pills + highlights */}
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {/* Experience Fit pill */}
                    {getDimensionScore(candidate, 'experience_fit') > 0 && (
                      <Badge variant="secondary" className="gap-1">
                        Experience <span className="text-green-600 dark:text-green-400">{getDimensionScore(candidate, 'experience_fit')}</span>
                      </Badge>
                    )}
                    {/* Organizational Fit pill */}
                    {getDimensionScore(candidate, 'organizational_fit') > 0 && (
                      <Badge variant="secondary" className="gap-1">
                        Organization <span className="text-green-600 dark:text-green-400">{getDimensionScore(candidate, 'organizational_fit')}</span>
                      </Badge>
                    )}
                    {/* Highlights */}
                    {candidate.highlights
                      .filter(h => !h.toLowerCase().includes('experience_fit') && !h.toLowerCase().includes('organizational_fit'))
                      .slice(0, 2)
                      .map((h, idx) => {
                        // Format: "skill_alignment: 96" -> "Skill Alignment 96"
                        const parts = h.split(':');
                        const dimName = parts[0]?.trim() || '';
                        const score = parts[1]?.trim() || '';
                        return (
                          <Badge key={idx} variant="secondary" className="gap-1">
                            {formatDimensionName(dimName)} <span className="text-green-600 dark:text-green-400">{score}</span>
                          </Badge>
                        );
                      })}
                  </div>
                </button>
              ))
              )}
            </div>
          </div>

          {/* Right: Candidate Detail & Email */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-dark-surface">
            {!selectedCandidate ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <UserGroupIcon className="w-16 h-16 mx-auto mb-4 text-gray-400 dark:text-gray-500 opacity-50" />
                  <p className="text-lg text-gray-500 dark:text-gray-400">Select a candidate to view details</p>
                </div>
              </div>
            ) : (
              <>
                {/* Candidate Header */}
                <div className="px-8 py-6 border-b border-gray-200 dark:border-dark-border">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="font-title text-h2 text-charcoal dark:text-gray-100">{selectedCandidate.name}</h2>
                      {/* Source badge */}
                      <Badge 
                        variant="outline"
                        className={
                          selectedCandidate.source === 'market'
                            ? 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800'
                            : selectedCandidate.source === 'previous_candidate'
                            ? 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800'
                            : 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-400 dark:border-sky-800'
                        }
                      >
                        {selectedCandidate.source === 'market' ? 'Market' : 
                         selectedCandidate.source === 'previous_candidate' ? 'Previous' :
                         'Applicant'}
                      </Badge>
                    </div>
                    
                    {/* Contact Info Row */}
                    <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-gray-400 mb-2">
                      {selectedCandidate.email && (
                        <div className="flex items-center gap-1">
                          <EnvelopeIcon className="w-4 h-4" />
                          <a href={`mailto:${selectedCandidate.email}`} className="hover:text-eliza-red transition-colors">
                            {selectedCandidate.email}
                          </a>
                        </div>
                      )}
                      {selectedCandidate.phone && (
                        <div className="flex items-center gap-1">
                          <PhoneIcon className="w-4 h-4" />
                          <a href={`tel:${selectedCandidate.phone}`} className="hover:text-eliza-red transition-colors">
                            {selectedCandidate.phone}
                          </a>
                        </div>
                      )}
                      {selectedCandidate.location && (
                        <div className="flex items-center gap-1">
                          <MapPinIcon className="w-4 h-4" />
                          <span>{selectedCandidate.location}</span>
                        </div>
                      )}
                    </div>
                    
                    {/* Profile Links Row */}
                    <div className="flex flex-wrap items-center gap-4 text-sm">
                      {/* LinkedIn Profile Link */}
                      {selectedCandidate.linkedin && (
                        <a
                          href={selectedCandidate.linkedin.startsWith('http') ? selectedCandidate.linkedin : `https://${selectedCandidate.linkedin}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-gray-500 dark:text-gray-400 hover:text-eliza-red dark:hover:text-eliza-red font-medium transition-colors"
                        >
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/>
                          </svg>
                          LinkedIn Profile
                        </a>
                      )}
                      
                      {/* Greenhouse Profile Link - use greenhouse_id to build URL if available */}
                      {(selectedCandidate.greenhouse_profile_url || selectedCandidate.greenhouse_id) && (
                        <a
                          href={selectedCandidate.greenhouse_profile_url || `https://app4.greenhouse.io/people/${selectedCandidate.greenhouse_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-gray-500 dark:text-gray-400 hover:text-eliza-red dark:hover:text-eliza-red font-medium transition-colors"
                        >
                          <BuildingOfficeIcon className="w-4 h-4" />
                          Greenhouse Profile
                        </a>
                      )}
                      
                      {/* Greenhouse Lookup Button - only show for applicants without greenhouse_id */}
                      {!selectedCandidate.greenhouse_profile_url && !selectedCandidate.greenhouse_id && selectedCandidate.source === 'applicant' && selectedCandidate.email && loadingGreenhouseUrl !== selectedCandidate.id && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => fetchGreenhouseProfileUrl(selectedCandidate)}
                          title="Search for candidate in Greenhouse"
                          className="text-xs"
                        >
                          <BuildingOfficeIcon className="w-3 h-3 mr-1" />
                          Find in Greenhouse
                        </Button>
                      )}
                      {loadingGreenhouseUrl === selectedCandidate.id && (
                        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                          <Spinner size="sm" />
                          Searching Greenhouse...
                        </div>
                      )}
                      
                      {/* Add to Greenhouse Button - only show for market candidates not yet in ATS */}
                      {selectedCandidate.source === 'market' && !selectedCandidate.greenhouse_id && (
                        <Button
                          onClick={() => handleAddToATS(selectedCandidate)}
                          disabled={addingToATS === selectedCandidate.id}
                          size="sm"
                          className="bg-green-600 hover:bg-green-500 text-white"
                          title="Add this candidate to Greenhouse ATS"
                        >
                          {addingToATS === selectedCandidate.id ? (
                            <>
                              <Spinner size="sm" className="mr-1.5" />
                              Adding to Greenhouse...
                            </>
                          ) : (
                            <>
                              <PlusIcon className="w-4 h-4 mr-1" />
                              Add to Greenhouse
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                    
                    {/* Add to ATS Result Message */}
                    {addToATSResult && (
                      <Alert 
                        variant={addToATSResult.success ? 'success' : 'error'} 
                        className="mt-2"
                        onDismiss={() => setAddToATSResult(null)}
                      >
                        {addToATSResult.message}
                      </Alert>
                    )}
                    
                    {/* Greenhouse Not Found Error */}
                    {greenhouseNotFoundError && (
                      <Alert 
                        variant="warning" 
                        className="mt-2"
                        onDismiss={() => setGreenhouseNotFoundError(null)}
                      >
                        {greenhouseNotFoundError}
                      </Alert>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-green-600 dark:text-green-400">{selectedCandidate.score}</div>
                    <p className="text-sm text-gray-500 dark:text-gray-400">Match Score</p>
                    {selectedCandidate.confidence && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {(selectedCandidate.confidence * 100).toFixed(0)}% confidence
                      </p>
                    )}
                  </div>
                </div>

                {/* Score Details - Compact Accordion with Top Scores */}
                {selectedCandidate.score_breakdown?.dimensions && (
                  <div className="mb-4 border border-gray-200 dark:border-dark-border rounded-xl overflow-hidden">
                    {/* Accordion Header with inline scores */}
                    <button
                      onClick={() => setIsScoreDetailsExpanded(!isScoreDetailsExpanded)}
                      className="w-full px-4 py-2.5 bg-gray-50 dark:bg-dark-surface-2 hover:bg-gray-100 dark:hover:bg-dark-surface-2/80 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        {/* Left: Top dimension scores as compact inline list */}
                        <div className="flex items-center gap-4 text-xs">
                          {selectedCandidate.score_breakdown.dimensions.slice(0, 4).map((dim: any, idx: number) => (
                            <div key={idx} className="flex items-center gap-1.5">
                              <span className="text-gray-500 dark:text-gray-400">{formatDimensionName(dim.dimension || '')}</span>
                              <span className={`font-semibold ${
                                dim.score >= 70 ? 'text-green-600 dark:text-green-400' : dim.score >= 50 ? 'text-amber-500' : 'text-red-500'
                              }`}>
                                {dim.score?.toFixed(0)}
                              </span>
                            </div>
                          ))}
                          {selectedCandidate.score_breakdown.dimensions.length > 4 && (
                            <span className="text-gray-400 dark:text-gray-500">
                              +{selectedCandidate.score_breakdown.dimensions.length - 4} more
                            </span>
                          )}
                        </div>
                        
                        {/* Right: Rate button and chevron */}
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setFeedbackCandidate(selectedCandidate);
                              setShowFeedbackModal(true);
                            }}
                            className={`
                              flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all border
                              ${selectedCandidate.has_feedback
                                ? 'bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 border-green-500/30 hover:bg-green-100 dark:hover:bg-green-900/40'
                                : 'bg-white dark:bg-dark-surface text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:bg-gray-100 dark:hover:bg-dark-surface-2/80 hover:text-charcoal dark:hover:text-gray-100'
                              }
                            `}
                          >
                            {selectedCandidate.has_feedback ? (
                              <>
                                <StarSolid className="w-3 h-3" />
                                <span>Rated</span>
                              </>
                            ) : (
                              <>
                                <HandThumbUpIcon className="w-3 h-3" />
                                <span>Rate</span>
                              </>
                            )}
                          </button>
                          <ChevronDownIcon 
                            className={`w-4 h-4 text-gray-400 dark:text-gray-500 transition-transform ${isScoreDetailsExpanded ? 'rotate-180' : ''}`} 
                          />
                        </div>
                      </div>
                    </button>
                    
                    {/* Expandable Content */}
                    {isScoreDetailsExpanded && (
                      <div className="px-4 py-3 bg-white dark:bg-dark-surface border-t border-gray-200 dark:border-dark-border">
                        {/* Full Score Breakdown */}
                        <div className="grid grid-cols-2 gap-x-8 gap-y-1.5">
                          {selectedCandidate.score_breakdown.dimensions.map((dim: any, idx: number) => (
                            <div key={idx} className="flex items-center justify-between text-sm">
                              <span className="text-gray-500 dark:text-gray-400">{formatDimensionName(dim.dimension || '')}</span>
                              <span className={`font-semibold ${
                                dim.score >= 70 ? 'text-green-600 dark:text-green-400' : dim.score >= 50 ? 'text-amber-500' : 'text-red-500'
                              }`}>
                                {dim.score?.toFixed(0)}
                              </span>
                            </div>
                          ))}
                        </div>
                        
                        {/* Analysis Info */}
                        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-dark-border/50 flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
                          <span>Analysis:</span>
                          <span className="text-charcoal/70 dark:text-gray-300">{selectedCandidate.analysis_name}</span>
                          <span className="text-gray-300 dark:text-gray-600">·</span>
                          <span>{selectedCandidate.analysis_date}</span>
                          <button
                            onClick={() => navigate(`/talent/history?id=${selectedCandidate.analysis_id}`)}
                            className="ml-1 text-eliza-red hover:text-eliza-red/80 transition-colors"
                          >
                            View →
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* No Email Warning */}
                {!selectedCandidate.email && (
                  <Alert variant="warning" className="mb-4">
                    <p className="font-medium">No email address available for this candidate</p>
                    <p className="text-xs mt-1 opacity-80">
                      Try reaching out via LinkedIn or other channels.
                    </p>
                  </Alert>
                )}
              </div>

              {/* Email Section */}
              <div className="flex-1 overflow-y-auto px-8 py-6">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-charcoal dark:text-gray-100 flex items-center gap-2">
                    <EnvelopeIcon className="w-5 h-5 text-gray-400 dark:text-gray-500" />
                    Outreach Email
                  </h3>
                  {/* Manage Templates Link */}
                  <Link
                    to="/talent/email-templates"
                    className="text-sm text-gray-500 dark:text-gray-400 hover:text-eliza-red dark:hover:text-eliza-red transition-colors"
                  >
                    Manage Templates →
                  </Link>
                </div>

                <div className="bg-gray-50 dark:bg-dark-surface-2/30 border border-gray-200 dark:border-dark-border rounded-xl p-5 space-y-4">
                  {/* Template Selector - Interactive Dropdown */}
                  <div className="flex items-center justify-between pb-3 border-b border-gray-200/50 dark:border-dark-border/50">
                    <div className="relative" data-template-picker>
                      <button
                        onClick={() => setShowTemplatePickerDropdown(!showTemplatePickerDropdown)}
                        className="flex items-center gap-2 text-xs hover:bg-gray-100 dark:hover:bg-dark-surface-2 px-2 py-1.5 -ml-2 rounded-lg transition-colors"
                      >
                        <SparklesIcon className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                        <span className="text-gray-500 dark:text-gray-400">Template:</span>
                        {selectedTemplateName ? (
                          <>
                            <span className="text-charcoal dark:text-gray-100 font-medium">{selectedTemplateName}</span>
                            {availableTemplates.find(t => t.name === selectedTemplateName)?.is_default && (
                              <Badge variant="secondary" className="text-[10px]">DEFAULT</Badge>
                            )}
                          </>
                        ) : (
                          <span className="text-gray-400 dark:text-gray-500 italic">Select template...</span>
                        )}
                        <ChevronDownIcon className={`w-3.5 h-3.5 text-gray-400 transition-transform ${showTemplatePickerDropdown ? 'rotate-180' : ''}`} />
                      </button>
                      {showTemplatePickerDropdown && (
                        <div className="absolute top-full left-0 mt-1 w-72 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl shadow-xl z-50 overflow-hidden">
                          <div className="px-3 py-2 border-b border-gray-200 dark:border-dark-border">
                            <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">Apply Template</span>
                          </div>
                          <div className="max-h-64 overflow-y-auto">
                            {availableTemplates.length === 0 ? (
                              <div className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                                No templates available
                              </div>
                            ) : (
                              availableTemplates.map((template) => (
                                <button
                                  key={template.id}
                                  onClick={() => {
                                    handleApplyTemplate(template.id);
                                    setSelectedTemplateName(template.name);
                                    setShowTemplatePickerDropdown(false);
                                  }}
                                  disabled={generatingEmail}
                                  className="w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors flex items-center justify-between disabled:opacity-50 border-b border-gray-200/30 dark:border-dark-border/30 last:border-0"
                                >
                                  <span className="text-charcoal dark:text-gray-100 text-sm font-medium">{template.name}</span>
                                  {template.is_default && (
                                    <Badge variant="secondary">Default</Badge>
                                  )}
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Subject with Edit Button */}
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-xs text-gray-500 dark:text-gray-400">Subject</Label>
                      {isEditingEmail ? (
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setIsEditingEmail(false)}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => {
                              handleSaveEmailChanges();
                              setIsEditingEmail(false);
                            }}
                          >
                            <CheckIcon className="w-3.5 h-3.5 mr-1" />
                            Save
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setIsEditingEmail(true)}
                        >
                        <PencilIcon className="w-3.5 h-3.5 mr-1" />
                        Edit
                      </Button>
                    )}
                    </div>
                    {isEditingEmail ? (
                      <Input
                        value={emailSubject}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmailSubject(e.target.value)}
                        className="mt-1"
                      />
                    ) : (
                      <div className="font-semibold text-charcoal dark:text-gray-100">{emailSubject}</div>
                    )}
                  </div>
                  
                  {/* Body */}
                  <div>
                    <Label className="text-xs text-gray-500 dark:text-gray-400 mb-2">Body</Label>
                    {isEditingEmail ? (
                      <Textarea
                        value={emailBody}
                        onChange={(e) => setEmailBody(e.target.value)}
                        rows={10}
                        className="mt-1"
                      />
                    ) : (
                      <div className="text-charcoal dark:text-gray-100 whitespace-pre-line leading-relaxed">
                        {emailBody}
                      </div>
                    )}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="mt-6 space-y-4">
                  {selectedCandidate.outreach_status === 'pending' && selectedCandidate.email && (
                    <div className="flex gap-3">
                      <Button
                        onClick={() => handleSendEmail(selectedCandidate.id)}
                        className="flex-1"
                        disabled={isEditingEmail}
                      >
                        <PaperAirplaneIcon className="w-4 h-4 mr-2" />
                        Send Now
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => handleScheduleEmail(selectedCandidate.id)}
                        className="flex-1"
                        disabled={isEditingEmail}
                      >
                        <ClockIcon className="w-4 h-4 mr-2" />
                        Schedule
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => handleRejectCandidate(selectedCandidate.id)}
                        disabled={isEditingEmail}
                      >
                        <XMarkIcon className="w-4 h-4 mr-2" />
                        Reject
                      </Button>
                    </div>
                  )}

                  {selectedCandidate.outreach_status === 'pending' && !selectedCandidate.email && (
                    <div className="w-full bg-gray-100 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border rounded-xl p-4 text-center">
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        Cannot send email - no email address available
                      </p>
                      {selectedCandidate.linkedin && (
                        <Button
                          variant="outline"
                          className="mt-2"
                          onClick={() => {
                            const url = selectedCandidate.linkedin;
                            if (url) {
                              window.open(url.startsWith('http') ? url : `https://${url}`, '_blank');
                            }
                          }}
                        >
                          Reach out on LinkedIn
                        </Button>
                      )}
                    </div>
                  )}

                  {selectedCandidate.outreach_status === 'sent' && (
                    <div className="space-y-4">
                      <Alert variant="success">
                        <p className="font-medium">Email may have been sent</p>
                        <p className="text-xs mt-1 opacity-80">Check your Gmail drafts or sent folder to confirm</p>
                      </Alert>
                      <div className="flex gap-3">
                        <Button
                          variant="outline"
                          onClick={() => handleSendEmail(selectedCandidate.id)}
                          className="flex-1"
                        >
                          <PaperAirplaneIcon className="w-4 h-4 mr-2" />
                          Send Again
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => handleScheduleEmail(selectedCandidate.id)}
                          className="flex-1"
                        >
                          <ClockIcon className="w-4 h-4 mr-2" />
                          Schedule
                        </Button>
                      </div>
                    </div>
                  )}

                  {selectedCandidate.outreach_status === 'rejected' && (
                    <Alert variant="error">
                      <p className="font-medium">Candidate match rejected</p>
                    </Alert>
                  )}
                </div>
              </div>
              </>
            )}
          </div>
        </div>
      </Page>

      {/* Email Edit Modal */}
      <Modal open={showEmailModal} onClose={() => setShowEmailModal(false)}>
        <ModalBackdrop />
        <ModalContent size="lg">
          <ModalHeader>
            <ModalTitle>Edit Email</ModalTitle>
          </ModalHeader>
          <ModalBody className="space-y-4">
            <div>
              <Label htmlFor="email-subject" className="mb-2">Subject</Label>
              <Input
                id="email-subject"
                type="text"
                value={emailSubject}
                onChange={(e) => setEmailSubject(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="email-body" className="mb-2">Body</Label>
              <Textarea
                id="email-body"
                value={emailBody}
                onChange={(e) => setEmailBody(e.target.value)}
                rows={15}
              />
            </div>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={() => setShowEmailModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveEmailChanges}>
              <CheckIcon className="w-4 h-4 mr-2" />
              Save Changes
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Template Selector Modal */}
      <Modal open={showTemplateSelector} onClose={() => setShowTemplateSelector(false)}>
        <ModalBackdrop />
        <ModalContent size="md">
          <ModalHeader>
            <ModalTitle>Select Email Template</ModalTitle>
            <ModalDescription>Choose a template to generate a personalized email</ModalDescription>
          </ModalHeader>
          <ModalBody>
            {loadingTemplates ? (
              <div className="flex items-center justify-center py-8">
                <Spinner size="sm" className="mr-2" />
                <span className="text-gray-500 dark:text-gray-400">Loading templates...</span>
              </div>
            ) : availableTemplates.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500 dark:text-gray-400 mb-2">No templates available</p>
                <a href="/talent/email-templates" className="text-eliza-red hover:underline text-sm">
                  Create your first template →
                </a>
              </div>
            ) : (
              <div className="space-y-2">
                {availableTemplates.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => handleApplyTemplate(template.id)}
                    disabled={generatingEmail}
                    className="w-full p-4 text-left bg-gray-50 dark:bg-dark-surface-2 hover:bg-gray-100 dark:hover:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg transition-colors disabled:opacity-50"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <span className="font-medium text-charcoal dark:text-gray-100">{template.name}</span>
                        {template.description && (
                          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{template.description}</p>
                        )}
                      </div>
                      <ChevronDownIcon className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0 -rotate-90" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </ModalBody>
          <ModalFooter className="justify-between">
            <a href="/talent/email-templates" className="text-sm text-eliza-red hover:underline">
              Manage Templates
            </a>
            <Button variant="ghost" onClick={() => setShowTemplateSelector(false)}>
              Cancel
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Generating Email Overlay */}
      <Modal open={generatingEmail} onClose={() => {}}>
        <ModalBackdrop />
        <ModalContent size="sm" className="text-center">
          <ModalBody className="py-8">
            <Spinner size="lg" className="mx-auto mb-4" />
            <p className="font-medium text-charcoal dark:text-gray-100">Generating personalized email...</p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">This may take a few seconds</p>
          </ModalBody>
        </ModalContent>
      </Modal>

      {/* Candidate Score Feedback Modal */}
      {showFeedbackModal && feedbackCandidate && (
        <CandidateFeedbackModal
          candidate={{
            id: feedbackCandidate.id,
            score_id: feedbackCandidate.score_id,
            name: feedbackCandidate.name,
            score: feedbackCandidate.score,
            score_breakdown: feedbackCandidate.score_breakdown,
            current_title: feedbackCandidate.current_title || undefined,
            current_company: feedbackCandidate.current_company || undefined,
          }}
          onClose={() => {
            setShowFeedbackModal(false);
            setFeedbackCandidate(null);
          }}
          onSubmit={() => {
            // Mark that this candidate now has feedback
            setCandidates(prev => prev.map(c => 
              c.id === feedbackCandidate.id 
                ? { ...c, has_feedback: true }
                : c
            ));
            // Also update selectedCandidate if it's the same
            if (selectedCandidate?.id === feedbackCandidate.id) {
              setSelectedCandidate(prev => prev ? { ...prev, has_feedback: true } : null);
            }
          }}
        />
      )}
    </>
  );
}

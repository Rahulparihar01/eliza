/**
 * GEPA Optimizer Page - Eliza Forge
 * 
 * Optimize RAG prompts using Genetic Prompt Algorithm (GEPA).
 * Features:
 * - Create new optimization jobs with configurable parameters
 * - Real-time progress tracking via SSE
 * - Pareto frontier visualization
 * - Component diff viewer
 * - Trace drill-downs
 * - Try candidate / Promote actions
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Layout from '../../components/layout/Layout';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Badge,
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  DataTable,
  Input,
  Textarea,
  Label,
  Select,
  SelectOption,
  Checkbox,
  Progress,
  Spinner,
} from '../../components/ui';
import type { Column } from '../../components/ui';
import {
  PlayIcon,
  PlusIcon,
  StopIcon,
  PauseIcon,
  ArrowPathIcon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  BeakerIcon,
  ClockIcon,
  ArrowTopRightOnSquareIcon,
  TrashIcon,
  ArrowUpIcon,
  EyeIcon,
  DocumentDuplicateIcon,
  AdjustmentsHorizontalIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { useToasts } from '../../stores/useToasts';
import { useRAGWorkspaces } from '../../hooks/useRAGDomains';
import { WorkspaceSelector } from '../../components/common/RAGDomainSelector';

// Types
interface OptimizerJob {
  id: number;
  job_id: string;
  name: string;
  description?: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  target_components: string[];
  objectives: string[];
  population_size: number;
  max_iterations: number;
  current_iteration: number;
  total_evals_used: number;
  eval_budget: number;
  best_quality_score?: number;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  created_at: string;
}

interface CandidateVariant {
  id: number;
  variant_id: string;
  generation: number;
  mutation_type?: string;
  parent_variant_ids?: string[];
  status: 'pending' | 'evaluating' | 'evaluated' | 'failed' | 'promoted';
  scores: {
    quality_score?: number;
    groundedness_score?: number;
    citation_accuracy?: number;
    avg_latency_ms?: number;
    avg_cost?: number;
  };
  pareto_rank?: number;
  crowding_distance?: number;
  is_baseline: boolean;
  is_promoted: boolean;
  promoted_to?: string;
  created_at: string;
}

interface ComponentDiff {
  component_type: string;
  baseline_value: string;
  variant_value: string;
  added_lines?: string[];
  removed_lines?: string[];
  similarity_score?: number;
}

interface CandidateVariantDetail extends CandidateVariant {
  component_values: Record<string, string>;
  component_diffs?: ComponentDiff[];
  eval_results_count: number;
  pass_count: number;
  fail_count: number;
  error_count: number;
}

interface EvalResultSummary {
  id: number;
  eval_case_id: string;
  question: string;
  verdict?: string;
  factual_correctness?: number;
  faithfulness?: number;
  citation_compliance?: number;
  latency_ms?: number;
}

interface TraceSummary {
  id: number;
  trace_id: string;
  trace_type: string;
  eval_case_id?: string;
  total_latency_ms?: number;
  total_tokens?: number;
  step_count?: number;
  error_count?: number;
  created_at: string;
}

interface ParetoFrontierPoint {
  variant_id: string;
  scores: Record<string, number>;
}

interface TelemetryEvent {
  event_type: string;
  stage_name?: string;
  message?: string;
  progress_percentage?: number;
  data?: any;
  timestamp?: string;
}

interface ComponentConfig {
  component_type: string;
  initial_value?: string;
}

interface ObjectiveConfig {
  name: string;
  weight: number;
  direction: 'maximize' | 'minimize';
}

// Human feedback types
type FeedbackRating = 'strongly_negative' | 'negative' | 'neutral' | 'positive' | 'strongly_positive';
type FeedbackType = 'per_query' | 'overall';

interface HumanFeedback {
  id: number;
  variant_id: number;
  feedback_type: FeedbackType;
  rating: FeedbackRating;
  rating_numeric: number;
  comment?: string;
  tags?: string[];
  target_components?: string[];
  user_id: number;
  incorporated: boolean;
  created_at: string;
}

const RATING_OPTIONS: { value: FeedbackRating; label: string; emoji: string; color: string }[] = [
  { value: 'strongly_negative', label: 'Very Poor', emoji: '😠', color: 'text-red-500' },
  { value: 'negative', label: 'Poor', emoji: '😕', color: 'text-orange-500' },
  { value: 'neutral', label: 'Neutral', emoji: '😐', color: 'text-gray-500' },
  { value: 'positive', label: 'Good', emoji: '🙂', color: 'text-green-500' },
  { value: 'strongly_positive', label: 'Excellent', emoji: '😍', color: 'text-emerald-500' },
];

const FEEDBACK_TAGS = [
  'too_verbose', 'too_concise', 'good_citations', 'missing_citations',
  'factually_incorrect', 'off_topic', 'good_structure', 'confusing',
  'professional_tone', 'wrong_tone', 'comprehensive', 'incomplete',
];

// Backend API URL
const API_BASE = window.location.port === '3000'
  ? 'http://localhost:5001/api/v1/optimizers/gepa'
  : '/api/v1/optimizers/gepa';

// Prompt Management API (for pre-filling baseline prompts)
const PROMPTS_API_BASE = window.location.port === '3000'
  ? 'http://localhost:5001/api/v1/prompts'
  : '/api/v1/prompts';

export default function GEPAOptimizerPage() {
  const token = localStorage.getItem('auth_token');
  const { push } = useToasts();

  // RAG Workspaces
  const {
    workspaces,
    selectedWorkspace,
    selectedWorkspaceId,
    setSelectedWorkspaceId,
    isLoading: isLoadingWorkspaces,
    error: workspacesError,
    refresh: refreshWorkspaces,
  } = useRAGWorkspaces({ autoSelect: true });

  // Job list state
  const [jobs, setJobs] = useState<OptimizerJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<OptimizerJob | null>(null);
  const [variants, setVariants] = useState<CandidateVariant[]>([]);
  const [variantsTotal, setVariantsTotal] = useState(0);
  const [variantsPage, setVariantsPage] = useState(1);
  const [frontier, setFrontier] = useState<ParetoFrontierPoint[]>([]);
  
  // UI state
  const [isCreating, setIsCreating] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<CandidateVariant | null>(null);
  const [selectedVariantDetail, setSelectedVariantDetail] = useState<CandidateVariantDetail | null>(null);
  const [isLoadingVariantDetail, setIsLoadingVariantDetail] = useState(false);
  const [variantEvalResults, setVariantEvalResults] = useState<EvalResultSummary[]>([]);
  const [variantEvalTotal, setVariantEvalTotal] = useState(0);
  const [variantTraces, setVariantTraces] = useState<TraceSummary[]>([]);
  const [variantTracesTotal, setVariantTracesTotal] = useState(0);
  
  // Feedback state
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [variantFeedback, setVariantFeedback] = useState<HumanFeedback[]>([]);
  const [feedbackData, setFeedbackData] = useState({
    rating: 'neutral' as FeedbackRating,
    comment: '',
    tags: [] as string[],
    improvement_suggestions: '',
  });
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  
  // SSE
  const eventSourceRef = useRef<EventSource | null>(null);

  // Create form state
  const [promptDomains, setPromptDomains] = useState<{ domain: string; display_name: string }[]>([]);
  const [isLoadingDomainPrompts, setIsLoadingDomainPrompts] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    use_prompt_management: true,
    import_prompt_feedback: false,
    prompt_feedback_environment: 'prod' as 'prod' | 'staging' | 'dev',
    prompt_feedback_limit: 20,
    components: [
      { component_type: 'query_rewrite_prompt', initial_value: '' },
      { component_type: 'answer_synthesis_prompt', initial_value: '' },
    ] as ComponentConfig[],
    objectives: [
      { name: 'quality', weight: 0.4, direction: 'maximize' as const },
      { name: 'groundedness', weight: 0.3, direction: 'maximize' as const },
      { name: 'latency', weight: 0.15, direction: 'minimize' as const },
      { name: 'cost', weight: 0.15, direction: 'minimize' as const },
    ] as ObjectiveConfig[],
    population_size: 10,
    max_iterations: 20,
    eval_budget: 500,
    mutation_rate: 0.3,
    crossover_rate: 0.5,
    elite_count: 2,
  });
  
  // Get current workspace name for API calls
  const currentWorkspaceName = selectedWorkspace?.name || 'fasb';

  // Fetch jobs filtered by current workspace
  const fetchJobs = useCallback(async () => {
    try {
      const params = new URLSearchParams({ page_size: '20' });
      if (currentWorkspaceName) {
        params.set('domain', currentWorkspaceName);
      }
      const res = await fetch(`${API_BASE}?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs || []);
      }
    } catch (e) {
      console.error('Failed to fetch jobs:', e);
    }
  }, [token, currentWorkspaceName]);

  // Prompt domains (for prefill) - now uses RAG domain
  const fetchPromptDomains = useCallback(async () => {
    try {
      const res = await fetch(`${PROMPTS_API_BASE}/domains?include_inactive=false`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const domains = (data.domains || []).map((d: any) => ({
          domain: d.domain,
          display_name: d.display_name || d.domain,
        }));
        setPromptDomains(domains);
      }
    } catch (e) {
      // Non-fatal; user can still type prompts manually
      console.error('Failed to fetch prompt domains:', e);
    }
  }, [token]);

  const loadWorkspacePrompts = async () => {
    if (!selectedWorkspace) {
      push({ kind: 'error', message: 'Select a workspace first' });
      return;
    }

    setIsLoadingDomainPrompts(true);
    try {
      const res = await fetch(`${PROMPTS_API_BASE}/domains/${currentWorkspaceName}/rag-prompts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        push({ kind: 'error', message: error.detail || 'Failed to load prompts for workspace' });
        return;
      }

      const data = await res.json();
      const prompts: Record<string, string> = data.prompts || {};

      const mapping: Array<{ pm: string; gepa: string }> = [
        { pm: 'system', gepa: 'system_prompt' },
        { pm: 'query_rewrite', gepa: 'query_rewrite_prompt' },
        { pm: 'synthesis', gepa: 'answer_synthesis_prompt' },
        { pm: 'retrieval', gepa: 'retrieval_instructions' },
      ];

      setFormData((prev) => {
        const next = { ...prev, use_prompt_management: true };
        const comps = [...next.components];

        for (const { pm, gepa } of mapping) {
          const content = (prompts[pm] || '').trim();
          if (!content) continue;
          const idx = comps.findIndex((c) => c.component_type === gepa);
          if (idx >= 0) comps[idx] = { ...comps[idx], initial_value: content };
          else comps.push({ component_type: gepa, initial_value: content } as any);
        }

        next.components = comps;
        return next;
      });

      push({ kind: 'success', message: `Loaded active prompts for ${currentWorkspaceName}` });
    } catch (e) {
      console.error('Failed to load workspace prompts:', e);
      push({ kind: 'error', message: 'Failed to load workspace prompts' });
    } finally {
      setIsLoadingDomainPrompts(false);
    }
  };

  // Fetch job details
  const fetchJobDetails = useCallback(async (jobId: string) => {
    try {
      console.log('Fetching job details for:', jobId);
      const res = await fetch(`${API_BASE}/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        console.log('Got job details:', data);
        setSelectedJob(data);
        setFrontier(data.current_frontier || []);
      } else {
        const error = await res.json();
        console.error('Failed to fetch job details:', error);
        push({ kind: 'error', message: `Failed to load job: ${error.detail || error.message || 'Unknown error'}` });
      }
    } catch (e) {
      console.error('Failed to fetch job details:', e);
      push({ kind: 'error', message: 'Failed to fetch job details' });
    }
  }, [token, push]);

  // Fetch variants
  const fetchVariants = useCallback(async (jobId: string) => {
    try {
      const pageSize = 200;
      const res = await fetch(`${API_BASE}/${jobId}/variants?page=${variantsPage}&page_size=${pageSize}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setVariants(data.variants || []);
        setVariantsTotal(data.total || 0);
      }
    } catch (e) {
      console.error('Failed to fetch variants:', e);
    }
  }, [token, variantsPage]);

  const loadMoreVariants = async () => {
    if (!selectedJob) return;
    const nextPage = variantsPage + 1;
    const pageSize = 200;
    try {
      const res = await fetch(`${API_BASE}/${selectedJob.job_id}/variants?page=${nextPage}&page_size=${pageSize}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      const next = data.variants || [];
      setVariants((prev) => [...prev, ...next]);
      setVariantsTotal(data.total || 0);
      setVariantsPage(nextPage);
    } catch (e) {
      console.error('Failed to load more variants:', e);
    }
  };

  const openVariantDetails = async (variant: CandidateVariant) => {
    if (!selectedJob) return;
    setSelectedVariant(variant);
    setSelectedVariantDetail(null);
    setVariantEvalResults([]);
    setVariantTraces([]);
    setVariantEvalTotal(0);
    setVariantTracesTotal(0);
    setShowFeedbackForm(false);

    setIsLoadingVariantDetail(true);
    try {
      const detailRes = await fetch(
        `${API_BASE}/${selectedJob.job_id}/variants/${variant.variant_id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (detailRes.ok) {
        const detail = await detailRes.json();
        setSelectedVariantDetail(detail);
      }

      const resultsRes = await fetch(
        `${API_BASE}/${selectedJob.job_id}/variants/${variant.variant_id}/results?page=1&page_size=50`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (resultsRes.ok) {
        const r = await resultsRes.json();
        setVariantEvalResults(r.results || []);
        setVariantEvalTotal(r.total || 0);
      }

      const tracesRes = await fetch(
        `${API_BASE}/${selectedJob.job_id}/variants/${variant.variant_id}/traces?page=1&page_size=50`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (tracesRes.ok) {
        const t = await tracesRes.json();
        setVariantTraces(t.traces || []);
        setVariantTracesTotal(t.total || 0);
      }
    } catch (e) {
      console.error('Failed to load variant detail:', e);
      push({ kind: 'error', message: 'Failed to load variant details' });
    } finally {
      setIsLoadingVariantDetail(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // When opening create modal, load available domains
  useEffect(() => {
    if (showCreateForm) {
      fetchPromptDomains();
    }
  }, [showCreateForm, fetchPromptDomains]);

  // Reset pagination when switching jobs
  useEffect(() => {
    if (selectedJob?.job_id) {
      setVariantsPage(1);
    }
  }, [selectedJob?.job_id]);

  // Subscribe to SSE for progress
  const subscribeToProgress = useCallback((jobId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `${API_BASE}/${jobId}/stream?token=${token}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data: TelemetryEvent = JSON.parse(event.data);
        
        if (data.progress_percentage !== undefined && data.progress_percentage >= 0) {
          setProgress(data.progress_percentage ?? 0);
        }
        if (data.message) {
          setProgressMessage(data.message);
        }

        if (data.event_type === 'complete' || data.event_type === 'final') {
          setIsStarting(false);
          eventSource.close();
          fetchJobs();
          fetchJobDetails(jobId);
          fetchVariants(jobId);
        } else if (data.event_type === 'error' || data.event_type === 'cancelled') {
          setIsStarting(false);
          eventSource.close();
          fetchJobs();
        } else if (data.event_type === 'frontier') {
          // Refresh frontier data
          fetchJobDetails(jobId);
          fetchVariants(jobId);
        }
      } catch (e) {
        console.error('Failed to parse SSE event:', e);
      }
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      setIsStarting(false);
      eventSource.close();
      fetchJobs();
    };
  }, [token, fetchJobs, fetchJobDetails, fetchVariants]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Create optimizer job
  const createJob = async () => {
    if (!selectedWorkspace) {
      push({ kind: 'error', message: 'Please select a workspace first' });
      return;
    }
    
    const hasAnyComponentValue = formData.components.some((c) => (c.initial_value || '').trim().length > 0);
    const canPrefillFromWorkspace = !!currentWorkspaceName && !!formData.use_prompt_management;

    if (!formData.name || (!hasAnyComponentValue && !canPrefillFromWorkspace)) {
      push({ kind: 'error', message: 'Please provide a name and either component values or a workspace to prefill from Prompt Management' });
      return;
    }

    setIsCreating(true);
    setProgress(0);
    setProgressMessage('Creating optimization job...');

    try {
      const res = await fetch(API_BASE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          domain: currentWorkspaceName,
          rag_domain_id: selectedWorkspaceId,
          use_prompt_management: formData.use_prompt_management,
          import_prompt_feedback: formData.import_prompt_feedback,
          prompt_feedback_environment: formData.prompt_feedback_environment,
          prompt_feedback_limit: formData.prompt_feedback_limit,
          components: formData.components
            .filter((c) => c.component_type) // allow empty initial_value (backend can prefill)
            .map((c) => ({
              component_type: c.component_type,
              initial_value: (c.initial_value || '').trim() || undefined,
            })),
          objectives: formData.objectives,
          population_size: formData.population_size,
          max_iterations: formData.max_iterations,
          eval_budget: formData.eval_budget,
          mutation_rate: formData.mutation_rate,
          crossover_rate: formData.crossover_rate,
          elite_count: formData.elite_count,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setIsStarting(true);
        setShowCreateForm(false);
        subscribeToProgress(data.job_id);
        setTimeout(fetchJobs, 1000);
        push({ kind: 'success', message: 'Optimization job started!' });
      } else {
        const error = await res.json();
        // Handle Pydantic validation errors (array of {msg, loc, type})
        let errorMessage = 'Failed to create job';
        if (Array.isArray(error.detail)) {
          errorMessage = error.detail.map((e: any) => e.msg || e.message).join(', ');
        } else if (typeof error.detail === 'string') {
          errorMessage = error.detail;
        }
        push({ kind: 'error', message: errorMessage });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to create optimization job' });
    } finally {
      setIsCreating(false);
    }
  };

  // Pause/resume job
  const pauseJob = async (jobId: string) => {
    try {
      const res = await fetch(`${API_BASE}/${jobId}/pause`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        fetchJobs();
        if (selectedJob?.job_id === jobId) {
          fetchJobDetails(jobId);
        }
      }
    } catch (e) {
      console.error('Failed to pause job:', e);
    }
  };

  const resumeJob = async (jobId: string) => {
    try {
      const res = await fetch(`${API_BASE}/${jobId}/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        setIsStarting(true);
        subscribeToProgress(jobId);
        fetchJobs();
      }
    } catch (e) {
      console.error('Failed to resume job:', e);
    }
  };

  // Cancel job
  const cancelJob = async (jobId: string) => {
    try {
      await fetch(`${API_BASE}/${jobId}/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      setIsStarting(false);
      fetchJobs();
    } catch (e) {
      console.error('Failed to cancel job:', e);
    }
  };

  // Delete job
  const deleteJob = async (jobId: string) => {
    if (!window.confirm('Delete this optimization job? This will remove all variants and results.')) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/${jobId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        setJobs(prev => prev.filter(j => j.job_id !== jobId));
        if (selectedJob?.job_id === jobId) {
          setSelectedJob(null);
          setVariants([]);
          setFrontier([]);
        }
        push({ kind: 'success', message: 'Deleted optimization job' });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to delete job' });
    }
  };

  // Promote state
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [promoteData, setPromoteData] = useState({
    variantId: '',
    domain: 'fasb',
    environment: 'dev',
    autoActivate: false,
  });

  // Promote variant
  const promoteVariant = async (variantId: string, environment: string, domain?: string, autoActivate?: boolean) => {
    if (!selectedJob) return;

    try {
      const res = await fetch(`${API_BASE}/${selectedJob.job_id}/variants/${variantId}/promote`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ 
          environment,
          domain: domain || promoteData.domain,
          auto_activate: autoActivate !== undefined ? autoActivate : promoteData.autoActivate,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const promptCount = data.prompts_created?.length || 0;
        push({ 
          kind: 'success', 
          message: `Promoted to ${environment}! ${promptCount} prompt(s) created${data.auto_activated ? ' and activated' : ''}.` 
        });
        fetchVariants(selectedJob.job_id);
        setShowPromoteModal(false);
      } else {
        const error = await res.json();
        const errorMessage = Array.isArray(error.detail) 
          ? error.detail.map((e: any) => e.msg || e.message).join(', ')
          : (error.detail || 'Failed to promote variant');
        push({ kind: 'error', message: errorMessage });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to promote variant' });
    }
  };

  const openPromoteModal = (variantId: string) => {
    setPromoteData({ ...promoteData, variantId });
    setShowPromoteModal(true);
  };

  // Feedback functions
  const fetchVariantFeedback = async (variantId: string) => {
    if (!selectedJob) return;
    
    try {
      const res = await fetch(`${API_BASE}/${selectedJob.job_id}/variants/${variantId}/feedback`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (res.ok) {
        const data = await res.json();
        setVariantFeedback(data.feedback || []);
      }
    } catch (e) {
      console.error('Failed to fetch feedback:', e);
    }
  };

  const submitFeedback = async () => {
    if (!selectedJob || !selectedVariant) return;
    
    setIsSubmittingFeedback(true);
    try {
      const res = await fetch(
        `${API_BASE}/${selectedJob.job_id}/variants/${selectedVariant.variant_id}/feedback`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            feedback_type: 'overall',
            rating: feedbackData.rating,
            comment: feedbackData.comment || null,
            tags: feedbackData.tags.length > 0 ? feedbackData.tags : null,
            improvement_suggestions: feedbackData.improvement_suggestions || null,
          }),
        }
      );

      if (res.ok) {
        push({ kind: 'success', message: 'Feedback submitted successfully!' });
        // Reset form
        setFeedbackData({
          rating: 'neutral',
          comment: '',
          tags: [],
          improvement_suggestions: '',
        });
        setShowFeedbackForm(false);
        // Refresh feedback list
        fetchVariantFeedback(selectedVariant.variant_id);
      } else {
        const error = await res.json();
        push({ kind: 'error', message: error.detail || 'Failed to submit feedback' });
      }
    } catch (e) {
      push({ kind: 'error', message: 'Failed to submit feedback' });
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const toggleFeedbackTag = (tag: string) => {
    setFeedbackData(prev => ({
      ...prev,
      tags: prev.tags.includes(tag)
        ? prev.tags.filter(t => t !== tag)
        : [...prev.tags, tag],
    }));
  };

  // Load feedback when variant is selected
  useEffect(() => {
    if (selectedVariant && selectedJob) {
      fetchVariantFeedback(selectedVariant.variant_id);
    } else {
      setVariantFeedback([]);
    }
  }, [selectedVariant?.variant_id, selectedJob?.job_id]);

  // Helper functions
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-emerald-500" />;
      case 'failed':
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      case 'running':
        return <ArrowPathIcon className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'paused':
        return <PauseIcon className="h-5 w-5 text-yellow-500" />;
      case 'cancelled':
        return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-400 dark:text-gray-500" />;
    }
  };

  const formatScore = (score?: number) => {
    if (score === undefined || score === null || isNaN(score)) return '—';
    return (score * 100).toFixed(1) + '%';
  };

  const formatLatency = (ms?: number) => {
    if (ms === undefined || ms === null) return '—';
    return ms < 1000 ? `${ms.toFixed(0)}ms` : `${(ms / 1000).toFixed(1)}s`;
  };

  // DataTable column definitions for variants
  const variantColumns: Column<CandidateVariant>[] = React.useMemo(
    () => [
      {
        id: 'variant_id',
        header: 'Variant',
        accessorKey: 'variant_id',
        width: '100px',
        cell: ({ row }) => (
          <div className="text-charcoal dark:text-gray-100 truncate" title={row.variant_id}>
            {row.is_baseline ? (
              <span className="text-yellow-500">baseline</span>
            ) : (
              row.variant_id.substring(0, 12)
            )}
          </div>
        ),
      },
      {
        id: 'generation',
        header: 'Gen',
        accessorFn: (row) => row.generation ?? 0,
        width: '60px',
      },
      {
        id: 'status',
        header: 'Status',
        accessorKey: 'status',
        width: '90px',
        cell: ({ row }) => (
          <Badge
            variant={
              row.status === 'evaluated' ? 'success'
              : row.status === 'evaluating' ? 'info'
              : row.status === 'promoted' ? 'brand'
              : row.status === 'failed' ? 'danger'
              : 'default'
            }
          >
            {row.status}
          </Badge>
        ),
      },
      {
        id: 'pareto',
        header: 'Pareto',
        align: 'center' as const,
        width: '70px',
        cell: ({ row }) => (
          row.pareto_rank === 0 ? (
            <CheckCircleIcon className="h-5 w-5 text-emerald-500 mx-auto" title="On Pareto frontier" />
          ) : row.pareto_rank !== undefined ? (
            <span className="text-gray-500 dark:text-gray-400">{row.pareto_rank}</span>
          ) : (
            <span className="text-gray-400">—</span>
          )
        ),
      },
      {
        id: 'quality',
        header: 'Quality',
        accessorFn: (row) => formatScore(row.scores.quality_score),
        align: 'center' as const,
        width: '80px',
      },
      {
        id: 'groundedness',
        header: 'Ground.',
        accessorFn: (row) => formatScore(row.scores.groundedness_score),
        align: 'center' as const,
        width: '80px',
      },
      {
        id: 'citation',
        header: 'Citation',
        accessorFn: (row) => formatScore(row.scores.citation_accuracy),
        align: 'center' as const,
        width: '80px',
      },
      {
        id: 'latency',
        header: 'Latency',
        accessorFn: (row) => formatLatency(row.scores.avg_latency_ms),
        align: 'center' as const,
        width: '80px',
      },
      {
        id: 'actions',
        header: 'Actions',
        width: '100px',
        cell: ({ row }) => (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={(e) => { e.stopPropagation(); openVariantDetails(row); }}
              className="text-gray-400 dark:text-gray-500 hover:text-charcoal dark:hover:text-gray-100"
              title="View details"
            >
              <EyeIcon className="h-4 w-4" />
            </Button>
            {row.pareto_rank === 0 && !row.is_promoted && (
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={(e) => { e.stopPropagation(); openPromoteModal(row.variant_id); }}
                className="text-gray-400 dark:text-gray-500 hover:text-eliza-red"
                title="Promote to Prompt Management"
              >
                <ArrowUpIcon className="h-4 w-4" />
              </Button>
            )}
            {row.is_promoted && (
              <span className="text-xs text-purple-400">
                {row.promoted_to}
              </span>
            )}
          </div>
        ),
      },
    ],
    [selectedJob]
  );

  return (
    <Layout>
      <Page layout="full-width">
      <PageHeader
        title="GEPA Optimizer"
        description="Genetic Prompt Algorithm - Optimize your RAG prompts using evolutionary search"
        actions={
          <Button
            variant="default"
            onClick={() => setShowCreateForm(true)}
            disabled={!selectedWorkspace}
          >
            <PlusIcon className="h-4 w-4" />
            New Optimization
          </Button>
        }
      />

      <PageBody fill padded={false}>
        {/* Workspace bar - matches Evals page pattern */}
        <div className="flex items-center gap-4 px-6 py-2 h-[52px] border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400 whitespace-nowrap">Workspace</span>
            <WorkspaceSelector
              workspaces={workspaces}
              selectedWorkspaceId={selectedWorkspaceId}
              onSelect={(id) => {
                setSelectedWorkspaceId(id);
                setSelectedJob(null);
                setVariants([]);
                setFrontier([]);
              }}
              isLoading={isLoadingWorkspaces}
              error={workspacesError}
              onRefresh={refreshWorkspaces}
              placeholder="Select workspace"
            />
            {selectedWorkspace && (
              <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                {selectedWorkspace.document_count} docs &middot; {selectedWorkspace.chunk_count} chunks
              </span>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel - Jobs List */}
          <div className="w-80 flex flex-col border-r border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface shrink-0">
            <div className="p-3 border-b border-gray-200 dark:border-dark-border flex items-center justify-between">
              <h3 className="text-sm font-medium text-charcoal dark:text-gray-100">Optimization Jobs</h3>
              <Button variant="ghost" size="sm" onClick={fetchJobs} className="h-7 w-7 p-0">
                <ArrowPathIcon className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-3">
              {/* Progress indicator for running job */}
              {isStarting && (
                <div className="mb-3 p-3 bg-blue-500/10 rounded-lg border border-blue-500/30">
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-gray-500 dark:text-gray-400">{progressMessage}</span>
                    <span className="text-eliza-red font-medium">{(progress ?? 0).toFixed(0)}%</span>
                  </div>
                  <Progress value={progress ?? 0} size="md" />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const runningJob = jobs.find(j => j.status === 'running');
                      if (runningJob) cancelJob(runningJob.job_id);
                    }}
                    className="mt-2 text-xs text-red-400 hover:text-red-300"
                  >
                    <StopIcon className="h-3 w-3" />
                    Cancel
                  </Button>
                </div>
              )}

              {/* Job list */}
              <div className="space-y-1">
                {jobs.map((job) => {
                  const isActive = selectedJob?.job_id === job.job_id;
                  const canDelete = !['pending', 'running'].includes(job.status);

                  return (
                    <div
                      key={job.job_id}
                      className={`group flex items-stretch gap-1 rounded-lg border transition-colors ${
                        isActive
                          ? 'bg-eliza-red/10 border-eliza-red/30'
                          : 'bg-transparent border-transparent hover:bg-gray-50 dark:hover:bg-dark-surface-2 hover:border-gray-200 dark:hover:border-dark-border'
                      }`}
                    >
                      <button
                        onClick={() => {
                          fetchJobDetails(job.job_id);
                          fetchVariants(job.job_id);
                        }}
                        className="flex-1 text-left p-2"
                      >
                        <div className="flex items-center gap-2">
                          {getStatusIcon(job.status)}
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-charcoal dark:text-gray-100 truncate">{job.name}</div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              Gen {job.current_iteration ?? 0}/{job.max_iterations ?? 0} • {job.total_evals_used ?? 0} evals
                            </div>
                          </div>
                          {job.best_quality_score && (
                            <div className="text-sm font-medium text-emerald-500">
                              {formatScore(job.best_quality_score)}
                            </div>
                          )}
                        </div>
                      </button>

                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => deleteJob(job.job_id)}
                        disabled={!canDelete}
                        className={`rounded-lg text-gray-400 dark:text-gray-500 hover:text-charcoal dark:hover:text-gray-100 ${
                          canDelete ? 'opacity-0 group-hover:opacity-100 transition-opacity' : 'opacity-30 cursor-not-allowed'
                        }`}
                        title={canDelete ? 'Delete job' : 'Cancel running job first'}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  );
                })}

                {jobs.length === 0 && (
                  <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                    No optimization jobs yet
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Panel - Job Details */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-dark-surface">
            {selectedJob ? (
              <>
                {/* Job Header */}
                <div className="p-4 border-b border-gray-200 dark:border-dark-border">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(selectedJob.status)}
                      <div>
                        <h2 className="text-lg font-medium text-charcoal dark:text-gray-100">{selectedJob.name}</h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {selectedJob.target_components.length} components • {selectedJob.objectives.length} objectives
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {selectedJob.status === 'running' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => pauseJob(selectedJob.job_id)}
                        >
                          <PauseIcon className="h-4 w-4" />
                          Pause
                        </Button>
                      )}
                      {selectedJob.status === 'paused' && (
                        <Button
                          variant="brand"
                          size="sm"
                          onClick={() => resumeJob(selectedJob.job_id)}
                        >
                          <PlayIcon className="h-4 w-4" />
                          Resume
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Progress metrics */}
                  <div className="grid grid-cols-5 gap-3">
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-eliza-red">
                        {selectedJob.current_iteration ?? 0}/{selectedJob.max_iterations ?? 0}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Generations</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {selectedJob.total_evals_used ?? 0}/{selectedJob.eval_budget ?? 0}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Evaluations</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-emerald-500">
                        {formatScore(selectedJob.best_quality_score)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Best Quality</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {frontier.length}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Pareto Frontier</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {variants.length}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Total Variants</div>
                    </div>
                  </div>
                </div>

                {/* Variants Table */}
                <div className="flex-1 overflow-y-auto p-4">
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Candidate Variants</h3>
                  
                  <DataTable
                    data={variants}
                    columns={variantColumns}
                    getRowId={(row) => row.variant_id}
                    compact
                    hoverable
                    emptyMessage="No variants yet. Waiting for optimization to generate candidates."
                    onRowClick={(row) => openVariantDetails(row)}
                    paginated={variantsTotal > 12}
                    pageSize={12}
                    totalItems={variantsTotal || variants.length}
                  />

                  {variantsTotal > variants.length && (
                    <div className="mt-3 flex justify-end">
                      <Button variant="outline" size="sm" onClick={loadMoreVariants}>
                        Load more
                      </Button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <SparklesIcon className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
                  <h3 className="mt-4 text-sm font-medium text-charcoal dark:text-gray-100">Select an optimization job to view details</h3>
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">or create a new optimization</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Create Form Sheet */}
        <Sheet open={showCreateForm} onClose={() => setShowCreateForm(false)}>
          <SheetContent side="right" size="2xl">
            <SheetHeader>
              <div>
                <SheetTitle>New GEPA Optimization</SheetTitle>
                <SheetDescription>Configure your prompt optimization run</SheetDescription>
              </div>
            </SheetHeader>

            <SheetBody className="space-y-5">
              {/* Basic Info */}
              <div>
                <Label className="mb-2 block">Name</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Optimize FASB RAG Prompts"
                />
              </div>

              <div>
                <Label className="mb-2 block">Description (optional)</Label>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  placeholder="Describe your optimization goals..."
                  className="min-h-0"
                />
              </div>

              {/* Workspace + Prefill */}
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <Label className="mb-2 block">Workspace</Label>
                  {selectedWorkspace ? (
                    <div className="p-3 bg-eliza-red/5 border border-eliza-red/20 rounded-lg">
                      <div className="font-medium text-charcoal dark:text-gray-100">{selectedWorkspace.display_name}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {selectedWorkspace.document_count} documents • {selectedWorkspace.chunk_count} chunks
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-sm text-yellow-500">
                      No workspace selected. Please select one from the header.
                    </div>
                  )}
                  <div className="mt-3">
                    <Checkbox
                      checked={formData.use_prompt_management}
                      onChange={(e) => setFormData({ ...formData, use_prompt_management: e.target.checked })}
                      label="Prefill missing component prompts from Prompt Management"
                    />
                  </div>

                  <div className="mt-3">
                    <Checkbox
                      checked={formData.import_prompt_feedback}
                      onChange={(e) => setFormData({ ...formData, import_prompt_feedback: e.target.checked })}
                      label="Import prod feedback for this domain into the run"
                      description="Used immediately for mutations"
                    />
                  </div>

                  {formData.import_prompt_feedback && (
                    <div className="mt-2 grid grid-cols-3 gap-2">
                      <div>
                        <Label className="text-xs mb-1 block">Env</Label>
                        <Select
                          value={formData.prompt_feedback_environment}
                          onValueChange={(v) => setFormData({ ...formData, prompt_feedback_environment: v as any })}
                        >
                          <SelectOption value="prod">prod</SelectOption>
                          <SelectOption value="staging">staging</SelectOption>
                          <SelectOption value="dev">dev</SelectOption>
                        </Select>
                      </div>
                      <div>
                        <Label className="text-xs mb-1 block">Limit</Label>
                        <Input
                          type="number"
                          min={1}
                          max={200}
                          value={formData.prompt_feedback_limit}
                          onChange={(e) => setFormData({ ...formData, prompt_feedback_limit: parseInt(e.target.value) || 20 })}
                        />
                      </div>
                      <div className="flex items-end">
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          GEPA will auto-import on start
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex items-end">
                  <Button
                    variant="outline"
                    onClick={loadWorkspacePrompts}
                    disabled={isLoadingDomainPrompts}
                    className="w-full"
                  >
                    {isLoadingDomainPrompts ? 'Loading…' : 'Load current prompts'}
                  </Button>
                </div>
              </div>

              {/* Components */}
              <div>
                <Label className="mb-2 block">Components to Optimize</Label>
                {formData.components.map((comp, idx) => (
                  <div key={idx} className="mb-3">
                    <div className="flex items-center gap-2 mb-1">
                      <Select
                        value={comp.component_type}
                        onValueChange={(v) => {
                          const newComps = [...formData.components];
                          newComps[idx].component_type = v;
                          setFormData({ ...formData, components: newComps });
                        }}
                      >
                        <SelectOption value="query_rewrite_prompt">Query Rewrite Prompt</SelectOption>
                        <SelectOption value="answer_synthesis_prompt">Answer Synthesis Prompt</SelectOption>
                        <SelectOption value="retrieval_instructions">Retrieval Instructions</SelectOption>
                        <SelectOption value="tool_instructions">Tool Instructions</SelectOption>
                        <SelectOption value="system_prompt">System Prompt</SelectOption>
                      </Select>
                    </div>
                    <Textarea
                      value={comp.initial_value ?? ''}
                      onChange={(e) => {
                        const newComps = [...formData.components];
                        newComps[idx].initial_value = e.target.value;
                        setFormData({ ...formData, components: newComps });
                      }}
                      rows={3}
                      placeholder="Enter your baseline prompt text..."
                      className="min-h-0 font-mono text-sm"
                    />
                  </div>
                ))}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setFormData({
                    ...formData,
                    components: [...formData.components, { component_type: 'system_prompt', initial_value: '' }]
                  })}
                  className="text-sm text-eliza-red hover:underline"
                >
                  + Add component
                </Button>
              </div>

              {/* Algorithm Parameters */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label className="text-xs mb-1 block">Population Size</Label>
                  <Input
                    type="number"
                    value={formData.population_size}
                    onChange={(e) => setFormData({ ...formData, population_size: parseInt(e.target.value) || 10 })}
                    min={4}
                    max={50}
                  />
                </div>
                <div>
                  <Label className="text-xs mb-1 block">Max Iterations</Label>
                  <Input
                    type="number"
                    value={formData.max_iterations}
                    onChange={(e) => setFormData({ ...formData, max_iterations: parseInt(e.target.value) || 20 })}
                    min={1}
                    max={100}
                  />
                </div>
                <div>
                  <Label className="text-xs mb-1 block">Eval Budget</Label>
                  <Input
                    type="number"
                    value={formData.eval_budget}
                    onChange={(e) => setFormData({ ...formData, eval_budget: parseInt(e.target.value) || 500 })}
                    min={10}
                    max={5000}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label className="text-xs mb-1 block">Mutation Rate</Label>
                  <Input
                    type="number"
                    value={formData.mutation_rate}
                    onChange={(e) => setFormData({ ...formData, mutation_rate: parseFloat(e.target.value) || 0.3 })}
                    min={0}
                    max={1}
                    step={0.1}
                  />
                </div>
                <div>
                  <Label className="text-xs mb-1 block">Crossover Rate</Label>
                  <Input
                    type="number"
                    value={formData.crossover_rate}
                    onChange={(e) => setFormData({ ...formData, crossover_rate: parseFloat(e.target.value) || 0.5 })}
                    min={0}
                    max={1}
                    step={0.1}
                  />
                </div>
                <div>
                  <Label className="text-xs mb-1 block">Elite Count</Label>
                  <Input
                    type="number"
                    value={formData.elite_count}
                    onChange={(e) => setFormData({ ...formData, elite_count: parseInt(e.target.value) || 2 })}
                    min={1}
                    max={10}
                  />
                </div>
              </div>
            </SheetBody>

            <SheetFooter className="flex items-center gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => setShowCreateForm(false)}>
                Close
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={createJob}
                disabled={isCreating}
              >
                {isCreating ? (
                  <Spinner size="sm" />
                ) : (
                  <PlayIcon className="h-4 w-4" />
                )}
                Start Optimization
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        {/* Variant Detail Modal */}
        <Modal open={!!selectedVariant} onClose={() => setSelectedVariant(null)}>
          <ModalContent size="full" className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <ModalHeader>
              <ModalTitle>Variant Details</ModalTitle>
              <ModalDescription>{selectedVariant?.variant_id}</ModalDescription>
            </ModalHeader>

            <ModalBody className="space-y-6">
              {isLoadingVariantDetail && (
                <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-4 text-sm text-gray-500 dark:text-gray-400">
                  Loading full variant details (prompt text, diffs, evals, traces)…
                </div>
              )}

              {selectedVariant && (
                <>
                  {/* Scores */}
                  <div className="grid grid-cols-5 gap-3">
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-emerald-500">
                        {formatScore(selectedVariant.scores.quality_score)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Quality</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {formatScore(selectedVariant.scores.groundedness_score)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Groundedness</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {formatScore(selectedVariant.scores.citation_accuracy)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Citation</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {formatLatency(selectedVariant.scores.avg_latency_ms)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Latency</div>
                    </div>
                    <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-center">
                      <div className="text-lg font-medium text-charcoal dark:text-gray-100">
                        {selectedVariant.scores.avg_cost ? `$${selectedVariant.scores.avg_cost.toFixed(4)}` : '—'}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Cost</div>
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Generation:</span>{' '}
                      <span className="text-charcoal dark:text-gray-100">{selectedVariant.generation ?? 0}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Mutation:</span>{' '}
                      <span className="text-charcoal dark:text-gray-100">{selectedVariant.mutation_type || '—'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Pareto Rank:</span>{' '}
                      <span className="text-charcoal dark:text-gray-100">
                        {selectedVariant.pareto_rank === 0 ? 'Frontier' : selectedVariant.pareto_rank ?? '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500 dark:text-gray-400">Status:</span>{' '}
                      <span className="text-charcoal dark:text-gray-100">{selectedVariant.status}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  {selectedVariant.pareto_rank === 0 && !selectedVariant.is_promoted && (
                    <div className="flex gap-3">
                      <Button
                        variant="brand"
                        size="sm"
                        onClick={() => {
                          openPromoteModal(selectedVariant.variant_id);
                          setSelectedVariant(null);
                        }}
                      >
                        <ArrowUpIcon className="h-4 w-4" />
                        Promote to Prompt Management
                      </Button>
                    </div>
                  )}

                  {/* Prompt components / diffs */}
                  <div className="border-t border-gray-200 dark:border-dark-border pt-6">
                    <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Prompt Components</h3>

                    {selectedVariantDetail?.component_diffs?.length ? (
                      <div className="space-y-3">
                        {selectedVariantDetail.component_diffs.map((d) => (
                          <details key={d.component_type} className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3">
                            <summary className="cursor-pointer text-sm text-charcoal dark:text-gray-100">
                              <span className="font-medium">{d.component_type}</span>
                              {typeof d.similarity_score === 'number' && (
                                <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                                  similarity {(d.similarity_score * 100).toFixed(1)}%
                                </span>
                              )}
                            </summary>
                            <div className="mt-3 grid grid-cols-2 gap-3">
                              <div>
                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Baseline</div>
                                <pre className="whitespace-pre-wrap text-xs font-mono text-charcoal dark:text-gray-100 bg-white dark:bg-dark-surface rounded p-2 border border-gray-200 dark:border-dark-border">
                                  {d.baseline_value}
                                </pre>
                              </div>
                              <div>
                                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Variant</div>
                                <pre className="whitespace-pre-wrap text-xs font-mono text-charcoal dark:text-gray-100 bg-white dark:bg-dark-surface rounded p-2 border border-gray-200 dark:border-dark-border">
                                  {d.variant_value}
                                </pre>
                              </div>
                            </div>

                            {(d.added_lines?.length || d.removed_lines?.length) && (
                              <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                                <div>
                                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Added</div>
                                  <div className="bg-white dark:bg-dark-surface rounded p-2 border border-gray-200 dark:border-dark-border">
                                    {(d.added_lines || []).slice(0, 50).map((l, i) => (
                                      <div key={i} className="text-emerald-400 font-mono whitespace-pre-wrap">+ {l}</div>
                                    ))}
                                  </div>
                                </div>
                                <div>
                                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Removed</div>
                                  <div className="bg-white dark:bg-dark-surface rounded p-2 border border-gray-200 dark:border-dark-border">
                                    {(d.removed_lines || []).slice(0, 50).map((l, i) => (
                                      <div key={i} className="text-red-400 font-mono whitespace-pre-wrap">- {l}</div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            )}
                          </details>
                        ))}
                      </div>
                    ) : selectedVariantDetail?.component_values ? (
                      <div className="space-y-3">
                        {Object.entries(selectedVariantDetail.component_values).map(([k, v]) => (
                          <details key={k} className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3">
                            <summary className="cursor-pointer text-sm text-charcoal dark:text-gray-100">
                              <span className="font-medium">{k}</span>
                            </summary>
                            <pre className="mt-2 whitespace-pre-wrap text-xs font-mono text-charcoal dark:text-gray-100 bg-white dark:bg-dark-surface rounded p-2 border border-gray-200 dark:border-dark-border">
                              {v}
                            </pre>
                          </details>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500 dark:text-gray-400">No component detail loaded yet.</div>
                    )}
                  </div>

                  {/* Eval Results + Traces (quick view) */}
                  <div className="border-t border-gray-200 dark:border-dark-border pt-6">
                    <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-3">Evaluations & Traces</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-sm text-charcoal dark:text-gray-100">Eval results</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">{variantEvalTotal || variantEvalResults.length} total</div>
                        </div>
                        {variantEvalResults.length ? (
                          <div className="space-y-2">
                            {variantEvalResults.slice(0, 10).map((r) => (
                              <div key={r.id} className="text-xs">
                                <div className="text-charcoal dark:text-gray-100 truncate" title={r.question}>{r.question}</div>
                                <div className="text-gray-500 dark:text-gray-400">
                                  {r.verdict || '—'} • {r.latency_ms ? `${Math.round(r.latency_ms)}ms` : '—'}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-gray-500 dark:text-gray-400">No eval results loaded.</div>
                        )}
                      </div>

                      <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-sm text-charcoal dark:text-gray-100">Traces</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">{variantTracesTotal || variantTraces.length} total</div>
                        </div>
                        {variantTraces.length ? (
                          <div className="space-y-2">
                            {variantTraces.slice(0, 10).map((t) => (
                              <div key={t.id} className="text-xs">
                                <div className="text-charcoal dark:text-gray-100 truncate" title={t.trace_id}>{t.trace_type}: {t.trace_id}</div>
                                <div className="text-gray-500 dark:text-gray-400">
                                  {t.total_latency_ms ? `${Math.round(t.total_latency_ms)}ms` : '—'} • {t.error_count ? `${t.error_count} errors` : '0 errors'}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-gray-500 dark:text-gray-400">No traces loaded.</div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Human Feedback Section */}
                  <div className="border-t border-gray-200 dark:border-dark-border pt-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-sm font-medium text-charcoal dark:text-gray-100">Human Feedback</h3>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowFeedbackForm(!showFeedbackForm)}
                      >
                        {showFeedbackForm ? 'Cancel' : '+ Add Feedback'}
                      </Button>
                    </div>

                    {/* Feedback Form */}
                    {showFeedbackForm && (
                      <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-4 mb-4 space-y-4">
                        {/* Rating */}
                        <div>
                          <Label className="text-xs block mb-2">Rating</Label>
                          <div className="flex gap-2">
                            {RATING_OPTIONS.map((opt) => (
                              <button
                                key={opt.value}
                                onClick={() => setFeedbackData(prev => ({ ...prev, rating: opt.value }))}
                                className={`flex-1 p-2 rounded-lg border text-center transition-all ${
                                  feedbackData.rating === opt.value
                                    ? 'border-eliza-red bg-eliza-red/10'
                                    : 'border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-gray-500'
                                }`}
                              >
                                <div className="text-xl">{opt.emoji}</div>
                                <div className={`text-xs ${opt.color}`}>{opt.label}</div>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Tags */}
                        <div>
                          <Label className="text-xs block mb-2">Tags (click to select)</Label>
                          <div className="flex flex-wrap gap-2">
                            {FEEDBACK_TAGS.map((tag) => (
                              <button
                                key={tag}
                                onClick={() => toggleFeedbackTag(tag)}
                                className={`px-2 py-1 rounded-lg text-xs transition-all ${
                                  feedbackData.tags.includes(tag)
                                    ? 'bg-eliza-red text-white'
                                    : 'bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-gray-500'
                                }`}
                              >
                                {tag.replace(/_/g, ' ')}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Comment */}
                        <div>
                          <Label className="text-xs block mb-2">Comment (optional)</Label>
                          <Textarea
                            value={feedbackData.comment}
                            onChange={(e) => setFeedbackData(prev => ({ ...prev, comment: e.target.value }))}
                            className="min-h-0 h-20"
                            placeholder="Describe what you liked or didn't like about this variant..."
                          />
                        </div>

                        {/* Improvement Suggestions */}
                        <div>
                          <Label className="text-xs block mb-2">Improvement Suggestions (optional)</Label>
                          <Textarea
                            value={feedbackData.improvement_suggestions}
                            onChange={(e) => setFeedbackData(prev => ({ ...prev, improvement_suggestions: e.target.value }))}
                            className="min-h-0 h-16"
                            placeholder="Specific suggestions for how to improve this prompt..."
                          />
                        </div>

                        {/* Submit */}
                        <Button
                          variant="brand"
                          className="w-full"
                          onClick={submitFeedback}
                          disabled={isSubmittingFeedback}
                        >
                          {isSubmittingFeedback ? <Spinner size="sm" /> : null}
                          {isSubmittingFeedback ? 'Submitting...' : 'Submit Feedback'}
                        </Button>
                      </div>
                    )}

                    {/* Existing Feedback */}
                    {variantFeedback.length > 0 ? (
                      <div className="space-y-3">
                        {variantFeedback.map((fb) => {
                          const ratingOpt = RATING_OPTIONS.find(r => r.value === fb.rating);
                          return (
                            <div key={fb.id} className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3">
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-lg">{ratingOpt?.emoji}</span>
                                  <span className={`text-sm font-medium ${ratingOpt?.color}`}>
                                    {ratingOpt?.label}
                                  </span>
                                  {fb.incorporated && (
                                    <Badge variant="success">Incorporated</Badge>
                                  )}
                                </div>
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  {new Date(fb.created_at).toLocaleDateString()}
                                </span>
                              </div>
                              {fb.comment && (
                                <p className="text-sm text-charcoal dark:text-gray-100 mb-2">{fb.comment}</p>
                              )}
                              {fb.tags && fb.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {fb.tags.map((tag) => (
                                    <span key={tag} className="text-xs bg-white dark:bg-dark-surface px-2 py-0.5 rounded text-gray-500 dark:text-gray-400">
                                      {tag.replace(/_/g, ' ')}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-center text-sm text-gray-500 dark:text-gray-400 py-4">
                        No feedback yet. Be the first to provide feedback on this variant!
                      </div>
                    )}
                  </div>
                </>
              )}
            </ModalBody>
          </ModalContent>
        </Modal>

        {/* Promote Modal */}
        <Modal open={showPromoteModal} onClose={() => setShowPromoteModal(false)}>
          <ModalContent size="md">
            <ModalHeader>
              <ModalTitle>Promote Variant to Prompt Management</ModalTitle>
              <ModalDescription>Create new prompt versions from this optimized variant</ModalDescription>
            </ModalHeader>

            <ModalBody className="space-y-4">
              <div>
                <Label className="mb-1 block">Target Domain</Label>
                <Select
                  value={promoteData.domain}
                  onValueChange={(v) => setPromoteData({ ...promoteData, domain: v })}
                >
                  <SelectOption value="fasb">FASB</SelectOption>
                  <SelectOption value="insurance">Insurance</SelectOption>
                  <SelectOption value="hr">HR</SelectOption>
                  <SelectOption value="general">General</SelectOption>
                </Select>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  The domain where prompts will be stored
                </p>
              </div>

              <div>
                <Label className="mb-1 block">Environment</Label>
                <div className="flex gap-2">
                  {['dev', 'staging', 'prod'].map((env) => (
                    <Button
                      key={env}
                      variant={promoteData.environment === env ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setPromoteData({ ...promoteData, environment: env })}
                      className="flex-1"
                    >
                      {env.charAt(0).toUpperCase() + env.slice(1)}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-lg">
                <Checkbox
                  checked={promoteData.autoActivate}
                  onChange={(e) => setPromoteData({ ...promoteData, autoActivate: e.target.checked })}
                  label="Auto-activate prompts"
                  description="Immediately use in RAG pipeline"
                />
              </div>

              <div className="text-xs text-gray-500 dark:text-gray-400 bg-blue-500/10 rounded-lg p-3">
                <p className="font-medium text-blue-400 mb-1">What happens:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>New prompt versions created in Prompt Management</li>
                  <li>Each component becomes a versioned prompt</li>
                  {promoteData.autoActivate && (
                    <li className="text-emerald-400">Prompts will be immediately active</li>
                  )}
                  {!promoteData.autoActivate && (
                    <li>Prompts will be drafts (manual activation needed)</li>
                  )}
                </ul>
              </div>
            </ModalBody>

            <ModalFooter className="justify-between">
              <Button variant="outline" onClick={() => setShowPromoteModal(false)}>
                Cancel
              </Button>
              <Button
                variant="brand"
                onClick={() => promoteVariant(
                  promoteData.variantId,
                  promoteData.environment,
                  promoteData.domain,
                  promoteData.autoActivate
                )}
              >
                Promote Variant
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </PageBody>
      </Page>
    </Layout>
  );
}

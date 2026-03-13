/**
 * RAG Evaluations Page - Eliza Forge
 * 
 * Run and monitor RAG evaluations with Langfuse tracing.
 * Features:
 * - Eval Sets library (built-in static + user-uploaded)
 * - Start new evaluation runs with configurable parameters
 * - Eval source selection (eval set or random sampling)
 * - Real-time progress tracking via SSE
 * - Results display with RAGAS metrics
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
  ModalBody,
  ModalFooter,
  Input,
  Select,
  SelectOption,
  Switch,
  Spinner,
  Card,
  CardContent,
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Label,
  Alert,
  Progress,
  Textarea,
  SectionHeader,
  RadioGroup,
  RadioCard,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  DataTable,
  Skeleton,
  SkeletonCard,
} from '../../components/ui';
import type { Column } from '../../components/ui';
import {
  PlayIcon,
  PlusIcon,
  StopIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  BeakerIcon,
  ClockIcon,
  TrashIcon,
  FolderOpenIcon,
  CloudArrowUpIcon,
  DocumentTextIcon,
  ArrowDownTrayIcon,
  DocumentDuplicateIcon,
  EyeIcon,
  TagIcon,
} from '@heroicons/react/24/outline';
import { useToasts } from '../../stores/useToasts';
import { useRAGWorkspaces } from '../../hooks/useRAGDomains';
import { WorkspaceSelector } from '../../components/common/RAGDomainSelector';
import { useAuth } from '../../contexts/AuthContext';

// Types
interface EvalRun {
  id: number;
  run_id: string;
  domain: string;
  eval_type?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  sample_size: number;
  difficulty_counts?: Record<string, number>;
  eval_source?: string;
  eval_set_id?: number;
  eval_set_name?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  metrics?: {
    total_questions: number;
    pass_count: number;
    fail_count: number;
    error_count: number;
    pass_rate: number;
    factual_correctness_mean?: number;
    faithfulness_mean?: number;
    context_precision_mean?: number;
    context_recall_mean?: number;
    citation_compliance_mean?: number;
    citation_page_accuracy_mean?: number;
  };
  chat_model?: string;
  created_at: string;
}

interface EvalResult {
  id: number;
  eval_id: string;
  question: string;
  expected_answer: string;
  model_response?: string;
  verdict?: 'pass' | 'fail' | 'error';
  verdict_reason?: string;
  difficulty?: string;
  factual_correctness?: number;
  faithfulness?: number;
  context_precision?: number;
  context_recall?: number;
  citation_compliance?: number;
  citation_page_score?: number;
}

interface EvalResultRow extends EvalResult {
  rowNumber: number;
}

interface EvalSet {
  id: number;
  customer_id?: string;
  name: string;
  description?: string;
  domain: string;
  set_type: 'static' | 'uploaded';
  category: string;
  example_count: number;
  difficulty_distribution?: Record<string, number>;
  tags?: string[];
  is_built_in: boolean;
  created_by_user_id?: number;
  created_at: string;
  updated_at?: string;
}

interface TelemetryEvent {
  event_type: string;
  stage_name?: string;
  message?: string;
  progress_percentage?: number;
  data?: any;
  timestamp?: string;
}

// Backend API URL - in dev mode, call backend directly
const API_BASE = window.location.port === '3000' 
  ? 'http://localhost:5001/api/v1/rag-eval' 
  : '/api/v1/rag-eval';

type TabType = 'runs' | 'sets';
type EvalSourceType = 'random_sampling' | 'eval_set';

export default function EvalsPage() {
  const token = localStorage.getItem('auth_token');
  const { hasAnyPermission } = useAuth();
  const canWriteEvals = hasAnyPermission(['bi:write', 'platform:admin']);
  
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
  
  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('runs');
  const [showNewEvalSheet, setShowNewEvalSheet] = useState(false);
  
  // Runs state
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [isLoadingRuns, setIsLoadingRuns] = useState(true);
  const [selectedRun, setSelectedRun] = useState<EvalRun | null>(null);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [isLoadingRunDetails, setIsLoadingRunDetails] = useState(false);
  const [resultsPage, setResultsPage] = useState(1);
  const [expandedResultRows, setExpandedResultRows] = useState<Set<string | number>>(new Set());
  const [isStarting, setIsStarting] = useState(false);
  const [progress, setProgress] = useState<number>(0);
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  
  // Eval Sets state
  const [evalSets, setEvalSets] = useState<EvalSet[]>([]);
  const [isLoadingEvalSets, setIsLoadingEvalSets] = useState(true);
  const [selectedEvalSet, setSelectedEvalSet] = useState<EvalSet | null>(null);
  const [previewQuestions, setPreviewQuestions] = useState<any[]>([]);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pendingDeleteRunId, setPendingDeleteRunId] = useState<string | null>(null);
  const [pendingDeleteEvalSet, setPendingDeleteEvalSet] = useState<{ id: number; name: string } | null>(null);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const { push } = useToasts();

  const displayRuns: EvalRun[] = React.useMemo(() => {
    const byId = new Map<string, EvalRun>();
    for (const r of runs) byId.set(r.run_id, r);
    if (selectedRun) byId.set(selectedRun.run_id, selectedRun);

    return Array.from(byId.values()).sort((a, b) => {
      const at = new Date(a.created_at).getTime();
      const bt = new Date(b.created_at).getTime();
      return bt - at;
    });
  }, [runs, selectedRun]);

  // Configuration state
  const [config, setConfig] = useState({
    evalSource: 'random_sampling' as EvalSourceType,
    evalSetId: null as number | null,
    easyCount: 3,
    mediumCount: 3,
    hardCount: 3,
    seed: 42,
    concurrency: 3,
    validateCitations: false,
  });
  
  // Get workspace name for API calls
  const currentWorkspaceName = selectedWorkspace?.name || 'fasb';

  // Upload form state - domain will be set from selectedRAGDomain
  const [uploadForm, setUploadForm] = useState({
    name: '',
    description: '',
    category: 'general',
    tags: '',
    file: null as File | null,
  });

  const fetchRuns = useCallback(async () => {
    setIsLoadingRuns(true);
    try {
      const params = new URLSearchParams({ page_size: '20' });
      if (currentWorkspaceName) params.set('domain', currentWorkspaceName);
      const response = await fetch(`${API_BASE}/runs?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setRuns(data.runs || []);
      } else {
        const errorText = await response.text();
        console.error('Fetch runs error:', response.status, errorText);
      }
    } catch (error) {
      console.error('Failed to fetch runs:', error);
    } finally {
      setIsLoadingRuns(false);
    }
  }, [token, currentWorkspaceName]);

  const fetchEvalSets = useCallback(async () => {
    setIsLoadingEvalSets(true);
    try {
      const params = new URLSearchParams();
      if (currentWorkspaceName) params.set('domain', currentWorkspaceName);
      const qs = params.toString();
      const response = await fetch(`${API_BASE}/eval-sets${qs ? `?${qs}` : ''}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setEvalSets(data.eval_sets || []);
      } else {
        const errorText = await response.text();
        console.error('Fetch eval sets error:', response.status, errorText);
      }
    } catch (error) {
      console.error('Failed to fetch eval sets:', error);
    } finally {
      setIsLoadingEvalSets(false);
    }
  }, [token, currentWorkspaceName]);

  // Fetch data on mount and when workspace changes
  useEffect(() => {
    fetchRuns();
    fetchEvalSets();
    setSelectedRun(null);
    setResults([]);
  }, [fetchRuns, fetchEvalSets]);

  const fetchRunDetails = async (runId: string) => {
    setIsLoadingRunDetails(true);
    try {
      const response = await fetch(`${API_BASE}/runs/${runId}?include_results=true&results_page_size=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setSelectedRun(data.summary);
        setResults(data.results || []);
        setActiveTab('runs');
      }
    } catch (error) {
      console.error('Failed to fetch run details:', error);
    } finally {
      setIsLoadingRunDetails(false);
    }
  };

  const fetchEvalSetPreview = async (evalSetId: number) => {
    try {
      const response = await fetch(`${API_BASE}/eval-sets/${evalSetId}/questions?limit=10`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const data = await response.json();
        setPreviewQuestions(data.questions || []);
        setShowPreviewModal(true);
      }
    } catch (error) {
      console.error('Failed to fetch preview:', error);
      push({ kind: 'error', message: 'Failed to load preview' });
    }
  };

  const startEvaluation = async () => {
    setIsStarting(true);
    setProgress(0);
    setProgressMessage('Starting evaluation...');

    if (!token) {
      push({ kind: 'error', message: 'Not authenticated. Please log in again.' });
      setIsStarting(false);
      return;
    }

    try {
      const requestBody: any = {
        domain: currentWorkspaceName,
        eval_source: config.evalSource,
        seed: config.seed,
        concurrency: config.concurrency,
        validate_citations: config.validateCitations,
      };

      if (config.evalSource === 'eval_set') {
        if (!config.evalSetId) {
          push({ kind: 'error', message: 'Please select an eval set' });
          setIsStarting(false);
          return;
        }
        requestBody.eval_set_id = config.evalSetId;
      } else {
        requestBody.difficulty_counts = {
          easy: config.easyCount,
          medium: config.mediumCount,
          hard: config.hardCount,
        };
      }

      // Use v2 endpoint
      const response = await fetch(`${API_BASE}/runs/v2`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(requestBody),
      });

      if (response.ok) {
        const data = await response.json();
        const runId = data.run_id;

        setShowNewEvalSheet(false);
        push({ kind: 'success', message: 'Run started' });

        setActiveRunId(runId);

        fetchRunDetails(runId);

        // Start SSE streaming
        subscribeToProgress(runId);
        
        // Refresh runs list
        setTimeout(fetchRuns, 1000);
      } else {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        let errorMsg = 'Failed to start evaluation';
        try {
          const error = JSON.parse(errorText);
          errorMsg = error.detail || errorMsg;
        } catch {
          errorMsg = errorText || `Error ${response.status}`;
        }
        push({ kind: 'error', message: errorMsg });
        setIsStarting(false);
      }
    } catch (error) {
      console.error('Failed to start evaluation:', error);
      push({ kind: 'error', message: error instanceof Error ? error.message : 'Failed to start evaluation' });
      setIsStarting(false);
    }
  };

  const deleteEvalRun = async (runId: string) => {
    if (!token) {
      push({ kind: 'error', message: 'Not authenticated. Please log in again.' });
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/runs/${runId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const txt = await res.text();
        push({ kind: 'error', message: `Delete failed (${res.status}): ${txt || 'Unknown error'}` });
        return;
      }

      setRuns((prev) => prev.filter((r) => r.run_id !== runId));
      if (selectedRun?.run_id === runId) {
        setSelectedRun(null);
        setResults([]);
      }
      push({ kind: 'success', message: 'Deleted evaluation run' });
    } catch (e) {
      push({ kind: 'error', message: `Delete failed: ${e instanceof Error ? e.message : 'Unknown error'}` });
    }
  };

  const deleteEvalSet = async (evalSetId: number) => {
    if (!token) {
      push({ kind: 'error', message: 'Not authenticated. Please log in again.' });
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/eval-sets/${evalSetId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const txt = await res.text();
        push({ kind: 'error', message: `Delete failed: ${txt || 'Unknown error'}` });
        return;
      }

      setEvalSets((prev) => prev.filter((s) => s.id !== evalSetId));
      push({ kind: 'success', message: 'Deleted eval set' });
    } catch (e) {
      push({ kind: 'error', message: `Delete failed: ${e instanceof Error ? e.message : 'Unknown error'}` });
    }
  };

  const duplicateEvalSet = async (evalSetId: number) => {
    if (!token) return;

    try {
      const res = await fetch(`${API_BASE}/eval-sets/${evalSetId}/duplicate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        push({ kind: 'success', message: `Duplicated as "${data.name}"` });
        fetchEvalSets();
      } else {
        const txt = await res.text();
        push({ kind: 'error', message: `Duplicate failed: ${txt}` });
      }
    } catch (e) {
      push({ kind: 'error', message: `Duplicate failed: ${e instanceof Error ? e.message : 'Unknown error'}` });
    }
  };

  const downloadEvalSet = async (evalSetId: number, name: string) => {
    if (!token) return;

    try {
      const res = await fetch(`${API_BASE}/eval-sets/${evalSetId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${name.replace(/[^\w\-]/g, '_')}.jsonl`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        push({ kind: 'error', message: 'Download failed' });
      }
    } catch (e) {
      push({ kind: 'error', message: `Download failed: ${e instanceof Error ? e.message : 'Unknown error'}` });
    }
  };

  const uploadEvalSet = async () => {
    setUploadError(null);

    if (!token || !uploadForm.file || !uploadForm.name) {
      const message = 'Name and file are required.';
      setUploadError(message);
      push({ kind: 'error', message });
      return;
    }
    
    if (!selectedWorkspace) {
      const message = 'Please select a workspace first.';
      setUploadError(message);
      push({ kind: 'error', message });
      return;
    }

    const validationError = await validateJsonlUploadFile(uploadForm.file);
    if (validationError) {
      setUploadError(validationError);
      push({ kind: 'error', message: validationError });
      return;
    }

    setUploadLoading(true);

    try {
      const formData = new FormData();
      formData.append('name', uploadForm.name);
      formData.append('description', uploadForm.description);
      formData.append('domain', currentWorkspaceName);
      formData.append('category', uploadForm.category);
      if (uploadForm.tags) formData.append('tags', uploadForm.tags);
      formData.append('file', uploadForm.file);

      const res = await fetch(`${API_BASE}/eval-sets`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setUploadError(null);
        push({ kind: 'success', message: `Uploaded "${data.name}" with ${data.example_count} questions` });
        setShowUploadModal(false);
        setUploadForm({ name: '', description: '', category: 'general', tags: '', file: null });
        fetchEvalSets();
      } else {
        const txt = await res.text();
        const message = extractErrorMessage(txt, 'Upload failed.');
        setUploadError(message);
        push({ kind: 'error', message });
      }
    } catch (e) {
      const message = `Upload failed: ${e instanceof Error ? e.message : 'Unknown error'}`;
      setUploadError(message);
      push({ kind: 'error', message });
    } finally {
      setUploadLoading(false);
    }
  };

  const subscribeToProgress = (runId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `${API_BASE}/runs/${runId}/stream?token=${token}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data: TelemetryEvent = JSON.parse(event.data);
        
        if (data.progress_percentage !== undefined && data.progress_percentage >= 0) {
          setProgress(data.progress_percentage);
        }
        if (data.message) {
          setProgressMessage(data.message);
        }

        if (data.event_type === 'complete' || data.event_type === 'final') {
          setIsStarting(false);
          setActiveRunId(null);
          eventSource.close();
          fetchRuns();
          fetchRunDetails(runId);
          push({ kind: 'success', message: 'Evaluation completed' });
        } else if (data.event_type === 'error' || data.event_type === 'cancelled') {
          setIsStarting(false);
          setActiveRunId(null);
          eventSource.close();
          fetchRuns();
          push({ kind: data.event_type === 'error' ? 'error' : 'warning', message: data.event_type === 'error' ? 'Evaluation failed' : 'Evaluation cancelled' });
        }
      } catch (e) {
        console.error('Failed to parse SSE event:', e);
      }
    };

    eventSource.onerror = () => {
      console.error('SSE connection error');
      setIsStarting(false);
      setActiveRunId(null);
      eventSource.close();
      fetchRuns();
    };
  };

  const cancelEvaluation = async (runId: string) => {
    try {
      await fetch(`${API_BASE}/runs/${runId}/cancel`, {
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
      setActiveRunId(null);
      fetchRuns();
      push({ kind: 'warning', message: 'Evaluation cancelled' });
    } catch (error) {
      console.error('Failed to cancel evaluation:', error);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    setResultsPage(1);
    setExpandedResultRows(new Set());
  }, [selectedRun?.run_id]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-emerald-500" />;
      case 'failed':
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      case 'running':
        return <ArrowPathIcon className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'cancelled':
        return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />;
      default:
        return <ClockIcon className="h-5 w-5 text-gray-500 dark:text-gray-400" />;
    }
  };

  const formatScore = (score?: number) => {
    if (score === undefined || score === null || isNaN(score)) return '—';
    return (score * 100).toFixed(1) + '%';
  };

  const extractErrorMessage = (raw: string, fallback: string) => {
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed?.detail === 'string' && parsed.detail.trim().length > 0) {
        return parsed.detail;
      }
      if (Array.isArray(parsed?.detail)) {
        return parsed.detail
          .map((d: any) => (typeof d?.msg === 'string' ? d.msg : JSON.stringify(d)))
          .join(', ');
      }
      return fallback;
    } catch {
      const trimmed = raw.trim();
      return trimmed.length > 0 ? trimmed : fallback;
    }
  };

  const validateJsonlUploadFile = useCallback(async (file: File): Promise<string | null> => {
    if (!file.name.toLowerCase().endsWith('.jsonl')) {
      return 'Invalid file type. Please upload a .jsonl file.';
    }
    if (file.size === 0) {
      return 'File is empty. Please upload a JSONL file with at least one question.';
    }
    if (file.size > 10 * 1024 * 1024) {
      return 'File too large. Max file size is 10MB.';
    }

    try {
      const previewText = await file.slice(0, 200_000).text();
      const lines = previewText
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0);

      if (lines.length === 0) {
        return 'File appears to be empty. Add at least one JSON line.';
      }

      const sampleLines = lines.slice(0, Math.min(lines.length, 5));
      for (let i = 0; i < sampleLines.length; i += 1) {
        const line = sampleLines[i];
        let parsed: any;
        try {
          parsed = JSON.parse(line);
        } catch {
          return `Invalid JSON on line ${i + 1}.`;
        }
        if (typeof parsed.question !== 'string' || parsed.question.trim().length === 0) {
          return `Line ${i + 1} is missing required field: question.`;
        }
        if (typeof parsed.reference_answer !== 'string' || parsed.reference_answer.trim().length === 0) {
          return `Line ${i + 1} is missing required field: reference_answer.`;
        }
      }
    } catch (error) {
      return `Could not read file: ${error instanceof Error ? error.message : 'Unknown error'}`;
    }

    return null;
  }, []);

  const selectedEvalSetForRun = evalSets.find(s => s.id === config.evalSetId);
  const resultRows: EvalResultRow[] = React.useMemo(
    () => results.map((result, idx) => ({ ...result, rowNumber: idx + 1 })),
    [results]
  );

  const resultColumns: Column<EvalResultRow>[] = React.useMemo(
    () => [
      {
        id: 'rowNumber',
        header: '#',
        accessorKey: 'rowNumber',
        width: '48px',
      },
      {
        id: 'question',
        header: 'Question',
        accessorKey: 'question',
        cell: ({ row }) => (
          <div>
            <div className="text-charcoal dark:text-gray-100 truncate max-w-md" title={row.question}>
              {row.question}
            </div>
            {row.verdict === 'fail' && row.verdict_reason && (
              <div className="text-xs text-red-400 mt-1 truncate" title={row.verdict_reason}>
                {row.verdict_reason}
              </div>
            )}
          </div>
        ),
      },
      {
        id: 'difficulty',
        header: 'Difficulty',
        accessorKey: 'difficulty',
        cell: ({ row }) => (
          <Badge
            variant={
              row.difficulty === 'easy'
                ? 'success'
                : row.difficulty === 'medium'
                  ? 'warning'
                  : row.difficulty === 'hard'
                    ? 'danger'
                    : 'default'
            }
          >
            {row.difficulty || '—'}
          </Badge>
        ),
      },
      {
        id: 'verdict',
        header: 'Verdict',
        accessorKey: 'verdict',
        align: 'center',
        cell: ({ row }) => (
          <>
            {row.verdict === 'pass' && <CheckCircleIcon className="h-5 w-5 text-emerald-500 mx-auto" />}
            {row.verdict === 'fail' && <XCircleIcon className="h-5 w-5 text-red-500 mx-auto" />}
            {row.verdict === 'error' && <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500 mx-auto" />}
            {!row.verdict && <span className="text-gray-400">—</span>}
          </>
        ),
      },
      {
        id: 'factual',
        header: 'Factual',
        accessorFn: (row) => formatScore(row.factual_correctness),
        align: 'center',
      },
      {
        id: 'faithful',
        header: 'Faithful',
        accessorFn: (row) => formatScore(row.faithfulness),
        align: 'center',
      },
      {
        id: 'citationPage',
        header: 'Citation Page',
        accessorFn: (row) => formatScore(row.citation_page_score),
        align: 'center',
      },
    ],
    []
  );

  return (
    <Layout>
      <Page layout="full-width">
      <PageHeader
        title="RAG Evaluations"
        description="Run and monitor RAG evaluation suites"
        actions={
          <div className="flex items-center gap-3">
            {canWriteEvals && (
              <Button
                variant="default"
                onClick={() => setShowNewEvalSheet(true)}
              >
                <PlusIcon className="h-4 w-4" />
                New Evaluation
              </Button>
            )}
          </div>
        }
      />

      <PageBody fill padded={false}>
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabType)} defaultValue="runs" className="flex flex-col flex-1 min-h-0">
          {/* Workspace + Tabs bar */}
          <div className="flex items-center gap-4 px-6 py-2 h-[52px] border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-bg shrink-0">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-gray-500 dark:text-gray-400 whitespace-nowrap">Workspace</span>
              <WorkspaceSelector
                workspaces={workspaces}
                selectedWorkspaceId={selectedWorkspaceId}
                onSelect={setSelectedWorkspaceId}
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
            <div className="ml-auto">
              <TabsList>
                <TabsTrigger value="runs">Runs</TabsTrigger>
                <TabsTrigger value="sets">Eval Sets</TabsTrigger>
              </TabsList>
            </div>
          </div>

          {/* Eval Sets Tab */}
          <TabsContent value="sets" className="flex-1 overflow-y-auto p-6 mt-0 bg-white dark:bg-dark-surface">
            <div>
              <SectionHeader
                title="Eval Sets Library"
                description="Built-in static sets and your uploaded sets"
                actions={
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={fetchEvalSets}>
                      <ArrowPathIcon className="h-4 w-4" />
                      Refresh
                    </Button>
                    {canWriteEvals && (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => {
                          setUploadError(null);
                          setShowUploadModal(true);
                        }}
                      >
                        <CloudArrowUpIcon className="h-4 w-4" />
                        Upload Eval Set
                      </Button>
                    )}
                  </div>
                }
              />

              {/* Built-in Sets */}
              <div className="mb-8 mt-6">
                <h3 className="text-xs font-medium text-gray-400 dark:text-gray-500 tracking-wide mb-3">
                  Built-in Static Sets
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {isLoadingEvalSets ? (
                    Array.from({ length: 3 }).map((_, idx) => <SkeletonCard key={`builtin-skeleton-${idx}`} />)
                  ) : (
                    <>
                      {evalSets.filter(s => s.is_built_in).map((set) => (
                        <Card key={set.id}>
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <h4 className="font-medium text-charcoal dark:text-gray-100">{set.name}</h4>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{set.description}</p>
                              </div>
                              <Badge variant="brand">Static</Badge>
                            </div>
                            <div className="mt-3 flex items-center gap-2 flex-wrap">
                              <Badge variant="default">{set.category}</Badge>
                              <span className="text-xs text-gray-500 dark:text-gray-400">{set.example_count} questions</span>
                            </div>
                            {set.difficulty_distribution && (
                              <div className="mt-2 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                                {Object.entries(set.difficulty_distribution).map(([diff, count]) => (
                                  <span key={diff}>{diff}: {count}</span>
                                ))}
                              </div>
                            )}
                            <div className="mt-3 flex items-center gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => { setSelectedEvalSet(set); fetchEvalSetPreview(set.id); }}
                                className="text-xs h-7 px-2"
                              >
                                <EyeIcon className="h-3 w-3" />
                                Preview
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => downloadEvalSet(set.id, set.name)}
                                className="text-xs h-7 px-2"
                              >
                                <ArrowDownTrayIcon className="h-3 w-3" />
                                Download
                              </Button>
                              {canWriteEvals && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => duplicateEvalSet(set.id)}
                                  className="text-xs h-7 px-2"
                                >
                                  <DocumentDuplicateIcon className="h-3 w-3" />
                                  Duplicate
                                </Button>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                      {evalSets.filter(s => s.is_built_in).length === 0 && (
                        <div className="col-span-full text-center py-8 border border-dashed border-gray-200 dark:border-dark-border rounded-lg">
                          <FolderOpenIcon className="mx-auto h-8 w-8 text-gray-300 dark:text-gray-600" />
                          <p className="mt-2 text-sm text-gray-400 dark:text-gray-500">No built-in sets available</p>
                          <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">Contact admin to seed static sets</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Uploaded Sets */}
              <div>
                <h3 className="text-xs font-medium text-gray-400 dark:text-gray-500 tracking-wide mb-3">
                  Uploaded Sets
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {isLoadingEvalSets ? (
                    Array.from({ length: 3 }).map((_, idx) => <SkeletonCard key={`uploaded-skeleton-${idx}`} />)
                  ) : (
                    <>
                      {evalSets.filter(s => !s.is_built_in).map((set) => (
                        <Card key={set.id}>
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <h4 className="font-medium text-charcoal dark:text-gray-100">{set.name}</h4>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{set.description || 'No description'}</p>
                              </div>
                              <Badge variant="info">Uploaded</Badge>
                            </div>
                            <div className="mt-3 flex items-center gap-2 flex-wrap">
                              <Badge variant="default">{set.category}</Badge>
                              <span className="text-xs text-gray-500 dark:text-gray-400">{set.example_count} questions</span>
                            </div>
                            {set.tags && set.tags.length > 0 && (
                              <div className="mt-2 flex items-center gap-1 flex-wrap">
                                <TagIcon className="h-3 w-3 text-gray-500 dark:text-gray-400" />
                                {set.tags.map((tag, i) => (
                                  <span key={i} className="text-xs text-gray-500 dark:text-gray-400">{tag}{i < set.tags!.length - 1 ? ',' : ''}</span>
                                ))}
                              </div>
                            )}
                            <div className="mt-3 flex items-center gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => { setSelectedEvalSet(set); fetchEvalSetPreview(set.id); }}
                                className="text-xs h-7 px-2"
                              >
                                <EyeIcon className="h-3 w-3" />
                                Preview
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => downloadEvalSet(set.id, set.name)}
                                className="text-xs h-7 px-2"
                              >
                                <ArrowDownTrayIcon className="h-3 w-3" />
                                Download
                              </Button>
                              {canWriteEvals && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setPendingDeleteEvalSet({ id: set.id, name: set.name })}
                                  className="text-xs h-7 px-2 text-red-500 hover:text-red-600"
                                >
                                  <TrashIcon className="h-3 w-3" />
                                  Delete
                                </Button>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                      {evalSets.filter(s => !s.is_built_in).length === 0 && (
                        <div className="col-span-full text-center py-8 border-2 border-dashed border-gray-200 dark:border-dark-border rounded-lg">
                          <CloudArrowUpIcon className="mx-auto h-8 w-8 text-gray-400 dark:text-gray-500" />
                          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">No uploaded eval sets yet</p>
                          {canWriteEvals && (
                            <Button
                              variant="link"
                              size="sm"
                              onClick={() => {
                                setUploadError(null);
                                setShowUploadModal(true);
                              }}
                              className="mt-2"
                            >
                              Upload your first eval set
                            </Button>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Runs Tab */}
          <TabsContent value="runs" className="flex-1 min-h-0 flex mt-0">
            {/* Run List */}
            <div className="w-80 flex flex-col border-r border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface shrink-0">
                <div className="p-3 border-b border-gray-200 dark:border-dark-border flex items-center justify-between">
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100">All Runs</h3>
                  <Button variant="ghost" size="sm" onClick={fetchRuns} className="h-7 w-7 p-0">
                    <ArrowPathIcon className="h-4 w-4" />
                  </Button>
                </div>
                
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                  {isLoadingRuns ? (
                    Array.from({ length: 6 }).map((_, idx) => (
                      <div key={`run-skeleton-${idx}`} className="rounded-lg border border-gray-200 dark:border-dark-border p-2">
                        <div className="flex items-center gap-2">
                          <Skeleton variant="circular" width={20} height={20} />
                          <div className="flex-1 space-y-1">
                            <Skeleton width="70%" />
                            <Skeleton width="45%" height={12} />
                          </div>
                          <Skeleton width={44} height={16} />
                        </div>
                      </div>
                    ))
                  ) : (
                    <>
                      {displayRuns.map((run) => {
                        const isActive = selectedRun?.run_id === run.run_id;
                        const isRunning = (run.status === 'running' || run.status === 'pending') && run.run_id === activeRunId;
                        const canDelete = canWriteEvals && !isRunning && run.status !== 'running' && run.status !== 'pending';

                        return (
                          <div
                            key={run.run_id}
                            className={`group flex items-stretch gap-1 rounded-lg border transition-colors ${
                              isActive
                                ? 'bg-eliza-red/10 border-eliza-red/30'
                                : 'bg-transparent border-transparent hover:bg-gray-50 dark:hover:bg-dark-surface-2 hover:border-gray-200 dark:hover:border-dark-border'
                            }`}
                          >
                            <button
                              onClick={() => fetchRunDetails(run.run_id)}
                              className="flex-1 text-left p-2"
                              title="View run"
                            >
                              <div className="flex items-center gap-2">
                                {getStatusIcon(run.status)}
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm text-charcoal dark:text-gray-100 truncate">
                                    {run.eval_set_name || `${run.domain.toUpperCase()} • ${run.sample_size}q`}
                                  </div>
                                  <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2">
                                    <span>{new Date(run.created_at).toLocaleDateString()}</span>
                                    {run.eval_source && (
                                      <Badge variant={run.eval_source === 'eval_set' ? 'info' : 'default'} className="text-[10px] px-1 py-0">
                                        {run.eval_source === 'eval_set' ? 'Set' : 'Rand'}
                                      </Badge>
                                    )}
                                  </div>
                                </div>
                                {run.metrics && (
                                  <div className="text-sm font-medium text-emerald-500">
                                    {run.metrics.pass_rate.toFixed(0)}%
                                  </div>
                                )}
                              </div>
                            </button>

                            {isRunning && canWriteEvals ? (
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => cancelEvaluation(run.run_id)}
                                className="rounded-lg text-red-400 hover:text-red-600"
                                title="Cancel evaluation"
                              >
                                <StopIcon className="h-4 w-4" />
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => setPendingDeleteRunId(run.run_id)}
                                className={`rounded-lg text-gray-400 dark:text-gray-500 hover:text-charcoal dark:hover:text-gray-100 ${
                                  canDelete ? 'opacity-0 group-hover:opacity-100 transition-opacity' : 'opacity-30 cursor-not-allowed'
                                }`}
                                title={canDelete ? 'Delete run' : 'Cannot delete while running'}
                                disabled={!canDelete}
                              >
                                <TrashIcon className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        );
                      })}
                      
                      {displayRuns.length === 0 && (
                        <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
                          No evaluation runs yet
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Results Panel */}
              <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-dark-surface">
                {selectedRun ? (
                  <>
                    {/* Results Header */}
                    <div className="p-4 border-b border-gray-200 dark:border-dark-border">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {getStatusIcon(selectedRun.status)}
                          <div>
                            <h2 className="text-lg font-medium text-charcoal dark:text-gray-100">
                              {selectedRun.eval_set_name || `${selectedRun.domain.toUpperCase()} Evaluation`}
                            </h2>
                            <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
                              <span>{selectedRun.sample_size} questions</span>
                              <span>•</span>
                              <span>{selectedRun.chat_model || 'gpt-4o'}</span>
                              {selectedRun.eval_source && (
                                <>
                                  <span>•</span>
                                  <Badge variant={selectedRun.eval_source === 'eval_set' ? 'info' : 'default'}>
                                    {selectedRun.eval_source === 'eval_set' ? 'Eval Set' : 'Random Sampling'}
                                  </Badge>
                                </>
                              )}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Compact Metrics Strip */}
                      {selectedRun.metrics && (
                        <div className="flex items-center gap-4 flex-wrap text-sm mt-1">
                          {(() => {
                            const pr = selectedRun.metrics!.pass_rate;
                            const prClass = pr >= 80 ? 'text-emerald-600 dark:text-emerald-400' : pr >= 60 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400';
                            return (
                              <span className={`font-semibold ${prClass}`}>
                                Pass Rate: {pr.toFixed(0)}%
                              </span>
                            );
                          })()}
                          <span className="text-gray-300 dark:text-gray-600">|</span>
                          {[
                            { label: 'Factual', value: selectedRun.metrics!.factual_correctness_mean },
                            { label: 'Faithful', value: selectedRun.metrics!.faithfulness_mean },
                            { label: 'Ctx Prec.', value: selectedRun.metrics!.context_precision_mean },
                            { label: 'Ctx Recall', value: selectedRun.metrics!.context_recall_mean },
                            { label: 'Citations', value: selectedRun.metrics!.citation_compliance_mean },
                            { label: 'Cite Page', value: selectedRun.metrics!.citation_page_accuracy_mean },
                          ].map((m) => (
                            <span key={m.label} className="text-gray-600 dark:text-gray-400 whitespace-nowrap">
                              <span className="text-gray-400 dark:text-gray-500">{m.label}:</span>{' '}
                              <span className="font-medium text-charcoal dark:text-gray-200">{formatScore(m.value)}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Results Table or Progress */}
                    <div className="flex-1 overflow-y-auto p-4">
                      {(selectedRun.status === 'running' || selectedRun.status === 'pending') && resultRows.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full gap-4">
                          {selectedRun.run_id === activeRunId && isStarting ? (
                            <div className="w-full max-w-md space-y-3">
                              <Progress value={progress} showLabel />
                              <p className="text-sm text-gray-500 dark:text-gray-400 text-center">{progressMessage}</p>
                            </div>
                          ) : (
                            <div className="text-center space-y-3">
                              <Spinner size="lg" />
                              <p className="text-sm text-gray-500 dark:text-gray-400">Evaluation in progress&hellip;</p>
                            </div>
                          )}
                          {canWriteEvals && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => cancelEvaluation(selectedRun.run_id)}
                              className="mt-2"
                            >
                              <StopIcon className="h-4 w-4" />
                              Cancel Evaluation
                            </Button>
                          )}
                        </div>
                      ) : (
                        <DataTable
                          data={resultRows}
                          columns={resultColumns}
                          getRowId={(row) => row.id}
                          loading={isLoadingRunDetails}
                          loadingRows={8}
                          paginated
                          page={resultsPage}
                          pageSize={12}
                          onPageChange={setResultsPage}
                          expandable
                          expandedRows={expandedResultRows}
                          onExpandedChange={setExpandedResultRows}
                          allowMultipleExpanded
                          emptyMessage={selectedRun.status === 'completed' ? 'No results to display' : 'No results yet for this run'}
                          renderExpandedRow={(row) => (
                            <div className="p-4 space-y-3 bg-gray-50 dark:bg-dark-surface-2 rounded-lg">
                              <div>
                                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">Expected Answer</p>
                                <p className="text-sm text-charcoal dark:text-gray-100 whitespace-pre-wrap">
                                  {row.expected_answer || '—'}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">Model Response</p>
                                <p className="text-sm text-charcoal dark:text-gray-100 whitespace-pre-wrap">
                                  {row.model_response || 'No response captured.'}
                                </p>
                              </div>
                              {row.verdict_reason && (
                                <div>
                                  <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">Verdict Reason</p>
                                  <p className="text-sm text-red-500 dark:text-red-400 whitespace-pre-wrap">
                                    {row.verdict_reason}
                                  </p>
                                </div>
                              )}
                            </div>
                          )}
                        />
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <BeakerIcon className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
                      <h3 className="mt-4 text-sm font-medium text-charcoal dark:text-gray-100">Select a run</h3>
                      <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Choose an evaluation run to view results</p>
                    </div>
                  </div>
                )}
              </div>
          </TabsContent>
        </Tabs>

        {canWriteEvals && (
          <Sheet open={showNewEvalSheet} onClose={() => setShowNewEvalSheet(false)}>
          <SheetContent side="right" size="xl">
            <SheetHeader>
              <div>
                <SheetTitle>New Evaluation</SheetTitle>
                <SheetDescription>Configure and start a new evaluation run</SheetDescription>
              </div>
            </SheetHeader>
            <SheetBody className="space-y-5">
              {selectedWorkspace ? (
                <Alert variant="info">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500 dark:text-gray-400">Evaluating workspace:</span>
                      <span className="text-sm font-medium text-charcoal dark:text-gray-100">{selectedWorkspace.display_name}</span>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {selectedWorkspace.document_count} documents • {selectedWorkspace.chunk_count} chunks
                    </div>
                  </div>
                </Alert>
              ) : (
                <Alert variant="warning">
                  Please select a workspace from the header to run evaluations.
                </Alert>
              )}

              <div>
                <Label className="mb-2 block">Question Source</Label>
                <RadioGroup
                  value={config.evalSource}
                  onValueChange={(v) => setConfig({ ...config, evalSource: v as EvalSourceType })}
                  disabled={isStarting}
                >
                  <RadioCard value="eval_set">
                    <div className="text-sm font-medium text-charcoal dark:text-gray-100">Eval Set (Static)</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Run exact questions from a curated set</div>
                  </RadioCard>
                  <RadioCard value="random_sampling">
                    <div className="text-sm font-medium text-charcoal dark:text-gray-100">Random Sampling</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Stratified sample from question pool</div>
                  </RadioCard>
                </RadioGroup>
              </div>

              {config.evalSource === 'eval_set' && (
                <div>
                  <Label className="mb-1 block">Select Eval Set</Label>
                  <Select
                    value={config.evalSetId?.toString() || ''}
                    onValueChange={(v) => setConfig({ ...config, evalSetId: v ? parseInt(v) : null })}
                    disabled={isStarting}
                  >
                    <SelectOption value="">Choose an eval set...</SelectOption>
                    {evalSets.filter((s) => s.is_built_in).length > 0 && (
                      <>
                        <SelectOption value="" disabled>— Built-in Static Sets —</SelectOption>
                        {evalSets.filter((s) => s.is_built_in).map((s) => (
                          <SelectOption key={s.id} value={s.id.toString()}>
                            {s.name} ({s.example_count} questions)
                          </SelectOption>
                        ))}
                      </>
                    )}
                    {evalSets.filter((s) => !s.is_built_in).length > 0 && (
                      <>
                        <SelectOption value="" disabled>— Uploaded Sets —</SelectOption>
                        {evalSets.filter((s) => !s.is_built_in).map((s) => (
                          <SelectOption key={s.id} value={s.id.toString()}>
                            {s.name} ({s.example_count} questions)
                          </SelectOption>
                        ))}
                      </>
                    )}
                  </Select>
                  {selectedEvalSetForRun && (
                    <div className="mt-2 p-2 bg-gray-50 dark:bg-dark-surface-2 rounded-lg text-xs text-gray-500 dark:text-gray-400">
                      <div className="font-medium text-charcoal dark:text-gray-100">{selectedEvalSetForRun.name}</div>
                      {selectedEvalSetForRun.description && (
                        <div className="mt-1">{selectedEvalSetForRun.description}</div>
                      )}
                      <div className="mt-1 flex items-center gap-2">
                        <Badge variant="default">{selectedEvalSetForRun.category}</Badge>
                        <span>{selectedEvalSetForRun.example_count} questions</span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {config.evalSource === 'random_sampling' && (
                <div>
                  <Label className="mb-2 block">Questions by Difficulty</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-xs mb-1 block">Easy</Label>
                      <Input
                        type="number"
                        value={config.easyCount}
                        onChange={(e) => setConfig({ ...config, easyCount: parseInt(e.target.value) || 0 })}
                        min={0}
                        max={50}
                        disabled={isStarting}
                      />
                    </div>
                    <div>
                      <Label className="text-xs mb-1 block">Medium</Label>
                      <Input
                        type="number"
                        value={config.mediumCount}
                        onChange={(e) => setConfig({ ...config, mediumCount: parseInt(e.target.value) || 0 })}
                        min={0}
                        max={50}
                        disabled={isStarting}
                      />
                    </div>
                    <div>
                      <Label className="text-xs mb-1 block">Hard</Label>
                      <Input
                        type="number"
                        value={config.hardCount}
                        onChange={(e) => setConfig({ ...config, hardCount: parseInt(e.target.value) || 0 })}
                        min={0}
                        max={50}
                        disabled={isStarting}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div className="pt-4 border-t border-gray-200 dark:border-dark-border">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs mb-1 block">Seed</Label>
                    <Input
                      type="number"
                      value={config.seed}
                      onChange={(e) => setConfig({ ...config, seed: parseInt(e.target.value) || 42 })}
                      disabled={isStarting}
                    />
                  </div>
                  <div>
                    <Label className="text-xs mb-1 block">Concurrency</Label>
                    <Input
                      type="number"
                      value={config.concurrency}
                      onChange={(e) => setConfig({ ...config, concurrency: parseInt(e.target.value) || 3 })}
                      min={1}
                      max={10}
                      disabled={isStarting}
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between mt-4">
                  <div>
                    <Label>Citation Validation</Label>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Validate citations against PDF pages</p>
                  </div>
                  <Switch
                    checked={config.validateCitations}
                    onCheckedChange={(checked) => setConfig({ ...config, validateCitations: checked })}
                    disabled={isStarting}
                  />
                </div>
              </div>

            </SheetBody>
            <SheetFooter className="flex items-center gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => setShowNewEvalSheet(false)}>
                Close
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={startEvaluation}
                disabled={
                  isStarting ||
                  !selectedWorkspace ||
                  (config.evalSource === 'random_sampling' && config.easyCount + config.mediumCount + config.hardCount === 0) ||
                  (config.evalSource === 'eval_set' && !config.evalSetId)
                }
              >
                <PlayIcon className="h-4 w-4" />
                Start Evaluation
              </Button>
            </SheetFooter>
          </SheetContent>
          </Sheet>
        )}

        <Modal open={pendingDeleteRunId !== null} onClose={() => setPendingDeleteRunId(null)}>
          <ModalContent size="sm">
            <ModalHeader>
              <ModalTitle>Delete Evaluation Run</ModalTitle>
            </ModalHeader>
            <ModalBody>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Delete this evaluation run? This will remove its results and telemetry.
              </p>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={() => setPendingDeleteRunId(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={async () => {
                  if (!pendingDeleteRunId) return;
                  const runId = pendingDeleteRunId;
                  setPendingDeleteRunId(null);
                  await deleteEvalRun(runId);
                }}
              >
                Delete Run
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        <Modal open={pendingDeleteEvalSet !== null} onClose={() => setPendingDeleteEvalSet(null)}>
          <ModalContent size="sm">
            <ModalHeader>
              <ModalTitle>Delete Eval Set</ModalTitle>
            </ModalHeader>
            <ModalBody>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Delete
                {' '}
                <span className="font-medium text-charcoal dark:text-gray-100">
                  {pendingDeleteEvalSet?.name || 'this eval set'}
                </span>
                ?
              </p>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" onClick={() => setPendingDeleteEvalSet(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={async () => {
                  if (!pendingDeleteEvalSet) return;
                  const evalSetId = pendingDeleteEvalSet.id;
                  setPendingDeleteEvalSet(null);
                  await deleteEvalSet(evalSetId);
                }}
              >
                Delete Eval Set
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Upload Modal */}
        <Modal
          open={showUploadModal}
          onClose={() => {
            setShowUploadModal(false);
            setUploadForm({ name: '', description: '', category: 'general', tags: '', file: null });
            setUploadError(null);
          }}
        >
          <ModalContent size="lg">
            <ModalHeader>
              <ModalTitle>Upload Eval Set</ModalTitle>
            </ModalHeader>
            <ModalBody>
              <div className="space-y-4">
                {uploadError && (
                  <Alert variant="error">
                    <div>
                      <p className="font-medium">Upload failed</p>
                      <p className="text-sm opacity-80 mt-1">{uploadError}</p>
                    </div>
                  </Alert>
                )}
                <div>
                  <Label className="mb-1 block">Name *</Label>
                  <Input
                    value={uploadForm.name}
                    onChange={(e) => {
                      setUploadError(null);
                      setUploadForm({ ...uploadForm, name: e.target.value });
                    }}
                    placeholder="My Custom Eval Set"
                    disabled={uploadLoading}
                  />
                </div>

                <div>
                  <Label className="mb-1 block">Description</Label>
                  <Textarea
                    value={uploadForm.description}
                    onChange={(e) => {
                      setUploadError(null);
                      setUploadForm({ ...uploadForm, description: e.target.value });
                    }}
                    rows={2}
                    placeholder="Optional description..."
                    disabled={uploadLoading}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="mb-1 block">Workspace</Label>
                    <div className="px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-gray-50 dark:bg-dark-surface-2">
                      <span className="text-charcoal dark:text-gray-100">
                        {selectedWorkspace?.display_name || 'No workspace selected'}
                      </span>
                    </div>
                  </div>
                  <div>
                    <Label className="mb-1 block">Category</Label>
                    <Select
                      value={uploadForm.category}
                      onValueChange={(value) => {
                        setUploadError(null);
                        setUploadForm({ ...uploadForm, category: value });
                      }}
                      disabled={uploadLoading}
                    >
                      <SelectOption value="general">General</SelectOption>
                      <SelectOption value="retrieval">Retrieval</SelectOption>
                      <SelectOption value="synthesis">Synthesis</SelectOption>
                      <SelectOption value="grounding">Grounding</SelectOption>
                      <SelectOption value="multi_hop">Multi-hop</SelectOption>
                      <SelectOption value="edge_cases">Edge Cases</SelectOption>
                      <SelectOption value="regression">Regression</SelectOption>
                      <SelectOption value="custom">Custom</SelectOption>
                    </Select>
                  </div>
                </div>

                <div>
                  <Label className="mb-1 block">Tags (comma-separated)</Label>
                  <Input
                    value={uploadForm.tags}
                    onChange={(e) => {
                      setUploadError(null);
                      setUploadForm({ ...uploadForm, tags: e.target.value });
                    }}
                    placeholder="citation-heavy, multi-doc"
                    disabled={uploadLoading}
                  />
                </div>

                <div>
                  <Label className="mb-1 block">JSONL File *</Label>
                  <div className="border-2 border-dashed border-gray-200 dark:border-dark-border rounded-lg p-4 text-center">
                    {uploadForm.file ? (
                      <div className="flex items-center justify-center gap-2">
                        <DocumentTextIcon className="h-5 w-5 text-eliza-red" />
                        <span className="text-gray-900 dark:text-gray-100">{uploadForm.file.name}</span>
                        <button
                          onClick={() => {
                            setUploadError(null);
                            setUploadForm({ ...uploadForm, file: null });
                          }}
                          disabled={uploadLoading}
                          className="text-red-400 hover:text-red-300"
                        >
                          <XCircleIcon className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <label className="cursor-pointer">
                        <input
                          type="file"
                          accept=".jsonl"
                          className="hidden"
                          disabled={uploadLoading}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              setUploadError(null);
                              setUploadForm({ ...uploadForm, file });
                            }
                          }}
                        />
                        <CloudArrowUpIcon className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                        <p className="text-sm text-gray-500 dark:text-gray-400">Click to select JSONL file</p>
                        <p className="text-xs text-gray-400 mt-1">Max 10MB, 1000 questions</p>
                      </label>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    Each line must be JSON with: question, reference_answer (required); eval_id, difficulty, gold_chunk_ids (optional)
                  </p>
                </div>
              </div>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadForm({ name: '', description: '', category: 'general', tags: '', file: null });
                  setUploadError(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant="brand"
                onClick={uploadEvalSet}
                disabled={uploadLoading || !uploadForm.name || !uploadForm.file}
              >
                {uploadLoading && <Spinner size="sm" />}
                Upload
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Preview Modal */}
        <Modal
          open={showPreviewModal && selectedEvalSet !== null}
          onClose={() => {
            setShowPreviewModal(false);
            setPreviewQuestions([]);
            setSelectedEvalSet(null);
          }}
        >
          <ModalContent size="xl">
            <ModalHeader>
              <ModalTitle>{selectedEvalSet?.name || 'Preview'}</ModalTitle>
            </ModalHeader>
            <ModalBody>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                {selectedEvalSet?.example_count} questions total (showing first 10)
              </p>
              
              <div className="max-h-96 overflow-y-auto space-y-4">
                {previewQuestions.map((q, i) => (
                  <Card key={i}>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-gray-500 dark:text-gray-400">#{i + 1}</span>
                        {q.difficulty && (
                          <Badge
                            variant={
                              q.difficulty === 'easy' ? 'success' :
                              q.difficulty === 'medium' ? 'warning' : 'danger'
                            }
                          >
                            {q.difficulty}
                          </Badge>
                        )}
                      </div>
                      <div className="text-sm text-gray-900 dark:text-gray-100 font-medium mb-2">{q.question}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        <span className="font-medium">Reference: </span>
                        {(q.reference_answer || q.expected_answer || '').slice(0, 200)}
                        {(q.reference_answer || q.expected_answer || '').length > 200 && '...'}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setShowPreviewModal(false);
                  setPreviewQuestions([]);
                  setSelectedEvalSet(null);
                }}
              >
                Close
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </PageBody>
      </Page>
    </Layout>
  );
}

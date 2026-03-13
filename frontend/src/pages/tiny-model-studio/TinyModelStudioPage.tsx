import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '../../components/layout/Layout';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Page,
  PageBody,
  PageHeader,
  Select,
  SelectOption,
  Spinner,
  Textarea,
} from '../../components/ui';
import {
  BeakerIcon,
  BoltIcon,
  CheckCircleIcon,
  CpuChipIcon,
  ExclamationTriangleIcon,
  RocketLaunchIcon,
  SparklesIcon,
  TableCellsIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

const API_BASE = '/v1/tiny-model-studio';

type TaskType = 'classification' | 'regression' | 'clustering';
type RunStatus = 'pending' | 'running' | 'awaiting_selection' | 'completed' | 'failed';
type WinnerPolicy = 'best' | 'lightest';
type SweepLevel = 'quick' | 'standard' | 'deep';
type Augmenter = 'template' | 'openai';
type ProjectStage =
  | 'problem_defined'
  | 'sample_uploaded'
  | 'micro_preview_ready'
  | 'preview_ready'
  | 'ready_to_train'
  | 'training'
  | 'trained'
  | 'failed';

type ErrorTolerance = 
  | 'false_positive'
  | 'false_negative'
  | 'over_predict'
  | 'under_predict'
  | 'over_segment'
  | 'under_segment'
  | 'balanced';

interface TinyModelProject {
  project_id: string;
  project_name: string;
  task_type: TaskType;
  problem_brief: string;
  stage: ProjectStage;
  sample_record_count: number;
  approved_record_count: number;
  latest_run_id?: string | null;
  created_at: string;
  updated_at: string;
}

interface TinyModelPreviewRow {
  text: string;
  metadata: Record<string, string>;
  label?: string | null;
  target?: number | null;
  source: string;
}

interface TinyModelPreviewResponse {
  project_id: string;
  stage: ProjectStage;
  seed_count: number;
  synthetic_proposed_count: number;
  synthetic_approved_count: number;
  final_record_count: number;
  coverage_summary: Record<string, unknown>;
  preview_rows: TinyModelPreviewRow[];
}

interface TinyModelCandidateResult {
  name: string;
  task_type: TaskType;
  family: string;
  is_baseline: boolean;
  sweep_stage: string;
  hyperparameters: Record<string, unknown>;
  metrics_mean: Record<string, number>;
  metrics_std: Record<string, number>;
  quality_score: number;
  overfit_risk: string;
  latency_ms: number;
  interpretability_score: number;
  artifact_size_bytes: number;
}

interface TinyModelDatasetVersion {
  version_id: string;
  record_count: number;
  synthetic_count: number;
  llm_labeled_count: number;
  notes: string;
}

interface TinyModelVersion {
  version_id: string;
  candidate_name: string;
  winner_policy: WinnerPolicy;
}

interface TinyModelEvent {
  timestamp: string;
  event_type: string;
  message: string;
}

interface TinyModelRun {
  run_id: string;
  project_id?: string | null;
  project_name: string;
  task_type: TaskType;
  sweep_level: SweepLevel;
  max_sweep_candidates?: number | null;
  status: RunStatus;
  created_at: string;
  coverage_summary: Record<string, unknown>;
  dataset_versions: TinyModelDatasetVersion[];
  candidates: TinyModelCandidateResult[];
  selected_candidate?: string | null;
  selected_policy?: WinnerPolicy | null;
  published_versions: TinyModelVersion[];
  events: TinyModelEvent[];
  error_message?: string | null;
}

interface TinyModelPredictResponse {
  run_id: string;
  version_id: string;
  candidate_name: string;
  predictions: Array<string | number>;
  probabilities?: Array<Record<string, number>> | null;
}

const initialProjectForm = {
  project_name: 'Support Routing Model',
  task_type: 'classification' as TaskType,
  problem_brief:
    'Route inbound support requests by intent and urgency so high-risk security incidents are escalated quickly.',
  error_tolerance: 'balanced' as ErrorTolerance,
};

const initialGenerationForm = {
  synthetic_examples: 120,
  augmenter: 'template' as Augmenter,
  llm_model: 'gpt-4o-mini',
  approval_rate: 1.0,
  max_preview_rows: 60,
  error_tolerance: 'balanced' as ErrorTolerance,
};

const initialTrainingForm = {
  k_folds: 5,
  sweep_level: 'standard' as SweepLevel,
  max_sweep_candidates: 24,
  quality_threshold: 0.9,
};

const statusVariant: Record<RunStatus, 'default' | 'success' | 'warning' | 'danger'> = {
  pending: 'warning',
  running: 'warning',
  awaiting_selection: 'default',
  completed: 'success',
  failed: 'danger',
};

const projectStageVariant: Record<ProjectStage, 'default' | 'success' | 'warning' | 'danger'> = {
  problem_defined: 'default',
  sample_uploaded: 'default',
  micro_preview_ready: 'default',
  preview_ready: 'warning',
  ready_to_train: 'success',
  training: 'warning',
  trained: 'success',
  failed: 'danger',
};

function metricLabel(taskType: TaskType): string {
  if (taskType === 'classification') return 'F1';
  if (taskType === 'regression') return 'Quality (-RMSE)';
  return 'Clustering Quality';
}

function metricValue(taskType: TaskType, candidate: TinyModelCandidateResult): number {
  if (taskType === 'classification') return candidate.metrics_mean.f1_macro ?? candidate.quality_score;
  return candidate.quality_score;
}

export default function TinyModelStudioPage() {
  const [projectForm, setProjectForm] = useState(initialProjectForm);
  const [generationForm, setGenerationForm] = useState(initialGenerationForm);
  const [trainingForm, setTrainingForm] = useState(initialTrainingForm);

  const [projects, setProjects] = useState<TinyModelProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [microPreview, setMicroPreview] = useState<TinyModelPreviewResponse | null>(null);
  const [microApprovedIndices, setMicroApprovedIndices] = useState<Set<number>>(new Set());
  const [preview, setPreview] = useState<TinyModelPreviewResponse | null>(null);

  const [runs, setRuns] = useState<TinyModelRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [currentRun, setCurrentRun] = useState<TinyModelRun | null>(null);

  const [winnerPolicy, setWinnerPolicy] = useState<WinnerPolicy>('best');
  const [winnerThreshold, setWinnerThreshold] = useState<number>(0.9);
  const [selectedCandidateForInference, setSelectedCandidateForInference] = useState<string | null>(null);
  const [predictionInput, setPredictionInput] = useState<string>(
    'email request from us customer with high priority security concern'
  );
  const [predictionResult, setPredictionResult] = useState<TinyModelPredictResponse | null>(null);

  const [isLoadingProjects, setIsLoadingProjects] = useState<boolean>(false);
  const [isCreatingProject, setIsCreatingProject] = useState<boolean>(false);
  const [isUploadingSample, setIsUploadingSample] = useState<boolean>(false);
  const [isSeedingSample, setIsSeedingSample] = useState<boolean>(false);
  const [isGeneratingMicroPreview, setIsGeneratingMicroPreview] = useState<boolean>(false);
  const [isSubmittingMicroReview, setIsSubmittingMicroReview] = useState<boolean>(false);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState<boolean>(false);
  const [isApprovingPreview, setIsApprovingPreview] = useState<boolean>(false);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [isLoadingRuns, setIsLoadingRuns] = useState<boolean>(false);
  const [isSelectingWinner, setIsSelectingWinner] = useState<boolean>(false);
  const [isPredicting, setIsPredicting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === selectedProjectId) ?? null,
    [projects, selectedProjectId]
  );

  const fetchProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    try {
      const response = await AXIOS_INSTANCE.get<TinyModelProject[]>(`${API_BASE}/projects`);
      const items = response.data ?? [];
      setProjects(items);
      if (!selectedProjectId && items.length > 0) {
        setSelectedProjectId(items[0].project_id);
      }
    } catch (err) {
      setError('Failed to load Tiny Model Studio projects.');
      console.error(err);
    } finally {
      setIsLoadingProjects(false);
    }
  }, [selectedProjectId]);

  const fetchRuns = useCallback(async () => {
    setIsLoadingRuns(true);
    try {
      const response = await AXIOS_INSTANCE.get<TinyModelRun[]>(`${API_BASE}/runs`);
      const items = response.data ?? [];
      setRuns(items);
      if (!selectedRunId && items.length > 0) {
        setSelectedRunId(items[0].run_id);
      }
    } catch (err) {
      setError('Failed to load Tiny Model Studio runs.');
      console.error(err);
    } finally {
      setIsLoadingRuns(false);
    }
  }, [selectedRunId]);

  const fetchRun = useCallback(async (runId: string) => {
    try {
      const response = await AXIOS_INSTANCE.get<TinyModelRun>(`${API_BASE}/runs/${runId}`);
      setCurrentRun(response.data);
    } catch (err) {
      setError('Failed to load run details.');
      console.error(err);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
    fetchRuns();
  }, [fetchProjects, fetchRuns]);

  useEffect(() => {
    if (selectedProject?.latest_run_id) {
      setSelectedRunId(selectedProject.latest_run_id);
    }
  }, [selectedProject?.latest_run_id]);

  const sortedCandidates = useMemo(() => {
    if (!currentRun) return [];
    return [...currentRun.candidates].sort((a, b) => b.quality_score - a.quality_score);
  }, [currentRun]);

  useEffect(() => {
    if (selectedRunId) {
      fetchRun(selectedRunId);
      setPredictionResult(null);
      setSelectedCandidateForInference(null);
    }
  }, [selectedRunId, fetchRun]);

  useEffect(() => {
    if (currentRun && currentRun.candidates.length > 0 && !selectedCandidateForInference) {
      setSelectedCandidateForInference(sortedCandidates[0]?.name || null);
    }
  }, [currentRun, selectedCandidateForInference, sortedCandidates]);

  useEffect(() => {
    if (!selectedRunId || !currentRun) return;
    if (!['pending', 'running'].includes(currentRun.status)) return;

    const timer = setInterval(() => {
      fetchRun(selectedRunId);
      fetchRuns();
      fetchProjects();
    }, 2000);

    return () => clearInterval(timer);
  }, [currentRun, selectedRunId, fetchRun, fetchRuns, fetchProjects]);

  const createProject = async () => {
    setError(null);
    setIsCreatingProject(true);
    try {
      const response = await AXIOS_INSTANCE.post<TinyModelProject>(`${API_BASE}/projects`, projectForm);
      setSelectedProjectId(response.data.project_id);
      setPreview(null);
      await fetchProjects();
    } catch (err) {
      setError('Failed to create project.');
      console.error(err);
    } finally {
      setIsCreatingProject(false);
    }
  };

  const uploadSampleData = async () => {
    if (!selectedProject || !selectedFile) {
      setError('Select a project and choose a sample data file first.');
      return;
    }

    setError(null);
    setIsUploadingSample(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      await AXIOS_INSTANCE.post(`${API_BASE}/projects/${selectedProject.project_id}/sample-data`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(null);
      setMicroPreview(null);
      setMicroApprovedIndices(new Set());
      await fetchProjects();
    } catch (err) {
      setError('Failed to upload sample data. Use .jsonl, .json, or .csv.');
      console.error(err);
    } finally {
      setIsUploadingSample(false);
    }
  };

  const seedSampleData = async () => {
    if (!selectedProject) {
      setError('Select a project first.');
      return;
    }

    setError(null);
    setIsSeedingSample(true);
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/projects/${selectedProject.project_id}/seed-sample-data`);
      setPreview(null);
      setMicroPreview(null);
      setMicroApprovedIndices(new Set());
      await fetchProjects();
    } catch (err) {
      setError('Failed to load sample data.');
      console.error(err);
    } finally {
      setIsSeedingSample(false);
    }
  };

  const generateMicroPreview = async () => {
    if (!selectedProject) {
      setError('Select a project first.');
      return;
    }

    setError(null);
    setIsGeneratingMicroPreview(true);
    try {
      const response = await AXIOS_INSTANCE.post<TinyModelPreviewResponse>(
        `${API_BASE}/projects/${selectedProject.project_id}/generate-micro-preview`
      );
      setMicroPreview(response.data);
      setMicroApprovedIndices(new Set(response.data.preview_rows.map((_, idx) => idx)));
      await fetchProjects();
    } catch (err) {
      setError('Failed to generate micro-preview.');
      console.error(err);
    } finally {
      setIsGeneratingMicroPreview(false);
    }
  };

  const submitMicroReview = async () => {
    if (!selectedProject || !microPreview) return;

    const allIndices = microPreview.preview_rows.map((_, idx) => idx);
    const rejectedIndices = allIndices.filter((idx) => !microApprovedIndices.has(idx));

    setError(null);
    setIsSubmittingMicroReview(true);
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/projects/${selectedProject.project_id}/review-micro-preview`, {
        approved_indices: Array.from(microApprovedIndices),
        rejected_indices: rejectedIndices,
      });
      await fetchProjects();
    } catch (err) {
      setError('Failed to submit micro-review.');
      console.error(err);
    } finally {
      setIsSubmittingMicroReview(false);
    }
  };

  const generatePreview = async () => {
    if (!selectedProject) {
      setError('Select a project first.');
      return;
    }

    setError(null);
    setIsGeneratingPreview(true);
    try {
      const response = await AXIOS_INSTANCE.post<TinyModelPreviewResponse>(
        `${API_BASE}/projects/${selectedProject.project_id}/generate-preview`,
        generationForm
      );
      setPreview(response.data);
      await fetchProjects();
    } catch (err) {
      setError('Failed to generate training data preview.');
      console.error(err);
    } finally {
      setIsGeneratingPreview(false);
    }
  };

  const approvePreview = async (approve: boolean) => {
    if (!selectedProject) return;

    setError(null);
    setIsApprovingPreview(true);
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/projects/${selectedProject.project_id}/approve-preview`, {
        approve,
      });
      await fetchProjects();
      if (!approve) {
        setPreview(null);
      }
    } catch (err) {
      setError('Failed to update preview approval state.');
      console.error(err);
    } finally {
      setIsApprovingPreview(false);
    }
  };

  const trainModel = async () => {
    if (!selectedProject) return;

    setError(null);
    setIsTraining(true);
    try {
      const response = await AXIOS_INSTANCE.post<{ run_id: string }>(
        `${API_BASE}/projects/${selectedProject.project_id}/train`,
        trainingForm
      );
      setSelectedRunId(response.data.run_id);
      await fetchRuns();
      await fetchProjects();
    } catch (err) {
      setError('Failed to start model training.');
      console.error(err);
    } finally {
      setIsTraining(false);
    }
  };

  const selectWinner = async () => {
    if (!currentRun) return;

    setError(null);
    setIsSelectingWinner(true);
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/select-winner`, {
        winner_policy: winnerPolicy,
        quality_threshold: winnerThreshold,
      });
      await fetchRun(currentRun.run_id);
      await fetchProjects();
    } catch (err) {
      setError('Failed to select winner.');
      console.error(err);
    } finally {
      setIsSelectingWinner(false);
    }
  };

  const toggleMicroRowApproval = (index: number) => {
    const newSet = new Set(microApprovedIndices);
    if (newSet.has(index)) {
      newSet.delete(index);
    } else {
      newSet.add(index);
    }
    setMicroApprovedIndices(newSet);
  };

  const runPrediction = async () => {
    if (!currentRun) return;
    const inputs = predictionInput
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean);
    if (inputs.length === 0) {
      setError('Enter at least one input line for prediction.');
      return;
    }

    setIsPredicting(true);
    setError(null);
    try {
      const response = await AXIOS_INSTANCE.post<TinyModelPredictResponse>(
        `${API_BASE}/runs/${currentRun.run_id}/predict`,
        { 
          inputs,
          candidate_name: selectedCandidateForInference || undefined,
        }
      );
      setPredictionResult(response.data);
    } catch (err) {
      setError('Prediction failed. Select a candidate to test.');
      console.error(err);
    } finally {
      setIsPredicting(false);
    }
  };

  const filteredRuns = useMemo(() => {
    if (!selectedProjectId) return runs;
    return runs.filter((run) => run.project_id === selectedProjectId);
  }, [runs, selectedProjectId]);

  const canUploadSample = !!selectedProject;
  const canGenerateMicroPreview = !!selectedProject && selectedProject.sample_record_count > 0;
  const canSubmitMicroReview = !!microPreview && microApprovedIndices.size > 0;
  const canGeneratePreview = !!selectedProject && selectedProject.sample_record_count > 0;
  const canApprovePreview = !!preview;
  const canTrain =
    !!selectedProject &&
    (selectedProject.stage === 'ready_to_train' || selectedProject.stage === 'trained' || selectedProject.stage === 'training');

  return (
    <Layout>
      <Page layout="centered" maxWidth="2xl">
        <PageHeader
          title="Tiny Model Studio"
          description="Problem brief first, then sample upload, data generation preview, and model training sweeps."
          actions={
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={fetchProjects} disabled={isLoadingProjects}>
                {isLoadingProjects ? <Spinner size="sm" /> : <TableCellsIcon className="h-4 w-4" />}
                Refresh Projects
              </Button>
              <Button variant="outline" onClick={fetchRuns} disabled={isLoadingRuns}>
                {isLoadingRuns ? <Spinner size="sm" /> : <BoltIcon className="h-4 w-4" />}
                Refresh Runs
              </Button>
            </div>
          }
        />
        <PageBody>
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <RocketLaunchIcon className="h-5 w-5 text-eliza-red" />
                  1. Define Problem Brief
                </CardTitle>
                <CardDescription>
                  Start with a short description of what the model should do and choose task type.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="md:col-span-2">
                    <Label className="mb-1 block">Project Name</Label>
                    <Input
                      value={projectForm.project_name}
                      onChange={(e) => setProjectForm({ ...projectForm, project_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block">Task Type</Label>
                    <Select
                      value={projectForm.task_type}
                      onValueChange={(value) => setProjectForm({ ...projectForm, task_type: value as TaskType })}
                    >
                      <SelectOption value="classification">Classification</SelectOption>
                      <SelectOption value="regression">Regression</SelectOption>
                      <SelectOption value="clustering">Clustering</SelectOption>
                    </Select>
                  </div>
                </div>

                <div>
                  <Label className="mb-1 block">Problem Brief</Label>
                  <Textarea
                    rows={4}
                    value={projectForm.problem_brief}
                    onChange={(e) => setProjectForm({ ...projectForm, problem_brief: e.target.value })}
                    placeholder="In 2-5 sentences, explain the model objective, inputs, and success criteria."
                  />
                </div>

                <div>
                  <Label className="mb-1 block">Error Tolerance Preference</Label>
                  <Select
                    value={projectForm.error_tolerance}
                    onValueChange={(value) => setProjectForm({ ...projectForm, error_tolerance: value as ErrorTolerance })}
                  >
                    {projectForm.task_type === 'classification' && (
                      <>
                        <SelectOption value="false_positive">Higher False Positives (catch more)</SelectOption>
                        <SelectOption value="false_negative">Higher False Negatives (fewer false alarms)</SelectOption>
                      </>
                    )}
                    {projectForm.task_type === 'regression' && (
                      <>
                        <SelectOption value="over_predict">Over-predict</SelectOption>
                        <SelectOption value="under_predict">Under-predict</SelectOption>
                      </>
                    )}
                    {projectForm.task_type === 'clustering' && (
                      <>
                        <SelectOption value="over_segment">More Clusters</SelectOption>
                        <SelectOption value="under_segment">Fewer Clusters</SelectOption>
                      </>
                    )}
                    <SelectOption value="balanced">Balanced</SelectOption>
                  </Select>
                </div>

                <div className="flex justify-end">
                  <Button
                    onClick={createProject}
                    disabled={
                      isCreatingProject ||
                      projectForm.project_name.trim().length < 3 ||
                      projectForm.problem_brief.trim().length < 12
                    }
                  >
                    {isCreatingProject ? <Spinner size="sm" /> : <CheckCircleIcon className="h-4 w-4" />}
                    Save Project Brief
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Project Workspace</span>
                  {selectedProject && (
                    <Badge variant={projectStageVariant[selectedProject.stage]}>{selectedProject.stage}</Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Choose the project you want to continue. Steps below apply to the selected project.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="mb-1 block">Project</Label>
                  <Select
                    value={selectedProjectId ?? undefined}
                    onValueChange={(value) => {
                      setSelectedProjectId(value);
                      setPreview(null);
                      setMicroPreview(null);
                      setMicroApprovedIndices(new Set());
                    }}
                  >
                    {projects.length === 0 ? (
                      <SelectOption value="">No projects yet</SelectOption>
                    ) : (
                      projects.map((project) => (
                        <SelectOption key={project.project_id} value={project.project_id}>
                          {project.project_name} ({project.stage})
                        </SelectOption>
                      ))
                    )}
                  </Select>
                </div>

                {selectedProject && (
                  <div className="rounded-lg border border-gray-200 p-3 text-sm dark:border-dark-border">
                    <div className="font-medium text-charcoal dark:text-gray-100">{selectedProject.project_name}</div>
                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{selectedProject.problem_brief}</div>
                    <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      task: {selectedProject.task_type} • sample rows: {selectedProject.sample_record_count} • approved rows:{' '}
                      {selectedProject.approved_record_count}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TableCellsIcon className="h-5 w-5 text-eliza-red" />
                  2. Upload Sample Data
                </CardTitle>
                <CardDescription>
                  Upload a small representative dataset (.jsonl, .json, or .csv). You do not need full training data.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Input
                  type="file"
                  accept=".jsonl,.json,.csv"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                  disabled={!canUploadSample}
                />
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    onClick={seedSampleData}
                    disabled={!canUploadSample || isSeedingSample}
                  >
                    {isSeedingSample ? <Spinner size="sm" /> : <SparklesIcon className="h-4 w-4" />}
                    Load Sample Data
                  </Button>
                  <Button onClick={uploadSampleData} disabled={!canUploadSample || !selectedFile || isUploadingSample}>
                    {isUploadingSample ? <Spinner size="sm" /> : <TableCellsIcon className="h-4 w-4" />}
                    Upload Sample
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <SparklesIcon className="h-5 w-5 text-eliza-red" />
                  3a. Generate Micro-Preview
                </CardTitle>
                <CardDescription>
                  Generate a small sample batch (~10 rows) and review them individually before mass generation.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-end">
                  <Button onClick={generateMicroPreview} disabled={!canGenerateMicroPreview || isGeneratingMicroPreview}>
                    {isGeneratingMicroPreview ? <Spinner size="sm" /> : <SparklesIcon className="h-4 w-4" />}
                    Generate Sample Batch
                  </Button>
                </div>

                {microPreview && (
                  <div className="space-y-3 rounded-lg border border-gray-200 p-3 dark:border-dark-border">
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Review each sample. Check to approve, uncheck to reject.
                    </div>
                    
                    <div className="max-h-80 overflow-y-auto space-y-2">
                      {microPreview.preview_rows.map((row, index) => (
                        <div
                          key={`micro-${index}`}
                          className={`rounded-lg border p-3 ${
                            microApprovedIndices.has(index)
                              ? 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-950/20'
                              : 'border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-950/20'
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={microApprovedIndices.has(index)}
                              onChange={() => toggleMicroRowApproval(index)}
                              className="mt-1 h-4 w-4"
                            />
                            <div className="flex-1 text-sm">
                              <div className="text-charcoal dark:text-gray-100">{row.text}</div>
                              <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                {row.label && <span>label: {row.label}</span>}
                                {row.target !== null && row.target !== undefined && <span>target: {row.target.toFixed(2)}</span>}
                                {' • source: '}{row.source}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex gap-2 justify-end">
                      <Button
                        variant="outline"
                        onClick={() => setMicroApprovedIndices(new Set())}
                        disabled={isSubmittingMicroReview}
                      >
                        Reject All
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setMicroApprovedIndices(new Set(microPreview.preview_rows.map((_, idx) => idx)))}
                        disabled={isSubmittingMicroReview}
                      >
                        Approve All
                      </Button>
                      <Button onClick={submitMicroReview} disabled={!canSubmitMicroReview || isSubmittingMicroReview}>
                        {isSubmittingMicroReview ? <Spinner size="sm" /> : <CheckCircleIcon className="h-4 w-4" />}
                        Submit Review ({microApprovedIndices.size} approved)
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <SparklesIcon className="h-5 w-5 text-eliza-red" />
                  3b. Mass Generate Training Data
                </CardTitle>
                <CardDescription>
                  Generate full augmented dataset based on your reviewed samples.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
                  <div>
                    <Label className="mb-1 block">Synthetic Examples</Label>
                    <Input
                      type="number"
                      value={generationForm.synthetic_examples}
                      onChange={(e) =>
                        setGenerationForm({
                          ...generationForm,
                          synthetic_examples: parseInt(e.target.value, 10) || 10,
                        })
                      }
                      disabled={!canGeneratePreview}
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block">Augmenter</Label>
                    <Select
                      value={generationForm.augmenter}
                      onValueChange={(value) =>
                        setGenerationForm({ ...generationForm, augmenter: value as Augmenter })
                      }
                    >
                      <SelectOption value="template">Template Synthetic</SelectOption>
                      <SelectOption value="openai">OpenAI + Template</SelectOption>
                    </Select>
                  </div>
                  <div className="lg:col-span-2">
                    <Label className="mb-1 block">LLM Model</Label>
                    <Input
                      value={generationForm.llm_model}
                      onChange={(e) => setGenerationForm({ ...generationForm, llm_model: e.target.value })}
                      disabled={!canGeneratePreview}
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block">Approval Rate</Label>
                    <Input
                      type="number"
                      min={0.1}
                      max={1.0}
                      step={0.05}
                      value={generationForm.approval_rate}
                      onChange={(e) =>
                        setGenerationForm({
                          ...generationForm,
                          approval_rate: parseFloat(e.target.value) || 1.0,
                        })
                      }
                      disabled={!canGeneratePreview}
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={generatePreview} disabled={!canGeneratePreview || isGeneratingPreview}>
                    {isGeneratingPreview ? <Spinner size="sm" /> : <SparklesIcon className="h-4 w-4" />}
                    Generate Preview
                  </Button>
                </div>

                {preview && (
                  <div className="space-y-3 rounded-lg border border-gray-200 p-3 dark:border-dark-border">
                    <div className="grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400 md:grid-cols-4">
                      <span>seed: {preview.seed_count}</span>
                      <span>proposed synthetic: {preview.synthetic_proposed_count}</span>
                      <span>approved synthetic: {preview.synthetic_approved_count}</span>
                      <span>final rows: {preview.final_record_count}</span>
                    </div>

                    <div className="max-h-64 overflow-y-auto rounded-md border border-gray-200 dark:border-dark-border">
                      <table className="w-full table-auto text-xs">
                        <thead className="bg-gray-50 dark:bg-dark-surface-2">
                          <tr>
                            <th className="px-2 py-1 text-left">Text</th>
                            <th className="px-2 py-1 text-left">Label/Target</th>
                            <th className="px-2 py-1 text-left">Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {preview.preview_rows.map((row, index) => (
                            <tr key={`${row.source}-${index}`} className="border-t border-gray-100 dark:border-dark-border/40">
                              <td className="px-2 py-1 text-gray-600 dark:text-gray-300">{row.text}</td>
                              <td className="px-2 py-1 text-gray-500 dark:text-gray-400">
                                {row.label ?? (row.target !== null && row.target !== undefined ? row.target.toFixed(2) : '-')}
                              </td>
                              <td className="px-2 py-1 text-gray-500 dark:text-gray-400">{row.source}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="flex gap-2 justify-end">
                      <Button variant="outline" onClick={() => approvePreview(false)} disabled={isApprovingPreview || !canApprovePreview}>
                        Not Good - Regenerate
                      </Button>
                      <Button onClick={() => approvePreview(true)} disabled={isApprovingPreview || !canApprovePreview}>
                        {isApprovingPreview ? <Spinner size="sm" /> : <CheckCircleIcon className="h-4 w-4" />}
                        Looks Good - Approve
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CpuChipIcon className="h-5 w-5 text-eliza-red" />
                  4. Train Candidate Models
                </CardTitle>
                <CardDescription>
                  Run baseline + sweeps on the approved dataset and compare leaderboard results.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div>
                    <Label className="mb-1 block">K-Folds</Label>
                    <Input
                      type="number"
                      value={trainingForm.k_folds}
                      onChange={(e) =>
                        setTrainingForm({
                          ...trainingForm,
                          k_folds: parseInt(e.target.value, 10) || 2,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block">Sweep</Label>
                    <Select
                      value={trainingForm.sweep_level}
                      onValueChange={(value) =>
                        setTrainingForm({ ...trainingForm, sweep_level: value as SweepLevel })
                      }
                    >
                      <SelectOption value="quick">Quick</SelectOption>
                      <SelectOption value="standard">Standard</SelectOption>
                      <SelectOption value="deep">Deep</SelectOption>
                    </Select>
                  </div>
                  <div>
                    <Label className="mb-1 block">Max Candidates</Label>
                    <Input
                      type="number"
                      value={trainingForm.max_sweep_candidates}
                      onChange={(e) =>
                        setTrainingForm({
                          ...trainingForm,
                          max_sweep_candidates: parseInt(e.target.value, 10) || 3,
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block">Quality Threshold</Label>
                    <Input
                      type="number"
                      min={0.5}
                      max={1.0}
                      step={0.01}
                      value={trainingForm.quality_threshold}
                      onChange={(e) =>
                        setTrainingForm({
                          ...trainingForm,
                          quality_threshold: parseFloat(e.target.value) || 0.9,
                        })
                      }
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button onClick={trainModel} disabled={!canTrain || isTraining}>
                    {isTraining ? <Spinner size="sm" /> : <CpuChipIcon className="h-4 w-4" />}
                    Train Models
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BeakerIcon className="h-5 w-5 text-eliza-red" />
                  Runs
                </CardTitle>
              </CardHeader>
              <CardContent>
                {filteredRuns.length === 0 ? (
                  <div className="text-sm text-gray-500 dark:text-gray-400">No runs yet for this project.</div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {filteredRuns.map((run) => (
                      <Button
                        key={run.run_id}
                        variant={run.run_id === selectedRunId ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setSelectedRunId(run.run_id)}
                      >
                        {run.project_name}
                      </Button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {currentRun && (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span>{currentRun.project_name}</span>
                      <Badge variant={statusVariant[currentRun.status]}>{currentRun.status}</Badge>
                    </CardTitle>
                    <CardDescription>
                      {currentRun.task_type} • sweep {currentRun.sweep_level}
                      {currentRun.max_sweep_candidates ? ` • max ${currentRun.max_sweep_candidates}` : ''}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {currentRun.status === 'running' && (
                      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                        <Spinner size="sm" /> Sweep and cross-validation in progress.
                      </div>
                    )}

                    {currentRun.error_message && (
                      <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                        {currentRun.error_message}
                      </div>
                    )}

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      {currentRun.dataset_versions.map((version) => (
                        <div key={version.version_id} className="rounded-lg border border-gray-200 p-3 dark:border-dark-border">
                          <div className="text-sm font-medium text-charcoal dark:text-gray-100">{version.version_id}</div>
                          <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            records: {version.record_count} • synthetic: {version.synthetic_count} • llm:{' '}
                            {version.llm_labeled_count}
                          </div>
                          <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{version.notes}</div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Candidate Leaderboard</CardTitle>
                    <CardDescription>
                      Ranked by quality. Baseline and sweep-stage metadata included.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {sortedCandidates.length === 0 ? (
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        Candidates will appear when training finishes.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {sortedCandidates.map((candidate, index) => (
                          <div key={candidate.name} className="rounded-lg border border-gray-200 p-3 dark:border-dark-border">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-semibold text-charcoal dark:text-gray-100">
                                #{index + 1} {candidate.name}
                              </span>
                              <Badge variant={candidate.is_baseline ? 'default' : 'outline'}>
                                {candidate.is_baseline ? 'baseline' : candidate.sweep_stage}
                              </Badge>
                              <Badge variant="outline">{candidate.family}</Badge>
                              <Badge variant="outline">{candidate.overfit_risk} overfit-risk</Badge>
                            </div>
                            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400 md:grid-cols-5">
                              <span>
                                {metricLabel(currentRun.task_type)}: {metricValue(currentRun.task_type, candidate).toFixed(4)}
                              </span>
                              <span>latency: {candidate.latency_ms.toFixed(3)}ms</span>
                              <span>interpretability: {candidate.interpretability_score.toFixed(2)}</span>
                              <span>artifact: {(candidate.artifact_size_bytes / 1024).toFixed(1)}KB</span>
                              <span>quality: {candidate.quality_score.toFixed(4)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {currentRun.candidates.length > 0 && (
                  <>
                    <Card>
                      <CardHeader>
                        <CardTitle>Test Inference</CardTitle>
                        <CardDescription>
                          Test any candidate model before deploying. Enter one input per line.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div>
                          <Label className="mb-1 block">Select Candidate to Test</Label>
                          <Select
                            value={selectedCandidateForInference ?? undefined}
                            onValueChange={(value) => setSelectedCandidateForInference(value)}
                          >
                            {sortedCandidates.map((candidate, index) => (
                              <SelectOption key={candidate.name} value={candidate.name}>
                                #{index + 1} {candidate.name} (Q: {candidate.quality_score.toFixed(4)}, {candidate.latency_ms.toFixed(1)}ms)
                              </SelectOption>
                            ))}
                          </Select>
                        </div>

                        <Textarea rows={5} value={predictionInput} onChange={(e) => setPredictionInput(e.target.value)} />
                        
                        <Button onClick={runPrediction} disabled={isPredicting || !selectedCandidateForInference}>
                          {isPredicting ? <Spinner size="sm" /> : <CpuChipIcon className="h-4 w-4" />}
                          Test Prediction
                        </Button>

                        {predictionResult && (
                          <div className="rounded-lg border border-gray-200 p-3 text-sm dark:border-dark-border">
                            <div className="font-medium text-charcoal dark:text-gray-100">
                              {predictionResult.candidate_name} • {predictionResult.version_id}
                            </div>
                            <div className="mt-2 space-y-1 text-xs text-gray-500 dark:text-gray-400">
                              {predictionResult.predictions.map((item, index) => (
                                <div key={`${item}-${index}`}>#{index + 1}: {String(item)}</div>
                              ))}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader>
                        <CardTitle>Deploy Model</CardTitle>
                        <CardDescription>
                          After testing, deploy the winner with an explicit policy: best vs lightest (fast + interpretable).
                        </CardDescription>
                      </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                        <div>
                          <Label className="mb-1 block">Winner Policy</Label>
                          <Select
                            value={winnerPolicy}
                            onValueChange={(value) => setWinnerPolicy(value as WinnerPolicy)}
                          >
                            <SelectOption value="best">Best</SelectOption>
                            <SelectOption value="lightest">Lightest</SelectOption>
                          </Select>
                        </div>
                        <div>
                          <Label className="mb-1 block">Quality Threshold</Label>
                          <Input
                            type="number"
                            min={0.5}
                            max={1.0}
                            step={0.01}
                            value={winnerThreshold}
                            onChange={(e) => setWinnerThreshold(parseFloat(e.target.value) || 0.9)}
                          />
                        </div>
                        <div className="flex items-end">
                          <Button onClick={selectWinner} disabled={isSelectingWinner || currentRun.status === 'running'}>
                            {isSelectingWinner ? <Spinner size="sm" /> : <RocketLaunchIcon className="h-4 w-4" />}
                            Deploy Model
                          </Button>
                        </div>
                      </div>

                      {currentRun.selected_candidate && (
                        <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-900/60 dark:bg-green-950/30 dark:text-green-300">
                          Deployed: {currentRun.selected_candidate} ({currentRun.selected_policy})
                        </div>
                      )}
                    </CardContent>
                  </Card>
                  </>
                )}

                <Card>
                  <CardHeader>
                    <CardTitle>Event Feed</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-64 space-y-1 overflow-y-auto text-xs">
                      {currentRun.events.length === 0 ? (
                        <div className="text-gray-500 dark:text-gray-400">No events yet.</div>
                      ) : (
                        currentRun.events
                          .slice()
                          .reverse()
                          .map((event) => (
                            <div key={`${event.timestamp}-${event.event_type}`} className="text-gray-500 dark:text-gray-400">
                              [{new Date(event.timestamp).toLocaleTimeString()}] {event.message}
                            </div>
                          ))
                      )}
                    </div>
                  </CardContent>
                </Card>
              </>
            )}

            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                <ExclamationTriangleIcon className="h-4 w-4" />
                {error}
              </div>
            )}
          </div>
        </PageBody>
      </Page>
    </Layout>
  );
}

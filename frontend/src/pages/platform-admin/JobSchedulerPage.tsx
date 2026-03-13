/**
 * Job Scheduler Page
 * 
 * Platform admin page for viewing and managing Celery scheduled jobs.
 * Features:
 * - View all scheduled jobs with status
 * - Enable/disable jobs
 * - Manually trigger jobs
 * - Edit job configuration (name, schedule)
 * - View execution history
 * 
 * Migrated to DS components (Jan 2026).
 * 
 * DS Components used:
 * - Page, PageHeader, PageBody (layout)
 * - Button, Input, Textarea, Select, SelectOption, Label (form)
 * - Badge, Spinner, Alert (feedback)
 * - Modal, ModalBackdrop, ModalContent, ModalHeader, ModalTitle, ModalDescription, ModalBody, ModalFooter (dialogs)
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ClockIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  PencilIcon,
  SignalIcon,
  SignalSlashIcon,
} from '@heroicons/react/24/outline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';
import { format, formatDistanceToNow } from 'date-fns';
import { useJobSchedulerStream } from '../../hooks/useJobSchedulerStream';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Badge,
  Spinner,
  Alert,
} from '../../components/ui';

interface ScheduledJob {
  id: number;
  job_name: string;
  display_name: string;
  description: string | null;
  task_name: string;
  schedule_type: string;
  schedule_value: string;
  schedule_display: string | null;
  is_enabled: boolean;
  last_run_at: string | null;
  last_run_status: string;
  last_run_duration_seconds: number | null;
  last_error: string | null;
  last_task_id: string | null;
  next_run_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface JobExecution {
  id: number;
  job_name: string;
  task_id: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  status: string;
  error_message: string | null;
  triggered_by: string;
  result_summary: string | null;
}

const statusConfig: Record<string, { icon: React.ElementType; variant: 'default' | 'secondary' | 'brand' | 'success' | 'warning' | 'danger' | 'info'; label: string }> = {
  idle: { icon: ClockIcon, variant: 'secondary', label: 'Never Run' },
  running: { icon: ArrowPathIcon, variant: 'info', label: 'Running' },
  success: { icon: CheckCircleIcon, variant: 'success', label: 'Success' },
  failed: { icon: XCircleIcon, variant: 'danger', label: 'Failed' },
  cancelled: { icon: ExclamationTriangleIcon, variant: 'warning', label: 'Cancelled' },
};

// Preset schedule options
const INTERVAL_PRESETS = [
  { label: 'Every hour', value: '3600', type: 'interval' },
  { label: 'Every 2 hours', value: '7200', type: 'interval' },
  { label: 'Every 4 hours', value: '14400', type: 'interval' },
  { label: 'Every 6 hours', value: '21600', type: 'interval' },
  { label: 'Every 12 hours', value: '43200', type: 'interval' },
];

// Days of the week for scheduling
const DAYS_OF_WEEK = [
  { key: 'sun', label: 'S', fullLabel: 'Sunday', cronValue: 0 },
  { key: 'mon', label: 'M', fullLabel: 'Monday', cronValue: 1 },
  { key: 'tue', label: 'T', fullLabel: 'Tuesday', cronValue: 2 },
  { key: 'wed', label: 'W', fullLabel: 'Wednesday', cronValue: 3 },
  { key: 'thu', label: 'T', fullLabel: 'Thursday', cronValue: 4 },
  { key: 'fri', label: 'F', fullLabel: 'Friday', cronValue: 5 },
  { key: 'sat', label: 'S', fullLabel: 'Saturday', cronValue: 6 },
];

// Parse cron expression to get Eastern time and selected days
function cronToTimeAndDays(cron: string): { time: string; selectedDays: string[] } {
  const parts = cron.split(' ');
  if (parts.length !== 5) return { time: '06:00', selectedDays: [] };
  
  const [minute, hour, , , dayOfWeek] = parts;
  // Convert UTC to Eastern (subtract 5 hours)
  let easternHour = (parseInt(hour) - 5 + 24) % 24;
  const time = `${easternHour.toString().padStart(2, '0')}:${minute.padStart(2, '0')}`;
  
  // Parse days
  let selectedDays: string[] = [];
  if (dayOfWeek === '*') {
    // All days
    selectedDays = DAYS_OF_WEEK.map(d => d.key);
  } else if (dayOfWeek === '1-5') {
    // Weekdays
    selectedDays = ['mon', 'tue', 'wed', 'thu', 'fri'];
  } else if (dayOfWeek === '0-6' || dayOfWeek === '0,1,2,3,4,5,6') {
    // All days
    selectedDays = DAYS_OF_WEEK.map(d => d.key);
  } else {
    // Parse individual days
    const dayNumbers = dayOfWeek.split(',').map(d => parseInt(d.trim()));
    selectedDays = dayNumbers
      .map(num => DAYS_OF_WEEK.find(d => d.cronValue === num)?.key)
      .filter(Boolean) as string[];
  }
  
  return { time, selectedDays };
}

function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || statusConfig.idle;
  const Icon = config.icon;
  const isRunning = status === 'running';
  
  return (
    <Badge variant={config.variant} className="inline-flex items-center gap-1.5">
      <Icon className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
      {config.label}
    </Badge>
  );
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return '-';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function getScheduleLabel(type: string, value: string): string {
  // Check interval presets
  const intervalPreset = INTERVAL_PRESETS.find(p => p.value === value && p.type === type);
  if (intervalPreset) return intervalPreset.label;
  
  if (type === 'interval') {
    const seconds = parseInt(value, 10);
    if (isNaN(seconds)) return value;
    if (seconds >= 86400) return `Every ${Math.floor(seconds / 86400)} day(s)`;
    if (seconds >= 3600) return `Every ${Math.floor(seconds / 3600)} hour(s)`;
    if (seconds >= 60) return `Every ${Math.floor(seconds / 60)} minute(s)`;
    return `Every ${seconds} seconds`;
  }
  
  if (type === 'cron') {
    const { time, selectedDays } = cronToTimeAndDays(value);
    const timeLabel = formatTimeDisplay(time);
    
    // Format days nicely
    if (selectedDays.length === 7 || selectedDays.length === 0) {
      return `Daily at ${timeLabel} ET`;
    } else if (
      selectedDays.length === 5 && 
      ['mon', 'tue', 'wed', 'thu', 'fri'].every(d => selectedDays.includes(d))
    ) {
      return `Weekdays at ${timeLabel} ET`;
    } else if (selectedDays.length === 2 && selectedDays.includes('sat') && selectedDays.includes('sun')) {
      return `Weekends at ${timeLabel} ET`;
    } else {
      const dayLabels = selectedDays
        .map(key => DAYS_OF_WEEK.find(d => d.key === key)?.fullLabel?.slice(0, 3))
        .filter(Boolean)
        .join(', ');
      return `${dayLabels} at ${timeLabel} ET`;
    }
  }
  
  return value;
}

function getJobDescription(job: ScheduledJob): string | null {
  if (job.job_name === 'adoption-daily-sync') {
    return 'Syncs ChatGPT Enterprise adoption metrics from OpenAI Compliance API. Runs on the schedule configured in Adoption Settings.';
  }

  return job.description;
}

function formatTimeDisplay(time: string): string {
  const [hours, minutes] = time.split(':').map(Number);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  return `${displayHours}:${minutes.toString().padStart(2, '0')} ${period}`;
}

export function JobSchedulerPage() {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  // Use SSE for real-time job status updates
  const { 
    jobs: streamedJobs, 
    isConnected, 
    error: streamError, 
    lastUpdate,
    reconnect 
  } = useJobSchedulerStream(true);

  // Fallback: Fetch jobs via REST (used for initial load if SSE fails)
  const { data: jobsData, isLoading } = useQuery({
    queryKey: ['platform-jobs'],
    queryFn: async () => {
      const response = await AXIOS_INSTANCE.get<{ jobs: ScheduledJob[]; total: number }>(
        '/api/v1/platform-admin/jobs'
      );
      return response.data;
    },
    // Only refetch on interval if SSE is not connected
    refetchInterval: isConnected ? false : 10000,
    // Don't refetch on window focus if SSE is working
    refetchOnWindowFocus: !isConnected,
  });

  // Use SSE jobs if available, otherwise fall back to REST jobs
  const jobs = streamedJobs.length > 0 ? streamedJobs : (jobsData?.jobs || []);

  // Fetch executions for expanded job
  const { data: executionsData, isLoading: executionsLoading, refetch: refetchExecutions } = useQuery({
    queryKey: ['platform-job-executions', expandedJobId],
    queryFn: async () => {
      if (!expandedJobId) return null;
      const job = jobs.find(j => j.id === expandedJobId);
      if (!job) return null;
      const response = await AXIOS_INSTANCE.get<{ executions: JobExecution[]; total: number }>(
        `/api/v1/platform-admin/jobs/${job.job_name}/executions?limit=10`
      );
      return response.data;
    },
    enabled: !!expandedJobId,
  });

  // Refetch executions when we receive SSE updates (for the expanded job)
  useEffect(() => {
    if (lastUpdate && expandedJobId) {
      refetchExecutions();
    }
  }, [lastUpdate, expandedJobId, refetchExecutions]);

  // Trigger job
  const triggerJob = useMutation({
    mutationFn: async (jobName: string) => {
      const response = await AXIOS_INSTANCE.post(`/api/v1/platform-admin/jobs/${jobName}/trigger`);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['platform-jobs'] });
      if (data.success) {
        addToast({ kind: 'success', message: data.message });
      } else {
        addToast({ kind: 'warning', message: data.message });
      }
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to trigger job' });
    },
  });

  if (isLoading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Job Scheduler"
          description="Manage background tasks and scheduled jobs"
        />
        <PageBody>
          <div className="flex items-center justify-center h-64">
            <Spinner size="lg" />
          </div>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="xl">
      <PageHeader
        title="Job Scheduler"
        description="Monitor and trigger jobs. Configure schedules in Adoption Settings."
      />
      <PageBody>
        <div className="space-y-6">
        {/* Jobs List */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ClockIcon className="w-5 h-5 text-eliza-red" />
                <div>
                  <h2 className="text-base font-medium text-charcoal dark:text-gray-100">Scheduled Jobs</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{jobs.length} job{jobs.length !== 1 ? 's' : ''} configured</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {/* SSE Connection Status */}
                {isConnected ? (
                  <Badge variant="success" className="inline-flex items-center gap-1.5">
                    <SignalIcon className="w-3.5 h-3.5" />
                    Live updates
                  </Badge>
                ) : (
                  <div className="flex items-center gap-2">
                    <Badge variant="warning" className="inline-flex items-center gap-1.5">
                      <SignalSlashIcon className="w-3.5 h-3.5" />
                      {streamError || 'Connecting...'}
                    </Badge>
                    <Button variant="outline" size="sm" onClick={reconnect}>
                      Retry
                    </Button>
                  </div>
                )}
                {!isConnected && (
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                    <ArrowPathIcon className="w-3.5 h-3.5" />
                    <span>Polling every 10s</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {jobs.length === 0 ? (
            <div className="px-4 py-12 text-center text-gray-500 dark:text-gray-400 text-sm">
              No scheduled jobs configured.
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-dark-border">
              {jobs.map((job) => {
                const isExpanded = expandedJobId === job.id;
                const isRunning = job.last_run_status === 'running';
                
                return (
                  <div key={job.id} className="transition-colors">
                    {/* Job Row */}
                    <div
                      className="px-4 py-4 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer"
                      onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-gray-400 dark:text-gray-500">
                            {isExpanded ? (
                              <ChevronDownIcon className="w-4 h-4" />
                            ) : (
                              <ChevronRightIcon className="w-4 h-4" />
                            )}
                          </div>
                          
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-charcoal dark:text-gray-100">{job.display_name}</span>
                              {!job.is_enabled && (
                                <Badge variant="secondary">Disabled</Badge>
                              )}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                              {job.schedule_display || getScheduleLabel(job.schedule_type, job.schedule_value)}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <StatusBadge status={job.last_run_status} />
                          
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            {/* Edit Button */}
                            <Link to="/admin/adoption-settings">
                              <Button
                                variant="ghost"
                                size="sm"
                                title="Configure in Adoption Settings"
                              >
                                <PencilIcon className="w-4 h-4" />
                              </Button>
                            </Link>
                            
                            {/* Run Now Button */}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => triggerJob.mutate(job.job_name)}
                              disabled={isRunning || triggerJob.isPending}
                              title={isRunning ? 'Job is currently running' : 'Run now'}
                              className={isRunning ? 'cursor-not-allowed' : 'hover:text-green-500'}
                            >
                              <ArrowPathIcon className={`w-4 h-4 ${isRunning ? 'animate-spin' : ''}`} />
                            </Button>
                            
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="px-4 pb-4">
                        <div className="ml-7 space-y-4">
                          {/* Description */}
                          {getJobDescription(job) && (
                            <p className="text-sm text-gray-500 dark:text-gray-400">{getJobDescription(job)}</p>
                          )}

                          {/* Stats Grid */}
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3">
                              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Task Name</div>
                              <div className="text-sm text-charcoal dark:text-gray-100 font-mono truncate" title={job.task_name}>{job.task_name}</div>
                            </div>
                            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3">
                              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Last Run</div>
                              <div className="text-sm text-charcoal dark:text-gray-100">
                                {job.last_run_at 
                                  ? formatDistanceToNow(new Date(job.last_run_at), { addSuffix: true })
                                  : 'Never'
                                }
                              </div>
                            </div>
                            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3">
                              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Duration</div>
                              <div className="text-sm text-charcoal dark:text-gray-100">
                                {formatDuration(job.last_run_duration_seconds)}
                              </div>
                            </div>
                            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3">
                              <div className="text-xs text-gray-500 dark:text-gray-400 uppercase mb-1">Schedule</div>
                              <div className="text-sm text-charcoal dark:text-gray-100">{job.schedule_display || getScheduleLabel(job.schedule_type, job.schedule_value)}</div>
                            </div>
                          </div>

                          {/* Error Display */}
                          {job.last_error && (
                            <Alert variant="error">
                              <div>
                                <div className="text-xs uppercase mb-1 font-medium">Last Error</div>
                                <pre className="text-sm opacity-80 whitespace-pre-wrap font-mono">
                                  {job.last_error}
                                </pre>
                              </div>
                            </Alert>
                          )}

                          {/* Execution History */}
                          <div>
                            <h4 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">Recent Executions</h4>
                            {executionsLoading ? (
                              <div className="flex items-center justify-center py-4">
                                <Spinner size="md" />
                              </div>
                            ) : executionsData?.executions?.length ? (
                              <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="bg-gray-50 dark:bg-dark-surface-2 border-b border-gray-200 dark:border-dark-border">
                                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Started</th>
                                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Duration</th>
                                      <th className="text-left px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Triggered By</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-200 dark:divide-dark-border">
                                    {executionsData.executions.map((ex) => (
                                      <tr key={ex.id} className="hover:bg-gray-50 dark:hover:bg-dark-surface-2">
                                        <td className="px-3 py-2 text-charcoal dark:text-gray-100">
                                          {format(new Date(ex.started_at), 'MMM d, HH:mm:ss')}
                                        </td>
                                        <td className="px-3 py-2">
                                          <StatusBadge status={ex.status} />
                                        </td>
                                        <td className="px-3 py-2 text-gray-500 dark:text-gray-400">
                                          {formatDuration(ex.duration_seconds)}
                                        </td>
                                        <td className="px-3 py-2 text-gray-500 dark:text-gray-400 capitalize">
                                          {ex.triggered_by}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            ) : (
                              <div className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border">
                                No executions recorded yet
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Info Banner - moved below job list */}
        <Alert variant="info">
          <p>
            Jobs run automatically on their configured schedule. You can manually trigger jobs,
            view execution history, and enable/disable jobs. 
            {isConnected 
              ? ' Live updates are enabled via SSE - status changes appear in real-time.'
              : ' Status updates are polled every 10 seconds.'}
          </p>
          <p className="mt-2 text-xs opacity-75">
            Note: Schedule changes are stored in the database. For Celery Beat to pick up new schedules,
            you may need to restart the celery-beat worker.
          </p>
        </Alert>
        </div>

      </PageBody>
    </Page>
  );
}

export default JobSchedulerPage;

/**
 * Processing Status Components
 * Reusable components for showing document processing status, progress, and quality metrics
 */

import React from 'react';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  XCircleIcon,
  InformationCircleIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { Tooltip } from '../common/Tooltip';

export type ProcessingStatus = 'pending' | 'uploading' | 'processing' | 'completed' | 'failed' | 'cancelled';

// Status descriptions for tooltips
export const STATUS_DESCRIPTIONS: Record<ProcessingStatus, string> = {
  pending: 'File is queued and waiting to be uploaded',
  uploading: 'File is being transferred to the server',
  processing: 'File is being extracted, chunked, and embedded for AI queries',
  completed: 'Processing finished successfully - ready for AI queries',
  failed: 'An error occurred during processing - click retry to try again',
  cancelled: 'Processing was cancelled by the user',
};

interface StatusIconProps {
  status: ProcessingStatus;
  className?: string;
  animate?: boolean;
}

export function StatusIcon({ status, className = "w-5 h-5", animate = true }: StatusIconProps) {
  const baseClasses = className;
  
  switch (status) {
    case 'completed':
      return <CheckCircleIcon className={`${baseClasses} text-ai-success`} />;
    case 'failed':
      return <ExclamationTriangleIcon className={`${baseClasses} text-ai-danger`} />;
    case 'cancelled':
      return <XCircleIcon className={`${baseClasses} text-muted`} />;
    case 'processing':
      return (
        <ClockIcon 
          className={`${baseClasses} text-ai-warning ${animate ? 'animate-pulse' : ''}`} 
        />
      );
    case 'uploading':
      return (
        <div className={`${baseClasses} border-2 border-brand border-t-transparent rounded-full ${animate ? 'animate-spin' : ''}`} />
      );
    default:
      return <ClockIcon className={`${baseClasses} text-muted`} />;
  }
}

interface StatusBadgeProps {
  status: ProcessingStatus;
  className?: string;
  showTooltip?: boolean;
}

export function StatusBadge({ status, className = "", showTooltip = true }: StatusBadgeProps) {
  const baseClasses = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
  
  const statusClasses = {
    completed: "bg-ai-success-soft text-ai-success",
    failed: "bg-ai-danger-soft text-ai-danger",
    cancelled: "bg-surface-2 text-muted",
    processing: "bg-ai-warning-soft text-ai-warning",
    uploading: "bg-ai-info-soft text-ai-info",
    pending: "bg-surface-2 text-muted",
  };

  const badge = (
    <span className={`${baseClasses} ${statusClasses[status]} ${className}`}>
      {status}
    </span>
  );

  if (!showTooltip) {
    return badge;
  }

  return (
    <Tooltip content={STATUS_DESCRIPTIONS[status]} position="top">
      {badge}
    </Tooltip>
  );
}

interface ProgressBarProps {
  progress: number;
  status?: ProcessingStatus;
  className?: string;
  showPercentage?: boolean;
}

export function ProgressBar({ 
  progress, 
  status = 'processing', 
  className = "", 
  showPercentage = false 
}: ProgressBarProps) {
  const getProgressColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-ai-success';
      case 'failed':
        return 'bg-ai-danger';
      case 'cancelled':
        return 'bg-muted';
      case 'uploading':
        return 'bg-ai-info';
      default:
        return 'bg-brand';
    }
  };

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="w-full bg-surface-2 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-slow ${getProgressColor()} w-var`}
          style={{ ['--w' as any]: `${Math.min(Math.max(progress, 0), 100)}%` }}
        />
      </div>
      {showPercentage && (
        <div className="text-xs text-muted text-right">
          {Math.round(progress)}%
        </div>
      )}
    </div>
  );
}

interface QualityScoreProps {
  score: number;
  className?: string;
  showLabel?: boolean;
}

export function QualityScore({ score, className = "", showLabel = true }: QualityScoreProps) {
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-ai-success';
    if (score >= 0.6) return 'text-ai-warning';
    return 'text-ai-danger';
  };

  const getBarColor = (score: number) => {
    if (score >= 0.8) return 'bg-ai-success';
    if (score >= 0.6) return 'bg-ai-warning';
    return 'bg-ai-danger';
  };

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      <div className="flex-1">
        <div className="w-full bg-surface-2 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-slow ${getBarColor(score)} w-var`}
            style={{ ['--w' as any]: `${score * 100}%` }}
          />
        </div>
      </div>
      {showLabel && (
        <span className={`text-xs font-medium ${getScoreColor(score)}`}>
          {(score * 100).toFixed(0)}%
        </span>
      )}
    </div>
  );
}

interface ProcessingMetricsProps {
  chunks: number;
  processingTime?: number;
  qualityScore?: number;
  className?: string;
}

export function ProcessingMetrics({ 
  chunks, 
  processingTime, 
  qualityScore, 
  className = "" 
}: ProcessingMetricsProps) {
  const formatProcessingTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center space-x-1 text-muted">
          <ChartBarIcon className="w-4 h-4" />
          <span>Chunks</span>
        </div>
        <span className="text-text font-medium">{chunks}</span>
      </div>
      
      {processingTime && (
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-1 text-muted">
            <ClockIcon className="w-4 h-4" />
            <span>Processing Time</span>
          </div>
          <span className="text-text font-medium">
            {formatProcessingTime(processingTime)}
          </span>
        </div>
      )}
      
      {qualityScore !== undefined && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted">Quality Score</span>
          </div>
          <QualityScore score={qualityScore} showLabel={true} />
        </div>
      )}
    </div>
  );
}

interface ErrorDisplayProps {
  error: string;
  className?: string;
  compact?: boolean;
}

export function ErrorDisplay({ error, className = "", compact = false }: ErrorDisplayProps) {
  if (compact) {
    return (
      <div className={`flex items-center space-x-2 text-ai-danger ${className}`}>
        <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0" />
        <span className="text-xs truncate">{error}</span>
      </div>
    );
  }

  return (
    <div className={`bg-ai-danger-soft border border-ai-danger rounded-lg p-3 ${className}`}>
      <div className="flex items-start space-x-2">
        <ExclamationTriangleIcon className="w-5 h-5 text-ai-danger flex-shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-medium text-ai-danger">Processing Error</h4>
          <p className="text-sm text-ai-danger mt-1">{error}</p>
        </div>
      </div>
    </div>
  );
}

interface ProcessingStageProps {
  stage: 'upload' | 'extract' | 'chunk' | 'embed' | 'index' | 'complete';
  currentStage: string;
  className?: string;
}

export function ProcessingStage({ stage, currentStage, className = "" }: ProcessingStageProps) {
  const stages = [
    { key: 'upload', label: 'Upload', description: 'Uploading file' },
    { key: 'extract', label: 'Extract', description: 'Extracting content' },
    { key: 'chunk', label: 'Chunk', description: 'Creating chunks' },
    { key: 'embed', label: 'Embed', description: 'Generating embeddings' },
    { key: 'index', label: 'Index', description: 'Indexing vectors' },
    { key: 'complete', label: 'Complete', description: 'Processing complete' },
  ];

  const currentIndex = stages.findIndex(s => s.key === currentStage);
  const stageIndex = stages.findIndex(s => s.key === stage);

  const getStageStatus = () => {
    if (stageIndex < currentIndex) return 'completed';
    if (stageIndex === currentIndex) return 'processing';
    return 'pending';
  };

  const status = getStageStatus();
  const stageInfo = stages[stageIndex];

  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      <StatusIcon status={status} className="w-4 h-4" />
      <div>
        <div className="text-sm font-medium text-text">{stageInfo.label}</div>
        <div className="text-xs text-muted">{stageInfo.description}</div>
      </div>
    </div>
  );
}

interface ProcessingTimelineProps {
  currentStage: string;
  className?: string;
}

export function ProcessingTimeline({ currentStage, className = "" }: ProcessingTimelineProps) {
  const stages = ['upload', 'extract', 'chunk', 'embed', 'index', 'complete'];

  return (
    <div className={`space-y-3 ${className}`}>
      <h4 className="text-sm font-medium text-text">Processing Stages</h4>
      <div className="space-y-2">
        {stages.map((stage) => (
          <ProcessingStage 
            key={stage} 
            stage={stage as any} 
            currentStage={currentStage} 
          />
        ))}
      </div>
    </div>
  );
}

interface ProcessingSummaryProps {
  status: ProcessingStatus;
  progress?: number;
  error?: string;
  metrics?: {
    chunks?: number;
    processingTime?: number;
    qualityScore?: number;
  };
  className?: string;
}

export function ProcessingSummary({ 
  status, 
  progress = 0, 
  error, 
  metrics, 
  className = "" 
}: ProcessingSummaryProps) {
  return (
    <div className={`bg-surface border border-border rounded-lg p-4 space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <StatusIcon status={status} />
          <StatusBadge status={status} />
        </div>
        {(status === 'uploading' || status === 'processing') && (
          <span className="text-sm text-muted">{Math.round(progress)}%</span>
        )}
      </div>

      {(status === 'uploading' || status === 'processing') && (
        <ProgressBar progress={progress} status={status} />
      )}

      {error && <ErrorDisplay error={error} compact />}

      {metrics && status === 'completed' && (
        <ProcessingMetrics
          chunks={metrics.chunks || 0}
          processingTime={metrics.processingTime}
          qualityScore={metrics.qualityScore}
        />
      )}
    </div>
  );
}

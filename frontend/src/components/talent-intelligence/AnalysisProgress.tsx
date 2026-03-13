/**
 * Analysis Progress Component
 * 
 * Monitors AI analysis progress with real-time SSE updates
 * Displays 7-stage ML Talent Intelligence workflow
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircleIcon, ArrowPathIcon, SparklesIcon, XCircleIcon, ClockIcon } from '@heroicons/react/24/outline';
import { useAnalysisStream } from '../../hooks/useAnalysisStream';
import { useGetTalentAnalysis } from '../../generated/talent/talent';
import { useToasts } from '../../stores/useToasts';

interface AnalysisProgressProps {
  analysisId: string;
  onComplete: (results: any) => void;
}

interface StageProgress {
  id: number;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  message?: string;
  metadata?: any;
  startTime?: number;
  endTime?: number;
}

const STAGES: Omit<StageProgress, 'status' | 'message' | 'metadata' | 'startTime' | 'endTime'>[] = [
  {
    id: 1,
    name: 'Understanding Your Team',
    description: 'Analyzing your top performers to understand what makes them successful',
  },
  {
    id: 2,
    name: 'Analyzing Requirements',
    description: 'Understanding the key skills and qualities needed for this role',
  },
  {
    id: 3,
    name: 'Reviewing Applications',
    description: 'Analyzing candidate resumes and qualifications',
  },
  {
    id: 4,
    name: 'Evaluating Applicants',
    description: 'Scoring candidates against your ideal profile',
  },
  {
    id: 5,
    name: 'Searching Talent Market',
    description: 'Finding additional qualified candidates who match your needs',
  },
  {
    id: 6,
    name: 'Evaluating Market Candidates',
    description: 'Scoring newly discovered candidates',
  },
  {
    id: 7,
    name: 'Generating Insights',
    description: 'Creating your personalized talent intelligence report',
  },
];

export function AnalysisProgress({ analysisId, onComplete }: AnalysisProgressProps) {
  const navigate = useNavigate();
  const { push: addToast } = useToasts();
  const [stages, setStages] = useState<StageProgress[]>(
    STAGES.map(stage => ({ ...stage, status: 'pending' as const }))
  );

  const [currentMessage, setCurrentMessage] = useState('Initializing analysis...');
  const [errorDetails, setErrorDetails] = useState<string | null>(null);

  // Connect to SSE stream for real-time updates
  const {
    events,
    isComplete,
    isFailed,
    error,
    progressPercentage,
  } = useAnalysisStream(analysisId);

  // Fetch final results when complete
  const { data: analysisResults, refetch } = useGetTalentAnalysis(analysisId, {
    enabled: isComplete,
  });

  // Update stages based on SSE events
  useEffect(() => {
    if (events.length === 0) return;

    const latestEvent = events[events.length - 1];

    // Update current message
    if (latestEvent.message) {
      setCurrentMessage(latestEvent.message);
    }

    // Handle error events
    if (latestEvent.event_type === 'analysis_error' || latestEvent.event_type === 'analysis_failed') {
      setErrorDetails(latestEvent.message || 'An error occurred during analysis');
      // Mark all running stages as error
      setStages(prev => prev.map(stage => 
        stage.status === 'running' ? { ...stage, status: 'error' as const } : stage
      ));
      return;
    }

    // Update stage status based on event type
    const stageMatch = latestEvent.event_type.match(/stage_(\d+)_(started|completed)/);
    if (stageMatch) {
      const stageNum = parseInt(stageMatch[1]);
      const action = stageMatch[2];

      setStages(prev => prev.map(stage => {
        if (stage.id === stageNum) {
          return {
            ...stage,
            status: action === 'completed' ? 'completed' as const : 'running' as const,
            message: latestEvent.message,
            metadata: (latestEvent as any).metadata, // SSE events may have metadata
            startTime: action === 'started' ? Date.now() : stage.startTime,
            endTime: action === 'completed' ? Date.now() : undefined,
          };
        }
        return stage;
      }));
    }
  }, [events]);

  // Handle completion - redirect to history page
  useEffect(() => {
    if (isComplete && analysisResults) {
      refetch().then(() => {
        addToast({
          kind: 'success',
          message: 'Analysis completed successfully! Redirecting to results...',
        });
        // Wait a moment for the toast, then navigate
        setTimeout(() => {
          navigate(`/talent/history?analysis_id=${analysisId}`);
        }, 1500);
      });
    }
  }, [isComplete, analysisResults, addToast, navigate, analysisId, refetch]);
  
  // Handle failure - redirect to history page
  useEffect(() => {
    if (isFailed || errorDetails) {
      addToast({
        kind: 'error',
        message: 'Analysis failed. Redirecting to history...',
      });
      // Wait a moment for the toast, then navigate
      setTimeout(() => {
        navigate(`/talent/history?analysis_id=${analysisId}`);
      }, 2000);
    }
  }, [isFailed, errorDetails, addToast, navigate, analysisId]);

  // Calculate progress based on completed stages
  const completedStages = stages.filter(s => s.status === 'completed').length;
  const calculatedProgress = Math.round((completedStages / stages.length) * 100);
  const displayProgress = progressPercentage || calculatedProgress;

  // Error state
  if (isFailed || errorDetails) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <div className="w-20 h-20 mx-auto mb-4 bg-error/10 rounded-full flex items-center justify-center">
            <XCircleIcon className="w-10 h-10 text-error" />
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Analysis Failed</h2>
          <p className="text-muted mb-4">{errorDetails || error || 'An unexpected error occurred'}</p>
        </div>

        {/* Show stages with error state */}
        <div className="space-y-3">
          {stages.map((stage) => (
            <div key={stage.id} className="p-4 bg-surface rounded-lg border border-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    stage.status === 'error' ? 'bg-error/10' :
                    stage.status === 'completed' ? 'bg-success/10' :
                    stage.status === 'running' ? 'bg-primary/10' :
                    'bg-surface-3'
                  }`}>
                    {stage.status === 'error' ? (
                      <XCircleIcon className="w-4 h-4 text-error" />
                    ) : stage.status === 'completed' ? (
                      <CheckCircleIcon className="w-4 h-4 text-success" />
                    ) : (
                      <span className="text-xs text-muted-2">{stage.id}</span>
                    )}
                  </div>
                  <div>
                    <div className="font-medium text-foreground">{stage.name}</div>
                    <div className="text-xs text-muted">{stage.description}</div>
                  </div>
                </div>
                <div className={`text-xs font-medium ${
                  stage.status === 'error' ? 'text-error' :
                  stage.status === 'completed' ? 'text-success' :
                  'text-muted-2'
                }`}>
                  {stage.status === 'error' ? 'Failed' :
                   stage.status === 'completed' ? '✓' :
                   ''}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <div className="w-20 h-20 mx-auto mb-4 bg-primary/10 rounded-full flex items-center justify-center">
          <SparklesIcon className="w-10 h-10 text-primary animate-pulse" />
        </div>
        <h2 className="text-2xl font-bold text-foreground mb-2">
          AI Analysis in Progress
        </h2>
        <p className="text-muted">
          7-stage workflow analyzing requirements, parsing resumes, and generating insights
        </p>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted">Overall Progress</span>
          <span className="font-medium text-foreground">{displayProgress}%</span>
        </div>
        <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary to-brand transition-all duration-500"
            style={{ width: `${displayProgress}%` }}
          />
        </div>
        <div className="text-xs text-muted text-center">
          {completedStages} of {stages.length} stages complete
        </div>
      </div>

      {/* Current Message */}
      <div className="p-4 bg-surface-2 rounded-lg border border-border">
        <div className="flex items-center gap-3">
          <ArrowPathIcon className="w-5 h-5 text-primary animate-spin flex-shrink-0" />
          <p className="text-foreground text-sm">{currentMessage}</p>
        </div>
      </div>

      {/* Stage Progress */}
      <div className="space-y-3">
        {stages.map((stage) => {
          const duration = stage.startTime && stage.endTime 
            ? ((stage.endTime - stage.startTime) / 1000).toFixed(1) 
            : null;

          return (
            <div 
              key={stage.id} 
              className={`p-4 rounded-lg border transition-all ${
                stage.status === 'completed' ? 'bg-success/5 border-success/20' :
                stage.status === 'running' ? 'bg-primary/5 border-primary/30' :
                'bg-surface border-border'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3 flex-1">
                  {/* Icon */}
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                    stage.status === 'completed' ? 'bg-success/20' :
                    stage.status === 'running' ? 'bg-primary/20' :
                    'bg-surface-3'
                  }`}>
                    {stage.status === 'completed' ? (
                      <CheckCircleIcon className="w-5 h-5 text-success" />
                    ) : stage.status === 'running' ? (
                      <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />
                    ) : (
                      <span className="text-sm font-medium text-muted-2">{stage.id}</span>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-foreground">{stage.name}</h3>
                      {duration && (
                        <span className="text-xs text-muted flex items-center gap-1">
                          <ClockIcon className="w-3 h-3" />
                          {duration}s
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted mb-1">{stage.description}</p>
                    {stage.message && stage.status === 'running' && (
                      <p className="text-xs text-primary mt-2">{stage.message}</p>
                    )}
                    {stage.metadata && (
                      <div className="text-xs text-muted mt-2 space-y-1">
                        {stage.metadata.employee_count && (
                          <div>👥 {stage.metadata.employee_count} employees analyzed</div>
                        )}
                        {stage.metadata.parsed_count && (
                          <div>📄 {stage.metadata.parsed_count} resumes parsed</div>
                        )}
                        {stage.metadata.scored_count && (
                          <div>⭐ {stage.metadata.scored_count} candidates scored</div>
                        )}
                        {stage.metadata.candidate_count && (
                          <div>🔍 {stage.metadata.candidate_count} candidates found</div>
                        )}
                        {stage.metadata.insight_count && (
                          <div>💡 {stage.metadata.insight_count} insights generated</div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Status */}
                <div className={`text-sm font-medium flex-shrink-0 ${
                  stage.status === 'completed' ? 'text-success' :
                  stage.status === 'running' ? 'text-primary' :
                  'text-muted-2'
                }`}>
                  {stage.status === 'completed' ? 'Complete' :
                   stage.status === 'running' ? 'Running...' :
                   'Pending'}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Info */}
      <div className="p-4 bg-info/10 rounded-lg border border-info/30">
        <p className="text-sm text-foreground">
          <strong>What's happening:</strong> Our AI is analyzing your team, reviewing all candidates, 
          searching the market for additional qualified talent, and generating personalized insights. 
          This typically takes 1-2 minutes.
        </p>
      </div>
    </div>
  );
}


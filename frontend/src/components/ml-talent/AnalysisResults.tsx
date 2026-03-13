import React, { useState, useEffect } from 'react';
import {
  CheckCircleIcon,
  ClockIcon,
  ExclamationCircleIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import {
  useGetAnalysisStatusApiV1MlTalentAnalysisAnalysisIdStatusGet,
  useGetAnalysisApiV1MlTalentAnalysisAnalysisIdGet,
} from '../../generated/ml-talent-intelligence/ml-talent-intelligence';
import Card from '../../shared/ui/Card';
import { AnalysisStatus } from '../../generated/models/analysisStatus';

interface AnalysisResultsProps {
  analysisId: string;
}

export const AnalysisResults: React.FC<AnalysisResultsProps> = ({ analysisId }) => {
  const [pollingInterval, setPollingInterval] = useState(3000); // Poll every 3 seconds

  const { data: status, isLoading: statusLoading } = useGetAnalysisStatusApiV1MlTalentAnalysisAnalysisIdStatusGet(
    analysisId,
    {
      query: {
        refetchInterval: pollingInterval,
      },
    }
  );

  const { data: result, isLoading: resultLoading } = useGetAnalysisApiV1MlTalentAnalysisAnalysisIdGet(
    analysisId,
    {
      query: {
        enabled: status?.status === AnalysisStatus.completed,
      },
    }
  );

  // Stop polling when analysis is complete or failed
  useEffect(() => {
    if (status?.status === AnalysisStatus.completed || status?.status === AnalysisStatus.failed) {
      setPollingInterval(0);
    }
  }, [status?.status]);

  const getStatusIcon = () => {
    switch (status?.status) {
      case AnalysisStatus.completed:
        return <CheckCircleIcon className="w-6 h-6 text-success" />;
      case AnalysisStatus.failed:
        return <ExclamationCircleIcon className="w-6 h-6 text-error" />;
      case AnalysisStatus.processing:
      case AnalysisStatus.pending:
        return <ClockIcon className="w-6 h-6 text-brand animate-pulse" />;
      default:
        return <ClockIcon className="w-6 h-6 text-muted" />;
    }
  };

  const getStatusColor = () => {
    switch (status?.status) {
      case AnalysisStatus.completed:
        return 'text-success';
      case AnalysisStatus.failed:
        return 'text-error';
      case AnalysisStatus.processing:
        return 'text-brand';
      default:
        return 'text-muted';
    }
  };

  if (statusLoading && !status) {
    return (
      <Card>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <ClockIcon className="w-12 h-12 text-muted mx-auto mb-3 animate-pulse" />
            <p className="text-text font-medium">Loading Analysis...</p>
          </div>
        </div>
      </Card>
    );
  }

  const isProcessing = status?.status === AnalysisStatus.processing || status?.status === AnalysisStatus.pending;

  return (
    <div className="space-y-6">
      {/* Status Card */}
      <Card>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            {getStatusIcon()}
            <div>
              <h2 className="text-lg font-semibold text-text">Analysis Status</h2>
              <p className="text-sm text-muted">Analysis ID: {analysisId}</p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor()} bg-current bg-opacity-10`}>
            {status?.status?.toUpperCase() || 'UNKNOWN'}
          </span>
        </div>

        {status?.message && (
          <p className="text-text mb-3">{status.message}</p>
        )}

        {isProcessing && (
          <div className="space-y-2">
            <div className="w-full bg-surface rounded-full h-2 overflow-hidden">
              <div 
                className="h-full bg-brand transition-all duration-500"
                style={{ width: `${status?.progress_percentage || 0}%` }}
              ></div>
            </div>
            <p className="text-sm text-muted text-center">
              {status?.progress_percentage ? `${status.progress_percentage}% complete` : 'Processing...'}
            </p>
          </div>
        )}

        {status?.status === AnalysisStatus.failed && (
          <div className="mt-4 p-4 bg-error/10 border border-error/20 rounded-lg">
            <p className="text-error text-sm">
              Analysis failed. Please try again or contact support if the issue persists.
            </p>
          </div>
        )}
      </Card>

      {/* Results Card - Only shown when completed */}
      {status?.status === AnalysisStatus.completed && result && (
        <Card>
          <div className="flex items-center space-x-2 mb-4">
            <SparklesIcon className="w-5 h-5 text-brand" />
            <h2 className="text-lg font-semibold text-text">Analysis Results</h2>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-surface rounded-lg p-4 text-center">
              <p className="text-3xl font-bold text-brand">
                {result.applicant_results?.length || 0}
              </p>
              <p className="text-sm text-muted mt-1">Applicants Analyzed</p>
            </div>
            <div className="bg-surface rounded-lg p-4 text-center">
              <p className="text-3xl font-bold text-brand">
                {result.market_results?.length || 0}
              </p>
              <p className="text-sm text-muted mt-1">Market Candidates</p>
            </div>
            <div className="bg-surface rounded-lg p-4 text-center">
              <p className="text-3xl font-bold text-success">
                {result.overall_confidence ? Math.round(result.overall_confidence * 100) : 0}%
              </p>
              <p className="text-sm text-muted mt-1">Confidence</p>
            </div>
          </div>

          {/* Executive Summary */}
          {result.synthesis?.executive_summary && (
            <div className="mt-6 p-4 bg-surface rounded-lg">
              <h3 className="text-sm font-semibold text-text mb-2">Executive Summary</h3>
              <p className="text-text text-sm leading-relaxed">
                {result.synthesis.executive_summary}
              </p>
            </div>
          )}

          {/* Top Candidates */}
          {result.top_overall && result.top_overall.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-text mb-3">Top Candidates</h3>
              <div className="space-y-3">
                {result.top_overall.slice(0, 3).map((candidate: any, index: number) => (
                  <div key={index} className="bg-surface rounded-lg p-4 border border-divider">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <span className={`
                          w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                          ${index === 0 ? 'bg-brand text-white' : 'bg-surface border border-divider text-text'}
                        `}>
                          #{index + 1}
                        </span>
                        <div>
                          <p className="font-medium text-text">{candidate.name || `Candidate ${index + 1}`}</p>
                          <p className="text-sm text-muted">
                            {candidate.source === 'applicant' ? 'Applicant' : 'Market Search'}
                          </p>
                        </div>
                      </div>
                      <span className="px-3 py-1 bg-success/10 text-success rounded-full text-sm font-medium">
                        {Math.round((candidate.overall_score || 0) * 100)}
                      </span>
                    </div>
                    {candidate.explanation && (
                      <p className="text-sm text-muted mt-2 pl-11">
                        {candidate.explanation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Key Patterns */}
          {result.patterns && result.patterns.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-text mb-3">Key Patterns Identified</h3>
              <div className="space-y-2">
                {result.patterns.map((pattern: any, index: number) => (
                  <div key={index} className="bg-surface rounded-lg p-3 border border-divider">
                    <p className="text-sm font-medium text-text">{pattern.pattern_type}</p>
                    <p className="text-sm text-muted mt-1">{pattern.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Placeholder for when processing */}
      {isProcessing && (
        <Card>
          <div className="text-center py-12">
            <ClockIcon className="w-16 h-16 text-muted mx-auto mb-4 animate-pulse" />
            <h3 className="text-lg font-medium text-text mb-2">Analysis in Progress</h3>
            <p className="text-sm text-muted max-w-md mx-auto">
              We're parsing resumes, building baselines, scoring candidates, and searching the market.
              This typically takes 2-5 minutes.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
};

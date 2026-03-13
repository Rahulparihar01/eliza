/**
 * Results Display Component
 * Shows the analysis results from the Data Analysis Agent
 */

import React from 'react';
import {
  ChartBarIcon,
  DocumentTextIcon,
  LightBulbIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import Card from '../../shared/ui/Card';
import {
  useGetAnalysisResultV1BiQuestionsQuestionIdResultGet,
  useGetQuestionV1BiQuestionsQuestionIdGet,
} from '../../generated/business-intelligence/business-intelligence';
import { QuestionStatus } from '../../generated/models/questionStatus';

interface ResultsDisplayProps {
  questionId: string;
}

export default function ResultsDisplay({ questionId }: ResultsDisplayProps) {
  // Fetch question details
  const { data: questionData, isLoading: questionLoading } = useGetQuestionV1BiQuestionsQuestionIdGet(
    questionId,
    {
      query: {
        enabled: !!questionId,
        refetchInterval: 3000, // Refetch every 3 seconds until completed
      },
    }
  );

  const status = questionData?.status;
  const shouldFetchResult = !!questionId && status === QuestionStatus.completed;

  // Fetch result (only when completed)
  const { data: resultData, isLoading: resultLoading } = useGetAnalysisResultV1BiQuestionsQuestionIdResultGet(
    questionId,
    {
      query: {
        enabled: shouldFetchResult,
      },
    }
  );

  if (!questionData) {
    return null;
  }

  if (questionLoading) {
    return (
      <Card>
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
          <p className="text-muted mt-4">Loading question...</p>
        </div>
      </Card>
    );
  }

  // Show error if failed
  if (status === QuestionStatus.failed) {
    return (
      <Card>
        <div className="flex items-center space-x-3 mb-4">
          <ExclamationCircleIcon className="w-6 h-6 text-error" />
          <h2 className="text-lg font-semibold text-text">Processing Failed</h2>
        </div>
        <p className="text-muted mb-4">
          We encountered an error while processing your question.
        </p>
        {questionData.error_message && (
          <div className="p-4 bg-error-soft border border-error rounded-lg">
            <p className="text-sm text-error">{questionData.error_message}</p>
          </div>
        )}
      </Card>
    );
  }

  // Show processing status
  if (status !== QuestionStatus.completed) {
    return (
      <Card>
        <div className="flex items-center space-x-3 mb-4">
          <ClockIcon className="w-6 h-6 text-brand animate-pulse" />
          <h2 className="text-lg font-semibold text-text">Processing Your Question</h2>
        </div>
        <p className="text-muted mb-4">
          Your question is being processed through our AI analysis pipeline. This may take a few moments.
        </p>
        <div className="p-4 bg-bg border border-border rounded-lg">
          <p className="text-sm text-text font-medium mb-2">Original Question:</p>
          <p className="text-text">{questionData.original_question}</p>
        </div>
      </Card>
    );
  }

  // Show results
  if (resultLoading) {
    return (
      <Card>
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
          <p className="text-muted mt-4">Loading results...</p>
        </div>
      </Card>
    );
  }

  if (!resultData) {
    return null;
  }

  return (
    <Card>
      <div className="flex items-center space-x-3 mb-6">
        <CheckCircleIcon className="w-6 h-6 text-success" />
        <h2 className="text-lg font-semibold text-text">Analysis Complete</h2>
      </div>

      {/* Executive Summary */}
      {resultData.executive_summary && (
        <div className="mb-6 p-4 bg-brand-soft border border-brand rounded-lg">
          <h3 className="text-sm font-semibold text-brand mb-2">Executive Summary</h3>
          <p className="text-text">{resultData.executive_summary}</p>
        </div>
      )}

      {/* Analysis Text */}
      <div className="mb-6">
        <div className="flex items-center space-x-2 mb-3">
          <ChartBarIcon className="w-5 h-5 text-brand" />
          <h3 className="text-base font-semibold text-text">Detailed Analysis</h3>
        </div>
        <div className="prose prose-sm max-w-none text-text">
          <p className="whitespace-pre-wrap">{resultData.analysis_text}</p>
        </div>
      </div>

      {/* Key Findings */}
      {resultData.key_findings && resultData.key_findings.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center space-x-2 mb-3">
            <LightBulbIcon className="w-5 h-5 text-brand" />
            <h3 className="text-base font-semibold text-text">Key Findings</h3>
          </div>
          <ul className="space-y-2">
            {resultData.key_findings.map((finding: any, index: number) => (
              <li key={index} className="flex items-start space-x-2">
                <CheckCircleIcon className="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
                <span className="text-text">{typeof finding === 'string' ? finding : JSON.stringify(finding)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendations */}
      {resultData.recommendations && resultData.recommendations.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center space-x-2 mb-3">
            <DocumentTextIcon className="w-5 h-5 text-brand" />
            <h3 className="text-base font-semibold text-text">Recommendations</h3>
          </div>
          <ul className="space-y-2">
            {resultData.recommendations.map((rec: any, index: number) => (
              <li key={index} className="flex items-start space-x-2">
                <span className="text-brand font-bold mt-0.5 flex-shrink-0">{index + 1}.</span>
                <span className="text-text">{typeof rec === 'string' ? rec : JSON.stringify(rec)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Data Sources */}
      {resultData.data_sources_used && resultData.data_sources_used.length > 0 && (
        <div className="mb-6 p-4 bg-bg border border-border rounded-lg">
          <h3 className="text-sm font-semibold text-text mb-2">Data Sources Used</h3>
          <div className="flex flex-wrap gap-2">
            {resultData.data_sources_used.map((source: any, index: number) => (
              <span
                key={index}
                className="px-3 py-1 bg-surface border border-border rounded-full text-xs text-text"
              >
                {typeof source === 'string' ? source : JSON.stringify(source)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Confidence Score */}
      {resultData.confidence_score !== undefined && resultData.confidence_score !== null && (
        <div className="p-4 bg-bg border border-border rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-text">Confidence Score</span>
            <span className="text-sm font-bold text-brand">{(resultData.confidence_score * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-border rounded-full h-2">
            <div
              className="bg-brand h-2 rounded-full transition-all duration-300 w-var"
              style={{ ['--w' as any]: `${resultData.confidence_score * 100}%` }}
            ></div>
          </div>
        </div>
      )}
    </Card>
  );
}

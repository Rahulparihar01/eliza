/**
 * Results Display Component
 * Shows charts, tables, and insights from query results in a single scrollable view
 */
import React from 'react';
import {
  useGetAnalysisResultV1DataAnalystQuestionsQuestionIdResultGet,
  useGetQuestionStatusV1DataAnalystQuestionsQuestionIdStatusGet,
} from '../../generated/data-analyst/data-analyst';
import DataTable from './DataTable';
import ChartDisplay from './ChartDisplay';
import InsightsPanel from './InsightsPanel';
import LoadingSpinner from '../common/LoadingSpinner';
import { 
  ChartBarIcon, 
  TableCellsIcon, 
  LightBulbIcon,
  CodeBracketIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';

interface ResultsDisplayProps {
  questionId: string;
}

export default function ResultsDisplay({ questionId }: ResultsDisplayProps) {
  
  const { data: statusData } = useGetQuestionStatusV1DataAnalystQuestionsQuestionIdStatusGet(
    questionId,
    {
      query: {
        refetchInterval: (query) => {
          // Poll until completed or failed
          const status = query.state?.data?.status;
          return status === 'completed' || status === 'failed' ? false : 2000;
        },
      },
    }
  );

  const { data: resultData } = useGetAnalysisResultV1DataAnalystQuestionsQuestionIdResultGet(
    questionId,
    {
      query: {
        enabled: statusData?.status === 'completed',
      },
    }
  );

  if (!statusData) {
    return (
      <div className="p-8 text-center">
        <LoadingSpinner />
      </div>
    );
  }

  if (statusData.status === 'processing' || statusData.status === 'pending') {
    return (
      <div className="p-8 text-center">
        <LoadingSpinner />
        <p className="text-muted mt-4">Processing your question...</p>
        <p className="text-sm text-muted mt-2">
          {statusData.progress_percentage}% complete
        </p>
      </div>
    );
  }

  if (statusData.status === 'failed') {
    return (
      <div className="p-8">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-red-600 mb-2">Failed to Process Question</h3>
          <p className="text-sm text-muted">{statusData.error_message || 'Unknown error occurred'}</p>
        </div>
      </div>
    );
  }

  if (!resultData) {
    return (
      <div className="p-8 text-center text-muted">
        <p>No results available</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-bg">
      <div className="p-8 space-y-12 max-w-6xl mx-auto">
        <>
          {/* Key Metrics */}
          {resultData.result_metadata?.statistics && (
            <div className="space-y-6">
            <div className="flex items-center gap-2">
              <SparklesIcon className="w-4 h-4 text-brand/60" />
              <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Key Metrics</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {Object.entries(resultData.result_metadata.statistics).slice(0, 3).map(([col, stat]: [string, any]) => {
                if (stat?.type === 'numeric') {
                  return (
                    <div key={col} className="space-y-2">
                      <p className="text-xs text-muted/60 uppercase tracking-wide">{col}</p>
                      <p className="text-4xl font-light text-text">{stat.mean?.toFixed(2) || 'N/A'}</p>
                      <p className="text-xs text-muted/50">
                        {stat.min?.toFixed(2)} – {stat.max?.toFixed(2)}
                      </p>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          </div>
          )}

          {/* Executive Summary */}
          {resultData.result_metadata?.summary && typeof resultData.result_metadata.summary === 'string' && (
            <div className="space-y-4 pb-8 border-b border-border/20">
              <div className="flex items-center gap-2">
                <SparklesIcon className="w-4 h-4 text-brand/60" />
                <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Executive Summary</h2>
              </div>
              <p className="text-base text-text/80 leading-relaxed max-w-4xl">
                {resultData.result_metadata.summary}
              </p>
            </div>
          )}

          {/* Visualizations */}
          {resultData.result_metadata?.chart_suggestions && Array.isArray(resultData.result_metadata.chart_suggestions) && resultData.result_metadata.chart_suggestions.length > 0 && (
            <div className="space-y-6 pb-8 border-b border-border/20">
              <div className="flex items-center gap-2">
                <ChartBarIcon className="w-4 h-4 text-brand/60" />
                <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Visualizations</h2>
                <span className="text-xs text-muted/40">
                  {resultData.result_metadata.chart_suggestions.length} chart{resultData.result_metadata.chart_suggestions.length > 1 ? 's' : ''}
                </span>
              </div>
              <ChartDisplay
                metadata={resultData.result_metadata}
                data={resultData.result_data}
              />
            </div>
          )}

          {/* Insights Panel */}
          {resultData.result_metadata && (
            <div className="space-y-6 pb-8 border-b border-border/20">
              <div className="flex items-center gap-2">
                <LightBulbIcon className="w-4 h-4 text-brand/60" />
                <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Detailed Insights</h2>
              </div>
              <InsightsPanel metadata={resultData.result_metadata} />
            </div>
          )}

          {/* Data Table */}
          <div className="space-y-6 pb-8 border-b border-border/20">
            <div className="flex items-center gap-2">
              <TableCellsIcon className="w-4 h-4 text-brand/60" />
              <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Raw Data</h2>
              <span className="text-xs text-muted/40">
                {(resultData.result_data as { row_count?: number })?.row_count || 0} row{((resultData.result_data as { row_count?: number })?.row_count || 0) !== 1 ? 's' : ''}
              </span>
            </div>
            <DataTable data={resultData.result_data as { columns: string[]; rows: any[][]; row_count: number }} />
          </div>

          {/* Generated SQL */}
          {resultData.result_metadata?.sql && typeof resultData.result_metadata.sql === 'string' && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <CodeBracketIcon className="w-4 h-4 text-brand/60" />
                <h2 className="text-xs font-semibold text-muted uppercase tracking-wider">Generated SQL</h2>
              </div>
              <pre className="text-xs text-muted/70 overflow-x-auto bg-bg/30 p-6 rounded-lg border border-border/20 font-mono leading-relaxed">
                {resultData.result_metadata.sql}
              </pre>
            </div>
          )}
        </>
      </div>
    </div>
  );
}

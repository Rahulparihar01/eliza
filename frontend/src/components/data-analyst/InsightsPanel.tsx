/**
 * Rich Insights Panel Component
 * Displays structured insights, statistics, and recommendations
 */
import React, { useState } from 'react';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  CheckCircleIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';

interface InsightsPanelProps {
  metadata: any;
}

export default function InsightsPanel({ metadata }: InsightsPanelProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    summary: true,
    findings: true,
    statistics: false,
    anomalies: true,
    recommendations: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const insights = metadata?.insights || {};
  const statistics = metadata?.statistics || {};
  const keyFindings = insights?.key_findings || metadata?.key_findings || [];
  const anomalies = insights?.anomalies || metadata?.anomalies || [];
  const recommendations = insights?.recommendations || metadata?.recommendations || [];
  const executiveSummary = insights?.executive_summary || metadata?.summary || '';

  return (
    <div className="space-y-4">
      {/* Executive Summary */}
      {executiveSummary && (
        <div className="bg-surface p-6 rounded-lg border border-border">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-brand-soft rounded-lg">
              <DocumentTextIcon className="w-5 h-5 text-brand" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-text mb-2">Executive Summary</h3>
              <p className="text-sm text-muted leading-relaxed">{executiveSummary}</p>
            </div>
          </div>
        </div>
      )}

      {/* Key Findings */}
      {keyFindings.length > 0 && (
        <div className="bg-surface rounded-lg border border-border">
          <button
            onClick={() => toggleSection('findings')}
            className="w-full p-4 flex items-center justify-between hover:bg-surface-hover transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/10 rounded-lg">
                <LightBulbIcon className="w-5 h-5 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-text">Key Findings</h3>
              <span className="text-xs text-muted bg-surface-2 px-2 py-1 rounded">
                {keyFindings.length}
              </span>
            </div>
            {expandedSections.findings ? (
              <ChevronUpIcon className="w-5 h-5 text-muted" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-muted" />
            )}
          </button>
          {expandedSections.findings && (
            <div className="px-4 pb-4">
              <ul className="space-y-3">
                {keyFindings.map((finding: string, idx: number) => (
                  <li key={idx} className="flex items-start gap-3">
                    <CheckCircleIcon className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                    <span className="text-sm text-muted flex-1">{finding}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Statistical Summary */}
      {Object.keys(statistics).length > 0 && (
        <div className="bg-surface rounded-lg border border-border">
          <button
            onClick={() => toggleSection('statistics')}
            className="w-full p-4 flex items-center justify-between hover:bg-surface-hover transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/10 rounded-lg">
                <ChartBarIcon className="w-5 h-5 text-purple-600" />
              </div>
              <h3 className="text-lg font-semibold text-text">Statistical Summary</h3>
            </div>
            {expandedSections.statistics ? (
              <ChevronUpIcon className="w-5 h-5 text-muted" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-muted" />
            )}
          </button>
          {expandedSections.statistics && (
            <div className="px-4 pb-4">
              <div className="space-y-4">
                {Object.entries(statistics).map(([col, stat]: [string, any]) => (
                  <div key={col} className="border-b border-border/50 pb-3 last:border-0">
                    <h4 className="text-sm font-semibold text-text mb-2">{col}</h4>
                    {stat.type === 'numeric' ? (
                      <div className="grid grid-cols-2 gap-2 text-xs text-muted">
                        <div>
                          <span className="font-medium">Mean:</span> {stat.mean?.toFixed(2)}
                        </div>
                        <div>
                          <span className="font-medium">Median:</span> {stat.median?.toFixed(2)}
                        </div>
                        <div>
                          <span className="font-medium">Min:</span> {stat.min?.toFixed(2)}
                        </div>
                        <div>
                          <span className="font-medium">Max:</span> {stat.max?.toFixed(2)}
                        </div>
                        {stat.std_dev && (
                          <div>
                            <span className="font-medium">Std Dev:</span> {stat.std_dev.toFixed(2)}
                          </div>
                        )}
                        <div>
                          <span className="font-medium">Sum:</span> {stat.sum?.toFixed(2)}
                        </div>
                      </div>
                    ) : (
                      <div className="text-xs text-muted">
                        <div>
                          <span className="font-medium">Unique Values:</span> {stat.unique_count}
                        </div>
                        {stat.most_common && stat.most_common.length > 0 && (
                          <div className="mt-2">
                            <span className="font-medium">Most Common:</span>
                            <ul className="mt-1 space-y-1">
                              {stat.most_common.map((item: any, idx: number) => (
                                <li key={idx} className="ml-4">
                                  {item.value} ({item.count})
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <div className="bg-surface rounded-lg border border-border">
          <button
            onClick={() => toggleSection('anomalies')}
            className="w-full p-4 flex items-center justify-between hover:bg-surface-hover transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-500/10 rounded-lg">
                <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600" />
              </div>
              <h3 className="text-lg font-semibold text-text">Anomalies</h3>
              <span className="text-xs text-muted bg-surface-2 px-2 py-1 rounded">
                {anomalies.length}
              </span>
            </div>
            {expandedSections.anomalies ? (
              <ChevronUpIcon className="w-5 h-5 text-muted" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-muted" />
            )}
          </button>
          {expandedSections.anomalies && (
            <div className="px-4 pb-4">
              <ul className="space-y-2">
                {anomalies.map((anomaly: string, idx: number) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-muted">
                    <ExclamationTriangleIcon className="w-4 h-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                    <span>{anomaly}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="bg-surface rounded-lg border border-border">
          <button
            onClick={() => toggleSection('recommendations')}
            className="w-full p-4 flex items-center justify-between hover:bg-surface-hover transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/10 rounded-lg">
                <CheckCircleIcon className="w-5 h-5 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-text">Recommendations</h3>
              <span className="text-xs text-muted bg-surface-2 px-2 py-1 rounded">
                {recommendations.length}
              </span>
            </div>
            {expandedSections.recommendations ? (
              <ChevronUpIcon className="w-5 h-5 text-muted" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-muted" />
            )}
          </button>
          {expandedSections.recommendations && (
            <div className="px-4 pb-4">
              <ul className="space-y-3">
                {recommendations.map((rec: string, idx: number) => (
                  <li key={idx} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-brand/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-semibold text-brand">{idx + 1}</span>
                    </div>
                    <span className="text-sm text-muted flex-1">{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!executiveSummary && keyFindings.length === 0 && anomalies.length === 0 && recommendations.length === 0 && (
        <div className="bg-surface p-8 rounded-lg text-center text-muted border border-border">
          <LightBulbIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No insights available for this query</p>
        </div>
      )}
    </div>
  );
}

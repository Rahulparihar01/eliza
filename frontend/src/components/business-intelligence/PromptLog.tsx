/**
 * Prompt Log Component
 * Displays the history of enriched prompts from the Task Enrichment Flow
 */

import React, { useState } from 'react';
import {
  SparklesIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import {
  useListPromptsV1BiPromptsGet,
} from '../../generated/business-intelligence/business-intelligence';
import { queryKeys } from '../../lib/query-keys';

export default function PromptLog() {
  const [expandedPromptId, setExpandedPromptId] = useState<string | null>(null);
  const [pageSize] = useState(20);

  // Fetch enriched prompts
  const { data: promptsData, isLoading } = useListPromptsV1BiPromptsGet(
    { page: 1, page_size: pageSize },
    {
      query: {
        queryKey: queryKeys.businessIntelligence.prompts(),
        staleTime: 30000, // 30 seconds
      },
    }
  );

  const prompts = promptsData?.prompts || [];

  const toggleExpand = (promptId: string) => {
    setExpandedPromptId(expandedPromptId === promptId ? null : promptId);
  };

  if (isLoading) {
    return (
      <div className="bg-surface border border-border rounded-lg p-6">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
          <p className="text-muted mt-4">Loading enriched prompts...</p>
        </div>
      </div>
    );
  }

  if (prompts.length === 0) {
    return (
      <div className="bg-surface border border-border rounded-lg p-12 text-center">
        <SparklesIcon className="w-12 h-12 text-muted mx-auto mb-4" />
        <p className="text-muted">No enriched prompts yet. Submit a question to see how it's enriched!</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {prompts.map((prompt) => {
        const isExpanded = expandedPromptId === prompt.prompt_id;

        return (
          <div
            key={prompt.prompt_id}
            className="bg-surface border border-border rounded-lg overflow-hidden"
          >
            {/* Header */}
            <button
              onClick={() => toggleExpand(prompt.prompt_id)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-bg transition-colors duration-fast"
            >
              <div className="flex items-center space-x-3 flex-1 text-left">
                <SparklesIcon className="w-5 h-5 text-brand flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-text font-medium truncate">{prompt.original_input}</p>
                  <div className="flex items-center space-x-4 mt-1 text-sm text-muted">
                    <span className="flex items-center space-x-1">
                      <ClockIcon className="w-4 h-4" />
                      <span>{new Date(prompt.created_at).toLocaleString()}</span>
                    </span>
                    {prompt.intent_type && (
                      <span className="px-2 py-0.5 bg-brand-soft text-brand rounded text-xs font-medium">
                        {prompt.intent_type}
                      </span>
                    )}
                    {prompt.complexity && (
                      <span className="px-2 py-0.5 bg-bg border border-border rounded text-xs">
                        {prompt.complexity}
                      </span>
                    )}
                    {prompt.quality_score !== undefined && prompt.quality_score !== null && (
                      <span className="text-xs">
                        Quality: {(prompt.quality_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>
              {isExpanded ? (
                <ChevronUpIcon className="w-5 h-5 text-muted flex-shrink-0 ml-4" />
              ) : (
                <ChevronDownIcon className="w-5 h-5 text-muted flex-shrink-0 ml-4" />
              )}
            </button>

            {/* Expanded Content */}
            {isExpanded && (
              <div className="px-6 pb-6 space-y-4 border-t border-border">
                {/* Original Input */}
                <div className="pt-4">
                  <h4 className="text-sm font-semibold text-text mb-2">Original Question</h4>
                  <div className="p-3 bg-bg border border-border rounded-lg">
                    <p className="text-text text-sm">{prompt.original_input}</p>
                  </div>
                </div>

                {/* Enriched Prompt */}
                <div>
                  <h4 className="text-sm font-semibold text-text mb-2">Enriched Prompt</h4>
                  <div className="p-3 bg-brand-soft border border-brand rounded-lg">
                    <p className="text-text text-sm whitespace-pre-wrap">{prompt.enriched_prompt}</p>
                  </div>
                </div>

                {/* Metadata Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Intent & Complexity */}
                  <div>
                    <h4 className="text-sm font-semibold text-text mb-2">Classification</h4>
                    <div className="space-y-2">
                      {prompt.intent_type && (
                        <div className="flex items-center justify-between p-2 bg-bg border border-border rounded">
                          <span className="text-sm text-muted">Intent Type</span>
                          <span className="text-sm text-text font-medium">{prompt.intent_type}</span>
                        </div>
                      )}
                      {prompt.complexity && (
                        <div className="flex items-center justify-between p-2 bg-bg border border-border rounded">
                          <span className="text-sm text-muted">Complexity</span>
                          <span className="text-sm text-text font-medium">{prompt.complexity}</span>
                        </div>
                      )}
                      {prompt.confidence_score !== undefined && prompt.confidence_score !== null && (
                        <div className="flex items-center justify-between p-2 bg-bg border border-border rounded">
                          <span className="text-sm text-muted">Confidence</span>
                          <span className="text-sm text-text font-medium">
                            {(prompt.confidence_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Quality Score */}
                  {prompt.quality_score !== undefined && prompt.quality_score !== null && (
                    <div>
                      <h4 className="text-sm font-semibold text-text mb-2">Quality Score</h4>
                      <div className="p-3 bg-bg border border-border rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-muted">Overall Quality</span>
                          <span className="text-sm font-bold text-brand">
                            {(prompt.quality_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="w-full bg-border rounded-full h-2">
                          <div
                            className="bg-brand h-2 rounded-full transition-all duration-300 w-var"
                            style={{ ['--w' as any]: `${prompt.quality_score * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>


              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

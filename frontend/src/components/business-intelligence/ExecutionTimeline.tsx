/**
 * Execution Timeline Component
 * 
 * Displays a comprehensive, elegant timeline of agent execution including:
 * - Enriched prompts
 * - Tool executions with inputs/outputs
 * - Agent responses and reasoning
 * - Telemetry events
 */

import React, { useState } from 'react';
import {
  SparklesIcon,
  WrenchScrewdriverIcon,
  BeakerIcon,
  CheckCircleIcon,
  XCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClockIcon,
  DocumentTextIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { formatDistanceToNow } from 'date-fns';

interface ToolExecution {
  execution_id: string;
  tool_name: string;
  agent_name: string | null;
  tool_input: any;
  tool_output: any;
  status: string;
  error_message: string | null;
  duration_ms: number | null;
  results_count: number | null;
  started_at: string;
  completed_at: string | null;
}

interface AgentResponse {
  response_id: string;
  agent_name: string;
  stage_name: string | null;
  input_prompt: string | null;
  response_text: string;
  reasoning: string | null;
  tool_calls: any[] | null;
  confidence_score: number | null;
  duration_ms: number | null;
  created_at: string;
}

interface EnrichedPrompt {
  prompt_id: string;
  original_input: string;
  enriched_prompt: string;
  intent_type: string | null;
  complexity: string | null;
  confidence_score: number | null;
  quality_score: number | null;
  created_at: string;
}

interface TimelineData {
  question_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  enriched_prompt: EnrichedPrompt | null;
  tool_executions: ToolExecution[];
  agent_responses: AgentResponse[];
  telemetry_events: any[];
}

interface ExecutionTimelineProps {
  data: TimelineData;
}

export default function ExecutionTimeline({ data }: ExecutionTimelineProps) {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set(['enriched_prompt']));

  const toggleItem = (id: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedItems(newExpanded);
  };

  // Build chronological timeline
  const timelineItems: any[] = [];

  // Add enriched prompt
  if (data.enriched_prompt) {
    timelineItems.push({
      type: 'enriched_prompt',
      id: data.enriched_prompt.prompt_id,
      timestamp: data.enriched_prompt.created_at,
      data: data.enriched_prompt,
    });
  }

  // Add agent responses
  data.agent_responses.forEach((response) => {
    timelineItems.push({
      type: 'agent_response',
      id: response.response_id,
      timestamp: response.created_at,
      data: response,
    });
  });

  // Add tool executions
  data.tool_executions.forEach((execution) => {
    timelineItems.push({
      type: 'tool_execution',
      id: execution.execution_id,
      timestamp: execution.started_at,
      data: execution,
    });
  });

  // Sort by timestamp
  timelineItems.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <ClockIcon className="w-4 h-4 text-brand" />
          Execution Timeline
        </h3>
        <span className="text-xs text-muted">
          {timelineItems.length} events
        </span>
      </div>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-border" />

        {/* Timeline items */}
        <div className="space-y-4">
          {timelineItems.map((item, index) => (
            <TimelineItem
              key={item.id}
              item={item}
              isExpanded={expandedItems.has(item.id)}
              onToggle={() => toggleItem(item.id)}
              isLast={index === timelineItems.length - 1}
            />
          ))}
        </div>
      </div>

      {timelineItems.length === 0 && (
        <div className="text-center py-8 text-muted text-sm">
          No execution details available yet
        </div>
      )}
    </div>
  );
}

interface TimelineItemProps {
  item: any;
  isExpanded: boolean;
  onToggle: () => void;
  isLast: boolean;
}

function TimelineItem({ item, isExpanded, onToggle, isLast }: TimelineItemProps) {
  const renderIcon = () => {
    switch (item.type) {
      case 'enriched_prompt':
        return <SparklesIcon className="w-5 h-5 text-brand" />;
      case 'tool_execution':
        return <WrenchScrewdriverIcon className="w-5 h-5 text-purple-500" />;
      case 'agent_response':
        return <BeakerIcon className="w-5 h-5 text-blue-500" />;
      default:
        return <CpuChipIcon className="w-5 h-5 text-muted" />;
    }
  };

  const renderTitle = () => {
    switch (item.type) {
      case 'enriched_prompt':
        return 'Task Enrichment';
      case 'tool_execution':
        return item.data.tool_name || 'Tool Execution';
      case 'agent_response':
        return `${item.data.agent_name} Response`;
      default:
        return 'Event';
    }
  };

  const renderSubtitle = () => {
    switch (item.type) {
      case 'enriched_prompt':
        return `Intent: ${item.data.intent_type || 'unknown'} • Complexity: ${item.data.complexity || 'unknown'}`;
      case 'tool_execution':
        return item.data.status === 'success'
          ? `${item.data.results_count || 0} results • ${item.data.duration_ms || 0}ms`
          : `Failed • ${item.data.duration_ms || 0}ms`;
      case 'agent_response':
        return `Stage: ${item.data.stage_name || 'unknown'} • ${item.data.duration_ms || 0}ms`;
      default:
        return '';
    }
  };

  return (
    <div className="relative">
      {/* Timeline dot */}
      <div className="absolute left-3.5 top-2 w-5 h-5 rounded-full bg-surface border-2 border-border flex items-center justify-center z-10">
        <div className="w-2 h-2 rounded-full bg-brand" />
      </div>

      {/* Content */}
      <div className="ml-14">
        <button
          onClick={onToggle}
          className="w-full text-left p-3 bg-surface border border-border rounded-lg hover:border-brand-soft hover:bg-brand-soft/10 transition-all duration-fast"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="mt-0.5">{renderIcon()}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold text-text truncate">{renderTitle()}</h4>
                  {item.type === 'tool_execution' && item.data.status === 'success' && (
                    <CheckCircleIcon className="w-4 h-4 text-success flex-shrink-0" />
                  )}
                  {item.type === 'tool_execution' && item.data.status === 'failed' && (
                    <XCircleIcon className="w-4 h-4 text-error flex-shrink-0" />
                  )}
                </div>
                <p className="text-xs text-muted mt-1">{renderSubtitle()}</p>
                <p className="text-xs text-muted mt-1">
                  {formatDistanceToNow(new Date(item.timestamp), { addSuffix: true })}
                </p>
              </div>
            </div>
            {isExpanded ? (
              <ChevronDownIcon className="w-5 h-5 text-muted flex-shrink-0" />
            ) : (
              <ChevronRightIcon className="w-5 h-5 text-muted flex-shrink-0" />
            )}
          </div>
        </button>

        {isExpanded && (
          <div className="mt-2 p-4 bg-bg border border-border rounded-lg">
            {item.type === 'enriched_prompt' && <EnrichedPromptDetails data={item.data} />}
            {item.type === 'tool_execution' && <ToolExecutionDetails data={item.data} />}
            {item.type === 'agent_response' && <AgentResponseDetails data={item.data} />}
          </div>
        )}
      </div>
    </div>
  );
}

function EnrichedPromptDetails({ data }: { data: EnrichedPrompt }) {
  return (
    <div className="space-y-3">
      <div>
        <h5 className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Original Question</h5>
        <p className="text-sm text-text">{data.original_input}</p>
      </div>
      <div>
        <h5 className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Enriched Prompt</h5>
        <div className="p-3 bg-brand-soft border border-brand rounded text-sm text-text whitespace-pre-wrap">
          {data.enriched_prompt}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {data.intent_type && (
          <span className="px-2 py-1 bg-surface-2 border border-border rounded text-xs">
            Intent: {data.intent_type}
          </span>
        )}
        {data.complexity && (
          <span className="px-2 py-1 bg-surface-2 border border-border rounded text-xs">
            Complexity: {data.complexity}
          </span>
        )}
        {data.quality_score !== null && (
          <span className="px-2 py-1 bg-surface-2 border border-border rounded text-xs">
            Quality: {(data.quality_score * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}

function ToolExecutionDetails({ data }: { data: ToolExecution }) {
  const [showInput, setShowInput] = useState(true);
  const [showOutput, setShowOutput] = useState(true);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded text-xs font-semibold">
            {data.tool_name}
          </span>
          {data.agent_name && (
            <span className="text-xs text-muted">by {data.agent_name}</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          {data.status === 'success' && (
            <span className="flex items-center gap-1 text-success">
              <CheckCircleIcon className="w-4 h-4" />
              Success
            </span>
          )}
          {data.status === 'failed' && (
            <span className="flex items-center gap-1 text-error">
              <XCircleIcon className="w-4 h-4" />
              Failed
            </span>
          )}
        </div>
      </div>

      {data.error_message && (
        <div className="p-2 bg-error-soft border border-error rounded text-xs text-error">
          {data.error_message}
        </div>
      )}

      {/* Tool Input */}
      <div>
        <button
          onClick={() => setShowInput(!showInput)}
          className="flex items-center gap-1 text-xs font-semibold text-muted uppercase tracking-wide hover:text-text mb-1"
        >
          {showInput ? <ChevronDownIcon className="w-3 h-3" /> : <ChevronRightIcon className="w-3 h-3" />}
          Tool Input
        </button>
        {showInput && data.tool_input && (
          <pre className="p-2 bg-surface-2 border border-border rounded text-xs overflow-x-auto">
            {JSON.stringify(data.tool_input, null, 2)}
          </pre>
        )}
      </div>

      {/* Tool Output */}
      {data.status === 'success' && data.tool_output && (
        <div>
          <button
            onClick={() => setShowOutput(!showOutput)}
            className="flex items-center gap-1 text-xs font-semibold text-muted uppercase tracking-wide hover:text-text mb-1"
          >
            {showOutput ? <ChevronDownIcon className="w-3 h-3" /> : <ChevronRightIcon className="w-3 h-3" />}
            Tool Output {data.results_count !== null && `(${data.results_count} results)`}
          </button>
          {showOutput && (
            <pre className="p-2 bg-surface-2 border border-border rounded text-xs overflow-x-auto max-h-96">
              {JSON.stringify(data.tool_output, null, 2)}
            </pre>
          )}
        </div>
      )}

      {/* Metadata */}
      <div className="flex flex-wrap gap-2 text-xs">
        {data.duration_ms !== null && (
          <span className="px-2 py-1 bg-surface-2 border border-border rounded">
            Duration: {data.duration_ms}ms
          </span>
        )}
        {data.results_count !== null && (
          <span className="px-2 py-1 bg-surface-2 border border-border rounded">
            Results: {data.results_count}
          </span>
        )}
      </div>
    </div>
  );
}

function AgentResponseDetails({ data }: { data: AgentResponse }) {
  const [showInput, setShowInput] = useState(false);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded text-xs font-semibold">
            {data.agent_name}
          </span>
          {data.stage_name && (
            <span className="text-xs text-muted">Stage: {data.stage_name}</span>
          )}
        </div>
        {data.confidence_score !== null && (
          <span className="text-xs text-muted">
            Confidence: {(data.confidence_score * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {data.reasoning && (
        <div>
          <h5 className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Reasoning</h5>
          <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-text">
            {data.reasoning}
          </div>
        </div>
      )}

      <div>
        <h5 className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Response</h5>
        <div className="p-3 bg-surface-2 border border-border rounded text-sm text-text whitespace-pre-wrap max-h-96 overflow-y-auto">
          {data.response_text}
        </div>
      </div>

      {data.tool_calls && data.tool_calls.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Tools Used</h5>
          <div className="flex flex-wrap gap-2">
            {data.tool_calls.map((tool, index) => (
              <span key={index} className="px-2 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded text-xs">
                {tool.tool_name}
                {tool.results_count !== undefined && ` (${tool.results_count})`}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.input_prompt && (
        <div>
          <button
            onClick={() => setShowInput(!showInput)}
            className="flex items-center gap-1 text-xs font-semibold text-muted uppercase tracking-wide hover:text-text mb-1"
          >
            {showInput ? <ChevronDownIcon className="w-3 h-3" /> : <ChevronRightIcon className="w-3 h-3" />}
            Input Prompt
          </button>
          {showInput && (
            <pre className="p-2 bg-surface-2 border border-border rounded text-xs overflow-x-auto max-h-48">
              {data.input_prompt}
            </pre>
          )}
        </div>
      )}

      {data.duration_ms !== null && (
        <div className="text-xs text-muted">
          Execution time: {data.duration_ms}ms
        </div>
      )}
    </div>
  );
}


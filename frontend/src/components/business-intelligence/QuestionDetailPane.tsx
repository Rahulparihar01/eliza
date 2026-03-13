import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  SparklesIcon,
  ClockIcon,
  WrenchScrewdriverIcon,
  BeakerIcon,
} from '@heroicons/react/24/outline';
import { QuestionStatus } from '../../generated/models/questionStatus';
import { Tooltip } from '../common/Tooltip';
import {
  formatQuestionDateTime,
  getQuestionStatusBadgeClasses,
  getQuestionStatusText,
} from './questionUtils';

interface ProcessingSummary {
  status: QuestionStatus;
  currentStage?: string;
  startedAt?: string;
  completedAt?: string | null;
  errorMessage?: string | null;
}

export interface QuestionDetailPaneProps {
  question: any;
  processingSummary: ProcessingSummary;
  prompts: any[];
  result: any;
  questionId: string;
  timelineData: any;
  timelineLoading: boolean;
  onOpenTimeline: () => void;
}

export function QuestionDetailPane({
  question,
  processingSummary,
  prompts,
  result,
  questionId,
  timelineData,
  timelineLoading,
  onOpenTimeline,
}: QuestionDetailPaneProps) {
  const detailScrollRef = useRef<HTMLDivElement>(null);
  const detailInnerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sc = detailScrollRef.current;
    const inner = detailInnerRef.current;
    if (!sc || !inner) return;

    let touchStartY = 0;
    let animating = false;
    let lastBounce = 0;
    const COOLDOWN_MS = 900;
    const OUT_MS = 260;
    const BACK_MS = 420;

    const bounce = (amount: number) => {
      const now = Date.now();
      if (animating || now - lastBounce < COOLDOWN_MS) return;
      lastBounce = now;
      animating = true;
      inner.style.willChange = 'transform';
      inner.style.transition = `transform ${OUT_MS}ms cubic-bezier(0.15, 0.4, 0.1, 1)`;
      inner.style.transform = `translateY(${amount}px)`;
      setTimeout(() => {
        inner.style.transform = 'translateY(0)';
        inner.style.transition = `transform ${BACK_MS}ms cubic-bezier(0.15, 0.6, 0.1, 1)`;
        setTimeout(() => {
          inner.style.transition = '';
          inner.style.willChange = '';
          animating = false;
        }, BACK_MS + 20);
      }, OUT_MS);
    };

    const atExtents = (deltaY: number) => {
      const atTop = sc.scrollTop <= 0;
      const atBottom = sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 1;
      const noScroll = sc.scrollHeight <= sc.clientHeight + 1;
      return noScroll || (deltaY < 0 && atTop) || (deltaY > 0 && atBottom);
    };

    const onWheel = (e: WheelEvent) => {
      if (atExtents(e.deltaY)) {
        e.preventDefault();
        bounce(e.deltaY > 0 ? 12 : -12);
      }
    };

    const onTouchStart = (e: TouchEvent) => {
      touchStartY = e.touches[0]?.clientY || 0;
    };

    const onTouchMove = (e: TouchEvent) => {
      const currentY = e.touches[0]?.clientY || 0;
      const deltaY = touchStartY - currentY;
      if (atExtents(deltaY)) {
        e.preventDefault();
        bounce(deltaY > 0 ? 14 : -14);
      }
    };

    sc.addEventListener('wheel', onWheel, { passive: false });
    sc.addEventListener('touchstart', onTouchStart, { passive: true });
    sc.addEventListener('touchmove', onTouchMove, { passive: false });

    return () => {
      sc.removeEventListener('wheel', onWheel as any);
      sc.removeEventListener('touchstart', onTouchStart as any);
      sc.removeEventListener('touchmove', onTouchMove as any);
    };
  }, []);

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="px-5 py-4 bg-surface-2">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <p className="text-xs text-muted uppercase tracking-wide">Question</p>
            <h2 className="text-lg font-semibold text-text leading-snug break-words whitespace-pre-wrap">
              {question.original_question}
            </h2>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="px-2 py-1 rounded-md border border-border bg-surface-2/60">
                ID: <code className="text-[11px] font-mono">{questionId}</code>
              </span>
              {question.session_id && (
                <span className="px-2 py-1 rounded-md border border-border bg-surface-2/60">
                  Session: <code className="text-[11px] font-mono">{question.session_id}</code>
                </span>
              )}
            </div>
          </div>
          <div className={`ml-4 px-3 py-1.5 rounded-full text-xs font-semibold ${getQuestionStatusBadgeClasses(question.status)}`}>
            {getQuestionStatusText(question.status)}
          </div>
        </div>
      </div>

      <div ref={detailScrollRef} className="detail-scroll-container flex-1 min-h-0 overflow-y-scroll overscroll-y-auto scroll-slim ios-momentum">
        <div ref={detailInnerRef} className="always-scrollable pt-[2px] pb-[15vh]">
          <DetailSections
            questionId={questionId}
            processingSummary={processingSummary}
            enrichedPrompts={prompts}
            result={result}
            timelineData={timelineData}
            timelineLoading={timelineLoading}
            onOpenTimeline={onOpenTimeline}
          />
        </div>
      </div>
    </div>
  );
}

interface DetailSectionsProps {
  questionId: string;
  processingSummary: ProcessingSummary;
  enrichedPrompts: any[];
  result: any;
  timelineData: any;
  timelineLoading: boolean;
  onOpenTimeline: () => void;
}

function DetailSections({ questionId, processingSummary, enrichedPrompts, result, timelineData, timelineLoading, onOpenTimeline }: DetailSectionsProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    summary: true,
    timeline: true,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const summaryItems = useMemo(() => {
    if (!timelineData) return [] as any[];
    const items: any[] = [];
    if (timelineData.enriched_prompt) {
      items.push({
        type: 'enriched_prompt',
        id: timelineData.enriched_prompt.prompt_id,
        timestamp: timelineData.enriched_prompt.created_at,
        data: timelineData.enriched_prompt,
      });
    }
    (timelineData.agent_responses || []).forEach((response: any) => {
      items.push({ type: 'agent_response', id: response.response_id, timestamp: response.created_at, data: response });
    });
    (timelineData.tool_executions || []).forEach((execution: any) => {
      items.push({ type: 'tool_execution', id: execution.execution_id, timestamp: execution.started_at, data: execution });
    });
    items.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    return items;
  }, [timelineData]);

  const visibleItems = summaryItems;

  return (
    <div className="space-y-3 px-3 py-3">
      <Section
        title="Processing Summary"
        description="Current status, key timestamps, and diagnostic information"
        expanded={expandedSections.summary}
        onToggle={() => toggleSection('summary')}
      >
        <div className="space-y-3 text-sm text-text">
          <InfoRow label="Status" value={getQuestionStatusText(processingSummary.status)} />
          <InfoRow label="Stage" value={processingSummary.currentStage ?? '—'} />
          <InfoRow label="Started" value={formatQuestionDateTime(processingSummary.startedAt)} />
          <InfoRow label="Completed" value={formatQuestionDateTime(processingSummary.completedAt)} />
          {processingSummary.errorMessage && (
            <div className="rounded-md border border-error bg-error-soft p-3">
              <p className="text-xs font-semibold text-error uppercase tracking-wide mb-1">Error</p>
              <p className="text-sm text-error leading-relaxed">{processingSummary.errorMessage}</p>
            </div>
          )}
        </div>
      </Section>

      <Section
        title="Agent Execution Timeline"
        expanded={expandedSections.timeline}
        onToggle={onOpenTimeline}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">
            {timelineLoading ? 'Loading…' : summaryItems.length ? `${summaryItems.length} events` : 'No timeline yet'}
          </span>
          <button
            onClick={onOpenTimeline}
            className="px-3 py-1.5 bg-brand text-on-brand rounded text-xs font-semibold hover:bg-brand/90"
          >
            View Timeline Details
          </button>
        </div>

        <div className="h-2" />

        {timelineLoading ? (
          <div className="text-xs text-muted py-2">Fetching latest events…</div>
        ) : !timelineData || visibleItems.length === 0 ? (
          <div className="text-xs text-muted py-2">No execution details available yet.</div>
        ) : (
          <div className="space-y-2">
            {visibleItems.map((item: any) => {
              const renderIcon = () => {
                switch (item.type) {
                  case 'enriched_prompt':
                    return <SparklesIcon className="w-4 h-4 text-brand" />;
                  case 'tool_execution':
                    return <WrenchScrewdriverIcon className="w-4 h-4 text-purple-500" />;
                  case 'agent_response':
                    return <BeakerIcon className="w-4 h-4 text-blue-500" />;
                  default:
                    return <ClockIcon className="w-4 h-4 text-muted" />;
                }
              };

              const title =
                item.type === 'enriched_prompt'
                  ? 'Task Enrichment'
                  : item.type === 'tool_execution'
                  ? item.data.tool_name || 'Tool Execution'
                  : `${item.data.agent_name} Response`;

              const subtitle =
                item.type === 'enriched_prompt'
                  ? `Intent: ${item.data.intent_type || 'unknown'}`
                  : item.type === 'tool_execution'
                  ? item.data.status === 'success'
                    ? `${item.data.results_count || 0} results`
                    : 'Failed'
                  : item.data.stage_name
                  ? `Stage: ${item.data.stage_name}`
                  : 'Agent step';

              return (
                <Tooltip key={`${item.type}:${item.id}`} content="Open timeline details" className="block w-full">
                  <button
                    onClick={onOpenTimeline}
                    className="w-full text-left p-2 bg-surface border border-border rounded hover:border-brand-soft hover:bg-brand-soft/10 transition-colors duration-fast"
                  >
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5">{renderIcon()}</div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-text truncate">{title}</div>
                        <div className="text-xs text-muted truncate">{subtitle}</div>
                      </div>
                      <div className="text-[11px] text-muted whitespace-nowrap ml-2">
                        {new Date(item.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </button>
                </Tooltip>
              );
            })}
          </div>
        )}
      </Section>

      <Section
        title="Enriched Prompts"
        expanded={enrichedPrompts.length > 0}
        onToggle={() => toggleSection('summary')}
      >
        {enrichedPrompts.length === 0 ? (
          <div className="text-xs text-muted">No enriched prompt details available.</div>
        ) : (
          <div className="space-y-2 text-sm text-text">
            {enrichedPrompts.map((prompt) => (
              <div key={prompt.prompt_id} className="border border-border rounded-md p-3 bg-surface">
                <p className="text-xs uppercase text-muted tracking-wide mb-1">Prompt</p>
                <p className="whitespace-pre-wrap leading-relaxed">{prompt.enriched_prompt}</p>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Analysis Result"
        expanded={Boolean(result)}
        onToggle={() => toggleSection('summary')}
      >
        {result ? (
          <div className="space-y-3 text-sm text-text">
            {result.executive_summary && (
              <div className="p-3 bg-brand-soft border border-brand rounded">
                <p className="text-xs font-semibold text-brand uppercase tracking-wide mb-1">Executive Summary</p>
                <p className="leading-relaxed whitespace-pre-wrap">{result.executive_summary}</p>
              </div>
            )}
            {result.analysis_text && (
              <div className="p-3 bg-surface-2 border border-border rounded whitespace-pre-wrap">
                {result.analysis_text}
              </div>
            )}
            {result.key_findings && Array.isArray(result.key_findings) && result.key_findings.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">Key Findings</p>
                <ul className="space-y-2 list-disc list-inside">
                  {result.key_findings.map((finding: any, index: number) => (
                    <li key={index} className="text-sm text-text">
                      {typeof finding === 'string' ? finding : JSON.stringify(finding)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-muted">No analysis available yet.</div>
        )}
      </Section>
    </div>
  );
}

interface SectionProps {
  title: string;
  description?: string;
  children: ReactNode;
  expanded: boolean;
  onToggle: () => void;
}

function Section({ title, description, children, expanded, onToggle }: SectionProps) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-3 bg-transparent hover:bg-surface transition-colors duration-fast"
      >
        <div className="text-left">
          <p className="text-sm font-semibold text-text">{title}</p>
          {description && <p className="text-xs text-muted mt-1">{description}</p>}
        </div>
        <span className="text-xs text-muted">{expanded ? 'Hide' : 'Show'}</span>
      </button>
      {expanded && <div className="px-3 pt-0 pb-3">{children}</div>}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1 border-b border-border pb-2 last:border-transparent last:pb-0">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</span>
      <span className="text-sm text-text sm:text-right break-words whitespace-pre-wrap">{value}</span>
    </div>
  );
}

export default QuestionDetailPane;

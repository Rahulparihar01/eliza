/**
 * Business Intelligence Q&A Page
 * Main interface for asking questions about business data
 * Uses CrewAI flows for task enrichment and data analysis
 */

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Layout } from '../../components/layout/Layout';
import { Tooltip } from '../../components/common/Tooltip';
import { ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline';
import QuestionListHeader from '../../components/business-intelligence/QuestionListHeader';
import QuestionList from '../../components/business-intelligence/QuestionList';
import QuestionDetailPane from '../../components/business-intelligence/QuestionDetailPane';
import QuestionInput from '../../components/business-intelligence/QuestionInput';
import {
  useListQuestionsV1BiQuestionsGet,
  useGetQuestionV1BiQuestionsQuestionIdGet,
  useGetAnalysisResultV1BiQuestionsQuestionIdResultGet,
  useListPromptsV1BiPromptsGet,
} from '../../generated/business-intelligence/business-intelligence';
import { QuestionStatus } from '../../generated/models/questionStatus';
import ExecutionTimeline from '../../components/business-intelligence/ExecutionTimeline';
import CompanySelector from '../../components/business-intelligence/CompanySelector';
import { queryKeys } from '../../lib/query-keys';
import { AXIOS_INSTANCE } from '../../services/api-client';


export default function BusinessIntelligenceQA() {
  const location = useLocation();
  const isPreviewMode = location.pathname === '/business-intelligence/history-preview';
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const [detailPaneWidth, setDetailPaneWidth] = useState(360);
  const [isDraggingCenter, setIsDraggingCenter] = useState(false);
  const splitRef = useRef<HTMLDivElement>(null);
  const detailPaneRef = useRef<HTMLDivElement>(null);

  // Fetch recent questions
  const { data: questionsData, isLoading: questionsLoading } = useListQuestionsV1BiQuestionsGet(
    { page: 1, page_size: 10 },
    {
      query: {
        queryKey: queryKeys.businessIntelligence.questions(),
        staleTime: 10000, // 10 seconds
        refetchInterval: 5000, // Refetch every 5 seconds for status updates
      },
    }
  );

  const recentQuestions = questionsData?.questions || [];

  const selectedQuestionQuery = useGetQuestionV1BiQuestionsQuestionIdGet(selectedQuestionId ?? '', {
    query: {
      enabled: !!selectedQuestionId,
      refetchInterval: 3000,
    },
  });

  const selectedQuestion = selectedQuestionQuery.data;

  const resultQuery = useGetAnalysisResultV1BiQuestionsQuestionIdResultGet(selectedQuestionId ?? '', {
    query: {
      enabled: !!selectedQuestionId && selectedQuestion?.status === QuestionStatus.completed,
    },
  });

  const { data: promptsData } = useListPromptsV1BiPromptsGet(
    { page: 1, page_size: 20 },
    { query: { enabled: !!selectedQuestionId } }
  );

  // Fetch execution timeline for selected question
  const [timelineData, setTimelineData] = React.useState<any>(null);
  const [timelineLoading, setTimelineLoading] = React.useState(false);
  const [timelineOpen, setTimelineOpen] = React.useState(false);
  const timelineScrollRef = useRef<HTMLDivElement>(null);
  const timelineInnerRef = useRef<HTMLDivElement>(null);

  // Single-bounce tactile feedback helper
  const useBounce = (scrollRef: React.RefObject<HTMLDivElement>, innerRef: React.RefObject<HTMLDivElement>) => {
    useEffect(() => {
      const sc = scrollRef.current;
      const inner = innerRef.current;
      if (!sc || !inner) return;

      let touchStartY = 0;
      let animating = false;
      let lastBounce = 0; const COOLDOWN_MS = 900; const OUT_MS = 260; const BACK_MS = 420;

      const bounce = (amount: number) => {
        const now = Date.now();
        if (animating || now - lastBounce < COOLDOWN_MS) return; // throttle to a single slow bounce
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
    }, [scrollRef, innerRef]);
  };

  // Apply single-bounce to timeline pane
  useBounce(timelineScrollRef, timelineInnerRef);
  const MIN_LIST_WIDTH = 240;
  const MAX_LIST_WIDTH = 780;
  const MIN_DETAIL_WIDTH = 120;
  const MIN_TIMELINE_WIDTH = 260;
  const MAX_TIMELINE_WIDTH = 640;

  const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

  const [listWidth, setListWidth] = React.useState(420);
  const [timelineWidth, setTimelineWidth] = React.useState(320);
  const [isDraggingRight, setIsDraggingRight] = React.useState(false);
  const rightDragStateRef = useRef({
    startX: 0,
    startTimelineWidth: 0,
    startListWidth: 0,
    startDetailWidth: 0,
  });

  React.useEffect(() => {
    if (!selectedQuestionId) {
      setTimelineData(null);
      return;
    }

    const fetchTimeline = async () => {
      setTimelineLoading(true);
      try {
        const response = await AXIOS_INSTANCE.get(`/v1/bi/questions/${selectedQuestionId}/timeline`);
        setTimelineData(response.data);
      } catch (error: any) {
        if (error?.response) {
          console.error(`Failed to fetch timeline (${error.response.status}):`, error.response.data);
          if (error.response.status === 401) {
            console.error('Authentication failed. Token present:', !!localStorage.getItem('auth_token'));
          }
        } else {
          console.error('Failed to fetch timeline:', error);
        }
      } finally {
        setTimelineLoading(false);
      }
    };

    fetchTimeline();
    // Refetch timeline every 5 seconds if question is not completed
    const interval = setInterval(() => {
      if (selectedQuestion?.status !== QuestionStatus.completed && selectedQuestion?.status !== QuestionStatus.failed) {
        fetchTimeline();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [selectedQuestionId, selectedQuestion?.status]);

  const enrichedPromptsForQuestion = useMemo(() => {
    const sessionId = selectedQuestion?.session_id ?? undefined;
    if (!selectedQuestionId || !sessionId) return [];
    const prompts = promptsData?.prompts || [];
    return prompts.filter((prompt) => prompt.prompt_id.includes(String(sessionId)));
  }, [promptsData, selectedQuestionId, selectedQuestion?.session_id]);


  useEffect(() => {
    if (!selectedQuestionId && recentQuestions.length > 0) {
      setSelectedQuestionId(recentQuestions[0].question_id);
    }
  }, [recentQuestions, selectedQuestionId]);

  useLayoutEffect(() => {
    if (isDraggingCenter || isDraggingRight) return;
    const container = splitRef.current;
    if (!container) return;
    const reservedTimeline = timelineOpen ? timelineWidth : 0;
    const available = container.getBoundingClientRect().width - reservedTimeline - MIN_DETAIL_WIDTH;
    if (listWidth > available) {
      setListWidth(clamp(available, MIN_LIST_WIDTH, MAX_LIST_WIDTH));
    }
    const detailNode = detailPaneRef.current;
    if (detailNode) {
      setDetailPaneWidth(detailNode.getBoundingClientRect().width);
    }
  }, [timelineOpen, timelineWidth, listWidth, isDraggingCenter, isDraggingRight]);

  useEffect(() => {
    if (!isDraggingCenter) return;
    const handleMouseMove = (event: MouseEvent) => {
      const rect = splitRef.current?.getBoundingClientRect();
      if (!rect) return;
      const reservedTimeline = timelineOpen ? timelineWidth : 0;
      const maxLeft = rect.width - (MIN_DETAIL_WIDTH + reservedTimeline);
      const proposed = event.clientX - rect.left;
      const clampedLeft = clamp(proposed, MIN_LIST_WIDTH, Math.max(MIN_LIST_WIDTH, maxLeft));
      setListWidth(clampedLeft);
    };
    const handleMouseUp = () => setIsDraggingCenter(false);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingCenter, timelineOpen, timelineWidth]);

  useEffect(() => {
    const detailNode = detailPaneRef.current;
    if (!detailNode) return;
    const rect = detailNode.getBoundingClientRect();
    setDetailPaneWidth(rect.width);
  }, [listWidth, timelineWidth, timelineOpen]);

  useEffect(() => {
    if (!isDraggingRight) return;
    const handleMouseMove = (event: MouseEvent) => {
      const container = splitRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const totalWidth = rect.width;
      if (totalWidth <= 0) return;

      const { startX, startTimelineWidth, startListWidth, startDetailWidth } = rightDragStateRef.current;
      const delta = startX - event.clientX;
      const increasingTimeline = delta >= 0;

      const maxTimelineForLayout = Math.max(MIN_TIMELINE_WIDTH, totalWidth - MIN_LIST_WIDTH - MIN_DETAIL_WIDTH);
      let nextTimeline = startTimelineWidth + delta;
      let nextList = startListWidth;

      if (increasingTimeline) {
        const detailTarget = Math.max(startDetailWidth, MIN_DETAIL_WIDTH);
        const allowedTimelineMax = Math.min(
          MAX_TIMELINE_WIDTH,
          Math.max(MIN_TIMELINE_WIDTH, totalWidth - detailTarget - MIN_LIST_WIDTH)
        );
        nextTimeline = clamp(nextTimeline, MIN_TIMELINE_WIDTH, allowedTimelineMax);
        nextList = clamp(totalWidth - detailTarget - nextTimeline, MIN_LIST_WIDTH, MAX_LIST_WIDTH);
      } else {
        const allowedTimelineMax = Math.min(MAX_TIMELINE_WIDTH, maxTimelineForLayout);
        nextTimeline = clamp(nextTimeline, MIN_TIMELINE_WIDTH, allowedTimelineMax);
        nextList = clamp(startListWidth, MIN_LIST_WIDTH, MAX_LIST_WIDTH);
      }

      let detailWidth = totalWidth - nextTimeline - nextList;
      if (detailWidth < MIN_DETAIL_WIDTH) {
        const deficit = MIN_DETAIL_WIDTH - detailWidth;
        const reducibleList = nextList - MIN_LIST_WIDTH;
        if (reducibleList > 0) {
          const reduceBy = Math.min(deficit, reducibleList);
          nextList -= reduceBy;
          detailWidth += reduceBy;
        }
        if (detailWidth < MIN_DETAIL_WIDTH) {
          const reducibleTimeline = nextTimeline - MIN_TIMELINE_WIDTH;
          if (reducibleTimeline > 0) {
            const reduceBy = Math.min(MIN_DETAIL_WIDTH - detailWidth, reducibleTimeline);
            nextTimeline -= reduceBy;
            detailWidth += reduceBy;
          }
        }
      }

      setTimelineWidth(nextTimeline);
      setListWidth(nextList);
      setDetailPaneWidth(detailWidth);
    };
    const handleMouseUp = () => setIsDraggingRight(false);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingRight]);

  const processingSummary = useMemo(() => ({
    status: selectedQuestion?.status ?? QuestionStatus.pending,
    currentStage: selectedQuestion?.analysis_session?.status,
    startedAt: selectedQuestion?.created_at,
    completedAt: selectedQuestion?.completed_at,
    errorMessage: selectedQuestion?.error_message,
  }), [selectedQuestion]);

  const handleCenterDragStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDraggingCenter(true);
  };

  // legacy no-op handlers removed for center divider

  const handleRightDragStart = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    const container = splitRef.current;
    const detailNode = detailPaneRef.current;
    const containerWidth = container?.getBoundingClientRect().width ?? 0;
    const measuredDetailWidth =
      detailNode?.getBoundingClientRect().width ??
      (containerWidth > 0 ? Math.max(containerWidth - listWidth - timelineWidth, MIN_DETAIL_WIDTH) : detailPaneWidth);

    rightDragStateRef.current = {
      startX: event.clientX,
      startTimelineWidth: timelineWidth,
      startListWidth: listWidth,
      startDetailWidth: measuredDetailWidth,
    };
    setDetailPaneWidth(measuredDetailWidth);
    setIsDraggingRight(true);
  };

  return (
    <Layout sidebarCollapsedOverride={timelineOpen}>
      <div className="h-full flex flex-col px-0 overflow-x-hidden">
        {/* Slim Header Bar */}
        <div className="relative z-10 flex items-center justify-between h-10 px-3 bg-surface-2 border-b border-border">
          <div className="flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="w-5 h-5 text-brand" />
            <h1 className="text-sm font-semibold text-text">Business Intelligence Q&A</h1>
            <Tooltip position="top-right" className="z-50" content="Ask questions about your business data and get AI-powered insights">
              <span className="text-muted cursor-help">ⓘ</span>
            </Tooltip>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAskOpen((v) => !v)}
              className={`px-3 py-1 rounded-md text-sm transition-colors ${askOpen ? 'bg-brand text-on-brand' : 'bg-surface-2 text-text hover:bg-surface'}`}
              aria-expanded={askOpen}
            >
              {askOpen ? 'Hide Ask' : 'Ask a Question'}
            </button>
          </div>
        </div>

        {/* Ask Panel */}
        {askOpen && (
          <div className="mt-2 space-y-2">
            <div className="rounded-lg bg-surface shadow-1 p-3">
              <CompanySelector value={selectedCompany} onChange={setSelectedCompany} showDefault={true} />
            </div>
            <QuestionInput onQuestionSubmitted={(id)=>{ setSelectedQuestionId(id); setAskOpen(false); }} companyHrDataset={selectedCompany} variant="panel" />
          </div>
        )}


        {(
          <div ref={splitRef} className="flex flex-1 min-h-0">
            {/* Question list - native (no bordered card) */}
            <div className="pt-0 relative z-0 h-full flex flex-col" style={{ width: clamp(listWidth, MIN_LIST_WIDTH, MAX_LIST_WIDTH) }}>
              {!timelineOpen && (
                <QuestionListHeader title="Recent Questions" totalCount={recentQuestions.length} />
              )}
              <QuestionList
                questions={recentQuestions}
                isLoading={questionsLoading}
                selectedQuestionId={selectedQuestionId}
                onSelect={(id: string) => setSelectedQuestionId(id)}
                timelineOpen={timelineOpen}
              />
            </div>

            {/* Center divider (drag handle only; no visual seam) */}
            <div
              className="relative w-px -mx-px cursor-col-resize z-20"
              onMouseDown={handleCenterDragStart}
              title="Drag to resize"
            />

            {/* Detail Pane */}
            <div
              ref={detailPaneRef}
              className="flex-1 min-h-0 overflow-hidden overlay-pane-soft"
            >
              {selectedQuestion ? (
                <QuestionDetailPane
                  question={selectedQuestion}
                  processingSummary={processingSummary}
                  prompts={enrichedPromptsForQuestion}
                  result={resultQuery.data}
                  questionId={selectedQuestionId!}
                  timelineData={timelineData}
                  timelineLoading={timelineLoading}
                  onOpenTimeline={() => setTimelineOpen(true)}
                />
              ) : (
                <div className="h-full flex items-center justify-center text-sm text-muted">
                  Select a question to view full details
                </div>
              )}
            </div>

            {/* Right divider and Timeline Pane */}
            {timelineOpen && (
              <>
                <div className="relative w-px -mx-px cursor-col-resize z-20" onMouseDown={handleRightDragStart} title="Drag to resize" />
                <div className="h-full flex flex-col min-h-0 overflow-hidden overlay-pane-soft" style={{ width: clamp(timelineWidth, MIN_TIMELINE_WIDTH, MAX_TIMELINE_WIDTH) }}>
                  <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-text">Agent Execution Timeline</h2>
                    <button
                      className="text-xs text-muted hover:text-text"
                      onClick={() => setTimelineOpen(false)}
                    >
                      Close
                    </button>
                  </div>
                  <div ref={timelineScrollRef} className="timeline-scroll-container flex-1 min-h-0 px-4 pb-4 pt-0 overflow-y-scroll overscroll-y-auto scroll-slim ios-momentum">
                    <div ref={timelineInnerRef} className="bounce-inner pt-[2px] pb-[15vh]">
                    {timelineLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-brand"></div>
                        <p className="text-muted ml-3">Loading execution timeline...</p>
                      </div>
                    ) : timelineData ? (
                      <ExecutionTimeline data={timelineData} />
                    ) : (
                      <div className="text-sm text-muted">No execution timeline available yet.</div>
                    )}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

      </div>
    </Layout>
  );
}

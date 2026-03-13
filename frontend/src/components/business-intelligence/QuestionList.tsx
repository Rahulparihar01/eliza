import React from 'react';
import { Tooltip } from '../common/Tooltip';
import {
  QUESTION_METADATA_CONFIG,
  QUESTION_METADATA_LABELS,
  formatQuestionMeta,
  getQuestionStatusIcon,
  QuestionListEmptyState,
  type QuestionMetadataKey,
} from './questionUtils';

interface QuestionListProps {
  questions: any[];
  isLoading: boolean;
  selectedQuestionId: string | null;
  onSelect: (questionId: string) => void;
  timelineOpen?: boolean;
  metadataConfig?: typeof QUESTION_METADATA_CONFIG;
  metadataLabels?: typeof QUESTION_METADATA_LABELS;
  loadingMessage?: React.ReactNode;
  emptyState?: React.ReactNode;
}

export function QuestionList({
  questions,
  isLoading,
  selectedQuestionId,
  onSelect,
  timelineOpen = false,
  metadataConfig = QUESTION_METADATA_CONFIG,
  metadataLabels = QUESTION_METADATA_LABELS,
  loadingMessage = (
    <div className="flex items-center justify-center py-12">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-brand" />
        <p className="text-xs text-muted mt-3">Loading questions...</p>
      </div>
    </div>
  ),
  emptyState = <QuestionListEmptyState />,
}: QuestionListProps) {
  return (
    <div className="questions-scroll-container flex-1 min-h-0 overflow-y-scroll overscroll-contain overflow-x-visible ui-list scroll-slim ios-momentum bg-surface-2">
      <div className="always-scrollable -mt-px">
        {isLoading ? (
          loadingMessage
        ) : questions.length === 0 ? (
          emptyState
        ) : (
          questions.map((question) => {
            const isActive = question.question_id === selectedQuestionId;
            return (
              <button
                key={question.question_id}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(question.question_id);
                }}
                className={`ui-item pl-5 pr-4 text-left ${isActive ? 'ui-item-active' : ''}`}
                title={timelineOpen ? question.original_question : undefined}
              >
                <div className="flex items-center gap-3 min-w-0 relative">
                  <div className="flex-shrink-0">
                    {getQuestionStatusIcon(question.status)}
                  </div>
                  <div className="flex-1 min-w-0 w-full">
                    <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-3 items-start">
                      <span className="ui-item-title block min-w-0 truncate line-clamp-2 md:line-clamp-1 break-words">
                        {question.original_question}
                      </span>
                      <Tooltip
                        position="top-right"
                        content={(
                          <div className="space-y-1">
                            {metadataConfig.hoverOrder.map((key: QuestionMetadataKey) => {
                              const value = formatQuestionMeta(question, key);
                              if (!value) return null;
                              return (
                                <div key={key} className="flex items-start gap-2">
                                  <span className="text-gray-300">{metadataLabels[key] || key}:</span>
                                  <span className="text-white">{value}</span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                        className="col-start-2 justify-self-end inline-flex flex-shrink-0 text-right"
                      >
                        <div className="flex items-center justify-end gap-2 text-xs text-muted whitespace-nowrap">
                          <span className="ui-item-meta whitespace-nowrap">
                            {formatQuestionMeta(question, 'created_at')}
                          </span>
                          <span className="hidden md:inline ui-item-meta whitespace-nowrap capitalize">
                            • {formatQuestionMeta(question, 'status')}
                          </span>
                          {formatQuestionMeta(question, 'session_id') && (
                            <span className="hidden xl:inline ui-item-meta whitespace-nowrap">
                              • {formatQuestionMeta(question, 'session_id')}
                            </span>
                          )}
                        </div>
                      </Tooltip>
                    </div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

export default QuestionList;

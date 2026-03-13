import type { ReactNode } from 'react';
import {
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';

export const QUESTION_METADATA_CONFIG = {
  inlineVisibility: {
    base: ['created_at'] as const,
    md: ['status', 'created_at'] as const,
    lg: ['status', 'created_at'] as const,
    xl: ['status', 'created_at', 'session_id'] as const,
  },
  hoverOrder: ['status', 'created_at', 'completed_at', 'session_id'] as const,
} as const;

export const QUESTION_METADATA_LABELS: Record<string, string> = {
  status: 'Status',
  created_at: 'Created',
  completed_at: 'Completed',
  session_id: 'Session',
  id: 'ID',
};

export type QuestionMetadataKey =
  | (typeof QUESTION_METADATA_CONFIG.hoverOrder)[number]
  | 'id';

export function formatQuestionMeta(question: any, key: QuestionMetadataKey): string {
  switch (key) {
    case 'status':
      return question?.status ? String(question.status) : '';
    case 'created_at':
      return question?.created_at ? new Date(question.created_at).toLocaleDateString() : '';
    case 'completed_at':
      return question?.completed_at ? new Date(question.completed_at).toLocaleDateString() : '';
    case 'session_id':
      return question?.session_id ? String(question.session_id) : '';
    case 'id':
      return question?.question_id ? String(question.question_id) : '';
    default:
      return '';
  }
}

export function getQuestionStatusIcon(status: string): ReactNode {
  switch (status) {
    case 'completed':
      return <CheckCircleIcon className="w-5 h-5 text-success" />;
    case 'failed':
      return <ExclamationCircleIcon className="w-5 h-5 text-error" />;
    case 'processing':
    case 'enriching':
    case 'analyzing':
      return <SparklesIcon className="w-5 h-5 text-brand animate-pulse" />;
    default:
      return <ClockIcon className="w-5 h-5 text-muted" />;
  }
}

export function getQuestionStatusText(status: string): string {
  switch (status) {
    case 'pending':
      return 'Pending';
    case 'enriching':
      return 'Enriching Question';
    case 'analyzing':
      return 'Analyzing Data';
    case 'processing':
      return 'Processing';
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
}

export function getQuestionStatusBadgeClasses(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-ai-success-soft text-ai-success';
    case 'failed':
      return 'bg-ai-danger-soft text-ai-danger';
    case 'processing':
    case 'enriching':
    case 'analyzing':
      return 'bg-brand-soft text-brand';
    default:
      return 'bg-surface-2 text-muted';
  }
}

export function formatQuestionDateTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
}

export function QuestionListEmptyState() {
  return (
    <div className="text-center py-12 px-4 text-sm text-muted">
      <ChatBubbleLeftRightIcon className="w-8 h-8 mx-auto mb-3 text-muted" />
      No questions yet. Submit your first question!
    </div>
  );
}

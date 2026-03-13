import React from 'react';
import { cn } from '../../shared/lib/cn';

interface QuestionListHeaderProps {
  title: string;
  totalCount?: number;
  countLabel?: string;
  className?: string;
  actions?: React.ReactNode;
}

export function QuestionListHeader({
  title,
  totalCount,
  countLabel,
  className = '',
  actions,
}: QuestionListHeaderProps) {
  return (
    <div className={cn('px-3 bg-surface-2 h-9 flex items-center gap-2', className)}>
      <h2 className="text-xs font-semibold text-muted-2 uppercase tracking-wide">{title}</h2>
      <div className="ml-auto flex items-center gap-2">
        {typeof totalCount === 'number' && (
          <span className="text-xs text-muted">
            {countLabel ?? `${totalCount} total`}
          </span>
        )}
        {actions}
      </div>
    </div>
  );
}

export default QuestionListHeader;

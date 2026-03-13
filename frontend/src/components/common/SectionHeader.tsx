import type { ReactNode } from 'react';
import { cn } from '../../shared/lib/cn';

interface SectionHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
  badge?: ReactNode | number;
  size?: 'sm' | 'md';
  className?: string;
}

export function SectionHeader({
  title,
  description,
  action,
  badge,
  size = 'md',
  className,
}: SectionHeaderProps) {
  const containerClasses = cn(
    'flex items-center justify-between gap-3',
    size === 'sm'
      ? 'py-2 px-3 rounded-lg border border-border/60 bg-surface-2 text-[11px] font-semibold uppercase tracking-wide text-muted'
      : 'py-3 px-4 border-b border-border bg-surface-2 text-sm font-semibold text-text',
    className
  );

  return (
    <div className={containerClasses}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="truncate">{title}</span>
        {typeof badge !== 'undefined' && badge !== null && (
          <span className="inline-flex items-center justify-center rounded-full bg-surface text-muted text-[10px] font-semibold px-2 py-0.5 border border-border/60">
            {badge}
          </span>
        )}
        {description && size === 'md' && (
          <span className="text-xs font-normal text-muted truncate">{description}</span>
        )}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}

export default SectionHeader;

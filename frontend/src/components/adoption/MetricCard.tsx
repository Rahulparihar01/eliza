/**
 * Metric Card Component for Adoption Dashboard
 * 
 * Displays a single metric with optional trend indicator.
 * Migrated to Eliza Forge Design System.
 */

import React from 'react';
import {
  UsersIcon,
  ChatBubbleLeftRightIcon,
  CpuChipIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/outline';
import { Skeleton } from '../ui/skeleton';
import { InfoTooltip } from '../common/InfoTooltip';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: 'users' | 'conversations' | 'tokens' | 'messages';
  trend?: {
    value: number;
    direction: 'up' | 'down';
    label?: string;
  };
  color?: 'brand' | 'success' | 'warning' | 'info' | 'purple';
  loading?: boolean;
  tooltip?: string | React.ReactNode;
}

const iconMap = {
  users: UsersIcon,
  conversations: ChatBubbleLeftRightIcon,
  tokens: CpuChipIcon,
  messages: ChatBubbleLeftRightIcon,
};

// DS-compatible color classes
const colorClasses = {
  brand: 'bg-eliza-red/10 text-eliza-red',
  success: 'bg-green-500/10 text-green-600 dark:text-green-400',
  warning: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  info: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  purple: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',
};

export function MetricCard({
  title,
  value,
  subtitle,
  icon = 'users',
  trend,
  color = 'brand',
  loading = false,
  tooltip,
}: MetricCardProps) {
  const IconComponent = iconMap[icon];
  const TrendIcon = trend?.direction === 'up' ? ArrowTrendingUpIcon : ArrowTrendingDownIcon;

  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        <div className="flex items-center justify-between mb-4">
          <Skeleton variant="rounded" width={40} height={40} />
          <Skeleton variant="text" width={64} height={16} />
        </div>
        <Skeleton variant="text" width={96} height={32} className="mb-2" />
        <Skeleton variant="text" width={128} height={16} />
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6 hover:shadow-lg transition-all duration-200 hover:border-eliza-red/30">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-2.5 rounded-lg ${colorClasses[color]}`}>
          <IconComponent className="h-5 w-5" />
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-sm font-medium ${
            trend.direction === 'up' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          }`}>
            <TrendIcon className="h-4 w-4" />
            <span>{Math.abs(trend.value)}%</span>
          </div>
        )}
      </div>

      <div className="space-y-1">
        <h3 className="text-3xl font-bold text-charcoal dark:text-gray-100 tracking-tight">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </h3>
        <div className="flex items-center gap-1.5">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          {tooltip && <InfoTooltip content={tooltip} />}
        </div>
        {subtitle && (
          <p className="text-xs text-eliza-red">{subtitle}</p>
        )}
        {trend?.label && (
          <p className="text-xs text-gray-400 dark:text-gray-500">{trend.label}</p>
        )}
      </div>
    </div>
  );
}

export default MetricCard;


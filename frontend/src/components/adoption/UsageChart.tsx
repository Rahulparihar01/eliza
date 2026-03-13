/**
 * Usage Chart Component for Adoption Dashboard
 * 
 * Displays time-series chart of adoption metrics.
 * Migrated to Eliza Forge Design System.
 */

import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { DailyMetric } from '../../hooks/useAdoption';
import { InfoTooltip } from '../common/InfoTooltip';
import { Skeleton } from '../ui/skeleton';

interface UsageChartProps {
  data: DailyMetric[];
  metricType: 'users' | 'conversations' | 'tokens' | 'messages';
  title?: string;
  loading?: boolean;
  height?: number;
  infoTooltip?: string | React.ReactNode;
}

// Eliza theme-compatible colors that work in both light and dark mode
const metricConfigs = {
  users: {
    dataKey: 'active_users',
    label: 'Active Users',
    color: '#9D8B7A', // Warm taupe - brand-adjacent
    gradientId: 'usersGradient',
  },
  conversations: {
    dataKey: 'total_conversations',
    label: 'Conversations',
    color: '#6B8E9F', // Muted teal - info color
    gradientId: 'conversationsGradient',
  },
  tokens: {
    dataKey: 'total_tokens',
    label: 'Total Tokens',
    color: '#C4A484', // Warm cream - brand color
    gradientId: 'tokensGradient',
  },
  messages: {
    dataKey: 'total_messages',
    label: 'Messages',
    color: '#7A9F6B', // Sage green - success adjacent
    gradientId: 'messagesGradient',
  },
};

export function UsageChart({
  data,
  metricType,
  title,
  loading = false,
  height = 300,
  infoTooltip,
}: UsageChartProps) {
  const config = metricConfigs[metricType];

  const chartData = useMemo(() => {
    return data.map((d) => ({
      ...d,
      date: new Date(d.date + 'T12:00:00').toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
    }));
  }, [data]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        {title && (
        <div className="flex items-center gap-2 mb-4">
          <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">{title}</h3>
          {infoTooltip && <InfoTooltip content={infoTooltip} />}
        </div>
      )}
        <Skeleton variant="rounded" height={height} />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        {title && (
        <div className="flex items-center gap-2 mb-4">
          <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">{title}</h3>
          {infoTooltip && <InfoTooltip content={infoTooltip} />}
        </div>
      )}
        <div
          className="flex items-center justify-center text-gray-500 dark:text-gray-400"
          style={{ height }}
        >
          No data available for the selected period
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
      {title && (
        <div className="flex items-center gap-2 mb-4">
          <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">{title}</h3>
          {infoTooltip && <InfoTooltip content={infoTooltip} />}
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={config.gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={config.color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={config.color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="date"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#9CA3AF' }}
            stroke="#9CA3AF"
            interval="preserveStartEnd"
            tickMargin={5}
          />
          <YAxis
            fontSize={12}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#9CA3AF' }}
            stroke="#9CA3AF"
            tickFormatter={(value) =>
              value >= 1000000
                ? `${(value / 1000000).toFixed(1)}M`
                : value >= 1000
                ? `${(value / 1000).toFixed(1)}K`
                : value.toString()
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
              color: 'var(--color-text)',
            }}
            labelStyle={{ color: 'var(--color-text)' }}
            itemStyle={{ color: 'var(--color-text)' }}
            formatter={(value: number) => [value.toLocaleString(), config.label]}
          />
          <Area
            type="monotone"
            dataKey={config.dataKey}
            stroke={config.color}
            strokeWidth={2}
            fill={`url(#${config.gradientId})`}
            dot={false}
            activeDot={{ r: 6, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

interface MultiMetricChartProps {
  data: DailyMetric[];
  metrics: ('users' | 'conversations' | 'tokens' | 'messages')[];
  title?: string;
  loading?: boolean;
  height?: number;
}

export function MultiMetricChart({
  data,
  metrics,
  title,
  loading = false,
  height = 300,
}: MultiMetricChartProps) {
  const chartData = useMemo(() => {
    return data.map((d) => ({
      ...d,
      date: new Date(d.date + 'T12:00:00').toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
    }));
  }, [data]);

  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        {title && <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100 mb-4">{title}</h3>}
        <Skeleton variant="rounded" height={height} />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        {title && <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100 mb-4">{title}</h3>}
        <div
          className="flex items-center justify-center text-gray-500 dark:text-gray-400"
          style={{ height }}
        >
          No data available for the selected period
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
      {title && <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100 mb-4">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="date"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#9CA3AF' }}
            stroke="#9CA3AF"
            interval="preserveStartEnd"
            tickMargin={5}
          />
          <YAxis
            fontSize={12}
            tickLine={false}
            axisLine={false}
            tick={{ fill: '#9CA3AF' }}
            stroke="#9CA3AF"
            tickFormatter={(value) =>
              value >= 1000000
                ? `${(value / 1000000).toFixed(1)}M`
                : value >= 1000
                ? `${(value / 1000).toFixed(1)}K`
                : value.toString()
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
              color: 'var(--color-text)',
            }}
            labelStyle={{ color: 'var(--color-text)' }}
            itemStyle={{ color: 'var(--color-text)' }}
            formatter={(value: number, name: string) => [
              value.toLocaleString(),
              metricConfigs[name as keyof typeof metricConfigs]?.label || name,
            ]}
          />
          <Legend 
            formatter={(value: string) => (
              <span style={{ color: 'var(--color-text)' }}>
                {metricConfigs[value as keyof typeof metricConfigs]?.label || value}
              </span>
            )}
          />
          {metrics.map((metric) => {
            const cfg = metricConfigs[metric];
            return (
              <Line
                key={metric}
                type="monotone"
                dataKey={cfg.dataKey}
                name={metric}
                stroke={cfg.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5 }}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default UsageChart;


/**
 * GPT Adoption Chart Component
 * 
 * Pie chart showing the percentage of conversations using custom GPTs
 * vs base ChatGPT.
 * Migrated to Eliza Forge Design System.
 */

import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';
import { InfoTooltip } from '../common/InfoTooltip';
import { Skeleton } from '../ui/skeleton';

interface GPTAdoptionChartProps {
  gptConversations: number;
  baseConversations: number;
  loading?: boolean;
  title?: string;
}

// Eliza theme colors
const COLORS = {
  gpt: 'var(--color-brand, #C4A484)',  // Brand/cream color for custom GPTs
  base: 'var(--color-info, #6B8E9F)',   // Info/teal for base ChatGPT
};

export function GPTAdoptionChart({
  gptConversations,
  baseConversations,
  loading = false,
  title = 'GPT Adoption Rate',
}: GPTAdoptionChartProps) {
  const total = gptConversations + baseConversations;
  const adoptionRate = total > 0 ? ((gptConversations / total) * 100).toFixed(1) : '0.0';

  const data = [
    { name: 'Custom GPTs', value: gptConversations, color: COLORS.gpt },
    { name: 'Base ChatGPT', value: baseConversations, color: COLORS.base },
  ];

  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100 mb-4">{title}</h3>
        <Skeleton variant="rounded" height={280} />
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100 mb-4">{title}</h3>
        <div
          className="flex items-center justify-center text-gray-500 dark:text-gray-400"
          style={{ height: 280 }}
        >
          No conversation data available
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">{title}</h3>
          <InfoTooltip
            title="How is this calculated?"
            content={
              <div className="space-y-2">
                <p>
                  <strong>GPT Adoption Rate</strong> = Conversations using custom GPTs ÷ Total conversations × 100
                </p>
                <p>
                  This shows what percentage of all ChatGPT conversations in your organization used a custom-built GPT vs the base ChatGPT model.
                </p>
                <p className="text-xs mt-2">
                  Current: {gptConversations.toLocaleString()} GPT convos ÷ {total.toLocaleString()} total = {adoptionRate}%
                </p>
              </div>
            }
          />
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-eliza-red">{adoptionRate}%</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">of conversations use custom GPTs</div>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={75}
            paddingAngle={3}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number, name: string) => [
              `${value.toLocaleString()} conversations`,
              name,
            ]}
            contentStyle={{
              backgroundColor: 'var(--color-surface, #ffffff)',
              border: '1px solid var(--color-border, #e5e7eb)',
              borderRadius: '8px',
              color: 'var(--color-text, #1f2937)',
            }}
            labelStyle={{ color: 'var(--color-text, #1f2937)' }}
          />
          <Legend
            verticalAlign="bottom"
            height={32}
            iconType="circle"
            iconSize={10}
            formatter={(value: string) => (
              <span className="text-charcoal dark:text-gray-100 text-sm">{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>

      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-200 dark:border-dark-border">
        <div className="text-center">
          <div className="text-lg font-semibold text-eliza-red">{gptConversations.toLocaleString()}</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Custom GPTs</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-semibold text-blue-600 dark:text-blue-400">{baseConversations.toLocaleString()}</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">Base ChatGPT</div>
        </div>
      </div>
    </div>
  );
}


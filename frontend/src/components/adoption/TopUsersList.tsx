/**
 * Top Users List Component
 * 
 * Displays a ranked list of top ChatGPT users by usage metrics.
 * Migrated to Eliza Forge Design System.
 */

import React from 'react';
import { 
  UserCircleIcon,
  ChatBubbleLeftRightIcon,
  EnvelopeIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { TopUserInfo } from '../../hooks/useAdoption';
import { InfoTooltip } from '../common/InfoTooltip';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';

// Color palette for company pills
const COMPANY_COLORS = [
  { bg: 'bg-blue-500/15', text: 'text-blue-600', border: 'border-blue-500/30' },
  { bg: 'bg-emerald-500/15', text: 'text-emerald-600', border: 'border-emerald-500/30' },
  { bg: 'bg-violet-500/15', text: 'text-violet-600', border: 'border-violet-500/30' },
  { bg: 'bg-amber-500/15', text: 'text-amber-600', border: 'border-amber-500/30' },
  { bg: 'bg-rose-500/15', text: 'text-rose-600', border: 'border-rose-500/30' },
  { bg: 'bg-cyan-500/15', text: 'text-cyan-600', border: 'border-cyan-500/30' },
];

const getCompanyColor = (companyName: string) => {
  let hash = 0;
  for (let i = 0; i < companyName.length; i++) {
    hash = companyName.charCodeAt(i) + ((hash << 5) - hash);
  }
  return COMPANY_COLORS[Math.abs(hash) % COMPANY_COLORS.length];
};

interface TopUsersListProps {
  users: TopUserInfo[];
  title?: string;
  loading?: boolean;
  maxItems?: number;
  showCompanyName?: boolean;
}

export function TopUsersList({
  users,
  title = "Top ChatGPT Users",
  loading = false,
  maxItems = 3,
  showCompanyName = false,
}: TopUsersListProps) {
  const getRankBadgeStyle = (index: number) => {
    switch (index) {
      case 0:
        return 'bg-gradient-to-br from-yellow-400 to-yellow-600 text-white';
      case 1:
        return 'bg-gradient-to-br from-gray-300 to-gray-500 text-white';
      case 2:
        return 'bg-gradient-to-br from-amber-600 to-amber-800 text-white';
      default:
        return 'bg-surface-2 text-muted';
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        <Skeleton variant="text" width={160} height={24} className="mb-4" />
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} variant="rounded" height={64} />
          ))}
        </div>
      </div>
    );
  }

  const displayUsers = users.slice(0, maxItems);

  return (
    <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 dark:border-dark-border flex items-center gap-3">
        <div className="p-2 bg-blue-500/10 rounded-lg">
          <UserCircleIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">{title}</h3>
            <InfoTooltip
              content="Ranked by total messages sent during the selected time period. Shows users with the highest ChatGPT usage in your organization."
            />
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Most active users by messages</p>
        </div>
      </div>

      {/* User List */}
      {displayUsers.length === 0 ? (
        <div className="p-8 text-center">
          <UserCircleIcon className="h-10 w-10 text-gray-400 dark:text-gray-500 mx-auto mb-2" />
          <p className="text-gray-500 dark:text-gray-400">No user data available</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-200 dark:divide-dark-border">
          {displayUsers.map((user, index) => (
            <div 
              key={user.user_external_id || user.user_email} 
              className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
            >
              <div className="flex items-center gap-4">
                {/* Rank Badge */}
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${getRankBadgeStyle(index)}`}>
                  {index + 1}
                </div>

                {/* User Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 text-charcoal dark:text-gray-100 font-medium truncate">
                      <EnvelopeIcon className="h-4 w-4 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                      <span className="truncate">{user.user_email}</span>
                    </div>
                    {showCompanyName && user.company_name && (() => {
                      const colors = getCompanyColor(user.company_name);
                      return (
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex-shrink-0 ${colors.bg} ${colors.text} ${colors.border}`}>
                          {user.company_name}
                        </span>
                      );
                    })()}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
                    <span className="flex items-center gap-1">
                      <ChatBubbleLeftRightIcon className="h-3.5 w-3.5" />
                      {user.total_conversations.toLocaleString()} conversations
                    </span>
                    {user.gpts_used > 0 && (
                      <span className="flex items-center gap-1">
                        <SparklesIcon className="h-3.5 w-3.5" />
                        {user.gpts_used} GPTs used
                      </span>
                    )}
                  </div>
                </div>

                {/* Message Count */}
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 rounded-md">
                  <span className="text-sm text-blue-600 dark:text-blue-400 font-semibold">
                    {user.total_messages.toLocaleString()}
                  </span>
                  <span className="text-xs text-blue-600/70 dark:text-blue-400/70">msgs</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TopUsersList;


/**
 * Top GPTs List Component
 * 
 * Displays a ranked list of the most used GPTs with usage metrics
 */

import React, { useState } from 'react';
import { 
  SparklesIcon, 
  UserGroupIcon, 
  ChatBubbleLeftRightIcon,
  ArrowTopRightOnSquareIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

export interface GPTInfo {
  id: string;
  name: string;
  description?: string;
  uses: number;
  users?: number;
  conversations?: number;
  creator_email?: string;
  creator_name?: string;
  short_url?: string;
  company_id?: string;
  company_name?: string;
}

interface TopGPTsListProps {
  gpts: GPTInfo[];
  title?: string;
  loading?: boolean;
  maxItems?: number;
  maxExpandedItems?: number;  // Max items when expanded (default 50)
  showCompanyName?: boolean;  // Show company name when viewing all companies
}

// Color palette for company pills - distinct, professional colors
const COMPANY_COLORS = [
  { bg: 'bg-blue-500/15', text: 'text-blue-600', border: 'border-blue-500/30' },
  { bg: 'bg-emerald-500/15', text: 'text-emerald-600', border: 'border-emerald-500/30' },
  { bg: 'bg-violet-500/15', text: 'text-violet-600', border: 'border-violet-500/30' },
  { bg: 'bg-amber-500/15', text: 'text-amber-600', border: 'border-amber-500/30' },
  { bg: 'bg-rose-500/15', text: 'text-rose-600', border: 'border-rose-500/30' },
  { bg: 'bg-cyan-500/15', text: 'text-cyan-600', border: 'border-cyan-500/30' },
  { bg: 'bg-fuchsia-500/15', text: 'text-fuchsia-600', border: 'border-fuchsia-500/30' },
  { bg: 'bg-lime-500/15', text: 'text-lime-600', border: 'border-lime-500/30' },
];

// Get consistent color for a company based on its name
const getCompanyColor = (companyName: string) => {
  let hash = 0;
  for (let i = 0; i < companyName.length; i++) {
    hash = companyName.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % COMPANY_COLORS.length;
  return COMPANY_COLORS[index];
};

export function TopGPTsList({
  gpts,
  title = "Top GPTs",
  loading = false,
  maxItems = 5,
  maxExpandedItems = 50,
  showCompanyName = false,
}: TopGPTsListProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const getGPTLink = (gptId: string) => {
    // ChatGPT Enterprise GPT links format
    return `https://chatgpt.com/g/${gptId}`;
  };

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
      <div className="bg-surface rounded-xl border border-border p-6">
        <div className="h-6 w-32 bg-surface-2 rounded animate-pulse mb-4" />
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-surface-2 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const currentLimit = isExpanded ? maxExpandedItems : maxItems;
  const displayGpts = gpts.slice(0, currentLimit);
  const hasMore = gpts.length > maxItems;
  const remainingCount = Math.min(gpts.length, maxExpandedItems) - maxItems;

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border flex items-center gap-3">
        <div className="p-2 bg-ai-purple/10 rounded-lg">
          <SparklesIcon className="h-5 w-5 text-ai-purple" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text">{title}</h3>
          <p className="text-xs text-muted">Most used custom GPTs</p>
        </div>
      </div>

      {/* GPT List */}
      {displayGpts.length === 0 ? (
        <div className="p-8 text-center">
          <SparklesIcon className="h-10 w-10 text-muted mx-auto mb-2" />
          <p className="text-muted">No GPT usage data available</p>
        </div>
      ) : (
        <>
          <div className="divide-y divide-border">
            {displayGpts.map((gpt, index) => (
              <div 
                key={gpt.id || index} 
                className="px-6 py-4 hover:bg-surface-2/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {/* Rank Badge */}
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${getRankBadgeStyle(index)}`}>
                    {index + 1}
                  </div>

                  {/* GPT Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <a
                        href={getGPTLink(gpt.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-text hover:text-brand transition-colors flex items-center gap-1.5 group"
                      >
                        {gpt.name}
                        <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </a>
                      {showCompanyName && gpt.company_name && (() => {
                        const colors = getCompanyColor(gpt.company_name);
                        return (
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colors.bg} ${colors.text} ${colors.border}`}>
                            {gpt.company_name}
                          </span>
                        );
                      })()}
                    </div>
                    {(gpt.creator_name || gpt.creator_email) && (
                      <p className="text-xs text-muted mt-0.5 truncate">
                        by {gpt.creator_name || gpt.creator_email}
                      </p>
                    )}
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-sm">
                    {gpt.users !== undefined && (
                      <div className="flex items-center gap-1.5 text-muted" title="Users">
                        <UserGroupIcon className="h-4 w-4" />
                        <span className="font-medium text-text">{gpt.users.toLocaleString()}</span>
                      </div>
                    )}
                    {gpt.conversations !== undefined && (
                      <div className="flex items-center gap-1.5 text-muted" title="Conversations">
                        <ChatBubbleLeftRightIcon className="h-4 w-4" />
                        <span className="font-medium text-text">{gpt.conversations.toLocaleString()}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-ai-purple/10 rounded-md" title="Total Uses">
                      <span className="text-xs text-ai-purple font-medium">{gpt.uses.toLocaleString()} uses</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          
          {/* View More / Show Less Button */}
          {hasMore && (
            <div className="px-6 py-3 border-t border-border">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-center gap-2 py-2 text-sm font-medium text-muted hover:text-text hover:bg-surface-2 rounded-lg transition-colors"
              >
                {isExpanded ? (
                  <>
                    <ChevronUpIcon className="h-4 w-4" />
                    Show Less
                  </>
                ) : (
                  <>
                    <ChevronDownIcon className="h-4 w-4" />
                    View More ({remainingCount} more)
                  </>
                )}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default TopGPTsList;


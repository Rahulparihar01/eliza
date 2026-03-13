/**
 * GPT Breakdown Tab Component
 * 
 * Displays a detailed list of GPTs with expandable rows showing
 * title, description, and usage metrics.
 * Migrated to Eliza Forge Design System.
 */

import React, { useState } from 'react';
import { 
  SparklesIcon, 
  UserGroupIcon, 
  ChatBubbleLeftRightIcon,
  ArrowTopRightOnSquareIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { GPTUsageInfo } from '../../hooks/useAdoption';
import { Input } from '../ui/input';
import { Select, SelectOption } from '../ui/select';
import { Button } from '../ui/button';
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

interface GPTBreakdownTabProps {
  gpts: GPTUsageInfo[];
  loading?: boolean;
  showCompanyName?: boolean;
  initialDisplayCount?: number;
}

export function GPTBreakdownTab({
  gpts,
  loading = false,
  showCompanyName = false,
  initialDisplayCount = 20,
}: GPTBreakdownTabProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'uses' | 'users' | 'conversations' | 'name'>('uses');
  const [displayCount, setDisplayCount] = useState(initialDisplayCount);

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedIds(newExpanded);
  };

  const getGPTLink = (gptId: string) => {
    return `https://chatgpt.com/g/${gptId}`;
  };

  // Filter and sort GPTs
  const filteredGPTs = gpts
    .filter(gpt => {
      if (!searchQuery) return true;
      const query = searchQuery.toLowerCase();
      return (
        gpt.name?.toLowerCase().includes(query) ||
        gpt.description?.toLowerCase().includes(query) ||
        gpt.creator_email?.toLowerCase().includes(query) ||
        gpt.creator_name?.toLowerCase().includes(query)
      );
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return (a.name || '').localeCompare(b.name || '');
        case 'users':
          return (b.users || 0) - (a.users || 0);
        case 'conversations':
          return (b.conversations || 0) - (a.conversations || 0);
        case 'uses':
        default:
          return b.uses - a.uses;
      }
    });

  // Apply display limit
  const displayedGPTs = filteredGPTs.slice(0, displayCount);
  const hasMore = filteredGPTs.length > displayCount;
  const remainingCount = filteredGPTs.length - displayCount;

  // Reset display count when search changes
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setDisplayCount(initialDisplayCount);
  };

  const handleShowMore = () => {
    setDisplayCount(prev => prev + 20);
  };

  const handleShowAll = () => {
    setDisplayCount(filteredGPTs.length);
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton variant="rounded" width={256} height={40} />
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} variant="rounded" height={80} />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Total GPT Count Header */}
      <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-violet-500/10 rounded-xl">
              <SparklesIcon className="h-8 w-8 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <div className="text-3xl font-bold text-charcoal dark:text-gray-100">{gpts.length}</div>
              <div className="text-sm text-gray-500 dark:text-gray-400">Total Custom GPTs</div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold text-charcoal dark:text-gray-100">
              {gpts.filter(g => (g.uses || 0) > 0).length}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">with usage data</div>
          </div>
        </div>
      </div>

      {/* Filters Row */}
      <div className="flex items-center gap-4 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 dark:text-gray-500" />
          <Input
            type="text"
            placeholder="Search GPTs by name, description, or creator..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">Sort by:</span>
          <Select
            value={sortBy}
            onValueChange={(value) => setSortBy(value as typeof sortBy)}
          >
            <SelectOption value="uses">Messages</SelectOption>
            <SelectOption value="conversations">Conversations</SelectOption>
            <SelectOption value="users">Users</SelectOption>
            <SelectOption value="name">Name</SelectOption>
          </Select>
        </div>

        {/* Showing Count */}
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Showing {displayedGPTs.length} of {filteredGPTs.length}
        </div>
      </div>

      {/* GPT List */}
      {filteredGPTs.length === 0 ? (
        <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border p-12 text-center">
          <SparklesIcon className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-charcoal dark:text-gray-100 mb-1">No GPTs Found</h3>
          <p className="text-gray-500 dark:text-gray-400">
            {searchQuery ? 'Try adjusting your search query' : 'No GPTs available'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {displayedGPTs.map((gpt, index) => {
            const isExpanded = expandedIds.has(gpt.id);
            
            return (
              <div 
                key={gpt.id} 
                className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden transition-shadow hover:shadow-md"
              >
                {/* Main Row */}
                <div 
                  className="px-6 py-4 flex items-center gap-4 cursor-pointer"
                  onClick={() => toggleExpanded(gpt.id)}
                >
                  {/* Expand/Collapse Icon */}
                  <button className="p-1 hover:bg-gray-100 dark:hover:bg-dark-surface-2 rounded transition-colors">
                    {isExpanded ? (
                      <ChevronDownIcon className="h-5 w-5 text-gray-400 dark:text-gray-500" />
                    ) : (
                      <ChevronRightIcon className="h-5 w-5 text-gray-400 dark:text-gray-500" />
                    )}
                  </button>

                  {/* Rank */}
                  <div className="text-lg font-bold text-gray-400 dark:text-gray-500 w-8 text-center">
                    #{index + 1}
                  </div>

                  {/* GPT Icon */}
                  <div className="p-2 bg-violet-500/10 rounded-lg">
                    <SparklesIcon className="h-5 w-5 text-violet-600 dark:text-violet-400" />
                  </div>

                  {/* GPT Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <a
                        href={getGPTLink(gpt.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="font-semibold text-charcoal dark:text-gray-100 hover:text-eliza-red transition-colors flex items-center gap-1.5 group"
                      >
                        {gpt.name || gpt.id}
                        <ArrowTopRightOnSquareIcon className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
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
                    {gpt.creator_name || gpt.creator_email ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                        by {gpt.creator_name || gpt.creator_email}
                      </p>
                    ) : null}
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-6 text-sm">
                    {gpt.users !== undefined && (
                      <div className="flex items-center gap-1.5 text-gray-400 dark:text-gray-500" title="Unique Users">
                        <UserGroupIcon className="h-4 w-4" />
                        <span className="font-medium text-charcoal dark:text-gray-100">{gpt.users.toLocaleString()}</span>
                      </div>
                    )}
                    {gpt.conversations !== undefined && (
                      <div className="flex items-center gap-1.5 text-gray-400 dark:text-gray-500" title="Conversations">
                        <ChatBubbleLeftRightIcon className="h-4 w-4" />
                        <span className="font-medium text-charcoal dark:text-gray-100">{gpt.conversations.toLocaleString()}</span>
                      </div>
                    )}
                    <div className="px-3 py-1.5 bg-violet-500/10 rounded-md" title="Total Messages">
                      <span className="text-sm text-violet-600 dark:text-violet-400 font-semibold">
                        {gpt.uses.toLocaleString()} msgs
                      </span>
                    </div>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="px-6 py-4 bg-gray-50/50 dark:bg-dark-surface-2/30 border-t border-gray-200 dark:border-dark-border">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Description */}
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                          Description
                        </h4>
                        <p className="text-sm text-charcoal dark:text-gray-100">
                          {gpt.description || 'No description available'}
                        </p>
                      </div>

                      {/* Details */}
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
                          Details
                        </h4>
                        <div className="space-y-1.5 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-gray-500 dark:text-gray-400">GPT ID</span>
                            <code className="text-charcoal dark:text-gray-100 bg-white dark:bg-dark-surface px-2 py-0.5 rounded text-xs">
                              {gpt.id}
                            </code>
                          </div>
                          {gpt.creator_email && (
                            <div className="flex items-center justify-between">
                              <span className="text-gray-500 dark:text-gray-400">Creator Email</span>
                              <span className="text-charcoal dark:text-gray-100">{gpt.creator_email}</span>
                            </div>
                          )}
                          {gpt.short_url && (
                            <div className="flex items-center justify-between">
                              <span className="text-gray-500 dark:text-gray-400">Short URL</span>
                              <a 
                                href={gpt.short_url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-eliza-red hover:underline"
                              >
                                {gpt.short_url}
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
          
          {/* View More Button */}
          {hasMore && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <Button
                onClick={handleShowMore}
                variant="secondary"
              >
                Show More ({Math.min(20, remainingCount)} more)
              </Button>
              <Button
                onClick={handleShowAll}
                variant="ghost"
              >
                Show All ({remainingCount} remaining)
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default GPTBreakdownTab;


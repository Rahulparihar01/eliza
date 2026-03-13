/**
 * Data Source Selector Component
 * 
 * Allows users to select which data source/domain to query.
 * Shows built-in domains (Insurance, FASB) + user-created RAG domains.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DataSourceType } from '../../generated/models';
import {
  ChartBarIcon,
  ArrowTopRightOnSquareIcon,
  BookOpenIcon,
  FolderIcon,
  PlusIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import {
  Card,
  CardContent,
  PageContent,
} from '../ui';
import { cn } from '../../shared/lib/cn';
import { LoadingSpinner } from '../common/LoadingSpinner';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

// Icon mapping for user-created domains
const ICON_MAP: Record<string, React.ElementType> = {
  folder: FolderIcon,
  document: DocumentTextIcon,
  chart: ChartBarIcon,
  book: BookOpenIcon,
};

// Color mapping for user-created domains
const COLOR_MAP: Record<string, { text: string; bg: string }> = {
  violet: { text: 'text-violet-600', bg: 'from-violet-500/10 to-violet-600/5' },
  emerald: { text: 'text-emerald-600', bg: 'from-emerald-500/10 to-emerald-600/5' },
  blue: { text: 'text-blue-600', bg: 'from-blue-500/10 to-blue-600/5' },
  orange: { text: 'text-orange-600', bg: 'from-orange-500/10 to-orange-600/5' },
  pink: { text: 'text-pink-600', bg: 'from-pink-500/10 to-pink-600/5' },
  cyan: { text: 'text-cyan-600', bg: 'from-cyan-500/10 to-cyan-600/5' },
};

interface RAGFlowDomain {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  icon: string;
  color: string;
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  document_count: number;
  chunk_count: number;
}

interface DataSourceSelectorProps {
  onSelect: (source: DataSourceType) => void;
  onSelectRagDomain: (domainId: number, domainName: string) => void;
}

interface BuiltInDomainCard {
  type: DataSourceType;
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bgGradient: string;
  features: string[];
}

// Built-in domains (Insurance + FASB)
const BUILT_IN_DOMAINS: BuiltInDomainCard[] = [
  {
    type: DataSourceType.insurance,
    title: 'Insurance Analytics',
    description: 'Query insurance policy, claim, and customer data using natural language.',
    icon: ChartBarIcon,
    color: 'text-eliza-red',
    bgGradient: 'from-eliza-red/10 to-eliza-red-light/5',
    features: ['Policy Analysis', 'Claims Data', 'Customer Insights'],
  },
  {
    type: DataSourceType.fasb,
    title: 'FASB Standards (ASC)',
    description: 'Ask questions about FASB Accounting Standards Codification.',
    icon: BookOpenIcon,
    color: 'text-emerald-600',
    bgGradient: 'from-emerald-500/10 to-emerald-600/5',
    features: ['GAAP Guidance', 'ASC Topics', 'Cited Sources'],
  },
];

export default function DataSourceSelector({ onSelect, onSelectRagDomain }: DataSourceSelectorProps) {
  const navigate = useNavigate();
  const token = localStorage.getItem('auth_token');
  const [ragDomains, setRagDomains] = useState<RAGFlowDomain[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch user's RAG domains
  const fetchDomains = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        // API returns array directly
        setRagDomains(Array.isArray(data) ? data : data.domains || []);
      }
    } catch (e) {
      console.error('Failed to fetch RAG domains:', e);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDomains();
  }, [fetchDomains]);

  // Poll for status updates when any domain is indexing
  useEffect(() => {
    const hasIndexingDomains = ragDomains.some(d => d.status === 'indexing');
    if (!hasIndexingDomains) return;

    const interval = setInterval(fetchDomains, 5000);
    return () => clearInterval(interval);
  }, [ragDomains, fetchDomains]);

  const handleRagDomainClick = (domain: RAGFlowDomain) => {
    if (domain.status === 'ready') {
      onSelectRagDomain(domain.id, domain.display_name);
    } else {
      // For pending/indexing/failed domains, go to domain detail to manage
      navigate(`/domains/${domain.id}`);
    }
  };

  const getStatusBadge = (domain: RAGFlowDomain) => {
    switch (domain.status) {
      case 'indexing':
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 flex items-center gap-1">
            <span className="inline-block w-1.5 h-1.5 bg-amber-500 rounded-full animate-pulse" />
            Indexing
          </span>
        );
      case 'ready':
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            Ready
          </span>
        );
      case 'failed':
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 flex items-center gap-1">
            <ExclamationCircleIcon className="w-3 h-3" />
            Failed
          </span>
        );
      case 'pending':
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500 dark:bg-dark-surface-2 dark:text-gray-400">
            No Docs
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-gray-50 dark:bg-dark-bg">
      <PageContent maxWidth="lg" className="py-12">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="font-title text-3xl md:text-4xl text-charcoal dark:text-white mb-3">
            Select an Analytics Domain
          </h1>
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            Choose a domain to start asking questions
          </p>
        </div>

        {/* Domain Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {/* Built-in domains */}
          {BUILT_IN_DOMAINS.map((domain) => {
            const IconComponent = domain.icon;
            
            return (
              <Card
                key={domain.type}
                className="group cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5 overflow-hidden"
                onClick={() => onSelect(domain.type)}
              >
                <div className={cn(
                  "h-24 flex items-center justify-center",
                  `bg-gradient-to-br ${domain.bgGradient}`
                )}>
                  <div className={cn(
                    "p-4 rounded-xl bg-white/80 dark:bg-dark-surface/80 shadow-sm",
                    domain.color
                  )}>
                    <IconComponent className="h-8 w-8" />
                  </div>
                </div>

                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-lg text-charcoal dark:text-white group-hover:text-eliza-red transition-colors">
                      {domain.title}
                    </h3>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-1" />
                  </div>

                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 line-clamp-2">
                    {domain.description}
                  </p>

                  <div className="flex flex-wrap gap-1.5">
                    {domain.features.map((feature) => (
                      <span
                        key={feature}
                        className="px-2.5 py-1 text-xs rounded-full bg-gray-100 dark:bg-dark-surface-2 text-gray-600 dark:text-gray-400"
                      >
                        {feature}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {/* User-created RAG domains */}
          {ragDomains.map((domain) => {
            const IconComponent = ICON_MAP[domain.icon] || FolderIcon;
            const colorConfig = COLOR_MAP[domain.color] || COLOR_MAP.violet;
            const isReady = domain.status === 'ready';
            
            return (
              <Card
                key={`rag-${domain.id}`}
                className={cn(
                  "group overflow-hidden transition-all duration-200 cursor-pointer",
                  isReady 
                    ? "hover:shadow-lg hover:-translate-y-0.5" 
                    : "hover:shadow-md"
                )}
                onClick={() => handleRagDomainClick(domain)}
              >
                <div className={cn(
                  "h-24 flex items-center justify-center relative",
                  `bg-gradient-to-br ${colorConfig.bg}`
                )}>
                  <div className={cn(
                    "p-4 rounded-xl bg-white/80 dark:bg-dark-surface/80 shadow-sm",
                    colorConfig.text
                  )}>
                    <IconComponent className="h-8 w-8" />
                  </div>
                  {/* Status indicator */}
                  {domain.status === 'indexing' && (
                    <div className="absolute bottom-2 left-2 right-2">
                      <div className="h-1.5 bg-gray-200 dark:bg-dark-border rounded-full overflow-hidden">
                        <div className="h-full bg-amber-500 animate-pulse w-3/5" />
                      </div>
                    </div>
                  )}
                </div>

                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className={cn(
                      "font-semibold text-lg text-charcoal dark:text-white",
                      isReady && "group-hover:text-violet-600 transition-colors"
                    )}>
                      {domain.display_name}
                    </h3>
                    {isReady && (
                      <ArrowTopRightOnSquareIcon className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-1" />
                    )}
                  </div>

                  {domain.description && (
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 line-clamp-2">
                      {domain.description}
                    </p>
                  )}

                  <div className="flex flex-wrap gap-1.5 items-center">
                    <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 dark:bg-dark-surface-2 text-gray-600 dark:text-gray-400">
                      {domain.document_count} docs
                    </span>
                    <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 dark:bg-dark-surface-2 text-gray-600 dark:text-gray-400">
                      {domain.chunk_count} chunks
                    </span>
                    {getStatusBadge(domain)}
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {/* Loading state */}
          {isLoading && (
            <Card className="overflow-hidden">
              <div className="h-24 flex items-center justify-center bg-gradient-to-br from-gray-100 to-gray-50 dark:from-dark-surface-2 dark:to-dark-surface">
                <LoadingSpinner size="sm" />
              </div>
              <CardContent className="p-5">
                <div className="h-4 bg-gray-200 dark:bg-dark-surface-2 rounded animate-pulse mb-2" />
                <div className="h-3 bg-gray-100 dark:bg-dark-surface-2 rounded animate-pulse w-2/3" />
              </CardContent>
            </Card>
          )}

          {/* Create New Domain card */}
          <Card
            className="group cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5 overflow-hidden border-dashed border-2"
            onClick={() => navigate('/domains')}
          >
            <div className="h-24 flex items-center justify-center bg-gradient-to-br from-gray-100/50 to-gray-50/50 dark:from-dark-surface-2/50 dark:to-dark-surface/50">
              <div className="p-4 rounded-xl bg-white/80 dark:bg-dark-surface/80 shadow-sm">
                <PlusIcon className="h-8 w-8 text-gray-400 group-hover:text-violet-600 transition-colors" />
              </div>
            </div>

            <CardContent className="p-5 text-center">
              <h3 className="font-semibold text-lg text-charcoal dark:text-white group-hover:text-violet-600 transition-colors">
                Create New Domain
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Upload documents for RAG chat
              </p>
            </CardContent>
          </Card>
        </div>
      </PageContent>
    </div>
  );
}

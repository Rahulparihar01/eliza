/**
 * Adoption Dashboard Page
 * 
 * Main dashboard for viewing ChatGPT Enterprise and AI provider adoption metrics
 * across accessible tenants. Supports multi-tenant viewing via permission-based access.
 * 
 * Migrated to Eliza Forge Design System.
 */

import React, { useState, useMemo } from 'react';
import { format, subDays, startOfDay, endOfDay } from 'date-fns';
import {
  ShareIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Layout from '../../components/layout/Layout';
import {
  Page,
  PageHeader,
  PageBody,
  Tabs,
  TabsList,
  TabsTrigger,
  Button,
  Badge,
  Skeleton,
  DateRangePicker as DSDateRangePicker,
  DateRange as DSDateRange,
  Panel,
  PanelHeader,
  PanelTitle,
  PanelDescription,
  PanelBody,
} from '../../components/ui';
import { MetricCard } from '../../components/adoption/MetricCard';
import { UsageChart } from '../../components/adoption/UsageChart';
import { CompanySelector } from '../../components/adoption/CompanySelector';
import { SharingManager } from '../../components/adoption/SharingManager';
import { GPTInfo } from '../../components/adoption/TopGPTsList';
import { TopUsersList } from '../../components/adoption/TopUsersList';
import { GPTAdoptionChart } from '../../components/adoption/GPTAdoptionChart';
import { GPTBreakdownTab } from '../../components/adoption/GPTBreakdownTab';
import {
  useAdoptionMetrics,
  useAdoptionOverview,
  useTopGPTs,
  useTopUsers,
  DailyMetric,
  TopUserInfo,
} from '../../hooks/useAdoption';
import { useAuth } from '../../contexts/AuthContext';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Date range presets for the DS DateRangePicker
const DATE_RANGE_PRESETS: { label: string; range: DSDateRange }[] = [
  { 
    label: 'Last 7 days', 
    range: { 
      from: startOfDay(subDays(new Date(), 7)), 
      to: endOfDay(new Date()) 
    } 
  },
  { 
    label: 'Last 30 days', 
    range: { 
      from: startOfDay(subDays(new Date(), 30)), 
      to: endOfDay(new Date()) 
    } 
  },
  { 
    label: 'Last 90 days', 
    range: { 
      from: startOfDay(subDays(new Date(), 90)), 
      to: endOfDay(new Date()) 
    } 
  },
];

type TabType = 'overview' | 'gpts' | 'companies';

interface AdoptionSettingsSummary {
  last_synced_at: string | null;
}

export function AdoptionDashboardPage() {
  const { hasPermission } = useAuth();
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | 'all'>('all');
  const [dateRange, setDateRange] = useState<DSDateRange>({
    from: startOfDay(subDays(new Date(), 30)),
    to: endOfDay(new Date()),
  });
  const [showSharing, setShowSharing] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const { data: adoptionSettings } = useQuery({
    queryKey: ['adoption-settings-summary'],
    queryFn: async () => {
      const response = await AXIOS_INSTANCE.get<AdoptionSettingsSummary>('/api/v1/admin/adoption-settings');
      return response.data;
    },
  });

  // Format dates for API calls
  const startDateStr = dateRange.from ? format(dateRange.from, 'yyyy-MM-dd') : '';
  const endDateStr = dateRange.to ? format(dateRange.to, 'yyyy-MM-dd') : '';

  // Fetch data
  const { data: overview, isLoading: overviewLoading } = useAdoptionOverview();
  const { data: metrics, isLoading: metricsLoading } = useAdoptionMetrics({
    companyId: selectedCompanyId === 'all' ? undefined : selectedCompanyId,
    startDate: startDateStr,
    endDate: endDateStr,
  });

  // Fetch top GPTs from granular conversation data
  const { data: topGPTsData, isLoading: isLoadingGPTs } = useTopGPTs({
    companyId: selectedCompanyId === 'all' ? undefined : selectedCompanyId,
    startDate: startDateStr,
    endDate: endDateStr,
    limit: 50,
  });

  // Fetch top users
  const { data: topUsersData, isLoading: isLoadingUsers } = useTopUsers({
    companyId: selectedCompanyId === 'all' ? undefined : selectedCompanyId,
    startDate: startDateStr,
    endDate: endDateStr,
    limit: 10,
  });

  // Aggregate metrics across all companies if "all" is selected
  const aggregatedMetrics = useMemo(() => {
    if (!metrics || !Array.isArray(metrics) || metrics.length === 0) return null;

    const dailyMap = new Map<string, DailyMetric>();
    
    for (const companyMetrics of metrics) {
      for (const day of companyMetrics.metrics) {
        const existing = dailyMap.get(day.date);
        if (existing) {
          dailyMap.set(day.date, {
            date: day.date,
            active_users: existing.active_users + day.active_users,
            total_conversations: existing.total_conversations + day.total_conversations,
            total_messages: existing.total_messages + day.total_messages,
          });
        } else {
          dailyMap.set(day.date, { 
            date: day.date,
            active_users: day.active_users,
            total_conversations: day.total_conversations,
            total_messages: day.total_messages,
          });
        }
      }
    }

    const allDays = Array.from(dailyMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );

    const avgDailyUsers = allDays.length > 0
      ? allDays.reduce((sum, d) => sum + d.active_users, 0) / allDays.length
      : 0;
    
    const totalConversations = metrics.reduce((sum, m) => sum + (m.summary?.total_conversations || 0), 0);
    const totalMessages = metrics.reduce((sum, m) => sum + (m.summary?.total_messages || 0), 0);

    const summary = {
      total_conversations: totalConversations,
      total_messages: totalMessages,
      avg_daily_users: avgDailyUsers,
      avg_conversations_per_user: avgDailyUsers > 0 ? totalConversations / (avgDailyUsers * allDays.length) : 0,
    };

    return {
      metrics: allDays,
      summary,
    };
  }, [metrics]);

  // Transform GPTs to GPTInfo format
  const aggregatedTopGPTs: GPTInfo[] = useMemo(() => {
    if (!topGPTsData?.gpts) return [];
    return topGPTsData.gpts;
  }, [topGPTsData]);

  // Transform users to TopUserInfo format
  const topUsers: TopUserInfo[] = useMemo(() => {
    if (!topUsersData?.users) return [];
    return topUsersData.users;
  }, [topUsersData]);

  const isLoading = overviewLoading || metricsLoading;
  const canManageSharing = hasPermission('adoption:manage_sharing');
  const isEmptyDashboard = !isLoading && (!aggregatedMetrics || (aggregatedMetrics.summary?.total_conversations || 0) === 0);
  const lastSyncedLabel = adoptionSettings?.last_synced_at
    ? new Date(adoptionSettings.last_synced_at).toLocaleString()
    : 'Not synced yet';

  return (
    <Layout>
      <Page maxWidth="xl">
        {/* Header */}
        <PageHeader
          title="Adoption Dashboard"
          description="Track AI usage and adoption across your organization"
          actions={
            <div className="flex items-center gap-2">
              <Link to="/admin/adoption-settings">
                <Button variant="secondary">
                  <ArrowPathIcon className="h-4 w-4" />
                  Last synced: {lastSyncedLabel}
                </Button>
              </Link>
              {canManageSharing && (
                <Button
                  variant={showSharing ? 'brand' : 'secondary'}
                  onClick={() => setShowSharing(!showSharing)}
                >
                  <ShareIcon className="h-4 w-4" />
                  Sharing
                </Button>
              )}
            </div>
          }
        />

        <PageBody>
          {/* Filters Row */}
          <div className="flex items-center gap-4 mb-8">
            {/* Company Selector */}
            <div className="flex-shrink-0">
              <CompanySelector
                companies={overview || []}
                selectedCompanyId={selectedCompanyId}
                onSelect={setSelectedCompanyId}
                loading={overviewLoading}
              />
            </div>

            {/* Date Range Picker */}
            <div className="flex-shrink-0">
              <DSDateRangePicker
                value={dateRange}
                onChange={setDateRange}
                presets={DATE_RANGE_PRESETS}
                className="w-[260px]"
              />
            </div>

            {/* Spacer to push tabs right */}
            <div className="flex-1" />

            {/* Tabs - right side */}
            <div className="flex-shrink-0">
              <Tabs
                defaultValue="overview"
                value={activeTab}
                onValueChange={(value) => setActiveTab(value as TabType)}
              >
                <TabsList>
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="gpts">GPT Breakdown</TabsTrigger>
                  <TabsTrigger value="companies">Company Breakdown</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
          {/* Sharing Panel (Conditional) */}
          {showSharing && (
            <div className="mb-8">
              <SharingManager onClose={() => setShowSharing(false)} />
            </div>
          )}

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-8">
              {isEmptyDashboard && (
                <Panel>
                  <PanelHeader>
                    <PanelTitle>Set up Adoption Sync</PanelTitle>
                    <PanelDescription>
                      No adoption metrics have been synced yet. Configure your sync settings and run your first sync.
                    </PanelDescription>
                  </PanelHeader>
                  <PanelBody className="flex justify-center">
                    <Link to="/admin/adoption-settings">
                      <Button>Open Adoption Settings</Button>
                    </Link>
                  </PanelBody>
                </Panel>
              )}
              {/* Summary Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <MetricCard
                  title="Avg Daily Users"
                  value={Math.round(aggregatedMetrics?.summary?.avg_daily_users || 0)}
                  icon="users"
                  color="brand"
                  loading={isLoading}
                  subtitle={`${aggregatedMetrics?.metrics?.length || 0} days tracked`}
                  tooltip="Average number of unique users who sent at least one message per day during the selected period."
                />
                <MetricCard
                  title="Total Conversations"
                  value={aggregatedMetrics?.summary?.total_conversations || 0}
                  icon="conversations"
                  color="info"
                  loading={isLoading}
                  subtitle={`${(aggregatedMetrics?.summary?.avg_conversations_per_user || 0).toFixed(1)} per user`}
                  tooltip="Total number of chat sessions (conversations) started during the selected period. Each conversation can contain multiple messages."
                />
                <MetricCard
                  title="Total Messages"
                  value={aggregatedMetrics?.summary?.total_messages || 0}
                  icon="messages"
                  color="success"
                  loading={isLoading}
                  subtitle="User messages only"
                  tooltip="Total number of messages sent by users (not including AI assistant responses). This counts only user prompts and questions."
                />
              </div>

              {/* Main Chart */}
              <UsageChart
                data={aggregatedMetrics?.metrics || []}
                metricType="users"
                title="Active Users Over Time"
                loading={isLoading}
                height={350}
                infoTooltip="Unique users who sent at least one message per day. This is a daily count (not cumulative)."
              />

              {/* Secondary Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <UsageChart
                  data={aggregatedMetrics?.metrics || []}
                  metricType="conversations"
                  title="Conversations Over Time"
                  loading={isLoading}
                  height={250}
                  infoTooltip="Number of conversations with activity on each day. A conversation is counted if a user sent at least one message on that day."
                />
                <UsageChart
                  data={aggregatedMetrics?.metrics || []}
                  metricType="messages"
                  title="Messages Over Time"
                  loading={isLoading}
                  height={250}
                  infoTooltip="Total user messages sent per day. This only counts user prompts, not AI responses."
                />
              </div>

              {/* GPT Insights & Top Users Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* GPT Adoption Rate */}
                <GPTAdoptionChart
                  gptConversations={
                    metrics?.reduce((sum, m) => sum + (m.summary?.gpt_conversations || 0), 0) || 0
                  }
                  baseConversations={
                    metrics?.reduce((sum, m) => sum + (m.summary?.base_conversations || 0), 0) || 0
                  }
                  loading={isLoading}
                />
                
                {/* Top Users */}
                <TopUsersList
                  users={topUsers}
                  loading={isLoadingUsers}
                  maxItems={3}
                  showCompanyName={selectedCompanyId === 'all'}
                />
              </div>
            </div>
          )}

          {/* GPT Breakdown Tab */}
          {activeTab === 'gpts' && (
            <GPTBreakdownTab
              gpts={aggregatedTopGPTs}
              loading={isLoadingGPTs}
              showCompanyName={selectedCompanyId === 'all'}
            />
          )}

          {/* Company Breakdown Tab */}
          {activeTab === 'companies' && (
            <div className="space-y-6">
              <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200 dark:border-dark-border">
                  <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">Company Breakdown</h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                    Detailed metrics for each accessible company
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-gray-50 dark:bg-dark-surface-2">
                        <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Company
                        </th>
                        <th className="text-right px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Avg Daily Users
                        </th>
                        <th className="text-right px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Conversations
                        </th>
                        <th className="text-right px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Messages
                        </th>
                        <th className="text-right px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-dark-border">
                      {isLoading ? (
                        [...Array(3)].map((_, i) => (
                          <tr key={i}>
                            <td colSpan={5} className="px-6 py-4">
                              <Skeleton variant="text" height={24} />
                            </td>
                          </tr>
                        ))
                      ) : overview && overview.length > 0 ? (
                        overview.map((company) => {
                          const companyMetrics = metrics?.find(
                            (m) => m.company_id === company.company_id
                          );
                          return (
                            <tr
                              key={company.company_id}
                              className="hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
                            >
                              <td className="px-6 py-4">
                                <div className="flex items-center gap-3">
                                  <div className="font-medium text-charcoal dark:text-gray-100">
                                    {company.company_name}
                                  </div>
                                  {company.is_own_tenant && (
                                    <Badge variant="success">Your Tenant</Badge>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-4 text-right text-charcoal dark:text-gray-100 font-medium">
                                {Math.round(companyMetrics?.summary?.avg_daily_users || 0).toLocaleString()}
                              </td>
                              <td className="px-6 py-4 text-right text-charcoal dark:text-gray-100 font-medium">
                                {(companyMetrics?.summary?.total_conversations || 0).toLocaleString()}
                              </td>
                              <td className="px-6 py-4 text-right text-charcoal dark:text-gray-100 font-medium">
                                {(companyMetrics?.summary?.total_messages || 0).toLocaleString()}
                              </td>
                              <td className="px-6 py-4 text-right">
                                <Badge variant={company.has_adoption_enabled ? 'success' : 'default'}>
                                  {company.has_adoption_enabled ? 'Active' : 'Not Configured'}
                                </Badge>
                              </td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={5} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                            No companies available. Configure adoption data sources to get started.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </PageBody>
      </Page>
    </Layout>
  );
}

export default AdoptionDashboardPage;

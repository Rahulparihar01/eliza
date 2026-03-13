/**
 * Adoption Dashboard Hooks
 * 
 * Custom hooks for fetching adoption metrics, shares, and providers
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AXIOS_INSTANCE } from '../services/api-client';

// Types
export interface DailyMetric {
  date: string;
  customer_id?: string;
  provider_type?: string;
  active_users: number;
  total_conversations: number;
  total_messages: number;
  // Token fields - optional as not available from Compliance API
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
}

export interface GPTUsageInfo {
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

export interface TopUserInfo {
  user_email: string;
  user_external_id?: string;
  total_conversations: number;
  total_messages: number;
  gpts_used: number;
  company_id?: string;
  company_name?: string;
}

export interface TopUsersResponse {
  users: TopUserInfo[];
  total_count: number;
  start_date: string | null;
  end_date: string | null;
}

export interface AdoptionMetricsSummary {
  total_active_users?: number;  // Deprecated - use avg_daily_users instead
  total_conversations: number;
  total_messages: number;
  total_tokens?: number;  // Not available from Compliance API
  avg_daily_users: number;
  avg_conversations_per_user?: number;
  // GPT adoption metrics
  gpt_conversations?: number;  // Conversations using custom GPTs
  base_conversations?: number;  // Conversations using base ChatGPT
  gpt_adoption_rate?: number;  // Percentage: gpt_conversations / total_conversations * 100
  top_gpts?: GPTUsageInfo[];
}

export interface AdoptionMetricsResponse {
  company_id: string;
  start_date: string;
  end_date: string;
  metrics: DailyMetric[];
  summary: AdoptionMetricsSummary;
}

export interface CompanyOverview {
  company_id: string;
  company_name: string;
  is_own_tenant: boolean;
  has_adoption_enabled: boolean;
  last_sync_at: string | null;
  metrics_summary: AdoptionMetricsSummary | null;
}

export interface AdoptionShare {
  id: number;
  source_company_id: string;
  target_company_id: string;
  shared_by_user_id: number;
  permission_level: 'read' | 'admin';
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface AdoptionProvider {
  id: number;
  customer_id: string;
  provider_name: string;
  name: string | null;
  is_enabled: boolean;
  is_adoption_source: boolean;
  chatgpt_workspace_id: string | null;
  last_sync_at: string | null;
}

export interface DashboardWidget {
  widget_type: 'summary' | 'trend_chart' | 'company_comparison' | 'recent_activity';
  title: string;
  data: Record<string, unknown>;
}

export interface DashboardResponse {
  widgets: DashboardWidget[];
  accessible_companies: string[];
  last_updated: string;
}

// Top GPTs response from new granular API
export interface TopGPTsResponse {
  gpts: GPTUsageInfo[];
  total_count: number;
  start_date: string | null;
  end_date: string | null;
}

// Query Keys
export const adoptionQueryKeys = {
  all: ['adoption'] as const,
  metrics: (companyId?: string, startDate?: string, endDate?: string) => 
    ['adoption', 'metrics', { companyId, startDate, endDate }] as const,
  overview: () => ['adoption', 'overview'] as const,
  dashboard: () => ['adoption', 'dashboard'] as const,
  shares: () => ['adoption', 'shares'] as const,
  providers: () => ['adoption', 'providers'] as const,
  topGpts: (companyId?: string, startDate?: string, endDate?: string) =>
    ['adoption', 'topGpts', { companyId, startDate, endDate }] as const,
  topUsers: (companyId?: string, startDate?: string, endDate?: string) =>
    ['adoption', 'topUsers', { companyId, startDate, endDate }] as const,
};

// Hooks

/**
 * Fetch adoption metrics for accessible companies
 */
export function useAdoptionMetrics(options?: {
  companyId?: string;
  startDate?: string;
  endDate?: string;
}) {
  return useQuery({
    queryKey: adoptionQueryKeys.metrics(options?.companyId, options?.startDate, options?.endDate),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (options?.companyId) params.append('company_id', options.companyId);
      if (options?.startDate) params.append('start_date', options.startDate);
      if (options?.endDate) params.append('end_date', options.endDate);
      
      const { data } = await AXIOS_INSTANCE.get<AdoptionMetricsResponse[]>(
        `/v1/adoption/metrics?${params.toString()}`
      );
      return data;
    },
  });
}

/**
 * Fetch company overview for adoption dashboard
 */
export function useAdoptionOverview() {
  return useQuery({
    queryKey: adoptionQueryKeys.overview(),
    queryFn: async () => {
      const { data } = await AXIOS_INSTANCE.get<{ companies: CompanyOverview[]; total_companies: number; companies_with_data: number }>('/v1/adoption/overview');
      // API returns { companies: [...], total_companies, companies_with_data }
      // We just need the companies array for the component
      return data.companies;
    },
  });
}

/**
 * Fetch dashboard widgets with pre-aggregated data
 */
export function useAdoptionDashboard() {
  return useQuery({
    queryKey: adoptionQueryKeys.dashboard(),
    queryFn: async () => {
      const { data } = await AXIOS_INSTANCE.get<DashboardResponse>('/v1/adoption/dashboard');
      return data;
    },
  });
}

/**
 * Fetch adoption shares (for sharing management)
 */
export function useAdoptionShares() {
  return useQuery({
    queryKey: adoptionQueryKeys.shares(),
    queryFn: async () => {
      const { data } = await AXIOS_INSTANCE.get<AdoptionShare[]>('/v1/adoption/shares');
      return data;
    },
  });
}

/**
 * Fetch adoption providers (AI providers configured for adoption)
 */
export function useAdoptionProviders() {
  return useQuery({
    queryKey: adoptionQueryKeys.providers(),
    queryFn: async () => {
      const { data } = await AXIOS_INSTANCE.get<AdoptionProvider[]>('/v1/adoption/providers');
      return data;
    },
  });
}

/**
 * Fetch top GPTs with usage metrics from granular conversation data
 */
export function useTopGPTs(options?: {
  companyId?: string;
  startDate?: string;
  endDate?: string;
  days?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: adoptionQueryKeys.topGpts(options?.companyId, options?.startDate, options?.endDate),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (options?.companyId) params.append('customer_id', options.companyId);
      if (options?.startDate) params.append('start_date', options.startDate);
      if (options?.endDate) params.append('end_date', options.endDate);
      if (options?.days) params.append('days', options.days.toString());
      if (options?.limit) params.append('limit', options.limit.toString());
      
      const { data } = await AXIOS_INSTANCE.get<TopGPTsResponse>(
        `/v1/adoption/gpts/top?${params.toString()}`
      );
      return data;
    },
  });
}

/**
 * Fetch top users by ChatGPT usage
 */
export function useTopUsers(options?: {
  companyId?: string;
  startDate?: string;
  endDate?: string;
  days?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: adoptionQueryKeys.topUsers(options?.companyId, options?.startDate, options?.endDate),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (options?.companyId) params.append('customer_id', options.companyId);
      if (options?.startDate) params.append('start_date', options.startDate);
      if (options?.endDate) params.append('end_date', options.endDate);
      if (options?.days) params.append('days', options.days.toString());
      if (options?.limit) params.append('limit', options.limit.toString());
      
      const { data } = await AXIOS_INSTANCE.get<TopUsersResponse>(
        `/v1/adoption/users/top?${params.toString()}`
      );
      return data;
    },
  });
}

/**
 * Create a new adoption share
 */
export function useCreateAdoptionShare() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (shareData: {
      target_company_id: string;
      permission_level?: 'read' | 'admin';
      expires_at?: string;
    }) => {
      const { data } = await AXIOS_INSTANCE.post<AdoptionShare>('/v1/adoption/shares', shareData);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adoptionQueryKeys.shares() });
    },
  });
}

/**
 * Update an adoption share
 */
export function useUpdateAdoptionShare() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, ...updates }: {
      id: number;
      permission_level?: 'read' | 'admin';
      is_active?: boolean;
      expires_at?: string | null;
    }) => {
      const { data } = await AXIOS_INSTANCE.patch<AdoptionShare>(`/v1/adoption/shares/${id}`, updates);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adoptionQueryKeys.shares() });
    },
  });
}

/**
 * Delete an adoption share
 */
export function useDeleteAdoptionShare() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id: number) => {
      await AXIOS_INSTANCE.delete(`/v1/adoption/shares/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adoptionQueryKeys.shares() });
    },
  });
}

/**
 * Enable a provider for adoption data collection
 */
export function useEnableAdoptionProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (providerId: number) => {
      const { data } = await AXIOS_INSTANCE.post<AdoptionProvider>(
        `/v1/adoption/providers/${providerId}/enable`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adoptionQueryKeys.providers() });
    },
  });
}

/**
 * Disable a provider for adoption data collection
 */
export function useDisableAdoptionProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (providerId: number) => {
      const { data } = await AXIOS_INSTANCE.post<AdoptionProvider>(
        `/v1/adoption/providers/${providerId}/disable`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adoptionQueryKeys.providers() });
    },
  });
}

/**
 * Trigger a manual sync for adoption data
 */
export function useTriggerAdoptionSync() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (options?: { provider_id?: number }) => {
      const { data } = await AXIOS_INSTANCE.post<{ message: string; task_id: string }>(
        '/v1/adoption/sync',
        options || {}
      );
      return data;
    },
    onSuccess: () => {
      // Invalidate metrics after sync is triggered
      queryClient.invalidateQueries({ queryKey: adoptionQueryKeys.all });
    },
  });
}


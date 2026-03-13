/**
 * Generated API client for Talent Intelligence
 * Manually created based on backend routes in src/api/routes/talent.py
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import type { UseMutationOptions, UseQueryOptions } from '@tanstack/react-query';
import { customInstance } from '../../services/api-client';

// Types
export interface TalentAnalysisRequest {
  job_description?: string;
  ideal_candidate_description?: string;
  manual_persona?: Record<string, any>;
}

export interface TalentAnalysisResponse {
  analysis_id: string;
  status: string;
  message: string;
}

export interface TalentAnalysisResult {
  analysis_id: string;
  customer_id: string;
  status: string;
  created_at: string;
  completed_at?: string;
  job_description?: string;
  ideal_candidate_description?: string;
  ideal_persona?: Record<string, any>;
  candidates?: any[];
  insights_report?: Record<string, any>;
  error?: string;
}

export interface TalentAnalysisListResponse {
  total: number;
  analyses: Array<{
    analysis_id: string;
    status: string;
    created_at: string;
    completed_at?: string;
    candidate_count: number;
  }>;
}

// API Functions
export const startTalentAnalysis = (
  data: TalentAnalysisRequest
): Promise<TalentAnalysisResponse> => {
  return customInstance({
    url: '/api/talent/analyze',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    data,
  });
};

export const getTalentAnalysis = (
  analysisId: string
): Promise<TalentAnalysisResult> => {
  return customInstance({
    url: `/api/talent/analysis/${analysisId}`,
    method: 'GET',
  });
};

export const listTalentAnalyses = (params?: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<TalentAnalysisListResponse> => {
  return customInstance({
    url: '/api/talent/analyses',
    method: 'GET',
    params,
  });
};

// React Query Hooks
export const useStartTalentAnalysis = <TError = unknown, TContext = unknown>(
  options?: UseMutationOptions<
    TalentAnalysisResponse,
    TError,
    TalentAnalysisRequest,
    TContext
  >
) => {
  return useMutation<TalentAnalysisResponse, TError, TalentAnalysisRequest, TContext>(
    {
      mutationFn: (data: TalentAnalysisRequest) => startTalentAnalysis(data),
      ...options,
    }
  );
};

export const useGetTalentAnalysis = <TError = unknown>(
  analysisId: string,
  options?: Omit<UseQueryOptions<TalentAnalysisResult, TError>, 'queryKey' | 'queryFn'>
) => {
  return useQuery<TalentAnalysisResult, TError>({
    queryKey: ['talent', 'analysis', analysisId],
    queryFn: () => getTalentAnalysis(analysisId),
    enabled: !!analysisId,
    ...options,
  });
};

export const useListTalentAnalyses = <TError = unknown>(
  params?: { limit?: number; offset?: number; status?: string },
  options?: Omit<UseQueryOptions<TalentAnalysisListResponse, TError>, 'queryKey' | 'queryFn'>
) => {
  return useQuery<TalentAnalysisListResponse, TError>({
    queryKey: ['talent', 'analyses', params],
    queryFn: () => listTalentAnalyses(params),
    ...options,
  });
};


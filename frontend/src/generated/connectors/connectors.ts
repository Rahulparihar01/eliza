/**
 * Generated connector API client
 * 
 * NOTE: This file should be regenerated using orval from the OpenAPI spec.
 * Current version is manually created to match backend routes in:
 * - src/api/routes/connectors.py
 * 
 * To regenerate properly:
 * 1. Start backend: docker-compose up app
 * 2. Run: cd frontend && npm run generate:api
 * 
 * TODO: Regenerate with orval once Docker is available
 */

import { useQuery, useMutation, UseQueryOptions, UseMutationOptions, useQueryClient } from '@tanstack/react-query';
import { customInstance } from '../../services/api-client';
import { queryKeys } from '../../lib/query-keys';
import type { AxiosRequestConfig } from 'axios';

// ===== Enums =====

export enum ConnectorType {
  PEOPLE_DATA_LABS = 'people_data_labs',
  GREENHOUSE = 'greenhouse',
  LEVER = 'lever',
  WORKDAY = 'workday',
  BAMBOOHR = 'bamboohr',
  FILESYSTEM = 'filesystem',
  SALESFORCE = 'salesforce',
  HUBSPOT = 'hubspot',
  FATHOM = 'fathom',
  CUSTOM = 'custom',
}

export enum SyncMode {
  FULL_REFRESH = 'full_refresh',
  INCREMENTAL = 'incremental',
}

export enum SyncStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

// ===== Models =====

export interface ConnectorConfiguration {
  id: number;
  customer_id: string;
  connector_id: string;
  connector_name: string;
  connector_type: ConnectorType;
  use_shared_credentials: boolean;
  credentials_encrypted: string;
  sync_config: Record<string, any>;
  sync_mode: SyncMode;
  is_enabled: boolean;
  description?: string;
  tags?: string[];
  created_by_user_id: number;
  sync_schedule?: string;
  created_at: string;
  updated_at: string | null;
}

export interface ConnectorHealth {
  status: 'healthy' | 'unhealthy';
  message: string;
  metadata?: Record<string, any>;
}

export interface ConnectorSyncRun {
  id: number;
  sync_id: string;
  connector_id: number;
  customer_id: string;
  celery_task_id?: string;
  sync_mode: SyncMode;
  triggered_by: string;
  status: SyncStatus;
  started_at?: string;
  completed_at?: string;
  records_extracted: number;
  records_loaded: number;
  records_skipped: number;
  records_failed: number;
  checkpoint_before?: Record<string, any>;
  checkpoint_after?: Record<string, any>;
  error_message?: string;
  error_details?: Record<string, any>;
  duration_seconds?: number;
  api_calls_made: number;
  bytes_transferred: number;
  cost_incurred: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectorStatistics {
  total_records_ingested: number;
  total_sync_runs: number;
  successful_sync_runs: number;
  failed_sync_runs: number;
  last_successful_sync?: string;
  average_records_per_sync: number;
  average_duration_seconds: number;
  total_cost_incurred: number;
}

export interface ConnectorTelemetryEvent {
  id: number;
  sync_id: string;
  customer_id: string;
  event_type: string;
  progress_percentage?: number;
  current_stage?: string;
  records_processed?: number;
  api_calls_made?: number;
  cost_so_far?: number;
  user_message?: string;
  telemetry_metadata?: Record<string, any>;
  created_at: string;
}

export interface ConnectorTypeInfo {
  connector_type: string;
  display_name: string;
  description: string;
  required_credentials: string[];
  optional_config: Record<string, any>;
  supports_incremental: boolean;
  supports_scheduling: boolean;
}

// ===== Request Schemas =====

export interface CreateConnectorRequest {
  connector_name: string;
  connector_type: ConnectorType;
  credentials: Record<string, any>;
  sync_config?: Record<string, any>;
  sync_mode?: SyncMode;
  description?: string;
  tags?: string[];
  use_shared_credentials?: boolean;
  sync_schedule?: string;
}

export interface UpdateConnectorRequest {
  connector_name?: string;
  credentials?: Record<string, any>;
  sync_config?: Record<string, any>;
  sync_mode?: SyncMode;
  description?: string;
  tags?: string[];
  is_enabled?: boolean;
  sync_schedule?: string;
}

export interface TriggerSyncRequest {
  sync_mode?: SyncMode;
  sync_params?: Record<string, any>;
}

export interface ValidateConfigRequest {
  connector_type: ConnectorType;
  credentials: Record<string, any>;
  sync_config?: Record<string, any>;
}

export interface TestConnectionRequest {
  connector_type: ConnectorType;
  credentials: Record<string, any>;
}

export interface EstimateCostRequest {
  connector_type: ConnectorType;
  credentials: Record<string, any>;
  query_params?: Record<string, any>;
}

// ===== Response Schemas =====

export interface ConnectorListResponse {
  total: number;
  connectors: ConnectorConfiguration[];
}

export interface SyncRunListResponse {
  total: number;
  sync_runs: ConnectorSyncRun[];
}

export interface TelemetryListResponse {
  total: number;
  events: ConnectorTelemetryEvent[];
}

export interface ConnectorTypesListResponse {
  total: number;
  connector_types: ConnectorTypeInfo[];
}

export interface ValidateConfigResponse {
  valid: boolean;
  message: string;
  errors?: string[];
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  metadata?: Record<string, any>;
}

export interface EstimateCostResponse {
  estimated_record_count: number;
  estimated_cost: number;
  estimated_duration_seconds: number;
  warnings?: string[];
}

// ===== API Functions =====
// Base path: /api/connectors

export const listConnectors = (
  params?: { connector_type?: string; is_enabled?: boolean },
  options?: AxiosRequestConfig
): Promise<ConnectorListResponse> => {
  return customInstance<ConnectorListResponse>({
    url: '/api/connectors/configurations',
    method: 'GET',
    params,
    ...options,
  });
};

export const getConnector = (
  connectorId: string,
  options?: AxiosRequestConfig
): Promise<ConnectorConfiguration> => {
  return customInstance<ConnectorConfiguration>({
    url: `/api/connectors/configurations/${connectorId}`,
    method: 'GET',
    ...options,
  });
};

export const getConnectorPreview = (
  connectorId: string,
  options?: AxiosRequestConfig
): Promise<any> => {
  return customInstance<any>({
    url: `/api/connectors/configurations/${connectorId}/preview`,
    method: 'GET',
    ...options,
  });
};

export const createConnector = (
  data: CreateConnectorRequest,
  options?: AxiosRequestConfig
): Promise<ConnectorConfiguration> => {
  return customInstance<ConnectorConfiguration>({
    url: '/api/connectors/configurations',
    method: 'POST',
    data,
    ...options,
  });
};

export const updateConnector = (
  connectorId: string,
  data: UpdateConnectorRequest,
  options?: AxiosRequestConfig
): Promise<ConnectorConfiguration> => {
  return customInstance<ConnectorConfiguration>({
    url: `/api/connectors/configurations/${connectorId}`,
    method: 'PUT',
    data,
    ...options,
  });
};

export const deleteConnector = (
  connectorId: string,
  options?: AxiosRequestConfig
): Promise<void> => {
  return customInstance<void>({
    url: `/api/connectors/configurations/${connectorId}`,
    method: 'DELETE',
    ...options,
  });
};

export const triggerSync = (
  connectorId: string,
  data: TriggerSyncRequest,
  options?: AxiosRequestConfig
): Promise<ConnectorSyncRun> => {
  return customInstance<ConnectorSyncRun>({
    url: `/api/connectors/configurations/${connectorId}/trigger-sync`,
    method: 'POST',
    data,
    ...options,
  });
};

export const getConnectorStatistics = (
  connectorId: string,
  options?: AxiosRequestConfig
): Promise<ConnectorStatistics> => {
  return customInstance<ConnectorStatistics>({
    url: `/api/connectors/configurations/${connectorId}/statistics`,
    method: 'GET',
    ...options,
  });
};

export const listSyncRuns = (
  params?: { connector_id?: string; status?: SyncStatus; limit?: number; offset?: number },
  options?: AxiosRequestConfig
): Promise<SyncRunListResponse> => {
  return customInstance<SyncRunListResponse>({
    url: '/api/connectors/sync-runs',
    method: 'GET',
    params,
    ...options,
  });
};

export const getSyncRun = (
  syncId: string,
  options?: AxiosRequestConfig
): Promise<ConnectorSyncRun> => {
  return customInstance<ConnectorSyncRun>({
    url: `/api/connectors/sync-runs/${syncId}`,
    method: 'GET',
    ...options,
  });
};

export const getSyncTelemetry = (
  syncId: string,
  params?: { event_type?: string; limit?: number },
  options?: AxiosRequestConfig
): Promise<TelemetryListResponse> => {
  return customInstance<TelemetryListResponse>({
    url: `/api/connectors/sync-runs/${syncId}/telemetry`,
    method: 'GET',
    params,
    ...options,
  });
};

export const listConnectorTypes = (
  options?: AxiosRequestConfig
): Promise<ConnectorTypesListResponse> => {
  return customInstance<ConnectorTypesListResponse>({
    url: '/api/connectors/types',
    method: 'GET',
    ...options,
  });
};

export const validateConfig = (
  data: ValidateConfigRequest,
  options?: AxiosRequestConfig
): Promise<ValidateConfigResponse> => {
  return customInstance<ValidateConfigResponse>({
    url: '/api/connectors/validate-config',
    method: 'POST',
    data,
    ...options,
  });
};

export const testConnection = (
  data: TestConnectionRequest,
  options?: AxiosRequestConfig
): Promise<TestConnectionResponse> => {
  return customInstance<TestConnectionResponse>({
    url: '/api/connectors/test-connection',
    method: 'POST',
    data,
    ...options,
  });
};

export const estimateCost = (
  data: EstimateCostRequest,
  options?: AxiosRequestConfig
): Promise<EstimateCostResponse> => {
  return customInstance<EstimateCostResponse>({
    url: '/api/connectors/estimate-cost',
    method: 'POST',
    data,
    ...options,
  });
};

// ===== React Query Hooks =====

// List Connectors
export const useListConnectors = <TData = ConnectorListResponse>(
  params?: { connector_type?: string; is_enabled?: boolean },
  options?: { query?: Omit<UseQueryOptions<ConnectorListResponse, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<ConnectorListResponse, Error, TData>({
    queryKey: [...queryKeys.connectors.lists(), params] as const,
    queryFn: () => listConnectors(params, options?.request),
    ...options?.query,
  });
};

// Get Single Connector
export const useGetConnector = <TData = ConnectorConfiguration>(
  connectorId: string,
  options?: { query?: Omit<UseQueryOptions<ConnectorConfiguration, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<ConnectorConfiguration, Error, TData>({
    queryKey: queryKeys.connectors.detail(connectorId),
    queryFn: () => getConnector(connectorId, options?.request),
    enabled: !!connectorId,
    ...options?.query,
  });
};

// Get Connector Preview
export const useGetConnectorPreview = <TData = any>(
  connectorId: string,
  options?: { query?: Omit<UseQueryOptions<any, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<any, Error, TData>({
    queryKey: [...queryKeys.connectors.detail(connectorId), 'preview'],
    queryFn: () => getConnectorPreview(connectorId, options?.request),
    enabled: !!connectorId,
    ...options?.query,
  });
};

// Create Connector
export const useCreateConnector = (
  options?: { mutation?: UseMutationOptions<ConnectorConfiguration, Error, CreateConnectorRequest>, request?: AxiosRequestConfig }
) => {
  const queryClient = useQueryClient();
  return useMutation<ConnectorConfiguration, Error, CreateConnectorRequest>({
    mutationFn: (data) => createConnector(data, options?.request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.connectors.lists() });
    },
    ...options?.mutation,
  });
};

// Update Connector
export const useUpdateConnector = (
  connectorId: string,
  options?: { mutation?: UseMutationOptions<ConnectorConfiguration, Error, UpdateConnectorRequest>, request?: AxiosRequestConfig }
) => {
  const queryClient = useQueryClient();
  return useMutation<ConnectorConfiguration, Error, UpdateConnectorRequest>({
    mutationFn: (data) => updateConnector(connectorId, data, options?.request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.connectors.detail(Number(connectorId)) });
      queryClient.invalidateQueries({ queryKey: queryKeys.connectors.lists() });
    },
    ...options?.mutation,
  });
};

// Delete Connector
export const useDeleteConnector = (
  options?: { mutation?: UseMutationOptions<void, Error, string>, request?: AxiosRequestConfig }
) => {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (connectorId) => deleteConnector(connectorId, options?.request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.connectors.lists() });
    },
    ...options?.mutation,
  });
};

// Trigger Sync
export const useTriggerSync = (
  connectorId: string,
  options?: { mutation?: UseMutationOptions<ConnectorSyncRun, Error, TriggerSyncRequest>, request?: AxiosRequestConfig }
) => {
  const queryClient = useQueryClient();
  return useMutation<ConnectorSyncRun, Error, TriggerSyncRequest>({
    mutationFn: (data) => triggerSync(connectorId, data, options?.request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.connectors.syncHistory(connectorId) });
    },
    ...options?.mutation,
  });
};

// Get Statistics
export const useGetConnectorStatistics = <TData = ConnectorStatistics>(
  connectorId: string,
  options?: { query?: Omit<UseQueryOptions<ConnectorStatistics, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<ConnectorStatistics, Error, TData>({
    queryKey: queryKeys.connectors.statistics(connectorId),
    queryFn: () => getConnectorStatistics(connectorId, options?.request),
    enabled: !!connectorId,
    ...options?.query,
  });
};

// List Sync Runs
export const useListSyncRuns = <TData = SyncRunListResponse>(
  params?: { connector_id?: string; status?: SyncStatus; limit?: number; offset?: number },
  options?: { query?: Omit<UseQueryOptions<SyncRunListResponse, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<SyncRunListResponse, Error, TData>({
    queryKey: ['connector-sync-runs', params] as const,
    queryFn: () => listSyncRuns(params, options?.request),
    ...options?.query,
  });
};

// Get Sync Run
export const useGetSyncRun = <TData = ConnectorSyncRun>(
  syncId: string,
  options?: { query?: Omit<UseQueryOptions<ConnectorSyncRun, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<ConnectorSyncRun, Error, TData>({
    queryKey: ['connector-sync-run', syncId],
    queryFn: () => getSyncRun(syncId, options?.request),
    enabled: !!syncId,
    ...options?.query,
  });
};

// Get Sync Telemetry
export const useGetSyncTelemetry = <TData = TelemetryListResponse>(
  syncId: string,
  params?: { event_type?: string; limit?: number },
  options?: { query?: Omit<UseQueryOptions<TelemetryListResponse, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<TelemetryListResponse, Error, TData>({
    queryKey: ['connector-sync-telemetry', syncId, params],
    queryFn: () => getSyncTelemetry(syncId, params, options?.request),
    enabled: !!syncId,
    ...options?.query,
  });
};

// List Connector Types
export const useListConnectorTypes = <TData = ConnectorTypesListResponse>(
  options?: { query?: Omit<UseQueryOptions<ConnectorTypesListResponse, Error, TData>, 'queryKey' | 'queryFn'>, request?: AxiosRequestConfig }
) => {
  return useQuery<ConnectorTypesListResponse, Error, TData>({
    queryKey: ['connector-types'],
    queryFn: () => listConnectorTypes(options?.request),
    ...options?.query,
  });
};

// Validate Config
export const useValidateConfig = (
  options?: { mutation?: UseMutationOptions<ValidateConfigResponse, Error, ValidateConfigRequest>, request?: AxiosRequestConfig }
) => {
  return useMutation<ValidateConfigResponse, Error, ValidateConfigRequest>({
    mutationFn: (data) => validateConfig(data, options?.request),
    ...options?.mutation,
  });
};

// Test Connection
export const useTestConnection = (
  options?: { mutation?: UseMutationOptions<TestConnectionResponse, Error, TestConnectionRequest>, request?: AxiosRequestConfig }
) => {
  return useMutation<TestConnectionResponse, Error, TestConnectionRequest>({
    mutationFn: (data) => testConnection(data, options?.request),
    ...options?.mutation,
  });
};

// Estimate Cost
export const useEstimateCost = (
  options?: { mutation?: UseMutationOptions<EstimateCostResponse, Error, EstimateCostRequest>, request?: AxiosRequestConfig }
) => {
  return useMutation<EstimateCostResponse, Error, EstimateCostRequest>({
    mutationFn: (data) => estimateCost(data, options?.request),
    ...options?.mutation,
  });
};

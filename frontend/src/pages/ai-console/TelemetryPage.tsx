import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  ChatBubbleLeftRightIcon,
  ClockIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

import Layout from '../../components/layout/Layout';
import { WorkspaceSelector } from '../../components/common/RAGDomainSelector';
import { useRAGWorkspaces } from '../../hooks/useRAGDomains';
import { Button, Card, CardContent, Page, PageBody, PageHeader, Spinner } from '../../components/ui';

const API_BASE =
  process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');
const TELEMETRY_POLL_MS = 10000;

interface WorkspaceTelemetryRequest {
  conversation_id: number;
  conversation_uuid: string;
  user_message_id?: number | null;
  assistant_message_id: number;
  request_text?: string | null;
  response_text: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  created_at: string;
  latency_ms?: number | null;
}

interface WorkspaceLangfuseTrace {
  trace_id: string;
  name?: string | null;
  timestamp?: string | null;
  session_id?: string | null;
  user_id?: string | null;
  url?: string | null;
}

interface WorkspaceTelemetryResponse {
  workspace_id: number;
  workspace_name: string;
  langfuse_enabled: boolean;
  langfuse_host?: string | null;
  langfuse_public_url?: string | null;
  langfuse_embed_url?: string | null;
  langfuse_project_id?: string | null;
  recent_requests: WorkspaceTelemetryRequest[];
  traces: WorkspaceLangfuseTrace[];
  traces_fetch_error?: string | null;
}

function truncate(text: string | null | undefined, maxLength = 220): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
}

export default function TelemetryPage() {
  const token = localStorage.getItem('auth_token');
  const [searchParams, setSearchParams] = useSearchParams();
  const [telemetry, setTelemetry] = useState<WorkspaceTelemetryResponse | null>(null);
  const [isLoadingTelemetry, setIsLoadingTelemetry] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    workspaces,
    selectedWorkspace,
    selectedWorkspaceId,
    setSelectedWorkspaceId,
    isLoading: isLoadingWorkspaces,
    error: workspacesError,
    refresh: refreshWorkspaces,
  } = useRAGWorkspaces({ autoSelect: false });

  useEffect(() => {
    const rawWorkspaceId = searchParams.get('workspaceId');
    if (!rawWorkspaceId) return;
    const parsedWorkspaceId = parseInt(rawWorkspaceId, 10);
    if (Number.isNaN(parsedWorkspaceId) || parsedWorkspaceId <= 0) return;
    if (parsedWorkspaceId !== selectedWorkspaceId) {
      setSelectedWorkspaceId(parsedWorkspaceId);
    }
  }, [searchParams, selectedWorkspaceId, setSelectedWorkspaceId]);

  useEffect(() => {
    if (selectedWorkspaceId !== null || workspaces.length === 0) return;
    setSelectedWorkspaceId(workspaces[0].id);
  }, [workspaces, selectedWorkspaceId, setSelectedWorkspaceId]);

  useEffect(() => {
    if (selectedWorkspaceId === null) return;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const selectedWorkspaceText = String(selectedWorkspaceId);
      if (next.get('workspaceId') === selectedWorkspaceText) {
        return prev;
      }
      next.set('workspaceId', selectedWorkspaceText);
      return next;
    }, { replace: true });
  }, [selectedWorkspaceId, setSearchParams]);

  const fetchTelemetry = useCallback(
    async (forceLoading = false) => {
      if (!token) {
        setError('Not authenticated');
        return;
      }
      if (!selectedWorkspaceId) {
        setTelemetry(null);
        return;
      }

      if (forceLoading) {
        setIsLoadingTelemetry(true);
      }

      try {
        setError(null);
        const response = await fetch(`${API_BASE}/v1/workspaces/${selectedWorkspaceId}/telemetry?limit=30`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          const errorBody = await response.text();
          throw new Error(errorBody || `Failed to fetch telemetry (${response.status})`);
        }
        const payload = (await response.json()) as WorkspaceTelemetryResponse;
        setTelemetry(payload);
      } catch (fetchError) {
        const message = fetchError instanceof Error ? fetchError.message : 'Failed to fetch telemetry';
        setError(message);
      } finally {
        if (forceLoading) {
          setIsLoadingTelemetry(false);
        }
      }
    },
    [selectedWorkspaceId, token],
  );

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setTelemetry(null);
      return;
    }

    void fetchTelemetry(true);
    const interval = window.setInterval(() => {
      void fetchTelemetry(false);
    }, TELEMETRY_POLL_MS);

    return () => window.clearInterval(interval);
  }, [selectedWorkspaceId, fetchTelemetry]);

  const requests = telemetry?.recent_requests || [];
  const traces = telemetry?.traces || [];
  const externalLangfuseUrl = telemetry?.langfuse_public_url || telemetry?.langfuse_embed_url || '';

  return (
    <Layout>
      <Page maxWidth="2xl">
        <PageHeader
          title="Telemetry"
          description="Workspace request tracing and Langfuse observability"
          actions={
            <div className="flex items-center gap-2">
              <WorkspaceSelector
                workspaces={workspaces}
                selectedWorkspaceId={selectedWorkspaceId}
                onSelect={setSelectedWorkspaceId}
                isLoading={isLoadingWorkspaces}
                error={workspacesError}
                onRefresh={refreshWorkspaces}
                placeholder="Select workspace"
              />
              <Button variant="outline" size="sm" onClick={() => void fetchTelemetry(true)}>
                <ArrowPathIcon className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
          }
        />

        <PageBody>
          {!selectedWorkspace && !isLoadingWorkspaces && (
            <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">
              Select a workspace to view telemetry.
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-400">
              {error}
            </div>
          )}

          {isLoadingTelemetry && !telemetry && (
            <div className="flex items-center justify-center py-16">
              <Spinner size="lg" />
            </div>
          )}

          {telemetry && (
            <>
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardContent className="p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h2 className="text-base font-medium text-text">Recent Workspace Requests</h2>
                      <span className="text-xs text-muted">{requests.length} captured</span>
                    </div>

                    {requests.length === 0 ? (
                      <div className="rounded-lg border border-border bg-surface-2 p-4 text-sm text-muted">
                        No chat requests captured yet for this workspace.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {requests.map((request) => (
                          <div key={request.assistant_message_id} className="rounded-lg border border-border bg-surface-2 p-3">
                            <div className="mb-2 flex items-center justify-between">
                              <span className="text-xs text-muted">{formatTime(request.created_at)}</span>
                              <div className="flex items-center gap-3 text-xs text-muted">
                                <span>{request.total_tokens} tokens</span>
                                <span>{request.latency_ms ? `${Math.round(request.latency_ms)} ms` : '— ms'}</span>
                              </div>
                            </div>
                            <p className="text-sm text-text">
                              <span className="font-medium text-muted">Q:</span> {truncate(request.request_text, 260)}
                            </p>
                            <p className="mt-1 text-sm text-text">
                              <span className="font-medium text-muted">A:</span> {truncate(request.response_text, 280)}
                            </p>
                            <div className="mt-2 flex items-center justify-between">
                              <span className="text-xs text-muted">
                                Prompt {request.prompt_tokens} / Completion {request.completion_tokens}
                              </span>
                              <Link
                                to={`/chat/${telemetry.workspace_id}/${request.conversation_uuid}`}
                                className="inline-flex items-center gap-1 text-xs text-brand hover:underline"
                              >
                                <ChatBubbleLeftRightIcon className="h-3.5 w-3.5" />
                                Open chat
                              </Link>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-4">
                    <h2 className="mb-3 text-base font-medium text-text">Langfuse</h2>
                    <div className="space-y-2 text-sm text-muted">
                      <div className="flex items-center justify-between">
                        <span>Workspace</span>
                        <span className="font-medium text-text">{telemetry.workspace_name}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Tracing</span>
                        <span className={telemetry.langfuse_enabled ? 'text-emerald-500' : 'text-yellow-500'}>
                          {telemetry.langfuse_enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Traces</span>
                        <span className="font-medium text-text">{traces.length}</span>
                      </div>
                    </div>

                    {telemetry.traces_fetch_error && (
                      <div className="mt-3 rounded-md border border-yellow-500/30 bg-yellow-500/10 p-2 text-xs text-yellow-400">
                        <ExclamationTriangleIcon className="mr-1 inline h-4 w-4" />
                        {telemetry.traces_fetch_error}
                      </div>
                    )}

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {externalLangfuseUrl && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => window.open(externalLangfuseUrl, '_blank', 'noopener,noreferrer')}
                        >
                          <ArrowTopRightOnSquareIcon className="w-4 h-4 mr-2" />
                          Open UI
                        </Button>
                      )}
                    </div>

                    <div className="mt-4 max-h-64 space-y-2 overflow-y-auto">
                      {traces.length === 0 ? (
                        <div className="rounded-md border border-border bg-surface-2 p-2 text-xs text-muted">
                          No Langfuse traces returned for this workspace yet.
                        </div>
                      ) : (
                        traces.map((trace) => (
                          <div key={trace.trace_id} className="rounded-md border border-border bg-surface-2 p-2 text-xs">
                            <div className="flex items-center justify-between gap-2">
                              <span className="truncate font-medium text-text">{trace.name || 'workspace-chat'}</span>
                              <span className="shrink-0 text-muted">
                                <ClockIcon className="mr-1 inline h-3 w-3" />
                                {formatTime(trace.timestamp)}
                              </span>
                            </div>
                            <div className="mt-1 text-muted">Session: {trace.session_id || '—'}</div>
                            {trace.url && (
                              <a
                                href={trace.url}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-1 inline-flex items-center gap-1 text-brand hover:underline"
                              >
                                Open trace
                                <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>

            </>
          )}
        </PageBody>
      </Page>
    </Layout>
  );
}

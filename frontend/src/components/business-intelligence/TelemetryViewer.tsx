/**
 * Telemetry Viewer Component
 * Real-time display of CrewAI agent execution telemetry using Server-Sent Events (SSE)
 */

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  BoltIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { useGetQuestionStatusV1BiQuestionsQuestionIdStatusGet } from '../../generated/business-intelligence/business-intelligence';

interface TelemetryEvent {
  event_id: string;
  event_type: string;
  agent_name?: string;
  stage_name?: string;
  tool_name?: string;
  message?: string;
  user_message?: string;
  progress_percentage?: number;
  timestamp: string;
  metadata?: any;
}

export interface TelemetryStreamState {
  events: TelemetryEvent[];
  heartbeat?: TelemetryEvent;
  completion?: TelemetryEvent;
  failure?: TelemetryEvent;
  isConnected: boolean;
}

export function useTelemetryStream(questionId: string | null, questionStatus?: string) {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const hasTerminalEvent = useRef(false);

  useEffect(() => {
    if (!questionId) {
      setEvents([]);
      setIsConnected(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    // Don't connect SSE for already completed/failed questions
    if (questionStatus === 'completed' || questionStatus === 'failed') {
      console.log('[SSE] Question already', questionStatus, '- skipping SSE connection');
      return;
    }

    // Connect to SSE endpoint for real-time telemetry
    // Use relative URL for production (nginx proxies to backend)
    const apiUrl = (AXIOS_INSTANCE.defaults.baseURL || process.env.REACT_APP_API_URL || '').replace(/\/$/, '');

    // Get auth token (EventSource doesn't support headers, so pass as query param)
    const token = localStorage.getItem('auth_token');
    if (!token) {
      console.error('No auth token found for SSE connection');
      return;
    }

    console.log(`Connecting to SSE: ${apiUrl}/v1/bi/questions/${questionId}/telemetry`);

    const sseUrl = `${apiUrl}/v1/bi/questions/${questionId}/telemetry?token=${encodeURIComponent(token)}`;
    console.log(`[SSE] Connecting to: ${sseUrl.replace(/token=[^&]+/, 'token=***')}`);
    
    const eventSource = new EventSource(sseUrl, { withCredentials: false });

    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('[SSE] Connection opened successfully');
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        console.log('[SSE] Received event:', event.data.substring(0, 100) + '...');
        const telemetryEvent: TelemetryEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, telemetryEvent]);
        
        // Check if this is a terminal event (completion or failure)
        if (telemetryEvent.event_type === 'completed' || telemetryEvent.event_type === 'failed') {
          console.log('[SSE] Stream completed gracefully:', telemetryEvent.event_type);
          hasTerminalEvent.current = true;
          // Give time for final events to process before closing
          setTimeout(() => {
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
          }, 100);
        }
      } catch (error) {
        console.error('[SSE] Failed to parse telemetry event:', error);
      }
    };

    eventSource.onerror = (error) => {
      // Check if we received a terminal event (completion/failure) before the error
      if (hasTerminalEvent.current) {
        console.log('[SSE] Connection closed after receiving terminal event (expected behavior)');
      } else {
        console.error('[SSE] Connection error. ReadyState:', eventSource.readyState);
        console.error('[SSE] Error event:', error);
        console.error('[SSE] Error type:', error.type);
        console.error('[SSE] URL was:', sseUrl.replace(/token=[^&]+/, 'token=***'));
        
        // ReadyState: 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
        if (eventSource.readyState === EventSource.CLOSED) {
          console.error('[SSE] Connection closed by server or failed to connect');
        }
      }
      
      setIsConnected(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };

    // Cleanup on unmount or questionId change
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
      }
      hasTerminalEvent.current = false;
    };
  }, [questionId, questionStatus]);

  const heartbeat = [...events].reverse().find((event) => event.event_type === 'heartbeat');
  const completion = [...events].reverse().find((event) => event.event_type === 'completed');
  const failure = [...events].reverse().find((event) => event.event_type === 'failed');

  return {
    events,
    heartbeat,
    completion,
    failure,
    isConnected,
  } satisfies TelemetryStreamState;
}

interface TelemetryViewerProps {
  questionId: string;
  variant?: 'default' | 'compact';
  className?: string;
}

export default function TelemetryViewer({ questionId, variant = 'default', className }: TelemetryViewerProps) {
  const { data: statusData } = useGetQuestionStatusV1BiQuestionsQuestionIdStatusGet(
    questionId,
    {
      query: {
        enabled: true,
        refetchInterval: 2000,
      },
    }
  );
  
  const { events, heartbeat, completion, failure, isConnected } = useTelemetryStream(
    questionId, 
    statusData?.status
  );

  if (!questionId) {
    return null;
  }

  const filteredEvents = events.filter((event) => event.event_type !== 'heartbeat' && event.event_type !== 'completed' && event.event_type !== 'failed');

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'stage_started':
        return <BoltIcon className="w-4 h-4 text-brand" />;
      case 'stage_completed':
        return <CheckCircleIcon className="w-4 h-4 text-success" />;
      case 'stage_failed':
        return <ExclamationCircleIcon className="w-4 h-4 text-error" />;
      case 'agent_started':
      case 'agent_completed':
        return <CpuChipIcon className="w-4 h-4 text-brand" />;
      case 'info':
        return <CheckCircleIcon className="w-4 h-4 text-brand" />;
      case 'warning':
        return <ExclamationCircleIcon className="w-4 h-4 text-yellow-500" />;
      default:
        return <ClockIcon className="w-4 h-4 text-muted" />;
    }
  };

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'stage_started':
      case 'agent_started':
      case 'info':
        return 'text-brand';
      case 'stage_completed':
      case 'agent_completed':
        return 'text-success';
      case 'stage_failed':
      case 'agent_failed':
        return 'text-error';
      case 'warning':
        return 'text-yellow-500';
      default:
        return 'text-muted';
    }
  };

  const containerClasses = variant === 'default'
    ? 'bg-surface border border-border rounded-lg p-6 sticky top-6'
    : 'bg-surface border border-border rounded-lg p-4';

  const headerClasses = variant === 'default'
    ? 'flex items-center justify-between mb-4'
    : 'flex items-center justify-between mb-3';

  return (
    <div className={`${containerClasses} ${className ?? ''}`}>
      <div className={headerClasses}>
        <h2 className="text-lg font-semibold text-text">Processing Status</h2>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-success animate-pulse' : 'bg-muted'}`}></div>
          <span className="text-xs text-muted">
            {isConnected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Current Status */}
      {statusData && (
        <div className={`mb-4 ${variant === 'compact' ? 'p-3' : 'p-3'} bg-bg border border-border rounded-lg`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text">Status:</span>
            <span
              className={`text-sm font-semibold ${
                statusData.status === 'completed'
                  ? 'text-success'
                  : statusData.status === 'failed'
                  ? 'text-error'
                  : 'text-brand'
              }`}
            >
              {statusData.status.charAt(0).toUpperCase() + statusData.status.slice(1)}
            </span>
          </div>
          {statusData.current_stage && (
            <div className="mt-2 text-xs text-muted">Current Stage: {statusData.current_stage}</div>
          )}
          {statusData.progress_percentage !== undefined && statusData.progress_percentage !== null && (
            <div className="mt-2">
              <div className="flex items-center justify-between text-xs text-muted mb-1">
                <span>Progress</span>
                <span>{statusData.progress_percentage}%</span>
              </div>
              <div className="w-full bg-border rounded-full h-2">
                <div
                  className="bg-brand h-2 rounded-full transition-all duration-300 w-var"
                  style={{ ['--w' as any]: `${statusData.progress_percentage}%` }}
                ></div>
              </div>
            </div>
          )}
          <div className="mt-2 space-y-1 text-xs text-muted">
            {heartbeat && heartbeat.timestamp && (
              <div>Last heartbeat: {new Date(heartbeat.timestamp).toLocaleTimeString()}</div>
            )}
            {completion && completion.timestamp && (
              <div>Completed: {new Date(completion.timestamp).toLocaleTimeString()}</div>
            )}
            {failure && failure.timestamp && (
              <div className="text-error">Failed: {new Date(failure.timestamp).toLocaleTimeString()}</div>
            )}
          </div>
        </div>
      )}

      {/* Error Message (shown when failure event received) */}
      {failure && failure.message && (
        <div className="mb-4 p-3 bg-error-soft border border-error rounded-lg">
          <div className="flex items-start space-x-2">
            <ExclamationCircleIcon className="w-5 h-5 text-error mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-error mb-1">FAILED</h3>
              <p className="text-sm text-text break-words whitespace-pre-wrap">{failure.message}</p>
            </div>
          </div>
        </div>
      )}

      {/* Telemetry Events */}
      <div className={`${variant === 'default' ? 'max-h-96' : 'max-h-80'} space-y-3 overflow-y-auto`}> 
        {filteredEvents.length === 0 ? (
          <div className="text-center py-8">
            <ClockIcon className="w-8 h-8 text-muted mx-auto mb-2" />
            <p className="text-sm text-muted">Waiting for processing to start...</p>
          </div>
        ) : (
          filteredEvents.map((event) => (
            <div key={event.event_id} className="p-3 bg-bg border border-border rounded-lg">
              <div className="flex items-start space-x-2">
                <div className="mt-0.5">{getEventIcon(event.event_type)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-xs font-medium ${getEventColor(event.event_type)}`}>
                      {event.event_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span className="text-xs text-muted">
                      {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : ''}
                    </span>
                  </div>
                  {event.agent_name && <div className="text-xs text-muted mb-1">Agent: {event.agent_name}</div>}
                  {event.stage_name && <div className="text-xs text-muted mb-1">Stage: {event.stage_name}</div>}
                  {event.tool_name && <div className="text-xs text-muted mb-1">Tool: {event.tool_name}</div>}
                  <p className="text-sm text-text break-words">{event.user_message || event.message || 'Processing...'}</p>
                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs text-muted cursor-pointer hover:text-text">View Details</summary>
                      <pre className="mt-2 text-xs text-muted bg-surface p-2 rounded overflow-x-auto">
                        {JSON.stringify(event.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

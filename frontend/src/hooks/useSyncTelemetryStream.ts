/**
 * Sync Telemetry Stream Hook
 * Real-time SSE streaming for data connector sync progress
 */

import { useEffect, useState, useRef } from 'react';
import { AXIOS_INSTANCE } from '../services/api-client';

export interface SyncTelemetryEvent {
  event_id: string;
  event_type: 'sync_started' | 'sync_progress' | 'sync_completed' | 'sync_failed' | 'heartbeat';
  sync_id?: string;
  connector_id?: number;
  progress_percentage?: number;
  records_extracted?: number;
  records_loaded?: number;
  records_skipped?: number;
  current_stage?: string;
  user_message?: string;
  error_message?: string;
  cost_so_far?: number;
  timestamp: string;
}

export interface SyncStreamState {
  events: SyncTelemetryEvent[];
  latestProgress?: SyncTelemetryEvent;
  completion?: SyncTelemetryEvent;
  failure?: SyncTelemetryEvent;
  isConnected: boolean;
}

export function useSyncTelemetryStream(syncId: string | null): SyncStreamState {
  const [events, setEvents] = useState<SyncTelemetryEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!syncId) {
      setEvents([]);
      setIsConnected(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    // Connect to SSE endpoint for real-time sync progress
    // Use relative URL for production (nginx proxies to backend)
    const apiUrl = (
      AXIOS_INSTANCE.defaults.baseURL ||
      process.env.REACT_APP_API_URL ||
      ''
    ).replace(/\/$/, '');

    // Get auth token (EventSource doesn't support headers, so pass as query param)
    const token = localStorage.getItem('auth_token');
    if (!token) {
      console.error('No auth token found for SSE connection');
      return;
    }

    console.log(`Connecting to sync SSE: ${apiUrl}/api/connectors/sync/${syncId}/stream`);

    const eventSource = new EventSource(
      `${apiUrl}/api/connectors/sync/${syncId}/stream?token=${encodeURIComponent(token)}`,
      { withCredentials: false }
    );

    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('Sync SSE connection opened');
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const telemetryEvent: SyncTelemetryEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, telemetryEvent]);
      } catch (error) {
        console.error('Failed to parse sync telemetry event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Sync SSE connection error:', error);
      setIsConnected(false);
      eventSource.close();
    };

    // Cleanup on unmount or syncId change
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        setIsConnected(false);
      }
    };
  }, [syncId]);

  // Extract latest progress, completion, and failure events
  const latestProgress = [...events]
    .reverse()
    .find((event) => event.event_type === 'sync_progress' || event.event_type === 'sync_started');
  const completion = [...events].reverse().find((event) => event.event_type === 'sync_completed');
  const failure = [...events].reverse().find((event) => event.event_type === 'sync_failed');

  return {
    events,
    latestProgress,
    completion,
    failure,
    isConnected,
  };
}


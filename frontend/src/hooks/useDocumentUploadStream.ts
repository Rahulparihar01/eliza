/**
 * Document Upload Stream Hook
 * Real-time SSE streaming for document upload progress
 */

import { useEffect, useState, useRef } from 'react';
import { AXIOS_INSTANCE } from '../services/api-client';

export interface UploadStatusEvent {
  event_id: string;
  event_type: 'status_update' | 'completed' | 'failed' | 'error' | 'heartbeat';
  upload_id?: string;
  status?: string;
  total_files?: number;
  completed_files?: number;
  failed_files?: number;
  progress_percentage?: number;
  total_chunks_created?: number;
  message?: string;
  total_chunks?: number;
  timestamp: string;
}

export interface UploadStreamState {
  events: UploadStatusEvent[];
  latestStatus?: UploadStatusEvent;
  completion?: UploadStatusEvent;
  failure?: UploadStatusEvent;
  isConnected: boolean;
}

export function useDocumentUploadStream(uploadId: string | null): UploadStreamState {
  const [events, setEvents] = useState<UploadStatusEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!uploadId) {
      setEvents([]);
      setIsConnected(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    // Connect to SSE endpoint for real-time upload progress
    // Use relative URL for production (nginx proxies to backend)
    const apiUrl = (AXIOS_INSTANCE.defaults.baseURL || process.env.REACT_APP_API_URL || '').replace(/\/$/, '');

    // Get auth token (EventSource doesn't support headers, so pass as query param)
    const token = localStorage.getItem('auth_token');
    if (!token) {
      console.error('No auth token found for SSE connection');
      return;
    }

    console.log(`Connecting to upload SSE: ${apiUrl}/v1/documents/upload/${uploadId}/stream`);

    const eventSource = new EventSource(
      `${apiUrl}/v1/documents/upload/${uploadId}/stream?token=${encodeURIComponent(token)}`,
      { withCredentials: false }
    );

    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('Upload SSE connection opened');
      setIsConnected(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const uploadEvent: UploadStatusEvent = JSON.parse(event.data);
        setEvents((prev) => [...prev, uploadEvent]);
      } catch (error) {
        console.error('Failed to parse upload event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Upload SSE connection error:', error);
      setIsConnected(false);
      eventSource.close();
    };

    // Cleanup on unmount or uploadId change
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        setIsConnected(false);
      }
    };
  }, [uploadId]);

  // Extract latest status, completion, and failure events
  const latestStatus = [...events].reverse().find((event) => event.event_type === 'status_update');
  const completion = [...events].reverse().find((event) => event.event_type === 'completed');
  const failure = [...events].reverse().find((event) => event.event_type === 'failed' || event.event_type === 'error');

  return {
    events,
    latestStatus,
    completion,
    failure,
    isConnected,
  };
}

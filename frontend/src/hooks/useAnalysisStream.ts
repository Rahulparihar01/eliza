/**
 * Custom hook for streaming real-time talent analysis progress via SSE
 * 
 * Similar to useSyncTelemetryStream but for talent intelligence analysis
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

export interface AnalysisEvent {
  event_id?: number;
  event_type: string;
  analysis_id: string;
  agent_name?: string;
  message?: string;
  progress_percentage?: number;
  data?: Record<string, any>;
  timestamp?: string;
}

export interface UseAnalysisStreamReturn {
  events: AnalysisEvent[];
  latestEvent: AnalysisEvent | null;
  isComplete: boolean;
  isFailed: boolean;
  error: string | null;
  progressPercentage: number;
  currentAgent: string | null;
  currentMessage: string | null;
}

export function useAnalysisStream(analysisId: string | null): UseAnalysisStreamReturn {
  const navigate = useNavigate();
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [latestEvent, setLatestEvent] = useState<AnalysisEvent | null>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEvent = useCallback((event: AnalysisEvent) => {
    setEvents(prev => [...prev, event]);
    setLatestEvent(event);

    // Check for completion/failure
    if (event.event_type === 'analysis_completed') {
      setIsComplete(true);
    } else if (event.event_type === 'analysis_failed') {
      setIsFailed(true);
      setError(event.message || 'Analysis failed');
    }
  }, []);

  useEffect(() => {
    if (!analysisId) {
      return;
    }

    // Get auth token for SSE
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setError('Not authenticated');
      return;
    }

    // Create SSE connection with token as query param
    // Note: EventSource doesn't support custom headers, so we pass token as query param
    // Use relative URL for production (nginx proxies to backend)
    const eventSource = new EventSource(
      `/api/talent/analysis/${analysisId}/stream?token=${encodeURIComponent(token)}`
    );

    eventSource.onmessage = (event) => {
      try {
        const data: AnalysisEvent = JSON.parse(event.data);
        handleEvent(data);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE connection error:', err);
      
      // Check if this is an authentication error (403)
      // EventSource doesn't give us the status code directly, but we can infer it
      // from the immediate error on connection
      fetch(`/api/talent/analysis/${analysisId}/stream?token=${encodeURIComponent(token)}`, {
        method: 'HEAD'
      }).then(response => {
        if (response.status === 403) {
          // Token expired or invalid - clear auth and redirect to login
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user');
          eventSource.close();
          navigate('/login', { 
            state: { message: 'Your session has expired. Please log in again.' }
          });
          return;
        }
      }).catch(() => {
        // Network error or other issue
      });
      
      eventSource.close();
      
      // Only set error if we haven't completed successfully
      if (!isComplete) {
        setError('Connection to server lost');
      }
    };

    // Cleanup
    return () => {
      eventSource.close();
    };
  }, [analysisId, handleEvent, isComplete]);

  // Derived values
  const progressPercentage = latestEvent?.progress_percentage || 0;
  const currentAgent = latestEvent?.agent_name || null;
  const currentMessage = latestEvent?.message || null;

  return {
    events,
    latestEvent,
    isComplete,
    isFailed,
    error,
    progressPercentage,
    currentAgent,
    currentMessage,
  };
}


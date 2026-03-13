/**
 * Custom hook for streaming real-time job scheduler status via SSE
 * 
 * Provides live updates for job status, new executions, and status changes
 * without needing to refresh the page.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AXIOS_INSTANCE } from '../services/api-client';

export interface ScheduledJob {
  id: number;
  job_name: string;
  display_name: string;
  description: string | null;
  task_name: string;
  schedule_type: string;
  schedule_value: string;
  schedule_display: string | null;
  is_enabled: boolean;
  last_run_at: string | null;
  last_run_status: string;
  last_run_duration_seconds: number | null;
  last_error: string | null;
  last_task_id: string | null;
  next_run_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface JobExecution {
  id: number;
  job_name: string;
  task_id: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  status: string;
  error_message: string | null;
  triggered_by: string;
  result_summary: string | null;
}

export interface JobStreamEvent {
  event_id: string;
  event_type: 'connected' | 'job_update' | 'execution_update' | 'heartbeat' | 'error';
  jobs?: ScheduledJob[];
  job?: ScheduledJob;
  execution?: JobExecution;
  message?: string;
  timestamp: string;
}

export interface UseJobSchedulerStreamReturn {
  jobs: ScheduledJob[];
  isConnected: boolean;
  error: string | null;
  lastUpdate: Date | null;
  reconnect: () => void;
}

export function useJobSchedulerStream(enabled: boolean = true): UseJobSchedulerStreamReturn {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEvent = useCallback((event: JobStreamEvent) => {
    setLastUpdate(new Date());
    
    switch (event.event_type) {
      case 'connected':
        // Initial load - set all jobs
        if (event.jobs) {
          setJobs(event.jobs);
        }
        setIsConnected(true);
        setError(null);
        break;
        
      case 'job_update':
        // Update a single job
        if (event.job) {
          setJobs(prev => {
            const index = prev.findIndex(j => j.job_name === event.job!.job_name);
            if (index >= 0) {
              const updated = [...prev];
              updated[index] = event.job!;
              return updated;
            }
            // New job - add to list
            return [...prev, event.job!];
          });
        }
        break;
        
      case 'execution_update':
        // New execution - we don't track executions in this hook directly,
        // but we can trigger a refetch of executions for the specific job
        // The job_update event should also be sent for status changes
        break;
        
      case 'heartbeat':
        // Just update connection status
        break;
        
      case 'error':
        setError(event.message || 'Stream error');
        break;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;
    
    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    // Get auth token
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setError('Not authenticated');
      return;
    }

    // Get the API base URL (same pattern as useSyncTelemetryStream)
    const apiUrl = (
      AXIOS_INSTANCE.defaults.baseURL ||
      process.env.REACT_APP_API_URL ||
      ''
    ).replace(/\/$/, '');

    // Create SSE connection - use full URL to bypass proxy issues
    const eventSource = new EventSource(
      `${apiUrl}/api/v1/platform-admin/jobs/stream?token=${encodeURIComponent(token)}`,
      { withCredentials: false }
    );
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const data: JobStreamEvent = JSON.parse(event.data);
        handleEvent(data);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE connection error:', err);
      setIsConnected(false);
      eventSource.close();
      
      // Check if auth error
      fetch(`${apiUrl}/api/v1/platform-admin/jobs/stream?token=${encodeURIComponent(token)}`, {
        method: 'HEAD'
      }).then(response => {
        if (response.status === 403) {
          // Token expired - redirect to login
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user');
          navigate('/login', { 
            state: { message: 'Your session has expired. Please log in again.' }
          });
          return;
        }
        // Other error - try to reconnect after delay
        setError('Connection lost. Reconnecting...');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 5000);
      }).catch(() => {
        // Network error - try to reconnect
        setError('Connection lost. Reconnecting...');
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 5000);
      });
    };
  }, [enabled, handleEvent, navigate]);

  const reconnect = useCallback(() => {
    setError(null);
    connect();
  }, [connect]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [enabled, connect]);

  return {
    jobs,
    isConnected,
    error,
    lastUpdate,
    reconnect,
  };
}


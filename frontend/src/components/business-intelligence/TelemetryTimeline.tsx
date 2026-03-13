import React, { useMemo } from 'react';
import {
  BoltIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline';
import { useTelemetryStream } from './TelemetryViewer';

interface TelemetryTimelineProps {
  questionId: string;
}

export default function TelemetryTimeline({ questionId }: TelemetryTimelineProps) {
  const { events, isConnected } = useTelemetryStream(questionId);

  const timelineEvents = useMemo(() => {
    return events.filter((event) => event.event_type !== 'heartbeat');
  }, [events]);

  if (timelineEvents.length === 0) {
    return (
      <div className="text-sm text-muted">
        {isConnected ? 'Telemetry will appear here as the question progresses.' : 'Waiting for telemetry connection…'}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {timelineEvents.map((event, index) => {
        const key = event.event_id ?? `${event.event_type}-${index}`;
        return (
          <div key={key} className="flex items-start space-x-3">
            <div className="mt-0.5">{getIcon(event.event_type)}</div>
            <div className="flex-1">
              <EventContent event={event} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EventContent({ event }: { event: any }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className={`text-xs font-semibold ${getColor(event.event_type)}`}>
          {event.event_type.replace(/_/g, ' ').toUpperCase()}
        </span>
        <span className="text-xs text-muted">
          {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : '—'}
        </span>
      </div>
      {event.agent_name && <p className="text-xs text-muted">Agent: {event.agent_name}</p>}
      {event.stage_name && <p className="text-xs text-muted">Stage: {event.stage_name}</p>}
      {event.message && (
        <p className="text-sm text-text mt-2 whitespace-pre-wrap">{event.message}</p>
      )}
      {'user_message' in event && event.user_message && event.user_message !== event.message && (
        <p className="text-xs text-muted">User message: {event.user_message}</p>
      )}
      {event.progress_percentage !== undefined && event.progress_percentage !== null && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs text-muted mb-1">
            <span>Progress</span>
            <span>{event.progress_percentage}%</span>
          </div>
          <div className="w-full bg-border rounded-full h-1.5">
            <div
              className="bg-brand h-1.5 rounded-full w-var"
              style={{ ['--w' as any]: `${event.progress_percentage}%` }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
}

function getIcon(eventType: string) {
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
    default:
      return <ClockIcon className="w-4 h-4 text-muted" />;
  }
}

function getColor(eventType: string) {
  switch (eventType) {
    case 'stage_started':
    case 'agent_started':
      return 'text-brand';
    case 'stage_completed':
    case 'agent_completed':
      return 'text-success';
    case 'stage_failed':
    case 'agent_failed':
      return 'text-error';
    default:
      return 'text-muted';
  }
}

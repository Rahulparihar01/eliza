/**
 * Sync Progress Widget
 * 
 * Real-time progress indicator for data connector syncs using SSE
 */

import React from 'react';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CloudArrowUpIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useSyncTelemetryStream } from '../../hooks/useSyncTelemetryStream';

interface SyncProgressWidgetProps {
  syncId: string | null;
  connectorName?: string;
  onClose?: () => void;
  compact?: boolean;
}

export function SyncProgressWidget({
  syncId,
  connectorName,
  onClose,
  compact = false,
}: SyncProgressWidgetProps) {
  const { latestProgress, completion, failure, isConnected } = useSyncTelemetryStream(syncId);

  if (!syncId) return null;

  const isComplete = !!completion;
  const isFailed = !!failure;
  const isRunning = !isComplete && !isFailed;

  const progress = latestProgress?.progress_percentage || 0;
  const recordsLoaded = latestProgress?.records_loaded || 0;
  const message = latestProgress?.user_message || completion?.user_message || failure?.user_message;
  const stage = latestProgress?.current_stage;
  const errorMessage = failure?.error_message;

  // Compact version for inline display
  if (compact) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-surface-2 rounded-lg border border-border text-xs">
        {isRunning && (
          <>
            <ArrowPathIcon className="w-3 h-3 text-primary animate-spin" />
            <span className="text-foreground">{progress}%</span>
            {stage && <span className="text-muted-2">• {stage}</span>}
          </>
        )}
        {isComplete && (
          <>
            <CheckCircleIcon className="w-3 h-3 text-success" />
            <span className="text-success">Completed</span>
            <span className="text-muted-2">• {recordsLoaded} records</span>
          </>
        )}
        {isFailed && (
          <>
            <ExclamationCircleIcon className="w-3 h-3 text-error" />
            <span className="text-error">Failed</span>
          </>
        )}
        {!isConnected && isRunning && (
          <span className="text-warning">• Reconnecting...</span>
        )}
      </div>
    );
  }

  // Full version for standalone display
  return (
    <div className="bg-surface-2 rounded-lg border border-border p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-lg ${
              isComplete
                ? 'bg-success/10'
                : isFailed
                ? 'bg-error/10'
                : 'bg-primary/10'
            }`}
          >
            {isRunning && (
              <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />
            )}
            {isComplete && <CheckCircleIcon className="w-5 h-5 text-success" />}
            {isFailed && <ExclamationCircleIcon className="w-5 h-5 text-error" />}
          </div>
          <div>
            <h3 className="font-semibold text-foreground">
              {isRunning && 'Syncing'}
              {isComplete && 'Sync Completed'}
              {isFailed && 'Sync Failed'}
            </h3>
            {connectorName && (
              <p className="text-sm text-muted-2">{connectorName}</p>
            )}
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-surface-3 rounded transition-colors"
          >
            <XMarkIcon className="w-5 h-5 text-muted-2" />
          </button>
        )}
      </div>

      {/* Progress Bar */}
      {isRunning && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">Progress</span>
            <span className="text-sm font-medium text-foreground">{progress}%</span>
          </div>
          <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="text-xs text-muted-2 mb-1">Extracted</div>
          <div className="text-lg font-semibold text-foreground">
            {latestProgress?.records_extracted || 0}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-muted-2 mb-1">Loaded</div>
          <div className="text-lg font-semibold text-foreground">
            {recordsLoaded}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-muted-2 mb-1">Skipped</div>
          <div className="text-lg font-semibold text-foreground">
            {latestProgress?.records_skipped || 0}
          </div>
        </div>
      </div>

      {/* Current Stage */}
      {stage && isRunning && (
        <div className="mb-3 p-3 bg-info/10 rounded-lg">
          <div className="flex items-center gap-2">
            <CloudArrowUpIcon className="w-4 h-4 text-info" />
            <span className="text-sm text-info font-medium">{stage}</span>
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div
          className={`p-3 rounded-lg ${
            isComplete
              ? 'bg-success/10 text-success'
              : isFailed
              ? 'bg-error/10 text-error'
              : 'bg-surface-3 text-foreground'
          }`}
        >
          <p className="text-sm">{message}</p>
        </div>
      )}

      {/* Error Message */}
      {errorMessage && (
        <div className="mt-3 p-3 bg-error/10 rounded-lg">
          <div className="flex items-start gap-2">
            <ExclamationCircleIcon className="w-4 h-4 text-error flex-shrink-0 mt-0.5" />
            <p className="text-sm text-error">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Cost */}
      {latestProgress?.cost_so_far !== undefined && (
        <div className="mt-3 text-xs text-muted-2 text-right">
          Cost: ${latestProgress.cost_so_far.toFixed(4)}
        </div>
      )}

      {/* Connection Status */}
      {!isConnected && isRunning && (
        <div className="mt-3 p-2 bg-warning/10 rounded-lg">
          <p className="text-xs text-warning text-center">
            Connection lost. Attempting to reconnect...
          </p>
        </div>
      )}
    </div>
  );
}


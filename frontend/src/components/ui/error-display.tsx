/**
 * Error Display Component - Eliza Forge Design System
 * 
 * Displays error messages with consistent styling and retry functionality.
 * Uses DS components: Alert, Button, Card.
 * 
 * Variants:
 * - inline: Uses Alert component for inline error messages
 * - card: Uses Card component for contained error displays
 * - page: Full-page error display with centered Card
 */

import * as React from 'react'
import { ExclamationCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { Alert } from './alert'
import { Button } from './button'
import { Card, CardContent } from './card'
import { cn } from '../../shared/lib/cn'

export interface ErrorDisplayProps {
  /** Error title */
  title?: string
  /** Error message */
  message: string
  /** Technical error details (shown in expandable section) */
  details?: string
  /** Callback for retry action */
  onRetry?: () => void
  /** Label for retry button */
  retryLabel?: string
  /** Additional CSS classes */
  className?: string
  /** Display variant */
  variant?: 'inline' | 'page' | 'card'
}

export function ErrorDisplay({
  title = 'Error',
  message,
  details,
  onRetry,
  retryLabel = 'Try Again',
  className = '',
  variant = 'inline'
}: ErrorDisplayProps) {
  // Inline variant uses DS Alert component
  if (variant === 'inline') {
    return (
      <Alert variant="error" title={title} className={className}>
        <p className="mb-2">{message}</p>
        {details && (
          <details className="mb-3 text-left">
            <summary className="text-sm opacity-80 cursor-pointer hover:opacity-100 mb-2">
              View Details
            </summary>
            <div className="bg-red-100 dark:bg-red-950/50 rounded border border-red-200 dark:border-red-800/50 p-3 text-xs font-mono overflow-auto max-h-32">
              {details}
            </div>
          </details>
        )}
        {onRetry && (
          <Button size="sm" variant="secondary" onClick={onRetry} className="mt-2">
            <ArrowPathIcon className="h-4 w-4" />
            {retryLabel}
          </Button>
        )}
      </Alert>
    )
  }

  // Card variant uses DS Card component
  if (variant === 'card') {
    return (
      <Card className={className}>
        <CardContent className="p-6 text-center">
          <div className="flex justify-center mb-4">
            <ExclamationCircleIcon className="h-8 w-8 text-red-500" />
          </div>
          <h3 className="font-semibold text-charcoal dark:text-gray-100 mb-2 text-lg">
            {title}
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            {message}
          </p>
          {details && (
            <details className="mb-4 text-left max-w-md mx-auto">
              <summary className="text-sm text-gray-400 dark:text-gray-500 cursor-pointer hover:text-gray-500 dark:hover:text-gray-400 mb-2">
                View Details
              </summary>
              <div className="bg-gray-50 dark:bg-dark-surface-2 rounded border border-gray-200 dark:border-dark-border p-3 text-xs font-mono text-gray-600 dark:text-gray-300 overflow-auto max-h-32">
                {details}
              </div>
            </details>
          )}
          {onRetry && (
            <Button onClick={onRetry}>
              <ArrowPathIcon className="h-4 w-4" />
              {retryLabel}
            </Button>
          )}
        </CardContent>
      </Card>
    )
  }

  // Page variant - full page error display
  return (
    <div className={cn("min-h-[400px] flex items-center justify-center p-8", className)}>
      <Card className="max-w-md w-full">
        <CardContent className="p-8 text-center">
          <div className="flex justify-center mb-4">
            <ExclamationCircleIcon className="h-12 w-12 text-red-500" />
          </div>
          <h3 className="font-title text-xl text-charcoal dark:text-gray-100 mb-2">
            {title}
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            {message}
          </p>
          {details && (
            <details className="mb-4 text-left">
              <summary className="text-sm text-gray-400 dark:text-gray-500 cursor-pointer hover:text-gray-500 dark:hover:text-gray-400 mb-2">
                View Details
              </summary>
              <div className="bg-gray-50 dark:bg-dark-surface-2 rounded border border-gray-200 dark:border-dark-border p-3 text-xs font-mono text-gray-600 dark:text-gray-300 overflow-auto max-h-32">
                {details}
              </div>
            </details>
          )}
          {onRetry && (
            <Button onClick={onRetry}>
              <ArrowPathIcon className="h-4 w-4" />
              {retryLabel}
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ============================================
// Convenience Components for Common Scenarios
// ============================================

export interface ErrorStateProps {
  onRetry?: () => void
  className?: string
}

/** Network/connection error display */
export function NetworkError({ onRetry, className }: ErrorStateProps) {
  return (
    <ErrorDisplay
      title="Connection Error"
      message="Unable to connect to the server. Please check your internet connection and try again."
      onRetry={onRetry}
      variant="card"
      className={className}
    />
  )
}

/** Authentication/session error display */
export function AuthError({ onRetry, className }: ErrorStateProps) {
  return (
    <ErrorDisplay
      title="Authentication Error"
      message="Your session has expired or you don't have permission to access this resource."
      onRetry={onRetry}
      retryLabel="Sign In Again"
      variant="card"
      className={className}
    />
  )
}

/** 404 Not Found error display */
export function NotFoundError({ onRetry, className }: ErrorStateProps) {
  return (
    <ErrorDisplay
      title="Not Found"
      message="The page or resource you're looking for doesn't exist."
      onRetry={onRetry}
      retryLabel="Go Back"
      variant="page"
      className={className}
    />
  )
}

/** Server/500 error display */
export function ServerError({ onRetry, className }: ErrorStateProps) {
  return (
    <ErrorDisplay
      title="Server Error"
      message="Something went wrong on our end. Please try again in a few moments."
      onRetry={onRetry}
      variant="card"
      className={className}
    />
  )
}

/** Access denied/forbidden error display */
export function AccessDeniedError({ onRetry, className }: ErrorStateProps) {
  return (
    <ErrorDisplay
      title="Access Denied"
      message="You don't have permission to access this page or resource."
      onRetry={onRetry}
      retryLabel="Go Back"
      variant="page"
      className={className}
    />
  )
}

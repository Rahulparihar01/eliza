/**
 * Error Boundary Component - Eliza Forge Design System
 * 
 * React Error Boundary that catches JavaScript errors in child components
 * and displays a fallback UI using DS components.
 * 
 * Usage:
 * ```tsx
 * <ErrorBoundary onReset={() => refetch()}>
 *   <MyComponent />
 * </ErrorBoundary>
 * 
 * // With custom fallback
 * <ErrorBoundary fallback={<CustomError />}>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { XCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { Card, CardContent } from './card'
import { Button } from './button'

export interface ErrorBoundaryProps {
  /** Child components to wrap */
  children: ReactNode
  /** Callback when user clicks retry */
  onReset?: () => void
  /** Custom fallback UI to display on error */
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
  }

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: undefined })
    this.props.onReset?.()
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-dark-bg p-6">
          <Card className="max-w-md w-full">
            <CardContent className="p-8 text-center">
              <XCircleIcon className="w-16 h-16 text-red-500 mx-auto mb-4" />
              <h2 className="font-title text-2xl text-charcoal dark:text-gray-100 mb-2">
                Something went wrong
              </h2>
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                {this.state.error?.message || 'An unexpected error occurred'}
              </p>
              <Button onClick={this.handleReset}>
                <ArrowPathIcon className="w-4 h-4" />
                Try Again
              </Button>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

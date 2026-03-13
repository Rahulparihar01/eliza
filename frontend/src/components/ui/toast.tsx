/**
 * Toast - Notification Component
 * 
 * Temporary popup notifications for user feedback.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../shared/lib/cn"

/* ============================================
   TOAST VARIANTS
   ============================================ */

const toastVariants = cva(
  [
    "flex items-start gap-3 p-4 rounded-xl shadow-lg border",
    "animate-in slide-in-from-top-2 fade-in-0 duration-200",
    "min-w-[300px] max-w-[420px]",
  ],
  {
    variants: {
      variant: {
        default: "bg-white border-gray-200 text-charcoal dark:bg-dark-surface dark:border-dark-border/50 dark:text-gray-100",
        success: "bg-green-50 border-green-200 text-green-800 dark:bg-green-950/50 dark:border-green-800/50 dark:text-green-200",
        error: "bg-red-50 border-red-200 text-red-800 dark:bg-red-950/50 dark:border-red-800/50 dark:text-red-200",
        warning: "bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-950/50 dark:border-amber-800/50 dark:text-amber-200",
        info: "bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950/50 dark:border-blue-800/50 dark:text-blue-200",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const iconMap = {
  default: InformationCircleIcon,
  success: CheckCircleIcon,
  error: ExclamationCircleIcon,
  warning: ExclamationTriangleIcon,
  info: InformationCircleIcon,
}

/* ============================================
   TOAST COMPONENT
   ============================================ */

interface ToastProps extends VariantProps<typeof toastVariants> {
  id: string
  title?: string
  message: string
  duration?: number
  onDismiss: (id: string) => void
}

const Toast: React.FC<ToastProps> = ({
  id,
  variant = "default",
  title,
  message,
  duration = 5000,
  onDismiss,
}) => {
  const Icon = iconMap[variant || "default"]

  React.useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => onDismiss(id), duration)
      return () => clearTimeout(timer)
    }
  }, [id, duration, onDismiss])

  return (
    <div className={toastVariants({ variant })}>
      <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        {title && <p className="font-medium">{title}</p>}
        <p className={cn("text-sm", title && "opacity-90")}>{message}</p>
      </div>
      <button
        onClick={() => onDismiss(id)}
        className="flex-shrink-0 p-1 rounded-lg hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
      >
        <XMarkIcon className="w-4 h-4" />
      </button>
    </div>
  )
}

/* ============================================
   TOAST CONTAINER
   ============================================ */

interface ToastContainerProps {
  toasts: Array<ToastProps>
  position?: "top-right" | "top-left" | "bottom-right" | "bottom-left" | "top-center" | "bottom-center"
}

const positionClasses = {
  "top-right": "top-4 right-4",
  "top-left": "top-4 left-4",
  "bottom-right": "bottom-4 right-4",
  "bottom-left": "bottom-4 left-4",
  "top-center": "top-4 left-1/2 -translate-x-1/2",
  "bottom-center": "bottom-4 left-1/2 -translate-x-1/2",
}

const ToastContainer: React.FC<ToastContainerProps> = ({
  toasts,
  position = "top-right",
}) => {
  if (toasts.length === 0) return null

  return (
    <div className={cn("fixed z-[100] flex flex-col gap-2", positionClasses[position])}>
      {toasts.map((toast) => (
        <Toast key={toast.id} {...toast} />
      ))}
    </div>
  )
}

/* ============================================
   USE TOAST HOOK
   ============================================ */

type ToastInput = Omit<ToastProps, "id" | "onDismiss">

interface UseToastReturn {
  toasts: ToastProps[]
  toast: (input: ToastInput) => string
  success: (message: string, title?: string) => string
  error: (message: string, title?: string) => string
  warning: (message: string, title?: string) => string
  info: (message: string, title?: string) => string
  dismiss: (id: string) => void
  dismissAll: () => void
}

function useToast(): UseToastReturn {
  const [toasts, setToasts] = React.useState<ToastProps[]>([])

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = React.useCallback((input: ToastInput): string => {
    const id = Math.random().toString(36).substring(2, 9)
    const newToast: ToastProps = { ...input, id, onDismiss: dismiss }
    setToasts((prev) => [...prev, newToast])
    return id
  }, [dismiss])

  const success = React.useCallback((message: string, title?: string) => {
    return toast({ variant: "success", message, title })
  }, [toast])

  const error = React.useCallback((message: string, title?: string) => {
    return toast({ variant: "error", message, title })
  }, [toast])

  const warning = React.useCallback((message: string, title?: string) => {
    return toast({ variant: "warning", message, title })
  }, [toast])

  const info = React.useCallback((message: string, title?: string) => {
    return toast({ variant: "info", message, title })
  }, [toast])

  const dismissAll = React.useCallback(() => {
    setToasts([])
  }, [])

  return { toasts, toast, success, error, warning, info, dismiss, dismissAll }
}

export { Toast, ToastContainer, useToast, toastVariants }
export type { ToastProps, ToastContainerProps, ToastInput, UseToastReturn }

/**
 * SidebarContentSwitch - Content Transition Component
 * 
 * A DS component that handles switching between different
 * sidebar content views (e.g., main nav ↔ section nav).
 * 
 * Features:
 * - Instant content switching
 * - Works with collapsed sidebar mode
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

/* ============================================
   Types
   ============================================ */

interface SidebarContentSwitchProps {
  /** Unique key for current content */
  activeKey: string
  /** Direction (kept for API compatibility) */
  direction?: 'forward' | 'backward'
  /** Duration (kept for API compatibility) */
  duration?: number
  /** Content to display */
  children: React.ReactNode
  /** Additional className for the container */
  className?: string
}

/* ============================================
   Component
   ============================================ */

export function SidebarContentSwitch({
  children,
  className,
}: SidebarContentSwitchProps) {
  return (
    <div
      className={cn(
        "relative flex-1 overflow-hidden",
        className
      )}
    >
      <div className="w-full h-full">
        {children}
      </div>
    </div>
  )
}

/* ============================================
   Exports
   ============================================ */

export type { SidebarContentSwitchProps }

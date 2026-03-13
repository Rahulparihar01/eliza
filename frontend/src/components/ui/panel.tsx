/**
 * Panel Component - Eliza Forge Design System
 * 
 * A flat container without shadow, ideal for admin interfaces and data tables.
 * Use Panel for functional UI containers; use Card for elevated content that needs emphasis.
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

/* ============================================
   PANEL - Flat container without shadow
   ============================================ */

const Panel = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border border-gray-200 bg-white",
      "dark:bg-dark-surface dark:border-dark-border",
      className
    )}
    {...props}
  />
))
Panel.displayName = "Panel"

/* ============================================
   PANEL HEADER - Top section with title
   ============================================ */

const PanelHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "px-6 py-4 border-b border-gray-200 dark:border-dark-border",
      className
    )}
    {...props}
  />
))
PanelHeader.displayName = "PanelHeader"

/* ============================================
   PANEL TITLE - Header title text
   ============================================ */

const PanelTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "font-subtitle text-h3 text-charcoal dark:text-gray-100",
      className
    )}
    {...props}
  />
))
PanelTitle.displayName = "PanelTitle"

/* ============================================
   PANEL DESCRIPTION - Header description text
   ============================================ */

const PanelDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      "text-sm text-gray-500 dark:text-gray-400 mt-0.5",
      className
    )}
    {...props}
  />
))
PanelDescription.displayName = "PanelDescription"

/* ============================================
   PANEL BODY - Main content area
   ============================================ */

const PanelBody = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("p-6", className)}
    {...props}
  />
))
PanelBody.displayName = "PanelBody"

/* ============================================
   PANEL FOOTER - Bottom section
   ============================================ */

const PanelFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "px-6 py-4 border-t border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2",
      className
    )}
    {...props}
  />
))
PanelFooter.displayName = "PanelFooter"

export { Panel, PanelHeader, PanelTitle, PanelDescription, PanelBody, PanelFooter }

/**
 * SidebarContextPanel - Contextual Sub-Navigation Panel
 * 
 * A wrapper around SidebarSubmenu for use with the NavigationContext.
 * This component is what gets rendered in Layout.tsx when a contextual
 * section is active.
 * 
 * @see SidebarSubmenu for the underlying implementation
 */

import * as React from "react"
import { SidebarSubmenu, SubmenuItem } from "./sidebar-submenu"

/* ============================================
   Types
   ============================================ */

// Re-export SubmenuItem as ContextPanelItem for backward compatibility
export type ContextPanelItem = SubmenuItem

interface SidebarContextPanelProps {
  /** Section title */
  title: string
  /** Section icon (not used in submenu style, kept for API compatibility) */
  icon?: React.ComponentType<{ className?: string }>
  /** Navigation items */
  items: ContextPanelItem[]
  /** Callback when back button is clicked */
  onBack: () => void
  /** Whether the panel is visible */
  isVisible: boolean
  /** Callback when hamburger menu is clicked (toggle sidebar) */
  onToggle?: () => void
  /** Additional className */
  className?: string
}

/* ============================================
   Component
   ============================================ */

export function SidebarContextPanel({
  title,
  icon, // Kept for API compatibility, not used in submenu style
  items,
  onBack,
  isVisible,
  onToggle,
  className,
}: SidebarContextPanelProps) {
  return (
    <SidebarSubmenu
      title={title}
      items={items}
      onBack={onBack}
      isVisible={isVisible}
      onToggle={onToggle}
      className={className}
      showFooter={true}
    />
  )
}

export default SidebarContextPanel

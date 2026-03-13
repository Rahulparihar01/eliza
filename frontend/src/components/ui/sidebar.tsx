/**
 * Sidebar - Unified Navigation Component
 * 
 * A flexible sidebar that supports both simple lists and expandable sub-menus.
 * Use the same components - just add children to SidebarItem for expandable behavior.
 * 
 * Features:
 * - Collapsible with animated transitions
 * - Context-based state management
 * - Tooltip hints when collapsed
 */

import * as React from "react"
import { ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/outline"
import { cn } from "../../shared/lib/cn"

/* ============================================
   SIDEBAR CONTEXT (for mode state)
   ============================================ */

/**
 * Sidebar display modes:
 * - 'expanded': Full width with labels (default)
 * - 'collapsed': Icon-only mode with tooltips
 * - 'hidden': Completely hidden (width: 0, for contextual navigation)
 */
export type SidebarMode = 'expanded' | 'collapsed' | 'hidden'

interface SidebarContextValue {
  /** Current sidebar mode */
  mode: SidebarMode
  /** Set the sidebar mode directly */
  setMode: (mode: SidebarMode) => void
  /** Convenience method: set mode to 'expanded' */
  expand: () => void
  /** Convenience method: set mode to 'collapsed' */
  collapse: () => void
  /** Convenience method: set mode to 'hidden' */
  hide: () => void
  // Backward compatibility
  /** @deprecated Use mode === 'collapsed' instead */
  collapsed: boolean
  /** @deprecated Use setMode() instead */
  setCollapsed: (collapsed: boolean) => void
  /** @deprecated Use expand()/collapse() instead */
  toggleCollapsed: () => void
}

const SidebarContext = React.createContext<SidebarContextValue | undefined>(undefined)

const useSidebar = () => {
  const context = React.useContext(SidebarContext)
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider")
  }
  return context
}

/* ============================================
   SIDEBAR PROVIDER (wrap your layout)
   ============================================ */

interface SidebarProviderProps {
  children: React.ReactNode
  /** Initial mode (default: 'expanded') */
  defaultMode?: SidebarMode
  /** Callback when mode changes */
  onModeChange?: (mode: SidebarMode) => void
  /** @deprecated Use defaultMode instead */
  defaultCollapsed?: boolean
  /** @deprecated Use onModeChange instead */
  onCollapsedChange?: (collapsed: boolean) => void
}

const SidebarProvider: React.FC<SidebarProviderProps> = ({
  children,
  defaultMode,
  onModeChange,
  defaultCollapsed = false,
  onCollapsedChange,
}) => {
  // Determine initial mode from new or legacy props
  const initialMode: SidebarMode = defaultMode ?? (defaultCollapsed ? 'collapsed' : 'expanded')
  const [mode, setModeState] = React.useState<SidebarMode>(initialMode)

  const setMode = React.useCallback((newMode: SidebarMode) => {
    setModeState(newMode)
    onModeChange?.(newMode)
    // Legacy callback for backward compatibility
    if (onCollapsedChange) {
      onCollapsedChange(newMode === 'collapsed')
    }
  }, [onModeChange, onCollapsedChange])

  // Convenience methods
  const expand = React.useCallback(() => setMode('expanded'), [setMode])
  const collapse = React.useCallback(() => setMode('collapsed'), [setMode])
  const hide = React.useCallback(() => setMode('hidden'), [setMode])

  // Backward compatibility
  const collapsed = mode === 'collapsed'
  const setCollapsed = React.useCallback((value: boolean) => {
    setMode(value ? 'collapsed' : 'expanded')
  }, [setMode])
  const toggleCollapsed = React.useCallback(() => {
    setMode(mode === 'collapsed' ? 'expanded' : 'collapsed')
  }, [mode, setMode])

  const value: SidebarContextValue = {
    mode,
    setMode,
    expand,
    collapse,
    hide,
    // Backward compatibility
    collapsed,
    setCollapsed,
    toggleCollapsed,
  }

  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  )
}

/* ============================================
   SIDEBAR CONTAINER
   ============================================ */

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Controlled mode (use with SidebarProvider for uncontrolled) */
  mode?: SidebarMode
  /** @deprecated Use mode instead */
  collapsed?: boolean
  /** Collapsed width in pixels */
  collapsedWidth?: number
  /** Expanded width in pixels */
  expandedWidth?: number
}

const Sidebar = React.forwardRef<HTMLDivElement, SidebarProps>(
  ({ className, mode: controlledMode, collapsed: controlledCollapsed, collapsedWidth = 64, expandedWidth = 256, ...props }, ref) => {
    // Try to use context, fallback to controlled props
    const context = React.useContext(SidebarContext)
    
    // Determine mode from context, controlled mode prop, or legacy collapsed prop
    let currentMode: SidebarMode = 'expanded'
    if (context) {
      currentMode = context.mode
    } else if (controlledMode) {
      currentMode = controlledMode
    } else if (controlledCollapsed !== undefined) {
      currentMode = controlledCollapsed ? 'collapsed' : 'expanded'
    }

    // Calculate width based on mode
    const width = currentMode === 'hidden' ? 0 
      : currentMode === 'collapsed' ? collapsedWidth 
      : expandedWidth

    return (
      <div
        ref={ref}
        style={{
          width,
          minWidth: width,
        }}
        className={cn(
          "flex h-full flex-col bg-white border-r border-gray-200",
          "dark:bg-dark-surface dark:border-dark-border/30",
          // Smooth transitions - slower for a more polished feel
          "transition-[width,min-width,opacity,transform] duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
          "overflow-hidden",
          // Hidden mode: fade out and disable interactions (transform controlled by implementing component)
          currentMode === 'hidden' && "opacity-0 pointer-events-none",
          className
        )}
        {...props}
      />
    )
  }
)
Sidebar.displayName = "Sidebar"

/* ============================================
   SIDEBAR COLLAPSE TRIGGER
   ============================================ */

interface SidebarCollapseTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Show as floating button on the edge */
  floating?: boolean
}

const SidebarCollapseTrigger = React.forwardRef<HTMLButtonElement, SidebarCollapseTriggerProps>(
  ({ className, floating = false, ...props }, ref) => {
    const { collapsed, toggleCollapsed } = useSidebar()

    if (floating) {
      return (
        <button
          ref={ref}
          onClick={toggleCollapsed}
          className={cn(
            "absolute -right-3 top-6 z-50",
            "flex h-6 w-6 items-center justify-center",
            "rounded-full border border-gray-200 bg-white shadow-sm",
            "hover:bg-gray-50 hover:shadow-md",
            "dark:border-dark-border/50 dark:bg-dark-surface-2 dark:hover:bg-dark-border/50",
            "transition-all duration-200",
            className
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          {...props}
        >
          {collapsed ? (
            <ChevronRightIcon className="h-3.5 w-3.5 text-gray-500 dark:text-gray-400" />
          ) : (
            <ChevronLeftIcon className="h-3.5 w-3.5 text-gray-500 dark:text-gray-400" />
          )}
        </button>
      )
    }

    return (
      <button
        ref={ref}
        onClick={toggleCollapsed}
        className={cn(
          "flex items-center justify-center",
          "w-8 h-8 rounded-lg",
          "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
          "text-gray-500 dark:text-gray-400",
          "transition-colors duration-150",
          className
        )}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        {...props}
      >
        {collapsed ? (
          <ChevronRightIcon className="h-4 w-4" />
        ) : (
          <ChevronLeftIcon className="h-4 w-4" />
        )}
      </button>
    )
  }
)
SidebarCollapseTrigger.displayName = "SidebarCollapseTrigger"

/* ============================================
   SIDEBAR HEADER
   ============================================ */

interface SidebarHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Show separate collapse toggle button in header (not needed if using SidebarLogo with showToggleOnHover) */
  showCollapseToggle?: boolean
}

const SidebarHeader = React.forwardRef<HTMLDivElement, SidebarHeaderProps>(
  ({ className, showCollapseToggle = false, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = context ? context.mode !== 'expanded' : false

    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center",
          isCollapsed ? "justify-center px-2 py-4" : "px-4 py-4",
          className
        )}
        {...props}
      >
        {children}
        {showCollapseToggle && context && !isCollapsed && (
          <SidebarCollapseTrigger />
        )}
      </div>
    )
  }
)
SidebarHeader.displayName = "SidebarHeader"

/* ============================================
   SIDEBAR LOGO (Consistent branding)
   ============================================ */

interface SidebarLogoProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Override collapsed state from context */
  collapsed?: boolean
  /** Show toggle button (ChatGPT style - always visible when expanded, hover to reveal when collapsed) */
  showToggleOnHover?: boolean
}

const SidebarLogo = React.forwardRef<HTMLDivElement, SidebarLogoProps>(
  ({ className, collapsed: controlledCollapsed, showToggleOnHover = false, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)
    const [isHovered, setIsHovered] = React.useState(false)

    // When collapsed: show toggle on hover over the "e"
    // When expanded: always show the toggle in top-right
    const showToggleOverlay = showToggleOnHover && context && isCollapsed && isHovered

    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center transition-all duration-300 relative",
          isCollapsed ? "justify-center" : "justify-between flex-1",
          className
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        {...props}
      >
        {/* Logo content */}
        <div className={cn(
          "flex items-baseline transition-opacity duration-200",
          showToggleOverlay && "opacity-0"
        )}>
          {isCollapsed ? (
            // "eliza" word - sans-serif bold in charcoal/white (smaller to fit collapsed width)
            <span 
              className="font-sans text-sm font-bold text-charcoal dark:text-white tracking-tight cursor-pointer"
              onClick={context?.toggleCollapsed}
            >
              eliza
            </span>
          ) : (
            <>
              <span className="font-sans text-lg font-bold text-charcoal dark:text-white tracking-tight">eliza</span>
              <span className="font-title text-lg italic text-eliza-red">forge</span>
            </>
          )}
        </div>

        {/* Toggle button - always visible when expanded, overlay when collapsed+hovered */}
        {showToggleOnHover && context && (
          <>
            {/* Expanded: show toggle button on the right */}
            {!isCollapsed && (
              <button
                onClick={context.toggleCollapsed}
                className={cn(
                  "flex items-center justify-center",
                  "w-8 h-8 rounded-lg",
                  "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
                  "text-gray-500 dark:text-gray-400",
                  "transition-colors duration-150"
                )}
                aria-label="Collapse sidebar"
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
            )}

            {/* Collapsed: show toggle overlay on hover */}
            {isCollapsed && (
              <div className={cn(
                "absolute inset-0 flex items-center justify-center",
                "transition-opacity duration-200",
                showToggleOverlay ? "opacity-100" : "opacity-0 pointer-events-none"
              )}>
                <button
                  onClick={context.toggleCollapsed}
                  className={cn(
                    "flex items-center justify-center",
                    "w-8 h-8 rounded-lg",
                    "bg-gray-100 dark:bg-dark-surface-2",
                    "text-gray-600 dark:text-gray-300"
                  )}
                  aria-label="Expand sidebar"
                >
                  <ChevronRightIcon className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    )
  }
)
SidebarLogo.displayName = "SidebarLogo"

/* ============================================
   SIDEBAR CONTENT (Scrollable area)
   ============================================ */

const SidebarContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex-1 overflow-y-auto py-2", className)}
    {...props}
  />
))
SidebarContent.displayName = "SidebarContent"

/* ============================================
   SIDEBAR SECTION
   ============================================ */

interface SidebarSectionProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string
  /** Override collapsed state from context */
  collapsed?: boolean
}

const SidebarSection = React.forwardRef<HTMLDivElement, SidebarSectionProps>(
  ({ className, title, collapsed: controlledCollapsed, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)

    return (
      <div ref={ref} className={cn("px-2 py-2", className)} {...props}>
        {title && (
          <div className="relative h-7 overflow-hidden">
            {/* Title text - fades out when collapsed */}
            <div 
              className={cn(
                "px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 whitespace-nowrap",
                "transition-all duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                isCollapsed ? "opacity-0 -translate-x-2" : "opacity-100 translate-x-0"
              )}
            >
              {title}
            </div>
            {/* Divider line - fades in when collapsed */}
            <div 
              className={cn(
                "absolute inset-0 flex justify-center items-center",
                "transition-all duration-[350ms] ease-[cubic-bezier(0.4,0,0.2,1)]",
                isCollapsed ? "opacity-100" : "opacity-0"
              )}
            >
              <div className="w-6 h-px bg-gray-200 dark:bg-dark-border/50" />
            </div>
          </div>
        )}
        <div className="space-y-0.5">{children}</div>
      </div>
    )
  }
)
SidebarSection.displayName = "SidebarSection"

/* ============================================
   SIDEBAR ITEM (Supports both flat and expandable)
   ============================================ */

interface SidebarItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode
  isActive?: boolean
  /** Override collapsed state from context */
  collapsed?: boolean
  badge?: string | number
  defaultOpen?: boolean
  /** Tooltip text when collapsed (defaults to text content) */
  tooltip?: string
  children?: React.ReactNode
}

const SidebarItem = React.forwardRef<HTMLButtonElement, SidebarItemProps>(
  ({ className, icon, isActive, collapsed: controlledCollapsed, badge, defaultOpen = false, tooltip, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)

    // Check if this item has sub-items (React elements as children beyond text)
    const childArray = React.Children.toArray(children)
    const textContent = childArray.filter(child => typeof child === 'string' || typeof child === 'number')
    const subItems = childArray.filter(child => React.isValidElement(child))
    const hasSubItems = subItems.length > 0
    
    const [isOpen, setIsOpen] = React.useState(defaultOpen || isActive)
    const [showTooltip, setShowTooltip] = React.useState(false)

    const tooltipText = tooltip || textContent.join(' ')

    // If it has sub-items, render as expandable group
    if (hasSubItems && !isCollapsed) {
      return (
        <div className={className}>
          <button
            ref={ref}
            onClick={() => setIsOpen(!isOpen)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium",
              "transition-colors duration-150",
              "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
              isActive || isOpen
                ? "text-charcoal dark:text-white"
                : "text-charcoal dark:text-gray-300"
            )}
            {...props}
          >
            {icon && (
              <span className={cn(
                "flex-shrink-0",
                isActive ? "text-eliza-red" : "text-gray-500 dark:text-gray-400"
              )}>
                {icon}
              </span>
            )}
            <span className="flex-1 text-left whitespace-nowrap overflow-hidden text-ellipsis">{textContent}</span>
            <ChevronDownIcon
              className={cn(
                "h-4 w-4 text-gray-400 transition-transform duration-200 flex-shrink-0",
                isOpen && "rotate-180"
              )}
            />
          </button>
          
          {/* Sub-items */}
          <div
            className={cn(
              "overflow-hidden transition-all duration-200",
              isOpen ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
            )}
          >
            <div className="py-1 space-y-0.5">
              {subItems}
            </div>
          </div>
        </div>
      )
    }

    // Simple item (no sub-items) or collapsed with sub-items
    const buttonContent = (
      <button
        ref={ref}
        onMouseEnter={() => isCollapsed && setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={cn(
          "w-full flex items-center py-2 rounded-lg text-sm font-medium",
          "transition-colors duration-150",
          "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
          isActive
            ? "bg-eliza-red/15 text-eliza-red border border-eliza-red/25 dark:bg-eliza-red/25 dark:text-white dark:border-eliza-red/40"
            : "text-charcoal dark:text-gray-300 border border-transparent",
          isCollapsed ? "justify-center px-2" : "gap-3 px-3",
          className
        )}
        {...props}
      >
        {icon && (
          <span className={cn(
            "flex-shrink-0 transition-transform duration-[350ms] ease-out",
            isActive ? "text-eliza-red dark:text-white" : "text-gray-500 dark:text-gray-400"
          )}>
            {icon}
          </span>
        )}
        {/* Text content - only rendered when expanded */}
        {!isCollapsed && (
          <span className="flex-1 truncate text-left whitespace-nowrap overflow-hidden">
            {textContent}
          </span>
        )}
        {/* Badge - inline when expanded */}
        {!isCollapsed && badge && (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-eliza-red px-1.5 text-[10px] font-semibold text-white flex-shrink-0 ml-auto">
            {badge}
          </span>
        )}
        {/* Badge - absolute positioned when collapsed */}
        {isCollapsed && badge && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-eliza-red px-1 text-[9px] font-semibold text-white">
            {badge}
          </span>
        )}
      </button>
    )

    // Wrap with tooltip when collapsed
    if (isCollapsed) {
      return (
        <div className="relative">
          {buttonContent}
          {showTooltip && tooltipText && (
            <div
              className={cn(
                "absolute left-full top-1/2 -translate-y-1/2 ml-2 z-50",
                "px-2.5 py-1.5 rounded-md",
                "bg-charcoal text-white text-xs font-medium whitespace-nowrap",
                "dark:bg-white dark:text-charcoal",
                "shadow-lg",
                "transition-opacity duration-150"
              )}
            >
              {tooltipText}
              {/* Arrow */}
              <div
                className={cn(
                  "absolute right-full top-1/2 -translate-y-1/2",
                  "border-4 border-transparent border-r-charcoal",
                  "dark:border-r-white"
                )}
              />
            </div>
          )}
        </div>
      )
    }

    return buttonContent
  }
)
SidebarItem.displayName = "SidebarItem"

/* ============================================
   SIDEBAR SUB-ITEM (For nested items)
   ============================================ */

interface SidebarSubItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  isActive?: boolean
}

const SidebarSubItem = React.forwardRef<HTMLButtonElement, SidebarSubItemProps>(
  ({ className, isActive, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "w-full text-left py-2 pl-11 pr-3 text-sm rounded-r-lg transition-colors",
        isActive
          ? "text-eliza-red font-medium bg-eliza-red/10 border-l-2 border-eliza-red dark:text-white dark:bg-eliza-red/20 dark:border-eliza-red"
          : "text-gray-600 hover:text-charcoal hover:bg-gray-50 border-l-2 border-transparent dark:text-gray-400 dark:hover:text-white dark:hover:bg-dark-surface-2",
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
)
SidebarSubItem.displayName = "SidebarSubItem"

/* ============================================
   SIDEBAR ACTION BUTTON (Like "+ New project")
   ============================================ */

interface SidebarActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode
  /** Override collapsed state from context */
  collapsed?: boolean
}

const SidebarAction = React.forwardRef<HTMLButtonElement, SidebarActionProps>(
  ({ className, icon, collapsed: controlledCollapsed, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)

    return (
      <button
        ref={ref}
        className={cn(
          "flex items-center justify-center gap-2 rounded-full",
          "bg-charcoal text-white py-2.5",
          "hover:bg-charcoal/90 transition-all duration-200",
          "dark:bg-dark-surface-2 dark:text-gray-100 dark:hover:bg-dark-border/50 dark:border dark:border-dark-border/30",
          "text-sm font-medium",
          isCollapsed ? "mx-2 w-10 h-10 px-0" : "mx-3 mb-3 px-4",
          className
        )}
        {...props}
      >
        {icon}
        {!isCollapsed && children}
      </button>
    )
  }
)
SidebarAction.displayName = "SidebarAction"

/* ============================================
   SIDEBAR LABEL (For sections like "Starred", "Recents")
   ============================================ */

interface SidebarLabelProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Override collapsed state from context */
  collapsed?: boolean
}

const SidebarLabel = React.forwardRef<HTMLDivElement, SidebarLabelProps>(
  ({ className, collapsed: controlledCollapsed, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)

    if (isCollapsed) return null
    return (
      <div
        ref={ref}
        className={cn(
          "px-5 py-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500",
          "whitespace-nowrap overflow-hidden",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
SidebarLabel.displayName = "SidebarLabel"

/* ============================================
   SIDEBAR LINK (Small text items for recents/starred)
   ============================================ */

interface SidebarLinkProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  isActive?: boolean
  /** Override collapsed state from context */
  collapsed?: boolean
}

const SidebarLink = React.forwardRef<HTMLButtonElement, SidebarLinkProps>(
  ({ className, isActive, collapsed: controlledCollapsed, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)

    if (isCollapsed) return null
    return (
      <button
        ref={ref}
        className={cn(
          "w-full text-left px-5 py-1.5 text-sm truncate",
          "hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors",
          isActive
            ? "text-eliza-red"
            : "text-gray-600 dark:text-gray-400",
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
SidebarLink.displayName = "SidebarLink"

/* ============================================
   SIDEBAR FOOTER
   ============================================ */

interface SidebarFooterProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Override collapsed state from context */
  collapsed?: boolean
  /** Show expand button when collapsed (set to false if using SidebarLogo with showToggleOnHover) */
  showExpandButton?: boolean
}

const SidebarFooter = React.forwardRef<HTMLDivElement, SidebarFooterProps>(
  ({ className, collapsed: controlledCollapsed, showExpandButton = false, children, ...props }, ref) => {
    const context = React.useContext(SidebarContext)
    const isCollapsed = controlledCollapsed ?? (context ? context.mode !== 'expanded' : false)

    return (
      <div
        ref={ref}
        className={cn(
          "mt-auto border-t border-gray-100 py-3",
          "dark:border-dark-border/30",
          "transition-all duration-200",
          isCollapsed ? "px-2 flex flex-col items-center" : "px-4",
          className
        )}
        {...props}
      >
        {children}
        {isCollapsed && showExpandButton && context && (
          <SidebarCollapseTrigger className="mt-2" />
        )}
      </div>
    )
  }
)
SidebarFooter.displayName = "SidebarFooter"

/* ============================================
   SIDEBAR SEPARATOR
   ============================================ */

const SidebarSeparator = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("mx-3 my-2 h-px bg-gray-100 dark:bg-dark-border/30", className)}
    {...props}
  />
))
SidebarSeparator.displayName = "SidebarSeparator"

export {
  // Context
  SidebarProvider,
  useSidebar,
  // Container
  Sidebar,
  SidebarCollapseTrigger,
  // Header
  SidebarHeader,
  SidebarLogo,
  // Content
  SidebarContent,
  SidebarSection,
  SidebarItem,
  SidebarSubItem,
  // Actions
  SidebarAction,
  SidebarLabel,
  SidebarLink,
  // Footer
  SidebarFooter,
  SidebarSeparator,
}

export type { SidebarProps, SidebarItemProps, SidebarSectionProps }

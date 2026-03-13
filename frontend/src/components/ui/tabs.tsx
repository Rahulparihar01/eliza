/**
 * Tabs - Tab Switcher Component
 * 
 * A container with tabs on top to switch between different content panels.
 * Follows the Eliza Forge design system.
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

/* ============================================
   TABS CONTEXT
   ============================================ */

interface TabsContextValue {
  activeTab: string
  setActiveTab: (value: string) => void
}

const TabsContext = React.createContext<TabsContextValue | undefined>(undefined)

function useTabsContext() {
  const context = React.useContext(TabsContext)
  if (!context) {
    throw new Error("Tabs components must be used within a Tabs provider")
  }
  return context
}

/* ============================================
   TABS ROOT
   ============================================ */

interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue: string
  value?: string
  onValueChange?: (value: string) => void
}

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  ({ className, defaultValue, value, onValueChange, children, ...props }, ref) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue)
    
    const activeTab = value ?? internalValue
    const setActiveTab = React.useCallback((newValue: string) => {
      if (!value) {
        setInternalValue(newValue)
      }
      onValueChange?.(newValue)
    }, [value, onValueChange])

    return (
      <TabsContext.Provider value={{ activeTab, setActiveTab }}>
        <div ref={ref} className={cn("w-full", className)} {...props}>
          {children}
        </div>
      </TabsContext.Provider>
    )
  }
)
Tabs.displayName = "Tabs"

/* ============================================
   TABS LIST (Container for tab triggers)
   ============================================ */

interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "pills" | "underline"
}

const TabsList = React.forwardRef<HTMLDivElement, TabsListProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1",
        variant === "default" && "bg-gray-100 dark:bg-dark-surface-2 p-1 rounded-xl",
        variant === "pills" && "gap-2",
        variant === "underline" && "border-b border-gray-200 dark:border-dark-border/30 gap-0",
        className
      )}
      role="tablist"
      {...props}
    />
  )
)
TabsList.displayName = "TabsList"

/* ============================================
   TAB TRIGGER (Individual tab button)
   ============================================ */

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
  variant?: "default" | "pills" | "underline"
}

const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, value, variant = "default", children, ...props }, ref) => {
    const { activeTab, setActiveTab } = useTabsContext()
    const isActive = activeTab === value

    return (
      <button
        ref={ref}
        role="tab"
        aria-selected={isActive}
        onClick={() => setActiveTab(value)}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-all",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-eliza-red focus-visible:ring-offset-2",
          "disabled:pointer-events-none disabled:opacity-50",
          
          // Default variant (contained tabs)
          variant === "default" && [
            "px-4 py-2 rounded-lg",
            isActive
              ? "bg-white text-charcoal shadow-sm dark:bg-dark-surface dark:text-white"
              : "text-gray-600 hover:text-charcoal dark:text-gray-400 dark:hover:text-white"
          ],
          
          // Pills variant
          variant === "pills" && [
            "px-4 py-2 rounded-full border",
            isActive
              ? "bg-eliza-red/10 text-eliza-red border-eliza-red/25 dark:bg-eliza-red/20 dark:text-white dark:border-eliza-red/40"
              : "text-gray-600 border-gray-200 hover:border-gray-300 hover:text-charcoal dark:text-gray-400 dark:border-dark-border/50 dark:hover:text-white dark:hover:border-dark-border"
          ],
          
          // Underline variant
          variant === "underline" && [
            "px-4 py-3 border-b-2 -mb-px",
            isActive
              ? "border-eliza-red text-eliza-red dark:text-white dark:border-eliza-red"
              : "border-transparent text-gray-600 hover:text-charcoal hover:border-gray-300 dark:text-gray-400 dark:hover:text-white dark:hover:border-dark-border"
          ],
          
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
TabsTrigger.displayName = "TabsTrigger"

/* ============================================
   TAB CONTENT (Panel that shows when active)
   ============================================ */

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
}

const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, value, children, ...props }, ref) => {
    const { activeTab } = useTabsContext()
    
    if (activeTab !== value) return null

    return (
      <div
        ref={ref}
        role="tabpanel"
        className={cn("mt-4 focus-visible:outline-none", className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)
TabsContent.displayName = "TabsContent"

export { Tabs, TabsList, TabsTrigger, TabsContent }
export type { TabsProps, TabsListProps, TabsTriggerProps, TabsContentProps }

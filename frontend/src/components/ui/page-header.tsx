/**
 * Page Layout Components - Consistent page structure
 * 
 * Provides standardized page layouts with aligned headers and content.
 * Uses the Eliza Forge design system.
 * 
 * LAYOUT TYPES:
 * 
 * 1. CENTERED (default) - For admin pages, settings, list views
 *    Content is constrained to maxWidth and centered on the page.
 * 
 *   <Page layout="centered" maxWidth="2xl">
 *     <PageHeader title="Search Templates" />
 *     <PageBody>...</PageBody>
 *   </Page>
 * 
 * 2. FULL-WIDTH - For productivity spaces, split panels, workspaces
 *    Content uses full available width (with padding).
 * 
 *   <Page layout="full-width">
 *     <PageHeader title="Search Results" />
 *     <PageBody>
 *       <div className="flex flex-1 min-h-0">
 *         <div className="w-2/5">List</div>
 *         <div className="flex-1">Detail</div>
 *       </div>
 *     </PageBody>
 *   </Page>
 * 
 * LEGACY PATTERN (Still supported):
 * 
 *   <PageHeader title="Dashboard" maxWidth="xl" />
 *   <PageContent maxWidth="xl">...</PageContent>
 */

import * as React from "react"
import { cn } from "../../shared/lib/cn"

/* ============================================
   SHARED MAX WIDTH CLASSES
   ============================================ */

type MaxWidth = "sm" | "md" | "lg" | "xl" | "2xl" | "full"

const maxWidthClasses: Record<MaxWidth, string> = {
  sm: "max-w-2xl",
  md: "max-w-4xl",
  lg: "max-w-5xl",
  xl: "max-w-6xl",
  "2xl": "max-w-[1600px]",
  full: "max-w-full",
}

/* ============================================
   LAYOUT TYPES
   ============================================ */

type PageLayout = "centered" | "full-width"

/* ============================================
   PAGE CONTEXT (for passing layout settings to children)
   ============================================ */

interface PageContextValue {
  maxWidth: MaxWidth
  layout: PageLayout
}

const PageContext = React.createContext<PageContextValue | null>(null)

function usePageContext() {
  return React.useContext(PageContext)
}

/* ============================================
   PAGE CONTAINER
   ============================================ */

interface PageProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  /** 
   * Layout type:
   * - "centered" (default): Content constrained to maxWidth and centered
   * - "full-width": Content uses full available width (for productivity spaces)
   */
  layout?: PageLayout
  /** Max width for content (only applies when layout="centered") */
  maxWidth?: MaxWidth
  /** Background color variant */
  variant?: "default" | "plain"
}

const Page = React.forwardRef<HTMLDivElement, PageProps>(
  ({ className, children, layout = "centered", maxWidth = "2xl", variant = "default", ...props }, ref) => {
    return (
      <PageContext.Provider value={{ maxWidth, layout }}>
        <div
          ref={ref}
          className={cn(
            "h-full overflow-y-auto scrollbar-gutter-stable",
            variant === "default" && "bg-gray-50 dark:bg-dark-bg",
            variant === "plain" && "bg-white dark:bg-dark-surface",
            // For full-width layout, use flex-col to allow children to stretch
            layout === "full-width" && "flex flex-col",
            className
          )}
          style={{ scrollbarGutter: 'stable' }}
          {...props}
        >
          {children}
        </div>
      </PageContext.Provider>
    )
  }
)
Page.displayName = "Page"

/* ============================================
   PAGE HEADER (for use inside Page)
   ============================================ */

interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Page title */
  title: string
  /** Optional description/subtitle */
  description?: string
  /** Optional action buttons (right side) */
  actions?: React.ReactNode
  /** Optional breadcrumb or back link (above title) */
  breadcrumb?: React.ReactNode
  /** Whether to show a bottom border (default: false) */
  bordered?: boolean
  /** 
   * Max width constraint (only needed when NOT inside a Page component)
   * When using inside Page component, this is inherited from Page.
   */
  maxWidth?: MaxWidth
}

const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ className, title, description, actions, breadcrumb, bordered = false, maxWidth: maxWidthProp, ...props }, ref) => {
    const pageContext = usePageContext()
    const maxWidth = maxWidthProp || pageContext?.maxWidth || "2xl"
    const layout = pageContext?.layout || "centered"
    
    const content = (
      <>
        {breadcrumb && (
          <div className="mb-2">
            {breadcrumb}
          </div>
        )}
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="font-title text-h1 text-charcoal dark:text-gray-100 truncate">
              {title}
            </h1>
            {description && (
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                {description}
              </p>
            )}
          </div>
          {actions && (
            <div className="flex items-center gap-3 flex-shrink-0">
              {actions}
            </div>
          )}
        </div>
      </>
    )

    // For full-width layout, don't apply max-width or centering
    // For centered layout, center content with max-width
    return (
      <header
        ref={ref}
        className={cn(
          "flex-shrink-0",
          bordered && "border-b border-gray-200 dark:border-dark-border",
          className
        )}
        {...props}
      >
        <div className={cn(
          "px-8 py-6",
          layout === "centered" && cn("mx-auto", maxWidthClasses[maxWidth])
        )}>
          {content}
        </div>
      </header>
    )
  }
)
PageHeader.displayName = "PageHeader"

/* ============================================
   PAGE BODY (for use inside Page)
   ============================================ */

interface PageBodyProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  /** 
   * Whether the body should fill remaining height (for full-width layouts with split panels)
   * When true, adds flex-1 and min-h-0 for proper overflow handling
   */
  fill?: boolean
  /**
   * Whether to include default padding (default: true)
   * Set to false when you need edge-to-edge content like split panels
   */
  padded?: boolean
}

const PageBody = React.forwardRef<HTMLDivElement, PageBodyProps>(
  ({ className, children, fill = false, padded = true, ...props }, ref) => {
    const pageContext = usePageContext()
    const maxWidth = pageContext?.maxWidth || "2xl"
    const layout = pageContext?.layout || "centered"
    
    return (
      <div
        ref={ref}
        className={cn(
          // For centered layout, apply max-width and centering
          layout === "centered" && cn("mx-auto", maxWidthClasses[maxWidth]),
          // Padding (can be disabled for edge-to-edge content)
          padded && (layout === "centered" ? "px-8 pt-4 pb-6" : "px-8 py-4"),
          // Fill remaining height (for split panels)
          fill && "flex-1 min-h-0 flex flex-col",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
PageBody.displayName = "PageBody"

/* ============================================
   PAGE CONTENT (Legacy - for backward compatibility)
   Use PageBody inside Page component instead.
   ============================================ */

interface PageContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  /** Max width constraint */
  maxWidth?: MaxWidth
}

const PageContent = React.forwardRef<HTMLDivElement, PageContentProps>(
  ({ className, children, maxWidth = "2xl", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "px-8 py-6",
          maxWidthClasses[maxWidth],
          "mx-auto",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
PageContent.displayName = "PageContent"

/* ============================================
   SECTION HEADER
   ============================================ */

interface SectionHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Section title */
  title: string
  /** Optional description */
  description?: string
  /** Optional icon (displayed before title) */
  icon?: React.ReactNode
  /** Optional action buttons (right side) */
  actions?: React.ReactNode
}

const SectionHeader = React.forwardRef<HTMLDivElement, SectionHeaderProps>(
  ({ className, title, description, icon, actions, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("flex items-center justify-between gap-4 mb-6", className)}
        {...props}
      >
        <div className="min-w-0 flex-1">
          <h2 className="font-subtitle text-h2 text-charcoal dark:text-gray-100 flex items-center gap-2">
            {icon && (
              <span className="text-gray-400 flex-shrink-0">{icon}</span>
            )}
            <span className="truncate">{title}</span>
          </h2>
          {description && (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {description}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-3 flex-shrink-0">
            {actions}
          </div>
        )}
      </div>
    )
  }
)
SectionHeader.displayName = "SectionHeader"

export { Page, PageHeader, PageBody, PageContent, SectionHeader }
export type { PageProps, PageHeaderProps, PageBodyProps, PageContentProps, SectionHeaderProps, MaxWidth, PageLayout }

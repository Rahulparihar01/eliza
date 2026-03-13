/**
 * UI Components - Eliza Forge Design System
 * 
 * Central export for all shadcn-style UI primitives.
 */

export { Button, buttonVariants } from './button'
export type { ButtonProps } from './button'

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent } from './card'

// Panel - Flat container without shadow (for admin interfaces)
export { Panel, PanelHeader, PanelTitle, PanelDescription, PanelBody, PanelFooter } from './panel'

export { Input } from './input'
export type { InputProps } from './input'

export { Textarea } from './textarea'
export type { TextareaProps } from './textarea'

export { Badge, badgeVariants } from './badge'
export type { BadgeProps } from './badge'

export { Switch } from './switch'
export type { SwitchProps } from './switch'

export { Label } from './label'
export type { LabelProps } from './label'

export { Separator } from './separator'

// Sidebar - Unified navigation component (supports both flat and expandable, collapsible)
export {
  // Context for collapse state
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
} from './sidebar'
export type { SidebarMode, SidebarProps, SidebarItemProps, SidebarSectionProps } from './sidebar'

// Sidebar Content Switch - Animated content transitions for sidebar
export { SidebarContentSwitch } from './sidebar-content-switch'
export type { SidebarContentSwitchProps } from './sidebar-content-switch'

// Tenant Switcher - Multi-tenant organization selector
export { TenantSwitcher, TenantSwitcherCompact } from './tenant-switcher'
export type { Tenant, TenantSwitcherProps, TenantSwitcherCompactProps } from './tenant-switcher'

// Tabs - Tab switcher component
export { Tabs, TabsList, TabsTrigger, TabsContent } from './tabs'
export type { TabsProps, TabsListProps, TabsTriggerProps, TabsContentProps } from './tabs'

// Modal - Dialog component
export { Modal, ModalBackdrop, ModalContent, ModalHeader, ModalTitle, ModalDescription, ModalBody, ModalFooter } from './modal'
export type { ModalProps, ModalBackdropProps, ModalContentProps, ModalHeaderProps } from './modal'

export { ModalFloatingActions } from './modal-floating-actions'
export type { ModalFloatingActionsProps } from './modal-floating-actions'

// Chip - Toggleable pill component
export { Chip, ChipGroup, chipVariants } from './chip'
export type { ChipProps, ChipGroupProps } from './chip'

// Avatar - User profile picture
export { Avatar, AvatarGroup, avatarVariants } from './avatar'
export type { AvatarProps, AvatarGroupProps } from './avatar'

// Tooltip - Hover hint
export { Tooltip } from './tooltip'
export type { TooltipProps } from './tooltip'

// Checkbox - Form checkbox
export { Checkbox } from './checkbox'
export type { CheckboxProps } from './checkbox'

// Spinner - Loading indicator
export { Spinner, LoadingOverlay, spinnerVariants } from './spinner'
export type { SpinnerProps, LoadingOverlayProps } from './spinner'

// Alert - Inline banner
export { Alert, alertVariants } from './alert'
export type { AlertProps } from './alert'

// Skeleton - Loading placeholder
export { Skeleton, SkeletonAvatar, SkeletonText, SkeletonCard, SkeletonTableRow } from './skeleton'
export type { SkeletonProps } from './skeleton'

// Select - Form dropdown
export { Select, SelectOption, SelectGroup } from './select'
export type { SelectProps, SelectOptionProps, SelectGroupProps } from './select'

export { SliderInput } from './slider-input'
export type { SliderInputProps } from './slider-input'

// Toast - Notifications
export { Toast, ToastContainer, useToast, toastVariants } from './toast'
export type { ToastProps, ToastContainerProps, ToastInput, UseToastReturn } from './toast'

// Dropdown Menu - Action menus
export { DropdownMenu, DropdownTrigger, DropdownContent, DropdownItem, DropdownLabel, DropdownSeparator, DropdownSubmenu } from './dropdown-menu'
export type { DropdownMenuProps, DropdownContentProps, DropdownItemProps, DropdownSubmenuProps } from './dropdown-menu'

// Radio Group - Single select
export { RadioGroup, RadioGroupItem, RadioCard } from './radio-group'
export type { RadioGroupProps, RadioGroupItemProps, RadioCardProps } from './radio-group'

// Progress - Progress bars
export { Progress, CircularProgress, progressVariants, progressBarVariants } from './progress'
export type { ProgressProps, CircularProgressProps } from './progress'

// Accordion - Collapsible sections
export { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from './accordion'
export type { AccordionProps, AccordionItemProps, AccordionTriggerProps } from './accordion'

// MultiSelect - Multi-select dropdown
export { MultiSelect, MultiSelectOption, MultiSelectGroup, MultiSelectActions } from './multi-select'
export type { MultiSelectProps, MultiSelectOptionProps, MultiSelectGroupProps } from './multi-select'

// Card Variants - Extended card components
export { ImageCard, MetricCard, StatCard, ContentCard, LinkCard, ProgressCard } from './card-variants'
export type { ImageCardProps, MetricCardProps, StatCardProps, ContentCardProps, LinkCardProps, ProgressCardProps } from './card-variants'

// Date Picker - Date selection
export { Calendar, DatePicker, DateRangePicker } from './date-picker'
export type { CalendarProps, DatePickerProps, DateRangePickerProps, DateRange } from './date-picker'

// Prompt Bar - AI input variants
export { PromptBar, PromptBarWithAttachments, PromptBarWithTools, PromptBarWithDomain } from './prompt-bar'
export type { PromptBarProps, PromptBarWithAttachmentsProps, PromptBarWithToolsProps, PromptBarWithDomainProps, Attachment, Tool, Domain } from './prompt-bar'

// Breadcrumb - Navigation trail
export { Breadcrumb, BreadcrumbItem, BreadcrumbEllipsis } from './breadcrumb'
export type { BreadcrumbProps, BreadcrumbItemProps, BreadcrumbEllipsisProps } from './breadcrumb'

// Pagination - Page navigation
export { Pagination, SimplePagination } from './pagination'
export type { PaginationProps, SimplePaginationProps } from './pagination'

// Combobox / Autocomplete - Searchable select
export { Combobox, MultiCombobox } from './combobox'
export type { ComboboxProps, ComboboxOption, MultiComboboxProps } from './combobox'

// Chat Components - Full chat UI
export {
  // Context
  ChatProvider,
  useChat,
  // Layout
  ChatContainer,
  ChatMessagesPane,
  ChatScrollArea,
  ChatInputArea,
  // Messages
  MessageBubble,
  MessageContent,
  messageBubbleVariants,
  // Indicators
  ThinkingIndicator,
  // Media
  ChatImage,
  ChatCodeBlock,
  // Canvas
  CanvasPanel,
  ArtifactButton,
} from './chat'
export type {
  ChatContainerProps,
  ChatMessagesPaneProps,
  ChatScrollAreaProps,
  MessageBubbleProps,
  ThinkingIndicatorProps,
  ExecutionStep,
  ChatImageProps,
  ChatCodeBlockProps,
  CanvasPanelProps,
  ArtifactButtonProps,
} from './chat'

// Page Layout - Consistent page headers and sections
export { Page, PageHeader, PageBody, PageContent, SectionHeader } from './page-header'
export type { PageProps, PageHeaderProps, PageBodyProps, PageContentProps, SectionHeaderProps, MaxWidth, PageLayout } from './page-header'

// DataTable - Data tables with sorting, pagination, selection
export { 
  DataTable, 
  DataTableCell, 
  DataTableBadge, 
  DataTableAvatar, 
  DataTableActions, 
  DataTableActionButton 
} from './data-table'
export type { 
  DataTableProps, 
  Column, 
  SortDirection, 
  SortState 
} from './data-table'

// Sidebar Context Panel - Contextual sub-navigation
export { SidebarContextPanel } from './sidebar-context-panel'
export type { ContextPanelItem } from './sidebar-context-panel'

// Sidebar Submenu - Simple list submenu for immersive navigation
export { SidebarSubmenu, SubmenuNavItem } from './sidebar-submenu'
export type { SidebarSubmenuProps, SubmenuNavItemProps, SubmenuItem } from './sidebar-submenu'

// Sidebar Conversation List - For chat apps with conversation history
export { SidebarConversationList } from './sidebar-conversation-list'
export type { SidebarConversation } from './sidebar-conversation-list'

// Domain Context Pill - For domain/context switching in headers
export { DomainContextPill, DEFAULT_DOMAINS } from './domain-context-pill'
export type { DomainOption } from './domain-context-pill'

// Toolbar - Top application bar
export {
  Toolbar,
  ToolbarSection,
  ToolbarDivider,
  ToolbarItem,
  ToolbarTextButton,
} from './toolbar'
export type {
  ToolbarProps,
  ToolbarSectionProps,
  ToolbarItemProps,
} from './toolbar'

// Citation Components - Inline citations and sources for RAG responses
export { InlineCitation, CitationGroup } from './inline-citation'
export type { InlineCitationProps, CitationGroupProps } from './inline-citation'

export { SourceCard, VerdictBadge } from './source-card'
export type { 
  SourceCardProps, 
  CitationVerdict, 
  CitationValidationResult as SourceCardValidationResult,
  CitationValidationState as SourceCardValidationState,
} from './source-card'

export { SourcesAccordion, parseCitation, parseSourcesFromSummary } from './sources-accordion'
export type { 
  SourcesAccordionProps, 
  Source,
  CitationValidationResult,
  CitationValidationState,
} from './sources-accordion'

export { PdfCanvasViewer } from './pdf-canvas-viewer'
export type { PdfCanvasViewerProps } from './pdf-canvas-viewer'

export { ChartCanvasViewer, ChartThumbnail } from './chart-canvas-viewer'
export type { ChartCanvasViewerProps, ChartThumbnailProps, ChartSuggestion, ChartData, ChartType } from './chart-canvas-viewer'

// Popover - Floating content panel for rich interactions
export {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverClose,
  PopoverHeader,
  PopoverBody,
  PopoverFooter,
  usePopoverContext,
} from './popover'
export type {
  PopoverProps,
  PopoverTriggerProps,
  PopoverContentProps,
  PopoverCloseProps,
  PopoverHeaderProps,
} from './popover'

// Banner - Full-width contextual notification bars
export { Banner, BannerContainer, bannerVariants } from './banner'
export type { BannerProps, BannerContainerProps } from './banner'

// Error Display - Error message components
export { 
  ErrorDisplay, 
  NetworkError, 
  AuthError, 
  NotFoundError, 
  ServerError, 
  AccessDeniedError 
} from './error-display'
export type { ErrorDisplayProps, ErrorStateProps } from './error-display'

// Error Boundary - React error boundary
export { ErrorBoundary } from './error-boundary'
export type { ErrorBoundaryProps } from './error-boundary'

// Sheet - Slide-in panel from edge of screen
export {
  Sheet,
  SheetBackdrop,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  useSheetContext,
} from './sheet'
export type {
  SheetProps,
  SheetBackdropProps,
  SheetContentProps,
  SheetHeaderProps,
  SheetSide,
  SheetSize,
} from './sheet'

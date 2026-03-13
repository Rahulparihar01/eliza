/**
 * Component Showcase - Eliza Forge Design System
 * 
 * A living style guide page to visually iterate on component designs.
 * Access at /design-system
 */

import React, { useState, useEffect } from 'react'
import {
  Button,
  Card,
  CardHeader, 
  CardTitle, 
  CardDescription, 
  CardContent,
  CardFooter,
  Panel,
  PanelHeader,
  PanelTitle,
  PanelDescription,
  PanelBody,
  PanelFooter,
  Input,
  Textarea,
  Badge,
  Switch,
  Label,
  Separator,
  SliderInput,
  // Unified Sidebar (Collapsible)
  SidebarProvider,
  Sidebar,
  SidebarCollapseTrigger,
  SidebarHeader,
  SidebarLogo,
  SidebarContent,
  SidebarSection,
  SidebarItem,
  SidebarSubItem,
  SidebarAction,
  SidebarLabel,
  SidebarLink,
  SidebarFooter,
  SidebarSeparator,
  // Tenant Switcher
  TenantSwitcher,
  TenantSwitcherCompact,
  // Tabs
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  // Modal
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  ModalFloatingActions,
  // Sheet
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  // Chip
  Chip,
  ChipGroup,
  // Avatar
  Avatar,
  AvatarGroup,
  // Tooltip
  Tooltip,
  // Checkbox
  Checkbox,
  // Spinner
  Spinner,
  LoadingOverlay,
  // Alert
  Alert,
  // Skeleton
  Skeleton,
  SkeletonAvatar,
  SkeletonText,
  SkeletonCard,
  // Select
  Select,
  SelectOption,
  SelectGroup,
  // Toast
  ToastContainer,
  useToast,
  // Dropdown Menu
  DropdownMenu,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
  DropdownLabel,
  DropdownSeparator,
  // Radio Group
  RadioGroup,
  RadioGroupItem,
  RadioCard,
  // Progress
  Progress,
  CircularProgress,
  // Accordion
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
  // MultiSelect
  MultiSelect,
  MultiSelectOption,
  MultiSelectGroup,
  MultiSelectActions,
  // Card Variants
  ImageCard,
  MetricCard,
  StatCard,
  ContentCard,
  LinkCard,
  ProgressCard,
  // Date Picker
  DatePicker,
  DateRangePicker,
  // Prompt Bar
  PromptBar,
  PromptBarWithAttachments,
  PromptBarWithTools,
  PromptBarWithDomain,
  // Chat Components
  ChatProvider,
  ChatContainer,
  ChatMessagesPane,
  ChatScrollArea,
  ChatInputArea,
  MessageBubble,
  MessageContent,
  ThinkingIndicator,
  ChatImage,
  ChatCodeBlock,
  CanvasPanel,
  ArtifactButton,
  // Breadcrumb
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbEllipsis,
  // Pagination
  Pagination,
  SimplePagination,
  // Combobox
  Combobox,
  MultiCombobox,
  // DataTable
  DataTable,
  DataTableBadge,
  DataTableAvatar,
  DataTableActions,
  DataTableActionButton,
  // Page Layout
  PageHeader,
  PageContent,
  SectionHeader,
  // Toolbar
  Toolbar,
  ToolbarSection,
  ToolbarDivider,
  ToolbarItem,
  ToolbarTextButton,
  // Sidebar Submenu
  SidebarSubmenu,
  // Citation Components
  InlineCitation,
  CitationGroup,
  SourceCard,
  SourcesAccordion,
  PdfCanvasViewer,
  // Chart Components
  ChartCanvasViewer,
  // Popover - Floating content panel
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverClose,
  PopoverHeader,
  PopoverBody,
  PopoverFooter,
  // Banner - Full-width notification bars
  Banner,
  BannerContainer,
  // Error Components
  ErrorDisplay,
  NetworkError,
  AuthError,
  NotFoundError,
  ServerError,
  AccessDeniedError,
  ErrorBoundary,
} from '../../components/ui'
import type { Column, SortState } from '../../components/ui'
import type { ComboboxOption } from '../../components/ui'
import type { Tenant } from '../../components/ui'
import {
  ArrowUpIcon,
  SparklesIcon,
  UserGroupIcon,
  ChartBarIcon,
  MagnifyingGlassIcon,
  BellIcon,
  SunIcon,
  MoonIcon,
  CalendarIcon,
  EnvelopeIcon,
  HomeIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  FolderIcon,
  ChatBubbleLeftRightIcon,
  StarIcon,
  PlusIcon,
  ShoppingBagIcon,
  ClipboardDocumentListIcon,
  CodeBracketIcon,
  UsersIcon,
  PencilIcon,
  TrashIcon,
  EyeIcon,
  BuildingOffice2Icon,
  ChevronDownIcon,
  CircleStackIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline'

// Sample tenants for demo
const sampleTenants: Tenant[] = [
  { id: '1', name: 'Eliza', slug: 'eliza', isDefault: false },
  { id: '2', name: 'Eliza Platform', slug: 'platform', isDefault: true },
  { id: '3', name: 'Acme Corp', slug: 'acme', isDefault: false },
]

// Default theme colors (Eliza Forge palette)
const defaultTheme = {
  primary: '#c9506b',
  primaryLight: '#e8a598',
  accent: '#f5c4a1',
  text: '#5c4a5a',
}

// Preset brand themes for quick switching
const brandPresets = {
  'Eliza Forge': { primary: '#c9506b', primaryLight: '#e8a598', accent: '#f5c4a1', text: '#5c4a5a' },
  'Ocean Blue': { primary: '#0369a1', primaryLight: '#38bdf8', accent: '#06b6d4', text: '#334155' },
  'Forest Green': { primary: '#15803d', primaryLight: '#4ade80', accent: '#84cc16', text: '#374151' },
  'Royal Purple': { primary: '#7c3aed', primaryLight: '#a78bfa', accent: '#c084fc', text: '#374151' },
  'Sunset Orange': { primary: '#ea580c', primaryLight: '#fb923c', accent: '#facc15', text: '#431407' },
}

// Convert hex to RGB values for CSS variables
function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return '0 0 0'
  return `${parseInt(result[1], 16)} ${parseInt(result[2], 16)} ${parseInt(result[3], 16)}`
}

export default function ComponentShowcase() {
  const [switchOn, setSwitchOn] = useState(false)
  const [darkMode, setDarkMode] = useState(false)
  const [tenants, setTenants] = useState<Tenant[]>(sampleTenants)
  const [currentTenant, setCurrentTenant] = useState<Tenant>(sampleTenants[1])
  const [theme, setTheme] = useState(defaultTheme)
  // Modal states
  const [showBasicModal, setShowBasicModal] = useState(false)
  const [showFormModal, setShowFormModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  // Sheet states
  const [showRightSheet, setShowRightSheet] = useState(false)
  const [showLeftSheet, setShowLeftSheet] = useState(false)
  // Banner demo state
  const [showDismissibleBanner, setShowDismissibleBanner] = useState(true)
  // Chip states for feature allocation demo
  const [selectedFeatures, setSelectedFeatures] = useState<Set<string>>(
    new Set(['ai-documents', 'ai-chat', 'agent-config'])
  )
  const toggleFeature = (feature: string) => {
    setSelectedFeatures(prev => {
      const next = new Set(prev)
      if (next.has(feature)) {
        next.delete(feature)
      } else {
        next.add(feature)
      }
      return next
    })
  }

  // Toast hook for notifications demo
  const { toasts, success, error, warning, info } = useToast()

  // Date picker states
  const [selectedDate, setSelectedDate] = React.useState<Date | null>(null)
  const [dateRange, setDateRange] = React.useState<{ from: Date | null; to: Date | null }>({ from: null, to: null })

  // Prompt bar states
  const [promptAttachments, setPromptAttachments] = React.useState<Array<{ id: string; name: string; type: "file" | "image"; size?: number }>>([])
  const [selectedTools, setSelectedTools] = React.useState<string[]>(["search"])
  const [selectedDomain, setSelectedDomain] = React.useState<string | null>("insurance")

  const handleSetDefault = (tenant: Tenant) => {
    setTenants(prev => prev.map(t => ({
      ...t,
      isDefault: t.id === tenant.id
    })))
  }

  // Apply theme colors as CSS variables
  useEffect(() => {
    document.documentElement.style.setProperty('--color-primary', hexToRgb(theme.primary))
    document.documentElement.style.setProperty('--color-primary-light', hexToRgb(theme.primaryLight))
    document.documentElement.style.setProperty('--color-accent', hexToRgb(theme.accent))
    document.documentElement.style.setProperty('--color-text', hexToRgb(theme.text))
  }, [theme])

  // Apply dark mode class to the container
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    return () => {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  return (
    <div className={`fixed inset-0 overflow-y-auto transition-colors duration-300 ${darkMode ? 'bg-dark-bg' : 'bg-canvas'}`}>
      {/* Toast Container */}
      <ToastContainer toasts={toasts} position="top-right" />
      
      {/* Header */}
      <header className={`sticky top-0 z-50 backdrop-blur-md border-b transition-colors duration-300 ${
        darkMode 
          ? 'bg-dark-bg/90 border-dark-border/50' 
          : 'bg-white/80 border-gray-100'
      }`}>
        <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Logo area */}
            <div className="flex items-baseline">
              <span className="font-sans text-2xl font-bold text-charcoal dark:text-white tracking-tight">eliza</span>
              <span className="font-title text-2xl italic text-eliza-red ml-0.5">forge</span>
            </div>
            <span className={`${darkMode ? 'text-gray-600' : 'text-gray-300'}`}>/</span>
            <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Design System</span>
          </div>
          <div className="flex items-center gap-4">
            {/* Dark mode toggle */}
            <Button 
              variant="ghost" 
              size="icon-sm"
              onClick={() => setDarkMode(!darkMode)}
              className="relative"
            >
              {darkMode ? (
                <SunIcon className="h-5 w-5 text-yellow-500" />
              ) : (
                <MoonIcon className="h-5 w-5" />
              )}
            </Button>
            <Button variant="ghost" size="icon-sm">
              <BellIcon className="h-5 w-5" />
            </Button>
            <div className="w-8 h-8 rounded-full bg-eliza-red flex items-center justify-center text-white text-xs font-medium">
              EP
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-8 py-12">
        {/* Page Title */}
        <div className="mb-12">
          <h1 className={`font-title text-5xl mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
            Eliza Forge
          </h1>
          <p className={`font-subtitle text-lg max-w-2xl ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
            Design system & component library. Iterate on look and feel here before rolling out to the app.
          </p>
        </div>

        {/* Theme Customizer */}
        <section className="mb-16">
          <Card className="overflow-hidden">
            <div className="h-1 bg-gradient-to-r from-eliza-red via-eliza-red-light to-eliza-red-coral"></div>
            <CardHeader>
              <CardTitle className="font-sans text-lg flex items-center gap-2">
                <SparklesIcon className="h-5 w-5 text-eliza-red" />
                Theme Customizer
              </CardTitle>
              <CardDescription>Adjust brand colors - all components update automatically via CSS variables</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-8">
                {/* Color Pickers */}
                <div className="space-y-4">
                  <h4 className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Brand Colors</h4>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="primary">Primary</Label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          id="primary"
                          value={theme.primary}
                          onChange={(e) => setTheme(prev => ({ ...prev, primary: e.target.value }))}
                          className="w-10 h-10 rounded-lg border border-gray-200 dark:border-dark-border cursor-pointer"
                        />
                        <Input 
                          value={theme.primary} 
                          onChange={(e) => setTheme(prev => ({ ...prev, primary: e.target.value }))}
                          className="font-mono text-sm"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="primaryLight">Primary Light</Label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          id="primaryLight"
                          value={theme.primaryLight}
                          onChange={(e) => setTheme(prev => ({ ...prev, primaryLight: e.target.value }))}
                          className="w-10 h-10 rounded-lg border border-gray-200 dark:border-dark-border cursor-pointer"
                        />
                        <Input 
                          value={theme.primaryLight} 
                          onChange={(e) => setTheme(prev => ({ ...prev, primaryLight: e.target.value }))}
                          className="font-mono text-sm"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="accent">Accent (Coral)</Label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          id="accent"
                          value={theme.accent}
                          onChange={(e) => setTheme(prev => ({ ...prev, accent: e.target.value }))}
                          className="w-10 h-10 rounded-lg border border-gray-200 dark:border-dark-border cursor-pointer"
                        />
                        <Input 
                          value={theme.accent} 
                          onChange={(e) => setTheme(prev => ({ ...prev, accent: e.target.value }))}
                          className="font-mono text-sm"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="text">Text Color</Label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          id="text"
                          value={theme.text}
                          onChange={(e) => setTheme(prev => ({ ...prev, text: e.target.value }))}
                          className="w-10 h-10 rounded-lg border border-gray-200 dark:border-dark-border cursor-pointer"
                        />
                        <Input 
                          value={theme.text} 
                          onChange={(e) => setTheme(prev => ({ ...prev, text: e.target.value }))}
                          className="font-mono text-sm"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Presets */}
                <div className="space-y-4">
                  <h4 className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Brand Presets</h4>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(brandPresets).map(([name, colors]) => (
                      <button
                        key={name}
                        onClick={() => setTheme(colors)}
                        className={`
                          flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium
                          border transition-all
                          ${theme.primary === colors.primary 
                            ? 'border-eliza-red bg-eliza-red/10 text-eliza-red' 
                            : 'border-gray-200 dark:border-dark-border hover:border-gray-300 dark:hover:border-dark-border text-charcoal dark:text-gray-300'
                          }
                        `}
                      >
                        <div 
                          className="w-4 h-4 rounded-full" 
                          style={{ background: `linear-gradient(135deg, ${colors.primary}, ${colors.primaryLight})` }}
                        />
                        {name}
                      </button>
                    ))}
                  </div>
                  
                  <div className="pt-4">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setTheme(defaultTheme)}
                    >
                      Reset to Default
                    </Button>
                  </div>
                </div>
              </div>

              {/* Live Preview Bar */}
              <div className={`mt-6 p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                <div className="flex items-center gap-4 flex-wrap">
                  <span className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Live Preview:</span>
                  <Button variant="brand" size="sm">Primary Button</Button>
                  <Button variant="secondary" size="sm">Secondary</Button>
                  <Badge variant="brand">Brand Badge</Badge>
                  <span className="text-eliza-red font-medium">Accent Text</span>
                  <div className="h-6 w-24 rounded-full bg-gradient-to-r from-eliza-red via-eliza-red-light to-eliza-red-coral"></div>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Color Palette */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Color Palette</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Official Eliza Forge brand colors</p>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <div className="space-y-2">
              <div className="h-20 rounded-2xl bg-eliza-red"></div>
              <p className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Primary Red</p>
              <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>#b11e4c</p>
              <p className={`text-xs ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>Buttons, logo, main accent</p>
            </div>
            <div className="space-y-2">
              <div className="h-20 rounded-2xl bg-eliza-red-light"></div>
              <p className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Light Red</p>
              <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>#dd6c66</p>
              <p className={`text-xs ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>Hover states, secondary</p>
            </div>
            <div className="space-y-2">
              <div className="h-20 rounded-2xl bg-eliza-red-coral"></div>
              <p className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Coral</p>
              <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>#ed6545</p>
              <p className={`text-xs ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>Gradients, warm accents</p>
            </div>
            <div className="space-y-2">
              <div className="h-20 rounded-2xl bg-charcoal"></div>
              <p className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Charcoal</p>
              <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>#434343</p>
              <p className={`text-xs ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>Body text</p>
            </div>
            <div className="space-y-2">
              <div className="h-20 rounded-2xl bg-gradient-to-br from-eliza-red via-eliza-red-light to-eliza-red-coral"></div>
              <p className={`text-sm font-medium ${darkMode ? 'text-white' : 'text-charcoal'}`}>Brand Gradient</p>
              <p className={`text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>Primary → Coral</p>
              <p className={`text-xs ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>Hero sections, accents</p>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Typography */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Typography</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Brand fonts for titles, subtitles, and body text</p>
          <div className="grid md:grid-cols-2 gap-8">
            <Card>
              <CardHeader>
                <CardTitle>Title Font</CardTitle>
                <CardDescription>Libre Baskerville - for main headings</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <h1 className={`font-title text-5xl ${darkMode ? 'text-white' : 'text-charcoal'}`}>Good morning, Eliza.</h1>
                <h2 className={`font-title text-3xl ${darkMode ? 'text-white' : 'text-charcoal'}`}>Section Header</h2>
                <h3 className={`font-title text-2xl ${darkMode ? 'text-white' : 'text-charcoal'}`}>Card Title</h3>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="font-sans">Body & Subtitle Fonts</CardTitle>
                <CardDescription>Inter for body, Hedvig Letters Serif for subtitles</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className={`font-subtitle text-lg ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Subtitle text - Hedvig Letters Serif</p>
                <p className={`font-sans text-base ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>Body text - Inter 16px</p>
                <p className={`font-sans text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>Small text - Inter 14px</p>
                <p className={`font-sans text-xs ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>Micro text - Inter 12px</p>
                <p className={`font-mono text-sm ${darkMode ? 'text-gray-400' : 'text-gray-600'}`}>Monospace - JetBrains Mono</p>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Buttons */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Buttons</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>All button variants and sizes</p>
          
          <div className="space-y-8">
            {/* Primary Variants */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Button Variants</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4">
                  <Button variant="default">Get Started</Button>
                  <Button variant="brand">Primary Action</Button>
                  <Button variant="secondary">Secondary</Button>
                  <Button variant="outline">Outline</Button>
                  <Button variant="ghost">Ghost</Button>
                  <Button variant="destructive">Destructive</Button>
                  <Button variant="link">Link style →</Button>
                </div>
              </CardContent>
            </Card>

            {/* Sizes */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Button Sizes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-4">
                  <Button size="sm">Small</Button>
                  <Button size="default">Default</Button>
                  <Button size="lg">Large</Button>
                  <Button size="xl">Extra Large</Button>
                </div>
              </CardContent>
            </Card>

            {/* With Icons */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Buttons with Icons</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-4">
                  <Button variant="default">
                    <SparklesIcon className="h-4 w-4" />
                    Create job spec
                  </Button>
                  <Button variant="brand">
                    <UserGroupIcon className="h-4 w-4" />
                    Search talent pool
                  </Button>
                  <Button variant="secondary">
                    <ChartBarIcon className="h-4 w-4" />
                    Pipeline analytics
                  </Button>
                  <Button variant="brand" size="icon">
                    <ArrowUpIcon className="h-5 w-5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Form Elements */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Form Elements</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Inputs, textareas, and controls</p>
          
          <div className="grid md:grid-cols-2 gap-8">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Input Fields</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" placeholder="you@example.com" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="search">Search</Label>
                  <div className="relative">
                    <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input id="search" className="pl-10" placeholder="Search candidates..." />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="disabled">Disabled</Label>
                  <Input id="disabled" disabled placeholder="Disabled input" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Input Variants</CardTitle>
                <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Ghost variants for minimal, inline editing</p>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label className="text-xs text-gray-500">Default (bordered)</Label>
                  <Input placeholder="Standard input with border..." />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-gray-500">Ghost (minimal)</Label>
                  <Input variant="ghost" placeholder="Transparent, subtle border on hover/focus..." />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-gray-500">Ghost Large (for titles)</Label>
                  <Input variant="ghost-lg" placeholder="Untitled Document" />
                </div>
                <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                  <p className={`text-xs mb-3 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Example: Inline title editing</p>
                  <Input variant="ghost-lg" placeholder="Analysis name" defaultValue="Senior Engineer Search" />
                  <Input variant="ghost" placeholder="Add a short description..." className="mt-1" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Textarea & Switch</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="message">Message</Label>
                  <Textarea 
                    id="message" 
                    placeholder="Describe the workflow you need..."
                    rows={3}
                  />
                </div>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <Label>Enable notifications</Label>
                    <p className={`text-sm ${darkMode ? 'text-gray-500' : 'text-gray-500'}`}>Get notified when candidates match</p>
                  </div>
                  <Switch checked={switchOn} onCheckedChange={setSwitchOn} />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Slider Input</CardTitle>
                <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Combined slider and number input for numeric values</p>
              </CardHeader>
              <CardContent className="space-y-6">
                <SliderInput
                  label="Market Search Limit"
                  description="Max candidates to search from external talent market"
                  value={50}
                  onChange={() => {}}
                  min={0}
                  max={200}
                />
                <SliderInput
                  label="ATS Pipeline Limit"
                  description="Max candidates to fetch from your connected ATS"
                  value={100}
                  onChange={() => {}}
                  min={0}
                  max={500}
                />
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Badges */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Badges</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Status and category indicators</p>
          
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-wrap gap-3">
                <Badge variant="default">Default</Badge>
                <Badge variant="brand">Brand</Badge>
                <Badge variant="secondary">Secondary</Badge>
                <Badge variant="success">Success</Badge>
                <Badge variant="warning">Warning</Badge>
                <Badge variant="danger">Danger</Badge>
                <Badge variant="info">Info</Badge>
                <Badge variant="outline">Outline</Badge>
              </div>
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Cards */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>App Cards</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Cards for the home dashboard grid</p>
          
          <div className="grid md:grid-cols-3 gap-6">
            {/* App Card Style */}
            <Card className="group hover:shadow-card-hover hover:-translate-y-1 transition-all duration-200 cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex justify-between items-start mb-4">
                  <div className={`w-12 h-12 rounded-xl border flex items-center justify-center group-hover:scale-105 transition-transform ${
                    darkMode ? 'bg-dark-surface-2 border-gray-700' : 'bg-gray-50 border-gray-100'
                  }`}>
                    <UserGroupIcon className={`h-6 w-6 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`} />
                  </div>
                  <span className={`group-hover:text-eliza-red transition-colors ${darkMode ? 'text-gray-600' : 'text-gray-300'}`}>↗</span>
                </div>
                <h3 className={`font-medium mb-1 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Talent Search</h3>
                <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>AI candidate discovery across sources.</p>
              </CardContent>
            </Card>

            <Card className="group hover:shadow-card-hover hover:-translate-y-1 transition-all duration-200 cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex justify-between items-start mb-4">
                  <div className={`w-12 h-12 rounded-xl border flex items-center justify-center group-hover:scale-105 transition-transform ${
                    darkMode ? 'bg-dark-surface-2 border-gray-700' : 'bg-gray-50 border-gray-100'
                  }`}>
                    <EnvelopeIcon className={`h-6 w-6 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`} />
                  </div>
                  <span className={`group-hover:text-eliza-red transition-colors ${darkMode ? 'text-gray-600' : 'text-gray-300'}`}>↗</span>
                </div>
                <h3 className={`font-medium mb-1 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Outreach</h3>
                <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Personalized campaign management.</p>
              </CardContent>
            </Card>

            <Card className="group hover:shadow-card-hover hover:-translate-y-1 transition-all duration-200 cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex justify-between items-start mb-4">
                  <div className={`w-12 h-12 rounded-xl border flex items-center justify-center group-hover:scale-105 transition-transform ${
                    darkMode ? 'bg-dark-surface-2 border-gray-700' : 'bg-gray-50 border-gray-100'
                  }`}>
                    <CalendarIcon className={`h-6 w-6 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`} />
                  </div>
                  <span className={`group-hover:text-eliza-red transition-colors ${darkMode ? 'text-gray-600' : 'text-gray-300'}`}>↗</span>
                </div>
                <h3 className={`font-medium mb-1 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Scheduler</h3>
                <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Automate interviews and follow-ups.</p>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Card Variants */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Card Variants</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Different card styles for various use cases</p>

          {/* KPI / Metric Cards */}
          <div className="mb-8">
            <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>KPI & Metric Cards</h3>
            <div className="grid md:grid-cols-4 gap-4">
              <MetricCard
                title="Total Users"
                value="12,847"
                change={12.5}
                changeLabel="vs last month"
                trend="up"
              />
              <MetricCard
                title="Active Sessions"
                value="1,284"
                change={-3.2}
                changeLabel="vs last week"
                trend="down"
              />
              <MetricCard
                title="AI Queries"
                value="45.2K"
                change={28}
                changeLabel="vs last month"
                trend="up"
                variant="gradient"
              />
              <MetricCard
                title="Avg Response Time"
                value="1.2s"
                trend="neutral"
              />
            </div>
          </div>

          {/* Stat Cards */}
          <div className="mb-8">
            <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>Stat Cards</h3>
            <div className="grid md:grid-cols-5 gap-4">
              <StatCard label="Documents" value="1,234" color="default" />
              <StatCard label="Processed" value="1,180" subValue="95.6%" color="success" />
              <StatCard label="Pending" value="42" color="warning" />
              <StatCard label="Failed" value="12" color="danger" />
              <StatCard label="Queued" value="0" color="info" />
            </div>
          </div>

          {/* Progress Cards */}
          <div className="mb-8">
            <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>Progress / Adoption Cards</h3>
            <div className="grid md:grid-cols-3 gap-4">
              <ProgressCard
                title="Onboarding Complete"
                current={78}
                target={100}
                unit="%"
                color="success"
              />
              <ProgressCard
                title="Storage Used"
                current={45}
                target={100}
                unit=" GB"
                color="default"
              />
              <ProgressCard
                title="API Calls This Month"
                current={8420}
                target={10000}
                color="warning"
              />
            </div>
          </div>

          {/* Image Cards */}
          <div className="mb-8">
            <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>Image Cards</h3>
            <div className="grid md:grid-cols-3 gap-6">
              <ImageCard
                image="https://images.unsplash.com/photo-1551434678-e076c223a692?w=600&h=400&fit=crop"
                title="Team Collaboration"
                description="Enhance your team's productivity with AI-powered insights."
                badge="New"
              />
              <ImageCard
                image="https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&h=400&fit=crop"
                title="Analytics Dashboard"
                description="Real-time metrics and visualizations."
                overlay
              />
              <ImageCard
                image="https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?w=600&h=400&fit=crop"
                title="Data Processing"
                description="Automated document analysis and extraction."
              />
            </div>
          </div>

          {/* Content Cards */}
          <div className="mb-8">
            <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>Content Cards</h3>
            <div className="grid md:grid-cols-2 gap-6">
              <ContentCard
                title="Getting Started with Eliza Forge"
                excerpt="Learn how to set up your first AI-powered workflow in just a few minutes. This guide covers the basics of connecting data sources and creating queries."
                author={{ name: "Alex Chen" }}
                date="Dec 15, 2025"
                readTime="5 min read"
                tags={["Tutorial", "Getting Started"]}
              />
              <ContentCard
                title="Best Practices for Document Processing"
                excerpt="Optimize your document ingestion pipeline with these proven strategies for handling large volumes of files efficiently."
                author={{ name: "Sarah Miller" }}
                date="Dec 10, 2025"
                readTime="8 min read"
                tags={["Best Practices"]}
              />
            </div>
          </div>

          {/* Link Cards */}
          <div>
            <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>Link / Navigation Cards</h3>
            <div className="grid md:grid-cols-4 gap-4">
              <LinkCard
                title="Documentation"
                description="Explore guides and API reference"
                icon={<DocumentTextIcon className="w-6 h-6" />}
                external
              />
              <LinkCard
                title="Integrations"
                description="Connect your favorite tools"
                icon={<Cog6ToothIcon className="w-6 h-6" />}
              />
              <LinkCard
                title="Templates"
                description="Pre-built workflows to get started"
                icon={<SparklesIcon className="w-6 h-6" />}
              />
              <LinkCard
                title="Support"
                description="Get help from our team"
                icon={<ChatBubbleLeftRightIcon className="w-6 h-6" />}
                external
              />
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Panels */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Panels</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
            Flat containers without shadow for admin interfaces and data tables
          </p>

          <div className="space-y-8">
            {/* Basic Panel */}
            <div>
              <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>
                Basic Panel with Header
              </h3>
              <Panel>
                <PanelHeader>
                  <PanelTitle>Active Grants</PanelTitle>
                  <PanelDescription>2 grants configured</PanelDescription>
                </PanelHeader>
                <PanelBody>
                  <p className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                    Panel content goes here. Use for data tables, lists, and functional UI containers.
                  </p>
                </PanelBody>
              </Panel>
            </div>

            {/* Panel with Footer */}
            <div>
              <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>
                Panel with Footer
              </h3>
              <Panel>
                <PanelHeader>
                  <PanelTitle>Configuration</PanelTitle>
                  <PanelDescription>Manage your settings</PanelDescription>
                </PanelHeader>
                <PanelBody>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Enable notifications</span>
                      <Switch />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Auto-sync data</span>
                      <Switch defaultChecked />
                    </div>
                  </div>
                </PanelBody>
                <PanelFooter>
                  <div className="flex justify-end gap-3">
                    <Button variant="outline">Cancel</Button>
                    <Button>Save Changes</Button>
                  </div>
                </PanelFooter>
              </Panel>
            </div>

            {/* Panel vs Card Comparison */}
            <div>
              <h3 className={`font-sans text-lg font-semibold mb-4 ${darkMode ? 'text-gray-200' : 'text-charcoal'}`}>
                Panel vs Card Comparison
              </h3>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Panel (flat, no shadow)</p>
                  <Panel>
                    <PanelHeader>
                      <PanelTitle>Panel Example</PanelTitle>
                    </PanelHeader>
                    <PanelBody>
                      <p className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                        Use for admin interfaces, settings pages, data tables, and functional containers.
                      </p>
                    </PanelBody>
                  </Panel>
                </div>
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Card (elevated, with shadow)</p>
                  <Card>
                    <CardHeader>
                      <CardTitle className="font-sans text-lg">Card Example</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                        Use for featured content, hero sections, and elements that need visual emphasis.
                      </p>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Date Pickers */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Date Pickers</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Calendar-based date selection for dashboards</p>

          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Single Date Picker</CardTitle>
                <CardDescription>Select a single date</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="max-w-xs">
                  <Label className="mb-1.5 block">Select date</Label>
                  <DatePicker
                    value={selectedDate}
                    onChange={setSelectedDate}
                    placeholder="Choose a date"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Date Range Picker</CardTitle>
                <CardDescription>Select a date range with presets</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="max-w-sm">
                  <Label className="mb-1.5 block">Select date range</Label>
                  <DateRangePicker
                    value={dateRange}
                    onChange={setDateRange}
                    placeholder="Choose date range"
                    presets={[
                      { label: "Today", range: { from: new Date(), to: new Date() } },
                      { label: "Last 7 days", range: { from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), to: new Date() } },
                      { label: "Last 30 days", range: { from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), to: new Date() } },
                      { label: "This month", range: { from: new Date(new Date().getFullYear(), new Date().getMonth(), 1), to: new Date() } },
                    ]}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Prompt Bar Variants */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Prompt Bar Variants</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>AI input components with different capabilities</p>

          <div className="space-y-8">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Basic Prompt Bar</CardTitle>
                <CardDescription>Simple text input with send button</CardDescription>
              </CardHeader>
              <CardContent>
                <PromptBar
                  placeholder="Ask anything..."
                  onSubmit={(value) => console.log("Submitted:", value)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">With File Attachments</CardTitle>
                <CardDescription>Attach files and images to your prompt</CardDescription>
              </CardHeader>
              <CardContent>
                <PromptBarWithAttachments
                  placeholder="Ask about your files..."
                  attachments={promptAttachments}
                  onAttachmentsChange={setPromptAttachments}
                  onSubmit={(value) => console.log("Submitted:", value)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Full Featured (Files + Tools)</CardTitle>
                <CardDescription>File attachments and AI tools in one prompt bar</CardDescription>
              </CardHeader>
              <CardContent>
                <PromptBarWithTools
                  placeholder="Ask anything..."
                  tools={[
                    { id: "search", name: "Web Search", icon: <MagnifyingGlassIcon className="w-4 h-4" />, description: "Search the web for information" },
                    { id: "code", name: "Code Interpreter", icon: <CodeBracketIcon className="w-4 h-4" />, description: "Execute and analyze code" },
                    { id: "docs", name: "Document Analysis", icon: <DocumentTextIcon className="w-4 h-4" />, description: "Analyze uploaded documents" },
                    { id: "data", name: "Data Analysis", icon: <ChartBarIcon className="w-4 h-4" />, description: "Analyze and visualize data" },
                  ]}
                  selectedTools={selectedTools}
                  onToolsChange={setSelectedTools}
                  attachments={promptAttachments}
                  onAttachmentsChange={setPromptAttachments}
                  showVoice
                  onVoiceClick={() => console.log("Voice clicked")}
                  onSubmit={(value) => console.log("Submitted:", value)}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">With Data Domain Selector</CardTitle>
                <CardDescription>Select a data domain before querying - ideal for BI chat interfaces</CardDescription>
              </CardHeader>
              <CardContent>
                <PromptBarWithDomain
                  placeholder="Ask a question about your data..."
                  domains={[
                    { id: "insurance", name: "Insurance Analytics", description: "Policy, claims, and customer data", icon: <ChartBarIcon className="w-4 h-4" /> },
                    { id: "finance", name: "Finance Analytics", description: "Revenue, expenses, and forecasts", icon: <CircleStackIcon className="w-4 h-4" /> },
                    { id: "hr", name: "HR Analytics", description: "Employee and workforce data", icon: <UsersIcon className="w-4 h-4" /> },
                  ]}
                  selectedDomain={selectedDomain}
                  onDomainChange={setSelectedDomain}
                  attachments={promptAttachments}
                  onAttachmentsChange={setPromptAttachments}
                  onSubmit={(value) => console.log("Submitted to domain:", selectedDomain, value)}
                />
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Tenant Switcher */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Tenant Switcher</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Multi-tenant organization selector with elizaforge branding</p>
          
          <div className="space-y-8">
            {/* Full Tenant Switcher */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Header Tenant Switcher</CardTitle>
                <CardDescription>Text logo with "for [Organization]" pattern</CardDescription>
              </CardHeader>
              <CardContent>
                <TenantSwitcher
                  tenants={tenants}
                  currentTenant={currentTenant}
                  onTenantChange={setCurrentTenant}
                  onSetDefault={handleSetDefault}
                />
              </CardContent>
            </Card>

            {/* Compact Variant */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Compact Tenant Switcher</CardTitle>
                <CardDescription>For sidebar headers or space-constrained areas</CardDescription>
              </CardHeader>
              <CardContent>
                <TenantSwitcherCompact
                  tenants={tenants}
                  currentTenant={currentTenant}
                  onTenantChange={setCurrentTenant}
                />
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Toolbar */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Toolbar</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Top application bar with tenant switcher as first element and actions on the right</p>

          <div className="space-y-8">
            {/* Full Toolbar */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Header Toolbar</CardTitle>
                <CardDescription>Tenant switcher is the first element, actions on the right</CardDescription>
              </CardHeader>
              <CardContent className="p-0 overflow-hidden rounded-b-xl">
                <Toolbar
                  leftContent={
                    <TenantSwitcher
                      tenants={tenants}
                      currentTenant={currentTenant}
                      onTenantChange={setCurrentTenant}
                      onSetDefault={handleSetDefault}
                    />
                  }
                  rightContent={
                    <ToolbarSection>
                      <ToolbarItem 
                        icon={darkMode ? <SunIcon className="h-5 w-5" /> : <MoonIcon className="h-5 w-5" />}
                        tooltip={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                        onClick={() => setDarkMode(!darkMode)}
                      />
                      <ToolbarItem 
                        icon={<BellIcon className="h-5 w-5" />} 
                        badge={3} 
                        tooltip="Notifications"
                        onClick={() => info('Notification clicked')}
                      />
                      <ToolbarDivider />
                      <ToolbarTextButton 
                        icon={<ChatBubbleLeftRightIcon className="h-4 w-4" />}
                        onClick={() => info('Help clicked')}
                      >
                        Help / Feedback
                      </ToolbarTextButton>
                      <div 
                        className="flex items-center gap-1 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors cursor-pointer"
                        onClick={() => info('User menu clicked')}
                      >
                        <Avatar
                          size="sm"
                          name="Sarah Chen"
                          className="ring-2 ring-white dark:ring-dark-surface"
                        />
                        <ChevronDownIcon className="h-3 w-3 text-gray-500 dark:text-gray-400" />
                      </div>
                    </ToolbarSection>
                  }
                />
              </CardContent>
            </Card>

            {/* Toolbar Components */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Toolbar Components</CardTitle>
                <CardDescription>Individual toolbar building blocks</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-dark-surface-2 rounded-lg">
                  <ToolbarItem icon={<BellIcon className="h-5 w-5" />} badge={5} />
                  <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">ToolbarItem with badge</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-dark-surface-2 rounded-lg">
                  <ToolbarTextButton icon={<Cog6ToothIcon className="h-4 w-4" />}>
                    Settings
                  </ToolbarTextButton>
                  <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">ToolbarTextButton</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-dark-surface-2 rounded-lg">
                  <ToolbarDivider />
                  <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">ToolbarDivider</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Chips */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Chips</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Toggleable pills for feature allocation, filters, and tags</p>
          
          <div className="space-y-6">
            {/* Feature Allocation Example */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Feature Allocation</CardTitle>
                <CardDescription>Select the features this tenant should have access to</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <ChipGroup label="Assistant">
                  <Chip 
                    selected={selectedFeatures.has('ai-documents')} 
                    onToggle={() => toggleFeature('ai-documents')}
                  >
                    AI Assistant - Documents
                  </Chip>
                  <Chip 
                    selected={selectedFeatures.has('ai-chat')} 
                    onToggle={() => toggleFeature('ai-chat')}
                  >
                    AI Assistant - Chat
                  </Chip>
                  <Chip 
                    selected={selectedFeatures.has('question-log')} 
                    onToggle={() => toggleFeature('question-log')}
                  >
                    AI Assistant - Question Log
                  </Chip>
                </ChipGroup>

                <ChipGroup label="Administration">
                  <Chip 
                    selected={selectedFeatures.has('data-connections')} 
                    onToggle={() => toggleFeature('data-connections')}
                  >
                    Data Connections
                  </Chip>
                  <Chip 
                    selected={selectedFeatures.has('users-roles')} 
                    onToggle={() => toggleFeature('users-roles')}
                  >
                    Users & Roles
                  </Chip>
                  <Chip 
                    selected={selectedFeatures.has('admin-settings')} 
                    onToggle={() => toggleFeature('admin-settings')}
                  >
                    Admin Settings
                  </Chip>
                  <Chip 
                    selected={selectedFeatures.has('audit-logging')} 
                    onToggle={() => toggleFeature('audit-logging')}
                  >
                    Audit & Logging
                  </Chip>
                </ChipGroup>

                <ChipGroup label="Labs">
                  <Chip 
                    selected={selectedFeatures.has('agent-config')} 
                    onToggle={() => toggleFeature('agent-config')}
                  >
                    Labs - Agent Configuration
                  </Chip>
                  <Chip 
                    selected={selectedFeatures.has('resume-parsing')} 
                    onToggle={() => toggleFeature('resume-parsing')}
                  >
                    Labs - Resume Parsing
                  </Chip>
                </ChipGroup>

                <div className={`pt-4 border-t ${darkMode ? 'border-dark-border/30' : 'border-gray-200'}`}>
                  <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                    {selectedFeatures.size} features selected
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Variant Examples */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Chip Variants</CardTitle>
                <CardDescription>Different visual styles for chips</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Default</p>
                  <div className="flex flex-wrap gap-2">
                    <Chip variant="default" selected={false}>Unselected</Chip>
                    <Chip variant="default" selected={true}>Selected</Chip>
                  </div>
                </div>
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Outline</p>
                  <div className="flex flex-wrap gap-2">
                    <Chip variant="outline" selected={false}>Unselected</Chip>
                    <Chip variant="outline" selected={true}>Selected</Chip>
                  </div>
                </div>
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Ghost</p>
                  <div className="flex flex-wrap gap-2">
                    <Chip variant="ghost" selected={false}>Unselected</Chip>
                    <Chip variant="ghost" selected={true}>Selected</Chip>
                  </div>
                </div>
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Without Icons</p>
                  <div className="flex flex-wrap gap-2">
                    <Chip showIcon={false} selected={false}>No Icon</Chip>
                    <Chip showIcon={false} selected={true}>Selected</Chip>
                  </div>
                </div>
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Icon on Right</p>
                  <div className="flex flex-wrap gap-2">
                    <Chip iconPosition="right" selected={false}>Right Icon</Chip>
                    <Chip iconPosition="right" selected={true}>Selected</Chip>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Modals */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Modals</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Dialog overlays for focused interactions</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Modal Examples</CardTitle>
              <CardDescription>Click a button to open different modal types</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => setShowBasicModal(true)}>
                  Basic Modal
                </Button>
                <Button variant="secondary" onClick={() => setShowFormModal(true)}>
                  Form Modal
                </Button>
                <Button variant="destructive" onClick={() => setShowDeleteModal(true)}>
                  Delete Confirmation
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Basic Modal */}
          <Modal open={showBasicModal} onClose={() => setShowBasicModal(false)}>
            <ModalContent size="md">
              <ModalHeader>
                <ModalTitle>Welcome to Eliza Forge</ModalTitle>
                <ModalDescription>This is a basic modal with title and description.</ModalDescription>
              </ModalHeader>
              <ModalBody>
                <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>
                  Modals are great for focused interactions that require the user's attention. 
                  They block the rest of the page and can be dismissed by clicking the backdrop, 
                  pressing Escape, or clicking the close button.
                </p>
              </ModalBody>
              <ModalFooter>
                <Button variant="secondary" onClick={() => setShowBasicModal(false)}>
                  Close
                </Button>
                <Button variant="brand" onClick={() => setShowBasicModal(false)}>
                  Got it
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>

          {/* Form Modal */}
          <Modal open={showFormModal} onClose={() => setShowFormModal(false)}>
            <ModalContent size="lg">
              <ModalHeader>
                <ModalTitle>Create New Project</ModalTitle>
                <ModalDescription>Fill in the details to create a new project.</ModalDescription>
              </ModalHeader>
              <ModalBody>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="project-name">Project Name</Label>
                    <Input id="project-name" placeholder="Enter project name" className="mt-1.5" />
                  </div>
                  <div>
                    <Label htmlFor="project-desc">Description</Label>
                    <Textarea id="project-desc" placeholder="Describe your project..." className="mt-1.5" rows={3} />
                  </div>
                  <div className="flex items-center gap-3">
                    <Switch id="project-public" />
                    <Label htmlFor="project-public">Make project public</Label>
                  </div>
                </div>
              </ModalBody>
              <ModalFooter>
                <Button variant="secondary" onClick={() => setShowFormModal(false)}>
                  Cancel
                </Button>
                <Button variant="brand" onClick={() => setShowFormModal(false)}>
                  Create Project
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>

          {/* Delete Confirmation Modal */}
          <Modal open={showDeleteModal} onClose={() => setShowDeleteModal(false)}>
            <ModalContent size="sm">
              <ModalHeader>
                <ModalTitle>Delete Item?</ModalTitle>
              </ModalHeader>
              <ModalBody>
                <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>
                  Are you sure you want to delete this item? This action cannot be undone.
                </p>
              </ModalBody>
              <ModalFooter>
                <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>
                  Cancel
                </Button>
                <Button variant="destructive" onClick={() => setShowDeleteModal(false)}>
                  Delete
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>
        </section>

        <Separator className="my-12" />

        {/* Modal Floating Actions */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Modal Floating Actions</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Floating action buttons with gradient backdrop for workspace-style modals</p>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Static Preview */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Floating Actions Preview</CardTitle>
                <CardDescription>Actions float at bottom with subtle gradient fade</CardDescription>
              </CardHeader>
              <CardContent>
                <div className={`relative h-64 rounded-xl border overflow-hidden ${darkMode ? 'bg-dark-surface border-dark-border' : 'bg-white border-gray-200'}`}>
                  {/* Mock content */}
                  <div className="p-4 space-y-3">
                    <div className={`h-4 w-3/4 rounded ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-100'}`} />
                    <div className={`h-4 w-1/2 rounded ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-100'}`} />
                    <div className={`h-4 w-2/3 rounded ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-100'}`} />
                    <div className={`h-4 w-1/2 rounded ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-100'}`} />
                    <div className={`h-4 w-3/4 rounded ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-100'}`} />
                  </div>
                  
                  {/* Floating Actions */}
                  <ModalFloatingActions>
                    <Button variant="outline" size="sm">Save Draft</Button>
                    <Button size="sm">Publish</Button>
                  </ModalFloatingActions>
                </div>
              </CardContent>
            </Card>

            {/* Positions */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Position Variants</CardTitle>
                <CardDescription>bottom-right (default), bottom-center, bottom-left</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Bottom Right */}
                <div className={`relative h-24 rounded-xl border overflow-hidden ${darkMode ? 'bg-dark-surface border-dark-border' : 'bg-white border-gray-200'}`}>
                  <div className="absolute top-2 left-3 text-xs text-gray-400">bottom-right (default)</div>
                  <ModalFloatingActions position="bottom-right" gradientHeight="sm">
                    <Button size="sm" variant="outline">Cancel</Button>
                    <Button size="sm">Save</Button>
                  </ModalFloatingActions>
                </div>
                
                {/* Bottom Center */}
                <div className={`relative h-24 rounded-xl border overflow-hidden ${darkMode ? 'bg-dark-surface border-dark-border' : 'bg-white border-gray-200'}`}>
                  <div className="absolute top-2 left-3 text-xs text-gray-400">bottom-center</div>
                  <ModalFloatingActions position="bottom-center" gradientHeight="sm">
                    <Button size="sm" variant="outline">Back</Button>
                    <Button size="sm">Continue</Button>
                  </ModalFloatingActions>
                </div>
                
                {/* Bottom Left */}
                <div className={`relative h-24 rounded-xl border overflow-hidden ${darkMode ? 'bg-dark-surface border-dark-border' : 'bg-white border-gray-200'}`}>
                  <div className="absolute top-2 left-3 text-xs text-gray-400">bottom-left</div>
                  <ModalFloatingActions position="bottom-left" gradientHeight="sm">
                    <Button size="sm">Previous</Button>
                    <Button size="sm">Next</Button>
                  </ModalFloatingActions>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Sheets */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Sheets</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Slide-in panels from the edge of the screen</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Sheet Examples</CardTitle>
              <CardDescription>Click a button to open sheets from different sides</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => setShowRightSheet(true)}>
                  Right Sheet
                </Button>
                <Button variant="secondary" onClick={() => setShowLeftSheet(true)}>
                  Left Sheet
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Right Sheet */}
          <Sheet open={showRightSheet} onClose={() => setShowRightSheet(false)}>
            <SheetContent side="right" size="md">
              <SheetHeader>
                <SheetTitle>Right Sheet</SheetTitle>
                <SheetDescription>This sheet slides in from the right side.</SheetDescription>
              </SheetHeader>
              <SheetBody>
                <div className="space-y-4">
                  <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>
                    Sheets are great for secondary content, forms, or detail views that don't require a full page. 
                    They slide in from the edge of the screen and can be dismissed by clicking the backdrop, 
                    pressing Escape, or clicking the close button.
                  </p>
                  <div className="space-y-2">
                    <Label>Example Input</Label>
                    <Input placeholder="Type something..." />
                  </div>
                  <div className="space-y-2">
                    <Label>Example Textarea</Label>
                    <Textarea placeholder="Enter details..." rows={3} />
                  </div>
                </div>
              </SheetBody>
              <SheetFooter>
                <div className="flex gap-3 w-full justify-end">
                  <Button variant="secondary" onClick={() => setShowRightSheet(false)}>
                    Cancel
                  </Button>
                  <Button variant="brand" onClick={() => setShowRightSheet(false)}>
                    Save
                  </Button>
                </div>
              </SheetFooter>
            </SheetContent>
          </Sheet>

          {/* Left Sheet */}
          <Sheet open={showLeftSheet} onClose={() => setShowLeftSheet(false)}>
            <SheetContent side="left" size="sm">
              <SheetHeader>
                <SheetTitle>Left Sheet</SheetTitle>
                <SheetDescription>Smaller sheet from the left side.</SheetDescription>
              </SheetHeader>
              <SheetBody>
                <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>
                  This is a smaller sheet that slides in from the left. 
                  Useful for navigation panels or quick actions.
                </p>
                <div className="mt-4 space-y-2">
                  <Button variant="ghost" className="w-full justify-start">Option 1</Button>
                  <Button variant="ghost" className="w-full justify-start">Option 2</Button>
                  <Button variant="ghost" className="w-full justify-start">Option 3</Button>
                </div>
              </SheetBody>
            </SheetContent>
          </Sheet>
        </section>

        <Separator className="my-12" />

        {/* Tabs */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Tabs</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Tab switcher with three style variants</p>
          
          <div className="space-y-8">
            {/* Default Tabs */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Default Tabs</CardTitle>
                <CardDescription>Contained style with background</CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="overview">
                  <TabsList variant="default">
                    <TabsTrigger value="overview" variant="default">Overview</TabsTrigger>
                    <TabsTrigger value="analytics" variant="default">Analytics</TabsTrigger>
                    <TabsTrigger value="reports" variant="default">Reports</TabsTrigger>
                    <TabsTrigger value="settings" variant="default">Settings</TabsTrigger>
                  </TabsList>
                  <TabsContent value="overview">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Overview content goes here. This is the default tab.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="analytics">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Analytics dashboard with charts and metrics.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="reports">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Generated reports and exports.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="settings">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Configuration and preferences.</p>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* Pills Tabs */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Pills Tabs</CardTitle>
                <CardDescription>Pill-shaped buttons with border</CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="all">
                  <TabsList variant="pills">
                    <TabsTrigger value="all" variant="pills">All</TabsTrigger>
                    <TabsTrigger value="active" variant="pills">Active</TabsTrigger>
                    <TabsTrigger value="completed" variant="pills">Completed</TabsTrigger>
                    <TabsTrigger value="archived" variant="pills">Archived</TabsTrigger>
                  </TabsList>
                  <TabsContent value="all">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Showing all items.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="active">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Showing active items only.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="completed">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Showing completed items.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="archived">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Showing archived items.</p>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* Underline Tabs */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Underline Tabs</CardTitle>
                <CardDescription>Classic underline style</CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="profile">
                  <TabsList variant="underline">
                    <TabsTrigger value="profile" variant="underline">Profile</TabsTrigger>
                    <TabsTrigger value="account" variant="underline">Account</TabsTrigger>
                    <TabsTrigger value="security" variant="underline">Security</TabsTrigger>
                    <TabsTrigger value="notifications" variant="underline">Notifications</TabsTrigger>
                  </TabsList>
                  <TabsContent value="profile">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Edit your profile information.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="account">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Manage your account settings.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="security">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Password and 2FA settings.</p>
                    </div>
                  </TabsContent>
                  <TabsContent value="notifications">
                    <div className={`p-4 rounded-xl ${darkMode ? 'bg-dark-surface-2' : 'bg-gray-50'}`}>
                      <p className={darkMode ? 'text-gray-300' : 'text-gray-600'}>Email and push notification preferences.</p>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Avatars */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Avatars</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>User profile pictures with initials fallback</p>
          
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Avatar Sizes</CardTitle>
                <CardDescription>From xs to 2xl</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-4">
                  <Avatar size="xs" name="Alice Brown" />
                  <Avatar size="sm" name="Bob Smith" />
                  <Avatar size="md" name="Carol Davis" />
                  <Avatar size="lg" name="David Wilson" />
                  <Avatar size="xl" name="Eve Johnson" />
                  <Avatar size="2xl" name="Frank Miller" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Avatar with Image</CardTitle>
                <CardDescription>Falls back to initials if image fails</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <Avatar 
                    size="lg" 
                    src="https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face" 
                    name="John Doe"
                  />
                  <Avatar 
                    size="lg" 
                    src="https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face" 
                    name="Jane Smith"
                  />
                  <Avatar size="lg" src="/broken-image.jpg" name="Fallback Test" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Avatar Group</CardTitle>
                <CardDescription>Stacked avatars with overflow indicator</CardDescription>
              </CardHeader>
              <CardContent>
                <AvatarGroup max={4} size="md">
                  <Avatar name="Alice Brown" />
                  <Avatar name="Bob Smith" />
                  <Avatar name="Carol Davis" />
                  <Avatar name="David Wilson" />
                  <Avatar name="Eve Johnson" />
                  <Avatar name="Frank Miller" />
                </AvatarGroup>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Tooltips */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Tooltips</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Hover hints for additional information</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Tooltip Positions</CardTitle>
              <CardDescription>Hover over the buttons to see tooltips</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-center gap-4">
                <Tooltip content="Tooltip on top" position="top">
                  <Button variant="secondary">Top</Button>
                </Tooltip>
                <Tooltip content="Tooltip on bottom" position="bottom">
                  <Button variant="secondary">Bottom</Button>
                </Tooltip>
                <Tooltip content="Tooltip on left" position="left">
                  <Button variant="secondary">Left</Button>
                </Tooltip>
                <Tooltip content="Tooltip on right" position="right">
                  <Button variant="secondary">Right</Button>
                </Tooltip>
              </div>
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Checkboxes */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Checkboxes</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Form checkboxes for multi-select options</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Checkbox States</CardTitle>
              <CardDescription>Different checkbox configurations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Checkbox label="Unchecked checkbox" />
              <Checkbox label="Checked checkbox" defaultChecked />
              <Checkbox 
                label="With description" 
                description="This checkbox has a helpful description below the label"
              />
              <Checkbox indeterminate label="Indeterminate state" />
              <Checkbox label="Disabled checkbox" disabled />
              <Checkbox label="Disabled checked" disabled defaultChecked />
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Spinners */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Spinners</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Loading indicators for async operations</p>
          
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Spinner Sizes & Variants</CardTitle>
                <CardDescription>Different sizes and color variants</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <Spinner size="xs" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>xs</p>
                  </div>
                  <div className="text-center">
                    <Spinner size="sm" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>sm</p>
                  </div>
                  <div className="text-center">
                    <Spinner size="md" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>md</p>
                  </div>
                  <div className="text-center">
                    <Spinner size="lg" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>lg</p>
                  </div>
                  <div className="text-center">
                    <Spinner size="xl" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>xl</p>
                  </div>
                </div>
                <div className="flex items-center gap-6 mt-6">
                  <div className="text-center">
                    <Spinner variant="default" size="lg" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>default</p>
                  </div>
                  <div className="text-center">
                    <Spinner variant="primary" size="lg" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>primary</p>
                  </div>
                  <div className="p-3 bg-charcoal rounded-lg text-center">
                    <Spinner variant="white" size="lg" />
                    <p className="text-xs mt-2 text-gray-300">white</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Loading Overlay</CardTitle>
                <CardDescription>Full container loading state</CardDescription>
              </CardHeader>
              <CardContent>
                <div className={`relative h-32 rounded-xl border ${darkMode ? 'border-dark-border/30' : 'border-gray-200'}`}>
                  <LoadingOverlay message="Loading content..." />
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Alerts */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Alerts</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Inline banners for contextual feedback</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Alert Variants</CardTitle>
              <CardDescription>Info, success, warning, error, and neutral</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert variant="info" title="Information">
                This is an informational message to help guide the user.
              </Alert>
              <Alert variant="success" title="Success">
                Your changes have been saved successfully.
              </Alert>
              <Alert variant="warning" title="Warning">
                Please review this information before proceeding.
              </Alert>
              <Alert variant="error" title="Error">
                Something went wrong. Please try again later.
              </Alert>
              <Alert variant="neutral">
                A neutral message without a title for simple notices.
              </Alert>
              <Alert variant="info" title="Dismissible Alert" onDismiss={() => {}}>
                This alert can be dismissed by clicking the X button.
              </Alert>
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Error States */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Error States</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Error display components for various scenarios</p>
          
          <div className="space-y-8">
            {/* ErrorDisplay Variants */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">ErrorDisplay Variants</CardTitle>
                <CardDescription>Inline, card, and page error displays</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Inline Variant (uses Alert)</p>
                  <ErrorDisplay
                    variant="inline"
                    title="Validation Error"
                    message="Please check your input and try again."
                    details="Field 'email' is required. Field 'password' must be at least 8 characters."
                    onRetry={() => alert('Retry clicked')}
                  />
                </div>
                <Separator />
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Card Variant</p>
                  <div className="max-w-md">
                    <ErrorDisplay
                      variant="card"
                      title="Failed to Load"
                      message="We couldn't load the requested data."
                      onRetry={() => alert('Retry clicked')}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Convenience Components */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Error Presets</CardTitle>
                <CardDescription>Pre-built error components for common scenarios</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>NetworkError</p>
                    <NetworkError onRetry={() => alert('Retry')} />
                  </div>
                  <div>
                    <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>ServerError</p>
                    <ServerError onRetry={() => alert('Retry')} />
                  </div>
                  <div>
                    <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>AuthError</p>
                    <AuthError onRetry={() => alert('Sign In')} />
                  </div>
                  <div>
                    <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>NotFoundError (page variant)</p>
                    <div className="border border-gray-200 dark:border-dark-border rounded-lg overflow-hidden">
                      <NotFoundError onRetry={() => alert('Go Back')} />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* ErrorBoundary */}
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">ErrorBoundary</CardTitle>
                <CardDescription>React error boundary for catching component errors</CardDescription>
              </CardHeader>
              <CardContent>
                <Alert variant="info" title="Usage">
                  <code className="text-xs font-mono">
                    {`<ErrorBoundary onReset={() => refetch()}>
  <MyComponent />
</ErrorBoundary>`}
                  </code>
                </Alert>
                <p className={`mt-4 text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  The ErrorBoundary catches JavaScript errors in child components and displays a fallback UI with a "Try Again" button.
                </p>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Skeletons */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Skeletons</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Loading placeholders for content</p>
          
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Skeleton Variants</CardTitle>
                <CardDescription>Different shapes for various content types</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Text</p>
                  <div className="space-y-2">
                    <Skeleton variant="text" width="100%" />
                    <Skeleton variant="text" width="80%" />
                    <Skeleton variant="text" width="60%" />
                  </div>
                </div>
                <div>
                  <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Shapes</p>
                  <div className="flex items-center gap-4">
                    <Skeleton variant="circular" width={48} height={48} />
                    <Skeleton variant="rectangular" width={100} height={48} />
                    <Skeleton variant="rounded" width={100} height={48} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Skeleton Presets</CardTitle>
                <CardDescription>Pre-built loading patterns</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Avatar + Text</p>
                    <div className="flex items-center gap-3">
                      <SkeletonAvatar size="md" />
                      <div className="flex-1">
                        <SkeletonText lines={2} lastLineWidth="50%" />
                      </div>
                    </div>
                  </div>
                  <div>
                    <p className={`text-sm font-medium mb-3 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>Card Skeleton</p>
                    <SkeletonCard />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Select */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Select</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Form dropdowns for selecting options</p>
          
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Basic Select</CardTitle>
                <CardDescription>Simple dropdown selection</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="mb-1.5 block">Choose a fruit</Label>
                  <Select placeholder="Select a fruit" defaultValue="apple">
                    <SelectOption value="apple">Apple</SelectOption>
                    <SelectOption value="banana">Banana</SelectOption>
                    <SelectOption value="orange">Orange</SelectOption>
                    <SelectOption value="grape">Grape</SelectOption>
                    <SelectOption value="mango">Mango</SelectOption>
                  </Select>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Grouped Select</CardTitle>
                <CardDescription>Options organized in groups</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="mb-1.5 block">Choose a role</Label>
                  <Select placeholder="Select a role">
                    <SelectGroup label="Engineering">
                      <SelectOption value="frontend">Frontend Developer</SelectOption>
                      <SelectOption value="backend">Backend Developer</SelectOption>
                      <SelectOption value="fullstack">Full Stack Developer</SelectOption>
                    </SelectGroup>
                    <SelectGroup label="Design">
                      <SelectOption value="ux">UX Designer</SelectOption>
                      <SelectOption value="ui">UI Designer</SelectOption>
                    </SelectGroup>
                  </Select>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Multi-Select */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Multi-Select</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Dropdown for selecting multiple options</p>
          
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Basic Multi-Select</CardTitle>
                <CardDescription>Select multiple items with chips</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="mb-1.5 block">Select technologies</Label>
                  <MultiSelect placeholder="Choose technologies" defaultValues={["react", "typescript"]}>
                    <MultiSelectOption value="react">React</MultiSelectOption>
                    <MultiSelectOption value="vue">Vue.js</MultiSelectOption>
                    <MultiSelectOption value="angular">Angular</MultiSelectOption>
                    <MultiSelectOption value="typescript">TypeScript</MultiSelectOption>
                    <MultiSelectOption value="javascript">JavaScript</MultiSelectOption>
                    <MultiSelectOption value="python">Python</MultiSelectOption>
                  </MultiSelect>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">With Groups & Actions</CardTitle>
                <CardDescription>Organized options with select all/clear</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="mb-1.5 block">Assign team members</Label>
                  <MultiSelect placeholder="Select team members" defaultValues={["alice", "bob"]}>
                    <MultiSelectActions allValues={["alice", "bob", "carol", "david", "eve"]} />
                    <MultiSelectGroup label="Engineering">
                      <MultiSelectOption value="alice">Alice Chen</MultiSelectOption>
                      <MultiSelectOption value="bob">Bob Smith</MultiSelectOption>
                      <MultiSelectOption value="carol">Carol White</MultiSelectOption>
                    </MultiSelectGroup>
                    <MultiSelectGroup label="Design">
                      <MultiSelectOption value="david">David Kim</MultiSelectOption>
                      <MultiSelectOption value="eve">Eve Johnson</MultiSelectOption>
                    </MultiSelectGroup>
                  </MultiSelect>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Toasts */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Toasts</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Temporary notifications for user feedback</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Toast Variants</CardTitle>
              <CardDescription>Click buttons to trigger different toast types</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-3">
                <Button 
                  variant="secondary" 
                  onClick={() => success("Your changes have been saved successfully.")}
                >
                  Success Toast
                </Button>
                <Button 
                  variant="secondary" 
                  onClick={() => error("Something went wrong. Please try again.", "Error")}
                >
                  Error Toast
                </Button>
                <Button 
                  variant="secondary" 
                  onClick={() => warning("Please review before proceeding.", "Warning")}
                >
                  Warning Toast
                </Button>
                <Button 
                  variant="secondary" 
                  onClick={() => info("New features are now available!", "What's New")}
                >
                  Info Toast
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Dropdown Menu */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Dropdown Menu</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Action menus and context menus</p>
          
          <Card>
            <CardHeader>
              <CardTitle className="font-sans text-lg">Menu Examples</CardTitle>
              <CardDescription>Click buttons to open dropdown menus</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4">
                <DropdownMenu>
                  <DropdownTrigger asChild>
                    <Button variant="secondary">Actions Menu</Button>
                  </DropdownTrigger>
                  <DropdownContent>
                    <DropdownLabel>Actions</DropdownLabel>
                    <DropdownItem>Edit</DropdownItem>
                    <DropdownItem>Duplicate</DropdownItem>
                    <DropdownItem>Archive</DropdownItem>
                    <DropdownSeparator />
                    <DropdownItem destructive>Delete</DropdownItem>
                  </DropdownContent>
                </DropdownMenu>

                <DropdownMenu>
                  <DropdownTrigger asChild>
                    <Button variant="secondary">User Menu</Button>
                  </DropdownTrigger>
                  <DropdownContent align="start">
                    <DropdownLabel>My Account</DropdownLabel>
                    <DropdownItem>Profile</DropdownItem>
                    <DropdownItem>Settings</DropdownItem>
                    <DropdownItem>Billing</DropdownItem>
                    <DropdownSeparator />
                    <DropdownItem>Sign out</DropdownItem>
                  </DropdownContent>
                </DropdownMenu>
              </div>
            </CardContent>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Radio Group */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Radio Group</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Single-select options for forms</p>
          
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Basic Radio Group</CardTitle>
                <CardDescription>Vertical and horizontal layouts</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <Label className="mb-3 block">Notification preference</Label>
                  <RadioGroup defaultValue="email">
                    <RadioGroupItem value="email" label="Email" />
                    <RadioGroupItem value="sms" label="SMS" />
                    <RadioGroupItem value="push" label="Push notification" />
                    <RadioGroupItem value="none" label="None" disabled />
                  </RadioGroup>
                </div>
                <div>
                  <Label className="mb-3 block">Size (horizontal)</Label>
                  <RadioGroup defaultValue="md" orientation="horizontal">
                    <RadioGroupItem value="sm" label="Small" />
                    <RadioGroupItem value="md" label="Medium" />
                    <RadioGroupItem value="lg" label="Large" />
                  </RadioGroup>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Radio Cards</CardTitle>
                <CardDescription>Selectable card-style options</CardDescription>
              </CardHeader>
              <CardContent>
                <RadioGroup defaultValue="pro" className="grid grid-cols-1 gap-3">
                  <RadioCard value="free">
                    <div className="font-medium text-charcoal dark:text-white">Free</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">Basic features for individuals</div>
                  </RadioCard>
                  <RadioCard value="pro">
                    <div className="font-medium text-charcoal dark:text-white">Pro</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">Advanced features for teams</div>
                  </RadioCard>
                  <RadioCard value="enterprise">
                    <div className="font-medium text-charcoal dark:text-white">Enterprise</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">Custom solutions for large orgs</div>
                  </RadioCard>
                </RadioGroup>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Progress */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Progress</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Progress bars and indicators</p>
          
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Progress Bars</CardTitle>
                <CardDescription>Linear progress indicators</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Default (65%)</p>
                  <Progress value={65} />
                </div>
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>With Label</p>
                  <Progress value={42} showLabel />
                </div>
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Sizes</p>
                  <div className="space-y-3">
                    <Progress value={80} size="sm" />
                    <Progress value={80} size="md" />
                    <Progress value={80} size="lg" />
                  </div>
                </div>
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Variants</p>
                  <div className="space-y-3">
                    <Progress value={75} variant="default" />
                    <Progress value={75} variant="success" />
                    <Progress value={75} variant="warning" />
                    <Progress value={75} variant="gradient" />
                  </div>
                </div>
                <div>
                  <p className={`text-sm mb-2 ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>Indeterminate</p>
                  <Progress indeterminate />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Circular Progress</CardTitle>
                <CardDescription>Ring-style progress indicators</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-6">
                  <div className="text-center">
                    <CircularProgress value={25} size={48} />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>25%</p>
                  </div>
                  <div className="text-center">
                    <CircularProgress value={50} size={56} showLabel />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>With label</p>
                  </div>
                  <div className="text-center">
                    <CircularProgress value={75} size={64} variant="success" />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Success</p>
                  </div>
                  <div className="text-center">
                    <CircularProgress indeterminate size={48} />
                    <p className={`text-xs mt-2 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Loading</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Accordion */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Accordion</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Collapsible content sections</p>
          
          <div className="grid md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Single Accordion</CardTitle>
                <CardDescription>Only one item open at a time</CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="single" defaultValue={["item-1"]}>
                  <AccordionItem value="item-1">
                    <AccordionTrigger>What is Eliza Forge?</AccordionTrigger>
                    <AccordionContent>
                      Eliza Forge is an AI-powered platform that helps organizations 
                      build intelligent applications with ease. It provides tools for 
                      document processing, business intelligence, and more.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-2">
                    <AccordionTrigger>How do I get started?</AccordionTrigger>
                    <AccordionContent>
                      Getting started is easy! Simply sign up for an account, configure 
                      your data connections, and start asking questions. Our AI will 
                      analyze your data and provide insights.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="item-3">
                    <AccordionTrigger>What data sources are supported?</AccordionTrigger>
                    <AccordionContent>
                      We support a wide variety of data sources including databases 
                      (PostgreSQL, MySQL, MongoDB), file storage (S3, Google Drive), 
                      and SaaS applications (Salesforce, HubSpot, Zendesk).
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="font-sans text-lg">Multiple Accordion</CardTitle>
                <CardDescription>Multiple items can be open</CardDescription>
              </CardHeader>
              <CardContent>
                <Accordion type="multiple" defaultValue={["faq-1", "faq-2"]}>
                  <AccordionItem value="faq-1">
                    <AccordionTrigger>Is my data secure?</AccordionTrigger>
                    <AccordionContent>
                      Yes! We use enterprise-grade encryption for data at rest and 
                      in transit. Your data is never shared with third parties and 
                      you maintain full control over access permissions.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="faq-2">
                    <AccordionTrigger>Can I cancel anytime?</AccordionTrigger>
                    <AccordionContent>
                      Absolutely. You can cancel your subscription at any time with 
                      no cancellation fees. Your data will be available for export 
                      for 30 days after cancellation.
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="faq-3">
                    <AccordionTrigger>Do you offer support?</AccordionTrigger>
                    <AccordionContent>
                      We offer 24/7 support for Enterprise customers and business 
                      hours support for Pro customers. All plans include access to 
                      our comprehensive documentation and community forums.
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Sidebars */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Sidebars</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Collapsible sidebars with expandable sub-menus and tooltips</p>
          
          <div className="grid md:grid-cols-3 gap-8">
            {/* Collapsible Sidebar */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Collapsible Sidebar (ChatGPT Style)</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Hover over the logo to reveal the toggle. When collapsed, shows lowercase "e".</p>
              <div className="border rounded-2xl overflow-hidden h-[500px] flex">
                <SidebarProvider>
                  <Sidebar className="h-full rounded-none border-0">
                    <SidebarHeader>
                      <SidebarLogo showToggleOnHover />
                    </SidebarHeader>
                    <SidebarContent>
                      <SidebarSection title="Main">
                        <SidebarItem icon={<HomeIcon className="h-5 w-5" />} isActive>
                          Home
                        </SidebarItem>
                        <SidebarItem icon={<DocumentTextIcon className="h-5 w-5" />}>
                          Documents
                        </SidebarItem>
                        <SidebarItem icon={<UserGroupIcon className="h-5 w-5" />} badge={3}>
                          Talent Search
                        </SidebarItem>
                        <SidebarItem icon={<EnvelopeIcon className="h-5 w-5" />}>
                          Outreach
                        </SidebarItem>
                        <SidebarItem icon={<ChatBubbleLeftRightIcon className="h-5 w-5" />}>
                          Chat
                        </SidebarItem>
                      </SidebarSection>
                      <SidebarSection title="Settings">
                        <SidebarItem icon={<Cog6ToothIcon className="h-5 w-5" />}>
                          Configuration
                        </SidebarItem>
                      </SidebarSection>
                    </SidebarContent>
                    <SidebarFooter>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                        <span className="whitespace-nowrap overflow-hidden">v1.0</span>
                      </div>
                    </SidebarFooter>
                  </Sidebar>
                </SidebarProvider>
              </div>
            </div>

            {/* Simple Sidebar */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Simple List Sidebar</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Basic navigation without collapsing.</p>
              <div className="border rounded-2xl overflow-hidden h-[500px]">
                <Sidebar className="h-full rounded-none border-0">
                  <SidebarHeader>
                    <SidebarLogo />
                  </SidebarHeader>
                  <SidebarContent>
                    <SidebarSection title="Main">
                      <SidebarItem icon={<HomeIcon className="h-5 w-5" />} isActive>
                        Home
                      </SidebarItem>
                      <SidebarItem icon={<DocumentTextIcon className="h-5 w-5" />}>
                        Documents
                      </SidebarItem>
                      <SidebarItem icon={<UserGroupIcon className="h-5 w-5" />} badge={3}>
                        Talent Search
                      </SidebarItem>
                      <SidebarItem icon={<EnvelopeIcon className="h-5 w-5" />}>
                        Outreach
                      </SidebarItem>
                      <SidebarItem icon={<ChatBubbleLeftRightIcon className="h-5 w-5" />}>
                        Chat
                      </SidebarItem>
                    </SidebarSection>
                    <SidebarSection title="Settings">
                      <SidebarItem icon={<Cog6ToothIcon className="h-5 w-5" />}>
                        Configuration
                      </SidebarItem>
                    </SidebarSection>
                  </SidebarContent>
                  <SidebarFooter>
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
                      Eliza Forge v1.0
                    </div>
                  </SidebarFooter>
                </Sidebar>
              </div>
            </div>

            {/* Expandable Sidebar */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Expandable Sub-menus</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Add children to SidebarItem for expandable behavior.</p>
              <div className="border rounded-2xl overflow-hidden h-[500px]">
                <Sidebar className="h-full w-full rounded-none border-0">
                  <SidebarHeader>
                    <SidebarLogo />
                  </SidebarHeader>
                  
                  <SidebarAction icon={<PlusIcon className="h-4 w-4" />}>
                    New project
                  </SidebarAction>

                  <SidebarContent>
                    <SidebarSection>
                      {/* Home with sub-items - just add SidebarSubItem children! */}
                      <SidebarItem icon={<HomeIcon className="h-5 w-5" />} defaultOpen>
                        Home
                        <SidebarSubItem isActive>Market Analysis</SidebarSubItem>
                        <SidebarSubItem>Buy Home</SidebarSubItem>
                        <SidebarSubItem>Sell Home</SidebarSubItem>
                        <SidebarSubItem>Rent Home</SidebarSubItem>
                        <SidebarSubItem>Property Investment</SidebarSubItem>
                        <SidebarSubItem>Mortgage Calculator</SidebarSubItem>
                      </SidebarItem>

                      {/* Simple nav items - no children = no expansion */}
                      <SidebarItem icon={<ShoppingBagIcon className="h-5 w-5" />}>
                        Shopping
                      </SidebarItem>
                      <SidebarItem icon={<FolderIcon className="h-5 w-5" />}>
                        Projects
                      </SidebarItem>
                      <SidebarItem icon={<ChatBubbleLeftRightIcon className="h-5 w-5" />}>
                        Chat
                      </SidebarItem>
                    </SidebarSection>

                    <SidebarSeparator />

                    {/* Starred section */}
                    <SidebarLabel>Starred</SidebarLabel>
                    <SidebarLink>AI Voice Assistant for Inbound Call...</SidebarLink>

                    {/* Recents section */}
                    <SidebarLabel>Recents</SidebarLabel>
                    <SidebarLink>Modern Farmhouse Design Project</SidebarLink>
                    <SidebarLink>Downtown Loft Development Analysis</SidebarLink>
                  </SidebarContent>
                </Sidebar>
              </div>
            </div>

            {/* Submenu Sidebar (Contextual Navigation) */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Submenu Sidebar</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>For contextual/immersive navigation with back button.</p>
              <div className="border rounded-2xl overflow-hidden h-[360px]">
                <SidebarSubmenu
                  title="Platform Settings"
                  items={[
                    { label: 'Admin Management', path: '#admin-mgmt', icon: UsersIcon },
                    { label: 'AI Providers', path: '#ai-providers', icon: SparklesIcon },
                    { label: 'Email Integration', path: '#email', icon: EnvelopeIcon },
                    { label: 'Job Scheduler', path: '#scheduler', icon: CalendarIcon },
                  ]}
                  onBack={() => info('Back clicked - would return to main sidebar')}
                  isVisible={true}
                />
              </div>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Breadcrumb, Pagination, Combobox */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Navigation & Selection</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Breadcrumbs, pagination, and autocomplete components</p>

          <div className="grid md:grid-cols-2 gap-8 mb-8">
            {/* Breadcrumb */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Breadcrumb</h3>
              <Card>
                <CardContent className="p-6 space-y-6">
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Basic</p>
                    <Breadcrumb>
                      <BreadcrumbItem href="#">Home</BreadcrumbItem>
                      <BreadcrumbItem href="#">Products</BreadcrumbItem>
                      <BreadcrumbItem href="#">Category</BreadcrumbItem>
                      <BreadcrumbItem isCurrent>Item</BreadcrumbItem>
                    </Breadcrumb>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">With Home Icon</p>
                    <Breadcrumb showHome>
                      <BreadcrumbItem href="#">Settings</BreadcrumbItem>
                      <BreadcrumbItem isCurrent>Account</BreadcrumbItem>
                    </Breadcrumb>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">With Ellipsis</p>
                    <Breadcrumb>
                      <BreadcrumbItem href="#">Home</BreadcrumbItem>
                      <BreadcrumbEllipsis />
                      <BreadcrumbItem href="#">Parent</BreadcrumbItem>
                      <BreadcrumbItem isCurrent>Current</BreadcrumbItem>
                    </Breadcrumb>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Pagination */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Pagination</h3>
              <Card>
                <CardContent className="p-6 space-y-6">
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Full Pagination</p>
                    <Pagination
                      page={5}
                      totalPages={10}
                      onPageChange={(p) => console.log('Page:', p)}
                    />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Simple Pagination</p>
                    <SimplePagination
                      page={3}
                      totalPages={7}
                      onPageChange={(p) => console.log('Page:', p)}
                    />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Small Size</p>
                    <Pagination
                      page={2}
                      totalPages={5}
                      size="sm"
                      showFirstLast={false}
                      onPageChange={(p) => console.log('Page:', p)}
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Combobox */}
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Combobox / Autocomplete</h3>
              <Card>
                <CardContent className="p-6 space-y-6">
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Single Select</p>
                    <Combobox
                      options={[
                        { value: 'react', label: 'React', description: 'A JavaScript library' },
                        { value: 'vue', label: 'Vue', description: 'The Progressive Framework' },
                        { value: 'angular', label: 'Angular', description: 'Platform for web apps' },
                        { value: 'svelte', label: 'Svelte', description: 'Cybernetically enhanced' },
                        { value: 'solid', label: 'Solid', description: 'Simple and performant' },
                      ] as ComboboxOption[]}
                      placeholder="Select a framework..."
                      onChange={(v) => console.log('Selected:', v)}
                    />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">With Icons</p>
                    <Combobox
                      options={[
                        { value: 'home', label: 'Home', icon: <HomeIcon className="w-4 h-4" /> },
                        { value: 'documents', label: 'Documents', icon: <DocumentTextIcon className="w-4 h-4" /> },
                        { value: 'settings', label: 'Settings', icon: <Cog6ToothIcon className="w-4 h-4" /> },
                      ] as ComboboxOption[]}
                      placeholder="Go to..."
                      onChange={(v) => console.log('Selected:', v)}
                    />
                  </div>
                </CardContent>
              </Card>
            </div>

            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Multi Combobox</h3>
              <Card>
                <CardContent className="p-6 space-y-6">
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Multi Select</p>
                    <MultiCombobox
                      options={[
                        { value: 'typescript', label: 'TypeScript' },
                        { value: 'javascript', label: 'JavaScript' },
                        { value: 'python', label: 'Python' },
                        { value: 'rust', label: 'Rust' },
                        { value: 'go', label: 'Go' },
                        { value: 'java', label: 'Java' },
                      ] as ComboboxOption[]}
                      placeholder="Select languages..."
                      onChange={(v) => console.log('Selected:', v)}
                    />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">With Pre-selected</p>
                    <MultiCombobox
                      options={[
                        { value: 'alice', label: 'Alice Smith' },
                        { value: 'bob', label: 'Bob Johnson' },
                        { value: 'carol', label: 'Carol Williams' },
                        { value: 'dave', label: 'Dave Brown' },
                      ] as ComboboxOption[]}
                      value={['alice', 'carol']}
                      placeholder="Add team members..."
                      onChange={(v) => console.log('Selected:', v)}
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* DataTable */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>DataTable</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Feature-rich data tables with sorting, pagination, and row selection</p>

          <DataTableShowcase darkMode={darkMode} />
        </section>

        <Separator className="my-12" />

        {/* Chat Components */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Chat Components</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Complete chat UI with message bubbles, thinking indicators, and canvas mode</p>

          {/* Full Chat Demo */}
          <div className="mb-8">
            <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Full Chat Interface with Canvas</h3>
            <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Click on code blocks or artifacts to open them in the canvas panel on the right.</p>

            <ChatProvider>
              <div className="border rounded-2xl overflow-hidden h-[600px]">
                <ChatContainer>
                  <ChatMessagesPane className="bg-white dark:bg-dark-surface">
                    <ChatScrollArea>
                      {/* System message */}
                      <MessageBubble role="system">
                        Conversation started
                      </MessageBubble>

                      {/* User message */}
                      <MessageBubble role="user" timestamp="10:30 AM">
                        <MessageContent>
                          Can you help me write a function to calculate fibonacci numbers?
                        </MessageContent>
                      </MessageBubble>

                      {/* Assistant message with code */}
                      <MessageBubble role="assistant" timestamp="10:30 AM">
                        <MessageContent>
                          <p>Of course! Here's a Python function to calculate Fibonacci numbers:</p>
                        </MessageContent>
                        <ChatCodeBlock 
                          language="python"
                          filename="fibonacci.py"
                          code={`def fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# Example usage
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")`}
                        />
                        <MessageContent>
                          <p>This uses recursion. For better performance with large numbers, you might want to use memoization or an iterative approach.</p>
                        </MessageContent>
                      </MessageBubble>

                      {/* User message */}
                      <MessageBubble role="user" timestamp="10:31 AM">
                        <MessageContent>
                          Can you show me an image of the Fibonacci spiral?
                        </MessageContent>
                      </MessageBubble>

                      {/* Assistant message with image */}
                      <MessageBubble role="assistant" timestamp="10:31 AM">
                        <MessageContent>
                          <p>Here's a visualization of the Fibonacci spiral:</p>
                        </MessageContent>
                        <ChatImage 
                          src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/FibonacciSpiral.svg/354px-FibonacciSpiral.svg.png"
                          alt="Fibonacci Spiral"
                          caption="The golden spiral, an approximation of the Fibonacci spiral"
                        />
                      </MessageBubble>

                      {/* Artifact button example */}
                      <MessageBubble role="assistant" timestamp="10:32 AM">
                        <MessageContent>
                          <p>I've also created an interactive visualization you can explore:</p>
                        </MessageContent>
                        <ArtifactButton
                          artifactType="code"
                          title="Fibonacci Visualizer"
                          description="Interactive spiral generator"
                          canvasContent={
                            <div className="p-6 text-center text-white">
                              <h2 className="text-xl font-bold mb-4">Fibonacci Visualizer</h2>
                              <p className="text-gray-400 mb-4">Interactive content would go here</p>
                              <div className="w-48 h-48 mx-auto border-2 border-dashed border-gray-600 rounded-full flex items-center justify-center">
                                <span className="text-gray-500">Canvas Content</span>
                              </div>
                            </div>
                          }
                        />
                      </MessageBubble>
                    </ChatScrollArea>

                    <ChatInputArea>
                      <PromptBar placeholder="Type a message..." onSubmit={(v) => console.log(v)} />
                    </ChatInputArea>
                  </ChatMessagesPane>

                  <CanvasPanel defaultWidthPercent={40} />
                </ChatContainer>
              </div>
            </ChatProvider>
          </div>

          {/* Message Bubbles */}
          <div className="grid md:grid-cols-2 gap-8 mb-8">
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Message Bubbles</h3>
              <Card>
                <CardContent className="p-6 space-y-4">
                  <MessageBubble role="user">
                    <MessageContent>This is a user message with the brand color.</MessageContent>
                  </MessageBubble>
                  <MessageBubble role="assistant">
                    <MessageContent>This is an assistant response with a subtle background.</MessageContent>
                  </MessageBubble>
                  <MessageBubble role="assistant" isStreaming>
                    <MessageContent>This message is currently streaming</MessageContent>
                  </MessageBubble>
                  <MessageBubble role="system">
                    System notification
                  </MessageBubble>
                </CardContent>
              </Card>
            </div>

            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Thinking Indicators</h3>
              <Card>
                <CardContent className="p-6 space-y-6">
                  <ThinkingIndicator label="Thinking" />
                  <ThinkingIndicator
                    label="Reasoning"
                    expandable
                    thinkingText={`Let me analyze this step by step:

1. First, I need to understand the problem...
2. The key insight here is that...
3. Therefore, the solution would be...

This approach ensures optimal performance while maintaining readability.`}
                  />
                  <ThinkingIndicator
                    label="Deep thinking"
                    expandable
                    defaultExpanded
                    thinkingText={`Analyzing the request...
Considering multiple approaches...
Evaluating trade-offs...`}
                  />
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Thinking Indicator with Execution Steps */}
          <div className="mb-8">
            <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Execution Steps (Data Analysis)</h3>
            <Card>
              <CardContent className="p-6 space-y-8">
                {/* Active execution */}
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wider">Processing Query</p>
                  <ThinkingIndicator
                    label="Executing query..."
                    steps={[
                      { id: '1', label: 'Parsing question', status: 'completed', description: 'Extracted intent and entities' },
                      { id: '2', label: 'Generating SQL', status: 'completed', description: 'Created optimized query' },
                      { id: '3', label: 'Executing query', status: 'active', description: 'Running against insurance database' },
                      { id: '4', label: 'Analyzing results', status: 'pending' },
                      { id: '5', label: 'Generating insights', status: 'pending' },
                    ]}
                  />
                </div>

                {/* Completed execution */}
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wider">Completed (auto-detected)</p>
                  <ThinkingIndicator
                    label="Analysis complete"
                    steps={[
                      { id: '1', label: 'Parsing question', status: 'completed' },
                      { id: '2', label: 'Generating SQL', status: 'completed' },
                      { id: '3', label: 'Executing query', status: 'completed', description: 'Retrieved 1,247 rows in 0.3s' },
                      { id: '4', label: 'Analyzing results', status: 'completed' },
                      { id: '5', label: 'Generating insights', status: 'completed' },
                    ]}
                    stepsDefaultExpanded={false}
                  />
                </div>

                {/* Explicitly complete (no steps) */}
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wider">Completed (explicit)</p>
                  <ThinkingIndicator
                    isComplete
                    completeLabel="Analysis complete"
                    expandable
                    thinkingText="Query executed successfully in 0.3s. Found 1,247 matching records."
                  />
                </div>

                {/* Failed step */}
                <div>
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3 uppercase tracking-wider">With Error</p>
                  <ThinkingIndicator
                    label="Query failed"
                    steps={[
                      { id: '1', label: 'Parsing question', status: 'completed' },
                      { id: '2', label: 'Generating SQL', status: 'completed' },
                      { id: '3', label: 'Executing query', status: 'failed', description: 'Connection timeout after 30s' },
                      { id: '4', label: 'Analyzing results', status: 'pending' },
                    ]}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Code Blocks */}
          <div className="mb-8">
            <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Code Blocks in Chat</h3>
            <Card>
              <CardContent className="p-6">
                <ChatProvider>
                  <ChatCodeBlock
                    language="typescript"
                    filename="example.ts"
                    code={`interface User {
  id: string;
  name: string;
  email: string;
}

function greetUser(user: User): string {
  return \`Hello, \${user.name}!\`;
}`}
                  />
                </ChatProvider>
              </CardContent>
            </Card>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Page Layout Components */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Page Layout</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Consistent page structure with headers and sections</p>

          <div className="space-y-8">
            {/* PageHeader Examples */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Page Header</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Standardized page titles with Libre Baskerville font, optional description, and action buttons.
              </p>
              <Card>
                <CardContent className="p-0">
                  <PageHeader
                    title="Admin Settings"
                    description="Configure AI model providers and system settings for your organization"
                    actions={
                      <div className="flex gap-2">
                        <Button variant="secondary" size="sm">Export</Button>
                        <Button size="sm">
                          <PlusIcon className="h-4 w-4 mr-1" />
                          Add New
                        </Button>
                      </div>
                    }
                  />
                </CardContent>
              </Card>
            </div>

            {/* PageHeader with Breadcrumb */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Page Header with Breadcrumb</h3>
              <Card>
                <CardContent className="p-0">
                  <PageHeader
                    title="User Details"
                    description="View and manage user information"
                    breadcrumb={
                      <Breadcrumb>
                        <BreadcrumbItem href="#">Dashboard</BreadcrumbItem>
                        <BreadcrumbItem href="#">Users</BreadcrumbItem>
                        <BreadcrumbItem isCurrent>Alice Johnson</BreadcrumbItem>
                      </Breadcrumb>
                    }
                    actions={
                      <Button variant="outline" size="sm">
                        <PencilIcon className="h-4 w-4 mr-1" />
                        Edit
                      </Button>
                    }
                  />
                </CardContent>
              </Card>
            </div>

            {/* SectionHeader Examples */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Section Headers</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Section titles with Hedvig Letters Serif font, optional icons, and action buttons.
              </p>
              <Card>
                <CardContent className="p-6 space-y-6">
                  <SectionHeader
                    icon={<Cog6ToothIcon className="h-5 w-5" />}
                    title="AI Model Configuration"
                    description="Configure your own API keys for OpenAI, Anthropic, and AWS Bedrock"
                    actions={
                      <Button size="sm">
                        <PlusIcon className="h-4 w-4 mr-1" />
                        Add Provider
                      </Button>
                    }
                  />
                  
                  <Separator />
                  
                  <SectionHeader
                    icon={<UsersIcon className="h-5 w-5" />}
                    title="Team Members"
                    description="Manage team access and permissions"
                  />
                  
                  <Separator />
                  
                  <SectionHeader
                    title="Simple Section"
                    description="Just a title and description, no icon or actions"
                  />
                </CardContent>
              </Card>
            </div>

            {/* PageContent Example */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Page Content Wrapper</h3>
              <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Provides consistent padding and max-width constraints for page content.
              </p>
              <Card>
                <CardContent className="p-0 bg-gray-100 dark:bg-dark-bg">
                  <div className="border-b border-gray-200 dark:border-dark-border py-2 px-4 text-xs text-gray-500 font-mono">
                    {'<PageContent maxWidth="lg">'}
                  </div>
                  <PageContent maxWidth="lg" className="bg-white dark:bg-dark-surface rounded-b-lg">
                    <div className="p-4 border-2 border-dashed border-gray-300 dark:border-dark-border rounded-lg text-center text-gray-500 dark:text-gray-400">
                      Page content goes here (max-w-5xl)
                    </div>
                  </PageContent>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Full Dashboard Preview */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Dashboard Preview</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>A mini preview of how the home dashboard will look</p>
          
          <Card className="overflow-hidden">
            {/* Gradient header */}
            <div className="h-1 bg-gradient-to-r from-eliza-red via-eliza-red-light to-eliza-red-coral"></div>
            
            <div className={`p-12 ${darkMode ? 'bg-gradient-to-b from-eliza-red/10 to-dark-surface' : 'bg-gradient-to-b from-eliza-red/5 to-white'}`}>
              <div className="text-center max-w-2xl mx-auto">
                <h1 className={`font-title text-4xl md:text-5xl mb-3 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                  Good morning, Eliza.
                </h1>
                <p className={`font-subtitle mb-8 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  Your enterprise ecosystem is ready for deployment.
                </p>
                
                {/* Prompt bar */}
                <div className="relative mb-6">
                  <Input 
                    placeholder="Describe the workflow you need..."
                    className="h-14 text-base rounded-2xl shadow-card border-gray-100 dark:border-gray-700 pr-14"
                  />
                  <Button 
                    variant="brand" 
                    size="icon" 
                    className="absolute right-2 top-1/2 -translate-y-1/2 shadow-lg"
                  >
                    <ArrowUpIcon className="h-5 w-5" />
                  </Button>
                </div>
                
                {/* Quick actions */}
                <div className="flex flex-wrap justify-center gap-3">
                  <Button variant="secondary" size="sm">
                    <SparklesIcon className="h-4 w-4 text-eliza-red" />
                    Create job spec
                  </Button>
                  <Button variant="secondary" size="sm">
                    <UserGroupIcon className="h-4 w-4 text-eliza-red" />
                    Search talent pool
                  </Button>
                  <Button variant="secondary" size="sm">
                    <ChartBarIcon className="h-4 w-4 text-eliza-red" />
                    Pipeline analytics
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </section>

        <Separator className="my-12" />

        {/* Citation Components */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Citation Components</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Inline citations, source cards, and PDF viewing for RAG responses</p>

          <CitationComponentsSection darkMode={darkMode} />
        </section>

        <Separator className="my-12" />

        {/* Popover */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Popover</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Floating content panel for rich interactions</p>

          <div className="space-y-8">
            {/* Basic Popover */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Basic Popover
              </h3>
              <Card>
                <CardContent className="p-6 flex gap-4 flex-wrap">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline">Open Popover</Button>
                    </PopoverTrigger>
                    <PopoverContent>
                      <PopoverBody>
                        <h4 className={`font-medium mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Popover Title</h4>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          This is a popover with rich content. Unlike dropdown menus, popovers can contain any content.
                        </p>
                      </PopoverBody>
                    </PopoverContent>
                  </Popover>
                </CardContent>
              </Card>
            </div>

            {/* Alignment Options */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Alignment Options
              </h3>
              <Card>
                <CardContent className="p-6 flex gap-4 flex-wrap items-start justify-center">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="sm">Align Start</Button>
                    </PopoverTrigger>
                    <PopoverContent align="start">
                      <PopoverBody className="text-sm">Aligned to start</PopoverBody>
                    </PopoverContent>
                  </Popover>
                  
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="sm">Align Center</Button>
                    </PopoverTrigger>
                    <PopoverContent align="center">
                      <PopoverBody className="text-sm">Aligned to center (default)</PopoverBody>
                    </PopoverContent>
                  </Popover>
                  
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="sm">Align End</Button>
                    </PopoverTrigger>
                    <PopoverContent align="end">
                      <PopoverBody className="text-sm">Aligned to end</PopoverBody>
                    </PopoverContent>
                  </Popover>
                </CardContent>
              </Card>
            </div>

            {/* With Header & Footer */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                With Header & Footer
              </h3>
              <Card>
                <CardContent className="p-6 flex gap-4 flex-wrap">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline">
                        <BellIcon className="h-4 w-4 mr-2" />
                        Notifications
                        <Badge variant="brand" className="ml-2">3</Badge>
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent align="end" className="w-80">
                      <PopoverHeader>
                        <div className="flex items-center gap-2">
                          <span>Notifications</span>
                          <Badge variant="brand">3</Badge>
                        </div>
                      </PopoverHeader>
                      <div className="max-h-64 overflow-y-auto divide-y divide-gray-200 dark:divide-dark-border/30">
                        <div className="p-3 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer">
                          <p className="font-medium text-sm">New message received</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">2 minutes ago</p>
                        </div>
                        <div className="p-3 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer">
                          <p className="font-medium text-sm">Analysis completed</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">1 hour ago</p>
                        </div>
                        <div className="p-3 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer">
                          <p className="font-medium text-sm">New user joined</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">3 hours ago</p>
                        </div>
                      </div>
                      <PopoverFooter className="flex justify-between">
                        <Button variant="ghost" size="sm">Mark all read</Button>
                        <Button variant="link" size="sm">View all</Button>
                      </PopoverFooter>
                    </PopoverContent>
                  </Popover>
                </CardContent>
              </Card>
            </div>

            {/* Controlled State */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Usage
              </h3>
              <Card>
                <CardContent className="p-6">
                  <pre className={`text-xs p-4 rounded-lg overflow-x-auto ${darkMode ? 'bg-dark-surface-2 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
{`<Popover>
  <PopoverTrigger asChild>
    <Button>Open</Button>
  </PopoverTrigger>
  <PopoverContent align="end">
    <PopoverHeader>Title</PopoverHeader>
    <PopoverBody>Content here</PopoverBody>
    <PopoverFooter>Footer actions</PopoverFooter>
  </PopoverContent>
</Popover>`}
                  </pre>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Banner */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Banner</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Full-width contextual notification bars</p>

          <div className="space-y-8">
            {/* Variants */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Variants
              </h3>
              <Card>
                <CardContent className="p-0 space-y-0">
                  <Banner
                    variant="info"
                    message="This is an informational banner for general notices."
                    dismissible={false}
                  />
                  <Banner
                    variant="success"
                    message="Operation completed successfully!"
                    dismissible={false}
                  />
                  <Banner
                    variant="warning"
                    message="Please review your settings before continuing."
                    dismissible={false}
                  />
                  <Banner
                    variant="error"
                    message="An error occurred. Please try again."
                    dismissible={false}
                  />
                  <Banner
                    variant="brand"
                    message="Welcome to Eliza Forge!"
                    dismissible={false}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Admin Variants */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Admin Variants (Solid Colors)
              </h3>
              <Card>
                <CardContent className="p-0 space-y-0">
                  <Banner
                    variant="tenant-view"
                    icon={<EyeIcon className="h-5 w-5" />}
                    title="Viewing As Tenant"
                    message={<>You are viewing the application as <strong>Demo Corp</strong></>}
                    action={{
                      label: "Exit View Mode",
                      onClick: () => {},
                    }}
                    dismissible={false}
                  />
                  <Banner
                    variant="cross-tenant"
                    icon={<GlobeAltIcon className="h-5 w-5" />}
                    title="Cross-Tenant Access Mode"
                    message={<>You are viewing data from <strong>ALL TENANTS</strong></>}
                    action={{
                      label: "Exit Cross-Tenant Mode",
                      onClick: () => {},
                    }}
                    dismissible={false}
                  />
                </CardContent>
              </Card>
            </div>

            {/* With Title */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                With Icon and Title
              </h3>
              <Card>
                <CardContent className="p-0">
                  <Banner
                    variant="brand"
                    icon={<BuildingOffice2Icon className="h-5 w-5" />}
                    title="Logged in"
                    message={<>You're logged into <strong>Acme Corp</strong></>}
                    dismissible={false}
                  />
                </CardContent>
              </Card>
            </div>

            {/* With Action */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                With Action Button
              </h3>
              <Card>
                <CardContent className="p-0">
                  <Banner
                    variant="warning"
                    title="Session Expiring"
                    message="Your session will expire in 5 minutes."
                    action={{
                      label: "Extend Session",
                      onClick: () => alert("Session extended!"),
                    }}
                    dismissible={false}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Dismissible */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Dismissible (Interactive)
              </h3>
              <Card>
                <CardContent className="p-0">
                  {showDismissibleBanner ? (
                    <Banner
                      variant="success"
                      message="This banner can be dismissed. Click the X to hide it."
                      onDismiss={() => setShowDismissibleBanner(false)}
                    />
                  ) : (
                    <div className="p-4 text-center">
                      <Button onClick={() => setShowDismissibleBanner(true)}>Show Banner</Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Usage */}
            <div>
              <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
                Usage
              </h3>
              <Card>
                <CardContent className="p-6">
                  <pre className={`text-xs p-4 rounded-lg overflow-x-auto ${darkMode ? 'bg-dark-surface-2 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
{`<Banner
  variant="brand"
  icon={<BuildingOffice2Icon className="h-5 w-5" />}
  title="Logged in"
  message={<>You're logged into <strong>Tenant Name</strong></>}
  action={{
    label: "Switch",
    onClick: () => handleSwitch(),
  }}
  dismissible={true}
  onDismiss={() => setShowBanner(false)}
  autoDismiss={3000} // Auto-hide after 3s
/>`}
                  </pre>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <Separator className="my-12" />

        {/* Chart Components */}
        <section className="mb-16">
          <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Chart Components</h2>
          <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Data visualization for the canvas panel</p>

          <ChartComponentsSection darkMode={darkMode} />
        </section>

        {/* Footer */}
        <div className={`text-center py-12 text-sm ${darkMode ? 'text-gray-600' : 'text-gray-400'}`}>
          Eliza Forge Design System • v1.0
        </div>
      </main>
    </div>
  )
}

/* ===========================================
   DataTable Showcase Component
   =========================================== */

interface User {
  id: number
  name: string
  email: string
  role: string
  status: 'active' | 'pending' | 'inactive'
  department: string
  joinedAt: string
}

const sampleUsers: User[] = [
  { id: 1, name: 'Alice Johnson', email: 'alice@example.com', role: 'Admin', status: 'active', department: 'Engineering', joinedAt: '2024-01-15' },
  { id: 2, name: 'Bob Smith', email: 'bob@example.com', role: 'Developer', status: 'active', department: 'Engineering', joinedAt: '2024-02-20' },
  { id: 3, name: 'Carol Williams', email: 'carol@example.com', role: 'Designer', status: 'pending', department: 'Design', joinedAt: '2024-03-10' },
  { id: 4, name: 'David Brown', email: 'david@example.com', role: 'Developer', status: 'active', department: 'Engineering', joinedAt: '2024-01-05' },
  { id: 5, name: 'Eve Davis', email: 'eve@example.com', role: 'Manager', status: 'active', department: 'Operations', joinedAt: '2023-11-12' },
  { id: 6, name: 'Frank Miller', email: 'frank@example.com', role: 'Developer', status: 'inactive', department: 'Engineering', joinedAt: '2023-08-22' },
  { id: 7, name: 'Grace Lee', email: 'grace@example.com', role: 'Designer', status: 'active', department: 'Design', joinedAt: '2024-04-01' },
  { id: 8, name: 'Henry Wilson', email: 'henry@example.com', role: 'Developer', status: 'active', department: 'Engineering', joinedAt: '2024-02-14' },
  { id: 9, name: 'Ivy Chen', email: 'ivy@example.com', role: 'Analyst', status: 'pending', department: 'Analytics', joinedAt: '2024-05-01' },
  { id: 10, name: 'Jack Taylor', email: 'jack@example.com', role: 'Manager', status: 'active', department: 'Sales', joinedAt: '2023-09-30' },
  { id: 11, name: 'Kate Anderson', email: 'kate@example.com', role: 'Developer', status: 'active', department: 'Engineering', joinedAt: '2024-03-25' },
  { id: 12, name: 'Leo Martinez', email: 'leo@example.com', role: 'Designer', status: 'active', department: 'Design', joinedAt: '2024-01-18' },
]

function DataTableShowcase({ darkMode }: { darkMode: boolean }) {
  const [sortState, setSortState] = React.useState<SortState>({ column: null, direction: null })
  const [page, setPage] = React.useState(1)
  const [selectedRows, setSelectedRows] = React.useState<Set<string | number>>(new Set())
  const [isLoading, setIsLoading] = React.useState(false)

  // Apply sorting
  const sortedUsers = React.useMemo(() => {
    if (!sortState.column || !sortState.direction) return sampleUsers
    
    return [...sampleUsers].sort((a, b) => {
      const aVal = a[sortState.column as keyof User]
      const bVal = b[sortState.column as keyof User]
      
      if (aVal < bVal) return sortState.direction === 'asc' ? -1 : 1
      if (aVal > bVal) return sortState.direction === 'asc' ? 1 : -1
      return 0
    })
  }, [sortState])

  const userColumns: Column<User>[] = [
    {
      id: 'name',
      header: 'User',
      sortable: true,
      cell: ({ row }) => (
        <DataTableAvatar 
          name={row.name} 
          subtitle={row.email}
        />
      ),
    },
    {
      id: 'role',
      header: 'Role',
      accessorKey: 'role',
      sortable: true,
    },
    {
      id: 'department',
      header: 'Department',
      accessorKey: 'department',
      sortable: true,
      hideOnMobile: true,
    },
    {
      id: 'status',
      header: 'Status',
      sortable: true,
      cell: ({ row }) => (
        <DataTableBadge 
          variant={row.status === 'active' ? 'success' : row.status === 'pending' ? 'warning' : 'error'}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${
            row.status === 'active' ? 'bg-green-500' : 
            row.status === 'pending' ? 'bg-yellow-500' : 'bg-red-500'
          }`} />
          {row.status.charAt(0).toUpperCase() + row.status.slice(1)}
        </DataTableBadge>
      ),
    },
    {
      id: 'joinedAt',
      header: 'Joined',
      sortable: true,
      hideOnMobile: true,
      cell: ({ row }) => new Date(row.joinedAt).toLocaleDateString(),
    },
    {
      id: 'actions',
      header: '',
      align: 'right' as const,
      cell: ({ row }) => (
        <DataTableActions>
          <DataTableActionButton
            icon={<EyeIcon className="w-4 h-4" />}
            label="View"
            onClick={() => console.log('View', row.id)}
          />
          <DataTableActionButton
            icon={<PencilIcon className="w-4 h-4" />}
            label="Edit"
            onClick={() => console.log('Edit', row.id)}
          />
          <DataTableActionButton
            icon={<TrashIcon className="w-4 h-4" />}
            label="Delete"
            onClick={() => console.log('Delete', row.id)}
            variant="danger"
          />
        </DataTableActions>
      ),
    },
  ]

  // Simulate loading
  const handleLoadingDemo = () => {
    setIsLoading(true)
    setTimeout(() => setIsLoading(false), 2000)
  }

  return (
    <div className="space-y-8">
      {/* Full Featured Table */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Full Featured Table</h3>
        <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          With sorting, pagination, row selection, and action buttons. Click column headers to sort.
        </p>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {selectedRows.size > 0 && `${selectedRows.size} row(s) selected`}
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={handleLoadingDemo}>
                  Toggle Loading
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setSelectedRows(new Set())}>
                  Clear Selection
                </Button>
              </div>
            </div>
            
            <DataTable
              data={sortedUsers}
              columns={userColumns}
              getRowId={(row) => row.id}
              loading={isLoading}
              selectable
              selectedRows={selectedRows}
              onSelectionChange={setSelectedRows}
              sortable
              sortState={sortState}
              onSortChange={setSortState}
              paginated
              page={page}
              pageSize={5}
              onPageChange={setPage}
              hoverable
              onRowClick={(row) => console.log('Row clicked:', row.name)}
              emptyIcon={<UsersIcon className="w-12 h-12" />}
              emptyMessage="No users found"
            />
          </CardContent>
        </Card>
      </div>

      {/* Expandable Rows Table */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Expandable Rows</h3>
        <p className={`text-sm mb-4 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
          Click on a row to expand and show additional details. Perfect for master-detail views.
        </p>
        <Card>
          <CardContent className="p-4">
            <DataTable
              data={sampleUsers.slice(0, 6)}
              columns={[
                {
                  id: 'name',
                  header: 'User',
                  cell: ({ row }) => (
                    <DataTableAvatar 
                      name={row.name} 
                      subtitle={row.email}
                    />
                  ),
                },
                { id: 'role', header: 'Role', accessorKey: 'role' },
                { id: 'department', header: 'Department', accessorKey: 'department' },
                {
                  id: 'status',
                  header: 'Status',
                  cell: ({ row }) => (
                    <DataTableBadge 
                      variant={row.status === 'active' ? 'success' : row.status === 'pending' ? 'warning' : 'error'}
                    >
                      {row.status}
                    </DataTableBadge>
                  ),
                },
              ]}
              expandable
              allowMultipleExpanded={false}
              renderExpandedRow={(row) => (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Email</p>
                      <p className="text-sm text-charcoal dark:text-white">{row.email}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Department</p>
                      <p className="text-sm text-charcoal dark:text-white">{row.department}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Joined</p>
                      <p className="text-sm text-charcoal dark:text-white">{new Date(row.joinedAt).toLocaleDateString()}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Role</p>
                      <p className="text-sm text-charcoal dark:text-white">{row.role}</p>
                    </div>
                  </div>
                  <div className="flex gap-2 pt-2 border-t border-gray-200 dark:border-dark-border/50">
                    <Button size="sm" variant="outline">View Profile</Button>
                    <Button size="sm" variant="outline">Send Message</Button>
                    <Button size="sm" variant="ghost" className="text-red-500 hover:text-red-600">Remove</Button>
                  </div>
                </div>
              )}
              hoverable
            />
          </CardContent>
        </Card>
      </div>

      {/* Simple Table */}
      <div className="grid md:grid-cols-2 gap-8">
        <div>
          <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Simple Table</h3>
          <Card>
            <CardContent className="p-4">
              <DataTable
                data={sampleUsers.slice(0, 4)}
                columns={[
                  { id: 'name', header: 'Name', accessorKey: 'name' },
                  { id: 'email', header: 'Email', accessorKey: 'email' },
                  { id: 'role', header: 'Role', accessorKey: 'role' },
                ]}
                hoverable
              />
            </CardContent>
          </Card>
        </div>

        <div>
          <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Compact & Striped</h3>
          <Card>
            <CardContent className="p-4">
              <DataTable
                data={sampleUsers.slice(0, 5)}
                columns={[
                  { id: 'name', header: 'Name', accessorKey: 'name' },
                  { id: 'department', header: 'Dept', accessorKey: 'department' },
                  { 
                    id: 'status', 
                    header: 'Status', 
                    cell: ({ row }) => (
                      <DataTableBadge 
                        variant={row.status === 'active' ? 'success' : row.status === 'pending' ? 'warning' : 'error'}
                      >
                        {row.status}
                      </DataTableBadge>
                    ),
                  },
                ]}
                compact
                striped
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Loading & Empty States */}
      <div className="grid md:grid-cols-2 gap-8">
        <div>
          <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Loading State</h3>
          <Card>
            <CardContent className="p-4">
              <DataTable
                data={[]}
                columns={[
                  { id: 'name', header: 'Name' },
                  { id: 'email', header: 'Email' },
                  { id: 'role', header: 'Role' },
                ]}
                loading
                loadingRows={3}
              />
            </CardContent>
          </Card>
        </div>

        <div>
          <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>Empty State</h3>
          <Card>
            <CardContent className="p-4">
              <DataTable
                data={[]}
                columns={[
                  { id: 'name', header: 'Name' },
                  { id: 'email', header: 'Email' },
                  { id: 'role', header: 'Role' },
                ]}
                emptyIcon={<BuildingOffice2Icon className="w-10 h-10" />}
                emptyMessage="No tenants found. Create your first tenant to get started."
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

/* ============================================
   CITATION COMPONENTS SECTION
   ============================================ */

function CitationComponentsSection({ darkMode }: { darkMode: boolean }) {
  // Sample sources for demo
  const sampleSources = [
    {
      index: 1,
      docId: '815',
      pages: '168-168',
      chunkId: '844ff052',
      sectionTitle: '815 Derivatives and Hedging > 10 Overall > 20 Glossary',
    },
    {
      index: 2,
      docId: '815',
      pages: '259-260',
      chunkId: '1af2bd3b',
      sectionTitle: '815 Derivatives and Hedging > 15 Subtopic 15 > 20 Glossary > Entities',
    },
    {
      index: 3,
      docId: '260',
      pages: '12-12',
      chunkId: 'cbc9303a',
      sectionTitle: '260 Earnings Per Share > 10 Overall > 20 Glossary',
    },
  ]

  return (
    <div className="space-y-8">
      {/* Inline Citations */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Inline Citations
        </h3>
        <Card>
          <CardContent className="p-6">
            <p className={`text-sm leading-relaxed ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
              In accounting terms, a <strong>security</strong> is defined as a share, participation, 
              or other interest in property or in an entity of the issuer 
              <InlineCitation number={1} docId="815" pageNumber="168" sectionTitle="815 Derivatives > Glossary" />
              , that possesses all of the following characteristics: <strong>Representation</strong>, 
              <strong>Market Recognition</strong> 
              <InlineCitation number={2} docId="815" pageNumber="259-260" sectionTitle="815 Subtopic 15" />
              , and <strong>Divisibility</strong> 
              <InlineCitation number={3} docId="260" pageNumber="12" sectionTitle="260 Earnings Per Share" />
              .
            </p>
            
            <div className="mt-6 pt-4 border-t border-gray-200 dark:border-dark-border/50">
              <p className={`text-xs mb-3 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Citation sizes:
              </p>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Small:</span>
                  <InlineCitation number={1} size="sm" interactive={false} />
                  <InlineCitation number={2} size="sm" interactive={false} />
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>Medium:</span>
                  <InlineCitation number={1} size="md" interactive={false} />
                  <InlineCitation number={2} size="md" interactive={false} />
                </div>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-dark-border/50">
              <p className={`text-xs mb-3 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Citation group (adjacent citations):
              </p>
              <p className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                This statement is supported by multiple sources
                <CitationGroup>
                  <InlineCitation number={1} size="sm" interactive={false} />
                  <InlineCitation number={2} size="sm" interactive={false} />
                  <InlineCitation number={3} size="sm" interactive={false} />
                </CitationGroup>
                .
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Source Card */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Source Card
        </h3>
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardContent className="p-4">
              <p className={`text-xs mb-3 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                Default source card:
              </p>
              <SourceCard
                index={1}
                docId="815"
                pages="168-168"
                chunkId="844ff052"
                sectionTitle="815 Derivatives and Hedging > 10 Overall > 20 Glossary"
                onShowPdf={() => alert('Show PDF clicked')}
                onValidate={() => alert('Validate clicked')}
              />
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <p className={`text-xs mb-3 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                With validation result (pass):
              </p>
              <SourceCard
                index={2}
                docId="815"
                pages="259-260"
                chunkId="1af2bd3b"
                sectionTitle="815 Derivatives and Hedging > 15 Subtopic 15 > 20 Glossary"
                onShowPdf={() => alert('Show PDF clicked')}
                showValidateButton={false}
                validationState={{
                  status: 'success',
                  result: {
                    verdict: 'pass',
                    score: 0.875,
                    reason: 'The source text directly supports the claim about security definitions.',
                    evidence: 'A security is defined as a share, participation, or other interest...',
                  },
                }}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Sources Accordion */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Sources Accordion
        </h3>
        <Card>
          <CardContent className="p-4">
            <p className={`text-sm mb-4 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
              This is a sample response text that references multiple sources. The sources
              accordion below shows all cited documents with their metadata and actions.
            </p>
            <SourcesAccordion
              sources={sampleSources}
              questionId="sample-question-id"
              defaultExpanded={true}
              onShowPdf={(docId, pageNumber, highlightText) => {
                alert(`Show PDF: Doc ${docId}, Page ${pageNumber}\nHighlight: ${highlightText || 'none'}`)
              }}
              onValidateCitation={async (index) => {
                // Simulate API call
                await new Promise(resolve => setTimeout(resolve, 1000))
                return {
                  verdict: index === 1 ? 'pass' : index === 2 ? 'fail' : 'unsure',
                  score: index === 1 ? 0.92 : index === 2 ? 0.35 : 0.55,
                  reason: index === 1 
                    ? 'Source directly supports the claim.' 
                    : index === 2 
                      ? 'Source does not mention the claimed concept.'
                      : 'Source partially supports but lacks specificity.',
                }
              }}
            />
          </CardContent>
        </Card>
      </div>

      {/* PDF Canvas Viewer */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          PDF Canvas Viewer
        </h3>
        <Card>
          <CardContent className="p-4">
            <p className={`text-xs mb-3 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
              PDF viewer designed for the CanvasPanel. Note: This demo won&apos;t load an actual PDF.
            </p>
            <div className="h-[300px] border border-gray-200 dark:border-dark-border/50 rounded-lg overflow-hidden">
              <div className="h-full flex flex-col bg-gray-50 dark:bg-dark-surface">
                {/* Mock header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-dark-border/50 bg-white dark:bg-dark-surface-2">
                  <div className="flex items-center gap-3">
                    <DocumentTextIcon className="w-5 h-5 text-eliza-red" />
                    <div>
                      <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100">
                        Document 815
                      </h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Page 168-168
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Switch id="demo-highlight" defaultChecked />
                    <Label htmlFor="demo-highlight" className="text-xs text-gray-500">Highlighting</Label>
                  </div>
                </div>
                {/* Mock content */}
                <div className="flex-1 flex items-center justify-center">
                  <div className="text-center">
                    <DocumentTextIcon className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-2" />
                    <p className={`text-sm ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                      PDF content would render here
                    </p>
                    <p className={`text-xs mt-1 ${darkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                      Supports PDF.js highlighting or iframe fallback
                    </p>
                  </div>
                </div>
                {/* Mock footer */}
                <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 dark:border-dark-border/50 bg-white dark:bg-dark-surface-2">
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    PDF.js viewer (highlighting enabled)
                  </p>
                  <a className="text-xs text-eliza-red hover:underline flex items-center gap-1">
                    Open in new tab ↗
                  </a>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

/* ============================================
   CHART COMPONENTS SECTION
   ============================================ */

function ChartComponentsSection({ darkMode }: { darkMode: boolean }) {
  // Sample data for chart demos
  const sampleBarData = {
    columns: ['month', 'claims', 'amount'],
    rows: [
      ['Jan', 45, 125000],
      ['Feb', 52, 145000],
      ['Mar', 38, 98000],
      ['Apr', 61, 178000],
      ['May', 49, 132000],
      ['Jun', 55, 156000],
    ],
  }

  const sampleLineData = {
    columns: ['date', 'auto_claims', 'property_claims'],
    rows: [
      ['2024-01-01', 120, 85],
      ['2024-02-01', 135, 92],
      ['2024-03-01', 148, 78],
      ['2024-04-01', 142, 105],
      ['2024-05-01', 155, 98],
      ['2024-06-01', 168, 112],
    ],
  }

  const samplePieData = {
    columns: ['category', 'count'],
    rows: [
      ['Auto', 245],
      ['Property', 189],
      ['Liability', 134],
      ['Workers Comp', 87],
      ['Other', 45],
    ],
  }

  return (
    <div className="space-y-8">
      {/* Bar Chart */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Bar Chart
        </h3>
        <Card>
          <CardContent className="p-0">
            <div className="h-[400px]">
              <ChartCanvasViewer
                suggestion={{
                  chart_type: 'bar',
                  x_axis: 'month',
                  y_axis: 'claims',
                  title: 'Monthly Claims Count',
                }}
                data={sampleBarData}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Line Chart */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Line Chart (Multi-Series)
        </h3>
        <Card>
          <CardContent className="p-0">
            <div className="h-[400px]">
              <ChartCanvasViewer
                suggestion={{
                  chart_type: 'line',
                  x_axis: 'date',
                  y_axis: ['auto_claims', 'property_claims'],
                  title: 'Claims Trend by Type',
                }}
                data={sampleLineData}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pie Chart */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Pie Chart
        </h3>
        <Card>
          <CardContent className="p-0">
            <div className="h-[400px]">
              <ChartCanvasViewer
                suggestion={{
                  chart_type: 'pie',
                  label: 'category',
                  value: 'count',
                  title: 'Claims by Category',
                }}
                data={samplePieData}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Usage Info */}
      <div>
        <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
          Usage
        </h3>
        <Card>
          <CardContent className="p-6">
            <p className={`text-sm mb-4 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
              Charts are displayed in the CanvasPanel using the ArtifactButton component.
              The chart type, axes, and data are configured via the suggestion and data props.
            </p>
            <pre className={`text-xs p-4 rounded-lg overflow-x-auto ${darkMode ? 'bg-dark-surface-2 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
{`<ArtifactButton
  artifactType="chart"
  title="Monthly Claims"
  description="6 data points"
  canvasContent={
    <ChartCanvasViewer
      suggestion={{
        chart_type: 'bar',
        x_axis: 'month',
        y_axis: 'claims',
        title: 'Monthly Claims Count',
      }}
      data={chartData}
    />
  }
/>`}
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

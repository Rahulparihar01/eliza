# Eliza Forge Design System

> **Purpose:** Comprehensive guide to the Eliza Forge design system components, tokens, and migration patterns. Reference this before creating or modifying any frontend UI component.

---

## Quick Reference

```tsx
// ✅ CORRECT: Standard page layout pattern
import { Page, PageHeader, PageBody } from '../../components/ui';

<Page maxWidth="xl">
  <PageHeader
    title="Page Title"
    description="Optional description text"
    actions={<Button>Primary Action</Button>}
  />
  <PageBody>
    {/* Page content here - automatically aligned with header */}
  </PageBody>
</Page>
```

---

## Overview

The Eliza Forge design system provides a consistent set of components, tokens, and patterns for building frontend pages. All new pages must use design system components. The Component Showcase at `/design-system` serves as a living style guide.

**Key principles:**
- Use DS primitives (Button, Input, etc.) instead of raw HTML elements
- Use semantic color tokens instead of arbitrary Tailwind colors
- Monochromatic icons by default; accent color for emphasis only
- Every new component must be added to the Component Showcase

---

## Typography

### Font Families

| Token | Font | Usage |
|-------|------|-------|
| `font-title` | Libre Baskerville | Page titles, hero headings |
| `font-subtitle` | Hedvig Letters Serif | Section headers, card titles |
| `font-sans` | Inter | Body text, labels, UI elements |
| `font-mono` | JetBrains Mono | Code, data, technical content |

### Font Sizes

| Token | Size | Usage |
|-------|------|-------|
| `text-display` | 3.0rem (48px) | Hero sections, landing pages |
| `text-h1` | 1.875rem (30px) | Page titles |
| `text-h2` | 1.5rem (24px) | Section headers |
| `text-h3` | 1.25rem (20px) | Card titles, subsections |
| `text-body` | 1.0rem (16px) | Body text, paragraphs |
| `text-small` | 0.875rem (14px) | Labels, secondary text |
| `text-micro` | 0.75rem (12px) | Captions, hints, badges |
| `text-data` | 0.875rem (14px) | Table data, metrics |
| `text-code` | 0.8125rem (13px) | Inline code |

### Usage Examples

```tsx
// Page title - uses Libre Baskerville
<h1 className="font-title text-h1 text-charcoal dark:text-gray-100">
  Page Title
</h1>

// Section header - uses Hedvig Letters Serif  
<h2 className="font-subtitle text-h2 text-charcoal dark:text-gray-100">
  Section Header
</h2>

// Body text - uses Inter (default)
<p className="text-body text-charcoal dark:text-gray-100">
  Body text content...
</p>

// Muted/secondary text
<p className="text-small text-gray-500 dark:text-gray-400">
  Secondary information...
</p>
```

---

## Colors

### Brand Colors

| Token | Usage |
|-------|-------|
| `eliza-red` | Primary brand color, CTAs, active states |
| `eliza-red-light` | Hover states |
| `eliza-red-coral` | Accent highlights |

### Text Colors

| Token | Usage |
|-------|-------|
| `text-charcoal dark:text-gray-100` | Primary text |
| `text-gray-500 dark:text-gray-400` | Secondary/muted text |
| `text-gray-400 dark:text-gray-500` | Placeholder text |

### Surface Colors (Light Mode)

| Token | Usage |
|-------|-------|
| `bg-white` | Primary surface (cards, panels) |
| `bg-gray-50` | Page background, secondary surface |
| `bg-gray-100` | Tertiary surface, hover states |

### Surface Colors (Dark Mode)

| Token | Usage |
|-------|-------|
| `dark:bg-dark-bg` | Page background |
| `dark:bg-dark-surface` | Primary surface (cards, panels) |
| `dark:bg-dark-surface-2` | Secondary surface, hover states |

### Border Colors

| Token | Usage |
|-------|-------|
| `border-gray-200 dark:border-dark-border` | Default borders |
| `border-gray-300 dark:border-dark-border` | Input borders |

### Migration from Legacy Colors

| Legacy Class | New Class |
|--------------|-----------|
| `text-text` | `text-charcoal dark:text-gray-100` |
| `text-muted` | `text-gray-500 dark:text-gray-400` |
| `bg-bg` | `bg-gray-50 dark:bg-dark-bg` |
| `bg-surface` | `bg-white dark:bg-dark-surface` |
| `bg-surface-2` | `bg-gray-50 dark:bg-dark-surface-2` |
| `border-border` | `border-gray-200 dark:border-dark-border` |
| `text-brand` | `text-eliza-red` |

---

## Icons

### Icon Guidelines

#### 1. Monochromatic Icons (Preferred)

Most icons should be monochromatic, matching the text they accompany:

```tsx
// Default icon - matches text color
<CpuChipIcon className="h-5 w-5 text-gray-500 dark:text-gray-400" />

// Icon next to primary text
<ChartBarIcon className="h-5 w-5 text-charcoal dark:text-gray-100" />

// Muted icon
<InformationCircleIcon className="h-4 w-4 text-gray-400 dark:text-gray-500" />
```

#### 2. Accent Color Icons

Use the primary accent color (`eliza-red`) for:
- Action indicators
- Active/selected states
- Important callouts

```tsx
// Accent icon for emphasis
<ChartBarIcon className="h-5 w-5 text-eliza-red" />

// Active state
<CheckIcon className="h-5 w-5 text-eliza-red" />
```

#### 3. Semantic Icons (Status Only)

Use semantic colors ONLY for status indicators:

```tsx
// Success state
<CheckIcon className="h-5 w-5 text-green-500" />

// Error state
<ExclamationTriangleIcon className="h-5 w-5 text-red-500" />

// Warning state
<ExclamationCircleIcon className="h-5 w-5 text-amber-500" />
```

#### Avoid Arbitrary Brand Colors

```tsx
// ❌ BAD: Brand-specific colors
<div className="text-green-500 bg-green-500/10">
  <CpuChipIcon className="h-5 w-5" />
</div>

// ✅ GOOD: Consistent neutral or accent
<div className="text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2">
  <CpuChipIcon className="h-5 w-5" />
</div>

// ✅ GOOD: Primary accent when emphasis needed
<div className="text-eliza-red bg-eliza-red/10">
  <CpuChipIcon className="h-5 w-5" />
</div>
```

### Icon Sizes

| Size | Class | Usage |
|------|-------|-------|
| XS | `h-3 w-3` | Inline badges, chips |
| SM | `h-4 w-4` | Buttons, inline actions |
| MD | `h-5 w-5` | Section headers, list items |
| LG | `h-6 w-6` | Feature icons, cards |
| XL | `h-8 w-8` | Hero icons, empty states |
| 2XL | `h-12 w-12` | Large empty states |

---

## Components

### Page Layout Components

#### Layout Types: Centered vs Full-Width

The `Page` component supports **two layout types** via the `layout` prop:

| Layout Type | Prop Value | When to Use | Examples |
|-------------|------------|-------------|----------|
| **Centered** | `layout="centered"` (default) | Admin pages, list views, settings | Users & Roles, Search Templates |
| **Full-Width** | `layout="full-width"` | Productivity spaces, split panels | Search Results, Email Composer |

**Centered Layout (Default):**
- Content constrained to `maxWidth` and centered on page
- Looks elegant on large monitors
- Best for configuration, admin, and list-style pages

```tsx
// Centered layout - for Admin/Settings/List pages
<Page layout="centered" maxWidth="2xl">
  <PageHeader title="Search Templates" />
  <PageBody>
    <DataTable ... />
  </PageBody>
</Page>
```

**Full-Width Layout:**
- Content uses full available width (with padding)
- `Page` uses `flex flex-col` for proper height handling
- Best for productivity workspaces with split panels

```tsx
// Full-width layout - for Productivity Spaces
<Page layout="full-width">
  <PageHeader title="Search Results" />
  
  {/* Filter Bar */}
  <div className="flex-shrink-0 px-8 py-3 border-b ...">
    {/* Filters */}
  </div>
  
  {/* Split Panel - uses full width */}
  <div className="flex flex-1 min-h-0">
    <div className="w-2/5 border-r">List Panel</div>
    <div className="flex-1">Detail Panel</div>
  </div>
</Page>
```

**PageBody Props for Full-Width Layouts:**

| Prop | Default | Description |
|------|---------|-------------|
| `fill` | `false` | When `true`, adds `flex-1 min-h-0` for split panels |
| `padded` | `true` | When `false`, removes padding for edge-to-edge content |

```tsx
// Full-width with split panels
<Page layout="full-width">
  <PageHeader title="Workspace" />
  <PageBody fill padded={false}>
    <div className="flex flex-1">
      <div className="w-1/3 border-r">Sidebar</div>
      <div className="flex-1">Main Content</div>
    </div>
  </PageBody>
</Page>
```

**Decision Guide:**
- **Is the user configuring or managing?** → Use `layout="centered"`
- **Is the user actively working/producing?** → Use `layout="full-width"`
- **Does the page have a split panel?** → Use `layout="full-width"`
- **Is it a list/table of items to manage?** → Use `layout="centered"`

#### Page Container

**ALWAYS use the `Page` wrapper for all page layouts.** It ensures consistent structure and handles both centered and full-width layouts via the `layout` prop.

```tsx
import { Page, PageHeader, PageBody } from '../../components/ui';

<Page maxWidth="xl">
  <PageHeader
    title="Page Title"           // Uses font-title
    description="Optional description text"
    breadcrumb={<Breadcrumb />}  // Optional
    actions={<Button>Action</Button>}  // Optional
    bordered={false}             // Default: no border (cleaner look)
  />
  <PageBody>
    {/* Page content here - automatically aligned with header */}
  </PageBody>
</Page>
```

**Why use Page wrapper?** The `Page` component creates a single container that wraps both the header and body, ensuring they share the same max-width and are perfectly aligned. This creates a clean "invisible line" that anchors the entire page layout.

#### Primary Action Button Placement

Primary action buttons (e.g., "Create", "Add", "Invite") should be placed in the `PageHeader.actions` prop, positioned in the top-right of the page header. Use the default (primary) button style.

```tsx
<Page maxWidth="xl">
  <PageHeader
    title="Users & Roles"
    description="Manage user accounts and permissions"
    actions={
      <Button onClick={handleCreate}>
        <PlusIcon className="w-4 h-4 mr-2" />
        Create User
      </Button>
    }
  />
  <PageBody>
    {/* Search, filters, and content go here - NOT the primary action */}
  </PageBody>
</Page>
```

**Guidelines:**
- **One primary action** per page header (use the default `Button` variant)
- **Secondary actions** can be added alongside (use `variant="outline"`)
- **Search and filters** belong in `PageBody`, not in the header
- **Permission gating**: Wrap action buttons in permission checks if needed

```tsx
// Multiple actions example
actions={
  <>
    <Button variant="outline" onClick={handleExport}>
      <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
      Export
    </Button>
    <Button onClick={handleCreate}>
      <PlusIcon className="w-4 h-4 mr-2" />
      Create
    </Button>
  </>
}

// Permission-gated action
actions={canCreate ? <Button>Create</Button> : null}
```

#### Max Width Options

| Value | CSS Class | Description |
|-------|-----------|-------------|
| `sm` | `max-w-2xl` | Small content areas |
| `md` | `max-w-4xl` | Medium content areas |
| `lg` | `max-w-5xl` | Large content areas |
| `xl` | `max-w-6xl` | Extra large (recommended for dashboards) |
| `2xl` | `max-w-[1600px]` | Default, very wide |
| `full` | `max-w-full` | Full width |

#### Page Variants

```tsx
// Default: gray background
<Page maxWidth="xl">...</Page>

// Plain: white background  
<Page maxWidth="xl" variant="plain">...</Page>
```

#### Legacy Pattern (Still Supported)

If you need standalone components without alignment guarantee:

```tsx
import { PageHeader, PageContent } from '../../components/ui';

<PageHeader
  title="Page Title"
  maxWidth="xl"  // Must match PageContent!
/>
<PageContent maxWidth="xl">
  {/* Page content here */}
</PageContent>
```

**Note:** When using this pattern, you must manually ensure `maxWidth` matches between `PageHeader` and `PageContent`.

#### SectionHeader

Use for section titles within a page:

```tsx
import { SectionHeader } from '../../components/ui';

<SectionHeader
  title="Section Title"        // Uses font-subtitle
  description="Optional description"
  icon={<CpuChipIcon className="h-5 w-5" />}  // Optional
  actions={<Button>Action</Button>}  // Optional
/>
```

### Application Layout (Gemini-Style)

The application uses a **Gemini-style layout** where the sidebar and toolbar are arranged in columns, not stacked rows:

```
┌──────────────┬───────────────────────────────────────────────┐
│     [≡]      │ elizaforge for Eliza Platform ⭐ ▼      🔔 👤 │ ← Toolbar
├──────────────┼───────────────────────────────────────────────┤
│  FAVORITES   │                                               │
│    Home      │              Main Content                     │
│  AI RECRUITER│                                               │
│    ...       │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

**Key Benefits:**
- Toggle button is always in the **top-left corner** (discoverable, consistent)
- Sidebar header and Toolbar are at the **same height** (`h-12`)
- Clean visual columns - sidebar and content perfectly aligned
- Familiar pattern (Google Gemini, Gmail, Drive)

**Implementation in Layout.tsx:**
```tsx
<div className="flex-1 flex overflow-hidden">
  {/* Sidebar column - full height with its own header */}
  <Navigation mode={sidebarMode} onToggle={toggleSidebar} />
  
  {/* Right column - Toolbar + Content */}
  <div className="flex-1 flex flex-col">
    <Header />  {/* Toolbar only spans content area */}
    <main>{children}</main>
  </div>
</div>
```

### Toolbar

The top application bar with the DS TenantSwitcher (elizaforge branding) as the first element and global actions on the right. **Only spans the content area** (not full width).

**Location:** `frontend/src/components/ui/toolbar.tsx`, `frontend/src/components/layout/Header.tsx`

```tsx
import {
  Toolbar,
  ToolbarSection,
  ToolbarDivider,
  ToolbarItem,
  ToolbarTextButton,
} from '../ui/toolbar';
import { TenantSwitcher } from '../ui/tenant-switcher';

<Toolbar
  leftContent={
    <TenantSwitcher
      tenants={tenants}
      currentTenant={currentTenant}
      onTenantChange={handleTenantChange}
      onSetDefault={handleSetDefault}
    />
  }
  rightContent={
    <ToolbarSection>
      <ToolbarItem 
        icon={<BellIcon className="h-5 w-5" />} 
        badge={3} 
        tooltip="Notifications" 
      />
      <ToolbarDivider />
      <ToolbarTextButton icon={<ChatBubbleLeftRightIcon className="h-4 w-4" />}>
        Help / Feedback
      </ToolbarTextButton>
    </ToolbarSection>
  }
/>
```

**TenantSwitcher Branding:**

The DS TenantSwitcher displays the elizaforge logo with the organization name:

> **eliza***forge* for **Organization Name** ⭐ ▼

When clicked, shows a dropdown to switch between tenants with:
- Organization list with building icons
- Star button to set default tenant
- Checkmark for current selection

**Components:**

| Component | Description | Uses DS Components |
|-----------|-------------|-------------------|
| `Toolbar` | Container with left, center (optional), and right sections | Layout container |
| `ToolbarSection` | Groups toolbar items together | Flex container |
| `ToolbarDivider` | Vertical separator between items | Styled div |
| `ToolbarItem` | Icon button with badge and tooltip | **DS `Button` (ghost) + `Tooltip`** |
| `ToolbarTextButton` | Text button with optional icon | **DS `Button` (ghost)** |
| `TenantSwitcher` | Multi-tenant org selector with elizaforge branding | DS component |

**Key Design Decisions:**
- **elizaforge branding in TenantSwitcher** - Shows `eliza`*`forge` for [Org Name]
- **No separate logo icon** - The tenant switcher IS the branding
- **Uses DS Button** - `ToolbarItem` and `ToolbarTextButton` use `Button variant="ghost"`
- **Header fully migrated** - `Header.tsx` now uses all DS Toolbar components

### Sidebar Components

The Design System provides three sidebar variants for different navigation contexts.

**Location:** `frontend/src/components/ui/sidebar.tsx`, `sidebar-submenu.tsx`, `sidebar-context-panel.tsx`

#### 1. Main Sidebar (Collapsible)

The primary navigation sidebar. The elizaforge branding has moved to the Toolbar's TenantSwitcher.

```tsx
import {
  Sidebar,
  SidebarContent,
  SidebarSection,
  SidebarItem,
  SidebarFooter,
} from '../../components/ui';

<Sidebar mode="expanded">  {/* 'expanded' | 'collapsed' | 'hidden' */}
  <SidebarContent>
    <SidebarSection title="FAVORITES">
      <SidebarItem icon={<HomeIcon />} isActive>Home</SidebarItem>
    </SidebarSection>
    <SidebarSection title="AI RECRUITER">
      <SidebarItem icon={<SearchIcon />}>Talent Search</SidebarItem>
      <SidebarItem icon={<UsersIcon />}>Search Results</SidebarItem>
    </SidebarSection>
    <SidebarSection title="LABS">
      <SidebarItem icon={<DocumentTextIcon />}>Resume Parsing Test</SidebarItem>
    </SidebarSection>
  </SidebarContent>
  <SidebarFooter>
    <span>Eliza Forge v1.0</span>
  </SidebarFooter>
</Sidebar>
```

**Note:** The sidebar no longer includes a user info header - this was removed to save vertical space. User information is accessible via the user menu in the Toolbar.

**Sidebar Modes:**

| Mode | Width | Description |
|------|-------|-------------|
| `expanded` | 256px | Full width with labels (default) |
| `collapsed` | 64px | Icon-only with tooltips |
| `hidden` | 0px | Completely hidden (for contextual navigation) |

#### 2. SidebarSubmenu (Contextual Navigation)

A simplified sidebar for workspace/sub-app navigation. Features a simple back button header (non-collapsible by design).

```
┌─────────────────────────────────┐
│  ← Back                         │  ← Simple back button, h-12 height
├─────────────────────────────────┤
│  TENANT MANAGEMENT              │
│    🏢 Tenants                   │
│    ✓  Feature Allocation        │
│    📊 Adoption Access           │
├─────────────────────────────────┤
│  • Eliza Forge v1.0             │
└─────────────────────────────────┘
```

```tsx
import { SidebarSubmenu, SubmenuItem } from '../../components/ui';

const items: SubmenuItem[] = [
  { label: 'Tenants', path: '/platform-admin/tenants', icon: BuildingOffice2Icon },
  { label: 'Feature Allocation', path: '/platform-admin/features', icon: CheckCircleIcon },
  { label: 'Adoption Access', path: '/platform-admin/adoption', icon: ChartBarIcon },
];

<SidebarSubmenu
  title="Tenant Management"
  items={items}
  onBack={() => clearSection()}
  isVisible={true}
  showFooter={true}
/>
```

**Key Features:**
- **Simple back button** - `← Back` in header, returns to main sidebar
- **Header matches Toolbar height** - `h-12` for visual alignment
- **Non-collapsible** - Keeps UI simple; collapse main sidebar if more space needed
- **Section title** - Displayed as uppercase label below header
- **Keyboard support** - Press `Escape` to go back

**Design Decision - No Collapse:**
The submenu is for temporary workspace navigation. Users who need more screen space can:
1. Go back to main sidebar and collapse there
2. Navigate to a different section

This keeps the mental model simple: one back button, one action.

**Components:**

| Component | Description |
|-----------|-------------|
| `SidebarSubmenu` | Complete submenu with back button, title, items, footer |
| `SubmenuNavItem` | Individual navigation link using `NavLink` |

#### 3. SidebarContextPanel (Wrapper)

A thin wrapper around `SidebarSubmenu` for use with `NavigationContext`. This is what `Layout.tsx` renders.

```tsx
import { SidebarContextPanel, ContextPanelItem } from '../../components/ui';

<SidebarContextPanel
  title={sectionConfig.title}
  icon={sectionConfig.icon}
  items={sectionConfig.items}
  onBack={clearSection}
  isVisible={!!activeSection}
/>
```

### Form Components

| Component | Usage |
|-----------|-------|
| `Button` | All buttons (variant: default, ghost, outline, secondary, danger, link) |
| `Input` | Text inputs (variant: default, ghost, ghost-lg) |
| `Select` / `SelectOption` | Dropdowns (uses `onValueChange`, not `onChange`) |
| `Checkbox` | Multi-select (uses `onChange` with `e.target.checked`) |
| `Switch` | Toggle settings (uses `onCheckedChange`) |
| `Label` | Form labels |
| `Textarea` | Multi-line text |

#### Input Variants

The `Input` component supports multiple variants for different use cases:

| Variant | Usage |
|---------|-------|
| `default` | Standard input with border and background (default) |
| `ghost` | Minimal input with transparent background, subtle bottom border on hover/focus |
| `ghost-lg` | Large ghost variant with semibold font for inline titles |

```tsx
// Default - standard bordered input
<Input placeholder="Enter email..." />

// Ghost - minimal, transparent, shows subtle border on hover/focus
<Input variant="ghost" placeholder="Add a description..." />

// Ghost Large - for inline editable titles
<Input variant="ghost-lg" placeholder="Untitled" />
```

**When to use ghost variants:**
- Inline editing of titles or names (ghost-lg)
- Minimal forms where borders feel heavy
- Linear/Notion-style interfaces
- Secondary inputs that shouldn't compete visually with primary content

### Feedback Components

| Component | Usage |
|-----------|-------|
| `Alert` | Inline messages (variant: info, success, warning, error) |
| `Badge` | Status indicators (variant: default, brand, success, warning, danger, info) |
| `Spinner` | Loading states |
| `Modal` | Dialogs and overlays |
| `ModalFloatingActions` | Floating action buttons with gradient backdrop for workspace-style modals |
| `Sheet` | Slide-in panels from edge of screen (side: left, right, top, bottom) |

#### Sheet (Slide-in Panel)

Use **Sheet** for slide-in panels from the edge of the screen. Similar to Modal but slides in from a side rather than appearing centered.

```tsx
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
} from '../../components/ui';

<Sheet open={isOpen} onClose={() => setIsOpen(false)}>
  <SheetContent side="right" size="md" topOffset={48}>
    <SheetHeader>
      <SheetTitle>Panel Title</SheetTitle>
      <SheetDescription>Optional description</SheetDescription>
    </SheetHeader>
    <SheetBody>
      {/* Scrollable content */}
    </SheetBody>
    <SheetFooter>
      {/* Footer actions */}
    </SheetFooter>
  </SheetContent>
</Sheet>
```

**SheetContent Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `side` | `'left' \| 'right' \| 'top' \| 'bottom'` | `'right'` | Edge to slide in from |
| `size` | `'sm' \| 'md' \| 'lg' \| 'xl' \| 'full'` | `'md'` | Width (horizontal) or height (vertical) |
| `topOffset` | `number` | `0` | Top offset in pixels (e.g., 48 for header height) |

**Sheet Sub-components:**

| Component | Description |
|-----------|-------------|
| `Sheet` | Root context provider (handles open state, escape key, body scroll lock) |
| `SheetContent` | Sliding container with backdrop |
| `SheetHeader` | Header with close button |
| `SheetTitle` | Title text (font-semibold, text-lg) |
| `SheetDescription` | Description text (text-xs, muted) |
| `SheetBody` | Scrollable content area |
| `SheetFooter` | Footer with border and gray background |

**When to use Sheet vs Modal:**
- **Sheet:** Secondary content, forms, detail views that don't need full attention
- **Modal:** Focused interactions requiring immediate attention (confirmations, critical forms)

#### ModalFloatingActions (Floating Action Bar)

Use **ModalFloatingActions** for workspace-style modals where you want floating action buttons at the bottom with a subtle gradient backdrop. This creates a more open feel by removing the traditional modal footer.

```tsx
import { ModalFloatingActions } from '../../components/ui';

<ModalContent className="relative">
  <ModalHeader>...</ModalHeader>
  <ModalBody>...</ModalBody>
  
  {/* Floating actions at bottom-right */}
  <ModalFloatingActions>
    <Button variant="outline">Save</Button>
    <Button>Save & Run</Button>
  </ModalFloatingActions>
</ModalContent>
```

**ModalFloatingActions Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `position` | `'bottom-right' \| 'bottom-center' \| 'bottom-left'` | `'bottom-right'` | Position of the action buttons |
| `showGradient` | `boolean` | `true` | Whether to show the gradient backdrop |
| `gradientHeight` | `'sm' \| 'md' \| 'lg'` | `'md'` | Height of the gradient fade area |

**When to use:**
- Workspace-style modals with sidebar navigation
- Large configuration modals
- When you want to maximize content area

**Note:** The parent container (e.g., `ModalContent`) must have `position: relative` for the floating actions to position correctly.

### Data Components

| Component | Usage |
|-----------|-------|
| `DataTable` | Standard tables with sorting, pagination, selection, expandable rows |
| `Card` | Elevated content containers with shadow (use for emphasis) |
| `Panel` | Flat containers without shadow (use for admin interfaces, data tables) |
| `Skeleton` | Loading placeholders |

#### Card vs Panel

Use **Card** when content needs visual emphasis (elevated, with shadow):
- Hero sections, feature highlights
- Content that should "pop" from the page

Use **Panel** for functional UI containers (flat, no shadow):
- Admin interfaces, settings pages
- Data tables, lists
- Forms and configuration sections

```tsx
// Card - elevated with shadow
<Card>
  <CardHeader>
    <CardTitle>Featured Content</CardTitle>
  </CardHeader>
  <CardContent>...</CardContent>
</Card>

// Panel - flat without shadow
<Panel>
  <PanelHeader>
    <PanelTitle>Active Grants</PanelTitle>
    <PanelDescription>2 grants configured</PanelDescription>
  </PanelHeader>
  <PanelBody>...</PanelBody>
  <PanelFooter>...</PanelFooter>
</Panel>
```

**Panel Sub-components:**

| Component | Description |
|-----------|-------------|
| `Panel` | Container with border and rounded corners (no shadow) |
| `PanelHeader` | Top section with bottom border |
| `PanelTitle` | Header title (font-subtitle, text-h3) |
| `PanelDescription` | Header description text |
| `PanelBody` | Main content area with padding |
| `PanelFooter` | Bottom section with gray background |

### Citation Components (RAG/Document Sources)

Components for displaying citations and sources in RAG (Retrieval-Augmented Generation) responses.

| Component | Usage |
|-----------|-------|
| `InlineCitation` | Clickable inline citation badge (opens PDF in canvas) |
| `CitationGroup` | Wrapper for multiple adjacent inline citations |
| `SourceCard` | Full source display with metadata and validation |
| `SourcesAccordion` | Collapsible sources section with all source cards |
| `PdfCanvasViewer` | PDF viewer designed for the CanvasPanel |
| `ChartCanvasViewer` | Chart viewer (bar, line, pie) for the CanvasPanel |

#### InlineCitation

Clickable inline citation badge that opens the source PDF in the canvas panel.

```tsx
import { InlineCitation, CitationGroup } from '../../components/ui';

// Single citation
<InlineCitation
  number={1}
  docId="815"
  pageNumber="168"
  sectionTitle="815 Derivatives > Glossary"
  onClick={() => openPdfInCanvas()}
/>

// Multiple adjacent citations
<CitationGroup>
  <InlineCitation number={1} />
  <InlineCitation number={2} />
  <InlineCitation number={3} />
</CitationGroup>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `number` | `number` | Citation number (required) |
| `docId` | `string` | Document ID for PDF loading |
| `pageNumber` | `string` | Page number or range |
| `highlightText` | `string` | Text to highlight in PDF |
| `sectionTitle` | `string` | Section title for tooltip |
| `size` | `'sm' \| 'md'` | Size variant (default: 'sm') |
| `interactive` | `boolean` | Whether clickable (default: true) |
| `onClick` | `() => void` | Click handler |

#### SourceCard

Individual source display with full metadata and action buttons.

```tsx
import { SourceCard } from '../../components/ui';

<SourceCard
  index={1}
  docId="815"
  pages="168-168"
  chunkId="844ff052"
  sectionTitle="815 Derivatives and Hedging > 10 Overall > 20 Glossary"
  onShowPdf={() => openPdfInCanvas()}
  onValidate={() => validateCitation()}
  validationState={{ status: 'success', result: { verdict: 'pass', score: 0.87 } }}
/>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `index` | `number` | Source index number (required) |
| `docId` | `string` | Document ID |
| `pages` | `string` | Page range |
| `chunkId` | `string` | Chunk ID (auto-truncated to 8 chars) |
| `sectionTitle` | `string` | Section title/path |
| `onShowPdf` | `() => void` | Callback for Show PDF button |
| `onValidate` | `() => void` | Callback for Validate button |
| `validationState` | `CitationValidationState` | Current validation state |

#### SourcesAccordion

Collapsible accordion for displaying multiple sources.

```tsx
import { SourcesAccordion } from '../../components/ui';

<SourcesAccordion
  sources={[
    { index: 1, docId: '815', pages: '168', chunkId: '844ff052', sectionTitle: '...' },
    { index: 2, docId: '260', pages: '12', chunkId: 'abc123', sectionTitle: '...' },
  ]}
  questionId="question-123"
  onShowPdf={(docId, pageNumber, highlightText) => openPdfInCanvas()}
  onValidateCitation={async (index) => validateCitation(index)}
  defaultExpanded={false}
/>
```

**Helper Functions:**

```tsx
import { parseSourcesFromSummary, parseCitation } from '../../components/ui';

// Parse sources from summary text with "Sources:" section
const { mainContent, sources } = parseSourcesFromSummary(summary);

// Parse individual citation string into structured data
const source = parseCitation("doc:815 pages:168-168 chunk:844ff052 section:...");
// Returns: { docId, pages, chunkId, sectionTitle }
```

#### PdfCanvasViewer

PDF viewer component designed for the CanvasPanel. The highlighting toggle appears in the CanvasPanel header via context.

```tsx
import { PdfCanvasViewer } from '../../components/ui';
import { useChat } from '../../components/ui';

// Open PDF in canvas panel
const { setCanvasTitle, setCanvasContent, setCanvasOpen } = useChat();

setCanvasTitle(`Document 815 - Page 168`);
setCanvasContent(
  <PdfCanvasViewer
    docId="815"
    pageNumber="168"
    highlightText="security is defined as"
  />
);
setCanvasOpen(true);
```

**Features:**
- Toggle between PDF.js (with highlighting) and iframe fallback
- Highlighting toggle appears in CanvasPanel header (via `canvasHeaderActions` context)
- Loading state with spinner
- Footer with "Open in new tab" link
- Proper dark/light mode support

### Chart Components

| Component | Purpose |
|-----------|---------|
| `ChartCanvasViewer` | Chart viewer for the CanvasPanel (bar, line, pie) |
| `ChartThumbnail` | Clickable thumbnail for opening charts in canvas |

#### ChartCanvasViewer

Chart viewer component designed for the CanvasPanel. Supports bar, line, and pie charts with DS theming.

```tsx
import { ChartCanvasViewer } from '../../components/ui';
import { ArtifactButton } from '../../components/ui';

// Open chart in canvas panel via ArtifactButton
<ArtifactButton
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
      data={{
        columns: ['month', 'claims'],
        rows: [['Jan', 45], ['Feb', 52], ['Mar', 38]],
      }}
    />
  }
/>
```

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `suggestion` | `ChartSuggestion` | Chart configuration (type, axes, title) |
| `data` | `ChartData` | Data with columns and rows arrays |
| `title` | `string` | Optional title override |

**Supported Chart Types:**
- `bar` - Vertical bar charts with rounded corners
- `line` - Line charts with dots and multi-series support
- `pie` - Pie charts with percentage labels

**Features:**
- DS-aligned color palette (charcoal primary, vibrant for multi-series)
- Responsive sizing within CanvasPanel
- Smart axis formatting (dates, numbers)
- Tooltip with dark theme styling
- Header with chart info and data point count
- Footer with axis information
- Proper dark/light mode support

---

## Critical Rules

### Rule 1: Use DS Primitives in New Components

**Context:** Custom styled HTML elements create visual inconsistency and miss dark mode, accessibility, and theming support that DS components provide.

```tsx
// ❌ WRONG: Custom button styling
<button className="px-4 py-2 rounded-lg bg-gray-100 hover:bg-gray-200">
  Click me
</button>

// ✅ CORRECT: Use DS Button
import { Button } from './button';
<Button variant="ghost" size="sm">
  Click me
</Button>
```

**DS primitives to use:**
- `Button` - For all clickable actions
- `Input`, `Textarea`, `Select` - For form inputs
- `Tooltip` - For hover hints
- `Badge` - For status indicators
- `Spinner` - For loading states
- `Sidebar*` - For navigation layouts

### Rule 2: Every Component Must Be on the Showcase

**Context:** The Component Showcase (`/design-system`) ensures discoverability, visual regression testing, and living documentation. Unshowcased components get forgotten and duplicated.

Steps when creating a new UI component:
1. Create the component in `/frontend/src/components/ui/`
2. Export from index in `/frontend/src/components/ui/index.ts`
3. Add to Showcase in `/frontend/src/pages/design-system/ComponentShowcase.tsx`
4. Document in this guide under the appropriate section

### Rule 3: Do Not Create Custom Layouts Outside Page

**Context:** The `Page` component handles centered and full-width layouts with consistent padding, max-width, and alignment. Custom flex containers break this consistency.

```tsx
// ❌ WRONG: Custom layout wrapper
<div className="max-w-6xl mx-auto p-6">
  <h1 className="text-2xl font-bold">Title</h1>
  {/* content */}
</div>

// ✅ CORRECT: Use Page wrapper
<Page maxWidth="xl">
  <PageHeader title="Title" />
  <PageBody>{/* content */}</PageBody>
</Page>
```

---

## Patterns

### Migration: Step-by-Step Process

When migrating a page to the design system:

#### 1. Update Imports

```tsx
import {
  Button,
  Input,
  Select,
  SelectOption,
  Switch,
  Badge,
  Label,
  Alert,
  Spinner,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  Checkbox,
  Page,
  PageHeader,
  PageBody,
  PageContent,  // Legacy - use Page + PageBody instead
  SectionHeader,
} from '../../components/ui';
```

#### 2. Replace Page Structure

```tsx
// Before
<Layout>
  <div className="p-6">
    <h1 className="text-2xl font-bold">Title</h1>
    <p className="text-muted">Description</p>
  </div>
  {/* content */}
</Layout>

// After (Recommended - using Page wrapper for alignment)
<Layout>
  <Page maxWidth="xl">
    <PageHeader
      title="Title"
      description="Description"
    />
    <PageBody>
      {/* content - automatically aligned with header */}
    </PageBody>
  </Page>
</Layout>
```

#### 3. Replace Form Elements

```tsx
// Buttons
<button className="px-4 py-2 bg-blue-500">Save</button>
// → 
<Button>Save</Button>

// Inputs
<input type="text" className="border rounded" />
// →
<Input placeholder="..." />

// Selects (NOTE: different API!)
<select onChange={(e) => setValue(e.target.value)}>
// →
<Select onValueChange={(value) => setValue(value)}>
  <SelectOption value="a">Option A</SelectOption>
</Select>

// Checkboxes
<input type="checkbox" onChange={(e) => setChecked(e.target.checked)} />
// →
<Checkbox onChange={(e) => setChecked(e.target.checked)} />

// Switches
<Switch onCheckedChange={(checked) => setEnabled(checked)} />
```

#### 4. Update Colors

Replace all legacy color classes with new design system colors (see Colors section above).

#### 5. Update Icons

- Make icons monochromatic (gray tones) or use accent color
- Remove brand-specific colors (green for OpenAI, etc.)
- See Icons section above for guidelines

#### 6. Handle Special Cases

**DataTable with Expandable Rows:**
The DataTable component supports expandable rows via the `expandable` prop.

```tsx
<DataTable
  columns={columns}
  data={data}
  getRowId={(row) => row.id}
  expandable
  expandedRows={expandedRows}
  onExpandedChange={(ids) => setExpandedRows(ids)}
  allowMultipleExpanded={false}
  renderExpandedRow={(row) => (
    <div className="p-4">
      {/* Expanded content for this row */}
    </div>
  )}
/>
```

**Expandable Row Props:**

| Prop | Type | Description |
|------|------|-------------|
| `expandable` | `boolean` | Enable expandable rows |
| `renderExpandedRow` | `(row: T) => ReactNode` | Render function for expanded content |
| `expandedRows` | `Set<string \| number>` | Controlled expanded row IDs |
| `onExpandedChange` | `(ids: Set) => void` | Callback when expansion changes |
| `allowMultipleExpanded` | `boolean` | Allow multiple rows expanded (default: true) |
| `defaultExpandedRows` | `Set<string \| number>` | Default expanded IDs (uncontrolled mode) |

### Loading States

```tsx
// Full page loading
if (isLoading) {
  return (
    <Layout>
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    </Layout>
  );
}

// Inline loading
<Button disabled={isSubmitting}>
  {isSubmitting && <Spinner size="sm" className="mr-2" />}
  Save
</Button>
```

### Empty States

```tsx
<div className="text-center py-12">
  <DocumentIcon className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
  <h3 className="mt-4 text-sm font-medium text-charcoal dark:text-gray-100">
    No items found
  </h3>
  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
    Get started by creating a new item.
  </p>
  <Button className="mt-4">
    <PlusIcon className="h-4 w-4 mr-2" />
    Create Item
  </Button>
</div>
```

### Error States

```tsx
<Alert variant="error">
  <ExclamationTriangleIcon className="h-5 w-5" />
  <div>
    <p className="font-medium">Error loading data</p>
    <p className="text-sm opacity-80 mt-1">
      {error.message}
    </p>
  </div>
</Alert>
```

### Contextual Sidebar Navigation

The contextual sidebar pattern provides a Linear/Notion-style navigation experience where clicking a section with children **hides** the main sidebar completely and reveals a contextual sub-navigation panel (full replace, not just collapse).

**Sidebar Modes:**

The sidebar supports three display modes via `SidebarMode`:

| Mode | Width | Description |
|------|-------|-------------|
| `expanded` | 256px | Full width with labels (default) |
| `collapsed` | 64px | Icon-only with tooltips |
| `hidden` | 0px | Completely hidden (for contextual navigation) |

```tsx
import type { SidebarMode } from '../components/ui/sidebar';

// Using the mode
const { sidebarMode, setSidebarMode } = useNavigation();

// Methods available
setSidebarMode('hidden');  // Hide completely
setSidebarMode('expanded'); // Full width
setSidebarMode('collapsed'); // Icons only
```

**Key Components:**
- `NavigationContext` - Manages active section and sidebar mode (`frontend/src/contexts/NavigationContext.tsx`)
- `SidebarContextPanel` - Slide-in panel with sub-items (`frontend/src/components/ui/sidebar-context-panel.tsx`)
- `sectionConfigs` - Section definitions (`frontend/src/components/navigation/sectionConfigs.ts`)
- `SidebarMode` type - Exported from `sidebar.tsx`

**How It Works:**

1. **User clicks a section** (e.g., "Platform Settings") in the main sidebar
2. **Main sidebar hides** completely (width: 0, full replace)
3. **Context panel slides in** showing sub-navigation items
4. **User navigates** by clicking sub-items
5. **Press Esc or click Back** to restore the main sidebar to previous mode

**Adding a New Section:**

```tsx
// 1. Add to ActiveSection type in NavigationContext.tsx
export type ActiveSection = 'admin-settings' | 'platform-settings' | null;

// 2. Add config in sectionConfigs.ts
export const yourSectionConfig: SectionConfig = {
  id: 'your-new-section',
  title: 'Your Section',
  icon: YourIcon,
  basePath: '/your/base/path',
  items: [
    { label: 'Item 1', path: '/your/base/path/item1', icon: Item1Icon },
    { label: 'Item 2', path: '/your/base/path/item2', icon: Item2Icon },
  ],
};

// 3. Add to sectionConfigs map
export const sectionConfigs = {
  ...
  'your-new-section': yourSectionConfig,
};

// 4. Update getSectionFromPath helper
export function getSectionFromPath(path: string): ActiveSection {
  ...
  if (path.startsWith('/your/base/path')) {
    return 'your-new-section';
  }
  ...
}

// 5. Add contextualSection to navigation item
{
  label: 'Your Section',
  path: '/your/base/path',
  icon: 'your-icon',
  contextualSection: 'your-new-section',
}
```

**Keyboard Support:**
- `Escape` - Close context panel and return to main sidebar

---

## Component Showcase

The Component Showcase page (`/design-system`) is a living style guide that displays all design system components in one place.

**Access:** [http://localhost:3000/design-system](http://localhost:3000/design-system)

**Location:** `frontend/src/pages/design-system/ComponentShowcase.tsx`

### Purpose

- Visual reference for all available components
- Interactive examples to test component behavior
- Theme customization preview
- Dark mode testing

### Adding a Component to the Showcase

When adding a component to the showcase:

- [ ] Import the component at the top of `ComponentShowcase.tsx`
- [ ] Add a new `<section>` with consistent styling (see existing sections)
- [ ] Include multiple variants/states (sizes, colors, disabled, etc.)
- [ ] Show both light and dark mode rendering
- [ ] Add any interactive demos if applicable

**Example Section Structure:**

```tsx
<Separator className="my-12" />

{/* Your Component Name */}
<section className="mb-16">
  <h2 className={`font-title text-3xl mb-2 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
    Component Name
  </h2>
  <p className={`font-subtitle mb-6 ${darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
    Brief description of the component's purpose
  </p>

  <div className="space-y-8">
    {/* Variant 1 */}
    <div>
      <h3 className={`font-medium mb-4 ${darkMode ? 'text-white' : 'text-charcoal'}`}>
        Variant Name
      </h3>
      <Card>
        <CardContent className="p-4">
          {/* Your component examples here */}
        </CardContent>
      </Card>
    </div>
  </div>
</section>
```

---

## Page Migration Tracker

Track progress of migrating pages to use design system components.

### Migrated Pages

| Page | Path | Components Used | Date |
|------|------|-----------------|------|
| Admin Settings | `admin/AdminSettingsPage.tsx` | PageHeader, PageContent, SectionHeader, DataTable (expandable), Button, Input, Select, Switch, Badge, Checkbox, Alert, Modal, Spinner | Jan 2026 |
| Admin Management | `platform-admin/settings/AdminManagementPage.tsx` | Page, PageHeader, PageBody, DataTable, DataTableActions, DataTableActionButton, Button, Input, Badge, Avatar, Spinner, Modal | Jan 2026 |
| AI Providers | `platform-admin/settings/AIProvidersPage.tsx` | Page, PageHeader, PageBody, SectionHeader, Button, Input, Select, SelectOption, Checkbox, Label, Badge, Spinner, Modal | Jan 2026 |
| Component Showcase | `design-system/ComponentShowcase.tsx` | All components (reference implementation) | Jan 2026 |
| Adoption Dashboard | `adoption/AdoptionDashboardPage.tsx` | PageHeader, PageContent, Tabs, TabsList, TabsTrigger, Button, Badge, Skeleton, Input, Select, Switch | Jan 2026 |
| Analysis Config | `talent-intelligence/AnalysisConfigPage.tsx` | Page, PageHeader, PageBody, DataTable (expandable), Button, Badge, Alert, Spinner, Progress, Modal | Jan 2026 |
| Workspaces | `domains/DomainsPage.tsx` | Page, PageHeader, PageBody, Card, CardContent, Button, Input, Spinner, DropdownMenu | Feb 2026 |
| Workspace Detail | `domains/DomainDetailPage.tsx` | Page, PageHeader, PageBody, Button, Badge, Spinner, DataTable | Feb 2026 |

### Migrated Components

| Component | Path | DS Components Used | Date |
|-----------|------|-------------------|------|
| Navigation | `layout/Navigation.tsx` | Sidebar, SidebarContent, SidebarSection, SidebarFooter | Jan 2026 |
| Contextual Sidebar | `ui/sidebar-submenu.tsx` | Sidebar, SidebarContent, SidebarSection, SidebarFooter, Button (for back) | Jan 2026 |
| Toolbar Items | `ui/toolbar.tsx` | Button (ghost), Tooltip | Jan 2026 |
| Header | `layout/Header.tsx` | Toolbar, ToolbarSection, ToolbarDivider, ToolbarItem, ToolbarTextButton, TenantSwitcher (DS) | Jan 2026 |
| AdminShell | `layout/AdminShell.tsx` | DS colors (bg-gray-50, text-charcoal), font-title heading, proper dark mode | Jan 2026 |
| FASB Citations | `data-analyst/ConversationView.tsx` | InlineCitation, SourcesAccordion, SourceCard, PdfCanvasViewer, CanvasPanel | Jan 2026 |

### Pending Migration

#### High Priority (Core Admin/Settings)
- [ ] `admin/AdminDashboard.tsx`
- [ ] `platform-admin/TenantManagementPage.tsx`
- [ ] `platform-admin/FeatureAllocationPage.tsx`
- [x] `platform-admin/AdoptionAccessPage.tsx` (Jan 2026) - Panel, PanelHeader, PanelTitle, PanelDescription, PanelBody
- [x] `platform-admin/settings/AdminManagementPage.tsx` (Jan 2026)
- [x] `platform-admin/settings/AIProvidersPage.tsx` (Jan 2026)
- [ ] `platform-admin/settings/EmailIntegrationPage.tsx`
- [ ] `platform-admin/settings/JobSchedulerPage.tsx`
- [ ] `tenant-admin/UsersRolesPage.tsx`
- [ ] `tenant-admin/UserInvitesPage.tsx`
- [ ] `tenant-admin/RoleEditorPage.tsx`

#### Medium Priority (Feature Pages)
- [x] `domains/DomainsPage.tsx` (Feb 2026) - Page, PageHeader, PageBody, Card, Button, Input, Spinner, DropdownMenu
- [ ] `home/HomePage.tsx`
- [ ] `dashboard/DashboardPage.tsx`
- [ ] `business-intelligence/BusinessIntelligenceQA.tsx`
- [ ] `agent-configuration/AgentConfigurationPage.tsx`
- [ ] `data-connections/DataConnectionsPage.tsx`
- [ ] `company-data/CompanyDataOverview.tsx`
- [ ] `company-data/DocumentLibrary.tsx`
- [ ] `company-data/NewData.tsx`
- [ ] `insights/MyInsights.tsx`
- [ ] `data-analyst/DataAnalystPage.tsx`

#### Lower Priority (Specialized Pages)
- [ ] `talent-intelligence/TalentIntelligencePage.tsx`
- [x] `talent-intelligence/AnalysisConfigPage.tsx` (Jan 2026) - Page, PageHeader, PageBody, DataTable (expandable), Button, Badge, Alert, Spinner, Progress, Modal
- [ ] `talent-intelligence/CandidateOutreachPage.tsx`
- [ ] `talent-intelligence/EmailTemplatesPage.tsx`
- [ ] `talent-intelligence/TalentConfigurationPage.tsx`
- [ ] `talent-intelligence/TalentFeedbackPage.tsx`
- [ ] `ml-talent/MLTalentHistoryPage.tsx`
- [ ] `ml-talent/TalentAnalysisHistoryPage.tsx`
- [x] `adoption/AdoptionDashboardPage.tsx` (Jan 2026)
- [ ] `admin/AdoptionAccessPage.tsx`
- [ ] `admin/ResumeParsingTestPage.tsx`
- [ ] `caylent/EmployeesOverview.tsx`
- [ ] `reference-checks/ReferenceChecksPage.tsx`

#### Auth Pages (Separate Styling)
- [ ] `auth/LoginPage.tsx`
- [ ] `auth/AcceptInvitePage.tsx`

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Using raw `<button>` instead of `Button` | Import and use `Button` from `../../components/ui` |
| Using `onChange` on `Select` | DS `Select` uses `onValueChange`, not `onChange` |
| Mismatched `maxWidth` between `PageHeader` and `PageContent` | Use `Page` wrapper which handles alignment automatically |
| Using brand-specific icon colors (green, orange) | Use monochromatic gray or `eliza-red` accent only |
| Legacy color classes (`text-text`, `bg-surface`) | Replace with explicit classes (`text-charcoal dark:text-gray-100`, `bg-white dark:bg-dark-surface`) |
| Creating custom layout containers | Use `Page` component with `layout="centered"` or `layout="full-width"` |
| New component not on Showcase | Add to `ComponentShowcase.tsx` immediately after creation |

---

## Checklist

When migrating a page:

- [ ] Replace native HTML buttons with `Button` component
- [ ] Replace native inputs with `Input`, `Textarea`, `Select` components
- [ ] Replace native tables with `DataTable` component (use expandable if needed)
- [ ] Wrap page in `Page` component with appropriate `maxWidth`
- [ ] Add `PageHeader` inside `Page` for page title
- [ ] Add `PageBody` inside `Page` for content (ensures alignment with header)
- [ ] Add `SectionHeader` for section titles within content
- [ ] Replace modals with `Modal` components
- [ ] Replace alerts/notifications with `Alert` component
- [ ] Replace loading spinners with `Spinner` component
- [ ] Replace badges/pills with `Badge` component
- [ ] Update color classes (see Colors section)
- [ ] Update icon colors (monochromatic or accent)
- [ ] Verify all functionality still works
- [ ] Add page to showcase if it contains unique patterns

---

## Recent Updates

### January 2026

#### Citation Components for RAG/FASB
- InlineCitation - Clickable inline citation badges with subtle gray styling
- CitationGroup - Wrapper for multiple adjacent citations
- SourceCard - Full source display with metadata, Show PDF, and Validate buttons (black button)
- SourcesAccordion - Collapsible sources section using DS Accordion pattern
- PdfCanvasViewer - PDF viewer for CanvasPanel with highlighting toggle in header
- ChartCanvasViewer - Chart viewer for CanvasPanel (bar, line, pie) with DS theming
- Canvas integration - PDF and charts open in side canvas instead of inline/modal
- Hide View Raw Data - RAG responses (FASB) no longer show "View Raw Data" artifact
- Dark/light mode - All components support proper theming

#### New Homepage (Dashboard)
- Personalized greeting - "Good morning, {firstName}." using `font-title` (Libre Baskerville)
- Semantic search bar - Prominent prompt bar for asking questions, navigates to Data Analyst
- Quick action buttons - Create job spec, Search talent pool, Pipeline analytics
- App cards grid - 4 main apps (AI Recruiter, BI, Adoption Analytics, Knowledge Base)
- DS components - Uses `PageContent`, `SectionHeader`, proper typography
- Old homepage preserved - Available at `/home/widgets` for reference

#### Sidebar Refinements
- Hamburger icon always visible - Toggle icon stays as `Bars3Icon`, doesn't change to chevron
- No header separator - Removed default border from `SidebarHeader` component
- Cleaner visual - Sidebar flows seamlessly from toggle to navigation items

#### Gemini-Style Layout
- Sidebar + Toolbar columns - Layout restructured so sidebar spans full height, toolbar only spans content area
- Toggle in top-left corner - Collapse toggle is now in sidebar header, matching toolbar height (`h-12`)
- Visual column alignment - Sidebar and content area perfectly aligned top-to-bottom
- Familiar Google pattern - Matches Gmail, Drive, Gemini layout

#### Header and Toolbar Migration
- Header uses DS Toolbar - `Header.tsx` now uses `Toolbar` component with DS primitives
- DS TenantSwitcher integrated - Header shows elizaforge branding (`eliza`*`forge` for Organization)
- Toolbar items use DS Button - `ToolbarItem` and `ToolbarTextButton` use `Button variant="ghost"`
- Sidebar streamlined - Removed "Welcome back" user info section from Navigation sidebar

#### Navigation Architecture Overhaul
- Main Sidebar migrated to DS - `Navigation.tsx` now uses `Sidebar*` components
- LABS section added - Resume Parsing Test now visible in sidebar under LABS
- Contextual Navigation implemented - Full-replace pattern (main sidebar hides completely)
- SidebarSubmenu simplified - Simple back button, non-collapsible by design
- SidebarContextPanel wrapper - For use with `NavigationContext`
- Toolbar component created - Uses DS `Button` (ghost) for items
- SidebarMode extended - Now supports `expanded`, `collapsed`, `hidden`

#### Key Files Changed

| File | Change |
|------|--------|
| `pages/home/NewHomePage.tsx` | New dashboard with greeting, search bar, app cards |
| `layout/Layout.tsx` | Restructured to Gemini-style (sidebar + toolbar columns) |
| `layout/Header.tsx` | Migrated to DS Toolbar + TenantSwitcher with elizaforge branding |
| `layout/Navigation.tsx` | SidebarHeader with hamburger toggle (always visible), no border |
| `ui/sidebar.tsx` | Removed default border from `SidebarHeader` |
| `ui/tenant-switcher.tsx` | DS TenantSwitcher with elizaforge text branding |
| `ui/sidebar-submenu.tsx` | Simple back button header, no border, non-collapsible |
| `ui/sidebar-context-panel.tsx` | Wrapper using `SidebarSubmenu` |
| `ui/toolbar.tsx` | New component using DS Button |
| `contexts/NavigationContext.tsx` | Manages `activeSection` and `sidebarMode` |
| `contexts/sectionConfigs.ts` | Section definitions for contextual nav |

---

## Future Enhancements

### Planned Additions

- [x] DataTable: Expandable row support
- [x] Sidebar: `hidden` mode for contextual navigation
- [x] SidebarSubmenu: Contextual navigation with back button
- [x] Toolbar: Top bar with DS Button components
- [x] Homepage: Dashboard with greeting, search, app cards
- [x] Citation Components: InlineCitation, SourceCard, SourcesAccordion
- [x] Chart Components: ChartCanvasViewer for bar, line, pie charts
- [x] PdfCanvasViewer: PDF viewer with highlighting
- [ ] DataTable: Column resizing
- [ ] Toast notifications (global)
- [ ] Command palette (Cmd+K)
- [ ] DateRangePicker component

---

## References

- `frontend/src/components/ui/` — All DS component source files
- `frontend/src/components/ui/index.ts` — Component exports
- `frontend/src/pages/design-system/ComponentShowcase.tsx` — Living style guide
- `frontend/src/contexts/NavigationContext.tsx` — Navigation state management
- `frontend/src/components/navigation/sectionConfigs.ts` — Section definitions
- `frontend/src/components/layout/Layout.tsx` — Application layout structure
- `frontend/src/components/layout/Header.tsx` — Toolbar implementation
- `skills/code-templates/` — Frontend page and component templates
- `tailwind.config.js` — Design token definitions

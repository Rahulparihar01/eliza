# Eliza Forge Design System

> **Last Updated:** January 2026  
> **Status:** ✅ Implemented  
> **Component Library:** shadcn/ui-style + Radix primitives + Custom Components

---

## Overview

This document defines the complete design system and implementation plan for the Eliza Platform frontend redesign. It covers:

1. **Visual Identity** - Colors, typography, shapes
2. **Implemented Components** - Complete component catalog ✅
3. **Component Specifications** - Key UI patterns
4. **Screen Layouts** - Page-by-page breakdown
5. **AI Generation Prompts** - For rapid prototyping
6. **Component Library** - shadcn/ui architecture
7. **Folder Structure** - Code organization
8. **Cursor Rules** - AI enforcement
9. **Storybook** - Documentation
10. **Migration Plan** - Phased rollout

---

## 🎉 Implementation Status

The design system has been implemented with **50+ components** located in `frontend/src/components/ui/`. All components support:

- ✅ **Dark Mode** - Full dark theme support via `dark:` Tailwind classes
- ✅ **Accessibility** - WCAG AA contrast compliance, ARIA attributes
- ✅ **TypeScript** - Full type definitions and exports
- ✅ **CVA** - Class variance authority for variant management
- ✅ **Eliza Forge Branding** - Primary red (#b11e4c), custom typography

**Preview:** Run `npm start` and navigate to `/design-system/showcase` to see all components.

### Component Showcase Page

The showcase page at `/design-system/showcase` demonstrates all implemented components:

```
frontend/src/pages/design-system/ComponentShowcase.tsx
```

**Sections included:**
- Typography (Titles, Subtitles, Body, Code)
- Color Palette (Brand colors, surfaces, states)
- Buttons (All variants and sizes)
- Form Inputs (Input, Textarea, Switch, Label)
- Badges (All variants)
- Cards (Basic, with actions)
- Sidebar Components
- Tenant Switcher
- Tabs (Default, Pills, Underline)
- Modals (Basic, Form, Delete confirmation)
- Chips (Feature allocation patterns)
- Avatars & Avatar Groups
- Tooltips (All positions)
- Checkboxes (Various states)
- Spinners & Loading Overlays
- Alerts (All variants)
- Skeletons (Loading placeholders)
- Select Dropdowns
- Multi-Select Dropdowns
- Dropdown Menus
- Radio Groups & Cards
- Progress Bars (Linear & Circular)
- Accordions
- Card Variants (Metric, Stat, Progress, Image, Content, Link)
- Date Pickers (Single date, Date range with presets)
- Prompt Bar Variants (Basic, With Attachments, With Tools)
- Chat Components (Message Bubbles, Thinking Indicators, Canvas Mode)
- Breadcrumbs (With home icon, ellipsis support)
- Pagination (Full and Simple variants)
- Combobox / Autocomplete (Single and Multi-select with search)

### Dark Mode Support

All components support dark mode via Tailwind's `dark:` prefix. The design system uses:

- **Dark Background:** `#0f0f0f` (`dark-bg`)
- **Dark Surface:** `#1a1a1a` (`dark-surface`)
- **Dark Surface 2:** `#242424` (`dark-surface-2`)
- **Dark Borders:** `#374151` (Slate 700)

Enable dark mode by adding the `dark` class to the root `<html>` element:

```tsx
// Toggle dark mode
document.documentElement.classList.toggle('dark')
```

**Accessibility Notes:**
- Primary red (`#b11e4c`) on dark backgrounds uses white text for contrast
- Selected/active states use white text in dark mode for WCAG AA compliance
- Hover states use lighter tints that meet contrast requirements

---

## 1. Core Visual Identity (The "Vibe")

**Concept:** "Enterprise Clarity met with Human Warmth."

We are moving away from the standard "SaaS Blue/Gray" to a sophisticated, editorial palette using high-contrast typography and warm, human-centric gradients.

### A. Color Palette

**Brand Colors (Official - Eliza Forge Palette)**
- **Primary Rose:** `#c9506b` - Main brand color (buttons, logo, primary accents)
- **Warm Salmon:** `#e8a598` - Hover states, secondary accents
- **Peachy Cream:** `#f5c4a1` - Gradients, warm highlights

**Text Colors**
- **Normal Text:** `#5c4a5a` (Muted Charcoal with purple tint) - All body text
- **White on dark:** `#FFFFFF`

**The Brand Gradient**
- **Gradient:** `linear-gradient(135deg, #f5c4a1 0%, #e8a598 50%, #c9506b 100%)`
- **Use for:**
    - The background of the "Good Morning" hero section on the Dashboard.
    - The top accent bar on cards.
    - Subtle hover states on large cards.

**Surfaces**
- **Canvas (Light):** `#F9FAFB` - Main app background
- **Canvas (Dark):** `#0f0f0f` - Dark mode background
- **Cards/Panels (Light):** `#FFFFFF` (Pure White)
- **Cards/Panels (Dark):** `#1a1a1a`
- **Borders:** `#E5E7EB` (Light) / `#374151` (Dark)

### B. Typography

**Title Font**
* **Font:** **Libre Baskerville** (Google Font)
* **Style:** Regular and italic weights
* **Usage:** H1 (Page Titles), H2 (Section Headers)
    * *Example:* "Good morning, Eliza." or "Talent Search"

**Subtitle Font**
* **Font:** **Hedvig Letters Serif** (Google Font)
* **Style:** Optical sizing, elegant serif
* **Usage:** Subtitles, descriptions, card descriptions

**Body & UI Font**
* **Font:** **Inter**
* **Color:** `#434343` (Charcoal)
* **Style:** Clean, legible, variable weight (300-700)
* **Usage:** Sidebar links, table data, buttons, input text

**Code Font**
* **Font:** **JetBrains Mono**
* **Usage:** Code snippets, technical data

### C. Shape & Form (The "Soft" UI)

* **Corner Radius:**
    * **Outer Containers:** `24px` (Large, smooth curves like the marketing screenshots).
    * **Inner Cards/Inputs:** `12px` (Standard modern feel).
    * **Buttons:** `999px` (Full Pill Shape).
* **Shadows:**
    * **Cards:** `box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);` (Soft, diffuse, expensive-looking).

---

## 2. Implemented Components Catalog

All components are located in `frontend/src/components/ui/` and exported from `frontend/src/components/ui/index.ts`.

### Form Primitives

#### Button (`button.tsx`)
Standard button component with multiple variants.

```tsx
import { Button } from '@/components/ui'

<Button variant="default">Primary</Button>
<Button variant="brand">Brand Red</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Destructive</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>
<Button size="sm">Small</Button>
<Button size="lg">Large</Button>
<Button size="icon"><PlusIcon /></Button>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `variant` | `'default' \| 'brand' \| 'secondary' \| 'destructive' \| 'ghost' \| 'link'` | `'default'` | Visual style |
| `size` | `'default' \| 'sm' \| 'lg' \| 'icon'` | `'default'` | Size variant |

---

#### Input (`input.tsx`)
Text input field with focus states.

```tsx
import { Input } from '@/components/ui'

<Input placeholder="Enter text..." />
<Input type="email" placeholder="Email address" />
<Input disabled placeholder="Disabled" />
```

---

#### Textarea (`textarea.tsx`)
Multi-line text input.

```tsx
import { Textarea } from '@/components/ui'

<Textarea placeholder="Enter your message..." rows={4} />
```

---

#### Checkbox (`checkbox.tsx`)
Toggleable checkbox with label and description support.

```tsx
import { Checkbox } from '@/components/ui'

<Checkbox label="Accept terms" />
<Checkbox label="Newsletter" description="Receive weekly updates" />
<Checkbox checked={true} label="Checked" />
<Checkbox indeterminate label="Indeterminate" />
<Checkbox disabled label="Disabled" />
<Checkbox defaultChecked label="Default checked (uncontrolled)" />
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `label` | `string` | - | Checkbox label text |
| `description` | `string` | - | Helper text below label |
| `checked` | `boolean` | - | Controlled checked state |
| `defaultChecked` | `boolean` | - | Uncontrolled initial state |
| `indeterminate` | `boolean` | `false` | Shows minus icon for partial selection |
| `disabled` | `boolean` | `false` | Disables the checkbox |

---

#### Switch (`switch.tsx`)
Toggle switch for on/off states.

```tsx
import { Switch } from '@/components/ui'

<Switch />
<Switch defaultChecked />
<Switch disabled />
```

---

#### Label (`label.tsx`)
Form field label component.

```tsx
import { Label } from '@/components/ui'

<Label htmlFor="email">Email Address</Label>
```

---

#### Select (`select.tsx`)
Dropdown select component.

```tsx
import { Select, SelectOption, SelectGroup } from '@/components/ui'

<Select placeholder="Choose an option">
  <SelectOption value="1">Option 1</SelectOption>
  <SelectOption value="2">Option 2</SelectOption>
  <SelectOption value="3" disabled>Disabled</SelectOption>
</Select>

// With groups
<Select placeholder="Choose a fruit">
  <SelectGroup label="Citrus">
    <SelectOption value="orange">Orange</SelectOption>
    <SelectOption value="lemon">Lemon</SelectOption>
  </SelectGroup>
  <SelectGroup label="Berries">
    <SelectOption value="strawberry">Strawberry</SelectOption>
    <SelectOption value="blueberry">Blueberry</SelectOption>
  </SelectGroup>
</Select>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string` | - | Controlled value |
| `defaultValue` | `string` | - | Initial value (uncontrolled) |
| `placeholder` | `string` | `'Select...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disables the select |
| `onChange` | `(value: string) => void` | - | Change handler |

---

#### MultiSelect (`multi-select.tsx`)
Multi-selection dropdown with chips display.

```tsx
import { MultiSelect, MultiSelectOption, MultiSelectGroup, MultiSelectActions } from '@/components/ui'

const [selected, setSelected] = useState<string[]>([])

<MultiSelect 
  value={selected} 
  onChange={setSelected}
  placeholder="Select items..."
>
  <MultiSelectActions /> {/* Select All / Clear buttons */}
  <MultiSelectGroup label="Category A">
    <MultiSelectOption value="1">Item 1</MultiSelectOption>
    <MultiSelectOption value="2">Item 2</MultiSelectOption>
  </MultiSelectGroup>
</MultiSelect>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | `[]` | Selected values |
| `onChange` | `(values: string[]) => void` | - | Change handler |
| `placeholder` | `string` | `'Select...'` | Placeholder text |
| `maxDisplayedChips` | `number` | `3` | Max chips before "+N more" |

---

#### RadioGroup (`radio-group.tsx`)
Single-select radio button group.

```tsx
import { RadioGroup, RadioGroupItem, RadioCard } from '@/components/ui'

// Standard radio group
<RadioGroup value={value} onValueChange={setValue}>
  <RadioGroupItem value="option1" label="Option 1" />
  <RadioGroupItem value="option2" label="Option 2" description="With description" />
  <RadioGroupItem value="option3" label="Option 3" disabled />
</RadioGroup>

// Horizontal orientation
<RadioGroup orientation="horizontal">
  <RadioGroupItem value="a" label="A" />
  <RadioGroupItem value="b" label="B" />
</RadioGroup>

// Card-style selection
<RadioGroup value={value} onValueChange={setValue}>
  <RadioCard value="starter" label="Starter" description="For small teams">
    $10/mo
  </RadioCard>
  <RadioCard value="pro" label="Pro" description="For growing teams">
    $25/mo
  </RadioCard>
</RadioGroup>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string` | - | Selected value |
| `onValueChange` | `(value: string) => void` | - | Change handler |
| `orientation` | `'vertical' \| 'horizontal'` | `'vertical'` | Layout direction |

---

### Display Components

#### Card (`card.tsx`)
Container for content sections.

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui'

<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>Card description text</CardDescription>
  </CardHeader>
  <CardContent>
    Main content goes here
  </CardContent>
  <CardFooter>
    <Button>Action</Button>
  </CardFooter>
</Card>
```

---

#### Card Variants (`card-variants.tsx`)
Extended card components for specific use cases.

##### MetricCard
KPI display card with trend indicators.

```tsx
import { MetricCard } from '@/components/ui'

<MetricCard
  title="Total Users"
  value="12,543"
  change="+12.5%"
  trend="up"           // 'up' | 'down' | 'neutral'
  icon={<UsersIcon />}
  subtitle="vs last month"
/>
```

##### StatCard
Compact stat card with colored left border.

```tsx
import { StatCard } from '@/components/ui'

<StatCard
  label="Active Projects"
  value="24"
  color="red"    // 'red' | 'blue' | 'green' | 'yellow' | 'purple'
  icon={<FolderIcon />}
/>
```

##### ProgressCard
Card showing progress towards a target.

```tsx
import { ProgressCard } from '@/components/ui'

<ProgressCard
  title="Q4 Sales Target"
  current={75000}
  target={100000}
  unit="$"
  icon={<ChartBarIcon />}
/>
```

##### ImageCard
Card with prominent image header.

```tsx
import { ImageCard } from '@/components/ui'

<ImageCard
  title="Product Launch"
  description="New feature announcement"
  imageUrl="/images/product.jpg"
  badge="New"
  badgeVariant="primary"  // 'primary' | 'secondary' | 'success' | 'warning'
  overlayContent={<Button>Learn More</Button>}
  onClick={() => {}}
/>
```

##### ContentCard
Article/blog-style content card.

```tsx
import { ContentCard } from '@/components/ui'

<ContentCard
  title="Getting Started Guide"
  excerpt="Learn how to set up your first project..."
  author="Jane Smith"
  date="Jan 10, 2026"
  tags={['Tutorial', 'Beginner']}
  imageUrl="/images/article.jpg"
  readTime="5 min read"
  onClick={() => {}}
/>
```

##### LinkCard
Navigation tile card.

```tsx
import { LinkCard } from '@/components/ui'

<LinkCard
  title="Settings"
  description="Manage your account preferences"
  icon={<CogIcon className="w-6 h-6" />}
  href="/settings"
  // or onClick={() => {}}
/>
```

---

#### Badge (`badge.tsx`)
Small status indicator.

```tsx
import { Badge } from '@/components/ui'

<Badge>Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="success">Success</Badge>
<Badge variant="warning">Warning</Badge>
<Badge variant="destructive">Error</Badge>
<Badge variant="outline">Outline</Badge>
```

---

#### Chip (`chip.tsx`)
Toggleable pill for selections (e.g., feature allocation).

```tsx
import { Chip, ChipGroup } from '@/components/ui'

const [selected, setSelected] = useState(['feature1'])

<ChipGroup>
  <Chip 
    selected={selected.includes('feature1')}
    onClick={() => toggle('feature1')}
  >
    Feature 1
  </Chip>
  <Chip 
    selected={selected.includes('feature2')}
    onClick={() => toggle('feature2')}
    icon={<StarIcon />}
  >
    Feature 2
  </Chip>
</ChipGroup>

// Variants
<Chip variant="default">Default</Chip>
<Chip variant="outline">Outline</Chip>
<Chip variant="ghost">Ghost</Chip>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `selected` | `boolean` | `false` | Selected state |
| `variant` | `'default' \| 'outline' \| 'ghost'` | `'default'` | Visual style |
| `icon` | `ReactNode` | - | Icon element |
| `iconPosition` | `'left' \| 'right'` | `'left'` | Icon position |
| `disabled` | `boolean` | `false` | Disabled state |

---

#### Avatar (`avatar.tsx`)
User profile picture with fallback.

```tsx
import { Avatar, AvatarGroup } from '@/components/ui'

<Avatar src="/images/user.jpg" name="John Doe" />
<Avatar name="Jane Smith" />  {/* Shows initials */}
<Avatar size="sm" name="Bob" />
<Avatar size="lg" name="Alice" />
<Avatar size="xl" name="Charlie" />

// Avatar group (stacked)
<AvatarGroup max={3}>
  <Avatar name="User 1" />
  <Avatar name="User 2" />
  <Avatar name="User 3" />
  <Avatar name="User 4" />  {/* Shows +1 overflow */}
</AvatarGroup>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `src` | `string` | - | Image URL |
| `name` | `string` | - | Name for initials fallback |
| `size` | `'xs' \| 'sm' \| 'md' \| 'lg' \| 'xl'` | `'md'` | Avatar size |

---

#### Separator (`separator.tsx`)
Visual divider line.

```tsx
import { Separator } from '@/components/ui'

<Separator />
<Separator orientation="vertical" />
```

---

#### Skeleton (`skeleton.tsx`)
Loading placeholder animations.

```tsx
import { Skeleton, SkeletonAvatar, SkeletonText, SkeletonCard, SkeletonTableRow } from '@/components/ui'

// Basic shapes
<Skeleton variant="text" width="200px" />
<Skeleton variant="circular" width="40px" height="40px" />
<Skeleton variant="rectangular" width="100%" height="200px" />
<Skeleton variant="rounded" width="100%" height="100px" />

// Presets
<SkeletonAvatar />
<SkeletonText lines={3} />
<SkeletonCard />
<SkeletonTableRow columns={4} />
```

---

#### Progress (`progress.tsx`)
Progress indicators.

```tsx
import { Progress, CircularProgress } from '@/components/ui'

// Linear progress bar
<Progress value={75} />
<Progress value={50} showLabel />
<Progress value={30} size="sm" />
<Progress value={60} size="lg" variant="success" />
<Progress value={90} variant="warning" />
<Progress variant="gradient" value={80} />
<Progress indeterminate />  {/* Animated loading */}

// Circular progress
<CircularProgress value={75} />
<CircularProgress value={50} showLabel size="lg" />
<CircularProgress indeterminate />
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `number` | `0` | Progress 0-100 |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Size variant |
| `variant` | `'default' \| 'success' \| 'warning' \| 'info' \| 'gradient'` | `'default'` | Color variant |
| `showLabel` | `boolean` | `false` | Show percentage text |
| `indeterminate` | `boolean` | `false` | Animated loading state |

---

### Feedback Components

#### Alert (`alert.tsx`)
Inline notification banner.

```tsx
import { Alert } from '@/components/ui'

<Alert variant="info" title="Information">
  This is an informational message.
</Alert>

<Alert variant="success" title="Success!">
  Operation completed successfully.
</Alert>

<Alert variant="warning" title="Warning">
  Please review before proceeding.
</Alert>

<Alert variant="error" title="Error">
  Something went wrong.
</Alert>

<Alert 
  variant="info" 
  dismissible 
  onDismiss={() => {}}
>
  Dismissible alert
</Alert>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `variant` | `'info' \| 'success' \| 'warning' \| 'error' \| 'neutral'` | `'info'` | Alert type |
| `title` | `string` | - | Alert title |
| `icon` | `ReactNode` | - | Custom icon |
| `dismissible` | `boolean` | `false` | Show dismiss button |
| `onDismiss` | `() => void` | - | Dismiss callback |

---

#### Toast (`toast.tsx`)
Temporary popup notifications.

```tsx
import { ToastContainer, useToast } from '@/components/ui'

// Add ToastContainer to your app root
function App() {
  return (
    <>
      <ToastContainer />
      <YourApp />
    </>
  )
}

// Use the hook in components
function MyComponent() {
  const { toast, dismiss, dismissAll } = useToast()

  const showToast = () => {
    toast({
      title: "Success!",
      message: "Your changes have been saved.",
      variant: "success",
      duration: 5000,
    })
  }

  // Variants: 'default' | 'success' | 'error' | 'warning' | 'info'
}
```

---

#### Spinner (`spinner.tsx`)
Loading indicator.

```tsx
import { Spinner, LoadingOverlay } from '@/components/ui'

<Spinner />
<Spinner size="xs" />
<Spinner size="sm" />
<Spinner size="lg" />
<Spinner size="xl" />

<Spinner variant="primary" />  {/* Eliza red */}
<Spinner variant="white" />    {/* For dark backgrounds */}
<Spinner variant="muted" />

// Full container overlay
<LoadingOverlay text="Loading..." />
```

---

#### Tooltip (`tooltip.tsx`)
Hover hint with positioning.

```tsx
import { Tooltip } from '@/components/ui'

<Tooltip content="This is a tooltip">
  <Button>Hover me</Button>
</Tooltip>

<Tooltip content="Bottom tooltip" position="bottom">
  <span>Bottom</span>
</Tooltip>

<Tooltip content="Left tooltip" position="left">
  <span>Left</span>
</Tooltip>

<Tooltip content="Right tooltip" position="right">
  <span>Right</span>
</Tooltip>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `content` | `ReactNode` | - | Tooltip content |
| `position` | `'top' \| 'bottom' \| 'left' \| 'right'` | `'top'` | Tooltip position |
| `delay` | `number` | `200` | Delay before showing (ms) |

---

### Overlay Components

#### Modal (`modal.tsx`)
Dialog overlay component.

```tsx
import { Modal, ModalContent, ModalHeader, ModalTitle, ModalDescription, ModalBody, ModalFooter } from '@/components/ui'

const [open, setOpen] = useState(false)

<Modal open={open} onOpenChange={setOpen}>
  <ModalContent size="md">
    <ModalHeader>
      <ModalTitle>Modal Title</ModalTitle>
      <ModalDescription>Optional description text</ModalDescription>
    </ModalHeader>
    <ModalBody>
      Modal content goes here
    </ModalBody>
    <ModalFooter>
      <Button variant="secondary" onClick={() => setOpen(false)}>
        Cancel
      </Button>
      <Button onClick={handleSave}>Save</Button>
    </ModalFooter>
  </ModalContent>
</Modal>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `open` | `boolean` | - | Controlled open state |
| `onOpenChange` | `(open: boolean) => void` | - | State change handler |
| `size` | `'sm' \| 'md' \| 'lg' \| 'xl' \| 'full'` | `'md'` | Modal width |
| `closeOnBackdropClick` | `boolean` | `true` | Close on backdrop click |
| `closeOnEscape` | `boolean` | `true` | Close on Escape key |

---

#### DropdownMenu (`dropdown-menu.tsx`)
Action/context menu.

```tsx
import { DropdownMenu, DropdownTrigger, DropdownContent, DropdownItem, DropdownLabel, DropdownSeparator, DropdownSubmenu } from '@/components/ui'

<DropdownMenu>
  <DropdownTrigger asChild>
    <Button>Open Menu</Button>
  </DropdownTrigger>
  <DropdownContent>
    <DropdownLabel>Actions</DropdownLabel>
    <DropdownItem onClick={() => {}}>
      Edit
    </DropdownItem>
    <DropdownItem onClick={() => {}}>
      Duplicate
    </DropdownItem>
    <DropdownSeparator />
    <DropdownItem destructive onClick={() => {}}>
      Delete
    </DropdownItem>
  </DropdownContent>
</DropdownMenu>

// With submenu
<DropdownSubmenu label="More options">
  <DropdownItem>Option A</DropdownItem>
  <DropdownItem>Option B</DropdownItem>
</DropdownSubmenu>
```

---

### Navigation Components

#### Tabs (`tabs.tsx`)
Tab navigation component.

```tsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'

<Tabs defaultValue="tab1">
  <TabsList>
    <TabsTrigger value="tab1">Tab 1</TabsTrigger>
    <TabsTrigger value="tab2">Tab 2</TabsTrigger>
    <TabsTrigger value="tab3" disabled>Disabled</TabsTrigger>
  </TabsList>
  <TabsContent value="tab1">Content for tab 1</TabsContent>
  <TabsContent value="tab2">Content for tab 2</TabsContent>
  <TabsContent value="tab3">Content for tab 3</TabsContent>
</Tabs>

// Variants
<Tabs variant="default">...</Tabs>   {/* Gray background tabs */}
<Tabs variant="pills">...</Tabs>     {/* Pill-shaped tabs */}
<Tabs variant="underline">...</Tabs> {/* Underlined tabs */}
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string` | - | Controlled active tab |
| `defaultValue` | `string` | - | Initial active tab |
| `onValueChange` | `(value: string) => void` | - | Tab change handler |
| `variant` | `'default' \| 'pills' \| 'underline'` | `'default'` | Visual style |

---

#### Accordion (`accordion.tsx`)
Collapsible content sections.

```tsx
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui'

// Single item open at a time
<Accordion type="single" defaultValue="item-1">
  <AccordionItem value="item-1">
    <AccordionTrigger>Section 1</AccordionTrigger>
    <AccordionContent>Content for section 1</AccordionContent>
  </AccordionItem>
  <AccordionItem value="item-2">
    <AccordionTrigger>Section 2</AccordionTrigger>
    <AccordionContent>Content for section 2</AccordionContent>
  </AccordionItem>
</Accordion>

// Multiple items can be open
<Accordion type="multiple" defaultValue={['item-1', 'item-2']}>
  ...
</Accordion>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `type` | `'single' \| 'multiple'` | `'single'` | Allow one or multiple open |
| `value` | `string \| string[]` | - | Controlled open items |
| `defaultValue` | `string \| string[]` | - | Initial open items |
| `onValueChange` | `(value) => void` | - | Change handler |

---

#### Sidebar (`sidebar.tsx`)
Collapsible navigation sidebar with sections, expandable items, and tooltips.

##### Basic Collapsible Sidebar
```tsx
import { 
  SidebarProvider, 
  Sidebar, 
  SidebarHeader, 
  SidebarLogo, 
  SidebarContent, 
  SidebarSection, 
  SidebarItem, 
  SidebarSubItem, 
  SidebarFooter 
} from '@/components/ui'

// Wrap with SidebarProvider for collapse state management
<SidebarProvider defaultCollapsed={false} onCollapsedChange={(collapsed) => console.log(collapsed)}>
  <Sidebar>
    <SidebarHeader showCollapseToggle>
      <SidebarLogo />
    </SidebarHeader>
    <SidebarContent>
      <SidebarSection title="Main">
        <SidebarItem icon={<HomeIcon />} isActive>
          Dashboard
        </SidebarItem>
        <SidebarItem icon={<UsersIcon />} badge={3}>
          Users
        </SidebarItem>
        <SidebarItem icon={<CogIcon />} defaultOpen>
          Settings
          <SidebarSubItem isActive>General</SidebarSubItem>
          <SidebarSubItem>Security</SidebarSubItem>
        </SidebarItem>
      </SidebarSection>
    </SidebarContent>
    <SidebarFooter showExpandButton>
      <span>v1.0</span>
    </SidebarFooter>
  </Sidebar>
</SidebarProvider>
```

##### Using the Sidebar Hook
```tsx
import { useSidebar } from '@/components/ui'

function MyComponent() {
  const { collapsed, setCollapsed, toggleCollapsed } = useSidebar()
  
  return (
    <button onClick={toggleCollapsed}>
      {collapsed ? 'Expand' : 'Collapse'}
    </button>
  )
}
```

##### Programmatic Control
```tsx
// Control collapsed state externally
const [isCollapsed, setIsCollapsed] = useState(false)

<SidebarProvider 
  defaultCollapsed={isCollapsed} 
  onCollapsedChange={setIsCollapsed}
>
  <Sidebar />
</SidebarProvider>

// Or use without provider for simple controlled mode
<Sidebar collapsed={isCollapsed} />
```

**Features:**
- **Collapsible**: Animated collapse/expand with smooth transitions
- **Tooltips**: Hover hints when collapsed showing item names
- **Context-based**: `SidebarProvider` for shared collapse state
- **Badges**: Show notification counts (visible when collapsed too)
- **Expandable Items**: Add `SidebarSubItem` children for nested navigation
- **Custom Widths**: Configure `collapsedWidth` and `expandedWidth`

| Component | Props | Description |
|-----------|-------|-------------|
| `SidebarProvider` | `defaultCollapsed`, `onCollapsedChange` | Wrap sidebar for state management |
| `Sidebar` | `collapsed`, `collapsedWidth`, `expandedWidth` | Main container |
| `SidebarCollapseTrigger` | `floating` | Toggle button (auto or floating) |
| `SidebarHeader` | `showCollapseToggle` | Header with optional toggle |
| `SidebarSection` | `title` | Grouped section with label |
| `SidebarItem` | `icon`, `isActive`, `badge`, `tooltip`, `defaultOpen` | Navigation item |
| `SidebarSubItem` | `isActive` | Nested item (makes parent expandable) |
| `SidebarFooter` | `showExpandButton` | Footer with optional expand button |

---

#### TenantSwitcher (`tenant-switcher.tsx`)
Multi-tenant organization selector.

```tsx
import { TenantSwitcher, TenantSwitcherCompact } from '@/components/ui'

const tenants = [
  { id: '1', name: 'Acme Corp', logo: '/acme.png' },
  { id: '2', name: 'Globex Inc', logo: '/globex.png' },
]

<TenantSwitcher
  tenants={tenants}
  currentTenant={tenants[0]}
  onTenantChange={(tenant) => {}}
/>

// Compact version for narrow sidebars
<TenantSwitcherCompact
  tenants={tenants}
  currentTenant={tenants[0]}
  onTenantChange={(tenant) => {}}
/>
```

---

### Date & Time Components

#### Calendar (`date-picker.tsx`)
Calendar grid for date selection.

```tsx
import { Calendar } from '@/components/ui'

<Calendar
  value={selectedDate}
  onChange={setSelectedDate}
  minDate={new Date()}
  maxDate={new Date(2026, 11, 31)}
/>
```

---

#### DatePicker (`date-picker.tsx`)
Dropdown date selector.

```tsx
import { DatePicker } from '@/components/ui'

<DatePicker
  value={selectedDate}
  onChange={setSelectedDate}
  placeholder="Select a date"
/>
```

---

#### DateRangePicker (`date-picker.tsx`)
Date range selection with presets.

```tsx
import { DateRangePicker, DateRange } from '@/components/ui'

const [range, setRange] = useState<DateRange>({ from: null, to: null })

<DateRangePicker
  value={range}
  onChange={setRange}
  presets={[
    { label: 'Last 7 days', range: { from: subDays(new Date(), 7), to: new Date() } },
    { label: 'Last 30 days', range: { from: subDays(new Date(), 30), to: new Date() } },
    { label: 'This month', range: { from: startOfMonth(new Date()), to: new Date() } },
  ]}
/>
```

---

### AI Input Components

#### PromptBar (`prompt-bar.tsx`)
AI chat input with various features.

##### Basic PromptBar
```tsx
import { PromptBar } from '@/components/ui'

<PromptBar
  placeholder="Type your message..."
  onSubmit={(value) => console.log(value)}
  disabled={isLoading}
/>
```

##### PromptBar with Attachments
```tsx
import { PromptBarWithAttachments, Attachment } from '@/components/ui'

const [attachments, setAttachments] = useState<Attachment[]>([])

<PromptBarWithAttachments
  placeholder="Type your message..."
  onSubmit={(value, attachments) => {}}
  attachments={attachments}
  onAttachmentsChange={setAttachments}
  maxAttachments={5}
  acceptedFileTypes=".pdf,.doc,.docx,.txt,.png,.jpg"
/>
```

##### Full-Featured PromptBar with Tools
```tsx
import { PromptBarWithTools, Attachment, Tool } from '@/components/ui'

const tools: Tool[] = [
  { id: 'search', name: 'Web Search', icon: <SearchIcon /> },
  { id: 'code', name: 'Code Interpreter', icon: <CodeIcon /> },
  { id: 'image', name: 'Image Generation', icon: <PhotoIcon /> },
]

const [attachments, setAttachments] = useState<Attachment[]>([])
const [selectedTools, setSelectedTools] = useState<string[]>([])

<PromptBarWithTools
  placeholder="Type your message..."
  onSubmit={(value, attachments, tools) => {}}
  attachments={attachments}
  onAttachmentsChange={setAttachments}
  tools={tools}
  selectedTools={selectedTools}
  onToolsChange={setSelectedTools}
  showVoice={true}
/>
```

**Features:**
- File drag-and-drop with visual highlight
- Image thumbnails for image attachments
- Tool selection with chip display
- Voice input button (optional)
- Round send button with arrow icon
- Auto-resizing textarea

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `placeholder` | `string` | `'Type your message...'` | Input placeholder |
| `onSubmit` | `(value, attachments?, tools?) => void` | - | Submit handler |
| `disabled` | `boolean` | `false` | Disable input |
| `attachments` | `Attachment[]` | `[]` | File attachments |
| `onAttachmentsChange` | `(attachments) => void` | - | Attachment change handler |
| `tools` | `Tool[]` | `[]` | Available tools |
| `selectedTools` | `string[]` | `[]` | Selected tool IDs |
| `onToolsChange` | `(toolIds) => void` | - | Tool selection handler |
| `showVoice` | `boolean` | `false` | Show voice input button |

---

### Chat Components (`chat.tsx`)

Complete chat interface with message bubbles, thinking indicators, code blocks, images, and canvas mode.

#### ChatProvider & ChatContainer
Wrap your chat interface with the provider for canvas state management.

```tsx
import { ChatProvider, ChatContainer, ChatMessagesPane, ChatInputArea } from '@/components/ui'

<ChatProvider>
  <ChatContainer>
    <ChatMessagesPane>
      {/* Messages go here */}
    </ChatMessagesPane>
    <ChatInputArea>
      <PromptBar onSubmit={handleSubmit} />
    </ChatInputArea>
  </ChatContainer>
</ChatProvider>
```

#### MessageBubble
Message container with role-based styling.

```tsx
import { MessageBubble, MessageContent } from '@/components/ui'

// User message (gray bubble, no avatar)
<MessageBubble role="user">
  <MessageContent>Hello, how can you help me today?</MessageContent>
</MessageBubble>

// Assistant message (no bubble, markdown rendering)
<MessageBubble role="assistant" showAvatar avatar={<BotIcon />}>
  <MessageContent>I can help you with many things...</MessageContent>
</MessageBubble>

// Streaming message
<MessageBubble role="assistant" isStreaming>
  <MessageContent>Generating response</MessageContent>
</MessageBubble>

// With timestamp
<MessageBubble role="user" timestamp="2:34 PM">
  <MessageContent>Thanks!</MessageContent>
</MessageBubble>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `role` | `'user' \| 'assistant' \| 'system'` | - | Message sender |
| `showAvatar` | `boolean` | `true` for assistant | Show avatar |
| `avatar` | `ReactNode` | - | Custom avatar element |
| `timestamp` | `string` | - | Message timestamp |
| `isStreaming` | `boolean` | `false` | Show streaming indicator |

---

#### ThinkingIndicator
Expandable thinking/reasoning trace display.

```tsx
import { ThinkingIndicator } from '@/components/ui'

// Basic thinking dots
<ThinkingIndicator />

// Expandable with trace content
<ThinkingIndicator 
  expandable 
  thinkingTrace="Analyzing the user's request... Considering multiple approaches..."
/>

// Default expanded
<ThinkingIndicator 
  expandable 
  defaultExpanded
  thinkingTrace="Step 1: Parse input\nStep 2: Generate response..."
/>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `expandable` | `boolean` | `false` | Allow expanding to see trace |
| `thinkingTrace` | `string` | - | The thinking content |
| `defaultExpanded` | `boolean` | `false` | Start expanded |

---

#### ChatImage
Image display with canvas integration.

```tsx
import { ChatImage } from '@/components/ui'

<ChatImage
  src="/images/diagram.png"
  alt="Architecture diagram"
  caption="System architecture overview"
  openInCanvas  // Clicking opens in canvas panel
/>
```

---

#### ChatCodeBlock
Syntax-highlighted code with copy and canvas options.

```tsx
import { ChatCodeBlock } from '@/components/ui'

<ChatCodeBlock
  code={`function hello() {\n  console.log('Hello!');\n}`}
  language="javascript"
  filename="example.js"
  showCanvasButton  // Opens in canvas panel
/>
```

---

#### CanvasPanel
Slide-out panel for viewing artifacts (images, code, documents).

```tsx
import { useChat, CanvasPanel } from '@/components/ui'

// Canvas is automatically managed by ChatProvider
// Use the hook to control it programmatically:
const { openCanvas, closeCanvas, canvasOpen } = useChat()

openCanvas({
  title: "Generated Code",
  content: <CodeEditor code={myCode} />,
})
```

---

#### ArtifactButton
Inline button to open content in canvas.

```tsx
import { ArtifactButton } from '@/components/ui'

<ArtifactButton
  artifactType="code"
  title="Generated Function"
  description="A helper function for data processing"
  onClick={() => openCanvas({ title: "Code", content: <MyCode /> })}
/>

// Types: 'code' | 'image' | 'document' | 'chart'
```

---

### Breadcrumb (`breadcrumb.tsx`)
Hierarchical navigation path.

```tsx
import { Breadcrumb, BreadcrumbItem, BreadcrumbEllipsis } from '@/components/ui'

// Basic breadcrumb
<Breadcrumb>
  <BreadcrumbItem href="/">Home</BreadcrumbItem>
  <BreadcrumbItem href="/products">Products</BreadcrumbItem>
  <BreadcrumbItem current>Product Details</BreadcrumbItem>
</Breadcrumb>

// With home icon
<Breadcrumb showHomeIcon>
  <BreadcrumbItem href="/dashboard">Dashboard</BreadcrumbItem>
  <BreadcrumbItem current>Settings</BreadcrumbItem>
</Breadcrumb>

// With ellipsis for long paths
<Breadcrumb>
  <BreadcrumbItem href="/">Home</BreadcrumbItem>
  <BreadcrumbEllipsis />
  <BreadcrumbItem href="/category">Category</BreadcrumbItem>
  <BreadcrumbItem current>Item</BreadcrumbItem>
</Breadcrumb>

// Custom separator
<Breadcrumb separator="/">
  <BreadcrumbItem href="/">Home</BreadcrumbItem>
  <BreadcrumbItem current>Page</BreadcrumbItem>
</Breadcrumb>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `separator` | `ReactNode` | `ChevronRightIcon` | Custom separator |
| `showHomeIcon` | `boolean` | `false` | Show home icon for first item |

---

### Pagination (`pagination.tsx`)
Page navigation controls.

```tsx
import { Pagination, SimplePagination } from '@/components/ui'

// Full pagination with page numbers
<Pagination
  page={5}
  totalPages={10}
  onPageChange={(page) => setPage(page)}
  showFirstLast    // Show first/last buttons
  showPrevNext     // Show prev/next buttons
  siblingCount={1} // Pages to show around current
/>

// Simple prev/next pagination
<SimplePagination
  page={3}
  totalPages={7}
  onPageChange={(page) => setPage(page)}
  showPageInfo  // Shows "Page 3 of 7"
/>

// Size variants
<Pagination page={2} totalPages={5} size="sm" onPageChange={setPage} />
<Pagination page={2} totalPages={5} size="md" onPageChange={setPage} />
<Pagination page={2} totalPages={5} size="lg" onPageChange={setPage} />
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `page` | `number` | - | Current page (1-indexed) |
| `totalPages` | `number` | - | Total number of pages |
| `onPageChange` | `(page: number) => void` | - | Page change handler |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Button size |
| `showFirstLast` | `boolean` | `true` | Show first/last buttons |
| `showPrevNext` | `boolean` | `true` | Show prev/next buttons |
| `siblingCount` | `number` | `1` | Pages around current |

---

### Combobox (`combobox.tsx`)
Searchable dropdown with autocomplete.

##### Single Select Combobox
```tsx
import { Combobox, ComboboxOption } from '@/components/ui'

const options: ComboboxOption[] = [
  { value: 'react', label: 'React' },
  { value: 'vue', label: 'Vue', description: 'Progressive framework' },
  { value: 'angular', label: 'Angular', icon: <AngularIcon /> },
  { value: 'svelte', label: 'Svelte', disabled: true },
]

<Combobox
  options={options}
  value={selected}
  onChange={setSelected}
  placeholder="Search frameworks..."
  clearable
/>
```

##### Multi-Select Combobox
```tsx
import { MultiCombobox, ComboboxOption } from '@/components/ui'

const people: ComboboxOption[] = [
  { value: '1', label: 'Alice Smith' },
  { value: '2', label: 'Bob Jones' },
  { value: '3', label: 'Carol Williams' },
]

<MultiCombobox
  options={people}
  value={selectedPeople}
  onChange={setSelectedPeople}
  placeholder="Select team members..."
/>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `options` | `ComboboxOption[]` | `[]` | Available options |
| `value` | `string \| string[]` | - | Selected value(s) |
| `onChange` | `(value) => void` | - | Change handler |
| `placeholder` | `string` | `'Search...'` | Input placeholder |
| `clearable` | `boolean` | `false` | Show clear button (single) |
| `disabled` | `boolean` | `false` | Disable the combobox |
| `emptyMessage` | `string` | `'No results found'` | Empty state message |

**ComboboxOption Interface:**
```tsx
interface ComboboxOption {
  value: string
  label: string
  description?: string
  icon?: ReactNode
  disabled?: boolean
}
```

---

---

### DataTable (`data-table.tsx`)

Feature-rich data table with sorting, pagination, row selection, and custom cell rendering.

#### Basic Usage
```tsx
import { DataTable, Column } from '@/components/ui'

interface User {
  id: number
  name: string
  email: string
  role: string
}

const columns: Column<User>[] = [
  { id: 'name', header: 'Name', accessorKey: 'name' },
  { id: 'email', header: 'Email', accessorKey: 'email' },
  { id: 'role', header: 'Role', accessorKey: 'role' },
]

<DataTable
  data={users}
  columns={columns}
  getRowId={(row) => row.id}
/>
```

#### With Sorting, Pagination, and Selection
```tsx
import { DataTable, Column, SortState } from '@/components/ui'

const [sortState, setSortState] = useState<SortState>({ column: null, direction: null })
const [page, setPage] = useState(1)
const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set())

<DataTable
  data={users}
  columns={columns}
  getRowId={(row) => row.id}
  // Sorting
  sortable
  sortState={sortState}
  onSortChange={setSortState}
  // Pagination
  paginated
  page={page}
  pageSize={10}
  onPageChange={setPage}
  // Selection
  selectable
  selectedRows={selectedRows}
  onSelectionChange={setSelectedRows}
  // Styling
  hoverable
  striped
/>
```

#### Custom Cell Rendering with Helper Components
```tsx
import { 
  DataTable, 
  DataTableBadge, 
  DataTableAvatar, 
  DataTableActions, 
  DataTableActionButton 
} from '@/components/ui'
import { PencilIcon, TrashIcon } from '@heroicons/react/24/outline'

const columns: Column<User>[] = [
  {
    id: 'user',
    header: 'User',
    cell: ({ row }) => (
      <DataTableAvatar 
        name={row.name} 
        subtitle={row.email}
        src={row.avatarUrl}
      />
    ),
  },
  {
    id: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <DataTableBadge variant={row.isActive ? 'success' : 'error'}>
        {row.isActive ? 'Active' : 'Inactive'}
      </DataTableBadge>
    ),
  },
  {
    id: 'actions',
    header: '',
    align: 'right',
    cell: ({ row }) => (
      <DataTableActions>
        <DataTableActionButton
          icon={<PencilIcon className="w-4 h-4" />}
          label="Edit"
          onClick={() => handleEdit(row.id)}
        />
        <DataTableActionButton
          icon={<TrashIcon className="w-4 h-4" />}
          label="Delete"
          onClick={() => handleDelete(row.id)}
          variant="danger"
        />
      </DataTableActions>
    ),
  },
]
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `data` | `T[]` | - | Array of data to display |
| `columns` | `Column<T>[]` | - | Column definitions |
| `getRowId` | `(row: T) => string \| number` | `row.id` | Unique row identifier |
| `loading` | `boolean` | `false` | Show loading skeletons |
| `loadingRows` | `number` | `5` | Number of skeleton rows |
| `emptyMessage` | `string` | `'No data available'` | Empty state message |
| `emptyIcon` | `ReactNode` | - | Empty state icon |
| `selectable` | `boolean` | `false` | Enable row selection |
| `selectedRows` | `Set<string \| number>` | - | Selected row IDs |
| `onSelectionChange` | `(ids: Set) => void` | - | Selection change handler |
| `sortable` | `boolean` | `false` | Enable sorting |
| `sortState` | `SortState` | - | Current sort state |
| `onSortChange` | `(state: SortState) => void` | - | Sort change handler |
| `paginated` | `boolean` | `false` | Enable pagination |
| `page` | `number` | `1` | Current page (1-indexed) |
| `pageSize` | `number` | `10` | Items per page |
| `totalItems` | `number` | - | Total items (server-side pagination) |
| `onPageChange` | `(page: number) => void` | - | Page change handler |
| `onRowClick` | `(row: T) => void` | - | Row click handler |
| `compact` | `boolean` | `false` | Smaller padding |
| `striped` | `boolean` | `false` | Alternating row colors |
| `hoverable` | `boolean` | `true` | Highlight rows on hover |
| `stickyHeader` | `boolean` | `false` | Sticky table header |
| `maxHeight` | `string` | - | Max height with scroll |

**Column Definition:**
```tsx
interface Column<T> {
  id: string                          // Unique identifier
  header: string | ReactNode          // Column header
  accessorKey?: keyof T               // Simple data access
  accessorFn?: (row: T) => ReactNode  // Custom data accessor
  cell?: (props) => ReactNode         // Custom cell renderer
  sortable?: boolean                  // Enable sorting (default: true if table sortable)
  width?: string                      // Column width
  align?: 'left' | 'center' | 'right' // Text alignment
  hideOnMobile?: boolean              // Hide on small screens
}
```

---

### Styling Utilities

#### Text Selection
Custom text selection styling with Eliza brand colors.

```css
/* Light mode: soft rose highlight */
::selection {
  background-color: rgba(201, 80, 107, 0.25);
}

/* Dark mode: soft peach highlight */
.dark ::selection {
  background-color: rgba(232, 165, 152, 0.3);
}
```

---

## 3. Component Specifications

### The "Prompt Bar" (The AI Input)
*Ref: Image 3 ("Type your message here...")*
* **Container:** `12px` rounded corners.
* **Background:** `#F3F4F6` (Light Gray).
* **Input Text:** Inter, 16px, Placeholder color `#9CA3AF`.
* **Send Action:**
    * Circle button on the right side.
    * Background: **Brand Gradient** or Solid **Eliza Red** (`#BE123C`).
    * Icon: White Up Arrow (`↑`).

### The "App Card" (For the Home Grid)
* **Background:** White.
* **Border:** 1px solid transparent (normally).
* **Hover State:**
    * Transform: `translateY(-2px)` (Subtle lift).
    * Border: 1px solid `#FECDD3` (Very light pink).
    * Shadow: Increases intensity.
* **Icon:** Use an SVG icon with a subtle gradient background circle.

### Sidebar Navigation (The Hub & Spoke)
* **Global Rail (Far Left):**
    * Background: White or very light gray.
    * Icons: Charcoal (`#374151`).
    * **Active Icon:** Filled `#BE123C` (Eliza Red).
* **Context Sidebar (App Menu):**
    * **Header:** Serif Font ("Talent Search").
    * **Active Item:**
        * Text: `#BE123C` (Red).
        * Background: `#FFF1F2` (Rose 50 - very faint pink).
        * Indicator: Small vertical pink bar on the left edge.

---

## 3. Screen-by-Screen Breakdown (Ready for AI Generation)

### Screen 1: The "Home" Dashboard
* **Layout:** 60px Left Rail (Fixed) + Main Canvas.
* **Hero Section (Top 30%):**
    * **Background:** Very subtle "Sunrise Gradient" fading to white at the bottom.
    * **Text:** Serif H1 "Good morning, Eliza." (Dark Charcoal).
    * **Input:** The "Prompt Bar" centered below the text. Wide, inviting, soft shadow.
* **App Grid (Middle):**
    * Grid of white cards (Admin, Talent, Scheduler).
    * Cards have `24px` radius.
    * Icons are colorful but elegant.
* **Bottom Section:** "Recent Activity" list. Clean rows, Inter font.

### Screen 2: Talent Search App (The "Work" View)
* **Global Rail:** Persists on left.
* **App Sidebar (Next 240px):**
    * Header: "Talent Search" (Serif).
    * Menu items (Inter): "Candidates", "Shortlists", "Market Insights".
    * Background: White, separated from main content by a faint gray line.
* **Main Content:**
    * Background: `#F9FAFB` (Gray).
    * **Data Table Container:** White, `24px` radius, soft shadow. It floats in the center of the gray background (doesn't touch edges).
    * **Filters:** Pill-shaped buttons (White background, gray border).

### Screen 3: Settings (Tenant Admin)
* **Vibe:** Organized & Calm.
* **Layout:** Sidebar + Content.
* **Sidebar:** Grouped settings ("Company", "Billing", "Team").
* **Content Header:** Serif H2 "Company Settings".
* **Form Elements:**
    * Inputs: `12px` radius, light gray border.
    * Save Button: **Black Pill** (`#111827`) with "Save Changes" text.
    * Toggles: Pink (`#BE123C`) when active.

### Screen 4: Platform Admin (Superuser)
* **Differentiation:**
    * Top Bar / Header has a subtle **Red Striped pattern** or a "System Mode" badge to indicate high power.
* **Data Density:** Higher. Use smaller font size (13px Inter) for tables to fit more data.
* **Actions:** "Impersonate", "Delete", "Reset" buttons use outlined styles (White bg, Red border).

---

## 4. Prompt for AI Generators (Stitch/v0)

*Copy this block to generate your screens:*

> "Create a SaaS dashboard interface. Use a split navigation: a thin global icon rail on the left (60px) and a wider contextual sidebar (240px).
>
> **Design System:**
> * **Font:** Use 'Newsreader' serif font for the main page headers to create an editorial feel. Use 'Inter' for all UI elements.
> * **Colors:** Background is #F9FAFB. Cards are White. Primary buttons are Pill-shaped and Black (#111827). Accent color is Deep Rose (#BE123C).
> * **Styling:** Use large corner radius (24px) for main containers. Use soft, diffuse shadows.
> * **Hero Section:** Incorporate a very subtle, light pink-to-orange gradient in the background of the dashboard header.
>
> **Content:**
> * The main dashboard should feature a large, pill-shaped AI input field with a pink arrow button.
> * Below the input, show a grid of app cards (Talent Search, Scheduler, Admin) with elegant icons."

---

## 5. Component Library: shadcn/ui

### Why shadcn/ui (Not Headless UI)

| Consideration | Headless UI | shadcn/ui |
|---------------|-------------|-----------|
| **Total Components** | ~17 | **50+** |
| **Pre-styled** | ❌ Unstyled | ✅ Beautiful defaults |
| **Data Table** | ❌ | ✅ TanStack Table integration |
| **Charts** | ❌ | ✅ Recharts integration |
| **Command Palette** | ❌ | ✅ cmdk-based |
| **Sidebar** | ❌ | ✅ Pre-built |
| **Calendar/Date Picker** | ❌ | ✅ Included |
| **Ownership** | Dependency | ✅ Code copied to repo |
| **AI-friendly** | Drift-prone | ✅ Enforceable patterns |

### Installation

```bash
cd frontend
npx shadcn@latest init
```

**Configuration choices:**
- Style: **New York**
- Base color: **Neutral** (we'll customize)
- CSS variables: **Yes**
- Tailwind config: **tailwind.config.js**
- Components location: **src/components/ui**
- Utils location: **src/lib/utils**

### Core Components to Install

```bash
# Primitives (Phase 1)
npx shadcn@latest add button input textarea card badge

# Overlays (Phase 1)
npx shadcn@latest add dialog sheet popover tooltip

# Forms (Phase 2)
npx shadcn@latest add select checkbox switch label form

# Data (Phase 2)
npx shadcn@latest add table tabs accordion

# Navigation (Phase 3)
npx shadcn@latest add sidebar navigation-menu breadcrumb

# Advanced (Phase 3)
npx shadcn@latest add command calendar date-picker data-table chart
```

### Component Mapping to Our Design

| Our Component | shadcn Base | Customization |
|---------------|-------------|---------------|
| **Prompt Bar** | `Textarea` + `Button` | Custom composition |
| **App Card** | `Card` | 24px radius, hover effects |
| **Global Rail** | Custom | Icon-only nav, 60px |
| **Context Sidebar** | `Sidebar` | 240px, serif headers |
| **Data Tables** | `DataTable` | Our color tokens |
| **Modals** | `Dialog` / `Sheet` | Soft shadows |
| **Settings Forms** | `Form` + inputs | 12px radius inputs |

### Customizing for Eliza Forge

After installation, modify `frontend/src/components/ui/button.tsx`:

```tsx
// Example: Customize Button variants for our design system
const buttonVariants = cva(
  "inline-flex items-center justify-center font-medium transition-all focus-visible:outline-none focus-visible:ring-2",
  {
    variants: {
      variant: {
        // Our "Black Pill" primary
        default: "bg-charcoal text-white hover:bg-charcoal/90 rounded-full",
        // Our "Eliza Red" accent
        brand: "bg-eliza-red text-white hover:bg-eliza-red/90 rounded-full",
        // Secondary/ghost
        secondary: "bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 rounded-full",
        // Destructive outline (for Platform Admin)
        destructive: "bg-white border border-eliza-red text-eliza-red hover:bg-rose-50 rounded-full",
      },
      size: {
        default: "h-10 px-6 py-2",
        sm: "h-8 px-4 text-sm",
        lg: "h-12 px-8 text-lg",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)
```

---

## 6. Folder Structure

```
frontend/src/
├── components/
│   ├── ui/                      # ← shadcn/ui components (auto-generated)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── input.tsx
│   │   ├── sidebar.tsx
│   │   └── ... (all shadcn components)
│   │
│   ├── composites/              # ← Our custom compositions
│   │   ├── PromptBar.tsx        # AI input (Textarea + Button)
│   │   ├── AppCard.tsx          # Home grid cards
│   │   ├── ActivityFeed.tsx     # Recent activity list
│   │   ├── QuickActions.tsx     # Quick action buttons
│   │   └── index.ts
│   │
│   ├── layouts/                 # ← Page structure components
│   │   ├── GlobalRail.tsx       # 60px icon navigation
│   │   ├── ContextSidebar.tsx   # 240px app-specific nav
│   │   ├── PageShell.tsx        # Main content wrapper
│   │   ├── AppLayout.tsx        # Rail + Sidebar + Content
│   │   └── index.ts
│   │
│   ├── features/                # ← Feature-specific components
│   │   ├── talent-intelligence/
│   │   ├── business-intelligence/
│   │   ├── data-connections/
│   │   └── ...
│   │
│   └── common/                  # ← Legacy (migrate to ui/)
│       └── ... (existing components)
│
├── lib/
│   ├── utils.ts                 # shadcn utility (cn function)
│   └── tokens.ts                # Design token constants
│
├── styles/
│   └── globals.css              # CSS variables + base styles
│
└── pages/                       # ← Composition only
    ├── home/
    ├── talent/
    └── ...
```

### Import Rules

```tsx
// ✅ CORRECT: Pages import from ui/, composites/, layouts/
import { Button, Card } from "@/components/ui"
import { PromptBar, AppCard } from "@/components/composites"
import { AppLayout } from "@/components/layouts"

// ❌ WRONG: Never import Radix/shadcn internals in pages
import * as Dialog from "@radix-ui/react-dialog"  // NO!
```

---

## 7. Cursor Rules for Enforcement

Create `.cursor/rules/ui-components.mdc`:

```markdown
---
description: UI component rules for Eliza Platform
globs: ["frontend/src/**/*"]
alwaysApply: true
---

# Component Usage Rules

## 1. Use shadcn/ui Primitives

Always import UI primitives from `@/components/ui`:
- Button, Input, Textarea, Card, Badge
- Dialog, Sheet, Popover, Tooltip
- Select, Checkbox, Switch, Label
- Table, Tabs, Accordion
- Sidebar, NavigationMenu, Breadcrumb

```tsx
// ✅ CORRECT
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardContent } from "@/components/ui/card"

// ❌ WRONG - creating custom buttons
<button className="bg-blue-500 px-4 py-2 rounded">Click me</button>

// ❌ WRONG - importing Radix directly in pages
import * as Dialog from "@radix-ui/react-dialog"
```

## 2. Use Our Compositions

For complex patterns, use pre-built compositions from `@/components/composites`:
- PromptBar - AI chat input
- AppCard - Home dashboard cards
- ActivityFeed - Recent activity list
- QuickActions - Quick action buttons

## 3. Use Our Layouts

All pages must use layout components from `@/components/layouts`:
- AppLayout - Main app shell (Rail + Sidebar + Content)
- GlobalRail - 60px icon navigation
- ContextSidebar - 240px app menu
- PageShell - Content area wrapper

## 4. Design Token Rules

Use CSS variables for all colors, not hardcoded values:

```tsx
// ✅ CORRECT - uses design tokens
className="bg-canvas text-charcoal border-border"
className="bg-eliza-red text-white"

// ❌ WRONG - hardcoded colors
className="bg-[#F9FAFB] text-[#111827]"
className="bg-red-600"
```

## 5. Typography Rules

- Headings (H1, H2): Use `font-serif` (Newsreader/Playfair)
- Body/UI text: Use `font-sans` (Inter)

```tsx
// ✅ CORRECT
<h1 className="font-serif text-4xl">Good morning, Eliza.</h1>
<p className="font-sans text-sm">Manage your workflows</p>

// ❌ WRONG - wrong font for heading
<h1 className="font-sans text-4xl">Dashboard</h1>
```

## 6. Radius Rules

- Outer containers: `rounded-3xl` (24px)
- Cards/inputs: `rounded-xl` (12px)
- Buttons: `rounded-full` (pill shape)

## 7. New Component Guidelines

Before creating a new component:
1. Check if it exists in `@/components/ui`
2. Check if it exists in `@/components/composites`
3. If truly new and reusable (used 2+ times), add to appropriate folder with Storybook story
4. If one-off, create in the feature folder
```

---

## 8. Storybook Documentation

### Setup

```bash
cd frontend
npx storybook@latest init
```

### Story Structure

Every component in `ui/` and `composites/` MUST have a story:

```tsx
// components/ui/button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './button'

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'brand', 'secondary', 'destructive'],
    },
    size: {
      control: 'select', 
      options: ['default', 'sm', 'lg', 'icon'],
    },
  },
}
export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: {
    variant: 'default',
    children: 'Get Started',
  },
}

export const Brand: Story = {
  args: {
    variant: 'brand',
    children: 'Contact Us',
  },
}

export const Secondary: Story = {
  args: {
    variant: 'secondary',
    children: 'Cancel',
  },
}

export const Destructive: Story = {
  args: {
    variant: 'destructive',
    children: 'Delete Account',
  },
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex gap-4">
      <Button variant="default">Primary</Button>
      <Button variant="brand">Brand</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  ),
}
```

### Composite Stories

```tsx
// components/composites/PromptBar.stories.tsx
import type { Meta, StoryObj } from '@storybook/react'
import { PromptBar } from './PromptBar'

const meta: Meta<typeof PromptBar> = {
  title: 'Composites/PromptBar',
  component: PromptBar,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
}
export default meta
type Story = StoryObj<typeof PromptBar>

export const Default: Story = {
  args: {
    placeholder: 'Describe the workflow you need...',
  },
}

export const WithSuggestions: Story = {
  args: {
    placeholder: 'Describe the workflow you need...',
    suggestions: ['Create job spec', 'Search talent pool', 'Pipeline analytics'],
  },
}

export const Loading: Story = {
  args: {
    placeholder: 'Describe the workflow you need...',
    isLoading: true,
  },
}
```

### Running Storybook

```bash
npm run storybook        # Development
npm run build-storybook  # Production build
```

---

## 9. Migration Plan

> **🚨 CRITICAL RULE: Always Use Common UI Components**
> 
> Before building ANY visual element on a page:
> 1. **Check if a common component exists** in `@/components/ui`
> 2. **If it exists** → Use it. Do not create a custom version.
> 3. **If it needs modification** → Update the common component, not a page-specific copy.
> 4. **If truly custom** → Only then create in the feature folder, and consider if it should be promoted to common later.
> 
> This ensures consistency, reduces code duplication, and keeps the design system as the single source of truth.

### ✅ Phase 1: Foundation (COMPLETE)

**Status:** ✅ Done

- [x] Install and configure shadcn/ui patterns
- [x] Set up CSS variables for design tokens in `globals.css`
- [x] Create 50+ core components (Button, Input, Card, Modal, etc.)
- [x] Set up Component Showcase page at `/design-system/showcase`
- [x] Add Cursor rules file
- [x] Implement dark mode support
- [x] Create chat components (MessageBubble, ThinkingIndicator, CanvasPanel)
- [x] Create navigation components (Breadcrumb, Pagination, Combobox)

---

### 🚀 Phase 2: Pilot Migration - Platform Admin Settings

**Goal:** Validate the design system by fully migrating one page.

**Target:** Platform Admin Settings page (`/platform-admin/settings` or similar)

**Why this page:**
- Contains forms, inputs, toggles, cards - exercises many components
- Lower traffic/risk than core feature pages
- Validates the component library in production context

**Process for each UI element:**

```
┌─────────────────────────────────────────────────────────┐
│  For each visual element on the page:                   │
│                                                         │
│  1. Is there a common component in @/components/ui?     │
│     ├── YES → Use it directly                           │
│     └── NO  → Go to step 2                              │
│                                                         │
│  2. Is this a modification of an existing component?    │
│     ├── YES → Update the common component               │
│     └── NO  → Go to step 3                              │
│                                                         │
│  3. Is this reusable (will be used 2+ times)?           │
│     ├── YES → Create in @/components/ui                 │
│     └── NO  → Create in feature folder                  │
└─────────────────────────────────────────────────────────┘
```

**Checklist:**
- [ ] Audit existing Platform Admin Settings page
- [ ] Map each UI element to common components
- [ ] Identify gaps (components we're missing)
- [ ] Fill gaps by updating/creating common components
- [ ] Migrate the page using only common components
- [ ] Test in both light and dark mode
- [ ] Verify accessibility (keyboard nav, focus states)

---

### Phase 3: Feature-by-Feature Migration

**After pilot is validated, migrate in this order:**

#### 3a. Tenant Admin Pages
- [ ] Tenant Settings
- [ ] User Management
- [ ] Role/Permissions

#### 3b. Data Connections
- [ ] Connection List
- [ ] Create/Edit Connection Modal
- [ ] Connection Status Cards

#### 3c. Business Intelligence
- [ ] Question History
- [ ] Question Detail View
- [ ] Chat Interface

#### 3d. Talent Intelligence
- [ ] Analysis Config
- [ ] Candidate Search/Results
- [ ] Candidate Outreach
- [ ] Email Templates
- [ ] Feedback Dashboard

#### 3e. Home / Dashboard
- [ ] App Grid Cards
- [ ] PromptBar integration
- [ ] Activity Feed

---

### Phase 4: Layout & Navigation Overhaul

**Goal:** Update the global navigation structure.

- [ ] Migrate GlobalRail to use new Sidebar components
- [ ] Migrate ContextSidebar to use SidebarProvider pattern
- [ ] Update AppLayout wrapper
- [ ] Ensure collapse/expand works consistently

---

### Phase 5: Cleanup & Polish

- [ ] Remove legacy `components/common/` folder
- [ ] Remove unused Headless UI imports
- [ ] Final accessibility audit
- [ ] Performance check (bundle size)
- [ ] Update this documentation with any new components added

---

### Components to Add During Migration (As Needed)

| Component | When Needed | Priority | Status |
|-----------|-------------|----------|--------|
| DataTable | Data-heavy list pages | High | ✅ Done |
| CommandPalette | Global Cmd+K search | Medium | Pending |
| Sheet | Side panel detail views | Medium | Pending |
| Stepper | Multi-step forms | Low | Pending |
| Timeline | Activity/history views | Low | Pending |

---

## 10. Developer Guidelines

### Adding a New Page

1. **Use the layout:**
```tsx
import { AppLayout } from '@/components/layouts'

export function MyNewPage() {
  return (
    <AppLayout 
      rail={/* optional override */}
      sidebar={<MySidebar />}
    >
      <PageContent />
    </AppLayout>
  )
}
```

2. **Use existing components:**
```tsx
import { Button, Card, Input } from '@/components/ui'
import { PromptBar } from '@/components/composites'
```

3. **Follow typography rules:**
```tsx
<h1 className="font-serif text-4xl">Page Title</h1>
<p className="font-sans text-muted-foreground">Description</p>
```

### Adding a New Reusable Component

1. **Check if shadcn has it:**
```bash
npx shadcn@latest add [component-name]
```

2. **If custom, add to the right folder:**
   - Primitive (Button, Input) → `ui/` (rare, shadcn usually has it)
   - Composition (PromptBar, AppCard) → `composites/`
   - Feature-specific → `features/[feature]/`

3. **Create Storybook story:**
```tsx
// component.stories.tsx alongside component.tsx
```

4. **Export from index:**
```tsx
// composites/index.ts
export { PromptBar } from './PromptBar'
export { AppCard } from './AppCard'
```

### PR Checklist

- [ ] Uses only `@/components/ui/*` primitives
- [ ] No hardcoded colors (uses design tokens)
- [ ] Correct typography (serif for headings, sans for body)
- [ ] Storybook story added/updated for new components
- [ ] No direct Radix imports outside `ui/` folder

---

## Appendix: Design Tokens

### Tailwind Config Colors (in `tailwind.config.js`)

```js
colors: {
  // Brand Colors (Eliza Forge Palette)
  'eliza-red': {
    DEFAULT: '#c9506b',   // Primary rose - buttons, logo, main accent
    light: '#e8a598',     // Warm salmon - hover states, secondary
    coral: '#f5c4a1',     // Peachy cream - gradients, warm highlights
  },
  
  // Text
  charcoal: '#5c4a5a',    // Muted charcoal with purple tint
  
  // Surfaces
  canvas: '#F9FAFB',
  'dark-bg': '#0f0f0f',
  'dark-surface': '#1a1a1a',
  'dark-surface-2': '#242424',
}
```

### Font Families (in `tailwind.config.js`)

```js
fontFamily: {
  sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
  title: ['Libre Baskerville', 'Georgia', 'serif'],
  subtitle: ['Hedvig Letters Serif', 'Georgia', 'serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
}
```

### Google Fonts (in `public/index.html`)

```html
<!-- Inter -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<!-- Libre Baskerville (Title) -->
<link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">

<!-- Hedvig Letters Serif (Subtitle) -->
<link href="https://fonts.googleapis.com/css2?family=Hedvig+Letters+Serif:opsz@12..24&display=swap" rel="stylesheet">
```

### Gradient Utility

```css
.bg-brand-gradient {
  background: linear-gradient(135deg, #b11e4c 0%, #dd6c66 50%, #ed6545 100%);
}
```

---

## Quick Reference

| Need to... | Do this... |
|------------|------------|
| Add a button | `import { Button } from '@/components/ui'` |
| Add a modal | `import { Modal, ModalContent, ... } from '@/components/ui'` |
| Add a dropdown | `import { Select, SelectOption } from '@/components/ui'` |
| Add multi-select | `import { MultiSelect, MultiSelectOption } from '@/components/ui'` |
| Add tabs | `import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui'` |
| Add an accordion | `import { Accordion, AccordionItem, ... } from '@/components/ui'` |
| Add a dropdown menu | `import { DropdownMenu, DropdownTrigger, ... } from '@/components/ui'` |
| Add radio buttons | `import { RadioGroup, RadioGroupItem } from '@/components/ui'` |
| Add a date picker | `import { DatePicker } from '@/components/ui'` |
| Add a date range picker | `import { DateRangePicker } from '@/components/ui'` |
| Create AI input | `import { PromptBar } from '@/components/ui'` |
| Create AI input with files | `import { PromptBarWithAttachments } from '@/components/ui'` |
| Create AI input with tools | `import { PromptBarWithTools } from '@/components/ui'` |
| Add a tooltip | `import { Tooltip } from '@/components/ui'` |
| Add a toast notification | `import { useToast, ToastContainer } from '@/components/ui'` |
| Add an alert banner | `import { Alert } from '@/components/ui'` |
| Add a loading spinner | `import { Spinner, LoadingOverlay } from '@/components/ui'` |
| Add skeleton loading | `import { Skeleton, SkeletonCard } from '@/components/ui'` |
| Add a progress bar | `import { Progress, CircularProgress } from '@/components/ui'` |
| Add chips/tags | `import { Chip, ChipGroup } from '@/components/ui'` |
| Add avatars | `import { Avatar, AvatarGroup } from '@/components/ui'` |
| Add a metric card | `import { MetricCard } from '@/components/ui'` |
| Add a content card | `import { ContentCard, ImageCard, LinkCard } from '@/components/ui'` |
| Build a sidebar | `import { Sidebar, SidebarItem, ... } from '@/components/ui'` |
| Build a collapsible sidebar | `import { SidebarProvider, Sidebar, ... } from '@/components/ui'` |
| Get sidebar collapse state | `const { collapsed, toggleCollapsed } = useSidebar()` |
| Add tenant switcher | `import { TenantSwitcher } from '@/components/ui'` |
| Add breadcrumbs | `import { Breadcrumb, BreadcrumbItem } from '@/components/ui'` |
| Add pagination | `import { Pagination, SimplePagination } from '@/components/ui'` |
| Add searchable dropdown | `import { Combobox } from '@/components/ui'` |
| Add multi-select search | `import { MultiCombobox } from '@/components/ui'` |
| Build chat interface | `import { ChatProvider, ChatContainer, MessageBubble } from '@/components/ui'` |
| Add thinking indicator | `import { ThinkingIndicator } from '@/components/ui'` |
| Add code block in chat | `import { ChatCodeBlock } from '@/components/ui'` |
| Add canvas panel | `import { CanvasPanel, useChat } from '@/components/ui'` |
| Add data table | `import { DataTable, Column } from '@/components/ui'` |
| Add table with helpers | `import { DataTable, DataTableBadge, DataTableAvatar, DataTableActions } from '@/components/ui'` |
| Preview all components | Navigate to `/design-system/showcase` |
| See design tokens | Check `frontend/src/index.css` and `tailwind.config.js` |

---

## Component Import Cheatsheet

All components are exported from the central index file:

```tsx
// Import from the index
import { 
  // Form
  Button, Input, Textarea, Checkbox, Switch, Label,
  Select, SelectOption, SelectGroup,
  MultiSelect, MultiSelectOption, MultiSelectGroup,
  RadioGroup, RadioGroupItem, RadioCard,
  
  // Display
  Card, CardHeader, CardTitle, CardContent, CardFooter,
  MetricCard, StatCard, ProgressCard, ImageCard, ContentCard, LinkCard,
  Badge, Chip, ChipGroup,
  Avatar, AvatarGroup,
  Separator, Skeleton,
  Progress, CircularProgress,
  
  // Feedback
  Alert, Toast, ToastContainer, useToast,
  Spinner, LoadingOverlay,
  Tooltip,
  
  // Overlay
  Modal, ModalContent, ModalHeader, ModalTitle, ModalBody, ModalFooter,
  DropdownMenu, DropdownTrigger, DropdownContent, DropdownItem,
  
  // Navigation
  Tabs, TabsList, TabsTrigger, TabsContent,
  Accordion, AccordionItem, AccordionTrigger, AccordionContent,
  SidebarProvider, useSidebar,
  Sidebar, SidebarCollapseTrigger, SidebarHeader, SidebarLogo,
  SidebarContent, SidebarSection, SidebarItem, SidebarSubItem,
  SidebarAction, SidebarLabel, SidebarLink, SidebarFooter, SidebarSeparator,
  TenantSwitcher,
  Breadcrumb, BreadcrumbItem, BreadcrumbEllipsis,
  Pagination, SimplePagination,
  Combobox, MultiCombobox,
  
  // Date
  Calendar, DatePicker, DateRangePicker,
  
  // AI Input
  PromptBar, PromptBarWithAttachments, PromptBarWithTools,
  
  // Chat
  ChatProvider, useChat,
  ChatContainer, ChatMessagesPane, ChatScrollArea, ChatInputArea,
  MessageBubble, MessageContent,
  ThinkingIndicator,
  ChatImage, ChatCodeBlock,
  CanvasPanel, ArtifactButton,
  
  // Data Table
  DataTable,
  DataTableCell, DataTableBadge, DataTableAvatar,
  DataTableActions, DataTableActionButton,
} from '@/components/ui'
```
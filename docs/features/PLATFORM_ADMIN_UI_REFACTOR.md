# Platform Admin UI Refactoring Specification

> Streamlining the Platform Admin experience with sub-navigation, consistent breadcrumbs, and unified page layouts.

## ✅ Implementation Status

**All phases completed on January 5, 2026**

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Done | Foundation components (Breadcrumbs, SubNav, AdminShell) |
| Phase 2 | ✅ Done | Tenant Management section migration |
| Phase 3 | ✅ Done | Platform Settings uses AdminShell (tabs kept) |
| Phase 4 | ✅ Done | Cleanup, redirects, unused imports removed |

---

## 📋 Overview

### Problem Statement

The current Platform Admin pages are **disjointed**:
1. Each page has its own breadcrumb implementation (inconsistent)
2. Navigation is flat - 4 separate items with no logical grouping
3. Pages have different layouts and header styles
4. No unified admin shell component

### Goals

1. **Consistent Breadcrumbs** - Reusable breadcrumb component on all admin pages
2. **Sub-Navigation Pattern** - Each section has its own vertical sub-nav
3. **Unified Admin Shell** - Single wrapper component for all admin pages
4. **Logical Grouping** - Related pages grouped under parent sections
5. **Zero Breaking Changes** - All existing functionality must remain intact

---

## 🎨 Current State Analysis

### Navigation Structure (Current)

```
PLATFORM ADMIN (sidebar section)
├── Tenant Management      → /platform-admin/tenants
├── Feature Allocation     → /platform-admin/features  
├── Platform Settings      → /platform-admin/settings
└── Adoption Access        → /platform-admin/adoption
```

**Problems:**
- 4 flat items, no hierarchy
- Feature Allocation is tenant-related but separate
- Adoption Access is tenant-related but separate
- Platform Settings has tabs inside (Email, Providers, Admins)

---

## 🏗️ Proposed Architecture

### 1. Simplified Left Nav

**Sidebar (2 items only):**

```
PLATFORM ADMIN
├── 🏢 Tenant Management      → /platform-admin/tenants
└── ⚙️ Platform Settings      → /platform-admin/settings
```

### 2. Sub-Navigation Pattern

Each section has a **vertical sub-nav inside the page content area**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Breadcrumbs: Platform Admin > Tenant Management                         │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────┬──────────────────────────────────────────────────┐ │
│ │ SUB-NAV          │  MAIN CONTENT                                    │ │
│ │                  │                                                  │ │
│ │ • Tenants ←      │  (Tenant list, create button, etc.)              │ │
│ │   Feature Alloc  │                                                  │ │
│ │   Adoption Access│                                                  │ │
│ │                  │                                                  │ │
│ └──────────────────┴──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3. Route Structure

**Tenant Management Section:**
| Sub-Nav Item | Route | Description |
|--------------|-------|-------------|
| Tenants (default) | `/platform-admin/tenants` | Tenant list, create tenant |
| Feature Allocation | `/platform-admin/tenants/features` | Allocate features to tenants |
| Adoption Access | `/platform-admin/tenants/adoption` | Cross-tenant data sharing |

**Platform Settings Section:**
| Sub-Nav Item | Route | Description |
|--------------|-------|-------------|
| Admin Management (default) | `/platform-admin/settings` | Platform admin users |
| AI Providers | `/platform-admin/settings/providers` | LLM provider configs |
| Email Integration | `/platform-admin/settings/email` | Google OAuth setup |
| Job Scheduler | `/platform-admin/settings/jobs` | Celery task management (placeholder) |

### 4. Reusable Components

#### Breadcrumbs Component

```tsx
// frontend/src/components/common/Breadcrumbs.tsx

interface BreadcrumbItem {
  label: string;
  path?: string;      // If undefined, not clickable (current page)
  icon?: React.ComponentType<{ className?: string }>;
}

// Usage:
<Breadcrumbs items={[
  { label: 'Platform Admin', path: '/platform-admin/tenants', icon: ShieldCheckIcon },
  { label: 'Tenant Management' },
]} />
```

#### SubNav Component

```tsx
// frontend/src/components/layout/SubNav.tsx

interface SubNavItem {
  label: string;
  path: string;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: string | number;
}

interface SubNavProps {
  items: SubNavItem[];
  title?: string;
}

// Usage:
<SubNav 
  title="Tenant Management"
  items={[
    { label: 'Tenants', path: '/platform-admin/tenants', icon: BuildingIcon },
    { label: 'Feature Allocation', path: '/platform-admin/tenants/features', icon: ShieldIcon },
    { label: 'Adoption Access', path: '/platform-admin/tenants/adoption', icon: ChartIcon },
  ]}
/>
```

#### AdminShell Layout Component

```tsx
// frontend/src/components/layout/AdminShell.tsx

interface AdminShellProps {
  title: string;
  subtitle?: string;
  icon?: React.ComponentType<{ className?: string }>;
  breadcrumbs: BreadcrumbItem[];
  subNavItems: SubNavItem[];      // Sub-navigation items
  subNavTitle?: string;           // Sub-nav section title
  actions?: React.ReactNode;      // Header actions (buttons, etc.)
  children: React.ReactNode;
}

// Usage:
<AdminShell
  title="Tenant Management"
  subtitle="Create and manage customer organizations"
  icon={BuildingOfficeIcon}
  breadcrumbs={[
    { label: 'Platform Admin', path: '/platform-admin/tenants' },
    { label: 'Tenant Management' },
  ]}
  subNavItems={tenantSubNavItems}
  actions={<Button>+ Create Tenant</Button>}
>
  {/* Page content */}
</AdminShell>
```

---

## 📁 File Structure Changes

### New Files to Create

```
frontend/src/components/
├── common/
│   └── Breadcrumbs.tsx          # Reusable breadcrumb component
├── layout/
│   ├── AdminShell.tsx           # Unified admin page wrapper with sub-nav
│   └── SubNav.tsx               # Vertical sub-navigation component
└── navigation/
    └── platformAdminNav.ts      # Sub-nav configurations
```

### Pages to Refactor

```
frontend/src/pages/platform-admin/
├── tenants/                     # Tenant Management section
│   ├── TenantListPage.tsx       # MOVE: From TenantManagementPage.tsx
│   ├── FeatureAllocationPage.tsx# MOVE: Keep existing, add AdminShell
│   └── AdoptionAccessPage.tsx   # MOVE: From /platform-admin/adoption
├── settings/                    # Platform Settings section
│   ├── AdminManagementPage.tsx  # EXTRACT: From PlatformSettingsPage
│   ├── ProvidersPage.tsx        # EXTRACT: From PlatformSettingsPage
│   ├── EmailIntegrationPage.tsx # EXTRACT: From PlatformSettingsPage
│   └── JobSchedulerPage.tsx     # NEW: Placeholder for Phase 10
└── index.tsx                    # Redirect /platform-admin → /platform-admin/tenants
```

### Files to Remove (after migration)

```
frontend/src/pages/platform-admin/
├── TenantManagementPage.tsx     # Replaced by tenants/TenantListPage.tsx
├── PlatformSettingsPage.tsx     # Split into settings/*
└── AdoptionAccessPage.tsx       # Moved to tenants/
```

---

## 🎯 Implementation Plan

### Phase 1: Foundation Components (No Breaking Changes) ✅ DONE

**Goal:** Create new components without modifying existing pages.

1. **Create `Breadcrumbs.tsx`**
   - Standalone component
   - Consistent styling with existing theme
   - Accessibility compliant (aria-labels)

2. **Create `SubNav.tsx`**
   - Vertical sub-navigation component
   - Active state detection via route
   - Icons and optional badges
   - Consistent styling

3. **Create `AdminShell.tsx`**
   - Wrapper component combining:
     - Breadcrumbs (top)
     - Header with title, subtitle, icon, actions
     - SubNav (left side)
     - Content area (right side, scrollable)

### Phase 2: Tenant Management Section ✅ DONE

**Goal:** Migrate tenant-related pages to use AdminShell with sub-nav.

1. **Create `tenants/` directory structure**
2. **Move TenantManagementPage → tenants/TenantListPage.tsx**
3. **Move FeatureAllocationPage → tenants/FeatureAllocationPage.tsx**
4. **Move AdoptionAccessPage → tenants/AdoptionAccessPage.tsx**
5. **Update each to use AdminShell with sub-nav**
6. **Update sidebar Navigation.tsx** - Remove Feature Allocation & Adoption Access items

**Sub-Nav Items:**
| Label | Route | Default |
|-------|-------|---------|
| Tenants | `/platform-admin/tenants` | ✅ Yes |
| Feature Allocation | `/platform-admin/tenants/features` | |
| Adoption Access | `/platform-admin/tenants/adoption` | |

### Phase 3: Platform Settings Section ✅ DONE

**Goal:** Update Platform Settings to use AdminShell with sub-nav (tabs kept for now).

1. **Create `settings/` directory structure**
2. **Extract Admin Management → settings/AdminManagementPage.tsx**
3. **Extract AI Providers → settings/ProvidersPage.tsx**
4. **Extract Email Integration → settings/EmailIntegrationPage.tsx**
5. **Create placeholder → settings/JobSchedulerPage.tsx**
6. **Update each to use AdminShell with sub-nav**
7. **Redirect `/platform-admin/settings` → `/platform-admin/settings/admins`**

**Sub-Nav Items:**
| Label | Route | Default |
|-------|-------|---------|
| Admin Management | `/platform-admin/settings` | ✅ Yes |
| AI Providers | `/platform-admin/settings/providers` | |
| Email Integration | `/platform-admin/settings/email` | |
| Job Scheduler | `/platform-admin/settings/jobs` | Placeholder |

### Phase 4: Cleanup & Polish ✅ DONE

1. **Removed unused imports** (PlatformAdminsPage)
2. **Added redirects** for old routes:
   - `/platform-admin/features` → `/platform-admin/tenants/features`
   - `/platform-admin/adoption` → `/platform-admin/tenants/adoption`
   - `/platform-admin/admins` → `/platform-admin/settings`
3. **Update any deep links** in other parts of the app
4. **Test all functionality** - modals, forms, API calls

---

## 🎨 Visual Design

### Breadcrumb Style

```
┌─────────────────────────────────────────────────────────────┐
│ 🛡️ Platform Admin  ›  Tenant Management  ›  Feature Alloc  │
└─────────────────────────────────────────────────────────────┘

- Icon on first item only
- Chevron separator (›)
- Last item is bold, not a link
- Subtle hover states on clickable items
```

### Left Sidebar (Simplified)

```
PLATFORM ADMIN
┌─────────────────────────────────┐
│ 🏢 Tenant Management            │  ← Active when in /tenants/*
├─────────────────────────────────┤
│ ⚙️ Platform Settings            │  ← Active when in /settings/*
└─────────────────────────────────┘

- Only 2 top-level items
- Active state shows which section you're in
- Simple, clean
```

### Page Layout with Sub-Nav

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🛡️ Platform Admin › Tenant Management                                  │ ← Breadcrumbs
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ 🏢 Tenant Management                              [+ Create Tenant] │ │ ← Header
│ │    Create and manage customer organizations                         │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
├───────────────────┬─────────────────────────────────────────────────────┤
│ SUB-NAV           │  CONTENT                                            │
│                   │                                                     │
│ • Tenants    ←    │  ┌─────────────────────────────────────────────┐   │
│   Feature Alloc   │  │  Search tenants...                          │   │
│   Adoption Access │  ├─────────────────────────────────────────────┤   │
│                   │  │  TENANT         ID        ADMIN    STATUS   │   │
│                   │  │  ─────────────────────────────────────────  │   │
│                   │  │  Steve Org      steve-org  Steven   Active  │   │
│                   │  │  Platform       platform   —        Active  │   │
│                   │  │  Caylent        caylent    dev@     Active  │   │
│                   │  │  Eliza          eliza      —        Active  │   │
│                   │  └─────────────────────────────────────────────┘   │
│                   │                                                     │
└───────────────────┴─────────────────────────────────────────────────────┘

Sub-Nav (left):
- Fixed width (~180-200px)
- Vertical list of sub-pages
- Active item has accent color + bullet
- Subtle hover states
- Border-right separating from content

Content (right):
- Flexible width
- Scrollable
- Contains the actual page content
```

### Sub-Nav Component Design

```
┌─────────────────────┐
│ TENANT MANAGEMENT   │  ← Section title (optional)
├─────────────────────┤
│ • Tenants           │  ← Active: bullet, bold, accent color
│   Feature Alloc     │  ← Inactive: normal text, hover state
│   Adoption Access   │
└─────────────────────┘

- Minimal, clean design
- Clear active state
- Icons optional (depends on content)
- Matches sidebar styling
```

---

## ✅ Acceptance Criteria

### Must Have

- [ ] All existing routes continue to work (with redirects if needed)
- [ ] All existing functionality preserved
- [ ] Breadcrumbs on every platform admin page
- [ ] Sub-nav on Tenant Management pages
- [ ] Sub-nav on Platform Settings pages
- [ ] Consistent page headers via AdminShell
- [ ] Sidebar reduced to 2 items (Tenant Management, Platform Settings)

### Should Have

- [ ] Smooth transitions when switching sub-nav items
- [ ] Active state clearly visible in sub-nav
- [ ] Mobile-responsive (sub-nav collapses or stacks)

### Nice to Have

- [ ] Keyboard navigation for sub-nav (arrow keys)
- [ ] Persist last-visited sub-page per section

---

## 🔒 Risk Mitigation

### Breaking Change Prevention

1. **Route Preservation**
   - Keep all existing routes working
   - Add new routes as needed, don't replace
   - Use redirects for any route changes

2. **Incremental Migration**
   - Migrate one page at a time
   - Test thoroughly before moving to next
   - Feature flag if needed

3. **Styling Isolation**
   - New components use scoped classes
   - Don't modify global CSS
   - Test in both light and dark mode

### Testing Strategy

1. **Before Each Migration:**
   - Screenshot existing page
   - Document all interactive elements
   - List all API calls made

2. **After Each Migration:**
   - Compare screenshots
   - Verify all interactions work
   - Confirm API calls unchanged

---

## 📊 Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Breadcrumb consistency | ~25% (1/4 pages) | 100% |
| Sidebar items (Platform Admin) | 4 items | 2 items |
| Shared layout code | 0% | 90%+ |
| Largest page file | 1600+ lines | ~400 lines |
| Code reuse via AdminShell | 0 pages | All pages |

---

## 🗓️ Estimated Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | 1 day | Foundation components (Breadcrumbs, SubNav, AdminShell) |
| Phase 2 | 1-2 days | Tenant Management section migration |
| Phase 3 | 1-2 days | Platform Settings section split |
| Phase 4 | 0.5 day | Cleanup, redirects, testing |
| **Total** | **3-5 days** | Full refactor |

---

## 📝 Notes

- This refactor sets the foundation for Phase 10 (Job Scheduler)
- Same pattern (AdminShell + SubNav) can be applied to Tenant Admin section later
- AdminShell component becomes the standard for all admin-type pages
- Job Scheduler placeholder ensures route structure is ready for Phase 10

---

## 🔄 Route Migration Summary

| Old Route | New Route | Redirect? |
|-----------|-----------|-----------|
| `/platform-admin/tenants` | `/platform-admin/tenants` | Same |
| `/platform-admin/features` | `/platform-admin/tenants/features` | ✅ Yes |
| `/platform-admin/adoption` | `/platform-admin/tenants/adoption` | ✅ Yes |
| `/platform-admin/settings` | `/platform-admin/settings` | Same (shows Admin Management) |
| — | `/platform-admin/settings/providers` | New |
| — | `/platform-admin/settings/email` | New |
| — | `/platform-admin/settings/jobs` | New (placeholder) |

---

**Version:** 2.0  
**Created:** 2026-01-05  
**Updated:** 2026-01-05  
**Status:** Draft - Awaiting Approval


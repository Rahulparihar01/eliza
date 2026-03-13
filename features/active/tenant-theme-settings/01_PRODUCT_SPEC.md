# Product Requirements Document
## Tenant Theme Settings

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft |
| **Last Updated** | January 23, 2026 |
| **Product Owner** | Steven McAteer |
| **Engineering Lead** | TBD |

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [Target Users](#target-users)
5. [User Stories](#user-stories)
6. [Feature Details](#feature-details)
7. [Technical Requirements](#technical-requirements)
8. [Dependencies](#dependencies)
9. [Acceptance Criteria](#acceptance-criteria)
10. [Success Metrics](#success-metrics)
11. [Open Questions](#open-questions)
12. [Appendix](#appendix)

---

## Executive Summary

Enable tenant administrators to customize the Eliza Forge color scheme/theme for their organization. This allows each tenant to apply their own brand colors to the platform UI, creating a white-label experience. Theme settings are scoped to the tenant and persist across user sessions.

---

## Problem Statement

### Current State Challenges

| Challenge | Impact |
|-----------|--------|
| All tenants see the same default Eliza Forge branding | No brand differentiation for enterprise customers |
| Theme customization only exists as a demo on the `/design-system` page with no persistence | Changes are lost on page refresh |
| No ability for tenant admins to manage visual appearance | Limits white-label/enterprise appeal |

### The Opportunity

- **Enterprise value**: White-label theming is a common enterprise requirement that increases stickiness
- **Brand consistency**: Organizations can align Eliza Forge with their internal brand guidelines
- **Differentiation**: Creates a more personalized, premium experience for each tenant

---

## Goals and Non-Goals

### Goals (P0/P1/P2)

| Priority | Goal |
|----------|------|
| **P0** | Tenant admins can set primary, primary-light, accent, and text colors |
| **P0** | Theme settings persist in the database and apply across all users in the tenant |
| **P0** | Theme loads automatically on login/page refresh |
| **P1** | Quick-apply brand presets (Ocean Blue, Forest Green, Royal Purple, etc.) |
| **P1** | Reset to default Eliza Forge theme button |
| **P1** | Live preview of theme changes before saving |
| **P2** | Custom logo upload (tenant logo instead of elizaforge branding) |
| **P2** | Dark mode theme variants (separate colors for dark mode) |

### Non-Goals (Out of Scope)

| Item | Rationale |
|------|-----------|
| User-level theme preferences | This is tenant-scoped, not per-user |
| Custom fonts | Typography is part of design system consistency |
| Custom component styling | Only brand colors, not component behavior |
| CSS injection/arbitrary styles | Security and maintainability concerns |

---

## Target Users

### Primary Users

#### User Type 1: Tenant Administrator
- **Who they are:** Customer administrators who manage their organization's Eliza Forge settings
- **What they need:** Ability to customize the platform appearance to match their company brand
- **How they'll use this:** Access Theme settings page, pick colors or presets, save, and verify changes

#### User Type 2: Platform End Users (Indirect)
- **Who they are:** Regular users within a tenant organization
- **What they need:** Consistent brand experience when using Eliza Forge
- **How they'll use this:** Passively—they see the theme their admin configured

### Secondary Users

- **Platform Admins (Eliza team):** May need to reset or manage tenant themes in edge cases
- **Sales/CS Teams:** Demo white-label capability to prospects

---

## User Stories

### Epic: Theme Customization

**US-001:** As a tenant admin, I want to access a Theme settings page so that I can customize my organization's color scheme.

**US-002:** As a tenant admin, I want to pick custom brand colors (primary, primary-light, accent, text) using color pickers so that I can match our company branding.

**US-003:** As a tenant admin, I want to choose from preset color themes so that I can quickly apply a cohesive look without manual color selection.

**US-004:** As a tenant admin, I want to see a live preview of my theme changes so that I can verify the look before saving.

**US-005:** As a tenant admin, I want to reset to the default Eliza Forge theme so that I can undo customizations.

**US-006:** As a tenant user, I want the theme to load automatically when I log in so that I see my organization's branding immediately.

### Epic: Theme Persistence

**US-007:** As a tenant admin, I want my theme settings to persist in the database so that all users in my tenant see the same theme.

**US-008:** As a system, I want to serve cached theme settings efficiently so that page loads are not slowed by theme retrieval.

---

## Feature Details

### Feature 1: Theme Settings Page

**Location:** `/tenant-admin/theme`

**UI Design:**
- Mimic the Theme Customizer section from `/design-system` page
- Card-based layout with:
  - **Left column:** Color pickers for Primary, Primary Light, Accent, Text
  - **Right column:** Brand Presets grid (clickable preset buttons)
  - **Bottom:** Live Preview bar showing how buttons, badges, and accents look
  - **Footer:** Save and Reset buttons

**User Flow:**
1. Tenant admin navigates to `/tenant-admin/theme` via Admin Settings sidebar
2. Current theme values are loaded from database
3. Admin adjusts colors via pickers or selects a preset
4. Live preview updates in real-time (local state, no API calls)
5. Admin clicks "Save Theme" to persist changes
6. Success toast confirms save
7. Theme CSS variables update globally

**UI/UX Considerations:**
- Use existing DS components: `Card`, `CardHeader`, `CardContent`, `Button`, `Label`, `Input`
- Color pickers can use native HTML `<input type="color">` + hex input (as in design-system page)
- Must work in both light and dark mode
- Permission check: Only users with `theme:write` permission can access

### Feature 2: Theme API Endpoints

**Endpoints needed:**
1. `GET /api/v1/tenant-settings/theme` - Retrieve current theme for the authenticated user's tenant
2. `PUT /api/v1/tenant-settings/theme` - Update theme for the authenticated user's tenant

**Response Model:**
```json
{
  "primary": "#c9506b",
  "primaryLight": "#e8a598",
  "accent": "#f5c4a1",
  "text": "#5c4a5a",
  "preset": "eliza-forge"  // or null if custom
}
```

### Feature 3: Theme Application on Load

**How it works:**
1. On app initialization (or after login), frontend fetches theme from API
2. Theme colors are applied as CSS variables:
   - `--color-primary`
   - `--color-primary-light`
   - `--color-accent`
   - `--color-text`
3. Tailwind utilities like `bg-eliza-red`, `text-eliza-red` reference these CSS variables
4. All themed components update automatically

**Caching:**
- Theme can be cached in localStorage with a TTL
- On save, clear cache to force refresh
- Consider React context/Zustand store for theme state

### Feature 4: Navigation Integration

**Sidebar changes:**
- Add "Theme" item to Admin Settings section (`sectionConfigs.ts`)
- Path: `/tenant-admin/theme`
- Icon: `SwatchIcon` or `PaintBrushIcon` from Heroicons

**Route addition:**
- Add route in `App.tsx`
- Permission: `theme:write`

---

## Technical Requirements (High-Level)

### Data Requirements
- New database table or extend `CustomerSettings` to store theme configuration per tenant
- Fields: `primary_color`, `primary_light_color`, `accent_color`, `text_color`, `preset_name`

### Integration Requirements
- Frontend must apply CSS variables on load
- Theme context/store must be accessible throughout the app
- Must work with existing dark mode toggle

### Performance Requirements
- Theme fetch should complete in < 200ms
- Theme should be cached to avoid repeated API calls

### Security Requirements
- Only tenant admins can modify theme
- Validate hex color format server-side
- Sanitize inputs to prevent injection

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Owner |
|------------|--------|-------|
| Design System CSS Variables | Ready | Frontend |
| CustomerSettings model pattern | Ready | Backend |
| Authorization middleware | Ready | Backend |
| Admin Settings navigation section | Ready | Frontend |

### External Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| None | N/A | No external services required |

---

## Acceptance Criteria

### Feature 1: Theme Settings Page

- [ ] Page accessible at `/tenant-admin/theme`
- [ ] Page uses DS components (Card, Button, Label, Input)
- [ ] Four color pickers displayed: Primary, Primary Light, Accent, Text
- [ ] Hex value input shows alongside each color picker
- [ ] Preset buttons available: Eliza Forge, Ocean Blue, Forest Green, Royal Purple
- [ ] Clicking preset updates all color pickers
- [ ] Live preview section shows themed buttons, badges, gradient
- [ ] Save button persists theme to database
- [ ] Success toast shown on save
- [ ] Reset to Default button restores Eliza Forge colors
- [ ] Only accessible with proper permissions

### Feature 2: Theme API

- [ ] GET endpoint returns current theme or defaults
- [ ] PUT endpoint validates hex color formats
- [ ] PUT endpoint requires admin permissions
- [ ] Multi-tenant isolation: tenant A cannot see/edit tenant B's theme

### Feature 3: Theme Application

- [ ] Theme loads on app initialization
- [ ] CSS variables updated with tenant theme values
- [ ] All eliza-red, eliza-red-light, eliza-red-coral components use variables
- [ ] Theme persists across page refreshes
- [ ] Theme updates immediately after admin saves

### Feature 4: Navigation

- [ ] "Theme" item appears in Admin Settings sidebar section
- [ ] Theme page shows as active when on `/tenant-admin/theme`
- [ ] Back button returns to previous page

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Adoption rate | 30% of tenants customize theme within 90 days | Count tenants with non-default theme |
| Save completion | >95% of theme save attempts succeed | Monitor API success/error rates |
| Page load performance | Theme applied within 500ms of page load | Frontend timing metrics |

---

## Open Questions

- [x] **Q1:** Should we add a `theme:read` / `theme:write` permission or reuse `admin:settings:*`?
  - **Decision:** New `theme:write` permission for granular control
  
- [x] **Q2:** Should we store theme in a new `tenant_themes` table or extend `customer_settings`?
  - **Decision:** New `tenant_themes` table for cleaner separation and future extensibility (logo, dark mode variants)
  
- [ ] **Q3:** How should we handle the transition from hardcoded CSS to variable-based? 
  - Need to audit current usage of `eliza-red`, `eliza-red-light`, etc.
  
- [x] **Q4:** Should preset selection be tracked (for analytics/feature usage)?
  - **Decision:** Not needed for MVP

---

## Appendix

### Reference: Existing Theme Customizer

The `/design-system` page contains a working Theme Customizer component that serves as the UX reference:

**Location:** `frontend/src/pages/design-system/ComponentShowcase.tsx`

**Key implementation details:**
```typescript
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
}

// CSS variable application
useEffect(() => {
  document.documentElement.style.setProperty('--color-primary', hexToRgb(theme.primary))
  document.documentElement.style.setProperty('--color-primary-light', hexToRgb(theme.primaryLight))
  document.documentElement.style.setProperty('--color-accent', hexToRgb(theme.accent))
  document.documentElement.style.setProperty('--color-text', hexToRgb(theme.text))
}, [theme])
```

### Existing Customer Settings Pattern

The platform already uses tenant-scoped settings via `CustomerSettings`:

**Location:** `src/models/email_templates.py`

```python
class CustomerSettings(BaseModel):
    __tablename__ = "customer_settings"
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, unique=True, index=True)
    # ... various settings fields
```

This pattern can be extended or a parallel `TenantTheme` model can be created.

### Proposed Database Schema

```sql
CREATE TABLE tenant_themes (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL UNIQUE REFERENCES customers(customer_id),
    
    -- Color values (hex strings)
    primary_color VARCHAR(7) DEFAULT '#c9506b',
    primary_light_color VARCHAR(7) DEFAULT '#e8a598',
    accent_color VARCHAR(7) DEFAULT '#f5c4a1',
    text_color VARCHAR(7) DEFAULT '#5c4a5a',
    
    -- Preset tracking (null if custom)
    preset_name VARCHAR(50) DEFAULT 'eliza-forge',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tenant_themes_customer ON tenant_themes(customer_id);
```

### Navigation Structure

The Theme page will be added to the Admin Settings section:

```typescript
// In sectionConfigs.ts
export const adminSettingsConfig: SectionConfig = {
  id: 'admin-settings',
  title: 'Admin Settings',
  icon: Cog6ToothIcon,
  basePath: '/admin',
  items: [
    { label: 'Data Connections', path: '/data-connections', icon: LinkIcon },
    { label: 'Users & Roles', path: '/tenant-admin/users', icon: UsersIcon },
    { label: 'AI Providers', path: '/admin/settings', icon: CpuChipIcon },
    { label: 'Theme', path: '/tenant-admin/theme', icon: SwatchIcon },  // NEW
  ],
};
```

### Wireframe

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Theme Settings                                                    [Save] │
│ Customize your organization's color scheme                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐      │
│  │ Brand Colors                │  │ Brand Presets               │      │
│  │                             │  │                             │      │
│  │ Primary         [##c9506b]  │  │ [●] Eliza Forge            │      │
│  │ [color picker]   #c9506b   │  │ [○] Ocean Blue             │      │
│  │                             │  │ [○] Forest Green           │      │
│  │ Primary Light   [##e8a598]  │  │ [○] Royal Purple           │      │
│  │ [color picker]   #e8a598   │  │                             │      │
│  │                             │  │                             │      │
│  │ Accent          [##f5c4a1]  │  │ [Reset to Default]         │      │
│  │ [color picker]   #f5c4a1   │  │                             │      │
│  │                             │  │                             │      │
│  │ Text            [##5c4a5a]  │  │                             │      │
│  │ [color picker]   #5c4a5a   │  │                             │      │
│  └─────────────────────────────┘  └─────────────────────────────┘      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Live Preview                                                     │   │
│  │                                                                   │   │
│  │ [Primary Button]  [Secondary]  [Brand Badge]  Accent Text        │   │
│  │ ████████████████████████████████████████████ (gradient bar)      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

# Navigation Hierarchy Revamp Plan

> **Status:** ✅ COMPLETE  
> **Created:** 2026-01-10  
> **Completed:** 2026-01-12  
> **Goal:** Simplify sidebar to app-launcher style with contextual submenus

---

## Final Architecture

### Main Sidebar (When on Home)

```
┌─────────────────────────────────────────┐
│ ☰                                       │
├─────────────────────────────────────────┤
│ 🏠 Home                                 │  ← Active when on /home
│ 📱 Apps                                 │  ← Scrolls to apps section
├─────────────────────────────────────────┤
│ FAVORITES                               │  ← Only shown if user has favorites
│ ⭐ AI Recruiter                         │  ← User-pinned apps
│ ⭐ Knowledge Base                       │
├─────────────────────────────────────────┤
│ ADMIN                                   │  ← Footer section (permission-gated)
│ ⚙️ Admin Settings →                     │  ← Drill-down
│ 🏢 Platform Settings →                  │  ← Platform admin only
└─────────────────────────────────────────┘
```

### App Submenu (When in an App)

```
┌─────────────────────────────────────────┐
│ ☰                                       │
├─────────────────────────────────────────┤
│ ← Back                                  │  ← Returns to previous page
├─────────────────────────────────────────┤
│ AI RECRUITER                            │
│   Search Templates                      │
│   Search Results                        │
│   Email Templates                       │
│   Blueprints & DNA                      │
│   Search History                        │
│                                         │
│ COMING SOON                             │  ← Section subheader
│   Reference Checks         [Soon]       │  ← Disabled with badge
└─────────────────────────────────────────┘
```

### Homepage Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ Good afternoon, [Name].                                         │
│ [Search bar]                                                    │
│ [Quick actions: Create job spec, Search talent, Analytics]     │
├─────────────────────────────────────────────────────────────────┤
│ YOUR APPS                                    id="apps-section"  │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                │
│ │⭐ AI    │ │⭐ BI    │ │⭐ Adopt │ │⭐ Docs  │                │
│ │Recruiter│ │ Intel   │ │Analytics│ │ Base   │                │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘                │
├─────────────────────────────────────────────────────────────────┤
│ LABS                                                            │
│ ┌─────────────────┐ ┌─────────────────┐                        │
│ │ Agent Config    │ │ Resume Parsing  │                        │
│ │ [Experimental]  │ │ [Developer Tool]│                        │
│ └─────────────────┘ └─────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features Implemented

### ✅ Phase 1: Sidebar Architecture

| Component | Purpose | Location |
|-----------|---------|----------|
| `SidebarContentSwitch` | Animated content transitions | `ui/sidebar-content-switch.tsx` |
| `AppSidebar` | Unified sidebar with content switching | `layout/AppSidebar.tsx` |
| `MainNavContent` | Home + Apps + Favorites | `navigation/MainNavContent.tsx` |
| `SectionNavContent` | Section sub-nav with back button | `navigation/SectionNavContent.tsx` |

**Behaviors:**
- Hamburger ALWAYS toggles expanded ↔ collapsed
- Smooth directional animation when drilling in/out
- Back button navigates to previous page
- Admin section pinned to footer

### ✅ Phase 2: Navigation Simplification

- Sidebar reduced to: Home, Apps, Favorites (dynamic), Admin (footer)
- Apps accessed via homepage cards or favorites
- Admin Settings and Platform Settings drill-down
- Coming Soon support for future features

### ✅ Phase 3: Favorites System

- `useFavorites` Zustand store with localStorage persistence
- Star button on each homepage app card
- Favorites section in sidebar (alphabetically sorted, hidden when empty)
- Toggle favorite on click (filled star = favorited)

### ✅ Phase 4: Homepage Enhancements

- Labs section with Agent Configuration and Resume Parsing Test
- Coming Soon section in AI Recruiter submenu (Reference Checks)
- Section subheaders for visual grouping

---

## Section Configs

| Section | ID | Base Path | Items |
|---------|-----|-----------|-------|
| AI Recruiter | `ai-recruiter` | `/talent` | Search Templates, Results, Email Templates, Blueprints, History + Coming Soon: Reference Checks |
| AI Assistant | `bi-assistant` | `/data-analyst` | Chat, Question Log, Documents |
| Admin Settings | `admin-settings` | `/admin` | Data Connections, Users & Roles, Settings |
| Platform Settings | `platform-settings` | `/platform-admin` | Admin Mgmt, AI Providers, Email, Jobs, Tenants, Features, Adoption |

---

## Key Files

| File | Purpose |
|------|---------|
| `layout/AppSidebar.tsx` | Main sidebar with header, content switch, footer |
| `navigation/MainNavContent.tsx` | Home + Apps + Favorites |
| `navigation/SectionNavContent.tsx` | Section sub-nav with back button |
| `navigation/sectionConfigs.ts` | All section definitions |
| `contexts/NavigationContext.tsx` | Active section + return path state |
| `stores/useFavorites.ts` | Favorites persistence |
| `pages/home/NewHomePage.tsx` | Homepage with apps, labs, star buttons |

---

## Adding New Features

### Add a New App Section

1. Add section ID to `ActiveSection` type in `NavigationContext.tsx`
2. Add config to `sectionConfigs.ts` with items array
3. Add to `sectionConfigs` map
4. Add path detection in `getSectionFromPath`

### Add Coming Soon Item to Section

```typescript
// In sectionConfigs.ts
{
  label: 'COMING SOON',
  path: '#coming-soon',
  sectionHeader: true,  // Renders as section subheader
},
{
  label: 'New Feature',
  path: '/path',
  icon: SomeIcon,
  comingSoon: true,  // Renders disabled with "Soon" badge
},
```

### Add New App Card to Homepage

Add to `appCards` array in `NewHomePage.tsx`:
```typescript
{
  id: 'my-app',
  title: 'My App',
  description: 'Description here',
  icon: MyIcon,
  iconKey: 'my-icon',  // For favorites
  path: '/my-app',
  color: 'text-color-600',
  bgGradient: 'from-color-500/10 to-color-600/5',
  features: ['Feature 1', 'Feature 2'],
}
```

---

## Changelog

### 2026-01-12 (Final Session)
- ✅ Added Labs section to homepage (Agent Configuration, Resume Parsing Test)
- ✅ Added Coming Soon section to AI Recruiter submenu (Reference Checks)
- ✅ Added `sectionHeader` and `comingSoon` support to SubmenuItem
- ✅ Fixed Agent Configuration link to `/admin/agents`

### 2026-01-12 (Session 3 - Favorites)
- ✅ Created `useFavorites` Zustand store
- ✅ Added star button to homepage app cards
- ✅ Favorites persist to localStorage
- ✅ Sidebar shows FAVORITES section (alphabetically sorted)
- ✅ Section hidden when empty

### 2026-01-12 (Session 2)
- ✅ Simplified MainNavContent to Home + Apps
- ✅ Moved Admin section to sidebar footer
- ✅ Removed Eliza Forge version badge
- ✅ Added AI Recruiter and BI Assistant section configs
- ✅ Back button navigates to previous page
- ✅ Apps button scrolls to homepage apps section
- 🗑️ Deleted old `Navigation.tsx`

### 2026-01-12 (Session 1)
- ✅ Created `SidebarContentSwitch` DS component
- ✅ Created `AppSidebar` unified sidebar
- ✅ Extracted `MainNavContent` and `SectionNavContent`
- ✅ Simplified `Layout.tsx`
- ✅ Fixed animation direction for back navigation

### 2026-01-10
- Initial planning document created

---

## Migration Complete 🎉

The navigation system has been fully migrated from the old complex multi-sidebar architecture to a clean, app-launcher style navigation with:

- **Minimal main nav**: Just Home, Apps, Favorites, Admin
- **Contextual submenus**: Auto-detected from URL, with back navigation
- **Favorites system**: Star apps from homepage, see them in sidebar
- **Future-ready**: Coming Soon items for planned features
- **Consistent UX**: Smooth animations, proper active states, permission-gated sections

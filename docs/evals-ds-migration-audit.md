# RAG Evaluations Page - DS Migration Audit & UX Plan

> **Page:** `/evals` (`frontend/src/pages/evals/EvalsPage.tsx`)  
> **Current State:** Fully migrated. UX v2 redesign in progress — wider layout, inline workspace context, compact metrics, removal of redundant summary cards.  
> **Goal:** Fully migrate to DS, fix UX issues, fix file upload error handling, preserve permission gating.

---

## Table of Contents

1. [Progress Update (2026-02-10)](#1-progress-update-2026-02-10)
2. [Permission Gating (Must Preserve)](#2-permission-gating-must-preserve)
3. [Component Mapping: Current → DS](#3-component-mapping-current--ds)
4. [Legacy Color Token Cleanup](#4-legacy-color-token-cleanup)
5. [UX Issues & Recommendations](#5-ux-issues--recommendations)
6. [File Upload Bug Analysis](#6-file-upload-bug-analysis)
7. [Tab-by-Tab Breakdown](#7-tab-by-tab-breakdown)
8. [Implementation Checklist](#8-implementation-checklist)

---

## 1. Progress Update (2026-02-10)

### ✅ Completed in Code

> Note: Sections below include baseline audit notes from before the latest implementation pass; use this progress section and the checklist as the source of truth for current status.

#### Foundation / DS migration
- `Page` is now explicitly centered with `maxWidth="xl"`
- Tabs migrated to DS `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent`
- Tabs moved out of `PageHeader.actions` into `PageBody`
- Legacy color tokens removed from `EvalsPage` and replaced with DS-compatible colors
- DS components applied for form/feedback structure: `Label`, `Alert`, `RadioGroup`, `RadioCard`, `Switch`, `Progress`, `Textarea`, `SectionHeader`

#### UX architecture update
- The old `Run Eval` + `History` split has been consolidated into:
  - `Runs` (default homepage view)
  - `Eval Sets`
- Added `New Evaluation` primary action in header
- `New Evaluation` now opens a **right-side DS `Sheet`** with full configuration and start/progress controls

#### Runs homepage improvements
- Added **Recent Runs comparison cards** with prominent pass-rate KPI:
  - `0%`
  - `Pass Rate`
- Existing list-detail runs/results area remains available in the `Runs` tab for deeper inspection

#### Latest pass (Phase 4 + Phase 5)
- Replaced native results `<table>` with DS `DataTable` and expandable row details
- Replaced `window.confirm()` delete prompts with DS `Modal` confirmation dialogs
- Added frontend write-action gating (`bi:write`/`platform:admin`) for New Evaluation, Upload, Duplicate, and Delete actions
- Added upload hardening:
  - inline `Alert variant="error"` inside upload modal
  - 10MB file size validation
  - basic JSONL content validation (first lines + required keys)
  - clearer server/client error extraction

### ⚠️ Still Open — UX v2 Redesign
- Final dark-mode/disabled-state polish

---

## 1b. UX v2 Redesign (2026-02-10)

> The Runs tab had redundant UI (summary cards repeating the run list), cramped width, and a buried workspace selector. This redesign addresses all three.

### Problem Summary

| Issue | Detail |
|-------|--------|
| **Redundant cards** | "Recent Runs" cards at top duplicate the "All Runs" list below — same data in two treatments |
| **Metrics too heavy** | 7 `MetricCard`/`StatCard` boxes showing "—" for runs with no results looks broken |
| **Workspace buried** | Small dropdown in header; no visual cue that switching it scopes all content |
| **Page too narrow** | `maxWidth="xl"` (1152px) cramps the master-detail split |

### Design Decisions

| Area | Before | After | Rationale |
|------|--------|-------|-----------|
| Page width | `maxWidth="xl"` (1152px) | `maxWidth="2xl"` (1600px) | Master-detail needs room; this is a productivity page |
| Recent Runs cards | 4 summary cards above run list | **Removed** | Duplicate of run list; wastes vertical space |
| Workspace selector | In `PageHeader.actions` dropdown | **Inline strip above tabs** with label + status | Makes scope obvious; workspace is a filter, not an action |
| Metrics display | 7 `MetricCard`/`StatCard` boxes | **Compact inline summary line** (only shown when run has metrics) | Secondary KPIs shouldn't dominate; the DataTable is the content |
| Run list panel | `w-80` (320px) | `w-96` (384px) | More breathing room with wider page |
| MLflow button | In `PageHeader.actions` | Stays in header (no change) | Still an action |
| Run detail header | Status + name + metrics grid | Status + name + compact stats row | Tighter header, more room for table |

### Compact Metrics Layout

When a run has results, show a single-row summary strip instead of cards:

```
Pass Rate: 72%  ·  Factual: 85.2%  ·  Faithful: 91.0%  ·  Ctx Precision: 78.3%  ·  Ctx Recall: 90.1%  ·  Citations: 67.0%  ·  Citation Page: 55.2%
```

When a run is `running` — show progress. When `failed` — show error alert. When `pending` — show waiting state.

### Workspace Context Strip

```
┌──────────────────────────────────────────────────────────────────────┐
│  Workspace  [ hi (1 docs)  ▼ ]    ● ready   🔄                     │
└──────────────────────────────────────────────────────────────────────┘
```

- Rendered as a light `Panel`-style strip between `PageHeader` and `Tabs`
- `WorkspaceSelector` component moved here from header
- Clear label so new users understand scope

---

## 2. Permission Gating (Must Preserve)

### Frontend Route Guard
```tsx
// App.tsx — KEEP THIS
<Route
  path="/evals"
  element={
    <ProtectedRoute requiredPermissions={['ai_console:access', 'platform:admin']}>
      <EvalsPage />
    </ProtectedRoute>
  }
/>
```

### Sidebar Access Check
```tsx
// AppSidebar.tsx — KEEP THIS
const hasAiConsoleAccess = hasAnyPermission(['evals:read', 'platform:admin']);
```

### Backend Permissions (Reference — no changes needed)
| Operation | Permission |
|-----------|-----------|
| List/view runs, results, eval sets | `bi:read` OR `platform:admin` |
| Start/cancel/delete runs, upload/delete eval sets | `bi:write` OR `platform:admin` |
| Seed static eval sets | `platform:admin` only |

**Action:** None of these should change. Frontend now also hides write actions for read-only users (`bi:write`/`platform:admin` check), while backend permission enforcement remains the source of truth.

---

## 3. Component Mapping: Current → DS

### Page Layout

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| `<Page>` (no maxWidth) | 657 | `<Page maxWidth="xl">` | Should set explicit width. This is a config/admin page → centered layout. |
| `<PageHeader>` | 658-712 | Keep, but move tabs out of `actions` | Tabs should not be crammed into the header actions. See UX section. |
| `<PageBody>` | 714 | Keep | Remove overflow styling — let DS handle it |

### Tabs

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| Custom button group with `variant="brand"/"ghost"` for tabs | 674-699 | **`Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`** | Use `variant="default"` (pill-style container). Controlled via `value`/`onValueChange` matching current `activeTab` state. |

**Current (custom):**
```tsx
<div className="flex border ...">
  <Button variant={activeTab === 'run' ? 'brand' : 'ghost'}>Run Eval</Button>
  ...
</div>
```

**DS replacement:**
```tsx
<Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabType)} defaultValue="run">
  <TabsList>
    <TabsTrigger value="run">Run Eval</TabsTrigger>
    <TabsTrigger value="sets">Eval Sets</TabsTrigger>
    <TabsTrigger value="history">History</TabsTrigger>
  </TabsList>
  <TabsContent value="run">...</TabsContent>
  <TabsContent value="sets">...</TabsContent>
  <TabsContent value="history">...</TabsContent>
</Tabs>
```

### Form Elements

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| Native `<input type="radio">` for eval source | 748-783 | **`RadioGroup` + `RadioCard`** | RadioCard gives the bordered card look with active state highlighting — exactly what's currently hand-coded. |
| Native `<select>` for eval set picker | 789-810 | **DS `Select` + `SelectOption`** with `SelectGroup` for optgroups | Already imported but not used here. Native `<select>` with `<optgroup>` needs conversion. Note: DS Select doesn't have native `<optgroup>` — use `SelectGroup` or a flat list with headers. |
| Native `<input type="number">` (Easy/Medium/Hard counts) | 835-869 | **DS `Input` with `type="number"`** | Already imported. Just swap out. |
| Native `<input type="number">` (Seed, Concurrency) | 878-898 | **DS `Input` with `type="number"`** | Same as above. |
| Custom toggle switch (Citation Validation) | 906-920 | **DS `Switch`** with `onCheckedChange` | Already imported. Replace the custom `<button>` toggle. |
| Native `<textarea>` in upload modal | 1491-1498 | **DS `Textarea`** | Import and replace. |
| `<label className="text-sm text-muted">` throughout | Many | **DS `Label`** | Already imported but not used. |

### Data Display

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| Custom run cards (2x2 grid on Run tab) | 973-1007 | **DS `Card`/`CardContent`** or **`Panel`** | Already using `Card` in preview modal. Use `Panel` for these functional cards. |
| Native `<table>` for results | 1365-1417 | **DS `DataTable`** | Full replacement with Column definitions. Enables sorting, pagination, expandable rows for viewing model responses. |
| Custom badge-like `<span>` for category | 1000, 1066, etc. | **DS `Badge`** | Already imported. Replace all `<span className="...px-2 py-0.5 rounded...">` with `<Badge variant="...">`. |
| Custom eval source badge (Eval Set / Random) | 998-1004 | **DS `Badge`** | Use `variant="info"` for Eval Set, `variant="default"` for Random. |
| Custom difficulty badges | 1392-1398 | **DS `Badge`** | `variant="success"` for easy, `variant="warning"` for medium, `variant="danger"` for hard. |
| Metrics grid (7 stat boxes) | 1316-1359 | **DS `MetricCard`** or `StatCard` from `card-variants` | These are perfect candidates for the `MetricCard` or `StatCard` DS component. |
| Custom progress bar | 931-934 | **DS `Progress`** | Replace custom `<div>` bar with `<Progress value={progress} showLabel />`. |

### Actions & Buttons

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| DS `Button` (most places) | Multiple | Keep — already correct | variant="brand", "outline", "ghost", "secondary" used appropriately |
| Native `<button>` for Preview/Download/Duplicate/Delete in eval sets cards | 1079-1103, 1144-1168 | **DS `Button` with `variant="ghost"` and `size="sm"`** | These inline link-style actions should use Button ghost/link variant. |
| Native `<button>` for refresh in History header | 1196-1203 | **DS `Button` with `variant="ghost"` and `size="sm"`** | Replace. |
| Native `<button>` for delete runs in History list | 1249-1258 | **DS `Button` with `variant="ghost"` and `size="sm"`** | Replace. |
| `<a>` for MLflow link | 1302-1310 | **DS `Button` with `variant="outline"` as `<a>`** or keep but style consistently | Could use `Button` wrapping a link, or keep as styled anchor. |

### Feedback & States

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| Custom empty state (BeakerIcon + text) | 1010-1016, 1263-1266, 1427-1433 | **DS empty state pattern** (from Design System Guide) | Standardize all empty states with the DS pattern: centered icon + heading + description + optional CTA. |
| Custom error in progress message (`setProgressMessage`) | 377-380 | **DS `Alert variant="error"`** | Show errors as proper Alert components, not just text. |
| No loading skeleton for runs list | — | **DS `Skeleton`/`SkeletonCard`** | Add loading skeletons when fetching runs and eval sets. |
| `window.confirm()` for delete | 396, 429 | **DS `Modal` confirmation dialog** | Replace native `confirm()` with a proper DS Modal for delete confirmation. |

### Modals

| Current | Line(s) | DS Replacement | Notes |
|---------|---------|---------------|-------|
| Upload Modal | 1467-1593 | Already uses DS Modal — needs minor fixes | Replace `<textarea>` with DS `Textarea`. Replace `<label>` with DS `Label`. Fix error surfacing (see Section 5). |
| Preview Modal | 1596-1654 | Already uses DS Modal — good | Minor: Already uses `Card`/`CardContent`/`Badge`. |

---

## 4. Legacy Color Token Cleanup

All legacy semantic color tokens must be replaced:

| Legacy Token | Occurrences | DS Replacement |
|-------------|-------------|----------------|
| `text-text` | ~20 | `text-charcoal dark:text-gray-100` |
| `text-muted` | ~25 | `text-gray-500 dark:text-gray-400` |
| `bg-surface-2` | ~12 | `bg-gray-50 dark:bg-dark-surface-2` |
| `border-border` | ~15 | `border-gray-200 dark:border-dark-border` |
| `text-brand` | ~5 | `text-eliza-red` |
| `bg-brand/5`, `bg-brand/10`, `bg-brand/20` | ~4 | `bg-eliza-red/5`, `bg-eliza-red/10`, `bg-eliza-red/20` |
| `border-brand` | ~3 | `border-eliza-red` |
| `hover:bg-surface-2` | ~4 | `hover:bg-gray-50 dark:hover:bg-dark-surface-2` |
| `text-muted-2` | ~1 | `text-gray-400 dark:text-gray-500` |
| `bg-brand` (on switch) | ~1 | Use DS `Switch` component instead |
| `focus:ring-brand/50` | ~6 | Use DS Input/Select which handle focus rings |

---

## 5. UX Issues & Recommendations

### 4.1 Page Layout — Move tabs into the body, not the header actions

**Problem:** The tabs (Run Eval | Eval Sets | History) are crammed into the `PageHeader` actions alongside the WorkspaceSelector and MLflow toggle. This makes the header visually heavy and the tabs feel like secondary actions rather than primary navigation.

**Recommendation:** 
- `PageHeader` should contain only: title, description, and the WorkspaceSelector + MLflow toggle as actions.
- Tabs should be placed at the top of `PageBody` using the DS `Tabs` component. This gives them prominence and proper accessibility.
- Use `maxWidth="xl"` on `Page` for a centered admin layout.

### 4.2 Run Tab — Improve the split layout

**Problem:** The Run tab has a fixed-width left config panel (w-96) and a right "Recent Runs" area. This is an uncommon layout for a config page. The config panel feels like a sidebar within a sidebar, and "Recent Runs" is duplicated information (also in History tab).

**Recommendation:**
- Use a **single-column centered layout** for the Run tab.
- Show the config form at the top within a `Panel` component.
- Show "Recent Runs" below as a small summary (max 3-4 entries) in a horizontal card row or just link to the History tab.
- This simplifies the layout and removes the split-pane complexity.

### 4.3 History Tab — Use DataTable for results

**Problem:** The results table is a native `<table>` with no sorting, no pagination, and no row expansion. For runs with 50+ questions, this is unwieldy.

**Recommendation:**
- Replace with DS `DataTable` with columns for: #, Question, Difficulty, Verdict, Factual, Faithful, Citation Page.
- Enable `expandable` rows to show the full question, expected answer, model response, and verdict reason in the expanded row.
- Enable sorting on numeric columns (scores).
- This also handles the "truncate" display issue — expanded rows show full content.

### 4.4 History Tab — Run list UX

**Problem:** The left run list (w-80) with inline delete buttons and custom hover states is functional but has some issues:
- Delete uses `window.confirm()` — jarring native dialog
- No search/filter for runs
- Active state uses legacy colors

**Recommendation:**
- Replace `window.confirm()` with DS `Modal` confirmation.
- Keep the split layout for History (it's appropriate for list-detail), but use DS colors and components.
- Consider adding a simple status filter (all/completed/failed/running).

### 4.5 Eval Sets Tab — Inconsistent card actions

**Problem:** Card action buttons (Preview, Download, Duplicate, Delete) use native `<button>` elements with inline styles. Built-in sets show Preview/Download/Duplicate; uploaded sets show Preview/Download/Delete — but this inconsistency isn't immediately obvious.

**Recommendation:**
- Use DS `Button variant="ghost" size="sm"` for all card actions.
- Consider a `DropdownMenu` for secondary actions (Download, Duplicate, Delete) to reduce visual clutter.
- Or use a consistent row of small ghost buttons with icons.
- Uploaded sets should also have Duplicate.

### 4.6 Workspace Selector — Not using DS Select

**Problem:** `WorkspaceSelector` component (`frontend/src/components/common/RAGDomainSelector.tsx`) uses a native `<select>` with legacy color tokens (`text-muted`, `bg-surface-2`, `border-border`). It's shared across evals, GEPA, and prompt management pages.

**Recommendation:**
- Migrate `WorkspaceSelector` to use DS `Select`/`SelectOption` with proper DS colors.
- This is a separate shared component migration that benefits all three pages.

### 4.7 Metrics Display — Use DS metric components

**Problem:** The 7-column metrics grid in the History detail view uses custom styled `<div>` blocks. They look okay but don't use DS components.

**Recommendation:**
- Use DS `MetricCard` or `StatCard` from `card-variants` for each metric.
- These provide consistent sizing, colors, and dark mode support.

### 4.8 No loading states during data fetch

**Problem:** When runs, eval sets, or MLflow info are being fetched, there's no loading indicator. The page just shows empty content.

**Recommendation:**
- Add `Spinner` or `SkeletonCard` placeholders while data loads.
- Show `Spinner` inline with the Start Evaluation button when `isStarting`.

### 4.9 Progress area — Use DS Progress component

**Problem:** Custom progress bar using raw `<div>` with inline width style. The progress message is plain text.

**Recommendation:**
- Use DS `Progress` component with `value={progress}` and `showLabel`.
- Show the progress message as a separate line using `text-gray-500 dark:text-gray-400`.

### 4.10 Radio selection for eval source — Use RadioCard

**Problem:** Custom radio cards with native `<input type="radio">` and hand-coded active/inactive border states.

**Recommendation:**
- Replace with DS `RadioGroup` + `RadioCard`. The `RadioCard` component has built-in active state (eliza-red border, checkmark indicator) — matches the current design intent exactly.

---

## 6. File Upload Bug Analysis

### Current Behavior
The upload modal at lines 1467-1593 has several issues with error handling:

### Bug 1: No client-side file validation
- Only checks `.jsonl` extension via `accept=".jsonl"` on the file input
- Does NOT validate:
  - File size (backend allows up to some limit)
  - File content format (invalid JSON lines)
  - Empty file
  - File encoding

**Fix:** Add client-side validation before upload:
```tsx
// Validate file before sending
if (uploadForm.file.size > 10 * 1024 * 1024) {
  push({ kind: 'error', message: 'File too large. Max 10MB.' });
  return;
}
```

### Bug 2: Server errors not properly surfaced
Lines 532-540 try to parse the error response, but:
- The `push({ kind: 'error' })` toast may not be visible enough for validation errors
- The error parsing tries `JSON.parse(txt)` and uses `error.detail` — but the backend raises `HTTPException(status_code=400, detail=str(e))` which returns `{"detail": "..."}`, so the parsing should work IF the response is JSON.
- However, if the backend returns a non-JSON error (e.g., nginx 413 for large files), it falls through to the plain text catch.

**Fix:**
- Add an **inline error message** in the upload modal (using DS `Alert variant="error"`) rather than relying solely on toast notifications.
- Show validation errors directly below the file input so users see them immediately.
- Add a state variable `uploadError` displayed as `<Alert variant="error">` inside the modal body.

### Bug 3: File input doesn't reset on error
After a failed upload, the file remains selected. If the user clicks "Upload" again, it re-sends the same bad file.

**Fix:** On error, keep the file selected but show the error inline. On success, reset the form.

### Bug 4: No progress indication for upload
Large files may take time. The only indicator is `uploadLoading` which disables the button.

**Fix:** The `Spinner` is already shown on the button, but adding a small progress text or status message would help.

---

## 7. Tab-by-Tab Breakdown

### Run Tab

| Area | Current | Proposed DS | UX Change |
|------|---------|------------|-----------|
| Layout | 2-column split (w-96 config + flex-1 recent) | Single column centered in PageBody | Simpler, more standard |
| Workspace notice | Custom styled div | DS `Alert variant="info"` or DS `Panel` | Consistent styling |
| No workspace warning | Custom yellow div | DS `Alert variant="warning"` | Consistent styling |
| Eval source radio | Native radio + custom card styling | `RadioGroup` + `RadioCard` | DS-native, accessible |
| Eval set selector | Native `<select>` with `<optgroup>` | DS `Select` + `SelectOption` (flat list with visual section headers) | Consistent with DS |
| Difficulty count inputs | Native `<input type="number">` | DS `Input type="number"` | Consistent styling |
| Seed/Concurrency inputs | Native `<input type="number">` | DS `Input type="number"` | Consistent styling |
| Citation toggle | Custom `<button>` toggle | DS `Switch` with `onCheckedChange` | Proper toggle behavior |
| Labels | `<label className="text-sm text-muted">` | DS `Label` | Consistent typography |
| Progress bar | Custom div bar | DS `Progress` | Animated, themed |
| Start button | DS `Button variant="brand"` | Keep | Already correct |
| Cancel button | DS `Button variant="outline"` | Keep | Already correct |
| Recent Runs cards | Custom grid of divs | DS `Panel` or `Card` cards, or just a summary sentence linking to History tab | Reduce duplication |
| Empty state | Custom BeakerIcon + text | DS empty state pattern | Standardized |

### Eval Sets Tab

| Area | Current | Proposed DS | UX Change |
|------|---------|------------|-----------|
| Section header | Custom `<h2>` + `<p>` | DS `SectionHeader` | Consistent typography |
| Section subheaders | Custom `<h3>` uppercase | DS `SectionHeader` or styled heading | Consistent |
| Eval set cards | Custom `<div>` cards | DS `Panel` with `PanelBody` | Consistent container |
| Category badges | Custom `<span>` styling | DS `Badge` | Consistent badges |
| Type badges (Static/Uploaded) | Custom `<span>` | DS `Badge variant="brand"` / `Badge variant="info"` | Consistent |
| Action buttons (Preview, Download, etc.) | Native `<button>` | DS `Button variant="ghost" size="sm"` | Proper buttons |
| Upload CTA in empty state | Native `<button>` link | DS `Button variant="link"` | Consistent |
| Upload button in header | DS `Button variant="brand"` | Keep | Already correct |
| Refresh button in header | DS `Button variant="outline"` | Keep | Already correct |

### History Tab

| Area | Current | Proposed DS | UX Change |
|------|---------|------------|-----------|
| Left panel header | Custom `<h3>` + `<button>` | `SectionHeader` with action, or Panel header | Consistent |
| Run list items | Custom interactive divs | Styled list with DS colors | DS color tokens |
| Delete button in list | Native `<button>` | DS `Button variant="ghost" size="sm"` + DS `Modal` confirmation | Better UX |
| Status icons | HeroIcons with semantic colors | Keep — matches DS icon guidelines (semantic only for status) | Correct |
| Results header | Custom `<h2>` + metadata | Use `SectionHeader` or structured heading | Consistent |
| Metrics grid | Custom 7-col grid of divs | DS `MetricCard` or `StatCard` components | Consistent, themed |
| Results table | Native `<table>` | **DS `DataTable`** with expandable rows | Sorting, pagination, expansion |
| Empty state | Custom centered text | DS empty state pattern | Standardized |
| MLflow link | Custom `<a>` styled button | DS `Button variant="outline"` as link | Consistent |

---

## 8. Implementation Checklist

### Phase 1: Foundation (Layout, Tabs, Colors)
- [x] Set `<Page maxWidth="xl">` 
- [x] Move tabs from `PageHeader` actions into `PageBody` using DS `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent`
- [x] Keep WorkspaceSelector + MLflow toggle in `PageHeader` actions
- [x] Replace all legacy color tokens (text-text, text-muted, bg-surface-2, border-border, text-brand)
- [x] Verify permission gating unchanged (ProtectedRoute, sidebar check)

### Phase 2: Runs Homepage + New Evaluation Flow
- [x] Consolidate into `Runs` + `Eval Sets` tabs (remove separate `Run Eval`/`History` tab navigation)
- [x] Add `New Evaluation` primary action in header
- [x] Move eval configuration into right-side DS `Sheet`
- [x] Replace eval source radio cards with `RadioGroup` + `RadioCard`
- [x] Replace eval set native `<select>` with DS `Select`/`SelectOption`
- [x] Replace number inputs with DS `Input`
- [x] Replace citation validation toggle with DS `Switch`
- [x] Replace labels with DS `Label`
- [x] Replace progress bar with DS `Progress`
- [x] Add `Alert variant="warning"` for no workspace selected
- [x] Add `Alert variant="info"` for workspace details
- [x] Add recent run comparison cards with pass-rate KPI

### Phase 3: Eval Sets Tab
- [x] Add `SectionHeader` for "Built-in Static Sets" and "Uploaded Sets" sections
- [x] Replace eval set cards with DS `Panel` or `Card`
- [x] Replace category/type badges with DS `Badge`
- [x] Replace card action buttons with DS `Button variant="ghost" size="sm"`
- [x] Fix empty state with DS pattern

### Phase 4: Runs Detail Polish
- [x] Replace results `<table>` with DS `DataTable` (with expandable rows)
- [x] Replace metrics grid with DS `MetricCard` / `StatCard`
- [x] Replace `window.confirm()` with DS `Modal` confirmation dialog
- [x] Replace native buttons in run list with DS `Button`
- [x] Update all DS colors in run list and results panel

### Phase 5: File Upload Fix
- [x] Add `uploadError` state variable
- [x] Show inline `Alert variant="error"` in upload modal for errors
- [x] Add client-side file size validation (max 10MB)
- [x] Add client-side basic JSONL format check (first few lines)
- [x] Show error details (line number, specific validation issue)
- [x] Replace `<textarea>` with DS `Textarea`
- [x] Replace `<label>` with DS `Label`

### Phase 6: Polish
- [x] Add loading skeletons (`Skeleton`/`SkeletonCard`) for initial data fetch
- [ ] Ensure all icons follow DS guidelines (monochromatic for non-status, semantic for status)
- [ ] Test dark mode across all tabs
- [ ] Verify all DS `Button`, `Input`, `Select` disabled states work during evaluation run
- [ ] Migrate shared `WorkspaceSelector` component to DS colors/components (separate PR candidate)
- [ ] Never use breadcrumbs (confirmed — none exist, don't add any)

---

## Summary of Key Decisions

| Decision | Rationale |
|----------|-----------|
| Centered layout (`maxWidth="xl"`) | This is a config/admin page, not a productivity workspace |
| Tabs in body, not header | Tabs are primary navigation, not secondary actions |
| Single-column Run tab | The 2-column split is awkward; config form + summary below is cleaner |
| DataTable for results | Enables sorting, pagination, expandable rows for detailed inspection |
| RadioCard for eval source | DS component matches the current hand-coded design intent |
| Inline Alert for upload errors | Toast-only errors are easy to miss; inline errors are adjacent to the cause |
| DS Badge for all status/category pills | Consistent with rest of app, proper dark mode support |
| No breadcrumbs | Per design requirements |
| Preserve all permission gating | Frontend route guard + backend permission checks must remain |

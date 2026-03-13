# Analysis Config Page - Design System Migration Plan

> **Status:** Phase 1-6 COMPLETE + UX Polish, Phase 7-8 OPTIONAL  
> **Last Updated:** January 25, 2026

---

## Migration Status Summary

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Page Layout Migration | ✅ COMPLETE |
| Phase 2 | Modal Structure Refactor (Sidebar) | ✅ COMPLETE |
| Phase 3 | DS Component Integration | ✅ COMPLETE |
| Phase 4 | Modal UX Improvements | ✅ COMPLETE |
| Phase 5 | Analysis Setup Tab & Limits Redesign | ✅ COMPLETE |
| Phase 6 | Draft Auto-Save & State Persistence | ✅ COMPLETE |
| **UX Polish** | **Additional UX improvements** | ✅ COMPLETE |
| Phase 7 | Section Content Extraction | ⏳ OPTIONAL |
| Phase 8 | Final Polish & Cleanup | ⏳ OPTIONAL |

---

## Completed Work

### Phase 1: Page Layout Migration ✅

The main `AnalysisConfigPage.tsx` was migrated to use DS components:
- `Page`, `PageHeader`, `PageBody` structure
- `DataTable` with expandable rows
- `Badge` variants for status
- `Alert` for errors
- `Spinner` for loading
- `Progress` component
- DS color tokens throughout

### Phase 2: Modal Structure Refactor ✅

Transformed modal from inline-expanding pills to sidebar navigation:

**Files Created:**
- `frontend/src/components/talent-intelligence/analysisConfig.ts` - Section configuration
- `frontend/src/components/talent-intelligence/AnalysisModalSidebar.tsx` - Left navigation
- `frontend/src/components/talent-intelligence/AnalysisNavItem.tsx` - Nav item component

**Modal Structure Implemented:**
```
ModalContent (flex row)
├── Sidebar (w-60)
│   ├── Section: "CONFIGURATION"
│   │   ├── NavItem: ATS Connection
│   │   ├── NavItem: Career Blueprint
│   │   ├── NavItem: Company DNA
│   │   ├── NavItem: Job Description *
│   │   ├── NavItem: Candidate Source *
│   │   └── NavItem: Ideal Candidate
│   ├── Divider
│   ├── Section: "LIMITS"
│   │   ├── Market limit dropdown
│   │   └── ATS limit dropdown
│   └── Required legend
├── ContentArea (flex-1, scrollable, relative)
│   ├── Section-specific content
│   └── ModalFloatingActions (absolute bottom)
└── (No traditional footer - floating actions instead)
```

### Phase 3: DS Component Integration ✅

**New DS Components Created:**
- `frontend/src/components/ui/modal-floating-actions.tsx` - Floating action bar with gradient

**DS Component Enhancements:**
- `Chip` - Added `active` and `complete` props with styling variants
- `Input` - Added `ghost` and `ghost-lg` variants for minimal inputs

**Documentation Updated:**
- `skills/design-system/DESIGN_SYSTEM_GUIDE.md` - Documented new components
- `frontend/src/pages/design-system/ComponentShowcase.tsx` - Added demos

### Phase 4: Modal UX Improvements ✅

**Completed:**
- ✅ Two-row header (title + X, then inline-labeled name/description)
- ✅ Floating footer actions (Save, Save & Run)
- ✅ Gradient backdrop on floating actions
- ✅ "Done" buttons as subtle text links
- ✅ Completion checkmarks on nav items
- ✅ Required asterisks on nav items
- ✅ Info tooltips on nav items
- ✅ Removed duplicate X button
- ✅ Fixed gradient to only cover content area

### UX Polish (Post-Phase 6) ✅

**Section Subtitles:**
- ✅ Added descriptive subtitles to all section headers
- ✅ Removed redundant Alert banners (info moved to subtitles)
- ✅ Fixed duplicate subtitle in Company DNA section

**Section Subtitles Added:**
| Section | Subtitle |
|---------|----------|
| Analysis Setup | Configure the name, description, and search limits for your analysis |
| ATS Connection | Connect your ATS to import job postings and sync candidate data automatically |
| Career Blueprint | Add 2-5 LinkedIn profiles of people in similar roles to capture your ideal candidate profile |
| Company DNA | Search for employees at a company to build a DNA profile for better candidate matching |
| Job Description | Provide the job requirements to match candidates against |
| Candidate Source | Choose where to find candidates for this role |
| Ideal Candidate | Brief us like you would a headhunter |

**Per-Section Status Indicators:**
- ✅ Removed global "Draft saved" from header
- ✅ Added per-section status pills (Saved/Unsaved Changes/Connected/Optional/Required)
- ✅ Removed "Done" and "Cancel" buttons per section
- ✅ Updated section titles to larger font (`text-base font-medium`)

**Select Existing vs Create New:**
- ✅ Career Blueprint now has "Select Existing" / "Create New" modes
- ✅ Company DNA now has "Select Existing" / "Create New" modes
- ✅ List view for existing items with radio-style selection
- ✅ Clear selection button when item selected
- ✅ Empty state with CTA when no items exist

**Mode Selector Upgrade (Underline Tabs):**
- ✅ Replaced Chip-based mode selectors with DS `Tabs` component (underline variant)
- ✅ Updated sections: Career Blueprint, Company DNA, Job Description, Candidate Source
- ✅ Cleaner, more subtle visual design with red underline indicator
- ✅ Icons display inline with tab text

**Bug Fixes:**
- ✅ Fixed Ideal Candidate content cutoff (removed `max-h-[320px]`)
- ✅ Fixed data connection navigation (was going to 404)

---

## Completed Work (continued)

### Phase 5: Analysis Setup Tab & Limits Redesign ✅

> Implemented based on Gemini review recommendations

**Goal:** Create a dedicated "Analysis Setup" tab and move meta-configuration out of header/sidebar.

#### 5.1 Create "Analysis Setup" Section

**File:** `frontend/src/components/talent-intelligence/analysisConfig.ts`

Add new section at the top of `ANALYSIS_SECTIONS`:
```typescript
{
  id: 'analysis-setup',
  label: 'Analysis Setup',
  shortLabel: 'Setup',
  icon: Cog6ToothIcon,
  isRequired: true, // Name is required
  infoTooltip: 'Configure analysis name, description, and search limits',
  infoDetail: 'Set up the basic details for your analysis.',
}
```

#### 5.2 Simplify Modal Header

**File:** `frontend/src/components/talent-intelligence/NewAnalysisModal.tsx`

Remove name/description inputs from header. Header becomes:
```
┌─────────────────────────────────────────────────────────────┐
│ ✨ Create New Analysis                              [Draft] X │
└─────────────────────────────────────────────────────────────┘
```

- Static title (Baskerville font)
- "Draft" indicator (subtle, right side)
- X close button

#### 5.3 Clean Sidebar

**File:** `frontend/src/components/talent-intelligence/AnalysisModalSidebar.tsx`

Remove the "LIMITS" section entirely. Sidebar becomes pure navigation:
```
┌─────────────────────┐
│ CONFIGURATION       │
│ ○ Analysis Setup  * │  ← NEW (first item, default open)
│ ○ ATS Connection    │
│ ○ Career Blueprint  │
│ ○ Company DNA       │
│ ○ Job Description * │
│ ○ Candidate Source* │
│ ○ Ideal Candidate   │
│                     │
│ * Required to run   │
└─────────────────────┘
```

#### 5.4 Create SliderInput DS Component

**New File:** `frontend/src/components/ui/slider-input.tsx`

Combined Slider + Number Input component:
```typescript
interface SliderInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  description?: string;
}
```

Features:
- Slider on left, number input on right
- Values sync bidirectionally
- DS styling (works in light/dark mode)
- Optional description text below

Add to `ComponentShowcase.tsx` with examples.

#### 5.5 Analysis Setup Tab Content

**File:** `frontend/src/components/talent-intelligence/NewAnalysisModal.tsx`

When `activeSection === 'analysis-setup'`:
```
┌─────────────────────────────────────────────────────────────┐
│ ANALYSIS SETUP                                         Done │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Name                                                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Senior ML Engineer Search                               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ Description                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Finding top ML talent for the AI team...                │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ Market Search Limit                                         │
│ Max candidates to search from external talent market (PDL)  │
│ ════════════════════════○═══════  [50]                     │
│                                                             │
│ ATS Pipeline Limit                                          │
│ Max candidates to fetch from your connected ATS             │
│ ════════════════════════════════○  [100]                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 5.6 Standardize Company DNA Input

**File:** `frontend/src/components/talent-intelligence/NewAnalysisModal.tsx`

Current "Mad Libs" style:
```
"Analyze top [dropdown] employees"
```

Replace with standard labeled input:
```
Employee Search Limit
┌─────────────────────────────────────────────────────────────┐
│ 30                                                          │
└─────────────────────────────────────────────────────────────┘
Maximum number of employees to analyze for company DNA.
```

---

### Phase 6: Draft Auto-Save & State Persistence ✅

> Implemented for improved UX

#### 6.1 Create Draft State Hook

**New File:** `frontend/src/hooks/useAnalysisDraft.ts`

```typescript
interface AnalysisDraft {
  name: string;
  description: string;
  marketLimit: number;
  atsLimit: number;
  // ... all form state
  lastModified: Date;
}

function useAnalysisDraft(configId?: number) {
  // Load from localStorage on mount
  // Save on change (debounced 500ms)
  // Clear on successful save to backend
  // Return { draft, updateDraft, clearDraft, isDirty }
}
```

Key for localStorage: `analysis-draft-{configId}` or `analysis-draft-new`

#### 6.2 Draft Indicator in Header

Show subtle indicator when draft has unsaved changes:
```
┌─────────────────────────────────────────────────────────────┐
│ ✨ Create New Analysis              Draft saved ✓        X │
└─────────────────────────────────────────────────────────────┘
```

- "Draft saved" appears briefly after auto-save
- Fades out after 2 seconds
- Reappears on next change

#### 6.3 Tab Switch Auto-Preserve

State is already preserved when switching tabs (React state). The draft hook adds persistence across:
- Modal close/reopen
- Page refresh
- Browser close (localStorage)

#### 6.4 Footer Actions Update

```
                                    [Save Draft]  [Save & Run]
```

- **Save Draft** (secondary/outline): Saves to backend with `status: 'draft'`, closes modal
- **Save & Run** (primary): Validates required sections, saves, triggers analysis run

Validation for Save & Run:
```typescript
const canRun = 
  name.trim() !== '' &&
  completionState['job-description'] &&
  completionState['candidate-source'];
```

#### 6.5 Content Area Scroll Padding

Add `pb-24` to scrollable content container to prevent content hiding behind floating footer.

---

---

## Optional Work (Deferred)

### Phase 7: Section Content Extraction ⏳

> **Priority:** LOW - Code organization improvement (can be done later)

Extract inline section content into separate components for maintainability:

| Section | New Component File |
|---------|-------------------|
| Analysis Setup | `AnalysisSectionSetup.tsx` |
| ATS Connection | `AnalysisSectionATS.tsx` |
| Career Blueprint | `AnalysisSectionBlueprint.tsx` |
| Company DNA | `AnalysisSectionDNA.tsx` |
| Job Description | `AnalysisSectionJobDesc.tsx` |
| Candidate Source | `AnalysisSectionCandidates.tsx` |
| Ideal Candidate | `AnalysisSectionIdeal.tsx` |

Each component receives only the props it needs, reducing the complexity of `NewAnalysisModal.tsx`.

---

### Phase 8: Final Polish & Cleanup ⏳

> **Priority:** LOW - Post-feature cleanup

#### 8.1 Remove Deprecated Code
- [ ] Remove hidden legacy pill buttons from modal
- [ ] Remove unused state variables
- [ ] Remove old dropdown components

#### 8.2 Testing Checklist
- [ ] Create new analysis (all sections)
- [ ] Edit existing analysis (pre-populated)
- [ ] ATS dependency (Job Description "Select from ATS" disabled until ATS connected)
- [ ] Validation (can't Save & Run without required sections)
- [ ] Draft persistence (close/reopen modal)
- [ ] Dark mode throughout
- [ ] Responsive behavior

#### 8.3 Accessibility
- [ ] Keyboard navigation in sidebar
- [ ] Focus management when switching sections
- [ ] ARIA labels on all interactive elements
- [ ] Screen reader announcements for save/draft status

---

## Implementation Order

```
Phase 5.4 → Create SliderInput DS component
Phase 5.1 → Add "analysis-setup" to analysisConfig.ts
Phase 5.3 → Clean sidebar (remove Limits section)
Phase 5.2 → Simplify modal header
Phase 5.5 → Create Analysis Setup tab content
Phase 5.6 → Standardize Company DNA input
Phase 6.1 → Create useAnalysisDraft hook
Phase 6.2 → Add draft indicator
Phase 6.4 → Update footer actions
Phase 6.5 → Add scroll padding
Phase 7   → Extract section components (optional, can defer)
Phase 8   → Final cleanup
```

---

## File Changes Summary

| Action | File | Phase |
|--------|------|-------|
| Create | `frontend/src/components/ui/slider-input.tsx` | 5.4 |
| Update | `frontend/src/components/talent-intelligence/analysisConfig.ts` | 5.1 |
| Update | `frontend/src/components/talent-intelligence/AnalysisModalSidebar.tsx` | 5.3 |
| Update | `frontend/src/components/talent-intelligence/NewAnalysisModal.tsx` | 5.2, 5.5, 5.6 |
| Create | `frontend/src/hooks/useAnalysisDraft.ts` | 6.1 |
| Update | `frontend/src/pages/design-system/ComponentShowcase.tsx` | 5.4 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionSetup.tsx` | 7 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionATS.tsx` | 7 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionBlueprint.tsx` | 7 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionDNA.tsx` | 7 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionJobDesc.tsx` | 7 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionCandidates.tsx` | 7 |
| Create | `frontend/src/components/talent-intelligence/AnalysisSectionIdeal.tsx` | 7 |

---

## References

- **Design System Doc:** `skills/design-system/DESIGN_SYSTEM_GUIDE.md`
- **Component Showcase:** `http://localhost:3000/design-system`
- **DS Components Index:** `frontend/src/components/ui/index.ts`
- **Existing Modal:** `frontend/src/components/talent-intelligence/NewAnalysisModal.tsx`

---

## Historical Context

### Original Page Components (Pre-Migration)

| Current | DS Replacement | Status |
|---------|---------------|--------|
| `<div className="min-h-screen bg-bg">` | `<Page maxWidth="xl">` | ✅ Done |
| Custom header div | `<PageHeader>` | ✅ Done |
| Custom table | `<DataTable>` with expandable rows | ✅ Done |
| Custom status spans | `<Badge>` variants | ✅ Done |
| Custom error banner | `<Alert variant="error">` | ✅ Done |
| Custom spinner | `<Spinner>` | ✅ Done |
| Custom progress bar | `<Progress>` | ✅ Done |
| Custom modal | DS `Modal` components | ✅ Done |

### Modal Components (Pre-Migration)

| Current | DS Replacement | Status |
|---------|---------------|--------|
| Modal backdrop/container | `Modal`, `ModalBackdrop`, `ModalContent` | ✅ Done |
| Modal header | `ModalHeader`, `ModalTitle` | ✅ Done |
| Pill buttons | `Chip` + Sidebar navigation | ✅ Done |
| Form inputs | `Input`, `Textarea` | ✅ Done |
| Dropdowns | `Popover` / `Select` | ✅ Done |
| Loading states | `Spinner` | ✅ Done |
| Buttons | `Button` with appropriate variants | ✅ Done |
| Modal footer | `ModalFloatingActions` | ✅ Done |

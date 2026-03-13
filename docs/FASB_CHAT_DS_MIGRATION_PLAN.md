# FASB Chat Page - Design System Migration Plan

> **Goal**: Migrate the FASB chat citation and sources UI to the Eliza Forge Design System with proper dark/light mode support and canvas-based PDF viewing.

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [New Components Required](#new-components-required)
3. [Migration Tasks](#migration-tasks)
4. [Component Specifications](#component-specifications)
5. [Implementation Order](#implementation-order)
6. [Testing Checklist](#testing-checklist)

---

## Current State Analysis

### Files Involved

| File | Description |
|------|-------------|
| `frontend/src/components/data-analyst/ConversationView.tsx` | Main chat view with citations and sources |
| `frontend/src/components/ui/chat.tsx` | DS chat components (MessageBubble, CanvasPanel, etc.) |
| `frontend/src/components/shared/PdfPageViewer.tsx` | PDF.js viewer component |

### Current Components (Legacy)

| Component | Location | Issues |
|-----------|----------|--------|
| `renderCitations()` | ConversationView L377-417 | Uses legacy colors, not a DS component |
| `MarkdownAnswerWithSources` | ConversationView L577-787 | Uses legacy colors, modal popup for PDF |
| `PdfPreviewPopup` | ConversationView L58-204 | Modal instead of CanvasPanel, legacy colors |
| Sources dropdown | Inside MarkdownAnswerWithSources | Custom styling, not DS Accordion |
| Source cards | L662-769 | Legacy colors, custom button styling |
| "View Raw Data" button | L1386-1398 | Shows for both RAG and SQL use cases |

### Current Issues

1. **Inline Citations**:
   - Non-interactive (cursor-default, no click handler)
   - Uses legacy colors (`bg-brand/10`, `text-brand`)
   - Not a reusable DS component

2. **Sources Dropdown**:
   - Custom expand/collapse with `useState`
   - Uses `bg-surface`, `text-muted`, `border-border` (legacy tokens)
   - PDF opens in modal popup instead of CanvasPanel

3. **PDF Preview**:
   - Uses `PdfPreviewPopup` modal component
   - Not integrated with DS CanvasPanel
   - Legacy styling throughout

4. **View Raw Data**:
   - Shows for ALL data sources including FASB/RAG
   - Should only show for Text-to-SQL use cases

---

## New Components Required

### 1. `InlineCitation` (New DS Component)

A clickable inline citation badge that opens the source PDF in the canvas panel.

**Location**: `frontend/src/components/ui/inline-citation.tsx`

**Props**:
```typescript
interface InlineCitationProps {
  /** Citation number (e.g., 1, 2, 3) */
  number: number;
  /** Document ID for PDF loading */
  docId?: string;
  /** Page number or range (e.g., "168-168") */
  pageNumber?: string;
  /** Text to highlight in PDF */
  highlightText?: string;
  /** Section/title for the source */
  sectionTitle?: string;
  /** Tooltip text (defaults to "Source [number]") */
  tooltip?: string;
  /** Callback when clicked */
  onClick?: () => void;
  /** Size variant */
  size?: 'sm' | 'md';
}
```

**Behavior**:
- Renders as a small circular/pill badge with the number
- On click, opens the PDF in the CanvasPanel (via ChatContext)
- Hover shows tooltip with source info
- Works with dark/light mode

### 2. `SourcesAccordion` (New DS Component)

A collapsible section for displaying RAG sources with full metadata.

**Location**: `frontend/src/components/ui/sources-accordion.tsx`

**Props**:
```typescript
interface Source {
  index: number;
  docId: string;
  pages: string;
  chunkId: string;
  sectionTitle: string;
  rawCitation: string;
}

interface SourcesAccordionProps {
  /** Array of sources to display */
  sources: Source[];
  /** Callback to open PDF in canvas */
  onShowPdf?: (docId: string, pageNumber: string, highlightText?: string) => void;
  /** Callback to validate citation */
  onValidateCitation?: (index: number) => Promise<CitationValidationResult>;
  /** Question ID for validation API */
  questionId?: string;
  /** Default expanded state */
  defaultExpanded?: boolean;
}
```

**Sub-components**:
- `SourceCard` - Individual source item with all metadata
- Uses DS Accordion internally for expand/collapse

### 3. `SourceCard` (New DS Component)

Individual source display with all metadata and actions.

**Location**: `frontend/src/components/ui/source-card.tsx`

**Props**:
```typescript
interface SourceCardProps {
  /** Source index number */
  index: number;
  /** Document ID */
  docId: string;
  /** Page range */
  pages: string;
  /** Chunk ID (truncated) */
  chunkId: string;
  /** Section title/path */
  sectionTitle: string;
  /** Callback for Show PDF button */
  onShowPdf?: () => void;
  /** Callback for Validate button */
  onValidate?: () => void;
  /** Validation state */
  validationState?: CitationValidationState;
  /** Whether validation is loading */
  isValidating?: boolean;
}
```

### 4. `PdfCanvasViewer` (New DS Component)

PDF viewer designed for the CanvasPanel with highlighting support.

**Location**: `frontend/src/components/ui/pdf-canvas-viewer.tsx`

**Props**:
```typescript
interface PdfCanvasViewerProps {
  /** Document ID */
  docId: string;
  /** Initial page number */
  pageNumber: number;
  /** Text to highlight */
  highlightText?: string;
  /** Show page navigation controls */
  showNavigation?: boolean;
  /** Callback when PDF loads */
  onLoad?: () => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}
```

**Features**:
- Renders in CanvasPanel (not modal)
- Toggle between PDF.js (highlighting) and iframe (fallback)
- Header with doc info, page number, controls
- Open in new tab link
- Loading state with DS Spinner

---

## Migration Tasks

### Phase 1: Create New DS Components (Est: 4-5 hours)

#### Task 1.1: Create `InlineCitation` Component
- [ ] Create `frontend/src/components/ui/inline-citation.tsx`
- [ ] Implement clickable badge with proper DS colors
- [ ] Add hover tooltip using DS Tooltip component
- [ ] Integrate with ChatContext to open CanvasPanel
- [ ] Export from `frontend/src/components/ui/index.ts`
- [ ] Support dark/light mode

#### Task 1.2: Create `SourceCard` Component
- [ ] Create `frontend/src/components/ui/source-card.tsx`
- [ ] Display all metadata (Doc ID, Pages, Chunk ID as badges)
- [ ] Add "Show PDF" button using DS Button
- [ ] Add "Validate citation" button using DS Button
- [ ] Display validation results (pass/fail/unsure with score)
- [ ] Export from index.ts

#### Task 1.3: Create `SourcesAccordion` Component
- [ ] Create `frontend/src/components/ui/sources-accordion.tsx`
- [ ] Use DS Accordion for expand/collapse
- [ ] Integrate SourceCard for each source
- [ ] Add source count badge
- [ ] Export from index.ts

#### Task 1.4: Create `PdfCanvasViewer` Component
- [ ] Create `frontend/src/components/ui/pdf-canvas-viewer.tsx`
- [ ] Integrate existing PdfPageViewer for PDF.js mode
- [ ] Add iframe fallback mode
- [ ] Create header with doc info and controls
- [ ] Add toggle for highlighting mode
- [ ] Export from index.ts

### Phase 2: Integrate Components (Est: 2-3 hours)

#### Task 2.1: Update `renderCitations()` to use `InlineCitation`
- [ ] Import InlineCitation in ConversationView
- [ ] Replace badge render with InlineCitation component
- [ ] Pass docId, pageNumber from source data if available
- [ ] Wire up onClick to open PDF in canvas

#### Task 2.2: Replace Sources Section with `SourcesAccordion`
- [ ] Replace custom sources dropdown in MarkdownAnswerWithSources
- [ ] Remove local sourcesExpanded state
- [ ] Pass sources array to SourcesAccordion
- [ ] Wire up onShowPdf to open CanvasPanel with PdfCanvasViewer
- [ ] Wire up onValidateCitation to existing validation logic

#### Task 2.3: Remove `PdfPreviewPopup` Modal
- [ ] Remove PdfPreviewPopup component definition
- [ ] Remove pdfPreview state from MarkdownAnswerWithSources
- [ ] Use ChatContext to open PDF in CanvasPanel instead

#### Task 2.4: Hide "View Raw Data" for RAG Use Cases
- [ ] Add prop to distinguish RAG vs SQL mode
- [ ] Conditionally render ArtifactButton for raw data
- [ ] Keep SQL query artifact for both modes (if applicable)

### Phase 3: Dark/Light Mode Polish (Est: 1-2 hours)

#### Task 3.1: Replace Legacy Color Tokens
| Legacy Token | DS Token |
|--------------|----------|
| `text-text` | `text-charcoal dark:text-gray-100` |
| `text-muted` | `text-gray-500 dark:text-gray-400` |
| `bg-surface` | `bg-white dark:bg-dark-surface` |
| `bg-surface-2` | `bg-gray-50 dark:bg-dark-surface-2` |
| `border-border` | `border-gray-200 dark:border-dark-border` |
| `text-brand` | `text-eliza-red` |
| `bg-brand/10` | `bg-eliza-red/10` |

#### Task 3.2: Verify All New Components in Dark Mode
- [ ] Test InlineCitation
- [ ] Test SourceCard
- [ ] Test SourcesAccordion
- [ ] Test PdfCanvasViewer
- [ ] Test full chat flow

### Phase 4: Showcase & Documentation (Est: 1-2 hours)

#### Task 4.1: Add Components to Showcase
- [ ] Add "Citations & Sources" section to ComponentShowcase.tsx
- [ ] Add InlineCitation examples (different sizes, states)
- [ ] Add SourceCard examples (with/without validation)
- [ ] Add SourcesAccordion example with multiple sources
- [ ] Add PdfCanvasViewer in a mock canvas container

#### Task 4.2: Update DESIGN_SYSTEM.md
- [ ] Add Citations section under Components
- [ ] Document InlineCitation props and usage
- [ ] Document SourcesAccordion props and usage
- [ ] Document SourceCard props and usage
- [ ] Document PdfCanvasViewer props and usage
- [ ] Add to migration tracker

---

## Component Specifications

### InlineCitation Visual Spec

```
Light Mode:                      Dark Mode:
┌─────┐                          ┌─────┐
│  1  │ ← bg-eliza-red/10        │  1  │ ← bg-eliza-red/20
│     │   text-eliza-red         │     │   text-eliza-red-light
│     │   border-eliza-red/20    │     │   border-eliza-red/30
└─────┘                          └─────┘
   ↓ hover                          ↓ hover
┌─────┐                          ┌─────┐
│  1  │ ← bg-eliza-red/20        │  1  │ ← bg-eliza-red/30
└─────┘   cursor-pointer         └─────┘   cursor-pointer
```

**Sizes**:
- `sm`: h-5 min-w-5 text-[10px]
- `md`: h-6 min-w-6 text-xs

### SourcesAccordion Visual Spec

```
┌──────────────────────────────────────────────────────────────┐
│ ▶ 📄 Sources  [8]                                            │ ← Collapsed
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ ▼ 📄 Sources  [8]                                            │ ← Expanded header
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ (1)  [Doc 815] [Pages 168-168] [#844ff052]               │ │ ← SourceCard
│ │                                                          │ │
│ │ 815 Derivatives and Hedging > 10 Overall > 20 Glossary   │ │ ← Section path
│ │                                                          │ │
│ │                          [📄 Show PDF] [Validate citation]│ │ ← Actions
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ (2)  [Doc 815] [Pages 259-260] [#1af2bd3b]               │ │
│ │ ...                                                      │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### SourceCard Visual Spec (with Validation)

```
┌──────────────────────────────────────────────────────────────────┐
│ (1)    [Doc 815]  [Pages 168-168]  [#844ff052]                   │
│  ↑        ↑           ↑               ↑                          │
│ Badge  DocBadge   PagesBadge      ChunkBadge                     │
│                                                                  │
│ 815 Derivatives and Hedging > 10 Overall > 20 Glossary           │
│                                                                  │
│                                   [📄 Show PDF] [Validate citation]
└──────────────────────────────────────────────────────────────────┘

After validation (pass):
┌──────────────────────────────────────────────────────────────────┐
│ (1)    [Doc 815]  [Pages 168-168]  [#844ff052]                   │
│                                                                  │
│ 815 Derivatives and Hedging > 10 Overall > 20 Glossary           │
│                                                                  │
│ [PASS] 87.5%                                   [📄 Show PDF]     │
│ The source supports the claim about security definitions.        │
│ "A security is defined as a share, participation..."            │
└──────────────────────────────────────────────────────────────────┘
```

### PdfCanvasViewer in CanvasPanel

```
┌─────────────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📄 Document 815                               [×] Close     │ │ ← Canvas header
│ │    Page 168-168                                             │ │
│ ├─────────────────────────────────────────────────────────────┤ │
│ │ [✓ Highlighting]                    [Open in new tab ↗]    │ │ ← Controls
│ ├─────────────────────────────────────────────────────────────┤ │
│ │                                                             │ │
│ │                                                             │ │
│ │                   PDF Content Here                          │ │
│ │                                                             │ │
│ │                                                             │ │
│ │                                                             │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Order

```
Week 1:
├── Day 1-2: Phase 1 (Create DS Components)
│   ├── InlineCitation
│   ├── SourceCard
│   ├── SourcesAccordion
│   └── PdfCanvasViewer
│
├── Day 3: Phase 2 (Integration)
│   ├── Wire up InlineCitation in renderCitations
│   ├── Replace sources dropdown
│   └── Remove PdfPreviewPopup modal
│
├── Day 4: Phase 2 continued + Phase 3
│   ├── Hide View Raw Data for RAG
│   └── Dark/light mode polish
│
└── Day 5: Phase 4 (Showcase & Docs)
    ├── Add to ComponentShowcase
    └── Update DESIGN_SYSTEM.md
```

---

## Testing Checklist

### Functional Tests

- [ ] Inline citation click opens PDF in canvas panel
- [ ] Multiple citations in same paragraph work correctly
- [ ] Sources accordion expands/collapses
- [ ] Show PDF button opens correct page in canvas
- [ ] Validate citation button calls API and shows result
- [ ] Pass/Fail/Unsure validation states display correctly
- [ ] Canvas panel closes correctly
- [ ] PDF.js highlighting works when enabled
- [ ] Iframe fallback works when PDF.js fails
- [ ] "Open in new tab" link works
- [ ] View Raw Data hidden for FASB/RAG data source
- [ ] View Raw Data shown for SQL data sources

### Visual Tests (Light Mode)

- [ ] InlineCitation uses eliza-red colors
- [ ] SourceCard has white background
- [ ] Badges have gray-100 background
- [ ] Text uses charcoal color
- [ ] Borders use gray-200

### Visual Tests (Dark Mode)

- [ ] InlineCitation uses eliza-red-light
- [ ] SourceCard has dark-surface background
- [ ] Badges have dark-surface-2 background
- [ ] Text uses gray-100 color
- [ ] Borders use dark-border

### Accessibility Tests

- [ ] Citations have proper aria-labels
- [ ] Accordion has proper aria-expanded
- [ ] Buttons are keyboard accessible
- [ ] Focus states are visible
- [ ] Tooltips are accessible

---

## Files to Create

| File | Description |
|------|-------------|
| `frontend/src/components/ui/inline-citation.tsx` | Clickable citation badge |
| `frontend/src/components/ui/source-card.tsx` | Individual source display |
| `frontend/src/components/ui/sources-accordion.tsx` | Collapsible sources section |
| `frontend/src/components/ui/pdf-canvas-viewer.tsx` | PDF viewer for canvas |

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/components/ui/index.ts` | Export new components |
| `frontend/src/components/data-analyst/ConversationView.tsx` | Use new DS components |
| `frontend/src/pages/design-system/ComponentShowcase.tsx` | Add examples |
| `frontend/src/components/ui/DESIGN_SYSTEM.md` | Document new components |

---

## Dependencies

- Existing: `ChatContext` (useChat hook for canvas control)
- Existing: `CanvasPanel` (for PDF viewing)
- Existing: `PdfPageViewer` (for PDF.js rendering)
- Existing: DS Accordion components
- Existing: DS Button, Badge, Tooltip components

---

## Notes

### Why CanvasPanel instead of Modal?

1. **Consistency**: Other artifacts (SQL, Data Tables) use CanvasPanel
2. **Better UX**: Side-by-side viewing with chat context
3. **DS Alignment**: Uses existing DS patterns
4. **Resizable**: CanvasPanel supports resize, modal doesn't

### Why Hide "View Raw Data" for RAG?

1. RAG responses don't have structured row data
2. The "raw data" for RAG is the source documents (already in Sources)
3. Avoids confusion about what "raw data" means in document context
4. SQL responses have actual tabular data that benefits from DataTable view

### Citation Number Resolution

Currently, inline citations `[1]`, `[2]` etc. render as badges but don't link to specific sources because:
1. The markdown is processed before sources are parsed
2. Citation numbers in text may not map 1:1 to source indices

**Solution**: Parse sources first, create a mapping, pass to renderCitations so each badge knows its source data.

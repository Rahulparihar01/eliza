# AI Chat Page Migration Plan

> **Status:** ✅ Complete (All 7 Phases Done)
> **Created:** 2026-01-12
> **Updated:** 2026-01-13

---

## Known Issues / Future Improvements

### 1. SSE Execution Steps Not Showing for Fast Queries
**Priority:** Low  
**Type:** UX Enhancement

**Issue:** The ThinkingIndicator execution steps don't appear for queries that complete quickly (< 1-2 seconds). The SSE connection is established but the query completes before any events can be received.

**Root Cause:** 
- SSE EventSource takes time to connect
- Fast queries complete before SSE can send/receive events
- Message status transitions from `processing` → `completed` faster than SSE roundtrip

**Potential Solutions:**
1. **Simulated Steps** - Show estimated progress steps based on elapsed time
2. **Backend Buffering** - Buffer SSE events and send them even for fast queries
3. **Minimum Display Time** - Keep ThinkingIndicator visible for minimum 1-2 seconds
4. **Optimistic Steps** - Show common steps immediately ("Analyzing...", "Generating SQL...", "Executing...")

**Files Involved:**
- `frontend/src/components/data-analyst/ConversationView.tsx` - SSE connection logic
- Backend SSE endpoint - `/v1/data-analyst/questions/{id}/stream`

**Workaround:** For now, fast queries show "Analyzing..." shimmer briefly and then display results. This is acceptable UX.
> **Est. Time:** 14-20 hours (7 phases)  
> **Goal:** Migrate AI Chat (Data Analyst) page to use Design System components

---

## Overview

The AI Chat page uses a **two-step flow**:
1. **Domain Selection** - User picks a data domain (e.g., Insurance Analytics)
2. **Chat Interface** - Full chat experience with conversation history

We will use **existing DS components** from `chat.tsx` and `prompt-bar.tsx` rather than building new ones.

---

## Current Architecture

### Page Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Domain Selection (no sidebar submenu yet)                           │
│                                                                             │
│              ┌───────────────────────────────────────┐                      │
│              │     Select an Analytics Domain        │                      │
│              │   Choose a domain to start asking     │                      │
│              ├───────────────────────────────────────┤                      │
│              │  📊 Insurance Analytics          →    │                      │
│              │  Query insurance policy, claim...     │                      │
│              ├───────────────────────────────────────┤                      │
│              │  + Onboard New Domain (coming soon)   │                      │
│              └───────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Chat Interface (with sidebar submenu)                               │
│                                                                             │
│ ┌──────────────────┐  ┌───────────────────────────────────────────────────┐ │
│ │ ← Back           │  │                                                   │ │
│ │                  │  │    You: "count claims from last year"             │ │
│ │ AI ASSISTANT     │  │                                                   │ │
│ │  💬 Chat ←       │  │    Eliza: (Thinking... shimmer)                   │ │
│ │  📋 Question Log │  │           [Execution Steps Checklist]             │ │
│ │  📄 Documents    │  │                                                   │ │
│ │                  │  │    Eliza: Here's what I found...                  │ │
│ │ ────────────────── │  │           [Charts] [Data Table] [SQL]            │ │
│ │ CONVERSATIONS    │  │                                                   │ │
│ │  [+ New Chat]    │  │                                                   │ │
│ │                  │  │                                                   │ │
│ │  ○ Conv 15cc80   │  │ ┌───────────────────────────────────────────────┐ │ │
│ │  ● Conv abd423 ← │  │ │ Ask a question about your data...    [Send]  │ │ │
│ │                  │  │ └───────────────────────────────────────────────┘ │ │
│ └──────────────────┘  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Files

| File | Purpose | Keep/Replace |
|------|---------|--------------|
| `pages/data-analyst/DataAnalystPage.tsx` | Main page with domain selection + chat layout | **Refactor** |
| `components/data-analyst/DataSourceSelector.tsx` | Domain picker (Step 1) | **Migrate to DS** |
| `components/data-analyst/ConversationList.tsx` | Left sidebar with conversations | **Remove** - move to sidebar submenu |
| `components/data-analyst/ConversationView.tsx` | Main chat area with messages | **Migrate to DS Chat** |
| `components/data-analyst/DataTable.tsx` | Results table | **Keep** - styling pass |
| `components/data-analyst/ChartDisplay.tsx` | Visualization charts | **Keep** - styling pass |
| `components/data-analyst/MessageThread.tsx` | (Legacy?) message rendering | **Remove** if unused |
| `components/data-analyst/QuestionChat.tsx` | (Legacy?) chat component | **Remove** if unused |

---

## Available DS Components

### ✅ Chat Components (`chat.tsx`)

| Component | Description | Use For |
|-----------|-------------|---------|
| `ChatProvider` | Context for canvas state | Wrap chat page |
| `ChatContainer` | Main flex container | Page layout |
| `ChatMessagesPane` | Message area wrapper | Main content |
| `ChatScrollArea` | Auto-scrolling message list | Message list |
| `MessageBubble` | User/assistant message styling | Each message |
| `MessageContent` | Prose/markdown styling | Message text |
| `ThinkingIndicator` | Shimmer "Thinking..." with expandable trace | Processing state |
| `ChatImage` | Image attachments | Result images |
| `ChatCodeBlock` | Code blocks with copy/canvas | SQL display |
| `CanvasPanel` | Side panel for artifacts | Charts/data expanded |
| `ArtifactButton` | Inline button to open canvas | Chart/table links |
| `ChatInputArea` | Wrapper for prompt bar | Input container |

### ✅ Prompt Bars (`prompt-bar.tsx`)

| Component | Description | Use For |
|-----------|-------------|---------|
| `PromptBar` | Basic text input with send button | Simple chat input |
| `PromptBarWithAttachments` | With file upload, drag & drop | Future: file upload |
| `PromptBarWithTools` | Full featured with tools dropdown | Future: tool selection |

### ✅ Sidebar Submenu (Existing Pattern)

The **AI Assistant** section already exists in `sectionConfigs.ts`:

```typescript
export const biAssistantConfig: SectionConfig = {
  id: 'bi-assistant',
  title: 'AI Assistant',
  icon: ChatBubbleLeftRightIcon,
  basePath: '/data-analyst',
  items: [
    { label: 'Chat', path: '/data-analyst', icon: ChatBubbleLeftRightIcon },
    { label: 'Question Log', path: '/business-intelligence', icon: ClipboardDocumentListIcon },
    { label: 'Documents', path: '/knowledge-base', icon: DocumentTextIcon },
  ],
};
```

**Enhancement needed:** Add **Conversations** section below the nav items.

---

## Component Mapping (1:1)

### 1. Domain Selection Screen

| Current | DS Component |
|---------|--------------|
| Custom flex layout | `PageContent` centered |
| "Select an Analytics Domain" heading | `SectionHeader` title + description |
| Domain card buttons | `Card` with hover effects |
| Card icon container | Custom with DS colors |
| "Onboard New Domain" placeholder | `Card` with dashed border |

### 2. Sidebar with Conversations

| Current (`ConversationList.tsx`) | DS Approach |
|----------------------------------|-------------|
| Custom sidebar container | **Extend `biAssistantConfig`** in `sectionConfigs.ts` |
| "CONVERSATIONS" header | `SidebarSection` title |
| "New Conversation" button | `Button` variant="brand" size="sm" |
| "New Group" button | `Button` variant="secondary" size="sm" |
| Conversation list items | Custom styled divs (like SubmenuItem) |
| Selected conversation | Active state styling |
| Delete button on hover | Icon button on hover |
| Empty state | DS empty state pattern |

**Implementation:**
- Create new `SidebarSubmenuWithConversations` variant or
- Extend `SectionNavContent` to accept custom bottom section

### 3. Chat Area

| Current (`ConversationView.tsx`) | DS Component |
|----------------------------------|--------------|
| Flex container | `ChatContainer` + `ChatMessagesPane` |
| Scrollable message area | `ChatScrollArea` |
| User message bubble | `MessageBubble role="user"` |
| AI message bubble | `MessageBubble role="assistant"` |
| AI avatar (SparklesIcon) | `MessageBubble showAvatar` (built-in) |
| User avatar (UserCircleIcon) | `MessageBubble avatar={...}` |
| Processing indicator (steps) | `ThinkingIndicator` (shimmer) |
| Processing steps list | Keep custom OR simplify to shimmer |
| Clarification alert (amber) | `Alert variant="warning"` |
| Clarification input | `PromptBar` (secondary) |
| Error message | `Alert variant="error"` |
| Success message | `MessageContent` (prose) |
| Empty state | DS empty state pattern |

### 4. Message Results

| Current | DS Component |
|---------|--------------|
| Summary text | `MessageContent` (prose styling) |
| Key metrics grid | `Card` grid or custom |
| Charts | `ChartDisplay` (keep) → `ArtifactButton` to open |
| "View Raw Data" toggle | `Button` variant="secondary" size="sm" |
| Data table | `DataTable` (keep) → `ArtifactButton` to open |
| SQL collapsible | `ChatCodeBlock` with collapse |
| Canvas panel | `CanvasPanel` (for expanded view) |

### 5. Input Bar

| Current | DS Component |
|---------|--------------|
| `<form>` container | `ChatInputArea` |
| Text input | `PromptBar` |
| Submit button | Built into `PromptBar` |
| Loading state | `PromptBar loading={true}` |

---

## Implementation Plan

---

### Phase 1: Foundation & Chat Container ⭐ (Start Here)
**Est. Time:** 2-3 hours  
**Goal:** Set up the base chat structure using DS components without breaking existing functionality.

#### Step 1.1: Add ChatProvider Context
**File:** `pages/data-analyst/DataAnalystPage.tsx`
```tsx
// Wrap the page content
<ChatProvider>
  {/* existing content */}
</ChatProvider>
```
- [ ] Import `ChatProvider` from `@/components/ui/chat`
- [ ] Wrap main page content with `ChatProvider`
- [ ] Verify existing functionality still works

#### Step 1.2: Replace Main Layout with ChatContainer
**File:** `pages/data-analyst/DataAnalystPage.tsx`
- [ ] Replace outer flex container with `ChatContainer`
- [ ] Replace message area wrapper with `ChatMessagesPane`
- [ ] Add `ChatScrollArea` for auto-scrolling message list
- [ ] Add `ChatInputArea` wrapper for input at bottom
- [ ] Verify layout matches current design

#### Step 1.3: Set Up CanvasPanel Structure
**File:** `pages/data-analyst/DataAnalystPage.tsx`
- [ ] Add `CanvasPanel` component (initially hidden)
- [ ] Connect to `useChatCanvas()` hook from ChatProvider
- [ ] Add open/close state management
- [ ] Test panel opens/closes correctly

**Checkpoint:** Page renders with DS layout containers, existing messages still work.

---

### Phase 2: Message Components Migration
**Est. Time:** 2-3 hours  
**Goal:** Replace custom message rendering with DS MessageBubble components.

#### Step 2.1: Replace User Messages
**File:** `components/data-analyst/ConversationView.tsx` (or new component)
- [ ] Import `MessageBubble`, `MessageContent` from `@/components/ui/chat`
- [ ] Replace user message div with `<MessageBubble role="user">`
- [ ] Wrap message text in `<MessageContent>`
- [ ] Test user messages render correctly

#### Step 2.2: Replace Assistant Messages
- [ ] Replace AI message div with `<MessageBubble role="assistant">`
- [ ] Add `showAvatar` prop for Eliza avatar
- [ ] Wrap response text in `<MessageContent>`
- [ ] Test assistant messages with proper styling

#### Step 2.3: Replace Processing Indicator
- [ ] Import `ThinkingIndicator` from `@/components/ui/chat`
- [ ] Map current SSE execution steps to `ThinkingIndicator` steps format:
  ```tsx
  <ThinkingIndicator
    label={activeStepLabel}
    steps={executionSteps.map(s => ({
      id: s.id,
      label: s.name,
      status: s.status, // pending | active | completed | failed
      description: s.description
    }))}
  />
  ```
- [ ] Connect to SSE stream for real-time updates
- [ ] Test shimmer animation and step progression

**Checkpoint:** All messages render with DS styling, processing shows shimmer with steps.

---

### Phase 3: Input Bar & Prompt Migration
**Est. Time:** 1-2 hours  
**Goal:** Replace custom input form with DS PromptBar.

#### Step 3.1: Replace Input Form
**File:** `components/data-analyst/ConversationView.tsx`
- [ ] Remove custom `<form>` and `<input>`
- [ ] Import `PromptBar` from `@/components/ui/prompt-bar`
- [ ] Add PromptBar with props:
  ```tsx
  <PromptBar
    value={inputValue}
    onChange={setInputValue}
    onSubmit={handleSubmit}
    placeholder="Ask a question about your data..."
    loading={isProcessing}
  />
  ```
- [ ] Wire up existing submit handler
- [ ] Test question submission works

#### Step 3.2: Handle Loading State
- [ ] Pass `loading={true}` when processing
- [ ] Verify input is disabled during processing
- [ ] Test submit button shows loading spinner

**Checkpoint:** Questions can be submitted using DS PromptBar, loading states work.

---

### Phase 4: Canvas & Artifacts System
**Est. Time:** 3-4 hours  
**Goal:** Implement SQL and Data artifacts in expandable CanvasPanel.

#### Step 4.1: Create Artifact State Management
**File:** `pages/data-analyst/DataAnalystPage.tsx` or new hook
- [ ] Define artifact types:
  ```tsx
  type ArtifactType = 'sql' | 'data' | 'chart';
  interface Artifact {
    id: string;
    type: ArtifactType;
    content: any; // SQL string or data array
    messageId: string;
  }
  ```
- [ ] Create state: `const [activeArtifact, setActiveArtifact] = useState<Artifact | null>(null)`
- [ ] Create state: `const [isCanvasExpanded, setIsCanvasExpanded] = useState(false)`

#### Step 4.2: Add ArtifactButtons to Messages
**File:** Message rendering component
- [ ] Import `ArtifactButton` from `@/components/ui/chat`
- [ ] After each AI response with results, render:
  ```tsx
  <div className="flex gap-2 mt-3">
    <ArtifactButton
      icon={<TableCellsIcon />}
      label="View Raw Data"
      onClick={() => setActiveArtifact({ type: 'data', content: resultData, ... })}
    />
    <ArtifactButton
      icon={<CodeBracketIcon />}
      label="View SQL Query"
      onClick={() => setActiveArtifact({ type: 'sql', content: sqlQuery, ... })}
    />
  </div>
  ```
- [ ] Style buttons to match design

#### Step 4.3: Render Artifacts in CanvasPanel
**File:** `pages/data-analyst/DataAnalystPage.tsx`
- [ ] Update CanvasPanel content based on `activeArtifact`:
  ```tsx
  <CanvasPanel isOpen={!!activeArtifact} onClose={() => setActiveArtifact(null)}>
    <CanvasHeader>
      <button onClick={() => setIsCanvasExpanded(!isCanvasExpanded)}>
        {isCanvasExpanded ? 'Minimize' : 'Expand'}
      </button>
      <button onClick={() => setActiveArtifact(null)}>Close</button>
    </CanvasHeader>
    {activeArtifact?.type === 'sql' && (
      <ChatCodeBlock language="sql" code={activeArtifact.content} />
    )}
    {activeArtifact?.type === 'data' && (
      <DataTable data={activeArtifact.content} />
    )}
  </CanvasPanel>
  ```
- [ ] Implement expand/minimize toggle
- [ ] Style panel width (default 40%, expanded 60%+)

#### Step 4.4: Auto-Open Canvas on New Results
- [ ] When query completes, auto-set first artifact (data or SQL)
- [ ] Or keep closed and let user click to open

**Checkpoint:** Clicking artifact buttons opens CanvasPanel with correct content, expand works.

---

### Phase 5: Sidebar Conversations
**Est. Time:** 2-3 hours  
**Goal:** Move conversation list into sidebar submenu.

#### Step 5.1: Create SidebarConversationList Component
**File:** `components/navigation/SidebarConversationList.tsx` (new)
- [ ] Extract conversation fetching logic from `ConversationList.tsx`
- [ ] Create compact conversation item component:
  ```tsx
  <div className="px-3 py-2 hover:bg-gray-100 cursor-pointer">
    <div className="text-sm font-medium truncate">{title || 'Untitled'}</div>
    <div className="text-xs text-gray-500">{messageCount} msgs · {date}</div>
  </div>
  ```
- [ ] Add "New Chat" button at top
- [ ] Add delete on hover functionality

#### Step 5.2: Integrate into Sidebar Submenu
**File:** `components/navigation/SectionNavContent.tsx`
- [ ] Add `bottomContent?: React.ReactNode` prop
- [ ] Render bottomContent below nav items
- [ ] Or create `BIAssistantSidebar` custom variant

#### Step 5.3: Connect to Page State
**File:** `pages/data-analyst/DataAnalystPage.tsx`
- [ ] Pass `selectedConversationId` to sidebar
- [ ] Pass `onConversationSelect` callback
- [ ] Pass `onNewChat` callback
- [ ] Remove old `ConversationList.tsx` from main layout

**Checkpoint:** Conversations appear in sidebar, selecting switches chat, new chat works.

---

### Phase 6: Domain Selection (Zero State + Header)
**Est. Time:** 2-3 hours  
**Goal:** Implement domain picker for new chats and header context pill.

#### Step 6.1: Create DomainContextPill Component
**File:** `components/ui/domain-context-pill.tsx` (new)
- [ ] Create pill component:
  ```tsx
  <button className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-full">
    <CircleStackIcon className="w-4 h-4" />
    <span>{domain.name}</span>
    <ChevronDownIcon className="w-3 h-3" />
  </button>
  ```
- [ ] Add dropdown menu for domain switching
- [ ] Style active/hover states

#### Step 6.2: Implement State Machine
**File:** `pages/data-analyst/DataAnalystPage.tsx`
- [ ] Define states: `'no-domain' | 'has-domain'`
- [ ] When `no-domain`:
  - Show `DataSourceSelector` cards (full screen)
  - Hide PromptBar
- [ ] When `has-domain`:
  - Show DomainContextPill in header
  - Show chat + PromptBar

#### Step 6.3: Update DataSourceSelector Styling
**File:** `components/data-analyst/DataSourceSelector.tsx`
- [ ] Apply DS Card styling
- [ ] Use DS SectionHeader for title
- [ ] Ensure consistent colors/spacing

#### Step 6.4: Handle Domain Switching
- [ ] When pill clicked, show dropdown
- [ ] On domain change, show confirmation: "Start new chat with [domain]?"
- [ ] Create new conversation with selected domain

**Checkpoint:** New users see domain picker, active chats show header pill, switching works.

---

### Phase 7: Polish & Dark Mode
**Est. Time:** 1-2 hours  
**Goal:** Final styling pass and dark mode verification.

#### Step 7.1: Dark Mode Verification
- [ ] Test all components in dark mode
- [ ] Fix any hardcoded colors
- [ ] Verify CanvasPanel dark mode
- [ ] Verify DataTable dark mode

#### Step 7.2: Empty States
- [ ] Add empty state for no conversations
- [ ] Add empty state for new conversation (before first message)
- [ ] Use DS empty state patterns

#### Step 7.3: Loading States
- [ ] Add skeleton for conversation list loading
- [ ] Add skeleton for message history loading
- [ ] Use DS Spinner/Skeleton components

#### Step 7.4: Error States
- [ ] Replace custom error displays with DS Alert
- [ ] Add retry buttons where appropriate

#### Step 7.5: Accessibility Audit
- [ ] Verify keyboard navigation
- [ ] Check focus states
- [ ] Test with screen reader

**Checkpoint:** Full dark mode support, consistent empty/loading/error states.

---

## Implementation Summary

| Phase | Goal | Est. Time | Dependencies |
|-------|------|-----------|--------------|
| 1 | Foundation & Chat Container | 2-3h | None |
| 2 | Message Components | 2-3h | Phase 1 |
| 3 | Input Bar & Prompt | 1-2h | Phase 1 |
| 4 | Canvas & Artifacts | 3-4h | Phase 1, 2 |
| 5 | Sidebar Conversations | 2-3h | None (parallel) |
| 6 | Domain Selection | 2-3h | Phase 1 |
| 7 | Polish & Dark Mode | 1-2h | All phases |

**Total Estimated Time:** 14-20 hours

**Recommended Order:**
1. Phase 1 (Foundation) - Required first
2. Phase 5 (Sidebar) - Can run parallel with 2-4
3. Phase 2 (Messages) - After Phase 1
4. Phase 3 (Input) - After Phase 1
5. Phase 4 (Canvas/Artifacts) - After Phase 2
6. Phase 6 (Domain) - After Phase 1
7. Phase 7 (Polish) - Last

---

## Key Decisions

### 1. Sidebar Conversations
**Decision:** Extend sidebar submenu pattern with conversation list below nav items.
**Rationale:** Consistent with app-specific sidebar pattern (like AI Recruiter).

### 2. Processing Indicator (UPDATED)
**Decision:** Extended `ThinkingIndicator` to support execution steps with status tracking.
**Implementation:** Added `steps` prop to `ThinkingIndicator`:
```tsx
<ThinkingIndicator
  label="Executing query..."  // Current active step (shimmer)
  steps={[
    { id: '1', label: 'Parsing question', status: 'completed' },
    { id: '2', label: 'Generating SQL', status: 'active', description: 'Creating query...' },
    { id: '3', label: 'Executing query', status: 'pending' },
  ]}
/>
```
**Features:**
- Steps show as expandable checklist below shimmer label
- Status: `pending`, `active`, `completed`, `failed`
- Active step label becomes the shimmer text
- Steps can have optional descriptions

### 3. Domain Selection (UPDATED - Hybrid Approach)

**Decision:** Use "Zero State Hero" + "Header Context" pattern (recommended by Gemini).

**The Problem with Prompt Bar Placement:**
- Low discoverability - users might query wrong database
- Small indicator tucked near keyboard
- Long enterprise dataset names clutter input area

**The Hybrid Solution:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STATE 1: New Chat (Zero State)                                              │
│                                                                             │
│ ┌──────────────────┐  ┌───────────────────────────────────────────────────┐ │
│ │ ← Back           │  │                                                   │ │
│ │                  │  │     ┌─────────────────────────────────────┐       │ │
│ │ AI ASSISTANT     │  │     │   Select an Analytics Domain       │       │ │
│ │  💬 Chat         │  │     │   Choose a domain to start asking  │       │ │
│ │  📋 Question Log │  │     ├─────────────────────────────────────┤       │ │
│ │  📄 Documents    │  │     │ 📊 Insurance Analytics        →    │       │ │
│ │                  │  │     │ Query policies, claims, customers  │       │ │
│ │ CONVERSATIONS    │  │     ├─────────────────────────────────────┤       │ │
│ │  [+ New Chat]    │  │     │ 💰 Finance Analytics          →    │       │ │
│ │                  │  │     │ Revenue, expenses, forecasts       │       │ │
│ │  ○ Conv 1        │  │     └─────────────────────────────────────┘       │ │
│ │  ○ Conv 2        │  │                                                   │ │
│ │                  │  │     [Prompt bar hidden or disabled]               │ │
│ └──────────────────┘  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓ User clicks domain
┌─────────────────────────────────────────────────────────────────────────────┐
│ STATE 2: Active Chat (Domain Selected)                                      │
│                                                                             │
│ ┌──────────────────┐  ┌───────────────────────────────────────────────────┐ │
│ │ ← Back           │  │ [📊 Insurance Analytics ▾]     ← Header Context   │ │
│ │                  │  ├───────────────────────────────────────────────────┤ │
│ │ AI ASSISTANT     │  │                                                   │ │
│ │  💬 Chat ←       │  │    You: "count claims from last year"             │ │
│ │  📋 Question Log │  │                                                   │ │
│ │  📄 Documents    │  │    Eliza: Here's what I found...                  │ │
│ │                  │  │                                                   │ │
│ │ CONVERSATIONS    │  │                                                   │ │
│ │  [+ New Chat]    │  │                                                   │ │
│ │                  │  │ ┌───────────────────────────────────────────────┐ │ │
│ │  ● Conv 15cc80 ← │  │ │ Ask a question about your data...    [Send]  │ │ │
│ │  ○ Conv abd423   │  │ └───────────────────────────────────────────────┘ │ │
│ └──────────────────┘  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

1. **Zero State (New Chat):**
   - Keep existing `DataSourceSelector` cards component
   - Shows when no domain selected OR new empty conversation
   - Prompt bar hidden/disabled until domain picked
   - Forces conscious choice, prevents errors

2. **Header Context Pill (Active Chat):**
   - Domain shown as clickable pill in top-left of chat area
   - Click opens dropdown to switch domains
   - Always visible but never in the way of typing
   - Pattern: `[📊 Insurance Analytics ▾]`

3. **Domain Switching:**
   - Switching domain mid-chat could:
     - Start a new conversation (safer)
     - Show warning "This will start a new chat with [domain]"
   - Preserves conversation context per domain

**New Component Needed:** `DomainContextPill`
```tsx
<DomainContextPill
  domains={availableDomains}
  selectedDomain={currentDomain}
  onDomainChange={(domain) => {
    // Confirm and switch or start new chat
  }}
/>
```

**Benefits:**
- High discoverability for new users (hero cards)
- Clear global context (header pill always visible)
- Clean prompt bar focused on typing
- Matches ChatGPT/Gemini mental model
- Works with long enterprise dataset names

### 4. Message Bubbles
**Decision:** Use `MessageBubble` with built-in avatar support.
**Rationale:** DS already handles user vs assistant styling.

### 5. Results Display
**Decision:** Keep inline with chat, add `ArtifactButton` to open in `CanvasPanel`.
**Rationale:** Matches ChatGPT-style artifact expansion pattern.

### 6. Auto-Generated Artifacts (SQL + Data)
**Decision:** When a query runs, both **SQL** and **Data results** automatically appear as artifacts in the canvas system.

**Behavior:**
- SQL artifact: Created when SQL is generated (before execution)
- Data artifact: Created when query results return
- Both visible inline via `ArtifactButton` in the chat pane
- User clicks artifact button to open in `CanvasPanel`
- **One artifact at a time in canvas** - clicking different artifacts switches canvas content

**Artifact Display:**
- **SQL Query** → `ChatCodeBlock` with SQL syntax highlighting (language="sql")
- **Raw Data** → `DataTable` component (existing, with styling pass)

**Canvas Sizing:**
- Default: ~40% width panel on right
- Expandable: Full-width mode for large tables/long queries
- Toggle button to maximize/minimize canvas

**Rationale:** 
- Users need to see both the query and results together
- Makes it easy to copy SQL, inspect data, or share artifacts
- One artifact at a time keeps focus clear (click to switch)
- Expandable canvas accommodates wide data tables

---

## Files to Modify/Create

| Action | File | Changes |
|--------|------|---------|
| **Create** | `components/ui/domain-context-pill.tsx` | Header domain selector pill |
| **Create** | `components/navigation/SidebarConversationList.tsx` | Conversation list for sidebar |
| **Modify** | `components/navigation/SectionNavContent.tsx` | Add `bottomContent` prop or |
| **Create** | `components/navigation/BIAssistantSidebar.tsx` | Custom sidebar with conversations |
| **Modify** | `pages/data-analyst/DataAnalystPage.tsx` | State machine, DS chat components |
| **Modify** | `components/data-analyst/DataSourceSelector.tsx` | DS styling (keep cards) |
| **Remove** | `components/data-analyst/ConversationList.tsx` | Logic moves to sidebar |
| **Modify** | `components/data-analyst/ConversationView.tsx` | Use DS chat components |
| **Keep** | `components/data-analyst/DataTable.tsx` | Styling pass only |
| **Keep** | `components/data-analyst/ChartDisplay.tsx` | Styling pass only |

---

## Success Criteria

- [ ] Conversation history appears in sidebar submenu
- [ ] Chat uses `MessageBubble` for all messages
- [ ] Input uses `PromptBar` component
- [ ] Processing shows `ThinkingIndicator` shimmer
- [ ] Results can expand to `CanvasPanel`
- [ ] **Generated SQL automatically appears as canvas artifact**
- [ ] **Query data results automatically appear as canvas artifact**
- [ ] Domain selector uses DS Card/SectionHeader
- [ ] All colors use DS tokens
- [ ] Dark mode works correctly
- [ ] SSE streaming still works
- [ ] No visual regressions

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-01-12 | Initial plan created |
| 2026-01-12 | Updated to use existing DS chat.tsx and prompt-bar.tsx |
| 2026-01-12 | Added sidebar conversation list approach |
| 2026-01-12 | Extended `ThinkingIndicator` with execution steps (pending/active/completed/failed) |
| 2026-01-12 | Created `PromptBarWithDomain` for domain selection in prompt bar |
| 2026-01-12 | Updated ComponentShowcase with new examples |
| 2026-01-12 | **Revised domain selection**: Adopted "Zero State Hero" + "Header Context" pattern |
| 2026-01-12 | - Keep domain picker cards for new/empty chats (high discoverability) |
| 2026-01-12 | - Add `DomainContextPill` to header once chat active (always visible) |
| 2026-01-12 | - Prompt bar stays clean, focused on typing |
| 2026-01-13 | **Added auto-artifact requirement**: SQL + Data must appear in canvas automatically |
| 2026-01-13 | **Refined artifact UX**: One artifact at a time, SQL in CodeBlock, Data in DataTable |
| 2026-01-13 | - Canvas expandable for large tables, click artifact buttons to switch content |
| 2026-01-13 | **Created detailed phased implementation plan** with 7 phases and ~25 steps |
| 2026-01-13 | - Est. 14-20 hours total, with step-by-step code examples |
| 2026-01-13 | **IMPLEMENTATION START - Phases 1-4 Complete:** |
| 2026-01-13 | - Added `ChatProvider` wrapper to `DataAnalystPage.tsx` |
| 2026-01-13 | - Replaced `ConversationView` layout with DS chat components (`ChatContainer`, `ChatMessagesPane`, `ChatScrollArea`, `ChatInputArea`) |
| 2026-01-13 | - Replaced custom input form with DS `PromptBar` component |
| 2026-01-13 | - Added `CanvasPanel` for artifact display (SQL, Data) |
| 2026-01-13 | - Replaced user/assistant messages with DS `MessageBubble` + `MessageContent` |
| 2026-01-13 | - Replaced processing indicator with DS `ThinkingIndicator` (with execution steps) |
| 2026-01-13 | - Added `ArtifactButton` for SQL query (opens in canvas with `ChatCodeBlock`) |
| 2026-01-13 | - Added `ArtifactButton` for raw data (opens in canvas with `DataTable`) |
| 2026-01-13 | - Replaced inline alerts with DS `Alert` component |
| 2026-01-13 | - Updated legacy color classes to DS color system |
| 2026-01-13 | - Extracted `CompletedResults` component to resolve TypeScript inference issue |
| 2026-01-13 | **Phase 5 Complete - Sidebar Conversations:** |
| 2026-01-13 | - Created `BiConversationsContext` for shared state between page and sidebar |
| 2026-01-13 | - Created `SidebarConversationList` DS component for conversation history |
| 2026-01-13 | - Extended `SectionNavContent` to render conversations for BI Assistant section |
| 2026-01-13 | - Removed inline conversation list from page (now in sidebar) |
| 2026-01-13 | **Phase 6 Complete - Domain Selection:** |
| 2026-01-13 | - Created `DomainContextPill` DS component for domain switching |
| 2026-01-13 | - Created `ChatHeader` DS component for in-chat headers |
| 2026-01-13 | - Removed page title/breadcrumbs from Layout (max chat real estate) |
| 2026-01-13 | - Domain pill now lives inside `ChatHeader` within chat pane |
| 2026-01-13 | - Made domain pill header transparent with absolute positioning |
| 2026-01-13 | - Messages now scroll under the domain pill for max vertical space |
| 2026-01-13 | **Phase 7 Complete - Polish & Dark Mode:** |
| 2026-01-13 | - Fixed DataTable boolean formatting for dark mode |
| 2026-01-13 | - Verified CanvasPanel dark mode (intentionally dark theme) |
| 2026-01-13 | - All DS components use proper color tokens |
| 2026-01-13 | **🎉 MIGRATION COMPLETE** |
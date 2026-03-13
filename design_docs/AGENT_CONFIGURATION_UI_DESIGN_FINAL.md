# Agent Configuration UI Design - Clean List Pattern

## 🎯 Design Philosophy

Matching the **Business Intelligence page** with clean list UI:
- **No cards** - just clean list items with hover states
- **Section headers** for each flow (like BI question sections)
- **`.ui-list` + `.ui-item`** pattern from BI page
- **Subtle hover states** with background color
- **Active state** with brand color gradient background

---

## 📐 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 Agent Configuration                            [Test Agent]   │ ← Slim header (h-10)
├────────────┬────────────────────────────┬─────────────────────┤
│            │                            │                     │
│  Flows &   │  Agent Configuration       │  Test Results       │
│  Agents    │  Editor                    │  (Optional)         │
│            │                            │                     │
│┌──────────┐│┌──────────────────────────┐│┌───────────────────┐│
││DATA      │││ Agent: Data Retrieval    │││ Test Input:       ││
││ANALYSIS  │││                          │││ "Who are our..."  ││
││FLOW      │││ ━━ Prompts ━━━━━━━━━━━━━ │││                   ││
││          │││ Role: [............]     │││ Output:           ││
││ Data     │││ Goal: [............]     │││ "Found 5..."      ││
││ Retrieval││ ← Selected                │││                   ││
││ Agent    │││ ━━ Model Config ━━━━━━━━ │││ Performance:      ││
││          │││ Provider: [OpenAI  ▼]    │││ 2.3s, 450 tok     ││
││ BI       │││ Model: [gpt-4      ▼]    │││                   ││
││ Analyst  │││                          │││                   ││
││ Agent    │││ ━━ Tools ━━━━━━━━━━━━━━  │││                   ││
││          │││ [✓] HR Database Tool     │││                   ││
││┌─────────┐│││ [✓] Document Search     │││                   ││
│││TASK     │││                          │││                   ││
│││ENRICH.  │││ ━━ Documents ━━━━━━━━━━━ │││                   ││
│││FLOW     │││ [Add Document     ▼]     │││                   ││
││          │││ 📄 Policies.pdf  [x]     │││                   ││
││ Task     │││                          │││                   ││
││ Analysis │││                          │││                   ││
││ Agent    │││        Scroll            │││      Scroll       ││
││          │││          ↕               │││        ↕          ││
││ Enrich.  │││                          │││                   ││
││ Agent    │││                          │││                   ││
││          │││                          │││                   ││
││  Scroll  │││                          │││                   ││
││    ↕     │││                          │││                   ││
│└──────────┘│└──────────────────────────┘│└───────────────────┘│
└────────────┴────────────────────────────┴─────────────────────┘
```

---

## 🎨 Left Pane: Clean List with Section Headers

```tsx
// pages/admin/AgentConfigurationPage.tsx

<div className="h-full flex flex-col overflow-hidden bg-surface-2">
  {/* Pane Header (fixed) */}
  <div className="px-3 bg-surface-2 h-9 flex items-center gap-2 border-b border-border flex-shrink-0">
    <h2 className="text-xs font-semibold text-muted-2 uppercase tracking-wide">
      Flows & Agents
    </h2>
    <span className="ml-auto text-xs text-muted">
      {totalAgents} agents
    </span>
  </div>

  {/* Scrollable List */}
  <div className="flex-1 min-h-0 overflow-y-scroll overscroll-contain ui-list scroll-slim ios-momentum">
    <div className="always-scrollable">
      {flows.map(flow => (
        <React.Fragment key={flow.flow_identifier}>
          {/* Section Header for Flow */}
          <div className="px-3 py-2 bg-surface-2 border-b border-border sticky top-0 z-10">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-muted-2 uppercase tracking-wide">
                {flow.name}
              </h3>
              <span className="text-xs text-muted">
                {flow.agents.length} agents
              </span>
            </div>
          </div>

          {/* Agent List Items (no borders!) */}
          {flow.agents.map(agent => (
            <button
              key={agent.id}
              onClick={() => onSelectAgent(agent)}
              className={`ui-item pl-5 pr-4 text-left ${
                selectedAgentId === agent.id ? 'ui-item-active' : ''
              }`}
            >
              <div className="flex items-center gap-3 min-w-0 relative w-full">
                {/* Status Icon */}
                <div className="flex-shrink-0">
                  {agent.is_enabled ? (
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-gray-400" />
                  )}
                </div>

                {/* Agent Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-3">
                    {/* Agent Name */}
                    <span className="ui-item-title truncate">
                      {agent.name}
                    </span>

                    {/* Config Status */}
                    {agent.is_configured && (
                      <CheckIcon className="w-3 h-3 text-green-500 flex-shrink-0" />
                    )}
                  </div>

                  {/* Agent Metadata */}
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="ui-item-meta truncate">
                      {agent.model_name || 'Default Model'}
                    </span>
                    {agent.provider_name && (
                      <>
                        <span className="ui-item-meta">•</span>
                        <span className="ui-item-meta capitalize">
                          {agent.provider_name}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </React.Fragment>
      ))}
    </div>
  </div>
</div>
```

---

## 📋 Visual Structure

### **Section Headers** (Sticky)
```
┌────────────────────────────────┐
│ DATA ANALYSIS FLOW      2 agents│ ← Sticky header
├────────────────────────────────┤
```

**Styling:**
```css
/* Section header - sticky */
.px-3 .py-2 .bg-surface-2 .border-b .border-border .sticky .top-0 .z-10

/* Text */
.text-xs .font-semibold .text-muted-2 .uppercase .tracking-wide
```

### **List Items** (Clean, no borders)
```
  ● Data Retrieval Agent             ✓
    GPT-4 • OpenAI
    
  ● BI Analyst Agent
    Claude 3 • Anthropic
```

**Styling:**
```tsx
className="ui-item pl-5 pr-4 text-left"
// On hover: subtle background
// On active: brand gradient background
```

---

## 🎨 CSS Classes Used (From BI Page)

```css
/* Container */
.ui-list {
  /* Already defined in index.css */
}

/* List Item */
.ui-item {
  display: flex;
  align-items: center;
  padding: var(--ui-item-py) var(--ui-item-px);
  border-radius: var(--ui-item-radius);
  border: 1px solid transparent;
  transition: background var(--transition-fast);
}

.ui-item:hover {
  background: var(--surface-2);
  border-color: var(--border);
}

/* Active State */
.ui-item-active {
  background: transparent;
  color: var(--brand);
  border-color: transparent;
  box-shadow: none;
  border-radius: 0;
}

.ui-item-active::before {
  /* Brand gradient background */
  content: "";
  position: absolute;
  top: 0; bottom: 0;
  left: -9999px; right: -9999px;
  background: linear-gradient(180deg, color-mix(in oklab, var(--brand) 14%, transparent), transparent);
  z-index: -1;
}

/* Typography */
.ui-item-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
}

.ui-item-meta {
  font-size: 0.75rem;
  color: var(--muted);
}
```

---

## 📦 Complete Component Structure

```tsx
// pages/admin/AgentConfigurationPage.tsx

export default function AgentConfigurationPage() {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showTestPane, setShowTestPane] = useState(false);
  const [listWidth, setListWidth] = useState(320);
  const [testPaneWidth, setTestPaneWidth] = useState(400);
  
  return (
    <Layout edgeToEdge>
      <div className="h-full flex flex-col overflow-hidden">
        {/* Slim Header */}
        <AgentConfigHeader
          selectedAgent={selectedAgent}
          onTest={() => setShowTestPane(true)}
          onSave={handleSave}
        />

        {/* Three-Pane Layout */}
        <div className="flex-1 min-h-0 flex">
          {/* Left Pane: Flows & Agents List */}
          <div style={{ width: listWidth }} className="flex flex-col">
            <FlowsAgentsList
              flows={flows}
              selectedAgentId={selectedAgent?.id}
              onSelectAgent={setSelectedAgent}
              totalAgents={totalAgents}
            />
          </div>

          {/* Center Divider */}
          <ResizableDivider
            onResize={(delta) => setListWidth(listWidth + delta)}
          />

          {/* Center Pane: Agent Editor */}
          <div className="flex-1 min-w-[400px]">
            {selectedAgent ? (
              <AgentConfigurationEditor
                agent={selectedAgent}
                onUpdate={handleUpdate}
              />
            ) : (
              <EmptyState
                icon={<CpuChipIcon className="w-12 h-12" />}
                title="No agent selected"
                description="Select an agent from the list to configure"
              />
            )}
          </div>

          {/* Right Pane: Test Results (Optional) */}
          {showTestPane && (
            <>
              <ResizableDivider
                onResize={(delta) => setTestPaneWidth(testPaneWidth + delta)}
              />
              <div style={{ width: testPaneWidth }} className="flex flex-col">
                <TestResultsPane
                  agent={selectedAgent}
                  onClose={() => setShowTestPane(false)}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
```

---

## 🎯 Key Differences from Card Design

### **❌ NO Cards:**
```tsx
// DON'T DO THIS:
<div className="bg-white rounded-lg border shadow p-4">
  <h3>Flow Name</h3>
  {/* agents */}
</div>
```

### **✅ YES Clean List:**
```tsx
// DO THIS:
<>
  {/* Section Header */}
  <div className="px-3 py-2 bg-surface-2 border-b">
    <h3>FLOW NAME</h3>
  </div>
  
  {/* Clean list items - no card boundaries */}
  {agents.map(agent => (
    <button className="ui-item">
      {agent.name}
    </button>
  ))}
</>
```

---

## 📱 States & Interactions

### **Default State:**
```
┌────────────────────┐
│ DATA ANALYSIS FLOW │ ← Section header
├────────────────────┤
│ ● Data Retrieval   │ ← List item (default)
│   GPT-4 • OpenAI   │
```

### **Hover State:**
```
┌────────────────────┐
│ DATA ANALYSIS FLOW │
├────────────────────┤
│ ● Data Retrieval   │ ← Subtle bg-surface-2
│   GPT-4 • OpenAI   │
```

### **Active State:**
```
┌────────────────────┐
│ DATA ANALYSIS FLOW │
├────────────────────┤
│ ● Data Retrieval   │ ← Brand gradient background
│   GPT-4 • OpenAI   │    Brand text color
```

---

## 🎨 Visual Hierarchy

```
SECTION HEADER (uppercase, small, muted)
  ● Agent Name (14px, semibold, text color)    ✓
    Model • Provider (12px, muted)
    
  ● Agent Name
    Model • Provider
```

**Spacing:**
- Section header: `py-2 px-3`
- List items: `py-[var(--ui-item-py)] px-[var(--ui-item-px)]`
- Gap between icon and text: `gap-3`
- Gap between metadata items: `gap-2`

---

## ✅ Matches BI Page Pattern

| Element | BI Page | Agent Config |
|---------|---------|--------------|
| **Container** | `.ui-list` | `.ui-list` |
| **Items** | `.ui-item` (buttons) | `.ui-item` (buttons) |
| **Active** | `.ui-item-active` | `.ui-item-active` |
| **Text** | `.ui-item-title` | `.ui-item-title` |
| **Meta** | `.ui-item-meta` | `.ui-item-meta` |
| **Headers** | `QuestionListHeader` | Section headers |
| **Borders** | None (just hover) | None (just hover) |
| **Cards** | ❌ None | ❌ None |

---

## 🚀 Implementation Order

1. **Page Structure** - Three-pane layout with dividers
2. **Left Pane** - Clean list with section headers
3. **Center Pane** - Configuration editor
4. **Right Pane** - Test results (optional)
5. **Interactions** - Selection, hover, active states
6. **Polish** - Transitions, keyboard nav

---

This design is **clean, elegant, and matches your BI page exactly** - no ugly card boundaries! 🎨✨


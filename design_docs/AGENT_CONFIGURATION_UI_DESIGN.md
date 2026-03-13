# Agent Configuration UI Design - Multi-Pane Layout

## 🎯 Design Philosophy

Following the **Business Intelligence page pattern** with a single-page, multi-pane layout:
- **Left Pane**: Flows & Agents list (like question list)
- **Center Pane**: Agent configuration editor (like question detail)
- **Right Pane**: Test results / execution history (like timeline)
- **Resizable dividers** between panes
- **Slim header bar** at top

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
│ ┌────────┐ │ ┌────────────────────────┐ │ ┌─────────────────┐│
│ │ Data   │ │ │ Agent: Data Retrieval  │ │ │ Test Input:     ││
│ │Analysis│◀│ │                        │ │ │ "Who are our..."││
│ │ Flow   │ │ │ Prompts                │ │ │                 ││
│ │ • Data │ │ │ ├─ Role: [...]         │ │ │ Output:         ││
│ │   Retr.│ │ │ ├─ Goal: [...]         │ │ │ "Found 5..."    ││
│ │ • BI   │ │ │ └─ Backstory: [...]    │ │ │                 ││
│ │   Anal.│ │ │                        │ │ │ Performance:    ││
│ │        │ │ │ Model Configuration    │ │ │ 2.3s, 450 tok   ││
│ ├────────┤ │ │ ├─ Provider: [▼]       │ │ │                 ││
│ │ Task   │ │ │ ├─ Model: [▼]          │ │ └─────────────────┘│
│ │Enrich. │ │ │ ├─ Temp: [0.7]         │ │                     │
│ │ Flow   │ │ │ └─ Max: [2000]         │ │                     │
│ │ • Task │ │ │                        │ │                     │
│ │   Anal.│ │ │ Tools                  │ │                     │
│ │ • Enri.│ │ │ [✓] HR Database        │ │                     │
│ │        │ │ │ [✓] Document Search    │ │                     │
│ └────────┘ │ │                        │ │                     │
│            │ │ Mandatory Documents    │ │                     │
│            │ │ [Add Document ▼]       │ │                     │
│            │ │ 📄 Policies.pdf [x]    │ │                     │
│            │ │                        │ │                     │
│  Scroll    │ │ [Save Changes]         │ │                     │
│    ↕       │ │                        │ │      Scroll         │
│            │ │      Scroll            │ │        ↕            │
│            │ │        ↕               │ │                     │
└────────────┴────────────────────────────┴─────────────────────┘
   240-400px        flex-1 (min 400px)        300-600px
  resizable         (center pane)             resizable
```

---

## 🎨 Component Structure

```tsx
<Layout edgeToEdge>
  <div className="h-full flex flex-col overflow-hidden">
    {/* Slim Header Bar */}
    <div className="h-10 px-3 bg-surface-2 border-b border-border flex-shrink-0">
      <AgentConfigHeader />
    </div>

    {/* Three-Pane Layout */}
    <div className="flex-1 min-h-0 flex">
      {/* Left Pane: Flows & Agents List */}
      <div className="w-[320px] min-w-[240px] max-w-[400px] flex flex-col">
        <FlowsAgentsList 
          onSelectAgent={handleAgentSelect}
          selectedAgent={selectedAgent}
        />
      </div>

      {/* Center Divider (resizable) */}
      <ResizableDivider onResize={handleLeftResize} />

      {/* Center Pane: Agent Configuration Editor */}
      <div className="flex-1 min-w-[400px] flex flex-col overflow-hidden">
        {selectedAgent ? (
          <AgentConfigurationEditor 
            agent={selectedAgent}
            onSave={handleSave}
            onTest={handleTest}
          />
        ) : (
          <EmptyState message="Select an agent to configure" />
        )}
      </div>

      {/* Right Divider + Test Results Pane (conditional) */}
      {showTestResults && (
        <>
          <ResizableDivider onResize={handleRightResize} />
          <div className="w-[400px] min-w-[300px] max-w-[600px] flex flex-col">
            <TestResultsPane 
              results={testResults}
              onClose={() => setShowTestResults(false)}
            />
          </div>
        </>
      )}
    </div>
  </div>
</Layout>
```

---

## 📦 Detailed Components

### 1. **Header Bar** (Slim, Fixed)

```tsx
// components/agent-configuration/AgentConfigHeader.tsx

<div className="flex items-center justify-between h-full">
  <div className="flex items-center gap-2">
    <CpuChipIcon className="w-5 h-5 text-brand" />
    <h1 className="text-sm font-semibold text-text">Agent Configuration</h1>
    <Tooltip content="Configure your CrewAI agents and flows">
      <span className="text-muted cursor-help text-xs">ⓘ</span>
    </Tooltip>
  </div>
  
  <div className="flex items-center gap-2">
    {selectedAgent && (
      <>
        <button 
          onClick={handleTest}
          className="px-3 py-1 text-sm rounded-md bg-surface-2 hover:bg-surface border border-border"
        >
          <BoltIcon className="w-4 h-4 inline mr-1" />
          Test Agent
        </button>
        <button
          onClick={handleSave}
          disabled={!hasChanges}
          className="px-3 py-1 text-sm rounded-md bg-brand text-on-brand hover:opacity-90"
        >
          Save Changes
        </button>
      </>
    )}
  </div>
</div>
```

---

### 2. **Left Pane: Flows & Agents List**

```tsx
// components/agent-configuration/FlowsAgentsList.tsx

<div className="h-full flex flex-col overflow-hidden">
  {/* Pane Header */}
  <div className="px-3 py-2 border-b border-border bg-surface-2 flex-shrink-0">
    <h2 className="text-sm font-semibold text-text">Flows & Agents</h2>
    <p className="text-xs text-muted">Click an agent to configure</p>
  </div>

  {/* Scrollable List */}
  <div className="flex-1 overflow-y-auto scroll-slim ios-momentum">
    <div className="p-2 space-y-2">
      {flows.map(flow => (
        <FlowCard 
          key={flow.flow_identifier}
          flow={flow}
          selectedAgentId={selectedAgent?.id}
          onSelectAgent={onSelectAgent}
        />
      ))}
    </div>
  </div>
</div>
```

**FlowCard Component:**

```tsx
<div className="bg-surface rounded-lg border border-border overflow-hidden">
  {/* Flow Header */}
  <div 
    className="px-3 py-2 bg-surface-2 cursor-pointer flex items-center justify-between"
    onClick={() => setExpanded(!expanded)}
  >
    <div className="flex items-center gap-2">
      <ChevronRightIcon className={`w-4 h-4 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      <span className="text-sm font-medium text-text">{flow.name}</span>
    </div>
    <span className="text-xs text-muted">{flow.agents.length} agents</span>
  </div>

  {/* Agent List (collapsible) */}
  {expanded && (
    <div className="divide-y divide-border">
      {flow.agents.map(agent => (
        <button
          key={agent.id}
          onClick={() => onSelectAgent(agent)}
          className={`
            w-full px-4 py-2 text-left hover:bg-surface-2 transition-colors
            ${selectedAgentId === agent.id ? 'bg-brand/10 border-l-2 border-brand' : ''}
          `}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm text-text">{agent.name}</span>
            {agent.is_configured && (
              <CheckIcon className="w-4 h-4 text-green-500" />
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-muted">
              {agent.model_name || 'Default Model'}
            </span>
            {agent.is_enabled ? (
              <span className="text-xs text-green-600">● Active</span>
            ) : (
              <span className="text-xs text-gray-400">○ Inactive</span>
            )}
          </div>
        </button>
      ))}
    </div>
  )}
</div>
```

---

### 3. **Center Pane: Agent Configuration Editor**

```tsx
// components/agent-configuration/AgentConfigurationEditor.tsx

<div className="h-full flex flex-col overflow-hidden">
  {/* Pane Header */}
  <div className="px-4 py-3 border-b border-border bg-surface-2 flex-shrink-0">
    <div className="flex items-center gap-2">
      <div className={`p-1.5 rounded ${getAgentColor(agent.type)}`}>
        <CpuChipIcon className="w-4 h-4" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-text">{agent.name}</h2>
        <p className="text-xs text-muted">{agent.flow_name}</p>
      </div>
    </div>
    
    <div className="mt-2 flex items-center gap-2">
      <label className="flex items-center gap-1 text-xs">
        <input 
          type="checkbox"
          checked={agent.is_enabled}
          onChange={handleToggleEnabled}
          className="rounded"
        />
        <span className="text-muted">Enabled</span>
      </label>
    </div>
  </div>

  {/* Scrollable Configuration Form */}
  <div className="flex-1 overflow-y-auto scroll-slim ios-momentum">
    <div className="p-4 space-y-6">
      {/* Prompts Section */}
      <ConfigSection title="Agent Prompts" icon={<ChatBubbleIcon />}>
        <div className="space-y-3">
          <FormField label="Role" required>
            <textarea
              value={config.role}
              onChange={(e) => updateConfig('role', e.target.value)}
              className="w-full px-3 py-2 rounded-md border-border bg-surface"
              rows={2}
              placeholder="e.g., Data Retrieval Specialist"
            />
          </FormField>

          <FormField label="Goal" required>
            <textarea
              value={config.goal}
              onChange={(e) => updateConfig('goal', e.target.value)}
              className="w-full px-3 py-2 rounded-md border-border bg-surface"
              rows={3}
              placeholder="e.g., Retrieve relevant HR and document data..."
            />
          </FormField>

          <FormField label="Backstory">
            <textarea
              value={config.backstory}
              onChange={(e) => updateConfig('backstory', e.target.value)}
              className="w-full px-3 py-2 rounded-md border-border bg-surface"
              rows={4}
              placeholder="e.g., You are an expert at..."
            />
          </FormField>
        </div>
      </ConfigSection>

      {/* Model Configuration Section */}
      <ConfigSection title="Model Configuration" icon={<CpuChipIcon />}>
        <div className="space-y-3">
          <FormField label="Provider" required>
            <select
              value={config.provider_config_id}
              onChange={(e) => updateConfig('provider_config_id', e.target.value)}
              className="w-full px-3 py-2 rounded-md border-border bg-surface"
            >
              <option value="">Select provider...</option>
              {providers.map(p => (
                <option key={p.id} value={p.id}>
                  {p.provider_type.toUpperCase()} - {p.name}
                </option>
              ))}
            </select>
          </FormField>

          <FormField label="Model">
            <select
              value={config.model_override}
              onChange={(e) => updateConfig('model_override', e.target.value)}
              className="w-full px-3 py-2 rounded-md border-border bg-surface"
              disabled={!config.provider_config_id}
            >
              <option value="">Use provider default</option>
              {availableModels.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </FormField>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Temperature">
              <input
                type="number"
                min="0"
                max="2"
                step="0.1"
                value={config.temperature}
                onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
                className="w-full px-3 py-2 rounded-md border-border bg-surface"
              />
            </FormField>

            <FormField label="Max Tokens">
              <input
                type="number"
                min="1"
                max="8000"
                step="100"
                value={config.max_tokens}
                onChange={(e) => updateConfig('max_tokens', parseInt(e.target.value))}
                className="w-full px-3 py-2 rounded-md border-border bg-surface"
              />
            </FormField>
          </div>
        </div>
      </ConfigSection>

      {/* Tools Section */}
      <ConfigSection title="Tools" icon={<WrenchIcon />}>
        <div className="space-y-2">
          {availableTools.map(tool => (
            <label
              key={tool.id}
              className="flex items-start gap-3 p-3 rounded-md border border-border hover:bg-surface-2 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={config.enabled_tools.includes(tool.id)}
                onChange={(e) => handleToggleTool(tool.id, e.target.checked)}
                className="mt-0.5"
              />
              <div className="flex-1">
                <div className="text-sm font-medium text-text">{tool.name}</div>
                <div className="text-xs text-muted">{tool.description}</div>
              </div>
            </label>
          ))}
        </div>
      </ConfigSection>

      {/* Mandatory Documents Section */}
      <ConfigSection title="Mandatory Documents" icon={<DocumentIcon />}>
        <div className="space-y-2">
          <select
            onChange={(e) => handleAttachDocument(e.target.value)}
            className="w-full px-3 py-2 rounded-md border-border bg-surface text-sm"
          >
            <option value="">Add document...</option>
            {documents.map(doc => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>

          {config.attached_documents.length > 0 && (
            <div className="space-y-2 mt-3">
              {config.attached_documents.map(doc => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-2 rounded-md bg-surface-2"
                >
                  <div className="flex items-center gap-2">
                    <DocumentTextIcon className="w-4 h-4 text-muted" />
                    <span className="text-sm text-text">{doc.filename}</span>
                  </div>
                  <button
                    onClick={() => handleRemoveDocument(doc.id)}
                    className="text-xs text-red-600 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </ConfigSection>
    </div>
  </div>
</div>
```

---

### 4. **Right Pane: Test Results** (Optional/Toggleable)

```tsx
// components/agent-configuration/TestResultsPane.tsx

<div className="h-full flex flex-col overflow-hidden bg-surface">
  {/* Pane Header */}
  <div className="px-4 py-3 border-b border-border bg-surface-2 flex-shrink-0">
    <div className="flex items-center justify-between">
      <h2 className="text-sm font-semibold text-text">Test Results</h2>
      <button
        onClick={onClose}
        className="text-xs text-muted hover:text-text"
      >
        Close
      </button>
    </div>
  </div>

  {/* Scrollable Content */}
  <div className="flex-1 overflow-y-auto scroll-slim ios-momentum p-4">
    {loading ? (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand" />
        <span className="ml-3 text-sm text-muted">Testing agent...</span>
      </div>
    ) : results ? (
      <div className="space-y-4">
        {/* Test Input */}
        <div>
          <h3 className="text-xs font-medium text-muted mb-2">Test Input</h3>
          <div className="p-3 rounded-md bg-surface-2 text-sm text-text">
            {results.input}
          </div>
        </div>

        {/* Agent Output */}
        <div>
          <h3 className="text-xs font-medium text-muted mb-2">Agent Output</h3>
          <div className="p-3 rounded-md bg-surface-2 text-sm text-text whitespace-pre-wrap">
            {results.output}
          </div>
        </div>

        {/* Performance Metrics */}
        <div>
          <h3 className="text-xs font-medium text-muted mb-2">Performance</h3>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 rounded-md bg-surface-2">
              <div className="text-xs text-muted">Duration</div>
              <div className="text-sm font-medium text-text">
                {results.duration_ms}ms
              </div>
            </div>
            <div className="p-2 rounded-md bg-surface-2">
              <div className="text-xs text-muted">Tokens</div>
              <div className="text-sm font-medium text-text">
                {results.tokens_used}
              </div>
            </div>
          </div>
        </div>

        {/* Tools Used */}
        {results.tools_used.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-muted mb-2">Tools Used</h3>
            <div className="space-y-1">
              {results.tools_used.map((tool, idx) => (
                <div key={idx} className="text-xs text-text flex items-center gap-2">
                  <CheckIcon className="w-3 h-3 text-green-500" />
                  {tool}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    ) : (
      <div className="text-center py-8 text-sm text-muted">
        Click "Test Agent" to run a test execution
      </div>
    )}
  </div>
</div>
```

---

## 🎯 Interaction Patterns

### **Flow Selection:**
1. User clicks on a flow in left pane → Flow expands to show agents
2. User clicks on an agent → Center pane loads agent configuration
3. Selected agent highlights with brand color left border

### **Configuration Editing:**
1. User edits prompts/settings in center pane
2. "Save Changes" button in header becomes enabled
3. User can test configuration before saving

### **Testing:**
1. User clicks "Test Agent" in header
2. Right pane opens with test interface
3. User enters test input
4. Results stream into right pane
5. User can close right pane to get more editing space

### **Resizing:**
1. Drag dividers to resize panes
2. Min/max widths enforced
3. Pane widths persist in localStorage

---

## 📱 Responsive Behavior

### **Desktop (1920px+):**
- Left: 320px
- Center: flex-1 (800px+)
- Right: 400px (when open)

### **Laptop (1440px):**
- Left: 280px
- Center: flex-1 (600px+)
- Right: 360px (when open)

### **Small Screen (< 1200px):**
- Right pane becomes full-screen overlay
- Left pane collapsible
- Focus on center pane

---

## 🎨 Visual Design Tokens

```tsx
// Consistent with BI page
const colors = {
  surface: 'bg-surface',
  surface2: 'bg-surface-2',
  text: 'text-text',
  muted: 'text-muted',
  border: 'border-border',
  brand: 'bg-brand',
  onBrand: 'text-on-brand',
};

const layout = {
  header: 'h-10',
  divider: 'w-px cursor-col-resize',
  scrollable: 'overflow-y-auto scroll-slim ios-momentum',
  flexContainer: 'h-full flex flex-col overflow-hidden',
};
```

---

## 🚀 Implementation Priority

### Phase 1: Basic Layout
- [ ] Create page with 3-pane structure
- [ ] Add resizable dividers
- [ ] Implement flows/agents list (left pane)
- [ ] Empty state for center pane

### Phase 2: Configuration Editor
- [ ] Agent configuration form (center pane)
- [ ] Prompts section
- [ ] Model selector
- [ ] Tools checklist

### Phase 3: Testing
- [ ] Test results pane (right)
- [ ] Test execution
- [ ] Results display

### Phase 4: Polish
- [ ] Animations/transitions
- [ ] Keyboard shortcuts
- [ ] Accessibility
- [ ] Mobile responsiveness

---

## 📐 Key Measurements

```
┌─────────────────────────────────────────────┐
│ Header: h-10 (40px) - Fixed                 │
├───────────┬─────────────────┬───────────────┤
│           │                 │               │
│ Left Pane │  Center Pane    │  Right Pane   │
│ 240-400px │  flex-1         │  300-600px    │
│ (default: │  (min: 400px)   │  (default:    │
│  320px)   │                 │   400px)      │
│           │                 │  [Optional]   │
│           │                 │               │
│ Scroll ↕  │  Scroll ↕       │  Scroll ↕     │
│           │                 │               │
└───────────┴─────────────────┴───────────────┘
```

---

## ✅ Advantages of This Design

1. **Familiar Pattern**: Matches BI page, users already know how to use it
2. **Efficient**: See flows, edit config, test results - all on one screen
3. **Flexible**: Resize panes to focus on what you need
4. **Fast**: No page loads, instant switching between agents
5. **Clean**: No navigation mess, everything visible at once
6. **Scalable**: Add more agents/flows without cluttering UI

---

This design provides a clean, efficient interface that matches your existing BI page pattern! 🎉


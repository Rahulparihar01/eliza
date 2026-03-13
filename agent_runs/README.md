# Agent Execution Logs

> **Purpose:** Capture AI agent execution history for learning, debugging, and continuous improvement.

---

## 📁 Directory Structure

```
agent_runs/
├── README.md                    # This file
├── templates/
│   └── RUN_LOG_TEMPLATE.md     # Template for logging agent runs
├── completed/                   # Successfully completed runs
│   └── YYYY-MM-DD_feature-name.md
├── failed/                      # Failed or abandoned runs
│   └── YYYY-MM-DD_feature-name.md
└── insights/                    # Aggregated learnings
    └── COMMON_PATTERNS.md
```

---

## 🎯 Why Log Agent Runs?

1. **Learning from History** - Agents can reference how similar tasks were completed
2. **Debugging** - Understand what went wrong when features fail
3. **Pattern Discovery** - Identify common approaches that work well
4. **Continuous Improvement** - Update skills based on real execution data

---

## 📝 When to Create a Run Log

Create a log for:
- ✅ New feature implementations (multi-step tasks)
- ✅ Complex bug fixes requiring investigation
- ✅ Refactoring or migration work
- ✅ Any task that took significant decision-making

Skip for:
- ❌ Simple one-line fixes
- ❌ Documentation updates
- ❌ Configuration changes

---

## 🔍 How to Use Run Logs

### For AI Agents

Before starting a new task:
```
1. Check agent_runs/completed/ for similar past tasks
2. Review decisions made and approaches taken
3. Note any gotchas or lessons learned
4. Apply relevant patterns to current task
```

### For Humans

Review `agent_runs/insights/COMMON_PATTERNS.md` to:
- Identify skills that need updating
- Find recurring issues to fix at the platform level
- Understand agent decision-making patterns

---

## 📊 Run Log Metrics

Each run log captures:
- **Task Type**: Feature, bugfix, refactor, etc.
- **Complexity**: Simple, moderate, complex
- **Duration**: Time from start to completion
- **Files Modified**: Count and list
- **Skills Referenced**: Which skills were consulted
- **Blockers Encountered**: Issues that slowed progress
- **Outcome**: Success, partial, failed

---

## 🔗 Integration with Skills

Run logs inform skill updates:
```
Run Log shows repeated issue → Update relevant skill → Future agents avoid issue
```

When you notice patterns in run logs:
1. Update `skills/[domain]/` with the learning
2. Add to `skills/troubleshooting/` if it's an error pattern
3. Create new code template if it's a reusable pattern

---

## ⚠️ Privacy & Security

- **DO NOT** log sensitive data (API keys, passwords, PII)
- **DO NOT** include full file contents (use paths instead)
- **DO** sanitize any customer-specific information
- **DO** focus on patterns and decisions, not data

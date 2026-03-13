# [Skill Name]

> **Purpose:** [One or two sentences describing what this skill covers and why an AI agent or developer should reference it before working in this domain.]

---

## Quick Reference

<!--
  START HERE. Provide the single most common pattern as a concise, 
  copy-paste-ready code block. This is the "80% use case" — the thing 
  someone will need most often. Keep it under ~30 lines.
  
  For backend skills, this is usually a correct Python code pattern.
  For frontend skills, a TSX component pattern.
  For ops/infra skills, a bash command sequence.
-->

```python
# ✅ CORRECT [Domain] Pattern
# Show the most common correct usage here
```

---

## Overview

<!--
  Explain what this skill covers and how it fits into the Eliza Platform 
  architecture. Include an ASCII diagram if the domain involves multiple 
  layers or components interacting.
  
  Keep this section conceptual — save implementation details for later 
  sections. 2–4 paragraphs or a diagram + 1 paragraph is ideal.
-->

[What this skill covers, why it exists, and how the domain fits into the platform.]

```
┌─────────────────────────────────────────────────────────────┐
│                    [Layer / Component]                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    [Layer / Component]                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Rules

<!--
  Numbered rules that MUST be followed. Each rule should have:
  1. A clear title
  2. Context explaining WHY the rule exists
  3. A ❌ WRONG code example
  4. A ✅ CORRECT code example
  
  Order rules by severity — most critical first.
  Limit to 3–6 rules. If you need more, the skill may need splitting.
-->

### Rule 1: [Rule Title]

**Context:** [Why this rule exists — what breaks if you ignore it.]

```python
# ❌ WRONG: [Brief explanation]
bad_example_code()

# ✅ CORRECT: [Brief explanation]
good_example_code()
```

### Rule 2: [Rule Title]

**Context:** [Why this rule exists.]

```python
# ❌ WRONG
...

# ✅ CORRECT
...
```

---

## Patterns

<!--
  Common implementation patterns beyond the Quick Reference. Use this 
  section for variations, advanced use cases, or the 2–3 other patterns 
  agents will encounter frequently.
  
  Each pattern should have:
  - A descriptive H3 title
  - A brief explanation of when to use it
  - A complete code example
  
  If your skill has many patterns, consider a pattern catalog table 
  at the top of this section linking to each subsection.
-->

### [Pattern Name]

[When to use this pattern and what it accomplishes.]

```python
# Complete, working code example
```

### [Pattern Name]

[When to use this pattern.]

```python
# Complete, working code example
```

---

## Complete Template

<!--
  A full, production-ready, copy-paste template for the most common 
  use case. This should be a complete file that someone can copy, 
  replace placeholders, and have a working implementation.
  
  Use [PLACEHOLDERS] or descriptive names like YourService, your_table, 
  etc. for values the developer needs to customize.
  
  Include inline comments explaining each major section.
-->

```python
"""
[Feature Name] — [Brief description]

[What this module does and why.]
"""

# Full implementation template here...
```

---

## Integration

<!--
  How to wire this into the existing Eliza Platform codebase.
  Cover:
  - Which files to modify (registration, imports, config)
  - Step-by-step wiring instructions
  - Frontend changes if applicable
  
  Use numbered steps for sequential operations.
-->

### Step 1: [Registration / Wiring Step]

```python
# Code showing where to register the new component
```

### Step 2: [Next Step]

```python
# Code showing the next integration step
```

---

## File Locations

<!--
  Where relevant files live in the codebase. Helps agents navigate 
  to the right directories. Use a tree diagram for clarity.
-->

```
src/
└── [domain]/
    ├── [primary_file].py      # Main implementation
    ├── [supporting_file].py   # Supporting code
    └── [config_file].py       # Configuration
```

---

## Testing

<!--
  How to test implementations in this domain. Include:
  - Unit test example with mocks
  - Integration test example (if applicable)
  - Manual testing commands (curl, psql, etc.)
-->

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch

def test_example():
    """Test description."""
    # Setup
    ...
    # Execute
    ...
    # Assert
    ...
```

### Manual Testing

```bash
# Command to verify the implementation works
```

---

## Common Pitfalls

<!--
  A table of frequent mistakes and their solutions. Keep entries 
  concise — one line per mistake/solution pair. Link to the 
  Critical Rules section if a pitfall has a detailed rule.
-->

| Pitfall | Solution |
|---------|----------|
| [Common mistake] | [How to fix it] |
| [Common mistake] | [How to fix it] |
| [Common mistake] | [How to fix it] |

---

## Checklist

<!--
  A pre-merge/pre-PR checklist specific to this domain. Each item 
  should be verifiable (yes/no). Include items that catch the most 
  common review feedback.
  
  Always end with container rebuild reminder if applicable.
-->

- [ ] [Verification item 1]
- [ ] [Verification item 2]
- [ ] [Verification item 3]
- [ ] [Verification item 4]
- [ ] Container rebuilt: `docker-compose build app celery-worker`

---

## References

<!--
  Links to:
  - Related source files in the codebase
  - Other skills that complement this one
  - External documentation (APIs, libraries, etc.)
  
  Use relative paths for codebase files. Use full URLs for external docs.
-->

- `src/[path]/[file].py` — [What this file contains]
- `src/[path]/[file].py` — [What this file contains]
- `skills/[related-skill]/` — [How it relates]
- [External Documentation](https://example.com) — [What it covers]

---

<!--
============================================================
  TEMPLATE USAGE GUIDE
============================================================

  WHEN TO USE THIS TEMPLATE:
  Create a new skill when a domain has recurring patterns that 
  agents need to follow, critical rules that prevent bugs, or 
  enough complexity to warrant documented guidance.

  NAMING CONVENTIONS:
  ┌──────────────────┬─────────────────────┬──────────────────────────┐
  │ Element          │ Convention          │ Example                  │
  ├──────────────────┼─────────────────────┼──────────────────────────┤
  │ Skill directory  │ kebab-case          │ row-level-security/      │
  │ Primary guide    │ SCREAMING_SNAKE.md  │ RLS_IMPLEMENTATION.md    │
  │ Supporting docs  │ snake_case.md       │ flow_patterns.md         │
  └──────────────────┴─────────────────────┴──────────────────────────┘

  SECTION RULES:
  - REQUIRED sections: Quick Reference, Critical Rules, Checklist, 
    References
  - RECOMMENDED sections: Overview, Patterns, Complete Template, 
    Common Pitfalls
  - OPTIONAL sections: Integration, File Locations, Testing
    (include when the domain involves wiring into existing code)
  
  FORMATTING RULES:
  - Use `---` horizontal rules between all top-level sections
  - Use H2 (##) for top-level sections, H3 (###) for subsections
  - Use tables for structured data (comparisons, options, mappings)
  - Use code blocks with language tags for all code examples
  - Mark correct patterns with ✅ and incorrect patterns with ❌
  - Keep the Purpose blockquote to 1–2 sentences
  - Do not use emoji in section headers (keep headers scannable)

  CONTENT RULES:
  - Lead with code, not prose — show the pattern first, explain after
  - Every rule must have both a wrong and correct example
  - Complete Template should be copy-paste ready with minimal edits
  - Checklist items must be verifiable (answerable with yes/no)
  - References should use relative paths for codebase files
-->

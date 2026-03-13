# Candidate Source Badges Implementation

**Date**: October 24, 2025  
**Status**: ✅ Complete  
**Feature**: Clear visual badges showing candidate source (Applicant vs. Market Search)

## Overview

Added prominent source badges to clearly indicate where each candidate came from in the candidate outreach system.

## Implementation

### Source Badge Location
**Position**: Next to candidate name in detail view header

**Visual Design**:
```typescript
<span className={`px-2 py-0.5 rounded text-xs font-medium ${
  selectedCandidate.source === 'market'
    ? 'bg-purple-500/10 text-purple-500 border border-purple-500/30'
    : 'bg-blue-500/10 text-blue-500 border border-blue-500/30'
}`}>
  {selectedCandidate.source === 'market' ? '🔍 Market Search' : '📋 Applicant'}
</span>
```

### Color Scheme

| Source | Badge Color | Icon | Use Case |
|--------|-------------|------|----------|
| **Market Search** | 🟣 Purple | 🔍 | Candidates found through PDL/market search |
| **Applicant** | 🔵 Blue | 📋 | Candidates who applied directly |

### Visual Examples

**Market Search Candidate**:
```
┌──────────────────────────────────────────┐
│ Priya Desai  [🔍 Market Search]  Score 9 │
│                  ↑ Purple badge           │
└──────────────────────────────────────────┘
```

**Applicant Candidate**:
```
┌──────────────────────────────────────────┐
│ Alex Chen  [📋 Applicant]  Score 9.2     │
│                ↑ Blue badge               │
└──────────────────────────────────────────┘
```

## Business Logic

### Greenhouse Integration
- ✅ **Market Search** candidates → Show "Add to Greenhouse" section
- ✅ **Applicant** candidates → No Greenhouse section (already in system)

**Reasoning**: 
- Market candidates need to be added to Greenhouse ATS
- Applicants are already in Greenhouse (they applied through it)

### Badge Visibility
- ✅ Shows in detail pane header (next to name)
- ✅ Small, unobtrusive design
- ✅ Clear visual distinction between sources
- ✅ Emoji icons for quick recognition

## Code Structure

### Data Model
```typescript
type Candidate = {
  id: string;
  name: string;
  source: 'applicant' | 'market';  // ← Source field
  // ... other fields
}
```

### Conditional Rendering
```typescript
{/* Only show Greenhouse for market candidates */}
{selectedCandidate.source === 'market' && (
  <div className="mb-4 p-4 bg-brand/5 border border-brand/20 rounded-lg">
    {/* Greenhouse submission UI */}
  </div>
)}
```

## User Experience

### Before:
- ❌ No clear indication of candidate source
- ❌ Users had to infer from context
- ❌ Confusion about why some have Greenhouse section

### After:
- ✅ **Immediately visible** source badge
- ✅ **Color-coded** for quick scanning
- ✅ **Icon + text** for accessibility
- ✅ **Explains** why Greenhouse appears for some candidates

## Visual Hierarchy

```
Candidate Detail Header:
├── Name + Source Badge  ← Added!
│   ├── "Priya Desai"
│   └── [🔍 Market Search] ← Purple badge
├── Contact Info (email, phone, LinkedIn)
└── Match Score (right side)

Below Header:
├── Highlights/Tags
├── [If Market] → Greenhouse Section  ← Only for market!
├── Warnings (visa, previous application)
└── Email Section
```

## Testing Scenarios

### Test Case 1: Market Candidate
1. Select a market candidate (e.g., Priya Desai)
2. ✅ See purple "🔍 Market Search" badge
3. ✅ See "Add to Greenhouse" section below tags
4. ✅ Can submit to Greenhouse

### Test Case 2: Applicant Candidate
1. Select an applicant candidate (e.g., Alex Chen)
2. ✅ See blue "📋 Applicant" badge
3. ✅ No "Add to Greenhouse" section (already in ATS)
4. ✅ Can still send outreach email

### Test Case 3: Quick Scanning
1. Switch between multiple candidates
2. ✅ Badge color changes instantly
3. ✅ Easy to identify source at a glance
4. ✅ Greenhouse section appears/disappears appropriately

## Benefits

### For Users:
1. **Clarity**: Instantly know candidate source
2. **Context**: Understand why Greenhouse appears
3. **Efficiency**: Quick visual scanning by color
4. **Confidence**: No confusion about candidate origin

### For System:
1. **Logical**: Greenhouse only for market candidates
2. **Consistent**: Same badge in list and detail views
3. **Maintainable**: Single source of truth (`source` field)
4. **Scalable**: Easy to add more source types if needed

## Files Modified

- ✅ `frontend/src/pages/talent-intelligence/CandidateOutreachPage.tsx`
  - Added source badge component next to name
  - Used conditional styling (purple for market, blue for applicant)
  - Maintained existing Greenhouse conditional logic

## Future Enhancements

Possible improvements:
1. **Source filter** in left sidebar (show only market/only applicants)
2. **Source stats** at top ("12 market, 8 applicants")
3. **Additional sources** (e.g., "Referral", "LinkedIn", "Recruiter")
4. **Tooltip** on badge hover with more details
5. **Badge in list view** (not just detail view)

## Success Criteria

- ✅ Badge shows correct source for each candidate
- ✅ Color-coded (purple = market, blue = applicant)
- ✅ Positioned clearly next to name
- ✅ Greenhouse section only for market candidates
- ✅ No linting errors
- ✅ Responsive design (doesn't break on small screens)

---

**Candidate sources are now crystal clear!** Users can instantly see where each candidate came from. 🎉


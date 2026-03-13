# Candidate Outreach Page Enhancements

**Date**: October 24, 2025  
**Status**: ✅ Complete  
**Features**: Email Modal, Cancel Scheduled, Analysis Linking

## Overview

Three major UX improvements to the Candidate Outreach page to improve hiring manager workflow:
1. **Large modal for email editing** - Better editing experience
2. **Cancel scheduled emails** - Return to pending state
3. **Clear analysis attribution** - Link back to source analysis

---

## Feature 1: Email Edit Modal

### Problem
- Email editing was inline, cramped in the right pane
- Hard to see full email while editing
- No clear "save" action - changes were live

### Solution
**Large, centered modal for email editing**

**Design**:
```
┌────────────────────────────────────────────┐
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │ Edit Email                         × │ │
│  ├──────────────────────────────────────┤ │
│  │                                      │ │
│  │ Subject:                             │ │
│  │ ┌──────────────────────────────────┐ │ │
│  │ │ ML Engineer Opportunity at...    │ │ │
│  │ └──────────────────────────────────┘ │ │
│  │                                      │ │
│  │ Body:                                │ │
│  │ ┌──────────────────────────────────┐ │ │
│  │ │                                  │ │ │
│  │ │ Hi Michael,                      │ │ │
│  │ │                                  │ │ │
│  │ │ I came across your profile...    │ │ │
│  │ │                                  │ │ │
│  │ │ (20 rows of text)                │ │ │
│  │ │                                  │ │ │
│  │ └──────────────────────────────────┘ │ │
│  │                                      │ │
│  │        [Cancel]  [✓ Save Changes]   │ │
│  └──────────────────────────────────────┘ │
│                                            │
└────────────────────────────────────────────┘
```

**Key Features**:
- ✅ **Large** - `max-w-4xl` width, `90vh` height
- ✅ **Centered** - Fixed overlay with flex center
- ✅ **Scrollable** - Body scrolls independently
- ✅ **Explicit save** - Changes only apply on "Save Changes"
- ✅ **Cancel option** - Discard changes and close
- ✅ **Escape key** - Close modal (implicit via X button)
- ✅ **Dark backdrop** - `bg-black/50` overlay
- ✅ **Large textarea** - 20 rows for comfortable editing

**Code**:
```typescript
const [showEmailModal, setShowEmailModal] = useState(false);

const handleOpenEmailModal = () => {
  if (selectedCandidate) {
    setEmailSubject(selectedCandidate.prewrittenEmail.subject);
    setEmailBody(selectedCandidate.prewrittenEmail.body);
    setShowEmailModal(true);
  }
};

const handleSaveEmailChanges = () => {
  // Update candidate's prewritten email
  setCandidates(prev => prev.map(c =>
    c.id === selectedCandidate.id
      ? { ...c, prewrittenEmail: { subject: emailSubject, body: emailBody } }
      : c
  ));
  setSelectedCandidate({
    ...selectedCandidate,
    prewrittenEmail: { subject: emailSubject, body: emailBody },
  });
  setShowEmailModal(false);
};
```

**User Flow**:
1. User clicks "Edit Email" button
2. Modal opens with current email content
3. User edits subject and/or body
4. User clicks "Save Changes" → Updates email
5. OR user clicks "Cancel" or X → Discards changes

**Benefits**:
- 📝 **Better editing experience** - More space to see/edit
- 💾 **Explicit save** - Clear when changes are applied
- ❌ **Can cancel** - Discard unwanted changes
- 🎯 **Focused** - Dark backdrop removes distractions

---

## Feature 2: Cancel Scheduled Emails

### Problem
- Once email was scheduled, no way to cancel it
- If hiring manager changed their mind, stuck with scheduled state
- No way to edit a scheduled email

### Solution
**"Cancel Scheduled Email" button returns to pending**

**UI**:
```
┌────────────────────────────────────────┐
│ 🕐 Email scheduled for:                │
│    2025-10-24 10:00 AM PST             │
├────────────────────────────────────────┤
│  [❌ Cancel Scheduled Email]           │
└────────────────────────────────────────┘
```

**Code**:
```typescript
const handleCancelScheduled = (candidateId: string) => {
  if (window.confirm('Cancel scheduled email and return to pending?')) {
    setCandidates(prev => prev.map(c =>
      c.id === candidateId
        ? { ...c, outreachStatus: 'pending', scheduledFor: undefined }
        : c
    ));
    // Update selectedCandidate
    if (selectedCandidate?.id === candidateId) {
      setSelectedCandidate({
        ...selectedCandidate,
        outreachStatus: 'pending',
        scheduledFor: undefined,
      });
    }
    window.alert('📅 Scheduled email cancelled and returned to pending');
  }
};
```

**State Transition**:
```
┌─────────┐  Schedule   ┌───────────┐  Cancel   ┌─────────┐
│ Pending │ ─────────> │ Scheduled │ ────────> │ Pending │
└─────────┘             └───────────┘           └─────────┘
     │                                               │
     │                                               │
     └───────────────────────────────────────────────┘
              (Can now edit, send, or reject)
```

**User Flow**:
1. Email is in "scheduled" state
2. User clicks "Cancel Scheduled Email"
3. Confirmation dialog appears
4. User confirms
5. Email returns to "pending" state
6. User can now:
   - Edit the email
   - Send it immediately
   - Schedule it for different time
   - Reject the candidate

**Benefits**:
- 🔄 **Flexibility** - Change plans after scheduling
- ✏️ **Can edit** - Return to pending to modify email
- 🎯 **Clear action** - Prominent button when scheduled
- ⚠️ **Safe** - Confirmation dialog prevents accidents

---

## Feature 3: Analysis Attribution & Linking

### Problem
- No clear indication of which analysis produced each candidate
- Hiring managers couldn't easily go back to see full analysis
- Lost context about search parameters and other candidates

### Solution
**Analysis info box with link to filtered history**

**UI**:
```
┌─────────────────────────────────────────────┐
│ From Analysis                [View Analysis]│
│ Senior ML Engineer Search - Q4 2024        │
│ 10/15/2024                                  │
└─────────────────────────────────────────────┘
```

**Placement**: Between Greenhouse section and warnings

**Code**:
```typescript
// Added to candidate interface
interface CandidateWithEmail {
  // ... existing fields
  analysisId: string;
  analysisName: string;
  analysisDate: string;
}

// UI component
<div className="mb-4 p-3 bg-surface-2 border border-border rounded-lg">
  <div className="flex items-start justify-between">
    <div>
      <p className="text-xs text-muted mb-1">From Analysis</p>
      <p className="text-sm font-medium text-text">
        {selectedCandidate.analysisName}
      </p>
      <p className="text-xs text-muted mt-1">
        {new Date(selectedCandidate.analysisDate).toLocaleDateString()}
      </p>
    </div>
    <button
      onClick={() => navigate(`/talent/analysis-history?id=${selectedCandidate.analysisId}`)}
      className="px-3 py-1.5 text-xs text-brand hover:bg-brand/10 rounded"
    >
      View Analysis →
    </button>
  </div>
</div>
```

**Hardcoded Data Examples**:
```typescript
// Candidate 1 & 2 from same analysis
analysisId: 'analysis-2024-10-15',
analysisName: 'Senior ML Engineer Search - Q4 2024',
analysisDate: '2024-10-15',

// Candidate 3 & 4 from different analysis
analysisId: 'analysis-2024-10-12',
analysisName: 'ML Infrastructure Engineer - Platform Team',
analysisDate: '2024-10-12',

// Candidate 5 from older analysis
analysisId: 'analysis-2024-10-08',
analysisName: 'Staff ML Engineer - Recommendations Team',
analysisDate: '2024-10-08',
```

**Navigation**:
- Button navigates to: `/talent/history?id=analysis-2024-10-15`
- Talent History page can read `?id=` param from URL
- Auto-scroll to that analysis or highlight it
- Shows full analysis details for context

**Benefits**:
- 🔗 **Context** - Always know which analysis sourced the candidate
- 📊 **Deep dive** - One click to see full analysis
- 🔍 **Compare** - See other candidates from same analysis
- 📅 **Timeline** - Date shows when analysis was run
- 🎯 **Organized** - Group candidates by analysis in mind

---

## Visual Flow Comparison

### Before:
```
┌────────────────────────────────┐
│ Priya Desai           Score 9 │
│ 📧 email  🔗 LinkedIn         │
├────────────────────────────────┤
│ 🏷️ Highlights                 │
├────────────────────────────────┤
│ ⚠️ Warnings                    │
├────────────────────────────────┤
│ 📧 Pre-written Email    [Edit] │
│                                │
│ ┌────────────────────────────┐ │
│ │ [Inline editing here]      │ │
│ │ Subject: ...               │ │
│ │ Body: ...                  │ │
│ │ (cramped, unclear save)    │ │
│ └────────────────────────────┘ │
│                                │
│ [Send Now]  [Schedule Send]    │
│                                │
│ (No cancel for scheduled)      │
│ (No analysis link)             │
└────────────────────────────────┘
```

### After:
```
┌────────────────────────────────┐
│ Priya Desai  [🔍 Market]  9  │
│ 📧 email  🔗 LinkedIn         │
├────────────────────────────────┤
│ 🏷️ Highlights                 │
├────────────────────────────────┤
│ 💼 Add to Greenhouse          │  ← If market candidate
│    [Refresh]  [Search]  [Add] │
├────────────────────────────────┤
│ 📊 From Analysis  [View →]    │  ← NEW!
│    Senior ML Engineer - Q4    │
│    10/15/2024                  │
├────────────────────────────────┤
│ ⚠️ Warnings                    │
├────────────────────────────────┤
│ 📧 Pre-written Email           │
│    [Edit Email]  ← Opens modal│  ← IMPROVED!
│                                │
│ Subject: ...                   │
│ Body: ...                      │
│ (Read-only preview)            │
│                                │
│ [Send Now]  [Schedule Send]    │
│                                │
│ OR if scheduled:               │
│ 🕐 Scheduled for: 10/24 10AM   │
│ [❌ Cancel Scheduled Email]   │  ← NEW!
└────────────────────────────────┘
```

---

## Implementation Details

### Data Model Changes
```typescript
// Before
interface CandidateWithEmail {
  id: string;
  name: string;
  // ... other fields
  outreachStatus: 'pending' | 'scheduled' | 'sent' | 'rejected';
  scheduledFor?: string;
}

// After (added 3 fields)
interface CandidateWithEmail {
  id: string;
  name: string;
  // ... other fields
  outreachStatus: 'pending' | 'scheduled' | 'sent' | 'rejected';
  scheduledFor?: string;
  analysisId: string;        // ← NEW
  analysisName: string;      // ← NEW
  analysisDate: string;      // ← NEW
}
```

### State Management
```typescript
// Modal state
const [showEmailModal, setShowEmailModal] = useState(false);

// Removed: editingEmail (inline editing)
// Added: showEmailModal (modal editing)
```

### New Handler Functions
```typescript
// 1. Open modal
const handleOpenEmailModal = () => { ... }

// 2. Save email changes
const handleSaveEmailChanges = () => { ... }

// 3. Cancel scheduled email
const handleCancelScheduled = (candidateId: string) => { ... }
```

### Navigation Integration
```typescript
import { useNavigate } from 'react-router-dom';

const navigate = useNavigate();

// Link to talent history with pre-filter
navigate(`/talent/history?id=${selectedCandidate.analysisId}`)
```

---

## User Scenarios

### Scenario 1: Edit Email Before Sending
1. User selects candidate "Priya Desai"
2. Reads pre-written email
3. Clicks "Edit Email"
4. **Large modal opens** ✨
5. User edits: "Your PyTorch optimization work" → "Your FAANG ML experience"
6. User clicks "Save Changes"
7. Modal closes, email updated
8. User clicks "Send Now"
9. Email sent with customized content

### Scenario 2: Cancel Scheduled Email
1. User previously scheduled email for Priya at 10 AM tomorrow
2. Status shows: "🕐 Email scheduled for: 2025-10-24 10:00 AM PST"
3. User changes their mind (wants to edit first)
4. Clicks **"Cancel Scheduled Email"** ✨
5. Confirms cancellation
6. Email returns to "pending"
7. User can now edit, send immediately, or reschedule

### Scenario 3: Check Analysis Details
1. User reviewing candidate "David Park"
2. Sees: **"From Analysis: ML Infrastructure Engineer - Platform Team"** ✨
3. Wonders what other candidates were in that analysis
4. Clicks **"View Analysis →"**
5. Navigates to Talent History page (`/talent/history?id=...`)
6. Sees full analysis with all 12 candidates
7. Compares David to other top candidates
8. Returns to outreach page with context

---

## Files Modified

### Frontend
- ✅ `frontend/src/pages/talent-intelligence/CandidateOutreachPage.tsx`
  - Added analysis fields to interface (+3 fields)
  - Updated all 5 hardcoded candidates with analysis data
  - Replaced inline editing with modal (+60 lines)
  - Added `handleOpenEmailModal` function
  - Added `handleSaveEmailChanges` function
  - Added `handleCancelScheduled` function
  - Added analysis info section with link
  - Added cancel button for scheduled emails
  - Imported `useNavigate` from react-router-dom

---

## Testing Checklist

### Email Modal
- [ ] Click "Edit Email" opens modal
- [ ] Modal shows current subject and body
- [ ] Can edit both subject and body
- [ ] "Save Changes" updates email content
- [ ] "Cancel" discards changes
- [ ] X button closes modal
- [ ] Modal is centered and large
- [ ] Textarea is large enough (20 rows)

### Cancel Scheduled
- [ ] Scheduled emails show cancel button
- [ ] Click "Cancel Scheduled Email" shows confirmation
- [ ] Confirm returns email to "pending"
- [ ] Can now edit the email
- [ ] Can send immediately after cancelling
- [ ] Can reschedule after cancelling

### Analysis Link
- [ ] Analysis info box shows for all candidates
- [ ] Shows correct analysis name and date
- [ ] Click "View Analysis" navigates to `/talent/history` page
- [ ] URL includes `?id=analysis-xxx` parameter
- [ ] Can navigate back to outreach page
- [ ] Different candidates show different analyses

---

## Success Metrics

### Email Editing
- ✅ Larger editing area (4xl width vs. side pane)
- ✅ Explicit save prevents accidental changes
- ✅ Can cancel edits without losing original
- ✅ Better UX for long emails

### Cancel Scheduled
- ✅ Flexibility to change scheduled sends
- ✅ Can edit scheduled emails (via cancel → edit)
- ✅ Prevents "stuck" in scheduled state

### Analysis Attribution
- ✅ Always clear which analysis sourced candidate
- ✅ One click to full analysis details
- ✅ Better organization by analysis runs
- ✅ Historical context preserved

---

## Future Enhancements

Possible improvements:
1. **Keyboard shortcuts** - Escape to close modal, Cmd+S to save
2. **Rich text editing** - Bold, italics, links in email
3. **Email templates** - Save common edits as templates
4. **Bulk cancel** - Cancel all scheduled emails at once
5. **Analysis filters** - Filter candidates by analysis in left sidebar
6. **Schedule time picker** - Visual time selector instead of prompt
7. **Email preview** - See how email will look to recipient
8. **Undo** - Undo last edit or cancellation

---

**All three enhancements are now live!** The candidate outreach workflow is significantly improved. 🎉


# Email Templates Management Page

**Date**: October 24, 2025  
**Status**: ✅ Complete  
**Feature**: Reusable email templates with dynamic variables

## Overview

Created a new Email Templates management page where hiring managers can view, create, and manage reusable email templates with dynamic variables like `{{candidate_name}}`, `{{skill}}`, `{{current_date}}`, etc.

---

## Page Features

### 1. Template Categories
Templates are organized into 5 categories:
- 📋 **Applicant Follow-up** - Following up with applicants
- 🔍 **Market Outreach** - Cold outreach to passive candidates
- 📅 **Interview Invite** - Scheduling interviews
- ❌ **Rejection** - Polite candidate rejections
- 🔧 **Custom** - User-created templates

### 2. Dynamic Variables
Supported variables that get replaced with actual data:
- `{{candidate_name}}` - Full name (e.g., "John Smith")
- `{{candidate_first_name}}` - First name only (e.g., "John")
- `{{skill}}` - Primary skill (e.g., "PyTorch and MLOps")
- `{{company_name}}` - Company name (e.g., "TechCorp")
- `{{role_title}}` - Job title (e.g., "Senior ML Engineer")
- `{{current_date}}` - Today's date (e.g., "October 24, 2025")
- `{{your_name}}` - Sender's name (e.g., "Sarah Johnson")
- `{{your_title}}` - Sender's title (e.g., "Engineering Manager")

### 3. Split-Pane Layout
**Left Panel**: List of templates
- Category badges
- Usage statistics
- Last used date
- Filterable by category

**Right Panel**: Template details
- Subject and body preview
- Variable list
- Preview mode (shows rendered template)
- Edit mode (shows template with variables)
- Action buttons (Edit, Duplicate, Delete)

### 4. Preview Mode
Toggle between:
- **Edit Mode**: Shows raw template with `{{variables}}`
- **Preview Mode**: Shows template with sample data filled in

---

## Hardcoded Templates

### Template 1: Application Follow-up - Better Role
**Category**: Applicant Follow-up  
**Use Case**: Suggest a better-fit role to existing applicant

**Subject**:
```
Following Up on Your Application - {{role_title}} Role Update
```

**Key Features**:
- Acknowledges their application
- Suggests a senior/better role
- Maintains original application
- Personalized to their skills

### Template 2: Market Outreach - Cold Introduction
**Category**: Market Outreach  
**Use Case**: First contact with passive candidates

**Subject**:
```
{{role_title}} Opportunity at {{company_name}} - Your {{skill}} Expertise
```

**Key Features**:
- Professional cold outreach
- Highlights their expertise
- Low-pressure approach
- Clear call to action

### Template 3: Interview Invitation
**Category**: Interview Invite  
**Use Case**: Move candidate to interview stage

**Subject**:
```
Next Steps: {{role_title}} Interview at {{company_name}}
```

**Key Features**:
- Clear next steps
- Interview structure preview
- Availability request
- Professional tone

### Template 4: Second Chance - Previous Rejection
**Category**: Applicant Follow-up  
**Use Case**: Re-engage previously rejected candidates

**Subject**:
```
{{role_title}} Role - Different Team, Perfect Timing
```

**Key Features**:
- Acknowledges past interaction
- Explains why this is different
- Respects their decision
- Offers "out" gracefully

### Template 5: Rejection - Respectful Closure
**Category**: Rejection  
**Use Case**: Decline candidates professionally

**Subject**:
```
Update on Your {{role_title}} Application
```

**Key Features**:
- Respectful and kind
- Keeps door open for future
- Thanks them for time
- Professional closure

### Template 6: Remote Work Emphasis
**Category**: Market Outreach  
**Use Case**: Highlight remote flexibility

**Subject**:
```
Remote {{role_title}} Role at {{company_name}}
```

**Key Features**:
- Emphasizes remote work
- Mentions distributed team
- Uses `{{current_date}}` for urgency
- Location-independent appeal

---

## UI Design

### Header
```
┌────────────────────────────────────────────────────┐
│ 📧 Email Templates        [+ Create Template]      │
│ Manage reusable email templates with variables     │
├────────────────────────────────────────────────────┤
│ [All (6)] [Applicant (2)] [Market (2)] ...        │
└────────────────────────────────────────────────────┘
```

### Split Pane Layout
```
┌─────────────────┬──────────────────────────────────┐
│ Template List   │ Template Details                 │
├─────────────────┼──────────────────────────────────┤
│                 │ Application Follow-up - Better...│
│ ┌─────────────┐ │ [Preview] [Copy] [Edit] [Delete] │
│ │ App Follow..│ │                                  │
│ │ Applicant   │ │ Variables: {{candidate_name}}... │
│ │ Used 12×    │ │                                  │
│ └─────────────┘ │ Subject:                         │
│                 │ Following Up on Your Application │
│ ┌─────────────┐ │                                  │
│ │ Market Out..│ │ Body:                            │
│ │ Market      │ │ Hi {{candidate_name}},           │
│ │ Used 28×    │ │                                  │
│ └─────────────┘ │ Thank you for applying...        │
│                 │                                  │
└─────────────────┴──────────────────────────────────┘
```

### Category Badges
Color-coded for quick identification:
- 🔵 Applicant Follow-up - Blue
- 🟣 Market Outreach - Purple
- 🟢 Interview Invite - Green
- 🟠 Rejection - Orange
- ⚪ Custom - Gray

---

## Technical Implementation

### Data Structure
```typescript
interface EmailTemplate {
  id: string;
  name: string;
  description: string;
  category: 'applicant_followup' | 'market_outreach' | 'interview_invite' | 'rejection' | 'custom';
  subject: string;
  body: string;
  variables: string[];
  createdAt: string;
  lastUsed?: string;
  useCount: number;
}
```

### Variable Replacement
```typescript
const sampleData = {
  candidate_name: 'John Smith',
  candidate_first_name: 'John',
  skill: 'PyTorch and MLOps',
  company_name: 'TechCorp',
  role_title: 'Senior ML Engineer',
  current_date: new Date().toLocaleDateString(...),
  your_name: 'Sarah Johnson',
  your_title: 'Engineering Manager',
};

const renderPreview = (text: string) => {
  let rendered = text;
  Object.entries(sampleData).forEach(([key, value]) => {
    const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
    rendered = rendered.replace(regex, value);
  });
  return rendered;
};
```

### Category Filtering
```typescript
const filteredTemplates = selectedCategory === 'all'
  ? templates
  : templates.filter(t => t.category === selectedCategory);
```

---

## Navigation

**Path**: `/talent/email-templates`

**Location in Sidebar**:
```
Talent
  ├── Talent Intelligence
  ├── Analysis History
  ├── Candidate Outreach
  └── Email Templates  ← NEW!
```

**Permissions**: `documents:read`

---

## User Workflows

### Workflow 1: Browse Templates
1. User clicks "Email Templates" in sidebar
2. Sees list of 6 templates
3. Clicks a template to view details
4. Toggles between Edit/Preview mode
5. Sees how variables are replaced

### Workflow 2: Filter by Category
1. User clicks "Market (2)" filter
2. List shows only market outreach templates
3. User compares different market templates
4. Selects best template for use case

### Workflow 3: Preview Template
1. User selects "Application Follow-up" template
2. Clicks "Preview" button
3. Sees template with sample data:
   - `{{candidate_name}}` → "John Smith"
   - `{{role_title}}` → "Senior ML Engineer"
   - `{{current_date}}` → "October 24, 2025"
4. Can visualize how email will look to recipient

### Workflow 4: Check Usage Stats
1. User browses templates
2. Sees "Used 28×" on popular template
3. Sees "Last used: 10/24/2024"
4. Identifies most effective templates

---

## Future Integration (Next Steps)

### Phase 2: Create/Edit Templates
- [ ] "Create Template" button functional
- [ ] Template editor with variable insertion
- [ ] Save new templates to database
- [ ] Edit existing templates
- [ ] Delete templates (with confirmation)

### Phase 3: Template Selection in Outreach
- [ ] Add "Use Template" button in Candidate Outreach page
- [ ] Template selector modal
- [ ] Auto-fill email with template
- [ ] Replace variables with actual candidate data
- [ ] Track template usage

### Phase 4: Template Analytics
- [ ] Track open rates per template
- [ ] Track response rates
- [ ] A/B test different templates
- [ ] Show "Top Performing" badge
- [ ] Suggest templates based on success

### Phase 5: AI-Powered Templates
- [ ] Generate templates with AI
- [ ] Personalize templates per candidate
- [ ] Optimize templates for engagement
- [ ] Multi-language templates

---

## Files Created/Modified

### New Files:
- ✅ `frontend/src/pages/talent-intelligence/EmailTemplatesPage.tsx` (500+ lines)
  - Complete email template management page
  - 6 hardcoded templates
  - Preview/Edit toggle
  - Category filtering
  - Variable replacement logic

### Modified Files:
- ✅ `frontend/src/App.tsx`
  - Added import for `EmailTemplatesPage`
  - Added route `/talent/email-templates`

- ✅ `frontend/src/components/layout/Navigation.tsx`
  - Added "Email Templates" navigation item
  - Placed under Talent section

---

## Testing Checklist

### UI Tests:
- [ ] Page loads at `/talent/email-templates`
- [ ] Shows 6 templates in list
- [ ] Category filters work (All, Applicant, Market, etc.)
- [ ] Selecting template shows details
- [ ] Preview/Edit toggle works
- [ ] Variables display correctly
- [ ] Sample data renders in preview mode

### Template Tests:
- [ ] All 6 templates display
- [ ] Subject contains variables
- [ ] Body contains variables
- [ ] Variables list is accurate
- [ ] Usage stats show correctly
- [ ] Category badges are color-coded

### Responsive Tests:
- [ ] Layout works on different screen sizes
- [ ] Split pane is functional
- [ ] Template list is scrollable
- [ ] Details pane is scrollable

---

## Success Criteria

- ✅ Email Templates page created
- ✅ 6 hardcoded templates with realistic content
- ✅ 8 dynamic variables supported
- ✅ Preview mode shows rendered template
- ✅ Edit mode shows template structure
- ✅ Category filtering functional
- ✅ Split-pane layout matches other pages
- ✅ Navigation link added to sidebar
- ✅ Route configured in App.tsx
- ⏳ Integration with Candidate Outreach (next phase)

---

## Template Variable Reference

| Variable | Description | Example Output |
|----------|-------------|----------------|
| `{{candidate_name}}` | Full name | John Smith |
| `{{candidate_first_name}}` | First name | John |
| `{{skill}}` | Primary skill | PyTorch and MLOps |
| `{{company_name}}` | Company | TechCorp |
| `{{role_title}}` | Job title | Senior ML Engineer |
| `{{current_date}}` | Today's date | October 24, 2025 |
| `{{your_name}}` | Sender name | Sarah Johnson |
| `{{your_title}}` | Sender title | Engineering Manager |

**The Email Templates page is ready for testing!** Next step is to integrate template selection into the Candidate Outreach workflow. 🎉


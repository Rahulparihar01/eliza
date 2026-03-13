# Email Template Selector - Review & Configure Page

**Date**: October 24, 2025  
**Feature**: Email Template Selection in Talent Analysis Workflow

## Overview
Added an email template selector to the Review & Configure page (Step 4) of the Talent Intelligence workflow. This allows users to select which email template will be used for candidate outreach before running an analysis.

## Changes Made

### 1. Frontend State Management
**File**: `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx`

- Added `selectedEmailTemplateId: string | null` to `WorkflowConfig` interface
- Initialized field to `null` in component state
- Added field to `handleStartOver` reset logic

### 2. Analysis Summary Component
**File**: `frontend/src/components/talent-intelligence/AnalysisSummary.tsx`

Added new email template selector with:
- **Icon**: `EnvelopeIcon` from Heroicons
- **Template Options**: References the same hardcoded templates from `EmailTemplatesPage`:
  - `tmpl-001`: Application Follow-up - Better Role
  - `tmpl-002`: Market Outreach - Cold Intro
  - `tmpl-003`: Interview Invitation
  - `tmpl-004`: Second Chance - Previous Rejection
  - `tmpl-006`: Market Outreach - Remote Focus
- **Grouped dropdown**: Organized by category (Applicant Follow-up, Market Outreach, Interview)
- **Help text**: Includes link to Email Templates page for customization
- **Optional selection**: User can leave blank (no template selected)

### 3. Component Interface
Updated `AnalysisSummaryProps`:
- Added `selectedEmailTemplateId: string | null`
- Added `onEmailTemplateChange: (templateId: string) => void`

### 4. UI/UX Features
- Dropdown selector with optgroups for better organization
- Link to `/talent/email-templates` for template management
- Positioned below PDL Query Limit in Analysis Settings section
- Fully styled to match existing UI components
- Optional field (defaults to no template selected)

## Backend Integration
**Status**: NOT IMPLEMENTED (as requested by user)

The selected email template ID is:
- ✅ Stored in frontend state
- ✅ Displayed in the UI
- ❌ **NOT sent to backend API**
- ❌ **NOT stored in database**
- ❌ **NOT used in pipeline execution**

## Next Steps (Future Work)
When integrating email template handling into the pipeline:

1. **API Update**: Add `email_template_id` to `StartAnalysisFromConnectorRequest` in `src/api/routes/ml_talent.py`
2. **Database Schema**: Add `email_template_id` column to `talent_analyses` table
3. **Pipeline Integration**: Pass template to email generation stage
4. **Template Rendering**: Implement variable substitution for selected template
5. **Email Service**: Use template when sending candidate outreach emails

## Testing
- ✅ Frontend compiles without errors
- ✅ Linter checks pass
- ✅ Template selector displays correctly
- ✅ State management works properly
- ✅ Link to Email Templates page is functional
- ✅ Dropdown organizes templates by category

## Template Synchronization
The template list is **hardcoded** in both locations:
- `frontend/src/pages/talent-intelligence/EmailTemplatesPage.tsx` (full templates)
- `frontend/src/components/talent-intelligence/AnalysisSummary.tsx` (template IDs and names)

**Important**: If new templates are added to `EmailTemplatesPage`, they must be manually added to the `EMAIL_TEMPLATES` constant in `AnalysisSummary.tsx`.

Future improvement: Create a shared constants file or fetch templates from an API.

## Files Modified
1. `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx`
2. `frontend/src/components/talent-intelligence/AnalysisSummary.tsx`

## Files Created
1. `docs/20251024_EMAIL_TEMPLATE_SELECTOR.md` (this file)


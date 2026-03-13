# Tenant Management Page - Design System Migration Plan

> **Target Page:** `frontend/src/pages/platform-admin/TenantManagementPage.tsx`  
> **Current Lines:** ~1,958 lines  
> **Priority:** High (Core Admin/Settings)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Component Inventory](#current-component-inventory)
3. [Component Mapping](#component-mapping)
4. [Color Migration](#color-migration)
5. [Migration Phases](#migration-phases)
6. [Detailed Migration Steps](#detailed-migration-steps)
7. [Special Considerations](#special-considerations)
8. [Testing Checklist](#testing-checklist)

---

## Executive Summary

The Tenant Management page is a complex admin page with:
- **Expandable data table** for tenant list
- **4 modal dialogs** (Create, Deactivate, Reactivate, Feature Allocation)
- **Inline editing** for admin details
- **Feature chips** (toggleable selection)
- **Status badges** and validation feedback

**Estimated Effort:** 4-6 hours  
**Risk Level:** Medium (page has complex state management)

---

## Current Component Inventory

### Page Structure

| Current Element | Location | Count | Notes |
|-----------------|----------|-------|-------|
| `AdminShell` | Page wrapper | 1 | Already a DS-compatible component |
| Custom search input | Line 936-943 | 1 | Replace with `Input` |
| HTML `<table>` | Line 948-1304 | 1 | Keep for expandable rows (see notes) |

### Buttons

| Current Pattern | Location | Count | Replace With |
|-----------------|----------|-------|--------------|
| `<button className="...bg-brand...">` | Lines 847-852, 921-927, 1141, etc. | 15+ | `Button` |
| `<button className="...text-brand...">` (link style) | Lines 1107, 1146, etc. | 5+ | `Button variant="link"` |
| `<button className="...border-red...">` | Line 1280 | 2 | `Button variant="danger-outline"` |
| `<button className="...border-green...">` | Line 1290 | 1 | `Button variant="outline"` + green class |
| `<button className="...px-4 py-2...">` (cancel) | Lines 1363, 1421, 1811, etc. | 6 | `Button variant="ghost"` |
| Feature toggle chips | Lines 1637-1657 | Dynamic | Keep custom (specialized UI) |

### Inputs

| Current Pattern | Location | Count | Replace With |
|-----------------|----------|-------|--------------|
| `<input type="text"...>` | Lines 936, 1121, 1131, 1350, 1411, etc. | 10+ | `Input` |
| `<input type="email"...>` | Lines 1559, etc. | 2 | `Input type="email"` |
| `<input type="number"...>` | Line 1618 | 1 | `Input type="number"` |
| `<textarea...>` | Line 1338 | 1 | `Textarea` |
| `<select...>` | Line 1605 | 1 | `Select` + `SelectOption` |

### Modals

| Modal | Lines | Current Pattern | Replace With |
|-------|-------|-----------------|--------------|
| Deactivate Tenant | 1308-1378 | Custom `<div>` overlay | `Modal*` components |
| Reactivate Tenant | 1380-1438 | Custom `<div>` overlay | `Modal*` components |
| Create Tenant | 1440-1839 | Custom `<div>` overlay + scroll | `Modal*` components |
| Feature Allocation | 1841-1949 | Custom `<div>` overlay | `Modal*` components |

### Feedback Components

| Current Pattern | Location | Count | Replace With |
|-----------------|----------|-------|--------------|
| Error banner (`bg-error/10`) | Lines 897-899 | 1 | `Alert variant="error"` |
| Success banner (`bg-success/10`) | Lines 903-929 | 1 | `Alert variant="success"` |
| Info banner (cross-tenant mode) | Lines 885-892 | 1 | `Alert variant="info"` |
| Modal error alert | Lines 1458-1470 | 1 | `Alert variant="error"` |
| Warning text (`text-warning`) | Line 1660 | 2 | `Alert variant="warning"` or styled text |

### Status Badges

| Current Pattern | Location | Count | Replace With |
|-----------------|----------|-------|--------------|
| Active status (`bg-success/10`) | Lines 1032-1035 | 2 | `Badge variant="success"` |
| Pending invite (`bg-warning/10`) | Lines 1014-1017, 1173 | 3 | `Badge variant="warning"` |
| Deactivated (`bg-error/10`) | Lines 1038-1041 | 1 | `Badge variant="danger"` |
| Customer ID code badge | Line 1006 | 1 | Keep custom code styling |
| Feature chips (allocated) | Lines 1228-1234 | Dynamic | Keep custom or use `Badge` |

### Loading States

| Current Pattern | Location | Count | Replace With |
|-----------------|----------|-------|--------------|
| Page loading spinner | Lines 866-868 | 1 | `Spinner size="lg"` |
| Button loading spinners | Lines 1500, 1825, 1935 | 4+ | `Spinner size="sm"` |
| Availability check spinner | Line 1500 | 1 | `Spinner size="sm"` |

---

## Component Mapping

### Complete Mapping Table

| Current | DS Component | Props/Notes |
|---------|--------------|-------------|
| `<button className="bg-brand...">` | `Button` | Default variant |
| `<button className="text-brand hover:...">` | `Button variant="link"` | Link-style buttons |
| `<button className="border-border...">` | `Button variant="outline"` | Cancel/secondary actions |
| `<button className="bg-red-600...">` | `Button variant="danger"` | Destructive actions |
| `<button className="border-red-300...">` | `Button variant="outline"` + custom red | Danger outline |
| `<input type="text"...>` | `Input` | Add `placeholder`, handle `onChange` |
| `<input type="email"...>` | `Input type="email"` | Email validation |
| `<input type="number"...>` | `Input type="number"` | Numeric input |
| `<textarea...>` | `Textarea` | Use `rows` prop |
| `<select...><option>` | `Select` + `SelectOption` | **Note:** Use `onValueChange` not `onChange` |
| Custom modal overlay | `Modal, ModalBackdrop, ModalContent` | Combine with `ModalHeader`, `ModalBody`, `ModalFooter` |
| `<div className="bg-error/10...">` | `Alert variant="error"` | Error banners |
| `<div className="bg-success/10...">` | `Alert variant="success"` | Success banners |
| `<div className="bg-violet-600/10...">` | `Alert variant="info"` | Info banners |
| `<span className="bg-success/10 text-success...">` | `Badge variant="success"` | Status badges |
| `<span className="bg-warning/10 text-warning...">` | `Badge variant="warning"` | Pending status |
| `<span className="bg-error/10 text-error...">` | `Badge variant="danger"` | Error/inactive status |
| `<div className="animate-spin...">` | `Spinner` | Use `size` prop |
| `<label className="...">` | `Label` | Form labels |

---

## Color Migration

### Text Colors

| Legacy Class | DS Class |
|--------------|----------|
| `text-text` | `text-charcoal dark:text-gray-100` |
| `text-muted` | `text-gray-500 dark:text-gray-400` |
| `text-brand` | `text-eliza-red` |
| `text-brand-hover` | `text-eliza-red-light` |
| `text-success` | `text-green-600 dark:text-green-400` |
| `text-warning` | `text-amber-600 dark:text-amber-400` |
| `text-error` | `text-red-600 dark:text-red-400` |

### Background Colors

| Legacy Class | DS Class |
|--------------|----------|
| `bg-surface` | `bg-white dark:bg-dark-surface` |
| `bg-surface-2` | `bg-gray-50 dark:bg-dark-surface-2` |
| `bg-brand` | `bg-eliza-red` |
| `bg-brand/10` | `bg-eliza-red/10` |
| `bg-success/10` | `bg-green-100 dark:bg-green-900/20` |
| `bg-warning/10` | `bg-amber-100 dark:bg-amber-900/20` |
| `bg-error/10` | `bg-red-100 dark:bg-red-900/20` |

### Border Colors

| Legacy Class | DS Class |
|--------------|----------|
| `border-border` | `border-gray-200 dark:border-dark-border` |
| `border-brand` | `border-eliza-red` |
| `border-brand/50` | `border-eliza-red/50` |

---

## Migration Phases

### Phase 1: Imports & Setup (15 min)

Add DS component imports at the top of the file:

```tsx
import {
  // Layout
  PageHeader,
  PageContent,
  SectionHeader,
  
  // Form Components
  Button,
  Input,
  Select,
  SelectOption,
  Textarea,
  Label,
  
  // Feedback
  Alert,
  Badge,
  Spinner,
  
  // Modal
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
} from '../../components/ui';
```

### Phase 2: Loading States (20 min)

Replace custom spinners with `Spinner` component:

**Before:**
```tsx
<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
```

**After:**
```tsx
<Spinner size="lg" />
```

**Button spinners:**
```tsx
// Before
<div className="w-4 h-4 border-2 border-on-brand/30 border-t-on-brand rounded-full animate-spin"></div>

// After
<Spinner size="sm" className="text-on-brand" />
```

### Phase 3: Alert Banners (30 min)

**Error Banner (Line 896-899):**
```tsx
// Before
<div className="mb-6 p-4 bg-error/10 border border-error/20 rounded-lg text-error">
  {error}
</div>

// After
<Alert variant="error" className="mb-6">
  {error}
</Alert>
```

**Success Banner with Invite URL (Lines 902-930):**
```tsx
// Before (complex custom banner)
<div className="mb-6 p-4 bg-success/10 border border-success/20 rounded-lg">
  ...
</div>

// After
<Alert variant="success" className="mb-6" dismissible onDismiss={() => setCreatedInviteUrl(null)}>
  <div className="flex items-center justify-between">
    <div>
      <p className="font-medium">Tenant created successfully!</p>
      <p className="text-sm opacity-80 mt-1">Share this invite URL with the tenant admin:</p>
    </div>
  </div>
  <div className="mt-3 flex items-center gap-2">
    <code className="flex-1 px-3 py-2 bg-white/20 rounded text-sm font-mono truncate">
      {createdInviteUrl}
    </code>
    <Button size="sm" onClick={copyInviteUrl}>
      {copiedUrl ? <CheckIcon className="h-4 w-4" /> : <ClipboardDocumentIcon className="h-4 w-4" />}
      {copiedUrl ? 'Copied!' : 'Copy'}
    </Button>
  </div>
</Alert>
```

**Cross-Tenant Mode Banner (Lines 885-893):**
```tsx
// After
<Alert variant="info" className="mb-4">
  <GlobeAltIcon className="w-5 h-5" />
  <div>
    <p className="font-medium">Cross-Tenant Access Mode is active.</p>
    <p className="text-sm opacity-80">You can now view data from all tenants in reports and dashboards.</p>
  </div>
</Alert>
```

### Phase 4: Form Inputs (45 min)

**Search Input (Lines 933-944):**
```tsx
// Before
<input
  type="text"
  placeholder="Search tenants..."
  value={searchQuery}
  onChange={(e) => setSearchQuery(e.target.value)}
  className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg..."
/>

// After
<Input
  placeholder="Search tenants..."
  value={searchQuery}
  onChange={(e) => setSearchQuery(e.target.value)}
  className="pl-10"  // For icon positioning
/>
```

**Select Dropdown (Lines 1605-1614):**
```tsx
// Before
<select
  value={createForm.subscription_tier}
  onChange={(e) => setCreateForm(prev => ({ ...prev, subscription_tier: e.target.value }))}
  className="w-full px-3 py-2 bg-surface-2 border border-border rounded-lg..."
>
  <option value="starter">Starter</option>
  ...
</select>

// After
<Select
  value={createForm.subscription_tier}
  onValueChange={(value) => setCreateForm(prev => ({ ...prev, subscription_tier: value }))}
>
  <SelectOption value="starter">Starter</SelectOption>
  <SelectOption value="standard">Standard</SelectOption>
  <SelectOption value="professional">Professional</SelectOption>
  <SelectOption value="enterprise">Enterprise</SelectOption>
</Select>
```

**Text Input with Validation (Lines 1482-1516):**
```tsx
// After (with error state)
<Input
  type="text"
  required
  value={createForm.customer_id}
  onChange={(e) => handleCustomerIdChange(e.target.value)}
  onBlur={() => handleFieldBlur('customer_id', createForm.customer_id)}
  placeholder="acme-corp"
  error={!!fieldErrors.customer_id}
  className={customerIdAvailable === true && createForm.customer_id ? 'border-green-500' : ''}
/>
```

**Textarea (Line 1338-1344):**
```tsx
// After
<Textarea
  value={deactivateReason}
  onChange={(e) => setDeactivateReason(e.target.value)}
  placeholder="Please provide a reason for deactivating this tenant..."
  rows={3}
/>
```

### Phase 5: Buttons (60 min)

**Primary Action Buttons:**
```tsx
// Before
<button
  onClick={handleOpenCreateModal}
  className="flex items-center gap-2 px-4 py-2 bg-brand text-on-brand rounded-lg hover:bg-brand-hover transition-colors"
>
  <PlusIcon className="w-5 h-5" />
  Create Tenant
</button>

// After
<Button onClick={handleOpenCreateModal}>
  <PlusIcon className="h-4 w-4" />
  Create Tenant
</Button>
```

**Danger Buttons:**
```tsx
// Before
<button
  onClick={handleDeactivateTenant}
  disabled={deactivating || ...}
  className="flex-1 py-2 px-4 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50..."
>
  {deactivating ? 'Deactivating...' : 'Deactivate Tenant'}
</button>

// After
<Button 
  variant="danger" 
  onClick={handleDeactivateTenant}
  disabled={deactivating || deactivateConfirmation !== 'DEACTIVATE' || deactivateReason.length < 10}
>
  {deactivating && <Spinner size="sm" className="mr-2" />}
  {deactivating ? 'Deactivating...' : 'Deactivate Tenant'}
</Button>
```

**Outline/Cancel Buttons:**
```tsx
// Before
<button
  onClick={handleCloseDeactivateModal}
  className="flex-1 py-2 px-4 text-sm font-medium text-muted hover:text-text border border-border rounded-lg transition-colors"
>
  Cancel
</button>

// After
<Button variant="outline" onClick={handleCloseDeactivateModal}>
  Cancel
</Button>
```

**Link-Style Buttons:**
```tsx
// Before
<button
  onClick={() => handleStartEditAdmin(tenant)}
  className="text-xs text-brand hover:text-brand-hover flex items-center gap-1"
>
  <PencilIcon className="w-3 h-3" />
  Edit
</button>

// After
<Button variant="link" size="sm" onClick={() => handleStartEditAdmin(tenant)}>
  <PencilIcon className="h-3 w-3" />
  Edit
</Button>
```

### Phase 6: Status Badges (30 min)

**Active Status:**
```tsx
// Before
<span className="inline-flex items-center gap-1 px-2 py-0.5 bg-success/10 text-success rounded text-xs">
  <span className="w-1.5 h-1.5 bg-success rounded-full"></span>
  Active
</span>

// After
<Badge variant="success" dot>Active</Badge>
```

**Pending Invite:**
```tsx
// Before
<span className="inline-flex items-center gap-1 mt-0.5 px-1.5 py-0.5 bg-warning/10 text-warning rounded text-xs">
  <UserPlusIcon className="w-3 h-3" />
  Pending
</span>

// After
<Badge variant="warning">
  <UserPlusIcon className="h-3 w-3" />
  Pending
</Badge>
```

**Deactivated:**
```tsx
// After
<Badge variant="danger" dot>Deactivated</Badge>
```

### Phase 7: Modals (90 min)

This is the most complex phase. Each modal needs to be refactored to use DS components.

**Deactivate Modal Example (Lines 1307-1378):**

```tsx
// Before
{showDeactivateModal && deactivateTenant && (
  <div className="fixed inset-0 z-50 flex items-center justify-center">
    <div className="absolute inset-0 bg-black/50" onClick={handleCloseDeactivateModal} />
    <div className="relative bg-surface rounded-xl border border-border shadow-lg w-full max-w-md">
      <div className="p-6">
        {/* ... content ... */}
      </div>
    </div>
  </div>
)}

// After
<Modal open={showDeactivateModal && !!deactivateTenant} onClose={handleCloseDeactivateModal}>
  <ModalBackdrop />
  <ModalContent size="md">
    <ModalHeader>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
          <XMarkIcon className="w-5 h-5 text-red-600" />
        </div>
        <div>
          <ModalTitle>Deactivate Tenant</ModalTitle>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {deactivateTenant?.display_name || deactivateTenant?.name}
          </p>
        </div>
      </div>
    </ModalHeader>
    
    <ModalBody>
      <Alert variant="error" className="mb-4">
        <strong>Warning:</strong> Deactivating this tenant will immediately prevent all users from accessing the platform.
      </Alert>
      
      {deactivateError && (
        <Alert variant="error" className="mb-4">{deactivateError}</Alert>
      )}
      
      <div className="space-y-4">
        <div>
          <Label>Reason for Deactivation *</Label>
          <Textarea
            value={deactivateReason}
            onChange={(e) => setDeactivateReason(e.target.value)}
            placeholder="Please provide a reason..."
            rows={3}
          />
          <p className="text-xs text-gray-500 mt-1">{deactivateReason.length}/10 characters minimum</p>
        </div>
        
        <div>
          <Label>Type DEACTIVATE to confirm *</Label>
          <Input
            value={deactivateConfirmation}
            onChange={(e) => setDeactivateConfirmation(e.target.value)}
            placeholder="DEACTIVATE"
          />
        </div>
      </div>
    </ModalBody>
    
    <ModalFooter>
      <Button variant="outline" onClick={handleCloseDeactivateModal}>
        Cancel
      </Button>
      <Button 
        variant="danger"
        onClick={handleDeactivateTenant}
        disabled={deactivating || deactivateConfirmation !== 'DEACTIVATE' || deactivateReason.length < 10}
      >
        {deactivating && <Spinner size="sm" className="mr-2" />}
        {deactivating ? 'Deactivating...' : 'Deactivate Tenant'}
      </Button>
    </ModalFooter>
  </ModalContent>
</Modal>
```

**Apply similar pattern for:**
- Reactivate Modal (Lines 1380-1438)
- Create Tenant Modal (Lines 1440-1839) - **Largest, most complex**
- Feature Allocation Modal (Lines 1841-1949)

### Phase 8: Color Updates (30 min)

Do a find-and-replace for legacy color classes. Update throughout the file:

```tsx
// Text colors
text-text → text-charcoal dark:text-gray-100
text-muted → text-gray-500 dark:text-gray-400
text-brand → text-eliza-red

// Background colors
bg-surface → bg-white dark:bg-dark-surface
bg-surface-2 → bg-gray-50 dark:bg-dark-surface-2
bg-brand → bg-eliza-red

// Border colors
border-border → border-gray-200 dark:border-dark-border
```

### Phase 9: Table (Keep with DS Styling)

The tenant table uses **expandable rows**, which `DataTable` doesn't support yet. Keep the native HTML table but apply DS styling:

```tsx
<table className="w-full">
  <thead className="bg-gray-50 dark:bg-dark-surface-2">
    <tr>
      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
        Header
      </th>
    </tr>
  </thead>
  <tbody className="divide-y divide-gray-200 dark:divide-dark-border">
    {/* rows */}
  </tbody>
</table>
```

---

## Special Considerations

### 1. Feature Toggle Chips

The feature selection chips (lines 1637-1657, 1884-1906) are a specialized UI pattern. Options:

**Option A: Keep Custom (Recommended)**
They work well and have a unique interaction pattern (toggle on/off with visual feedback). Just update the colors.

**Option B: Use Badge Component**
Could use `Badge` but would need to add toggle behavior.

### 2. Validation States

The form validation (customer ID availability check, field error states) uses custom styling. The DS `Input` component supports an `error` prop:

```tsx
<Input
  error={!!fieldErrors.customer_id}
  // Custom classes for success state if needed
  className={customerIdAvailable === true ? 'border-green-500' : ''}
/>
```

### 3. AdminShell Component

The page uses `AdminShell` which already provides:
- Page header with title, subtitle, icon
- Breadcrumbs
- Sub-navigation
- Actions area

Verify this is DS-compatible or document separately.

### 4. View As Button

The "View As" button (lines 1051-1065) has unique styling (amber color for active state). Consider keeping custom or creating a specialized DS variant.

### 5. Create Modal Scroll

The Create Tenant modal has a sticky header and scrollable body. This should work with `ModalContent` but may need:
```tsx
<ModalContent size="lg" className="max-h-[90vh] overflow-hidden">
  <ModalHeader className="sticky top-0 z-10">...</ModalHeader>
  <ModalBody className="overflow-y-auto">...</ModalBody>
  <ModalFooter className="sticky bottom-0">...</ModalFooter>
</ModalContent>
```

---

## Testing Checklist

After migration, verify:

### Functional Tests

- [ ] Page loads without errors
- [ ] Search filters tenants correctly
- [ ] Tenant rows expand/collapse
- [ ] "View As" button works
- [ ] Cross-tenant toggle works

### Create Tenant Modal

- [ ] Modal opens with default features selected
- [ ] Customer ID validation works (format + uniqueness)
- [ ] Email validation works
- [ ] Feature chips toggle on/off
- [ ] Provider chips toggle on/off
- [ ] Adoption sharing checkboxes work
- [ ] Form submission creates tenant
- [ ] Invite URL displays in success banner
- [ ] Copy invite URL works
- [ ] Modal closes properly

### Deactivate/Reactivate

- [ ] Deactivate modal opens
- [ ] Reason field validates minimum length
- [ ] Confirmation text required
- [ ] Deactivation succeeds
- [ ] Reactivate modal opens
- [ ] Reactivation succeeds

### Feature Allocation Modal

- [ ] Modal opens with current features selected
- [ ] Toggle features on/off
- [ ] Save persists changes

### Admin Edit (Inline)

- [ ] Edit button shows form
- [ ] Save & Send Invite works
- [ ] Cancel reverts form
- [ ] Resend Invite works for pending admins

### Visual Tests

- [ ] Dark mode looks correct
- [ ] Loading states show spinners
- [ ] Error states show alerts
- [ ] Status badges display correctly
- [ ] Buttons have correct hover/focus states
- [ ] Modals have proper backdrop and close behavior

---

## Component Import Reference

```tsx
// Full import list for migrated page
import {
  // Form Components
  Button,
  Input,
  Select,
  SelectOption,
  Textarea,
  Label,
  
  // Feedback
  Alert,
  Badge,
  Spinner,
  
  // Modal
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
} from '../../components/ui';
```

---

## Migration Progress Tracker

| Phase | Description | Est. Time | Status |
|-------|-------------|-----------|--------|
| 1 | Imports & Setup | 15 min | ⬜ Pending |
| 2 | Loading States | 20 min | ⬜ Pending |
| 3 | Alert Banners | 30 min | ⬜ Pending |
| 4 | Form Inputs | 45 min | ⬜ Pending |
| 5 | Buttons | 60 min | ⬜ Pending |
| 6 | Status Badges | 30 min | ⬜ Pending |
| 7 | Modals | 90 min | ⬜ Pending |
| 8 | Color Updates | 30 min | ⬜ Pending |
| 9 | Table Styling | 15 min | ⬜ Pending |
| 10 | Testing | 30 min | ⬜ Pending |

**Total Estimated Time:** 5-6 hours

---

## Notes

- The `AdminShell` component may need its own DS migration analysis
- Consider extracting modal content into separate components for maintainability
- The feature toggle chips could become a reusable `FeatureSelector` DS component in the future
- After migration, add this page to the "Migrated Pages" list in `DESIGN_SYSTEM.md`

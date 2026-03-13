# Admin Management Page - DS Migration Plan

> **Page:** Platform Admin → Platform Settings → Admin Management
> **Path:** `/platform-admin/settings`
> **Source:** `frontend/src/pages/platform-admin/settings/AdminManagementPage.tsx`

---

## Current State Analysis

### Screenshot Reference

![Admin Management Page](./screenshots/admin-management-current.png)

The page displays:
1. **Breadcrumb navigation** - Platform Admin > Platform Settings > Admin Management
2. **Page header** with icon, title, subtitle, and "Add Admin" action button
3. **Section card** - "Platform Admins" with search functionality
4. **Data table** - List of admins with Name, Level, Status, Added date, and delete action
5. **Modal** - Add Admin dialog (not visible in screenshot)

---

## Component Mapping

### Current → DS Component Mapping

| Current Implementation | DS Component | Notes |
|------------------------|--------------|-------|
| `AdminShell` wrapper | Keep (uses DS internally) | Could migrate to `PageHeader` + `PageContent` |
| Native `<button>` (Add Admin) | **`Button`** | `variant="default"` with `PlusIcon` |
| Native `<input>` (search) | **`Input`** | With search icon prefix |
| Custom table `<table>` | **`DataTable`** | Use DS DataTable component |
| Custom status badges | **`Badge`** | `variant="success"` / `variant="danger"` |
| Custom level badge | **`Badge`** | `variant="brand"` |
| Delete button | **`Button`** | `variant="ghost"` + `size="sm"` |
| Modal overlay | **`Modal`** + `ModalBackdrop` | DS Modal components |
| Modal content | **`ModalContent`**, **`ModalHeader`**, **`ModalBody`**, **`ModalFooter`** | Full modal structure |
| Loading spinner | **`Spinner`** | Replace custom `animate-spin` div |
| User avatar circle | **`Avatar`** | DS Avatar component |

### Color Migrations

| Current Class | DS Replacement |
|---------------|----------------|
| `text-text` | `text-charcoal dark:text-gray-100` |
| `text-muted` | `text-gray-500 dark:text-gray-400` |
| `bg-surface` | `bg-white dark:bg-dark-surface` |
| `bg-surface-2` | `bg-gray-50 dark:bg-dark-surface-2` |
| `border-border` | `border-gray-200 dark:border-dark-border` |
| `bg-brand` | `bg-eliza-red` |
| `text-brand` | `text-eliza-red` |
| `bg-success/10 text-success` | `Badge variant="success"` |
| `bg-error/10 text-error` | `Badge variant="danger"` |

---

## Detailed Element Breakdown

### 1. Page Header Section

**Current:**
```tsx
<AdminShell
  title="Admin Management"
  subtitle="Manage platform administrators"
  icon={UsersIcon}
  breadcrumbs={breadcrumbs}
  actions={headerActions}
>
```

**Migration Options:**

**Option A: Keep AdminShell (Recommended)**
AdminShell already provides good structure. Just update the action button:

```tsx
const headerActions = (
  <Button onClick={handleOpenAddModal}>
    <PlusIcon className="w-4 h-4 mr-2" />
    Add Admin
  </Button>
);
```

**Option B: Full DS Migration**
```tsx
<div className="h-full overflow-y-auto bg-gray-50 dark:bg-dark-bg">
  <PageHeader
    title="Admin Management"
    description="Manage platform administrators"
    breadcrumb={<Breadcrumb items={breadcrumbs} />}
    actions={
      <Button onClick={handleOpenAddModal}>
        <PlusIcon className="w-4 h-4 mr-2" />
        Add Admin
      </Button>
    }
    bordered
  />
  <PageContent maxWidth="4xl">
    {/* content */}
  </PageContent>
</div>
```

### 2. Section Card with Search

**Current:**
```tsx
<div className="bg-surface rounded-lg border border-border overflow-hidden">
  <div className="px-4 py-3 flex items-center justify-between border-b border-border bg-surface-2/50">
    <div className="flex items-center gap-3">
      <UsersIcon className="w-5 h-5 text-brand" />
      <div>
        <h2 className="text-base font-medium text-text">Platform Admins</h2>
        <p className="text-xs text-muted">Users with platform-wide administrative access</p>
      </div>
    </div>
    <div className="relative w-48">
      <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
      <input ... />
    </div>
  </div>
```

**DS Migration:**
```tsx
<Card>
  <div className="px-4 py-3 flex items-center justify-between border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
    <SectionHeader
      title="Platform Admins"
      description="Users with platform-wide administrative access"
      icon={<UsersIcon className="h-5 w-5 text-eliza-red" />}
    />
    <div className="relative w-48">
      <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <Input
        placeholder="Search"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="pl-9"
      />
    </div>
  </div>
  {/* Table content */}
</Card>
```

### 3. Data Table

**Current:** Custom HTML table with inline styling

**DS Migration using DataTable:**

```tsx
import { DataTable, Column } from '../../components/ui';

const columns: Column<PlatformAdmin>[] = [
  {
    key: 'user_name',
    header: 'Name',
    render: (admin) => (
      <div className="flex items-center gap-3">
        <Avatar fallback={admin.user_name?.charAt(0) || '?'} size="sm" />
        <div>
          <div className="font-medium text-charcoal dark:text-gray-100 text-sm">
            {admin.user_name || 'Unknown'}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {admin.user_email}
          </div>
        </div>
      </div>
    ),
  },
  {
    key: 'admin_level',
    header: 'Level',
    render: (admin) => (
      <Badge variant="brand" className="capitalize">
        {admin.admin_level}
      </Badge>
    ),
  },
  {
    key: 'is_active',
    header: 'Status',
    render: (admin) => (
      admin.is_active ? (
        <Badge variant="success">
          <span className="w-1.5 h-1.5 bg-green-500 rounded-full mr-1.5" />
          Active
        </Badge>
      ) : (
        <Badge variant="danger">
          <span className="w-1.5 h-1.5 bg-red-500 rounded-full mr-1.5" />
          Inactive
        </Badge>
      )
    ),
  },
  {
    key: 'created_at',
    header: 'Added',
    render: (admin) => (
      <span className="text-sm text-gray-500 dark:text-gray-400">
        {new Date(admin.created_at).toLocaleDateString()}
      </span>
    ),
  },
  {
    key: 'actions',
    header: '',
    render: (admin) => (
      <div className="text-right">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handleRemoveAdmin(admin)}
          className="text-gray-400 hover:text-red-500"
        >
          <TrashIcon className="w-4 h-4" />
        </Button>
      </div>
    ),
  },
];

<DataTable
  columns={columns}
  data={filteredAdmins}
  emptyMessage={searchQuery ? 'No admins match your search' : 'No platform admins yet'}
/>
```

### 4. Add Admin Modal

**Current:** Custom modal with manual overlay

**DS Migration:**
```tsx
import {
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
} from '../../components/ui';

<Modal open={showAddModal} onClose={() => setShowAddModal(false)}>
  <ModalBackdrop />
  <ModalContent>
    <ModalHeader>
      <ModalTitle>Add Platform Admin</ModalTitle>
    </ModalHeader>
    <ModalBody>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Select a user to grant platform administrator access.
      </p>
      
      {/* Search Input */}
      <div className="relative mb-4">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <Input
          placeholder="Search users..."
          value={userSearchQuery}
          onChange={(e) => setUserSearchQuery(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* User List */}
      <div className="max-h-64 overflow-y-auto border border-gray-200 dark:border-dark-border rounded-lg">
        {availableUsers.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 text-sm">
            {userSearchQuery ? 'No users match your search' : 'No users available'}
          </div>
        ) : (
          availableUsers.map((user) => (
            <button
              key={user.id}
              onClick={() => setSelectedUserId(user.id)}
              className={`
                w-full px-4 py-3 flex items-center gap-3 text-left transition-colors
                ${selectedUserId === user.id
                  ? 'bg-eliza-red/10 border-l-2 border-eliza-red'
                  : 'hover:bg-gray-50 dark:hover:bg-dark-surface-2 border-l-2 border-transparent'
                }
              `}
            >
              <Avatar fallback={user.full_name?.charAt(0) || user.username.charAt(0)} size="sm" />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-charcoal dark:text-gray-100 text-sm truncate">
                  {user.full_name || user.username}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {user.email}
                </div>
              </div>
              {user.customer_id && (
                <Badge variant="secondary" className="text-xs">
                  {user.customer_id}
                </Badge>
              )}
            </button>
          ))
        )}
      </div>
    </ModalBody>
    <ModalFooter>
      <Button variant="ghost" onClick={() => setShowAddModal(false)}>
        Cancel
      </Button>
      <Button
        onClick={handleAddAdmin}
        disabled={!selectedUserId || saving}
      >
        {saving && <Spinner size="sm" className="mr-2" />}
        {saving ? 'Adding...' : 'Add as Admin'}
      </Button>
    </ModalFooter>
  </ModalContent>
</Modal>
```

### 5. Loading State

**Current:**
```tsx
<div className="flex items-center justify-center h-64">
  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
</div>
```

**DS Migration:**
```tsx
<div className="flex items-center justify-center h-64">
  <Spinner size="lg" />
</div>
```

---

## Migration Steps

### Phase 1: Import DS Components
```tsx
import {
  Button,
  Input,
  Badge,
  Spinner,
  Card,
  Avatar,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  DataTable,
  Column,
} from '../../components/ui';
```

### Phase 2: Update Header Actions
Replace custom button with DS Button.

### Phase 3: Update Loading State
Replace custom spinner with DS Spinner.

### Phase 4: Migrate Section Card + Search
- Wrap table in Card component
- Replace input with DS Input

### Phase 5: Migrate Data Table
- Replace custom table with DS DataTable
- Define columns with render functions

### Phase 6: Migrate Modal
- Replace custom modal with DS Modal components
- Update form elements

### Phase 7: Update Colors
- Replace all legacy color tokens with DS equivalents

### Phase 8: Final Testing
- [ ] Light mode appearance
- [ ] Dark mode appearance
- [ ] Add admin functionality
- [ ] Remove admin functionality
- [ ] Search filtering
- [ ] Empty states
- [ ] Loading states

---

## Required DS Components

| Component | Import From | Status |
|-----------|-------------|--------|
| `Button` | `ui/button` | ✅ Available |
| `Input` | `ui/input` | ✅ Available |
| `Badge` | `ui/badge` | ✅ Available |
| `Spinner` | `ui/spinner` | ✅ Available |
| `Card` | `ui/card` | ✅ Available |
| `Avatar` | `ui/avatar` | ✅ Available |
| `Modal*` | `ui/modal` | ✅ Available |
| `DataTable` | `ui/data-table` | ✅ Available |
| `SectionHeader` | `ui/page-header` | ✅ Available |

---

## Estimated Effort

| Task | Time Estimate |
|------|---------------|
| Import DS components | 5 min |
| Update header actions button | 5 min |
| Update loading state | 2 min |
| Migrate section card + search | 15 min |
| Migrate data table | 30 min |
| Migrate modal | 20 min |
| Update color tokens | 15 min |
| Testing & polish | 15 min |
| **Total** | **~2 hours** |

---

## Visual Changes Expected

### Before Migration
- Uses legacy color tokens (`text-text`, `bg-surface`, etc.)
- Custom styled table with hover states
- Custom modal implementation
- Brand-colored icons

### After Migration
- Consistent DS color tokens with dark mode support
- DS DataTable with standardized styling
- DS Modal with proper accessibility
- Monochromatic icons following DS guidelines
- DS Badge components for status indicators
- DS Avatar for user icons

---

## Files Affected

| File | Changes |
|------|---------|
| `AdminManagementPage.tsx` | Full component migration |
| No new files required | Uses existing DS components |

---

## Checklist

- [ ] Replace native buttons with `Button` component
- [ ] Replace native inputs with `Input` component
- [ ] Replace custom table with `DataTable`
- [ ] Replace custom modal with `Modal` components
- [ ] Replace custom badges with `Badge` component
- [ ] Replace custom spinner with `Spinner` component
- [ ] Update all color classes to DS tokens
- [ ] Make icons monochromatic (gray) or accent (eliza-red)
- [ ] Verify dark mode appearance
- [ ] Test all interactive functionality
- [ ] Update Page Migration Tracker in DESIGN_SYSTEM.md

---

## Notes

- The `AdminShell` component can be kept as-is since it provides good structure for admin pages
- Consider whether `DataTable` supports all needed features (the current table is simple, so it should work)
- The user selection list in the modal could potentially use a DS component, but the custom styling with selection state is reasonable
- Badge variants to use: `brand` for level, `success`/`danger` for status

# Frontend Implementation

## ✅ **COMPLETED**

### **Files Created (2)**

1. **`frontend/src/components/business-intelligence/CompanySelector.tsx`**
   - Company selector dropdown component
   - Shows accessible companies with employee counts
   - Displays default company
   - Auto-selects default on mount
   - Real-time permission checks

2. **`frontend/src/pages/admin/AdminSettingsPage.tsx`**
   - Admin settings management page
   - Default company configuration
   - View all system settings
   - View all companies with data
   - Edit/save functionality

### **Files Modified (5)**

1. **`frontend/src/components/business-intelligence/QuestionInput.tsx`**
   - Added `companyHrDataset` prop
   - Passes company to API when submitting questions

2. **`frontend/src/pages/business-intelligence/BusinessIntelligenceQA.tsx`**
   - Added `selectedCompany` state
   - Integrated CompanySelector component
   - Passes selected company to QuestionInput

3. **`frontend/src/lib/query-keys.ts`**
   - Added `companies` query keys
   - Added `settings` query keys

4. **`frontend/src/services/api-client.ts`**
   - Added `getCompaniesApi()` helper
   - Added `getSettingsApi()` helper

5. **`frontend/src/App.tsx`**
   - Added route for AdminSettingsPage at `/admin/settings`
   - Protected with `settings:read` permission

---

## 🎨 **Component Details**

### **CompanySelector Component**

**Features:**
- Fetches accessible companies from `/v1/companies/accessible`
- Fetches default company from `/v1/settings/default/company_hr_dataset`
- Auto-selects default company if no selection
- Shows employee count for each company
- Displays access status (accessible/restricted)
- Visual indicator for selected company
- Responsive dropdown UI

**Usage:**
```tsx
<CompanySelector 
  value={selectedCompany}
  onChange={setSelectedCompany}
  showDefault={true}
/>
```

**Props:**
- `value`: Currently selected company ID (string | null)
- `onChange`: Callback when selection changes
- `showDefault`: Whether to show default company option
- `className`: Optional CSS classes

---

### **Admin Settings Page**

**Sections:**

#### **1. Default Company Configuration**
- View current default company
- Edit/change default company
- Select from dropdown of available companies
- Save/cancel functionality
- Loading states during save

#### **2. All System Settings Table**
- Lists all system settings
- Displays key, value, type, description
- Read-only view

#### **3. Available Companies Table**
- Lists all companies with HR data
- Shows employee count per company
- Displays default company badge
- Shows access status (accessible/restricted)

**Permissions Required:**
- `settings:read` - View settings page
- `settings:write` - Modify settings (enforced by API)

**Route:** `/admin/settings`

---

## 🔄 **Data Flow**

### **BI Question Submission with Company Selection**

```
User visits BI page
  ↓
CompanySelector loads accessible companies
  ↓
Fetches default from /v1/settings/default/company_hr_dataset
  ↓
Auto-selects default (e.g., "caylent")
  ↓
User can change selection or keep default
  ↓
User types question
  ↓
Clicks Submit
  ↓
QuestionInput receives companyHrDataset prop
  ↓
POST /v1/bi/questions
  {
    "question": "What are the top skills?",
    "company_hr_dataset": "caylent"
  }
  ↓
Backend processes with selected company
```

### **Admin Settings Update**

```
Admin visits /admin/settings
  ↓
Page loads current settings
  ↓
Displays default company (e.g., "caylent")
  ↓
Admin clicks "Change"
  ↓
Dropdown shows all companies
  ↓
Admin selects new company (e.g., "eliza")
  ↓
Clicks "Save"
  ↓
PUT /v1/settings/default/company_hr_dataset?company_id=eliza
  ↓
Backend updates setting
  ↓
Success toast shown
  ↓
Page refreshes data
```

---

## 🎯 **Key Features**

### **User Experience**

✅ **Intuitive Selection**: Clear dropdown with company names and employee counts  
✅ **Visual Feedback**: Selected company highlighted with check icon  
✅ **Default Handling**: Auto-selects system default for convenience  
✅ **Real-time Updates**: Settings page refreshes after changes  
✅ **Permission-aware**: Only shows companies user can access  

### **Admin Experience**

✅ **Easy Configuration**: Simple edit/save workflow  
✅ **Comprehensive View**: See all settings and companies  
✅ **Status Indicators**: Visual badges for default/accessible  
✅ **Error Handling**: Clear error messages on failures  

---

## 📱 **UI Components**

### **CompanySelector UI**

```
┌─────────────────────────────────────┐
│ 🏢 Select Company                   │
├─────────────────────────────────────┤
│ [Dropdown: caylent (150 employees)] │✓
├─────────────────────────────────────┤
│ Analyzing data from caylent         │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │  caylent      150 employees     │ │
│ │  ✓ You have access              │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### **Admin Settings Page UI**

```
┌────────────────────────────────────────────┐
│ ⚙️  System Settings                        │
│ Configure system-wide settings and defaults│
├────────────────────────────────────────────┤
│ 🏢 Default Company for HR Queries          │
│ ┌────────────────────────────────────────┐ │
│ │  caylent ✓         [Change] button    │ │
│ │  Current default company               │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ All System Settings                        │
│ ┌────────────────────────────────────────┐ │
│ │ Key              | Value  | Type       │ │
│ │ default_company  | caylent| string     │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ Available Companies                        │
│ ┌────────────────────────────────────────┐ │
│ │ caylent [Default] | 150    | ✓Access  │ │
│ │ eliza             | 75     | ✓Access  │ │
│ └────────────────────────────────────────┘ │
└────────────────────────────────────────────┘
```

---

## 🧪 **Testing Guide**

### **Test 1: Company Selection on BI Page**

1. Navigate to `/business-intelligence`
2. Observe company selector loads with default
3. Change company selection
4. Submit a question
5. Verify question uses selected company

### **Test 2: Admin Settings Configuration**

1. Navigate to `/admin/settings` (as admin)
2. View current default company
3. Click "Change"
4. Select different company from dropdown
5. Click "Save"
6. Verify success message
7. Verify default updated in UI

### **Test 3: Permission Enforcement**

1. Log in as non-admin user
2. Try to access `/admin/settings`
3. Verify access denied (403)
4. Log in as admin
5. Verify access granted

### **Test 4: Default Behavior**

1. Navigate to BI page without selecting company
2. Verify default company auto-selected
3. Submit question without changing selection
4. Verify question uses default company

---

## 🔐 **Permission Requirements**

| Page | Permission | Purpose |
|------|-----------|---------|
| BI Page | `bi:write` | Submit questions |
| Company Selector | `hr:read:company:*` or specific | View companies |
| Admin Settings | `settings:read` | View settings |
| Admin Settings (Edit) | `settings:write` | Modify settings |

---

## 📊 **API Integration**

### **Endpoints Used**

```typescript
// Companies
GET  /v1/companies/accessible          // Get user's accessible companies
GET  /v1/companies                     // Get all companies (admin)

// Settings
GET  /v1/settings                      // Get all settings
GET  /v1/settings/default/company_hr_dataset   // Get default company
PUT  /v1/settings/default/company_hr_dataset   // Update default company

// BI Questions
POST /v1/bi/questions                  // Submit question with company
```

### **Request/Response Examples**

**Submit BI Question:**
```typescript
POST /v1/bi/questions
{
  "question": "What are the top skills?",
  "company_hr_dataset": "caylent"  // NEW: Selected company
}

Response: {
  "question_id": "q_abc123",
  "status": "pending",
  "message": "Question submitted successfully"
}
```

**Update Default Company:**
```typescript
PUT /v1/settings/default/company_hr_dataset?company_id=eliza

Response: {
  "setting_key": "default_company_hr_dataset",
  "value": "eliza",
  "message": "Default company set to 'eliza'"
}
```

---

## ✅ **Summary**

### **What's Been Built**

1. ✅ Company selector component for BI page
2. ✅ Admin settings page with full CRUD
3. ✅ Integration with backend APIs
4. ✅ Permission-based access control
5. ✅ Real-time updates and caching
6. ✅ Error handling and loading states
7. ✅ Responsive UI with Tailwind CSS

### **User Benefits**

- **Easy Company Selection**: Intuitive dropdown on every BI question
- **Smart Defaults**: System remembers default company
- **Admin Control**: Centralized settings management
- **Visual Feedback**: Clear indicators for status and permissions
- **Fast Performance**: Query caching for responsive UX

---

**Frontend implementation is complete and ready for deployment!**


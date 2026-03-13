# Multi-Tenant Architecture Analysis & Proposal

## 🎯 **Problem Statement**

The application currently **conflates** two distinct concepts:

1. **User's Organization** (who is logged in) - e.g., "eliza"
2. **Data Being Analyzed** (whose data to query) - e.g., "caylent" HR data

This creates a critical architectural flaw: **A user from Organization A cannot analyze data from Organization B**, even if they should have permission to do so (e.g., consultants, holding companies, service providers).

---

## 📊 **Current Architecture (Problematic)**

### **Data Flow:**
```
User Logs In
    ↓
CurrentUserContext.customer_id = "eliza"
    ↓
Submit BI Question
    ↓
process_bi_question(customer_id="eliza")
    ↓
HRDatabaseTool(customer_id="eliza")  ← FILTERS HR DATA
    ↓
Query: SELECT * FROM hr_employees WHERE customer_id = "eliza"
    ↓
Result: NO DATA (HR data is for "caylent")
```

### **Key Issues Identified:**

#### **1. Tight Coupling in Authentication**
- **File**: `src/core/auth_context.py`
- **Issue**: `CurrentUserContext.customer_id` represents the user's organization
- **Problem**: This is used as the filter for ALL data queries

#### **2. HR Tools Use User's customer_id**
- **Files**: 
  - `src/crewai_custom_tools.py` (line 143)
  - `src/crewai_custom_tools/hr_database_tool.py` (line 71)
  - `src/crewai_flows/data_analysis_flow.py` (line 100-102)
- **Code**:
  ```python
  hr_tool = HRDatabaseTool(customer_id=self.state.customer_id)
  query = db.query(Employee).filter(Employee.customer_id == self.customer_id)
  ```
- **Problem**: Tools are hard-coded to filter by the authenticated user's customer_id

#### **3. Document Search Uses User's customer_id**
- **File**: `src/crewai_custom_tools/document_search_tool.py`
- **Code**:
  ```python
  doc_tool = DocumentSearchTool(
      customer_id=self.state.customer_id,  # User's organization
      limit=10,
      similarity_threshold=0.7
  )
  ```
- **Problem**: Documents are also filtered by user's organization

#### **4. Connectivity Checks Assume Single Customer**
- **File**: `src/services/connectivity_service.py` (line 136)
- **Code**:
  ```python
  Employee.customer_id == customer_id
  ```
- **Problem**: Checks if user's customer has HR data, not the target dataset

#### **5. API Endpoints Hardcode customer_id**
- **File**: `src/api/routes/hr.py` (lines 609, 648)
- **Code**:
  ```python
  customer_id: str = Query("caylent", description="Customer ID to query HR data for")
  ```
- **Problem**: Default is hardcoded, should be a selectable parameter

---

## 🏗️ **Proposed Architecture (Multi-Tenant)**

### **Core Concept: Separate User Identity from Data Scope**

```
User Identity (Authentication)
    ↓
user.customer_id = "eliza"         ← WHO you are
user.permissions = ["hr:read:*"]   ← WHAT you can do
    ↓
BI Question Submission
    ↓
target_dataset = "caylent"          ← WHOSE data to analyze
    ↓
Authorization Check:
    - Does user have permission "hr:read:caylent"?
    - Or does user have wildcard "hr:read:*"?
    ↓
process_bi_question(
    user_customer_id="eliza",
    target_dataset="caylent"
)
    ↓
HRDatabaseTool(customer_id="caylent")
    ↓
Query: SELECT * FROM hr_employees WHERE customer_id = "caylent"
    ↓
Result: ✅ Returns Caylent employee data
```

---

## 🔧 **Proposed Changes**

### **Phase 1: Add Target Dataset Parameter**

#### **1.1 Update BIQuestion Model**
- **File**: `src/models/business_intelligence.py`
- **Change**: Add `target_customer_id` field

```python
class BIQuestion(Base):
    # ... existing fields ...
    customer_id = Column(String(100), nullable=False)  # WHO asked (user's org)
    target_customer_id = Column(String(100), nullable=True)  # WHOSE data to analyze
    # If target_customer_id is None, defaults to customer_id (backward compatible)
```

#### **1.2 Update API Endpoint**
- **File**: `src/api/routes/business_intelligence.py`
- **Change**: Accept optional `target_customer_id`

```python
@router.post("/questions")
async def submit_question(
    request: SubmitQuestionRequest,
    target_customer_id: Optional[str] = None,  # NEW PARAMETER
    current_user: CurrentUserContext = Depends(get_current_user)
):
    # Authorization: Check if user can query this target
    if target_customer_id and target_customer_id != current_user.customer_id:
        # Check permission: "hr:read:{target_customer_id}" or "hr:read:*"
        required_permission = f"hr:read:{target_customer_id}"
        if not (current_user.has_permission(required_permission) or 
                current_user.has_permission("hr:read:*")):
            raise HTTPException(403, "Access denied to target customer data")
    
    # Use target or default to user's customer
    effective_target = target_customer_id or current_user.customer_id
```

#### **1.3 Update Celery Task**
- **File**: `src/tasks/business_intelligence_tasks.py`
- **Change**: Pass both user's customer_id AND target_customer_id

```python
@celery_app.task(name="process_bi_question")
def process_bi_question(
    self, 
    question_id: str, 
    user_id: int, 
    user_customer_id: str,        # WHO is asking
    target_customer_id: str        # WHOSE data to analyze
) -> Dict[str, Any]:
    # Use target_customer_id for data queries
    hr_tool = HRDatabaseTool(customer_id=target_customer_id)
    doc_tool = DocumentSearchTool(customer_id=target_customer_id)
```

### **Phase 2: Update Tools and Services**

#### **2.1 HR Database Tool**
- **Files**: 
  - `src/crewai_custom_tools.py`
  - `src/crewai_custom_tools/hr_database_tool.py`
- **Change**: Already parameterized, just need to pass correct customer_id

```python
# ALREADY CORRECT - Just needs right parameter:
hr_tool = HRDatabaseTool(customer_id=target_customer_id)  # Not user's customer_id
```

#### **2.2 Document Search Tool**
- **File**: `src/crewai_custom_tools/document_search_tool.py`
- **Change**: Same as HR tool

```python
doc_tool = DocumentSearchTool(
    customer_id=target_customer_id,  # Not user's customer_id
    limit=10,
    similarity_threshold=0.7
)
```

#### **2.3 Connectivity Service**
- **File**: `src/services/connectivity_service.py`
- **Change**: Check target customer's data, not user's

```python
def check_hr_database_connectivity(self, target_customer_id: str):
    # Check if TARGET customer has HR data
    has_data = db.query(Employee).filter(
        Employee.customer_id == target_customer_id  # Not user's customer_id
    ).first() is not None
```

#### **2.4 HR API Endpoints**
- **File**: `src/api/routes/hr.py`
- **Change**: Make customer_id a required, authorized parameter

```python
@router.get("/tables")
async def get_hr_tables_list(
    target_customer_id: str = Query(..., description="Customer ID to query HR data for"),
    current_user = Depends(auth_middleware.require_permission("hr:read"))
):
    # Authorization check
    if target_customer_id != current_user.customer_id:
        required_permission = f"hr:read:{target_customer_id}"
        if not (current_user.has_permission(required_permission) or 
                current_user.has_permission("hr:read:*")):
            raise HTTPException(403, "Access denied to target customer data")
    
    # Query with target customer
    return await hr_service.get_tables(customer_id=target_customer_id)
```

### **Phase 3: Update RBAC System**

#### **3.1 Add Resource-Scoped Permissions**
- **File**: `scripts/init_rbac_data.py`
- **Change**: Add granular permissions

```python
# Current (coarse):
"hr:read" - Can read HR data

# Proposed (granular):
"hr:read:*"           - Can read ALL customer HR data (super admin)
"hr:read:caylent"     - Can read Caylent HR data only
"hr:read:acme"        - Can read ACME HR data only
```

#### **3.2 Update Permission Checks**
- **File**: `src/middleware/authorization.py`
- **Change**: Support resource-scoped permissions

```python
def check_resource_permission(
    user: CurrentUserContext, 
    action: str, 
    resource: str, 
    resource_id: str
) -> bool:
    """
    Check if user has permission for specific resource.
    
    Examples:
        check_resource_permission(user, "hr:read", "customer", "caylent")
        - Checks: "hr:read:caylent" OR "hr:read:*"
    """
    specific_perm = f"{action}:{resource_id}"
    wildcard_perm = f"{action}:*"
    
    return user.has_permission(specific_perm) or user.has_permission(wildcard_perm)
```

### **Phase 4: Update Frontend**

#### **4.1 Add Dataset Selector**
- **File**: `frontend/src/pages/business-intelligence/BusinessIntelligenceQA.tsx`
- **Change**: Add dropdown to select target customer

```typescript
// New state
const [targetCustomer, setTargetCustomer] = useState<string>(currentUser.customer_id);

// New UI component
<FormControl>
  <FormLabel>Analyze Data For:</FormLabel>
  <Select value={targetCustomer} onChange={(e) => setTargetCustomer(e.target.value)}>
    <option value={currentUser.customer_id}>My Organization ({currentUser.customer_id})</option>
    {/* If user has wildcard permission, show all customers */}
    {availableCustomers.map(customer => (
      <option key={customer.id} value={customer.id}>{customer.name}</option>
    ))}
  </Select>
</FormControl>

// Modified submission
const handleSubmit = async () => {
  await submitQuestion({
    question: questionText,
    target_customer_id: targetCustomer  // NEW PARAMETER
  });
};
```

#### **4.2 Add Customer Management API**
- **File**: `src/api/routes/customers.py` (new)
- **Purpose**: List available customers for selection

```python
@router.get("/customers/available")
async def get_available_customers(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Get list of customers this user can query data for.
    """
    # If user has wildcard permission, return all customers
    if current_user.has_permission("hr:read:*"):
        return await customer_service.list_all_customers()
    
    # Otherwise, return only their own customer + explicitly granted ones
    accessible_customers = [current_user.customer_id]
    
    # Parse permissions to find customer-specific grants
    for perm in current_user.permissions:
        if perm.startswith("hr:read:") and perm != "hr:read:*":
            customer_id = perm.split(":")[-1]
            accessible_customers.append(customer_id)
    
    return await customer_service.get_customers(accessible_customers)
```

---

## 📋 **Migration Plan**

### **Step 1: Database Migration**
```sql
-- Add new column to bi_questions
ALTER TABLE bi_questions 
ADD COLUMN target_customer_id VARCHAR(100);

-- Backfill existing records (default to user's customer)
UPDATE bi_questions 
SET target_customer_id = customer_id 
WHERE target_customer_id IS NULL;
```

### **Step 2: Update Permissions**
```sql
-- Grant existing users wildcard or specific access
-- Example: Give scott@eliza.com access to all customers
INSERT INTO user_permissions (user_id, permission)
SELECT id, 'hr:read:*' FROM users WHERE email = 'scott@eliza.com';

-- Example: Give consultants access to specific customers
INSERT INTO user_permissions (user_id, permission)
VALUES 
  (consultant_user_id, 'hr:read:caylent'),
  (consultant_user_id, 'hr:read:acme');
```

### **Step 3: Backward Compatibility**
- If `target_customer_id` is not provided, default to `user.customer_id`
- Existing API calls continue to work
- Gradually migrate to explicit target selection

---

## ✅ **Benefits**

1. **True Multi-Tenancy**: Users can analyze data across multiple organizations
2. **Flexible Access Control**: Granular permissions per customer dataset
3. **Enterprise Ready**: Supports holding companies, consultants, MSPs
4. **Backward Compatible**: Existing single-tenant usage still works
5. **Clear Separation**: User identity != Data scope
6. **Audit Trail**: Know WHO analyzed WHOSE data

---

## 🚨 **Security Considerations**

### **Authorization Layers:**
```
Layer 1: Authentication
├── Is user logged in?
├── Is user active?
└── Is session valid?

Layer 2: Permission Check
├── Does user have "hr:read" base permission?
├── Does user have "hr:read:{target_customer}" specific permission?
└── OR does user have "hr:read:*" wildcard permission?

Layer 3: Data Filtering
├── Query filters by target_customer_id
├── Results are from authorized dataset
└── Audit log records access
```

### **Audit Logging:**
```python
# Log every data access with:
audit_log.record(
    user_id=current_user.id,
    user_customer_id=current_user.customer_id,
    target_customer_id=target_customer_id,
    action="hr_query",
    resource_type="hr_employees",
    timestamp=datetime.utcnow()
)
```

---

## 📊 **Use Cases Enabled**

### **1. Holding Company**
```
Eliza Corp (Parent)
├── Subsidiary A (Caylent)
├── Subsidiary B (TechCo)
└── Subsidiary C (ConsultCo)

Eliza admin can:
- Analyze Caylent HR data
- Analyze TechCo HR data
- Compare across subsidiaries
```

### **2. Consulting Firm**
```
Consultant from Acme Consulting
├── Permission: "hr:read:client1"
├── Permission: "hr:read:client2"
└── Permission: "hr:read:client3"

Can analyze client data without being part of client's organization
```

### **3. Service Provider**
```
HR Analytics SaaS
├── Customer 1: Retail Corp
├── Customer 2: Manufacturing Inc
└── Customer 3: Tech Startup

Platform users can switch between customer datasets
```

---

## 🎯 **Implementation Priority**

### **HIGH PRIORITY (Core Functionality)**
1. ✅ Update `BIQuestion` model with `target_customer_id`
2. ✅ Update API endpoint to accept `target_customer_id`
3. ✅ Update Celery task parameter passing
4. ✅ Update tool initialization with correct customer_id
5. ✅ Add authorization checks

### **MEDIUM PRIORITY (Enhanced Security)**
6. ✅ Add resource-scoped permissions
7. ✅ Update permission checking logic
8. ✅ Add audit logging

### **LOW PRIORITY (UX Improvements)**
9. ✅ Add frontend dataset selector
10. ✅ Add customer list API
11. ✅ Update UI to show which dataset is being analyzed

---

## 📝 **Summary**

### **Current State:**
- ❌ User's `customer_id` = Data `customer_id` (tightly coupled)
- ❌ Cannot analyze cross-customer data
- ❌ HR data must match user's organization

### **Proposed State:**
- ✅ User's `customer_id` = Authentication (who you are)
- ✅ `target_customer_id` = Authorization + Data Scope (what you can access)
- ✅ Flexible multi-tenant architecture
- ✅ Backward compatible

### **Files Requiring Changes:**
1. `src/models/business_intelligence.py` - Add `target_customer_id` field
2. `src/api/routes/business_intelligence.py` - Accept target parameter
3. `src/tasks/business_intelligence_tasks.py` - Pass target to tools
4. `src/crewai_flows/data_analysis_flow.py` - Use target in tool init
5. `src/services/connectivity_service.py` - Check target customer
6. `src/api/routes/hr.py` - Authorize target access
7. `src/middleware/authorization.py` - Resource-scoped permissions
8. `frontend/src/pages/business-intelligence/` - UI selector
9. Database migration - Add column
10. RBAC seed data - Add granular permissions

---

## 🤔 **Questions for Review**

1. **Naming**: Should we use `target_customer_id` or `dataset_id` or `hr_dataset_customer_id`?
2. **Default Behavior**: When `target_customer_id` is omitted, default to user's customer or require explicit selection?
3. **Permission Model**: Use `hr:read:*` wildcard or explicitly grant each customer?
4. **Migration**: Big bang or gradual rollout?
5. **Frontend**: Auto-select user's customer or force explicit choice?
6. **Audit**: Log all cross-customer queries or only flagged ones?

---

## ✅ **Next Steps (Pending Your Approval)**

Please review this proposal and let me know:
1. ✅ Do you approve this architectural approach?
2. 🤔 Any concerns or modifications needed?
3. 🎯 Which priority level should we implement? (High only, Medium, or Full)
4. 📝 Any specific naming preferences?
5. 🚀 Should we proceed with implementation?

**I will NOT make any changes until you approve this plan.** 🛑


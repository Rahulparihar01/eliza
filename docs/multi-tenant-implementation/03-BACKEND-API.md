# Backend API Updates

## ✅ **COMPLETED**

### **Files Modified:**
1. `src/api/schemas/business_intelligence.py`
2. `src/api/routes/business_intelligence.py`
3. `src/services/business_intelligence_service.py`
4. `src/services/settings_service.py` (new)

---

## **1. Request Schema Update**

### **File:** `src/api/schemas/business_intelligence.py`

Added `company_hr_dataset` field:

```python
class QuestionSubmitRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=5000)
    company_hr_dataset: Optional[str] = Field(
        None, 
        description="Target company for HR data analysis (defaults to system setting if omitted)"
    )
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

**Example Request:**
```json
{
  "question": "What are the top skills in Engineering?",
  "company_hr_dataset": "caylent",
  "session_id": "session_123"
}
```

---

## **2. Settings Service**

### **File:** `src/services/settings_service.py` (NEW)

Created comprehensive settings management service:

```python
class SettingsService:
    def get_setting_value(self, key: str, default: Any = None) -> Any
    def set_setting(self, key: str, value: Any, ...) -> SystemSetting
    def delete_setting(self, key: str) -> bool
    def get_default_company_hr_dataset(self) -> str
    def set_default_company_hr_dataset(self, company_id: str) -> SystemSetting
```

**Key Features:**
- Type-safe value retrieval (string, int, bool, json)
- CRUD operations for settings
- Convenience methods for common settings
- Defaults to 'caylent' if not configured

---

## **3. BI Service Update**

### **File:** `src/services/business_intelligence_service.py`

Updated `create_question()` method:

```python
def create_question(
    self,
    user_id: int,
    customer_id: str,  # User's organization
    question: str,
    company_hr_dataset: Optional[str] = None,  # NEW: Target company
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> BIQuestion:
```

**Changes:**
- Accepts `company_hr_dataset` parameter
- Stores in database
- Logs company selection

---

## **4. API Endpoint Update**

### **File:** `src/api/routes/business_intelligence.py`

Updated `/v1/bi/questions` POST endpoint with multi-step logic:

### **Step 1: Determine Target Company**

```python
settings_service = SettingsService(db)
company_hr_dataset = request.company_hr_dataset

if not company_hr_dataset:
    # Use system default if not specified
    company_hr_dataset = settings_service.get_default_company_hr_dataset()
```

### **Step 2: Authorization Check**

```python
if not auth_middleware.check_company_access(current_user, company_hr_dataset):
    raise HTTPException(
        status_code=403,
        detail=f"You do not have permission to access data from company '{company_hr_dataset}'"
    )
```

### **Step 3: Create Question & Enqueue**

```python
question = bi_service.create_question(
    user_id=current_user.user_id,
    customer_id=current_user.customer_id,
    company_hr_dataset=company_hr_dataset,  # NEW
    question=request.question,
    ...
)

process_bi_question.delay(
    question_id=question.question_id,
    user_id=current_user.user_id,
    customer_id=current_user.customer_id,
    company_hr_dataset=company_hr_dataset  # NEW
)
```

---

## **🔐 Security Flow**

```
User submits question
   ↓
Extract/default company_hr_dataset
   ↓
Check permissions
   ├─ Has hr:read:company:*? → Allow
   ├─ Has hr:read:company:{company}? → Allow
   └─ Otherwise → 403 Forbidden
   ↓
Create question with company context
   ↓
Enqueue for processing
```

---

## **📊 Request Flow Examples**

### **Example 1: User specifies company**
```json
POST /v1/bi/questions
{
  "question": "What are the top skills?",
  "company_hr_dataset": "caylent"
}
```
- Checks permission for `caylent`
- Uses `caylent` data

### **Example 2: User omits company**
```json
POST /v1/bi/questions
{
  "question": "What are the top skills?"
}
```
- Looks up system default (e.g., `caylent`)
- Checks permission for default
- Uses default company data

### **Example 3: Unauthorized**
```json
POST /v1/bi/questions
{
  "question": "What are the top skills?",
  "company_hr_dataset": "eliza"
}
```
- User only has `hr:read:company:caylent`
- **Returns 403 Forbidden**
- Logs audit event

---

## **✅ What's Working**

1. ✅ API accepts `company_hr_dataset` parameter
2. ✅ Defaults to system setting if omitted
3. ✅ Enforces company-scoped permissions
4. ✅ Passes company context to Celery task
5. ✅ Stores company selection in database
6. ✅ Logs all authorization decisions

---

## **🔜 Next Steps**

- Update Celery task to use `company_hr_dataset`
- Update CrewAI flows to pass company to tools
- Update tools to query specific company data


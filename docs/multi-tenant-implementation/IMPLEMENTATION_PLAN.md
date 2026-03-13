# Multi-Tenant Implementation Plan

## 🎯 **Naming Conventions**

Based on "company" terminology:

- **Database Column**: `company_hr_dataset` - The company whose HR data to analyze
- **API Parameter**: `company_hr_dataset` - Target company for query
- **Permission Format**: `hr:read:company:{company_id}` or `hr:read:company:*`
- **Setting Key**: `default_company_hr_dataset` - System default company
- **Frontend Variable**: `selectedCompany` - User's selected company

---

## 📋 **Implementation Checklist**

### ✅ **Phase 1: Database & Models** (Steps 1-3)
- [ ] 1. Create Alembic migration for `company_hr_dataset` column
- [ ] 2. Create `SystemSettings` model for admin configuration
- [ ] 3. Update `BIQuestion` model with new field

### ✅ **Phase 2: Authorization** (Steps 4-5)
- [ ] 4. Add company-scoped permissions to RBAC schema
- [ ] 5. Update authorization middleware for resource checking

### ✅ **Phase 3: Backend Logic** (Steps 6-10)
- [ ] 6. Update BI API endpoint to accept `company_hr_dataset`
- [ ] 7. Update Celery task signature and parameter passing
- [ ] 8. Update CrewAI flows to use `company_hr_dataset`
- [ ] 9. Update connectivity service to check target company
- [ ] 10. Update HR API endpoints with authorization

### ✅ **Phase 4: Admin Features** (Steps 11-12)
- [ ] 11. Create admin settings API and service
- [ ] 12. Create companies list API endpoint

### ✅ **Phase 5: Frontend** (Steps 13-14)
- [ ] 13. Add company selector to BI question page
- [ ] 14. Create admin settings page for default company

### ✅ **Phase 6: Data & Testing** (Steps 15-16)
- [ ] 15. Update seed data with company-scoped permissions
- [ ] 16. End-to-end testing with cross-company queries

---

## 🚀 **Let's Begin!**


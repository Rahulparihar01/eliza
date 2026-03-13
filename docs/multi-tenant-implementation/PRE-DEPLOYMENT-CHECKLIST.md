# Pre-Deployment Checklist

## ⚠️ **Important Considerations Before Deploying**

### **1. Frontend API Type Generation** 🔴 CRITICAL

The backend has new API endpoints that the frontend needs to know about:
- `/v1/settings/*` - Settings API
- `/v1/companies/*` - Companies API
- Updated `/v1/bi/questions` schema (with `company_hr_dataset`)

**Action Required:**
```bash
# After backend is deployed, regenerate frontend API types
cd frontend
npm run generate-api  # or whatever your orval/openapi-generator command is
```

**Note**: The frontend code I created assumes these types exist. You may see TypeScript errors until types are regenerated.

---

### **2. Current System State Check** 🟡 RECOMMENDED

**Check Docker status:**
```bash
# Verify containers are running
docker ps | grep -E "(app|celery|postgres)"

# Check current database state
docker exec docker-app-1 python -m alembic current
```

**Expected**: Should show current revision (likely `7d0d11d0c3fc` or earlier)

---

### **3. Backup Current State** 🟡 RECOMMENDED

**Backup database:**
```bash
# Create database dump before migrations
docker exec docker-postgres-1 pg_dump -U postgres ai_enablement > backup_before_multitenant_$(date +%Y%m%d_%H%M%S).sql
```

**Backup vector indexes:**
```bash
# Backup existing FAISS indexes
docker exec docker-app-1 tar -czf /tmp/vectors_backup.tar.gz /app/data/vectors/
docker cp docker-app-1:/tmp/vectors_backup.tar.gz ./vectors_backup_$(date +%Y%m%d_%H%M%S).tar.gz
```

---

### **4. Frontend Build Consideration** 🟡 RECOMMENDED

The deployment script only handles backend. Frontend needs separate handling:

**Option A: Deploy frontend after backend**
```bash
# 1. Run backend deployment
./deploy-multi-tenant.sh

# 2. Regenerate API types
cd frontend
npm run generate-api

# 3. Fix any TypeScript errors
npm run build

# 4. Restart frontend container (if using Docker)
docker-compose restart frontend
```

**Option B: Skip frontend for now**
- Deploy backend first
- Test backend APIs manually
- Deploy frontend in a separate step

---

### **5. Migration Strategy** 🟢 INFO

The deployment will run TWO migrations:
1. `7d0d11d0c3fc` - Adds `company_hr_dataset` to BI questions + system_settings table
2. `8e1e22f1d4ab` - Adds `company_hr_dataset` to documents

**These migrations are safe:**
- ✅ Add new columns (nullable, with defaults)
- ✅ Create new tables
- ✅ Backfill existing data
- ✅ Add indexes
- ❌ No data deletion
- ❌ No column removals

---

### **6. Dependencies Check** 🟢 INFO

**No new Python packages required** - All changes use existing dependencies.

**Frontend might need:**
```bash
cd frontend
npm install  # In case any packages were added
```

---

### **7. Testing Plan** 🟡 RECOMMENDED

**After deployment, test in this order:**

1. **Backend APIs** (manual testing)
   ```bash
   # Test settings API
   curl -X GET http://localhost:5001/v1/settings \
     -H "Authorization: Bearer $TOKEN"
   
   # Test companies API
   curl -X GET http://localhost:5001/v1/companies/accessible \
     -H "Authorization: Bearer $TOKEN"
   ```

2. **Database state**
   ```bash
   # Verify migrations applied
   docker exec docker-app-1 python -m alembic current
   
   # Verify new tables
   docker exec docker-postgres-1 psql -U postgres ai_enablement \
     -c "\dt system_settings"
   ```

3. **Frontend** (after regenerating types and rebuilding)
   - Visit `/business-intelligence`
   - Check for company selector
   - Visit `/admin/settings` (as admin)

---

### **8. Rollback Plan** 🟡 RECOMMENDED

If something goes wrong:

**Rollback migrations:**
```bash
# Rollback both migrations
docker exec docker-app-1 python -m alembic downgrade -1  # Rollback documents migration
docker exec docker-app-1 python -m alembic downgrade -1  # Rollback BI migration
```

**Restore from backup:**
```bash
# Restore database
docker exec -i docker-postgres-1 psql -U postgres ai_enablement < backup_before_multitenant_*.sql

# Restore vector indexes
docker cp vectors_backup_*.tar.gz docker-app-1:/tmp/
docker exec docker-app-1 tar -xzf /tmp/vectors_backup_*.tar.gz -C /
```

**Restore old code:**
```bash
# Git has all the old versions, just reset if needed
git status
git diff  # Review changes
# If needed: git checkout -- <files>
```

---

### **9. Downtime Considerations** 🟢 INFO

**Expected downtime:** ~2-3 minutes
- Service restart: ~30 seconds
- Migration execution: ~10 seconds
- Cache warming: ~30 seconds

**Zero-downtime option:**
- Run migrations first (while app is running - they're additive)
- Then hot-reload code without full restart
- But current script does full restart (safer)

---

### **10. Environment Variables** 🟢 INFO

**No new environment variables required.**

All new settings are stored in database (`system_settings` table).

---

## ✅ **Pre-Deployment Commands to Run**

```bash
# 1. Check current state
echo "=== Current Container Status ==="
docker ps | grep -E "(app|celery|postgres)"

echo -e "\n=== Current Migration ==="
docker exec docker-app-1 python -m alembic current

# 2. Create backups (RECOMMENDED)
echo -e "\n=== Creating Backups ==="
docker exec docker-postgres-1 pg_dump -U postgres ai_enablement > backup_$(date +%Y%m%d_%H%M%S).sql
echo "Database backup created"

# 3. Verify script is ready
echo -e "\n=== Deployment Script ==="
ls -lh deploy-multi-tenant.sh
if [ -x deploy-multi-tenant.sh ]; then
    echo "✓ Script is executable"
else
    echo "✗ Script needs chmod +x"
fi

# 4. Check disk space
echo -e "\n=== Disk Space ==="
docker exec docker-app-1 df -h /app

echo -e "\n=== Ready to Deploy ==="
echo "Run: ./deploy-multi-tenant.sh"
```

---

## 🚨 **Known Issues / Gotchas**

### **Issue 1: Frontend TypeScript Errors**
**Symptom**: TypeScript compilation fails with unknown types  
**Cause**: Generated API types not updated  
**Fix**: Run `npm run generate-api` in frontend directory

### **Issue 2: Migration Already Applied**
**Symptom**: "Target database is not up to date" or "Revision not found"  
**Cause**: Migrations were manually applied earlier  
**Fix**: Check `docker exec docker-app-1 python -m alembic current` and verify state

### **Issue 3: Permission Denied on Settings Page**
**Symptom**: 403 error when accessing `/admin/settings`  
**Cause**: User doesn't have `settings:read` permission  
**Fix**: Run RBAC init script: `docker exec docker-app-1 python /app/scripts/init_rbac_data.py`

### **Issue 4: Company Selector Shows No Companies**
**Symptom**: Empty dropdown on BI page  
**Cause**: No HR data in database  
**Fix**: Seed HR data: `docker exec docker-app-1 python /app/scripts/seed_hr_data.py`

---

## 📋 **Final Checklist**

Before running `./deploy-multi-tenant.sh`:

- [ ] Verified containers are running
- [ ] Created database backup
- [ ] Checked current migration status
- [ ] Reviewed deployment script
- [ ] Understand rollback procedure
- [ ] Have time for testing (30-60 minutes)
- [ ] Ready to regenerate frontend API types afterward
- [ ] Users notified of brief downtime (if applicable)

---

## 🎯 **Deployment Order**

1. ✅ Run `./deploy-multi-tenant.sh` (backend deployment)
2. ✅ Verify backend APIs work
3. ✅ Regenerate frontend API types (`npm run generate-api`)
4. ✅ Build frontend (`npm run build`)
5. ✅ Restart frontend container (if applicable)
6. ✅ Test end-to-end functionality

---

## 💡 **Recommendation**

**SAFEST APPROACH:**

1. **First**: Deploy backend only (run the script)
2. **Test**: Verify backend APIs manually with curl
3. **Then**: Handle frontend separately after confirming backend works
4. **Finally**: End-to-end testing

This way, if there are issues, you can isolate whether they're backend or frontend problems.

---

**Ready to proceed when you are! 🚀**


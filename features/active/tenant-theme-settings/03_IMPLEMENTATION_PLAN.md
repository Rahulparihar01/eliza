# Implementation Plan
## Tenant Theme Settings

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | In Progress |
| **Last Updated** | January 23, 2026 |
| **PRD Reference** | [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md) |
| **Tech Spec Reference** | [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md) |

---

## Phase Overview

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Backend Foundation (Model, Migration, Permission) | ✅ Complete |
| **Phase 2** | Backend API (Routes, Schemas) | ✅ Complete |
| **Phase 3** | Frontend State (Zustand Store, Theme Loading) | ✅ Complete |
| **Phase 4** | Frontend Page (ThemePage Component) | ✅ Complete |
| **Phase 5** | Navigation & Routing | ✅ Complete |
| **Phase 6** | Testing & Verification | ✅ Complete |

---

## Phase 1: Backend Foundation

### Tasks

- [ ] **1.1** Create `src/models/tenant_theme.py` with SQLAlchemy model
- [ ] **1.2** Add model export to `src/models/__init__.py`
- [ ] **1.3** Create Alembic migration for `tenant_themes` table
- [ ] **1.4** Add `theme:write` permission to the permissions system

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/models/tenant_theme.py` | Create |
| `src/models/__init__.py` | Modify (add export) |
| `alembic/versions/xxxx_add_tenant_themes.py` | Create |
| Permission seeding (if applicable) | Modify |

---

## Phase 2: Backend API

### Tasks

- [ ] **2.1** Create `src/api/schemas/tenant_settings.py` with Pydantic models
- [ ] **2.2** Create `src/api/routes/tenant_settings.py` with GET/PUT endpoints
- [ ] **2.3** Register router in `src/main.py`
- [ ] **2.4** Test endpoints manually with curl/httpie

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/api/schemas/tenant_settings.py` | Create |
| `src/api/routes/tenant_settings.py` | Create |
| `src/main.py` | Modify (register router) |

---

## Phase 3: Frontend State

### Tasks

- [ ] **3.1** Create `frontend/src/stores/useTheme.ts` Zustand store
- [ ] **3.2** Add theme loading to `App.tsx` on init
- [ ] **3.3** Verify CSS variables are applied correctly

### Files to Create/Modify

| File | Action |
|------|--------|
| `frontend/src/stores/useTheme.ts` | Create |
| `frontend/src/App.tsx` | Modify (add theme loading) |

---

## Phase 4: Frontend Page

### Tasks

- [ ] **4.1** Create `frontend/src/pages/tenant-admin/ThemePage.tsx`
- [ ] **4.2** Implement color pickers, presets, live preview
- [ ] **4.3** Wire up save/reset functionality
- [ ] **4.4** Add success/error toast notifications

### Files to Create/Modify

| File | Action |
|------|--------|
| `frontend/src/pages/tenant-admin/ThemePage.tsx` | Create |

---

## Phase 5: Navigation & Routing

### Tasks

- [ ] **5.1** Add Theme item to `sectionConfigs.ts` (Admin Settings section)
- [ ] **5.2** Update `getSectionFromPath` to recognize `/tenant-admin/theme`
- [ ] **5.3** Add route in `App.tsx` with `theme:write` permission check

### Files to Modify

| File | Action |
|------|--------|
| `frontend/src/components/navigation/sectionConfigs.ts` | Modify |
| `frontend/src/App.tsx` | Modify (add route) |

---

## Phase 6: Testing & Verification

### Tasks

- [ ] **6.1** Verify theme loads on app init
- [ ] **6.2** Test color picker changes update live preview
- [ ] **6.3** Test preset selection works
- [ ] **6.4** Test save persists to database
- [ ] **6.5** Test theme applies after page refresh
- [ ] **6.6** Test permission enforcement (non-admin cannot access)
- [ ] **6.7** Rebuild containers and verify in Docker environment

---

## Execution Order

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
   │           │           │           │           │           │
   ▼           ▼           ▼           ▼           ▼           ▼
 Model      API        Zustand      Page       Routes      Test
 Migration  Endpoints   Store       Component  Nav         Verify
 Permission
```

---

## Notes

- Each phase is designed to be independently verifiable
- Backend phases (1-2) can be tested with curl before frontend work
- Frontend phases (3-5) build incrementally on each other
- Phase 6 is end-to-end verification

# SSO Settings Page Redesign — Implementation Plan

| **Status** | In Progress |
|------------|-------|
| **Date** | February 23, 2026 |
| **Author** | Agent |
| **Relates to** | `features/backlog/tenant-sso-and-password-hardening/01_PRODUCT_SPEC.md` |

---

## Phase Status

- [x] **Phase 1 (Additive migration)**: Completed
  - Added `tenant_sso_providers` and `tenant_sso_domains` via `zz27_multi_provider_sso`.
  - Backfilled existing `tenant_sso_configs` provider/domain data.
  - Verified locally in Docker:
    - `tenant_sso_providers`: `eliza | google | oidc | true`
    - `tenant_sso_domains`: `eliza | eliza.com | verified`
- [x] **Phase 2 (Backend hard cutover)**: Completed
  - Add SQLAlchemy models + Pydantic schemas for provider/domain CRUD.
  - Add tenant settings API endpoints for providers/domains.
- Hard-cut runtime and tenant settings flows to new provider/domain tables.
- [x] **Phase 3 (Runtime + login flow cutover)**: Completed
- [x] **Phase 4a (Frontend dashboard + sheet UX)**: Completed then superseded
  - Built sheet-based approach but found density mismatch: providers too dense for a sheet,
    policy too sparse. Sheets replaced by tabs in Phase 4b.
- [ ] **Phase 4b (Frontend status bar + tabs UX)**: In progress
  - Slim status bar at top with 3 clickable segments (policy badge, domain count, provider count).
  - Three tabs below: Login Policy, Verified Domains, SSO Providers.
  - Provider tab uses full-width master-detail (280px list + remaining detail).
  - Readiness checklist folded into status bar badges (no separate card — avoids "day 300 dead pixels").
  - Destructive actions use centered modals (no sheet layering concern).
  - Unsaved changes guard via `beforeunload` + provider-switch interception.
  - UI spec updated in `04_UI_SPEC.md`.
- [ ] **Phase 5 (Cleanup migration and old table removal)**: Not started

---

## Problems to Solve

### Problem 1: No way to add multiple SSO providers

The current data model (`TenantSSOConfig`) has a `UNIQUE` constraint on `customer_id`, so each tenant can only have one SSO provider. The UI is a single flat form — there is no mechanism to add a second provider or manage providers as a list.

Enterprise SaaS apps (Slack, GitHub, Okta Admin) routinely let tenants configure multiple identity providers (e.g., Azure AD for employees + Okta for contractors).

### Problem 2: Confusing form logic

The current page exposes both an "Enable SSO provider for this tenant" checkbox **and** a "Login Mode" dropdown that includes "Password only". These two controls conflict:

- A tenant can check "Enable SSO" and select "Password only" — contradictory.
- A tenant must know to both enable the checkbox **and** change the dropdown — two steps that mean the same thing.
- The `is_enabled` boolean on `TenantSSOConfig` mixes provider-level activation with tenant login policy.

### Problem 3: No domain verification mechanism

The "Require domain verification" checkbox is currently just a validation flag — there is no actual verification flow. No TXT record generation, no DNS lookup, no verification status per domain. Admins can type any domain into the allowlist without proving ownership.

---

## Proposed Design

### 1. Multi-Provider UI — Master / Detail Layout

**Recommendation: Master-detail split view** (not tabs).

Tabs don't scale well beyond 3-4 providers and make it hard to compare or manage providers at a glance. A master-detail layout is the standard enterprise admin pattern:

```
┌────────────────────────────┬───────────────────────────────────────────────┐
│  SSO Providers             │  Configure: Azure / Entra ID (OIDC)          │
│                            │                                               │
│  ┌──────────────────────┐  │  Display Name: [ Acme Corporate SSO      ]   │
│  │ ✅ Azure / Entra ID  │←─│                                               │
│  │    OIDC · Tested ✓   │  │  ── Provider Setup Guide ──────────────────  │
│  └──────────────────────┘  │  (Azure-specific instructions + links)        │
│  ┌──────────────────────┐  │                                               │
│  │ ○ Okta               │  │  ── OIDC Configuration ────────────────────  │
│  │    OIDC · Not tested  │  │  Issuer URL: [ https://login.microsoft... ]  │
│  └──────────────────────┘  │  Client ID:  [ abc-123-def               ]   │
│                            │  Client Secret: [ ••••••••  ] ✅ Stored       │
│  [ + Add Provider ]        │  Scopes: [ openid, profile, email        ]   │
│                            │                                               │
│                            │  ── Actions ─────────────────────────────────  │
│                            │  [ Test Configuration ]  [ Save ]  [ Delete ] │
└────────────────────────────┴───────────────────────────────────────────────┘
```

**Why master-detail over tabs:**

| Criteria | Master-Detail | Tabs |
|----------|--------------|------|
| Scales to N providers | Yes — list scrolls | No — tab bar overflows at 4+ |
| At-a-glance status | Yes — see all statuses in list | No — one tab visible at a time |
| Familiar pattern | Slack, GitHub, Okta, Azure Portal | Less common for admin config |
| Add/remove UX | Natural — "Add" button in list | Awkward — dynamic tab creation |
| Mobile-friendly | Stack list/detail vertically | Still needs tab bar |

**Data flow:**

- Left panel: list of `TenantSSOProvider` records for this tenant, each showing provider type, protocol, enabled/disabled badge, and test status.
- Right panel: the configuration form for the selected provider, including the **provider-specific** setup guide (not all guides at once).
- "Add Provider" button opens the detail panel with an empty form and provider/protocol selector.

### 2. Separate Login Policy from Provider Configuration

Currently everything is a single `TenantSSOConfig` row. The redesign separates concerns:

#### Tenant Login Policy (top of page, above the provider list)

A simple card:

```
┌─────────────────────────────────────────────────────────────┐
│  Login Policy                                                │
│                                                              │
│  How should users in this tenant authenticate?               │
│                                                              │
│  ○ Password only — SSO providers below are inactive          │
│  ○ SSO optional — users can choose SSO or password           │
│  ● SSO enforced — password login blocked (except break-glass)│
│                                                              │
│  [ Save Policy ]                                             │
└─────────────────────────────────────────────────────────────┘
```

Rules:
- When `password_only` is selected, the provider list is still visible (so admins can pre-configure), but providers are flagged as "inactive" and the login page won't show SSO buttons.
- When `sso_optional` or `sso_enforced` is selected, at least one provider must be enabled and tested.
- Removes the confusing `is_enabled` checkbox + `login_mode` dropdown overlap.

#### Per-Provider Configuration (detail panel)

Each provider has its own:
- Provider type (Azure, Okta, Google, Generic)
- Protocol (OIDC, SAML)
- Display name
- Enabled/disabled toggle
- Protocol-specific fields (issuer URL, client ID, etc.)
- Test status
- JIT provisioning toggle + default role

### 3. Domain Verification via DNS TXT Record

Standard flow used by Google Workspace, Microsoft 365, Slack, etc.

#### User Flow

```
1. Admin clicks "Add Domain" → enters "acme.com"
2. System generates a unique verification token:
   "eliza-domain-verify=t_abc123xyz789"
3. UI shows instructions:
   ┌──────────────────────────────────────────────────────┐
   │  Verify ownership of acme.com                        │
   │                                                      │
   │  Add the following TXT record to your DNS:           │
   │  ┌──────────────────────────────────────────────┐    │
   │  │ eliza-domain-verify=t_abc123xyz789           │ 📋 │
   │  └──────────────────────────────────────────────┘    │
   │                                                      │
   │  Record type: TXT                                    │
   │  Host: @ (or acme.com)                               │
   │  Value: eliza-domain-verify=t_abc123xyz789           │
   │                                                      │
   │  DNS changes can take up to 48 hours to propagate.   │
   │                                                      │
   │  [ Verify Now ]  Status: ⏳ Pending                  │
   └──────────────────────────────────────────────────────┘
4. Admin adds TXT record in their DNS provider
5. Admin clicks "Verify Now"
6. Backend performs DNS TXT lookup on acme.com
7. If token found → status changes to ✅ Verified
   If not found → status stays ⏳ Pending with message
```

#### Domain Section (separate card on the SSO settings page)

```
┌─────────────────────────────────────────────────────────────┐
│  Verified Domains                                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ acme.com          ✅ Verified    [ Re-verify ] [ ✕ ]  │  │
│  │ eu.acme.com       ⏳ Pending     [ Verify Now ] [ ✕ ] │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [ + Add Domain ]                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Model Changes

### New: `tenant_sso_providers` table

Replaces the single-provider-per-tenant constraint. Each row is one configured provider for a tenant.

```sql
CREATE TABLE tenant_sso_providers (
    id              SERIAL PRIMARY KEY,
    customer_id     VARCHAR(100) NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    
    -- Provider identity
    provider_type   VARCHAR(64)  NOT NULL,  -- azure, okta, google, generic
    protocol        VARCHAR(16)  NOT NULL,  -- oidc, saml
    display_name    VARCHAR(255),
    is_enabled      BOOLEAN      NOT NULL DEFAULT false,
    
    -- Protocol-specific public config (issuer URL, client ID, scopes, etc.)
    config_data     JSONB,
    
    -- Encrypted secrets (client secret, SAML cert)
    secret_data_encrypted JSONB,
    
    -- JIT provisioning (per-provider)
    jit_provisioning_enabled BOOLEAN NOT NULL DEFAULT false,
    jit_default_role         VARCHAR(100) NOT NULL DEFAULT 'viewer',
    
    -- Test tracking
    last_tested_at   TIMESTAMPTZ,
    last_test_status VARCHAR(32),   -- success, failed
    last_test_error  TEXT,
    
    -- Audit
    updated_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- A tenant can have at most one provider of the same type+protocol
    UNIQUE (customer_id, provider_type, protocol)
);
CREATE INDEX idx_sso_providers_customer ON tenant_sso_providers(customer_id);
```

### New: `tenant_sso_domains` table

Tracks domain ownership verification status.

```sql
CREATE TABLE tenant_sso_domains (
    id              SERIAL PRIMARY KEY,
    customer_id     VARCHAR(100) NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    
    domain          VARCHAR(255) NOT NULL,
    verification_token VARCHAR(255) NOT NULL,  -- "eliza-domain-verify=t_xxxxx"
    
    status          VARCHAR(32)  NOT NULL DEFAULT 'pending',  -- pending, verified, failed
    verified_at     TIMESTAMPTZ,
    last_checked_at TIMESTAMPTZ,
    last_check_error TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE (customer_id, domain)
);
CREATE INDEX idx_sso_domains_customer ON tenant_sso_domains(customer_id);
CREATE INDEX idx_sso_domains_domain ON tenant_sso_domains(domain);
```

### Modified: `tenant_sso_configs` table

Reduced to **tenant login policy only** (no more provider-specific fields):

```sql
-- Keep existing table but remove provider-specific columns over time.
-- For now, add a migration that:
-- 1. Creates the two new tables above
-- 2. Migrates existing provider data from tenant_sso_configs → tenant_sso_providers
-- 3. Migrates existing domain_allowlist entries → tenant_sso_domains (status='verified' for existing)
-- 4. tenant_sso_configs retains only: customer_id, login_mode, domain_verification_required
```

Retained columns on `tenant_sso_configs`:

| Column | Purpose |
|--------|---------|
| `customer_id` | FK to tenant (unique) |
| `login_mode` | password_only / sso_optional / sso_enforced |
| `domain_verification_required` | Whether enforced mode requires verified domains |
| `updated_by_user_id` | Audit |

Removed columns (migrated to `tenant_sso_providers`):
- `is_enabled`, `provider_type`, `protocol`, `provider_display_name`
- `config_data`, `secret_data_encrypted`
- `jit_provisioning_enabled`, `jit_default_role`
- `last_tested_at`, `last_test_status`, `last_test_error`

Removed columns (migrated to `tenant_sso_domains`):
- `domain_allowlist`

---

## API Changes

### New endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/tenant-settings/sso/providers` | List all providers for this tenant |
| `POST` | `/v1/tenant-settings/sso/providers` | Create a new provider |
| `GET` | `/v1/tenant-settings/sso/providers/{id}` | Get a single provider |
| `PUT` | `/v1/tenant-settings/sso/providers/{id}` | Update a provider |
| `DELETE` | `/v1/tenant-settings/sso/providers/{id}` | Delete a provider |
| `POST` | `/v1/tenant-settings/sso/providers/{id}/test` | Test a specific provider |
| `GET` | `/v1/tenant-settings/sso/domains` | List domains with verification status |
| `POST` | `/v1/tenant-settings/sso/domains` | Add a domain (returns verification token) |
| `POST` | `/v1/tenant-settings/sso/domains/{id}/verify` | Trigger DNS verification check |
| `DELETE` | `/v1/tenant-settings/sso/domains/{id}` | Remove a domain |

### Modified endpoints

| Method | Path | Change |
|--------|------|--------|
| `GET` | `/v1/tenant-settings/sso` | Returns only login policy + summary (not full provider config) |
| `PUT` | `/v1/tenant-settings/sso` | Updates only login policy (`login_mode`, `domain_verification_required`) |

### Removed endpoints

| Method | Path | Reason |
|--------|------|--------|
| `POST` | `/v1/tenant-settings/sso/test` | Replaced by per-provider test endpoint |

### Runtime service changes

`TenantSSORuntimeService` needs updates:

- `resolve_login()` → query `tenant_sso_providers` (multiple rows) instead of single `tenant_sso_configs` row
- `get_sso_config_for_customer()` → look up enabled providers for the tenant, resolve which one to use (by protocol or domain match)
- `_match_tenant_by_email_domain()` → query `tenant_sso_domains` (verified status) instead of `domain_allowlist` JSON
- `_effective_sso_runtime_enabled()` → check if tenant has **any** enabled provider with valid config
- Login page options endpoint (`/auth/sso/options`) → return list of available providers (not just one)

---

## Frontend Changes

### Component structure

```
frontend/src/pages/tenant-admin/
├── SsoSettingsPage.tsx          # Page shell: status bar + tabs
├── sso/
│   ├── types.ts                # Shared TypeScript types + helpers
│   ├── constants.ts            # Options, setup guides, labels
│   ├── useUnsavedChangesGuard.ts # Dirty tracking + beforeunload
│   ├── SsoStatusBar.tsx        # Slim 3-segment status strip (clickable → switches tab)
│   ├── PolicyTab.tsx           # Login mode radio cards + inline confirmation
│   ├── DomainsTab.tsx          # Domain add/verify/remove + DNS instructions
│   ├── ProvidersTab.tsx        # Full-width master-detail (280px list + detail)
│   └── ConfirmationModal.tsx   # Reusable centered modal for destructive actions
```

### Page layout

```tsx
<Page>
  <PageHeader title="SSO Settings" />
  <PageBody>
    {/* Slim status bar — clickable segments switch the active tab */}
    <SsoStatusBar
      loginMode={loginMode}
      providers={providers}
      domains={domains}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    />

    {/* Tabs */}
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <TabsList>
        <TabsTrigger value="policy">Login Policy</TabsTrigger>
        <TabsTrigger value="domains">Verified Domains</TabsTrigger>
        <TabsTrigger value="providers">SSO Providers</TabsTrigger>
      </TabsList>

      <TabsContent value="policy">
        <PolicyTab ... />
      </TabsContent>
      <TabsContent value="domains">
        <DomainsTab ... />
      </TabsContent>
      <TabsContent value="providers">
        <ProvidersTab ... />  {/* full-width master-detail */}
      </TabsContent>
    </Tabs>
  </PageBody>
</Page>
```

### Login page changes

The login page currently shows one SSO button. With multi-provider support:

- If only one provider is active → show single branded button (current behavior)
- If multiple providers are active → show a button per provider, each with provider display name
- Provider list comes from `/auth/sso/options` which will now return an array

---

## Migration Strategy

Because this is still pre-production and not yet in use:

1. **Phase A — Additive migration**
   - Create `tenant_sso_providers` and `tenant_sso_domains` tables
   - Copy data from `tenant_sso_configs` into new tables
   - Existing domains get `status='verified'` (grandfather existing config)
   - Keep `tenant_sso_configs` temporarily only to simplify data copy and rollback

2. **Phase B — Backend hard cuts over to new tables**
   - Update services + runtime to read from new tables
   - New API endpoints go live
   - Replace old `/sso` payload model and logic directly (no shim layer)

3. **Phase C — Frontend ships new UI**
   - New split-view page replaces current form
   - Domain verification UI goes live

4. **Phase D — Cleanup migration**
   - Drop unused columns from `tenant_sso_configs`
   - Optionally drop `tenant_sso_configs` entirely once policy fields are moved

---

## Implementation Order

| Step | Scope | Files | Estimate |
|------|-------|-------|----------|
| 1 | Alembic migration: create `tenant_sso_providers` + `tenant_sso_domains`, data copy | `alembic/versions/`, `src/models/` | 1 day |
| 2 | SQLAlchemy models for new tables | `src/models/tenant_sso.py` | 0.5 day |
| 3 | Pydantic schemas for new endpoints | `src/api/schemas/sso_settings.py` | 0.5 day |
| 4 | Provider CRUD service + domain verification service | `src/services/` | 1 day |
| 5 | New API routes (providers CRUD, domain CRUD + verify) | `src/api/routes/tenant_settings.py` | 1 day |
| 6 | Update runtime service for multi-provider resolution | `src/services/tenant_sso_runtime_service.py` | 1 day |
| 7 | Update login page options endpoint for multi-provider | `src/api/routes/auth.py` | 0.5 day |
| 8 | Frontend: Login policy card component | `frontend/src/pages/tenant-admin/sso/` | 0.5 day |
| 9 | Frontend: Provider list + detail components | `frontend/src/pages/tenant-admin/sso/` | 1.5 days |
| 10 | Frontend: Domain verification card + modal | `frontend/src/pages/tenant-admin/sso/` | 1 day |
| 11 | Frontend: Login page multi-provider buttons | `frontend/src/pages/auth/LoginPage.tsx` | 0.5 day |
| 12 | Integration testing all provider types | Manual testing | 1 day |
| 13 | Cleanup migration (drop old columns) | `alembic/versions/` | 0.5 day |

**Total estimate: ~10 days**

---

## Open Questions

1. **Should each provider have its own domain allowlist, or is the domain list tenant-wide?**
   - Recommendation: **Tenant-wide**. Domains represent the organization, not the IdP. A tenant with `acme.com` verified should be able to use it with any of their providers.

2. **What happens when a tenant has multiple providers and a user clicks "Sign in with SSO" on the login page?**
   - Recommendation: Show one button per enabled provider, each labeled with `display_name`. E.g., "Continue with Azure AD", "Continue with Okta".

3. **Should we auto-re-verify domains periodically?**
   - Recommendation: Not in v1. Manual re-verify button is sufficient. Can add periodic re-check as a follow-up.

4. **Unique constraint: one provider per (type + protocol) or fully open?**
   - Recommendation: Unique per `(customer_id, provider_type, protocol)` to prevent accidental duplicates. A tenant can have Azure OIDC + Okta OIDC but not two Azure OIDC entries.

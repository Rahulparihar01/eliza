# Product Requirements Document
## Tenant SSO and Password Hardening

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Implemented (MVP) |
| **Last Updated** | February 18, 2026 |
| **Product Owner** | Steven McAteer |
| **Engineering Lead** | TBD |

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [Target Users](#target-users)
5. [User Stories](#user-stories)
6. [Feature Details](#feature-details)
7. [Technical Requirements](#technical-requirements-high-level)
8. [Dependencies](#dependencies)
9. [Acceptance Criteria](#acceptance-criteria)
10. [Success Metrics](#success-metrics)
11. [Risks and Considerations](#risks-and-considerations)
12. [Implementation Phases](#implementation-phases)
13. [Open Questions](#open-questions)

---

## Executive Summary

Introduce tenant-configurable SSO with platform-level governance so each tenant can choose and configure their own identity provider (Azure/Entra, Okta, Google, and generic OIDC/SAML), and choose whether SSO is optional or enforced.  
In parallel, harden local password authentication with stronger policy enforcement and consistent validation across all password creation/change paths, while accounting for current constraints (no outbound email system, Northflank deployment, cloud portability).

### Implementation Status (February 18, 2026)

- Implemented across backend, auth runtime, and frontend for all planned phases in MVP scope.
- OIDC and SAML runtime flows are both available.
- Tenant and platform admin settings surfaces are implemented.
- Password policy enforcement is centralized on invite acceptance, create-user, and change-password paths.

---

## Problem Statement

### Current State Challenges

| Challenge | Impact |
|-----------|--------|
| No tenant-level SSO configuration | Enterprise customers cannot use corporate identity providers |
| No platform-level governance for SSO capability | No centralized way to enable/disable SSO feature by tenant allocation |
| Login is username/password only | Increased credential risk and reduced enterprise readiness |
| Password validation is inconsistent across auth paths | Security posture varies by entry point |
| No email server for account recovery/reset workflows | Password recovery and invite flows must avoid email-dependent assumptions |

### The Opportunity

- Make enterprise onboarding easier by supporting common IdPs and delegated authentication.
- Improve security by reducing password usage when SSO is enforced and hardening remaining password flows.
- Preserve tenant flexibility: each tenant can run optional SSO or enforced SSO based on readiness.
- Keep the platform cloud-portable (Northflank, AWS, GCP, Azure) by using standards-based auth and environment-driven config.

---

## Goals and Non-Goals

### Goals (P0/P1/P2)

| Priority | Goal |
|----------|------|
| **P0** | Platform admin can control whether SSO is available as a tenant feature (feature allocation + global guardrails) |
| **P0** | Tenant admin can configure at least one SSO provider for their tenant |
| **P0** | Tenant admin can choose `Optional SSO` or `Enforced SSO` |
| **P0** | If SSO is optional, username/password login still works |
| **P0** | If SSO is enforced, local username/password login is blocked for normal users |
| **P0** | Tenants may configure multiple SSO providers (mirrors enterprise SaaS norms) |
| **P0** | Support popular providers at launch: Azure/Entra ID, Okta, Google Workspace, and generic OIDC/SAML |
| **P0** | Strengthen password requirements and enforce them consistently everywhere passwords are set/changed |
| **P1** | Add platform admin controls for emergency override and break-glass access behavior |
| **P1** | Add audit visibility for SSO config changes and login method used (password vs SSO) |
| **P1** | Add role and attribute mapping options for SSO claims |
| **P2** | Add SCIM provisioning/deprovisioning |

### Non-Goals (Out of Scope for Initial Launch)

| Item | Rationale |
|------|-----------|
| Full SCIM lifecycle management | Higher implementation/ops complexity; can follow core SSO launch |
| Email-based password reset flows | Current platform has no email server |
| Consumer/social login (non-enterprise) | Not aligned with tenant enterprise use case |
| Provider-specific custom deep integrations beyond standards | Keep initial scope standards-based (OIDC/SAML) for portability |
| Hard requirement for all tenants to adopt SSO | Must support optional and staged rollout |

---

## Target Users

### Primary Users

#### User Type 1: Platform Administrator (Eliza Team)
- **Who they are:** Internal admins controlling tenant provisioning and feature allocation.
- **What they need:** Central controls for which tenants can use SSO, which providers are allowed, and emergency controls.
- **How they'll use this:** Platform settings + feature allocation pages.

#### User Type 2: Tenant Administrator
- **Who they are:** Customer admins who manage tenant settings and access policy.
- **What they need:** Self-service SSO setup with clear validation/testing and policy mode (optional vs enforced).
- **How they'll use this:** Tenant admin settings page for SSO provider setup and login policy.

#### User Type 3: Tenant End User
- **Who they are:** Users signing in to the application.
- **What they need:** Predictable login experience for their organization policy.
- **How they'll use this:** Login page with SSO buttons/flow and fallback behavior per tenant policy.

### Secondary Users

- Security/compliance stakeholders who need auditable authentication controls.
- Customer success and implementation teams onboarding enterprise tenants.

---

## User Stories

### Epic: Platform Governance

**US-001:** As a platform admin, I want SSO to be allocatable per tenant so I can enable it only for tenants with the right plan/entitlement.  
**US-002:** As a platform admin, I want a global SSO kill switch so I can rapidly disable SSO if there is a security incident.  
**US-003:** As a platform admin, I want to restrict allowed IdP types so only approved providers are available to tenants.

### Epic: Tenant SSO Configuration

**US-004:** As a tenant admin, I want to configure Azure/Okta/Google/generic OIDC or SAML so my users can sign in with company credentials.  
**US-005:** As a tenant admin, I want to test SSO configuration before enforcement so I can avoid tenant-wide lockout.  
**US-006:** As a tenant admin, I want to switch between optional and enforced SSO so I can roll out gradually.

### Epic: Login and Access Behavior

**US-007:** As a tenant user, I want to see my organization's SSO login options when available so I can use corporate auth.  
**US-008:** As a tenant user in optional mode, I want to still use password login if needed.  
**US-009:** As a tenant user in enforced mode, I want password login blocked so policy is consistently applied.

### Epic: Password Security Hardening

**US-010:** As a platform security owner, I want stronger password policy enforced consistently so weak credentials are reduced.  
**US-011:** As a tenant admin, I want to keep local login secure for optional-mode users and break-glass users.  
**US-012:** As an end user, I want clear password validation messages so I can create compliant credentials quickly.

---

## Feature Details

### Feature 1: Platform-Level SSO Controls

#### 1.1 Feature Allocation
- Add a new platform feature key: `sso_authentication` (name TBD).
- Platform admin can allocate/deallocate this feature per tenant using existing feature allocation flow.
- If deallocated:
  - Tenant cannot configure SSO.
  - Tenant login mode cannot be set to SSO optional/enforced.

#### 1.2 Global Platform Guardrails
Proposed platform-admin controls:

1. `global_sso_enabled` (kill switch)
2. `allowed_provider_types` (e.g., azure_oidc, okta_oidc, google_oidc, generic_oidc, generic_saml)
3. `allow_tenant_enforced_mode` (can tenants enforce, or optional only)
4. `require_domain_verification_for_enforced_mode`
5. `break_glass_policy` (required):
   - Allowed roles/accounts for local login when SSO is enforced
   - Whether break-glass is always on or only emergency-enabled
6. `jit_provisioning_default` (default **off** for new tenants)
   - If enabled by tenant, default JIT role is `viewer`
7. `default_password_policy_profile`

#### 1.3 Additional Platform Controls (Recommended)
- Central audit feed of SSO config changes (who changed issuer, client ID, mode, etc.).
- Tenant lockout recovery controls:
  - Temporarily switch tenant from enforced to optional.
  - Disable a tenant's SSO provider quickly.
- Session policy baseline:
  - Max session age
  - Reauthentication requirement for sensitive actions.

---

### Feature 2: Tenant SSO Settings

#### 2.1 Tenant Login Modes

Proposed enum:
- `PASSWORD_ONLY` (if SSO not configured or feature unavailable)
- `SSO_OPTIONAL`
- `SSO_ENFORCED`

Rules:
- `SSO_OPTIONAL`: both local login and SSO login are allowed.
- `SSO_ENFORCED`: local login blocked for standard users; only SSO (plus approved break-glass users).
- Tenant cannot select SSO modes unless tenant has SSO feature allocation and platform global SSO is enabled.
- `SSO_ENFORCED` requires domain allowlist/verification.

#### 2.2 Provider Configuration (Per Tenant)

MVP provider set:
- Microsoft Entra ID (Azure AD)
- Okta
- Google Workspace
- Generic OIDC
- Generic SAML 2.0

Provider constraint:
- Multiple active providers per tenant are allowed (aligns with standard enterprise SaaS patterns).

Per-provider config fields (minimum):
- Provider type
- Protocol (`oidc` or `saml`)
- Display label (e.g., "Sign in with Acme SSO")
- OIDC fields:
  - issuer URL
  - client ID
  - client secret (encrypted at rest)
  - scopes (default: `openid profile email`)
- SAML fields:
  - entity ID / audience
  - IdP SSO URL
  - IdP certificate (or metadata URL)
  - optional SP signing certificate settings (if required later)
- Optional domain allowlist (e.g., `acme.com`)
- Claims mapping:
  - email claim
  - given_name/family_name claim
  - optional groups/roles claim

#### 2.3 Tenant UX Requirements
- Tenant admin page: `/tenant-admin/sso` (proposed)
- Configuration validation:
  - Metadata discovery check
  - JWKS retrieval check
  - Client credential check (non-destructive)
- "Test login" before save/apply enforced mode.
- Explicit lockout warning before enabling `SSO_ENFORCED`.

---

### Feature 3: Runtime Authentication Behavior

#### 3.1 Login Experience

At login:
- User enters email or chooses tenant context.
- App determines tenant policy and configured providers.
- Show:
  - SSO button(s) for configured providers
  - Password form only when mode is `PASSWORD_ONLY` or `SSO_OPTIONAL`

#### 3.2 User Identity Linking

Decisions required in implementation:
- Matching key: email (normalized lower-case) as primary link key.
- If SSO user exists by email in tenant: sign in.
- If not existing:
  - If JIT provisioning enabled: create user with default role.
  - Else: deny and require tenant admin invite/user creation first.

Default decisions:
- JIT provisioning is **OFF by default** in MVP.
- If a tenant enables JIT, default role is `viewer`.

#### 3.3 Multi-Tenant Membership Consideration

Because users can belong to multiple tenants:
- SSO login must resolve tenant context explicitly.
- Same email may map to different tenant memberships and different role sets.
- Enforced-mode check must apply to active tenant context, not global user identity.

---

### Feature 4: Password Hardening

#### 4.1 Policy Proposal (Initial)

Recommended baseline:
- Min length: **8** characters
- Max length: 128
- Require at least:
  - 1 uppercase
  - 1 lowercase
  - 1 number
  - 1 special character
- Block known weak/common passwords (existing denylist + expanded list)
- Prevent reuse of recent passwords (existing history mechanism, fix consistency gaps)

Notes:
- This should replace inconsistent path-specific checks across invite acceptance, password change, and reset/admin reset paths.
- Future hardening option: move minimum length to 10-12 once tenant adoption is stable.

#### 4.2 Enforcement Locations

Password policy must be applied consistently to:
- Invite acceptance (new user)
- Password change endpoint
- Any admin-driven reset endpoint
- Any future user self-service password set/reset flow

#### 4.3 No Email Server Constraint

Given no email service:
- Do not depend on email reset links.
- For local account recovery:
  - Admin-driven reset flow in tenant admin UI
  - Or platform-admin emergency reset
- For SSO users:
  - Password recovery remains in IdP, not in app.

---

## Technical Requirements (High-Level)

### Data Requirements

Add tenant-scoped SSO configuration storage (new table(s) preferred):
- `tenant_sso_configs`
- `tenant_sso_providers`
- `tenant_sso_domains` (optional)
- encrypted secret fields for provider credentials

Why separate tables (vs JSON only):
- Better queryability and validation
- Better auditability and migration control
- Easier future expansion (multiple providers per tenant; OIDC/SAML metadata support)

### API Requirements

Proposed endpoint groups:

1. Tenant admin SSO settings:
- `GET /api/v1/tenant-settings/sso`
- `PUT /api/v1/tenant-settings/sso`
- `POST /api/v1/tenant-settings/sso/test`
- `POST /api/v1/tenant-settings/sso/mode`

2. Auth runtime:
- `GET /api/v1/auth/sso/providers` (tenant-aware)
- `GET /api/v1/auth/sso/authorize/{provider}`
- `GET /api/v1/auth/sso/callback/{provider}`
- `POST /api/v1/auth/sso/saml/acs/{provider}` (SAML assertion consumer service)

3. Platform admin controls:
- `GET /api/v1/platform-admin/auth/sso-policy`
- `PUT /api/v1/platform-admin/auth/sso-policy`

### Security Requirements

- Encrypt IdP client secrets at rest.
- Validate issuer URLs and enforce HTTPS.
- Store/validate OIDC state and nonce.
- Validate SAML signatures, audience, recipient, and time conditions.
- Include audit logs for:
  - SSO settings changes
  - Login method used
  - Enforced/optional mode changes
  - Failed SSO attempts
- Respect tenant isolation for all SSO config fetch and runtime operations.

### Performance Requirements

- Login page provider discovery response under 300ms (excluding IdP redirect).
- OIDC metadata/JWKS caching with sensible TTL and cache invalidation on config change.
- SAML metadata/certificate caching with sensible TTL and safe refresh behavior.
- No tenant cross-contamination in cache keys.

### Portability Requirements (Northflank + Any Cloud)

- No cloud-vendor-specific auth dependency for core SSO flow.
- Use standards-based OIDC/SAML endpoints and env-configured callback base URL.
- Secret management compatible with:
  - Northflank secrets
  - AWS/GCP/Azure secret managers (through env injection or adapter layer).

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Owner |
|------------|--------|-------|
| Existing auth routes/service (`src/api/routes/auth.py`, `src/services/auth_service.py`) | Ready (needs extension) | Backend |
| Tenant settings route pattern (`src/api/routes/tenant_settings.py`) | Ready | Backend |
| Feature allocation model and APIs (`platform_features`, `tenant_feature_allocations`) | Ready | Backend |
| Frontend login page and auth store | Ready (needs extension) | Frontend |

### External Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| OIDC/SAML-compatible IdP endpoints | Required | Azure, Okta, Google, generic OIDC/SAML |
| Cryptography/encryption utility for secrets | Available | Reuse existing encryption utilities |
| Optional libraries for OIDC/SAML flow handling | To confirm | Prefer standards-compliant, well-maintained packages |

---

## Acceptance Criteria

### A. Platform Admin Controls

- [ ] Platform feature list includes `sso_authentication` (name final TBD).
- [ ] Platform admin can allocate/deallocate SSO feature per tenant.
- [ ] Global SSO kill switch exists and disables all SSO flows when off.
- [ ] Platform admin can restrict which provider types are tenant-configurable.
- [ ] Platform admin can emergency-disable tenant enforced mode.

### B. Tenant SSO Configuration

- [ ] Tenant admin can open SSO settings page only if feature is allocated.
- [ ] Tenant admin can configure Azure, Okta, Google, and generic OIDC/SAML.
- [x] Tenants may configure multiple SSO providers.
- [ ] Provider secrets are never returned plaintext from API.
- [ ] "Test SSO config" endpoint validates metadata and client settings.
- [ ] Tenant admin can save and switch between optional/enforced modes.
- [ ] Enforced mode change presents explicit lockout warning/confirmation.
- [ ] Enforced mode requires configured and verified allowed domain(s).

### C. Login Behavior

- [ ] Optional mode allows both SSO and password login.
- [ ] Enforced mode blocks password login for non-break-glass users.
- [ ] Login page shows tenant-appropriate providers.
- [ ] Successful SSO login creates session and returns standard auth payload.
- [ ] Failed SSO login produces safe error (no secret leakage).

### D. Password Hardening

- [ ] All password set/change paths use a shared password policy validator.
- [ ] Password policy messages are user-friendly and actionable.
- [ ] Existing weak-password bypass paths are removed.
- [ ] Password history/reuse check behaves consistently.

### E. Audit and Security

- [ ] SSO config changes are auditable with actor and timestamp.
- [ ] Login method (password vs SSO) is captured in auth audit logs.
- [ ] Tenant isolation tests confirm no cross-tenant SSO config leakage.

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Tenants with successful SSO setup | >= 80% of targeted enterprise tenants in rollout cohort | Tenant onboarding tracking |
| Tenant SSO setup failure rate | < 10% after first pass | SSO test endpoint and support tickets |
| Password-based logins for enforced tenants | 0 (except break-glass) | Auth audit logs |
| Auth-related support incidents during rollout | < agreed threshold | Support issue tagging |
| Mean time to recover from SSO misconfiguration | < 15 minutes | Admin audit + incident timeline |

---

## Risks and Considerations

1. **Tenant lockout risk** if enforced mode is enabled with broken IdP config.
2. **User identity collision risk** across multi-tenant memberships if email mapping is not strict.
3. **Policy inconsistency risk** if password rules remain partially applied.
4. **Operational risk without email** for local account recovery.
5. **Provider variability** in claims/group formats may require per-provider mapping controls.
6. **Secret management risk** if not encrypted and masked consistently.
7. **Cloud edge configuration risk** for callback URLs in different ingress setups.

Mitigations:
- Test-before-enforce flow
- Break-glass mechanism
- Strong audit logging
- Strict URL/issuer validation
- Staged rollout by tenant cohort

---

## Implementation Phases

### Phase 0: Discovery and Final Decisions (3-5 days)

Status: Completed

Deliverables:
- Confirmed MVP protocol scope: OIDC + SAML.
- Final password baseline (8+ with composition) and compatibility strategy.
- Final list of platform guardrails and break-glass policy.

Exit Criteria:
- Approved PRD decisions and resolved open questions.

---

### Phase 1: Data and Backend Foundation (5-8 days)

Status: Completed

Deliverables:
- DB migration(s) for tenant SSO config.
- Models + schemas + services for SSO config CRUD.
- Encryption/masking for client secrets.
- Platform-level SSO policy storage and read/write endpoints.

Exit Criteria:
- API contracts pass validation.
- Migration and rollback tested locally.

---

### Phase 2: Auth Flow Integration (7-10 days)

Status: Completed

Deliverables:
- OIDC authorization/callback endpoints and SAML ACS/callback endpoints.
- Session/token issuance integrated with existing auth service.
- Tenant policy-aware login behavior.
- JIT provisioning toggle behavior implemented.

Exit Criteria:
- End-to-end login works for at least one provider in staging.
- Optional/enforced mode behavior validated.

---

### Phase 3: Frontend Admin and Login UX (6-9 days)

Status: Completed

Deliverables:
- Tenant SSO settings page (config, test, mode toggle).
- Platform admin SSO policy controls page/section.
- Login page provider rendering and tenant-aware options.
- UX copy for no-email recovery constraints.

Exit Criteria:
- Admin workflows complete without direct DB intervention.
- Login UX validated for all policy modes.

---

### Phase 4: Password Hardening and Consistency (3-5 days)

Status: Completed

Deliverables:
- Shared password policy validator enforced across all password entry points.
- Updated invite acceptance and change-password behavior.
- Regression coverage for lockout, policy errors, and reuse checks.

Exit Criteria:
- No known path can set weak password outside policy.

---

### Phase 5: Security Hardening, Audit, and Rollout (4-7 days)

Status: Completed

Deliverables:
- Audit events for config/login mode/method changes.
- Runbooks for lockout recovery and emergency disable.
- Staged rollout plan (internal tenant -> pilot tenants -> broader release).

Exit Criteria:
- Pilot tenants authenticated successfully with low incident rate.
- Rollback and break-glass procedures validated.

---

## Open Questions

None at PRD level for Phase 1 start. Remaining protocol and JIT defaults have been decided.

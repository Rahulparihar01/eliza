# Technical Specification
## Tenant SSO and Password Hardening

| Field | Value |
|---|---|
| Version | 1.0 |
| Status | Implemented (MVP) |
| Last Updated | February 18, 2026 |
| Feature Folder | `features/backlog/tenant-sso-and-password-hardening/` |

---

## 1. Scope and Decisions

This implementation covers all planned phases for MVP:

1. Tenant-scoped SSO configuration and platform governance controls.
2. Runtime auth integration for password + OIDC + SAML.
3. Frontend admin and login UX for SSO.
4. Password hardening consistency across password entry points.
5. Audit logging and operational controls (including break-glass behavior).

Confirmed product decisions applied:

- One provider per tenant (MVP).
- OIDC and SAML support both included.
- JIT provisioning default OFF.
- If JIT enabled, default role is `viewer`.
- Password baseline: minimum 8 characters + composition via shared security policy.

---

## 2. Data Model

### 2.1 `tenant_sso_configs`

Purpose: tenant-level SSO policy and provider config.

Key fields:

- `customer_id` (unique, FK to customers)
- `is_enabled`
- `login_mode` (`password_only`, `sso_optional`, `sso_enforced`)
- `provider_type` (`azure`, `okta`, `google`, `generic`)
- `protocol` (`oidc`, `saml`)
- `domain_allowlist` (JSON array)
- `domain_verification_required`
- `jit_provisioning_enabled`
- `jit_default_role`
- `config_data` (non-secret provider settings)
- `secret_data_encrypted` (encrypted secret payload)
- `last_test_*` fields for config test telemetry

### 2.2 `user_sso_identities`

Purpose: stable link from external IdP identity to internal user.

Key fields:

- `user_id` (FK to users)
- `customer_id` (tenant scope)
- `provider_type`, `protocol`
- `external_subject`
- `external_email`
- `claims_snapshot`
- `last_login_at`

Constraints:

- Unique external identity per tenant/provider/protocol.
- Unique user-provider mapping per tenant/provider/protocol.

### 2.3 Platform Feature Seed

Migration seeds/updates `platform_features.feature_key = 'sso_authentication'` to support tenant feature allocation gating.

---

## 3. Configuration and Policy Services

### 3.1 Tenant Settings Service

`TenantSSOSettingsService` handles:

- `GET`/`PUT` settings CRUD
- Secret encryption for OIDC secret and SAML certificate
- Resetting test metadata on config updates
- `test_settings()` connectivity/metadata checks

### 3.2 Platform Policy Service

`PlatformSSOPolicyService` handles system settings keys:

- `sso.global_enabled`
- `sso.allowed_provider_types`
- `sso.allow_tenant_enforced_mode`
- `sso.require_domain_verification_for_enforced_mode`
- `sso.break_glass_enabled`
- `sso.break_glass_allowed_user_emails`
- `sso.jit_provisioning_default`
- `sso.default_password_policy_profile`

---

## 4. Runtime Auth Architecture

`TenantSSORuntimeService` provides runtime policy resolution and protocol logic.

### 4.1 Tenant Resolution

Resolution order:

1. Existing user + tenant memberships (default membership preference).
2. Explicit `customer_id` hint (if provided).
3. Domain allowlist match from configured SSO tenants.

If ambiguous, runtime returns deterministic error instead of guessing.

### 4.2 Password Login Enforcement

Before password auth, `/v1/auth/login` checks tenant policy:

- `password_only` or `sso_optional`: password allowed.
- `sso_enforced`: password blocked unless break-glass allowed.

Break-glass allow criteria:

- Platform break-glass is enabled.
- Email is in break-glass allowlist OR user has platform admin permission.

### 4.3 OIDC Flow

Endpoints:

- `GET /v1/auth/sso/oidc/start`
- `GET /v1/auth/sso/oidc/callback`

Flow:

1. Resolve tenant + validate active OIDC config.
2. Discover OIDC metadata via `.well-known/openid-configuration`.
3. Build authorize URL with signed state + nonce.
4. Callback exchanges code at token endpoint.
5. Validate ID token via JWKS + audience + issuer + nonce.
6. Link/provision user, issue local session tokens, redirect to frontend callback.

### 4.4 SAML Flow

Endpoints:

- `GET /v1/auth/sso/saml/start`
- `POST /v1/auth/sso/saml/acs`

Flow:

1. Resolve tenant + validate active SAML config.
2. Generate AuthnRequest + RelayState (signed state token).
3. Redirect to IdP SSO URL.
4. ACS decodes response, validates status/time/audience, extracts identity claims.
5. Link/provision user, issue local session tokens, redirect to frontend callback.

Note:

- SAML parser validates structure/time/audience.
- Strict XML signature verification is a recommended hardening follow-up.

### 4.5 User Linking + JIT

User resolution order:

1. `user_sso_identities` match by subject.
2. Existing user by normalized email.
3. JIT create user if enabled.

JIT behavior:

- Generates strong system password.
- Creates tenant membership.
- Assigns configured JIT role, fallback to `viewer`.
- Updates active tenant context for session issuance.

---

## 5. API Endpoints

### 5.1 Public Auth Endpoints

- `GET /v1/auth/sso/options`
- `GET /v1/auth/sso/oidc/start`
- `GET /v1/auth/sso/oidc/callback`
- `GET /v1/auth/sso/saml/start`
- `POST /v1/auth/sso/saml/acs`

### 5.2 Tenant Admin Endpoints

- `GET /api/v1/tenant-settings/sso`
- `PUT /api/v1/tenant-settings/sso`
- `POST /api/v1/tenant-settings/sso/test`

### 5.3 Platform Admin Endpoints

- `GET /api/v1/platform-admin/auth/sso-policy`
- `PUT /api/v1/platform-admin/auth/sso-policy`

---

## 6. Frontend Changes

### 6.1 Login

`LoginPage` now supports:

- Tenant policy discovery (`/v1/auth/sso/options`)
- SSO button launch (OIDC/SAML)
- Password form disable when enforced mode requires SSO

### 6.2 SSO Callback

`/auth/sso/callback` page:

- Reads access/refresh tokens from URL fragment
- Stores tokens in local auth storage
- Refreshes user context and redirects to `/home`

### 6.3 Tenant Admin

`/tenant-admin/sso`:

- Full SSO policy/provider configuration form
- OIDC and SAML config sections
- Test configuration action

### 6.4 Platform Admin

`/platform-admin/sso-policy`:

- Global SSO governance controls
- Provider allowlist
- Break-glass and defaults

Navigation and route wiring updated in:

- `frontend/src/App.tsx`
- `frontend/src/components/navigation/sectionConfigs.ts`
- `frontend/src/components/navigation/platformAdminNav.ts`

---

## 7. Password Hardening

Shared policy is enforced in:

- Invite acceptance (`/v1/auth/invite/accept`)
- User creation (`/v1/auth/users` via `auth_service.create_user`)
- Change password (`/v1/auth/me/password`)

Policy uses `SecurityService.validate_password_policy` with:

- Min length 8
- Upper/lower/digit/special character requirements
- Common password checks
- Password history checks where user context is available

---

## 8. Auditing and Operations

Added audit coverage for:

- Tenant SSO settings changes
- Tenant SSO config test results
- Platform SSO policy updates
- Password auth method tagging (`auth_method=password`)
- SSO login method tagging (`auth_method=sso`, protocol/provider metadata)

Operational controls implemented:

- Platform global SSO kill switch
- Tenant feature allocation gating (`sso_authentication`)
- Break-glass local login policy for enforced mode

---

## 9. Portability and Deployment

Design remains cloud-portable:

- Standards-based OIDC/SAML only
- Secret encryption at app layer
- No dependence on cloud-specific auth SDKs
- Works behind Northflank ingress and any cloud with URL/env configuration

No email server dependency introduced.

---

## 10. Validation Executed

Completed validation in this implementation pass:

- Python compile checks for changed backend modules
- Frontend production build (`npm --prefix frontend run build`)

Build succeeds; repository-wide pre-existing lint warnings remain outside this feature scope.

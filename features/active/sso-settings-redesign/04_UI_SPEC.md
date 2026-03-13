# SSO Settings Page — UI Specification

| **Status** | In Progress (v2 — tabs approach) |
|------------|-------|
| **Date** | February 23, 2026 |
| **Relates to** | `features/active/sso-settings-redesign/PLAN.md` |
| **Route** | `/tenant-admin/sso` |

---

## Design Philosophy

**Status-first, tabs for depth.**

The page opens with a slim status bar that answers "what is the current state of SSO?" in one glance. Below, three tabs provide full-width editing surfaces for each concern: Login Policy, Verified Domains, and SSO Providers.

This replaces the earlier sheet-based approach, which suffered from a density mismatch: the Providers form was too dense for a slide-in panel, while the Policy form was too sparse. Tabs give each section the exact space it needs — full page width for the master-detail provider layout, a compact area for the three policy radio buttons.

### Key decisions

- **No separate readiness checklist.** Readiness is folded into the status bar badges themselves. A warning badge on "Domains: 0/1 pending" already communicates "action needed" without a dedicated card that becomes dead weight after day 1.
- **Destructive confirmations use centered modals.** Since everything is on-page (no sheet layering), modals are the simplest and most standard approach.
- **Status bar segments are clickable tab triggers.** If a user sees a warning on the Domains segment, clicking it jumps to the Domains tab.

---

## Page Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PageHeader: "SSO Settings"                                             │
│  description: "Manage login policy, identity providers, and domains."   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─── Status Bar (slim, single row) ──────────────────────────────────┐ │
│  │  [Policy: SSO optional]  [Domains: 1/1 ✓]  [Providers: 1 active]  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─── Tabs ───────────────────────────────────────────────────────────┐ │
│  │  [ Login Policy ]  [ Verified Domains ]  [ SSO Providers ]         │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │                                                                     │ │
│  │  (Selected tab content at full page width)                          │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Status Bar

A single horizontal strip with 3 segments. Each segment shows a label, a value, and a status badge. Clicking a segment switches the active tab.

### Layout

```
┌────────────────────┬────────────────────┬────────────────────┐
│  Login Policy      │  Verified Domains  │  SSO Providers     │
│  [SSO optional]    │  [1/1 ✓]           │  [1 active]        │
└────────────────────┴────────────────────┴────────────────────┘
```

Three equal-width segments in a `grid-cols-3` with subtle borders between them. The active segment has a highlighted bottom border or background tint matching the active tab.

### Segment details

| Segment | Badge variant | Badge text | Condition |
|---------|--------------|------------|-----------|
| Policy | `secondary` | "Password only" | `password_only` |
| Policy | `info` | "SSO optional" | `sso_optional` |
| Policy | `brand` | "SSO enforced" | `sso_enforced` |
| Domains | `success` | "{verified}/{total} ✓" | ≥ 1 verified |
| Domains | `warning` | "{total} pending" | domains exist, none verified |
| Domains | `secondary` | "none" | no domains |
| Providers | `success` | "{N} active" | ≥ 1 enabled |
| Providers | `warning` | "{N} not tested" | enabled but none tested |
| Providers | `secondary` | "none" | no providers |

---

## Tab 1: Login Policy

The lightest tab. Radio cards for login mode selection, conditional alerts, and a save button.

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  How should users in this tenant authenticate?                       │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ○ Password only                                                 │ │
│  │   SSO providers are inactive. Users sign in with email          │ │
│  │   and password.                                                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ● SSO optional                                                  │ │
│  │   Users can choose SSO or password at the login page.           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ○ SSO enforced                                                  │ │
│  │   Password login is blocked for all users except break-glass    │ │
│  │   admin recovery.                                               │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  IF sso_enforced + no verified domain:                               │
│    Alert(warning): "Enforcing SSO requires a verified domain."       │
│  IF sso_enforced + no enabled provider:                              │
│    Alert(warning): "Enforcing SSO requires an enabled provider."     │
│                                                                      │
│  [Save Policy]  (disabled when blocked or unchanged)                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Max width

Constrain the radio cards to `max-w-xl` so they don't stretch absurdly wide on large screens. The tab body remains left-aligned.

### Save behavior

- **Non-destructive** (e.g. `password_only` → `sso_optional`): Save immediately.
- **Destructive** (see Confirmation Modals below): Intercept with a centered `Modal`.

---

## Tab 2: Verified Domains

Medium-density tab. Domain add/verify/remove with DNS instructions.

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Add and verify domains via DNS TXT records before enforcing SSO.    │
│                                                                      │
│  ┌───────────────────────────────────────┐                           │
│  │ [acme.com_______________] [Add Domain]│                           │
│  └───────────────────────────────────────┘                           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  acme.com                                    [verified ✓]       │ │
│  │  TXT: eliza-domain-verify=t_abc123xyz789  [📋]                 │ │
│  │  ▸ DNS setup instructions (expand)                              │ │
│  │  [Re-verify]  [Remove]                                          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  eu.acme.com                                 [pending ⏳]       │ │
│  │  TXT: eliza-domain-verify=t_def456...     [📋]                 │ │
│  │  ▸ DNS setup instructions (expand)                              │ │
│  │  [Verify]  [Remove]                                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Empty state: Alert(neutral) "No domains yet."                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Max width

Constrain domain cards to `max-w-2xl`.

### Remove domain behavior

- Removing the last verified domain while `sso_enforced`: show `ConfirmationModal` warning.
- Otherwise: remove immediately with toast.

---

## Tab 3: SSO Providers

The heaviest tab. Full-width master-detail layout.

### Layout

```
┌────────────────────────────┬────────────────────────────────────────────┐
│  Providers                 │  Configure: Google SSO (OIDC)              │
│                            │                                            │
│  ┌──────────────────────┐  │  Provider Type: [Google Workspace ▾]       │
│  │ ✅ Google SSO        │←─│  Protocol: [OIDC ▾]                       │
│  │    oidc · tested ✓   │  │  Display Name: [Google SSO___________]     │
│  └──────────────────────┘  │                                            │
│  ┌──────────────────────┐  │  ☑ Enable this provider                    │
│  │ ○ Okta               │  │  ☐ Enable JIT provisioning                 │
│  │    oidc · disabled    │  │  JIT Default Role: [viewer ▾]              │
│  └──────────────────────┘  │                                            │
│                            │  ── OIDC Configuration ──────────────────  │
│  [+ Add Provider]          │  Issuer URL:    [https://accounts.goo...] │
│                            │  Client ID:     [1234593386...          ] │
│                            │  Client Secret: [••••••••] (stored) ✅    │
│                            │  Scopes:        [openid, profile, email]  │
│                            │                                            │
│                            │  ── Setup Guide ─────────────────────────  │
│                            │  (provider-specific instructions + links)  │
│                            │                                            │
│                            │  ── Last Test ───────────────────────────  │
│                            │  Alert: "success — No errors reported."    │
│                            │                                            │
│                            │  [Test]  [Save Provider]      [Delete]    │
└────────────────────────────┴────────────────────────────────────────────┘
```

### Grid layout

`grid-cols-[280px_1fr]` — provider list on the left, detail form on the right. On `< md` screens, stack vertically.

### Provider list (left panel)

- "+" Add Provider" button at top.
- Each provider is a selectable card showing: display name or `{type} ({protocol})`, enabled/disabled badge, test status indicator.
- Active provider has highlighted border.

### Detail form (right panel)

- Provider type + protocol selectors (disabled for existing providers — type/protocol are identity).
- Display name, enable toggle, JIT toggle + role.
- Protocol-specific fields section (OIDC or SAML).
- Setup guide (provider-specific, inline info panel).
- Last test result (Alert).
- Action buttons at bottom: Test, Save Provider, Delete (right-aligned, destructive style).

### Add Provider flow

1. Click "+ Add Provider" → detail panel shows blank form.
2. Select provider type + protocol.
3. Fill fields, click "Save Provider" → `POST`.
4. New provider appears in list, auto-selected.

### Delete Provider flow

- Click "Delete" → `ConfirmationModal`.
- If last enabled provider with active SSO policy → extra warning in modal.

### Switching providers with unsaved changes

- If form is dirty and user clicks a different provider → `ConfirmationModal` for unsaved changes.
- "Discard" switches, "Go Back" stays.

---

## Confirmation Modals

All destructive or security-sensitive mutations use centered `Modal` components. Since everything is on-page (no sheets), there are no z-index stacking concerns.

### Reusable ConfirmationModal component

```typescript
interface ConfirmationModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  body: string;
  bullets?: string[];
  confirmLabel: string;
  confirmVariant: 'default' | 'destructive';
  requireTypedConfirmation?: string;
  isLoading?: boolean;
}
```

### Modal 1: Enforce SSO

| Field | Value |
|-------|-------|
| **Trigger** | Save policy as `sso_enforced` from any other mode |
| **Title** | "Enforce SSO for all users?" |
| **Body** | "This will immediately block password-based login for all users in this tenant." |
| **Bullets** | Active sessions unaffected; unlinked users locked out; break-glass available |
| **Typed confirmation** | `"enforce"` |
| **Confirm button** | "Enforce SSO" (destructive, disabled until typed match) |

### Modal 2: Disable SSO

| Field | Value |
|-------|-------|
| **Trigger** | Save policy as `password_only` from `sso_optional` or `sso_enforced` |
| **Title** | "Disable SSO?" |
| **Body** | "SSO-only users will need a password reset. Provider configs are preserved but inactive." |
| **Confirm button** | "Switch to Password Only" (destructive) |

### Modal 3: Downgrade to Optional

| Field | Value |
|-------|-------|
| **Trigger** | Save policy as `sso_optional` from `sso_enforced` |
| **Title** | "Allow password logins again?" |
| **Body** | "Users will be able to choose SSO or password. SSO providers remain active." |
| **Confirm button** | "Allow Passwords" (default) |

### Modal 4: Delete Provider

| Field | Value |
|-------|-------|
| **Trigger** | Click "Delete" on a provider |
| **Title** | "Delete {provider name}?" |
| **Body** | "This permanently removes this provider." |
| **Extra warning** | If last enabled provider + active SSO: "SSO will stop working." |
| **Confirm button** | "Delete Provider" (destructive) |

### Modal 5: Remove Last Verified Domain (while enforced)

| Field | Value |
|-------|-------|
| **Trigger** | Remove last verified domain while `sso_enforced` |
| **Title** | "Remove last verified domain?" |
| **Body** | "Enforced SSO requires a verified domain. Your login policy will need to change." |
| **Confirm button** | "Remove Domain" (destructive) |

### Modal 6: Unsaved Changes

| Field | Value |
|-------|-------|
| **Trigger** | Switch providers or leave tab with dirty form |
| **Title** | "You have unsaved changes" |
| **Body** | "Your changes to {context} haven't been saved. Discard?" |
| **Buttons** | "Go Back" (secondary) / "Discard Changes" (destructive) |

---

## Unsaved Changes Guard

### Tab switching

When the user switches tabs while the Providers tab has unsaved changes:
- Show Modal 6.
- "Go Back" cancels the tab switch. "Discard" resets the form and switches.

### Provider switching (within Providers tab)

When the detail form is dirty and user clicks a different provider:
- Show Modal 6.
- Same behavior as tab switching.

### Browser navigation

```typescript
useEffect(() => {
  const handler = (e: BeforeUnloadEvent) => {
    if (isDirty) {
      e.preventDefault();
      e.returnValue = '';
    }
  };
  window.addEventListener('beforeunload', handler);
  return () => window.removeEventListener('beforeunload', handler);
}, [isDirty]);
```

### Dirty detection

| Context | Dirty when |
|---------|-----------|
| Login Policy tab | `localMode !== savedMode` |
| Domains tab | Never dirty (all actions are immediate) |
| Providers tab | Any field in `providerForm` differs from the loaded `ProviderResponse` |

---

## Component Hierarchy

```
SsoSettingsPage.tsx (page shell — status bar + tabs)
├── SsoStatusBar.tsx (slim 3-segment strip, clickable)
│
├── PolicyTab.tsx (radio cards + conditional alerts + save)
├── DomainsTab.tsx (domain CRUD + expandable DNS instructions)
├── ProvidersTab.tsx (master-detail, full page width)
│   ├── Provider list (left, 280px)
│   └── Provider detail form (right)
│
├── ConfirmationModal.tsx (reusable for all 6 confirmation types)
│
└── Shared:
    ├── types.ts
    ├── constants.ts
    └── useUnsavedChangesGuard.ts
```

---

## Design System Components Used

| Component | Usage |
|-----------|-------|
| `Page`, `PageHeader`, `PageBody` | Page scaffold |
| `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` | Three-tab layout |
| `Card` | Provider list items, domain cards |
| `Badge` | Status indicators in status bar and throughout |
| `Button` | All actions |
| `Modal`, `ModalContent`, `ModalHeader`, `ModalTitle`, `ModalBody`, `ModalFooter` | Confirmation dialogs |
| `RadioGroup`, `RadioCard` | Login mode selection |
| `Select`, `SelectOption` | Provider type, protocol, JIT role |
| `Input` | Text fields |
| `Textarea` | SAML cert |
| `Checkbox` | Enable provider, enable JIT |
| `Alert` | Warnings, info, validation messages |
| `Spinner` | Loading states |

---

## Data Flow

### Page load

```
SsoSettingsPage mounts
  → GET /api/v1/tenant-settings/sso/policy     → policyData
  → GET /api/v1/tenant-settings/sso/providers   → providersData
  → GET /api/v1/tenant-settings/sso/domains      → domainsData
  → Render status bar + default tab (Login Policy) from responses
```

### Policy save

```
User selects new login mode → clicks "Save Policy"
  → IF destructive → ConfirmationModal
    → User confirms → PUT /api/v1/tenant-settings/sso/policy
  → ELSE → PUT /api/v1/tenant-settings/sso/policy
  → On success: toast, refetch all, status bar updates
```

### Provider save/delete

```
User edits provider form → clicks "Save Provider"
  → IF selectedId → PUT /api/v1/.../providers/{id}
  → ELSE → POST /api/v1/.../providers
  → On success: toast, refetch providers

User clicks "Delete" → ConfirmationModal
  → Confirm → DELETE /api/v1/.../providers/{id}
  → Refetch, select next provider or blank
```

---

## Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| `< md` | Status bar stacks vertically (3 rows). Provider master-detail stacks (list above detail). |
| `md` – `lg` | Status bar horizontal. Provider list narrower (220px). |
| `≥ lg` | Full 3-segment status bar. Provider list 280px + full detail. |

---

## Files to create/modify

### New files

| File | Purpose |
|------|---------|
| `sso/SsoStatusBar.tsx` | Slim 3-segment status strip with clickable tab triggers |
| `sso/PolicyTab.tsx` | Login mode radio cards + save + inline alerts |
| `sso/DomainsTab.tsx` | Domain add/verify/remove + DNS instructions |
| `sso/ProvidersTab.tsx` | Full-width master-detail provider editor |
| `sso/ConfirmationModal.tsx` | Reusable modal for all destructive confirmations |

### Modified files

| File | Change |
|------|--------|
| `SsoSettingsPage.tsx` | Rewrite: status bar + Tabs + tab content components |

### Retained from v1

| File | Status |
|------|--------|
| `sso/types.ts` | Keep as-is |
| `sso/constants.ts` | Keep as-is |
| `sso/useUnsavedChangesGuard.ts` | Keep, minor updates for tab-switch interception |

### Deleted (replaced by tabs)

| File | Reason |
|------|--------|
| `sso/SsoSummaryCards.tsx` | Replaced by `SsoStatusBar.tsx` |
| `sso/SsoStatusCard.tsx` | Readiness folded into status bar badges |
| `sso/PolicySheet.tsx` | Replaced by `PolicyTab.tsx` |
| `sso/DomainsSheet.tsx` | Replaced by `DomainsTab.tsx` |
| `sso/ProvidersSheet.tsx` | Replaced by `ProvidersTab.tsx` |

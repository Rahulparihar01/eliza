export type LoginMode = 'password_only' | 'sso_optional' | 'sso_enforced';
export type Protocol = 'oidc' | 'saml' | '';
export type ProviderType = 'azure' | 'okta' | 'google' | 'generic' | '';

export interface PolicyResponse {
  login_mode: LoginMode;
  domain_verification_required: boolean;
}

export interface DomainResponse {
  id: number;
  domain: string;
  verification_token: string;
  status: 'pending' | 'verified' | 'failed';
  verified_at: string | null;
  last_check_error: string | null;
}

export interface ProviderResponse {
  id: number;
  provider_type: ProviderType;
  protocol: Protocol;
  display_name: string | null;
  is_enabled: boolean;
  jit_provisioning_enabled: boolean;
  jit_default_role: string;
  oidc_issuer_url: string | null;
  oidc_client_id: string | null;
  oidc_scopes: string[];
  has_oidc_client_secret: boolean;
  saml_entity_id: string | null;
  saml_sso_url: string | null;
  saml_metadata_url: string | null;
  has_saml_x509_cert: boolean;
  last_test_status: string | null;
  last_test_error: string | null;
}

export interface ProviderForm {
  provider_type: ProviderType;
  protocol: Protocol;
  display_name: string;
  is_enabled: boolean;
  jit_provisioning_enabled: boolean;
  jit_default_role: string;
  oidc_issuer_url: string;
  oidc_client_id: string;
  oidc_client_secret: string;
  oidc_scopes_text: string;
  saml_entity_id: string;
  saml_sso_url: string;
  saml_metadata_url: string;
  saml_x509_cert: string;
  has_oidc_client_secret: boolean;
  has_saml_x509_cert: boolean;
  last_test_status: string | null;
  last_test_error: string | null;
}

export function blankProviderForm(): ProviderForm {
  return {
    provider_type: '',
    protocol: '',
    display_name: '',
    is_enabled: true,
    jit_provisioning_enabled: false,
    jit_default_role: 'viewer',
    oidc_issuer_url: '',
    oidc_client_id: '',
    oidc_client_secret: '',
    oidc_scopes_text: 'openid, profile, email',
    saml_entity_id: '',
    saml_sso_url: '',
    saml_metadata_url: '',
    saml_x509_cert: '',
    has_oidc_client_secret: false,
    has_saml_x509_cert: false,
    last_test_status: null,
    last_test_error: null,
  };
}

export function providerFormFromResponse(p: ProviderResponse): ProviderForm {
  return {
    provider_type: p.provider_type || '',
    protocol: p.protocol || '',
    display_name: p.display_name || '',
    is_enabled: p.is_enabled,
    jit_provisioning_enabled: p.jit_provisioning_enabled,
    jit_default_role: p.jit_default_role || 'viewer',
    oidc_issuer_url: p.oidc_issuer_url || '',
    oidc_client_id: p.oidc_client_id || '',
    oidc_client_secret: '',
    oidc_scopes_text: (p.oidc_scopes || ['openid', 'profile', 'email']).join(', '),
    saml_entity_id: p.saml_entity_id || '',
    saml_sso_url: p.saml_sso_url || '',
    saml_metadata_url: p.saml_metadata_url || '',
    saml_x509_cert: '',
    has_oidc_client_secret: p.has_oidc_client_secret,
    has_saml_x509_cert: p.has_saml_x509_cert,
    last_test_status: p.last_test_status,
    last_test_error: p.last_test_error,
  };
}

export function getApiErrorMessage(error: any, fallback: string): string {
  const detail =
    error?.response?.data?.detail ??
    error?.response?.data?.message ??
    error?.message;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: any) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const msg = typeof item.msg === 'string' ? item.msg : null;
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : null;
          if (msg && loc) return `${loc}: ${msg}`;
          if (msg) return msg;
          try { return JSON.stringify(item); } catch { return String(item); }
        }
        return String(item);
      })
      .filter(Boolean);
    return messages.length > 0 ? messages.join(' | ') : fallback;
  }

  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message;
    try { return JSON.stringify(detail); } catch { return fallback; }
  }

  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}

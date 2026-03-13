import type { LoginMode, Protocol, ProviderType } from './types';

export interface SetupGuide {
  title: string;
  summary: string;
  steps: string[];
  valuesToCollect: string[];
  links: Array<{ label: string; href: string }>;
}

export const LOGIN_MODE_OPTIONS: Array<{ value: LoginMode; label: string; description: string }> = [
  {
    value: 'password_only',
    label: 'Password only',
    description: 'SSO providers are inactive. Users sign in with email and password.',
  },
  {
    value: 'sso_optional',
    label: 'SSO optional',
    description: 'Users can choose SSO or password at the login page.',
  },
  {
    value: 'sso_enforced',
    label: 'SSO enforced',
    description: 'Password login is blocked for all users except break-glass admin recovery.',
  },
];

export const LOGIN_MODE_LABELS: Record<LoginMode, string> = {
  password_only: 'Password only',
  sso_optional: 'SSO optional',
  sso_enforced: 'SSO enforced',
};

export const PROVIDER_OPTIONS: Array<{ value: ProviderType; label: string }> = [
  { value: '', label: 'Select provider' },
  { value: 'azure', label: 'Azure / Entra ID' },
  { value: 'okta', label: 'Okta' },
  { value: 'google', label: 'Google Workspace' },
  { value: 'generic', label: 'Generic' },
];

export const PROTOCOL_OPTIONS: Array<{ value: Protocol; label: string }> = [
  { value: '', label: 'Select protocol' },
  { value: 'oidc', label: 'OIDC' },
  { value: 'saml', label: 'SAML' },
];

export const JIT_ROLE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'viewer', label: 'viewer' },
  { value: 'analyst', label: 'analyst' },
  { value: 'manager', label: 'manager' },
  { value: 'admin', label: 'admin' },
];

export const PROVIDER_SETUP_GUIDES: Record<Exclude<ProviderType, ''>, SetupGuide> = {
  azure: {
    title: 'Azure / Entra ID setup',
    summary: 'Register an app in Entra ID, then copy the IdP values into this form.',
    steps: [
      'Create an Enterprise App or App Registration for this product.',
      'Configure redirect/assertion endpoints based on protocol (OIDC callback or SAML ACS).',
      'Assign test users/groups and verify the app can issue claims.',
    ],
    valuesToCollect: [
      'OIDC: issuer URL, client ID, client secret',
      'SAML: IdP sign-on URL, certificate (and metadata URL if available)',
    ],
    links: [
      { label: 'Create enterprise app', href: 'https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/add-application-portal' },
      { label: 'Configure OIDC in Entra', href: 'https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc' },
      { label: 'Configure SAML SSO in Entra', href: 'https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/add-application-portal-setup-sso' },
    ],
  },
  okta: {
    title: 'Okta setup',
    summary: 'Use Okta App Integration Wizard and copy the generated IdP values into this form.',
    steps: [
      'Create a new App Integration for either OIDC or SAML.',
      'Set callback/ACS URLs and audience as required by the selected protocol.',
      'Assign a test user and run a provider-side sign-in test.',
    ],
    valuesToCollect: [
      'OIDC: issuer URL (for example /oauth2/default), client ID, client secret',
      'SAML: IdP sign-on URL, X.509 certificate, optional metadata URL',
    ],
    links: [
      { label: 'App Integration Wizard overview', href: 'https://help.okta.com/oie/en-us/content/topics/apps/apps_app_integration_wizard.htm' },
      { label: 'OIDC app setup (Okta)', href: 'https://help.okta.com/oie/en-us/content/topics/apps/apps_app_integration_wizard_oidc.htm' },
      { label: 'SAML app setup (Okta)', href: 'https://help.okta.com/oie/en-us/content/topics/apps/apps_app_integration_wizard_saml.htm' },
    ],
  },
  google: {
    title: 'Google Workspace setup',
    summary: 'Create credentials in Google admin/cloud console, then copy the required values to Eliza.',
    steps: [
      'For OIDC, create a Web OAuth client and add your callback URL.',
      'For SAML, create a custom SAML app in Google Admin and map attributes.',
      'Assign users/groups and validate with a non-admin test account.',
    ],
    valuesToCollect: [
      'OIDC: issuer URL (https://accounts.google.com), client ID, client secret',
      'SAML: SSO URL and signing certificate from the custom SAML app',
    ],
    links: [
      { label: 'Google OpenID Connect', href: 'https://developers.google.com/identity/openid-connect/openid-connect' },
      { label: 'OAuth 2.0 Web app credentials', href: 'https://developers.google.com/identity/protocols/oauth2/web-server' },
      { label: 'Custom SAML app in Google Workspace', href: 'https://support.google.com/a/answer/6087519?hl=en' },
    ],
  },
  generic: {
    title: 'Generic provider setup',
    summary: 'Use any standards-compliant IdP. Collect protocol-specific values and validate claims.',
    steps: [
      'Create an app in your IdP for OIDC or SAML.',
      'Configure redirect/ACS endpoints and audience/entity identifiers.',
      'Map required user claims (email at minimum) before enabling for users.',
    ],
    valuesToCollect: [
      'OIDC: issuer URL, client ID, client secret, and required scopes',
      'SAML: IdP SSO URL, X.509 cert, optional metadata URL',
    ],
    links: [
      { label: 'OpenID Connect core spec', href: 'https://openid.net/specs/openid-connect-core-1_0.html' },
      { label: 'SAML v2.0 specifications', href: 'https://docs.oasis-open.org/security/saml/v2.0/' },
    ],
  },
};

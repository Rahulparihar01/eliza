/**
 * Login Page - Eliza Forge
 *
 * Authentication page with branded SSO discovery buttons, progressive
 * password disclosure, and tenant policy-aware SSO refinement.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Navigate, Link, useSearchParams } from 'react-router-dom';
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import { useAuth } from '../../contexts/AuthContext';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { Button, Input, Checkbox, Label, Alert, Spinner } from '../../components/ui';

const API_BASE =
  process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function completeMcpOAuthFlow(sessionKey: string, accessToken: string): Promise<string> {
  const res = await fetch(`${API_BASE}/mcp/oauth/authorize/complete`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ session: sessionKey }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error_description || 'Failed to complete MCP authorization.');
  }
  const data = await res.json();
  return data.redirect_url;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DiscoveryProvider {
  id: number;
  provider_type: string | null;
  protocol: 'oidc' | 'saml' | null;
  display_name: string | null;
}

interface SsoLoginOptions {
  email: string;
  customer_id: string | null;
  customer_name: string | null;
  login_mode: 'password_only' | 'sso_optional' | 'sso_enforced';
  sso_login_available: boolean;
  password_login_allowed: boolean;
  requires_sso: boolean;
  break_glass_allowed: boolean;
  provider_type: string | null;
  protocol: 'oidc' | 'saml' | null;
  provider_display_name: string | null;
  provider_id: number | null;
  providers: Array<{
    id: number;
    provider_type: string | null;
    protocol: 'oidc' | 'saml' | null;
    provider_display_name: string | null;
    is_enabled: boolean;
  }>;
}

// ---------------------------------------------------------------------------
// Provider icon + label helpers
// ---------------------------------------------------------------------------

const PROVIDER_ICONS: Record<string, string> = {
  google: '/icons/sso/google.svg',
  okta: '/icons/sso/okta_dark.svg',
  azure_ad: '/icons/sso/microsoft.svg',
  microsoft: '/icons/sso/microsoft.svg',
};

function ProviderIcon({ providerType }: { providerType: string | null }) {
  const src = PROVIDER_ICONS[providerType ?? ''];
  if (!src) return null;
  return <img src={src} alt="" className="h-5 w-5 shrink-0" />;
}

function providerLabel(
  providerType: string | null,
  displayName: string | null,
): string {
  switch (providerType) {
    case 'google':
      return 'Continue with Google';
    case 'okta':
      return `Continue with ${displayName || 'Okta'}`;
    case 'azure_ad':
    case 'microsoft':
      return `Continue with ${displayName || 'Microsoft'}`;
    default:
      return `Continue with ${displayName || 'SSO'}`;
  }
}

// ---------------------------------------------------------------------------
// LoginPage
// ---------------------------------------------------------------------------

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember_me: false,
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [startingSsoProviderId, setStartingSsoProviderId] = useState<number | null>(null);
  const [isCheckingSso, setIsCheckingSso] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [mcpOAuthSession] = useState<string | null>(
    () => searchParams.get('mcp_oauth_session'),
  );
  const [isCompletingOAuth, setIsCompletingOAuth] = useState(false);

  // Discovery: fetched on mount (all deployment-wide SSO providers)
  const [discoveryProviders, setDiscoveryProviders] = useState<DiscoveryProvider[]>([]);
  const [discoveryLoaded, setDiscoveryLoaded] = useState(false);

  // Email-resolved options (fetched on email blur)
  const [ssoOptions, setSsoOptions] = useState<SsoLoginOptions | null>(null);

  // ---- Startup: message from redirect & SSO discovery ----

  useEffect(() => {
    const message = searchParams.get('message');
    if (message) {
      setLoginError(message);
    }
  }, [searchParams]);

  const emailIsValid = EMAIL_REGEX.test(formData.email.trim());

  const checkSsoOptions = useCallback(
    async (
      options: { showErrors?: boolean } = {},
    ): Promise<SsoLoginOptions | null> => {
      if (!emailIsValid) {
        if (options.showErrors) setLoginError('Enter a valid email first.');
        return null;
      }

      setIsCheckingSso(true);
      try {
        const response = await AXIOS_INSTANCE.get<SsoLoginOptions>(
          '/v1/auth/sso/options',
          { params: { email: formData.email.trim().toLowerCase() } },
        );
        setSsoOptions(response.data);
        return response.data;
      } catch (error: any) {
        if (options.showErrors) {
          const detail = error?.response?.data?.detail;
          let message = 'Unable to fetch SSO options for this email.';
          if (typeof detail === 'string') {
            message = detail;
          } else if (Array.isArray(detail)) {
            message = detail.map((d: any) => (typeof d === 'string' ? d : d?.msg || 'Validation error')).join('. ');
          }
          setLoginError(message);
        }
        return null;
      } finally {
        setIsCheckingSso(false);
      }
    },
    [emailIsValid, formData.email],
  );

  useEffect(() => {
    let cancelled = false;
    AXIOS_INSTANCE.get<{ providers: DiscoveryProvider[] }>('/v1/auth/sso/discovery')
      .then((res) => {
        if (!cancelled) {
          setDiscoveryProviders(res.data.providers ?? []);
          setDiscoveryLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) setDiscoveryLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // If already authenticated and this is an OAuth flow, complete it immediately.
  // Uses a ref to prevent retry loops: once attempted (success or failure), don't re-fire.
  const oauthAttempted = useRef(false);
  useEffect(() => {
    if (!isAuthenticated || !mcpOAuthSession || oauthAttempted.current) return;
    oauthAttempted.current = true;
    setIsCompletingOAuth(true);
    const token = localStorage.getItem('auth_token');
    if (!token) {
      setLoginError('No auth token found. Please log in again.');
      setIsCompletingOAuth(false);
      return;
    }
    completeMcpOAuthFlow(mcpOAuthSession, token)
      .then((url) => { window.location.href = url; })
      .catch((err) => {
        setLoginError(err.message || 'Failed to complete MCP authorization.');
        setIsCompletingOAuth(false);
      });
  }, [isAuthenticated, mcpOAuthSession]);

  // All hooks declared above — safe to early-return now.
  if (isAuthenticated && !mcpOAuthSession) {
    return <Navigate to="/home" replace />;
  }

  // ---- Derived state ----

  const emailResolved = ssoOptions !== null;

  const passwordLoginBlocked = Boolean(
    ssoOptions?.requires_sso && !ssoOptions?.password_login_allowed,
  );

  // After email resolution, show tenant-specific providers when SSO is available.
  // When the tenant's policy disallows SSO (password_only), hide all SSO buttons.
  // Before email resolution, show discovery providers as branded login shortcuts.
  const resolvedProviders: Array<{
    id: number | null;
    provider_type: string | null;
    protocol: 'oidc' | 'saml' | null;
    display_name: string | null;
  }> = (() => {
    if (emailResolved) {
      if (!ssoOptions?.sso_login_available) {
        return [];
      }
      if (ssoOptions.providers && ssoOptions.providers.length > 0) {
        return ssoOptions.providers
          .filter((p) => p.is_enabled)
          .map((p) => ({
            id: p.id,
            provider_type: p.provider_type,
            protocol: p.protocol,
            display_name: p.provider_display_name,
          }));
      }
      return [
        {
          id: ssoOptions.provider_id,
          provider_type: ssoOptions.provider_type,
          protocol: ssoOptions.protocol,
          display_name: ssoOptions.provider_display_name,
        },
      ];
    }
    return discoveryProviders.map((p) => ({
      id: p.id,
      provider_type: p.provider_type,
      protocol: p.protocol,
      display_name: p.display_name,
    }));
  })();

  const showPasswordField = emailResolved
    ? ssoOptions?.password_login_allowed !== false
    : discoveryProviders.length === 0;

  // ---- Handlers ----

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    if (loginError) setLoginError(null);

    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));

    if (name === 'email') {
      setSsoOptions(null);
    }
  };

  const handleSsoLogin = async (selectedProviderId?: number) => {
    setLoginError(null);
    const normalizedEmail = formData.email.trim().toLowerCase();
    const hasValidEmail = EMAIL_REGEX.test(normalizedEmail);
    let options = ssoOptions;

    if (hasValidEmail) {
      options = ssoOptions || (await checkSsoOptions({ showErrors: true }));
      if (!options) return;
      if (!options.sso_login_available || resolvedProviders.length === 0) {
        setLoginError('SSO is not available for this organization.');
        return;
      }
    }

    const selectedProvider = resolvedProviders.find(
      (p) => p.id === selectedProviderId,
    );
    const providerProtocol =
      selectedProvider?.protocol || options?.protocol || 'oidc';

    if (providerProtocol === 'saml' && !hasValidEmail) {
      setLoginError('Enter a valid email before continuing with SAML sign-in.');
      return;
    }

    setStartingSsoProviderId(selectedProviderId ?? -1);
    const params = new URLSearchParams();
    if (providerProtocol === 'saml') {
      params.set('email', normalizedEmail);
    } else if (hasValidEmail) {
      params.set('email', normalizedEmail);
    }
    if (options?.customer_id) {
      params.set('customer_id', options.customer_id);
    }

    if (selectedProvider?.id) {
      params.set('provider_id', String(selectedProvider.id));
    }

    const endpoint =
      providerProtocol === 'saml'
        ? '/v1/auth/sso/saml/start'
        : '/v1/auth/sso/oidc/start';
    const query = params.toString();
    window.location.href = `${API_BASE}${endpoint}${query ? `?${query}` : ''}`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);

    // If password field isn't visible yet, treat Enter as "Continue with email"
    if (!showPasswordField || passwordLoginBlocked) {
      if (emailIsValid) {
        void checkSsoOptions({ showErrors: true });
      } else if (formData.email) {
        setLoginError('Please enter a valid email address.');
      }
      return;
    }
    if (!formData.email || !formData.password) {
      setLoginError('Please enter both email and password.');
      return;
    }
    if (!emailIsValid) {
      setLoginError('Please enter a valid email address.');
      return;
    }

    const latestOptions = ssoOptions || (await checkSsoOptions());
    if (latestOptions?.requires_sso && !latestOptions?.password_login_allowed) {
      setLoginError(
        'This organization requires SSO. Use the SSO button to continue.',
      );
      return;
    }

    setIsSubmitting(true);
    try {
      await login(formData);

      if (mcpOAuthSession) {
        setIsCompletingOAuth(true);
        try {
          const token = localStorage.getItem('auth_token');
          if (!token) throw new Error('No auth token found after login.');
          const redirectUrl = await completeMcpOAuthFlow(mcpOAuthSession, token);
          window.location.href = redirectUrl;
          return;
        } catch (oauthError: any) {
          setLoginError(oauthError.message || 'Failed to complete MCP authorization.');
          setIsCompletingOAuth(false);
        }
      }
    } catch (error: any) {
      let errorMessage = error?.message || 'Login failed. Please try again.';
      if (errorMessage === 'Not Found' || errorMessage.includes('404')) {
        errorMessage =
          'Unable to connect to the authentication service. Please try again or contact support.';
      } else if (
        errorMessage === 'Network Error' ||
        errorMessage.toLowerCase().includes('network')
      ) {
        errorMessage =
          'Network error. Please check your connection and try again.';
      } else if (
        errorMessage === 'Internal Server Error' ||
        errorMessage.includes('500')
      ) {
        errorMessage =
          'The server encountered an error. Please try again later.';
      }
      setLoginError(errorMessage);
      setFormData((prev) => ({ ...prev, password: '' }));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid = Boolean(formData.email && formData.password);

  // ---- Render ----

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-bg flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="flex items-baseline justify-center mb-6">
            <span className="font-sans text-4xl font-bold text-charcoal dark:text-white tracking-tight">
              eliza
            </span>
            <span className="font-title text-4xl italic text-eliza-red">
              forge
            </span>
          </div>
          <h1 className="font-title text-h1 text-charcoal dark:text-gray-100">
            {mcpOAuthSession ? 'Authorize Access' : 'Welcome back'}
          </h1>
          <p className="mt-2 text-body text-gray-500 dark:text-gray-400">
            {mcpOAuthSession
              ? 'Sign in to authorize an MCP client connection'
              : 'Sign in to your Eliza Forge account'}
          </p>
        </div>

        {isCompletingOAuth && (
          <div className="mt-8 flex flex-col items-center gap-3">
            <Spinner size="lg" />
            <p className="text-body text-gray-500 dark:text-gray-400">
              Completing authorization&hellip;
            </p>
          </div>
        )}

        <form className="mt-8 space-y-6" onSubmit={handleSubmit} style={isCompletingOAuth ? { display: 'none' } : undefined}>
          {/* Error alert */}
          {loginError && (
            <Alert
              variant="error"
              title="Login Failed"
              onDismiss={() => setLoginError(null)}
            >
              <p>{loginError}</p>
              {loginError.includes("couldn't find an account") && (
                <p className="mt-2 text-xs opacity-80 border-t border-red-200 dark:border-red-800 pt-2">
                  <strong>Tip:</strong> Make sure you&apos;re using the correct
                  email address.
                </p>
              )}
              {loginError.includes('password') &&
                loginError.includes('incorrect') && (
                  <p className="mt-2 text-xs opacity-80 border-t border-red-200 dark:border-red-800 pt-2">
                    <strong>Tip:</strong> Passwords are case-sensitive. Check
                    caps lock.
                  </p>
                )}
            </Alert>
          )}

          <div className="space-y-4">
            {/* SSO provider buttons */}
            {discoveryLoaded && resolvedProviders.length > 0 && (
              <div className="space-y-3">
                <div className="space-y-2">
                  {resolvedProviders.map((provider) => {
                    const isThisRedirecting =
                      startingSsoProviderId !== null &&
                      (startingSsoProviderId === provider.id ||
                        startingSsoProviderId === -1 && resolvedProviders.length === 1);
                    const anyRedirecting = startingSsoProviderId !== null;
                    return (
                      <Button
                        key={
                          provider.id ??
                          `${provider.provider_type}-${provider.protocol}`
                        }
                        type="button"
                        variant="outline"
                        className="w-full bg-white border-gray-300 text-charcoal hover:bg-gray-50 dark:bg-white dark:text-charcoal dark:border-gray-300"
                        onClick={() =>
                          void handleSsoLogin(provider.id ?? undefined)
                        }
                        disabled={anyRedirecting || isCheckingSso}
                      >
                        {isThisRedirecting ? (
                          <>
                            <Spinner size="sm" />
                            Redirecting...
                          </>
                        ) : (
                          <span className="inline-flex items-center gap-2">
                            <ProviderIcon
                              providerType={provider.provider_type}
                            />
                            {providerLabel(
                              provider.provider_type,
                              provider.display_name,
                            )}
                          </span>
                        )}
                      </Button>
                    );
                  })}
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-gray-200 dark:border-dark-border" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase tracking-wide">
                    <span className="bg-gray-50 px-2 text-gray-500 dark:bg-dark-bg dark:text-gray-400">
                      or
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Email input */}
            <div>
              <Label htmlFor="email">Email address</Label>
              <div className="mt-1">
                <Input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={formData.email}
                  onChange={handleInputChange}
                  onBlur={() => {
                    if (emailIsValid) {
                      checkSsoOptions();
                    }
                  }}
                  placeholder="Enter your email"
                />
              </div>
            </div>

            {/* Continue button — visible when SSO providers exist but email not yet resolved */}
            {!emailResolved && discoveryProviders.length > 0 && (
              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={!emailIsValid || isCheckingSso}
              >
                {isCheckingSso ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner size="sm" className="text-white" />
                    Checking...
                  </span>
                ) : (
                  'Continue with email'
                )}
              </Button>
            )}

            {/* SSO info / enforcement alert (after email resolution) */}
            {emailResolved && ssoOptions?.sso_login_available && (
              <Alert
                variant={ssoOptions.requires_sso ? 'warning' : 'info'}
                title={ssoOptions.requires_sso ? 'SSO Required' : 'SSO Available'}
              >
                <div className="space-y-3">
                  {ssoOptions.requires_sso ? (
                    <p>
                      This organization requires SSO. Use the button above to
                      continue.
                    </p>
                  ) : (
                    <p>
                      {resolvedProviders.length > 1
                        ? `${resolvedProviders.length} SSO providers are available`
                        : `${ssoOptions.provider_display_name || 'Single Sign-On'} is available`}
                      {ssoOptions.customer_name
                        ? ` for ${ssoOptions.customer_name}`
                        : ''}
                      .
                    </p>
                  )}
                </div>
              </Alert>
            )}

            {/* Password field (progressive disclosure) */}
            {showPasswordField && !passwordLoginBlocked && (
              <div>
                <Label htmlFor="password">Password</Label>
                <div className="relative mt-1">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder="Enter your password"
                    className="pr-10"
                  />
                  <button
                    type="button"
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-500 dark:text-gray-500 dark:hover:text-gray-400 transition-colors"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeSlashIcon className="h-5 w-5" />
                    ) : (
                      <EyeIcon className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Remember me + forgot password */}
          {showPasswordField && !passwordLoginBlocked && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="remember_me"
                  name="remember_me"
                  checked={formData.remember_me}
                  onChange={handleInputChange}
                />
                <Label
                  htmlFor="remember_me"
                  className="text-sm text-gray-500 dark:text-gray-400 cursor-pointer"
                >
                  Remember me
                </Label>
              </div>
              <Link
                to="/forgot-password"
                className="text-sm font-medium text-eliza-red hover:text-eliza-red-light transition-colors"
              >
                Forgot your password?
              </Link>
            </div>
          )}

          {/* Sign in button */}
          {showPasswordField && !passwordLoginBlocked && (
            <Button
              type="submit"
              disabled={!isFormValid || isSubmitting || isLoading}
              className="w-full"
              size="lg"
            >
              {isSubmitting || isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Spinner size="sm" className="text-white" />
                  Signing in...
                </span>
              ) : (
                'Sign in'
              )}
            </Button>
          )}
        </form>

        <div className="text-center">
          <p className="text-sm text-eliza-red">
            <span className="font-sans font-bold tracking-tight">Eliza</span>{' '}
            <span className="font-title italic">Forge</span> v1.0.0
          </p>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;

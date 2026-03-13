import React, { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
  Page,
  PageBody,
  PageHeader,
  Select,
  SelectOption,
  Spinner,
} from '../../components/ui';
import { useToasts } from '../../stores/useToasts';
import { AXIOS_INSTANCE } from '../../services/api-client';

type ProviderType = 'azure' | 'okta' | 'google' | 'generic';

interface PlatformSsoPolicyResponse {
  global_sso_enabled: boolean;
  allowed_provider_types: ProviderType[];
  allow_tenant_enforced_mode: boolean;
  require_domain_verification_for_enforced_mode: boolean;
  break_glass_enabled: boolean;
  break_glass_allowed_user_emails: string[];
  jit_provisioning_default: boolean;
  default_password_policy_profile: string;
}

interface FormState {
  global_sso_enabled: boolean;
  allowed_provider_types: ProviderType[];
  allow_tenant_enforced_mode: boolean;
  require_domain_verification_for_enforced_mode: boolean;
  break_glass_enabled: boolean;
  break_glass_allowed_user_emails_text: string;
  jit_provisioning_default: boolean;
  default_password_policy_profile: string;
}

const DEFAULT_FORM: FormState = {
  global_sso_enabled: true,
  allowed_provider_types: ['azure', 'okta', 'google', 'generic'],
  allow_tenant_enforced_mode: true,
  require_domain_verification_for_enforced_mode: true,
  break_glass_enabled: true,
  break_glass_allowed_user_emails_text: '',
  jit_provisioning_default: false,
  default_password_policy_profile: 'strong_8_char',
};

const PROVIDER_OPTIONS: Array<{ value: ProviderType; label: string }> = [
  { value: 'azure', label: 'Azure / Entra ID' },
  { value: 'okta', label: 'Okta' },
  { value: 'google', label: 'Google Workspace' },
  { value: 'generic', label: 'Generic OIDC/SAML' },
];

const PASSWORD_POLICY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'strong_8_char', label: 'strong_8_char (minimum 8 chars + complexity)' },
  { value: 'strong_12_char', label: 'strong_12_char (minimum 12 chars + complexity)' },
];

function getApiErrorMessage(error: any, fallback: string): string {
  const detail =
    error?.response?.data?.detail ??
    error?.response?.data?.message ??
    error?.message;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') {
          return item;
        }
        if (item && typeof item === 'object') {
          const itemMessage = typeof item.msg === 'string' ? item.msg : null;
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : null;
          if (itemMessage && loc) {
            return `${loc}: ${itemMessage}`;
          }
          if (itemMessage) {
            return itemMessage;
          }
          try {
            return JSON.stringify(item);
          } catch {
            return String(item);
          }
        }
        return String(item);
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join(' | ');
    }
    return fallback;
  }

  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  return fallback;
}

export default function SsoPolicyPage() {
  const { push } = useToasts();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const passwordPolicyOptions = useMemo(() => {
    if (
      form.default_password_policy_profile &&
      !PASSWORD_POLICY_OPTIONS.some(
        (option) => option.value === form.default_password_policy_profile
      )
    ) {
      return [
        ...PASSWORD_POLICY_OPTIONS,
        {
          value: form.default_password_policy_profile,
          label: `${form.default_password_policy_profile} (custom)`,
        },
      ];
    }
    return PASSWORD_POLICY_OPTIONS;
  }, [form.default_password_policy_profile]);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const response = await AXIOS_INSTANCE.get<PlatformSsoPolicyResponse>(
          '/api/v1/platform-admin/auth/sso-policy'
        );
        const data = response.data;
        setForm({
          global_sso_enabled: data.global_sso_enabled,
          allowed_provider_types: data.allowed_provider_types || [],
          allow_tenant_enforced_mode: data.allow_tenant_enforced_mode,
          require_domain_verification_for_enforced_mode:
            data.require_domain_verification_for_enforced_mode,
          break_glass_enabled: data.break_glass_enabled,
          break_glass_allowed_user_emails_text: (
            data.break_glass_allowed_user_emails || []
          ).join(', '),
          jit_provisioning_default: data.jit_provisioning_default,
          default_password_policy_profile:
            data.default_password_policy_profile || 'strong_8_char',
        });
      } catch (e: any) {
        push({
          kind: 'error',
          message: getApiErrorMessage(e, 'Failed to load SSO policy'),
        });
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [push]);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleProvider = (provider: ProviderType) => {
    setForm((prev) => {
      const has = prev.allowed_provider_types.includes(provider);
      return {
        ...prev,
        allowed_provider_types: has
          ? prev.allowed_provider_types.filter((p) => p !== provider)
          : [...prev.allowed_provider_types, provider],
      };
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload = {
        global_sso_enabled: form.global_sso_enabled,
        allowed_provider_types: form.allowed_provider_types,
        allow_tenant_enforced_mode: form.allow_tenant_enforced_mode,
        require_domain_verification_for_enforced_mode:
          form.require_domain_verification_for_enforced_mode,
        break_glass_enabled: form.break_glass_enabled,
        break_glass_allowed_user_emails: form.break_glass_allowed_user_emails_text
          .split(',')
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean),
        jit_provisioning_default: form.jit_provisioning_default,
        default_password_policy_profile: form.default_password_policy_profile.trim(),
      };

      await AXIOS_INSTANCE.put('/api/v1/platform-admin/auth/sso-policy', payload);
      push({ kind: 'success', message: 'Platform SSO policy saved' });
    } catch (e: any) {
      push({
        kind: 'error',
        message: getApiErrorMessage(e, 'Failed to save SSO policy'),
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Page maxWidth="xl">
        <PageBody>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner size="sm" />
            Loading platform SSO policy...
          </div>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="xl">
      <PageHeader
        title="Platform SSO Policy"
        description="Global SSO controls for tenant availability, provider allowlist, and break-glass behavior."
        actions={
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? <Spinner size="sm" className="mr-2" /> : null}
            Save Policy
          </Button>
        }
      />
      <PageBody className="space-y-6 pb-10">
        <Card>
          <CardHeader>
            <CardTitle>Global Controls</CardTitle>
            <CardDescription>
              Governs whether tenants can use SSO and what policy levels are allowed.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Checkbox
              id="platform-global-sso"
              checked={form.global_sso_enabled}
              onChange={(e) => setField('global_sso_enabled', e.target.checked)}
              label="Global SSO enabled"
            />

            <Checkbox
              id="platform-allow-enforced"
              checked={form.allow_tenant_enforced_mode}
              onChange={(e) => setField('allow_tenant_enforced_mode', e.target.checked)}
              label="Allow tenant enforced mode"
            />

            <Checkbox
              id="platform-domain-verification"
              checked={form.require_domain_verification_for_enforced_mode}
              onChange={(e) =>
                setField('require_domain_verification_for_enforced_mode', e.target.checked)
              }
              label="Require domain verification when tenant enforces SSO"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Allowed Providers</CardTitle>
            <CardDescription>Select which provider families tenant admins can configure.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {PROVIDER_OPTIONS.map((option) => {
              const selected = form.allowed_provider_types.includes(option.value);
              return (
                <div
                  key={option.value}
                  className="rounded-xl border border-gray-200 px-3 py-2 dark:border-dark-border"
                >
                  <Checkbox
                    id={`provider-${option.value}`}
                    checked={selected}
                    onChange={() => toggleProvider(option.value)}
                    label={option.label}
                  />
                </div>
              );
            })}
            <div>
              <Badge variant="info">
                {form.allowed_provider_types.length} provider type(s) enabled
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Break-Glass and Defaults</CardTitle>
            <CardDescription>
              Controls local-login exceptions and default provisioning settings.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Checkbox
              id="platform-break-glass"
              checked={form.break_glass_enabled}
              onChange={(e) => setField('break_glass_enabled', e.target.checked)}
              label="Break-glass login enabled for enforced tenants"
            />

            <div className="space-y-2">
              <Label>Break-Glass Allowed Emails (comma-separated)</Label>
              <Input
                value={form.break_glass_allowed_user_emails_text}
                onChange={(e) => setField('break_glass_allowed_user_emails_text', e.target.value)}
                placeholder="ops-admin@company.com, security@company.com"
              />
            </div>

            <Checkbox
              id="platform-default-jit"
              checked={form.jit_provisioning_default}
              onChange={(e) => setField('jit_provisioning_default', e.target.checked)}
              label="Default JIT provisioning to enabled"
            />

            <div className="space-y-2">
              <Label>Default Password Policy Profile</Label>
              <Select
                value={form.default_password_policy_profile}
                onValueChange={(value) => setField('default_password_policy_profile', value)}
              >
                {passwordPolicyOptions.map((option) => (
                  <SelectOption key={option.value} value={option.value}>
                    {option.label}
                  </SelectOption>
                ))}
              </Select>
            </div>
          </CardContent>
        </Card>
      </PageBody>
    </Page>
  );
}

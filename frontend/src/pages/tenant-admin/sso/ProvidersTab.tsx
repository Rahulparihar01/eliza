import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  Checkbox,
  Input,
  Label,
  Select,
  SelectOption,
  Spinner,
  Textarea,
} from '../../../components/ui';
import { AXIOS_INSTANCE } from '../../../services/api-client';
import { useToasts } from '../../../stores/useToasts';
import {
  JIT_ROLE_OPTIONS,
  PROTOCOL_OPTIONS,
  PROVIDER_OPTIONS,
  PROVIDER_SETUP_GUIDES,
} from './constants';
import {
  blankProviderForm,
  getApiErrorMessage,
  providerFormFromResponse,
  type LoginMode,
  type ProviderForm,
  type ProviderResponse,
  type ProviderType,
  type Protocol,
} from './types';
import { ConfirmationModal } from './ConfirmationModal';

interface ProvidersTabProps {
  providers: ProviderResponse[];
  loginMode: LoginMode;
  onRefresh: () => Promise<void>;
  onDirtyChange?: (isDirty: boolean) => void;
  discardSignal?: number;
}

type PendingSelection = { providerId: number | null } | null;

export function ProvidersTab({
  providers,
  loginMode,
  onRefresh,
  onDirtyChange,
  discardSignal = 0,
}: ProvidersTabProps) {
  const { push } = useToasts();

  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [form, setForm] = useState<ProviderForm>(blankProviderForm());
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [pendingSelection, setPendingSelection] = useState<PendingSelection>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Keep baseline to compute dirty state.
  const [baseline, setBaseline] = useState<ProviderForm>(blankProviderForm());

  const isDirty = useMemo(() => {
    const normalize = (obj: ProviderForm) => ({
      ...obj,
      oidc_client_secret: obj.oidc_client_secret.trim(),
      saml_x509_cert: obj.saml_x509_cert.trim(),
      oidc_scopes_text: obj.oidc_scopes_text.trim(),
    });
    return JSON.stringify(normalize(form)) !== JSON.stringify(normalize(baseline));
  }, [form, baseline]);

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

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

  useEffect(() => {
    if (providers.length > 0 && selectedProviderId === null && !isCreatingNew) {
      setSelectedProviderId(providers[0].id);
    }
    if (providers.length === 0) {
      setSelectedProviderId(null);
      setIsCreatingNew(true);
      const blank = blankProviderForm();
      setForm(blank);
      setBaseline(blank);
    }
  }, [providers, selectedProviderId, isCreatingNew]);

  useEffect(() => {
    const selected = providers.find((p) => p.id === selectedProviderId) ?? null;
    if (selected) {
      setIsCreatingNew(false);
      const next = providerFormFromResponse(selected);
      setForm(next);
      setBaseline(next);
      return;
    }
    if (selectedProviderId === null) {
      const blank = blankProviderForm();
      setForm(blank);
      setBaseline(blank);
    }
  }, [selectedProviderId, providers]);

  useEffect(() => {
    if (discardSignal === 0) return;
    const selected = providers.find((p) => p.id === selectedProviderId) ?? null;
    if (selected) {
      const reset = providerFormFromResponse(selected);
      setForm(reset);
      setBaseline(reset);
    } else {
      const blank = blankProviderForm();
      setForm(blank);
      setBaseline(blank);
    }
  }, [discardSignal]);

  const setField = <K extends keyof ProviderForm>(key: K, value: ProviderForm[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSelectProvider = (id: number | null) => {
    if (isDirty) {
      setPendingSelection({ providerId: id });
      return;
    }
    setIsCreatingNew(id === null);
    setSelectedProviderId(id);
  };

  const confirmDiscardAndSwitch = () => {
    const target = pendingSelection;
    setPendingSelection(null);
    if (target) {
      setIsCreatingNew(target.providerId === null);
      setSelectedProviderId(target.providerId);
    }
  };

  const selectedProvider = providers.find((p) => p.id === selectedProviderId) ?? null;

  const jitRoleOptions = useMemo(() => {
    if (form.jit_default_role && !JIT_ROLE_OPTIONS.some((o) => o.value === form.jit_default_role)) {
      return [
        ...JIT_ROLE_OPTIONS,
        { value: form.jit_default_role, label: `${form.jit_default_role} (custom)` },
      ];
    }
    return JIT_ROLE_OPTIONS;
  }, [form.jit_default_role]);

  const saveProvider = async () => {
    setIsSaving(true);
    try {
      const payload: Record<string, any> = {
        provider_type: form.provider_type || null,
        protocol: form.protocol || null,
        display_name: form.display_name || null,
        is_enabled: form.is_enabled,
        jit_provisioning_enabled: form.jit_provisioning_enabled,
        jit_default_role: form.jit_default_role || 'viewer',
        oidc_issuer_url: form.oidc_issuer_url.trim() || null,
        oidc_client_id: form.oidc_client_id.trim() || null,
        oidc_scopes: form.oidc_scopes_text
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        saml_entity_id: form.saml_entity_id.trim() || null,
        saml_sso_url: form.saml_sso_url.trim() || null,
        saml_metadata_url: form.saml_metadata_url.trim() || null,
      };
      if (form.oidc_client_secret.trim()) {
        payload.oidc_client_secret = form.oidc_client_secret.trim();
      }
      if (form.saml_x509_cert.trim()) {
        payload.saml_x509_cert = form.saml_x509_cert.trim();
      }

      if (selectedProviderId) {
        await AXIOS_INSTANCE.put(`/api/v1/tenant-settings/sso/providers/${selectedProviderId}`, payload);
      } else {
        const created = await AXIOS_INSTANCE.post<ProviderResponse>(
          '/api/v1/tenant-settings/sso/providers',
          payload,
        );
        setIsCreatingNew(false);
        setSelectedProviderId(created.data.id);
      }
      await onRefresh();
      push({ kind: 'success', message: 'SSO provider saved' });
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Failed to save provider') });
    } finally {
      setIsSaving(false);
    }
  };

  const testProvider = async () => {
    if (!selectedProviderId) {
      push({ kind: 'warning', message: 'Save the provider before testing' });
      return;
    }
    setIsTesting(true);
    try {
      await AXIOS_INSTANCE.post(`/api/v1/tenant-settings/sso/providers/${selectedProviderId}/test`);
      await onRefresh();
      push({ kind: 'success', message: 'Provider test completed' });
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Provider test failed') });
    } finally {
      setIsTesting(false);
    }
  };

  const deleteProvider = async () => {
    if (!selectedProviderId) return;
    setIsDeleting(true);
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/tenant-settings/sso/providers/${selectedProviderId}`);
      setSelectedProviderId(null);
      setIsCreatingNew(false);
      await onRefresh();
      setShowDeleteConfirm(false);
      push({ kind: 'success', message: 'Provider deleted' });
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Failed to delete provider') });
    } finally {
      setIsDeleting(false);
    }
  };

  const enabledCount = providers.filter((p) => p.is_enabled).length;
  const isLastEnabled =
    !!selectedProvider && selectedProvider.is_enabled && enabledCount === 1 && loginMode !== 'password_only';

  const guide = form.provider_type ? PROVIDER_SETUP_GUIDES[form.provider_type] : null;

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Button
              variant="secondary"
              className="w-full"
              onClick={() => handleSelectProvider(null)}
            >
              + Add Provider
            </Button>
            {isCreatingNew && (
              <div
                className="w-full rounded-lg border border-eliza-red bg-red-50 p-3 text-left dark:bg-red-950/20"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">
                    {form.display_name.trim() || 'New Provider'}
                  </div>
                  <Badge variant="info">draft</Badge>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  {(form.provider_type || 'select provider')} · {(form.protocol || 'select protocol')}
                </div>
              </div>
            )}
            {providers.map((provider) => (
              <button
                key={provider.id}
                type="button"
                onClick={() => handleSelectProvider(provider.id)}
                className={`w-full rounded-lg border p-3 text-left transition ${
                  selectedProviderId === provider.id
                    ? 'border-eliza-red bg-red-50 dark:bg-red-950/20'
                    : 'border-gray-200 hover:bg-gray-50 dark:border-dark-border dark:hover:bg-dark-surface-2'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">
                    {provider.display_name || `${provider.provider_type} (${provider.protocol})`}
                  </div>
                  <Badge variant={provider.is_enabled ? 'success' : 'secondary'}>
                    {provider.is_enabled ? 'enabled' : 'disabled'}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  {provider.provider_type} · {provider.protocol}
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Provider Type</Label>
                <Select
                  value={form.provider_type}
                  onValueChange={(value) => setField('provider_type', value as ProviderType)}
                  disabled={!!selectedProviderId}
                >
                  {PROVIDER_OPTIONS.map((option) => (
                    <SelectOption key={option.value || 'none'} value={option.value}>
                      {option.label}
                    </SelectOption>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Protocol</Label>
                <Select
                  value={form.protocol}
                  onValueChange={(value) => setField('protocol', value as Protocol)}
                  disabled={!!selectedProviderId}
                >
                  {PROTOCOL_OPTIONS.map((option) => (
                    <SelectOption key={option.value || 'none'} value={option.value}>
                      {option.label}
                    </SelectOption>
                  ))}
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Display Name</Label>
              <Input
                value={form.display_name}
                onChange={(e) => setField('display_name', e.target.value)}
                placeholder="Sign in with Company SSO"
              />
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <Checkbox
                id="provider-enabled"
                checked={form.is_enabled}
                onChange={(e) => setField('is_enabled', e.target.checked)}
                label="Enable this provider"
              />
              <Checkbox
                id="provider-jit"
                checked={form.jit_provisioning_enabled}
                onChange={(e) => setField('jit_provisioning_enabled', e.target.checked)}
                label="Enable JIT user provisioning"
              />
            </div>

            <div className="space-y-2">
              <Label>JIT Default Role</Label>
              <Select
                value={form.jit_default_role}
                onValueChange={(value) => setField('jit_default_role', value)}
              >
                {jitRoleOptions.map((option) => (
                  <SelectOption key={option.value} value={option.value}>
                    {option.label}
                  </SelectOption>
                ))}
              </Select>
            </div>

            {form.protocol === 'oidc' ? (
              <div className="space-y-3 rounded-lg border border-gray-200 p-4 dark:border-dark-border">
                <Label>OIDC Configuration</Label>
                <Input
                  value={form.oidc_issuer_url}
                  onChange={(e) => setField('oidc_issuer_url', e.target.value)}
                  placeholder="https://issuer.example.com"
                />
                <Input
                  value={form.oidc_client_id}
                  onChange={(e) => setField('oidc_client_id', e.target.value)}
                  placeholder="Client ID"
                />
                <Input
                  type="password"
                  value={form.oidc_client_secret}
                  onChange={(e) => setField('oidc_client_secret', e.target.value)}
                  placeholder={
                    form.has_oidc_client_secret ? 'Stored (enter to rotate)' : 'Client Secret'
                  }
                />
                <Input
                  value={form.oidc_scopes_text}
                  onChange={(e) => setField('oidc_scopes_text', e.target.value)}
                  placeholder="openid, profile, email"
                />
              </div>
            ) : null}

            {form.protocol === 'saml' ? (
              <div className="space-y-3 rounded-lg border border-gray-200 p-4 dark:border-dark-border">
                <Label>SAML Configuration</Label>
                <Input
                  value={form.saml_entity_id}
                  onChange={(e) => setField('saml_entity_id', e.target.value)}
                  placeholder="Entity ID"
                />
                <Input
                  value={form.saml_sso_url}
                  onChange={(e) => setField('saml_sso_url', e.target.value)}
                  placeholder="https://idp.example.com/sso/saml"
                />
                <Input
                  value={form.saml_metadata_url}
                  onChange={(e) => setField('saml_metadata_url', e.target.value)}
                  placeholder="https://idp.example.com/metadata"
                />
                <Textarea
                  value={form.saml_x509_cert}
                  onChange={(e) => setField('saml_x509_cert', e.target.value)}
                  rows={5}
                  placeholder={
                    form.has_saml_x509_cert ? 'Stored (enter to rotate)' : 'Paste PEM cert'
                  }
                />
              </div>
            ) : null}

            {guide && (
              <Alert variant="info" title={guide.title}>
                <div className="space-y-2">
                  <p>{guide.summary}</p>
                  <ul className="list-disc pl-5">
                    {guide.steps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ul>
                </div>
              </Alert>
            )}

            {form.last_test_status || form.last_test_error ? (
              <Alert variant={form.last_test_status === 'success' ? 'success' : 'warning'} title={`Last test: ${form.last_test_status || 'unknown'}`}>
                {form.last_test_error || 'No errors reported.'}
              </Alert>
            ) : null}

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => void testProvider()}
                disabled={isTesting || isSaving || !selectedProviderId}
              >
                {isTesting ? <Spinner size="sm" className="mr-2" /> : null}
                Test
              </Button>
              <Button onClick={() => void saveProvider()} disabled={isSaving || isTesting}>
                {isSaving ? <Spinner size="sm" className="mr-2" /> : null}
                Save Provider
              </Button>
              <Button
                variant="ghost"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={!selectedProviderId || isSaving || isTesting}
              >
                Delete
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <ConfirmationModal
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={deleteProvider}
        title={`Delete ${selectedProvider?.display_name || 'this provider'}?`}
        body="This will permanently remove this SSO provider configuration."
        bullets={
          isLastEnabled
            ? [
                'This is your only enabled SSO provider.',
                'Deleting it will make SSO non-functional until another provider is enabled.',
              ]
            : undefined
        }
        confirmLabel="Delete Provider"
        confirmVariant="destructive"
        isLoading={isDeleting}
      />

      <ConfirmationModal
        open={pendingSelection !== null}
        onClose={() => setPendingSelection(null)}
        onConfirm={confirmDiscardAndSwitch}
        title="You have unsaved changes"
        body="Your provider form has unsaved changes. Discard changes and continue?"
        confirmLabel="Discard Changes"
        confirmVariant="destructive"
      />
    </>
  );
}

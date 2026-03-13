import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, CardContent, RadioCard, RadioGroup, Spinner } from '../../../components/ui';
import type { DomainResponse, LoginMode, ProviderResponse } from './types';
import { LOGIN_MODE_OPTIONS } from './constants';
import { ConfirmationModal } from './ConfirmationModal';

interface PolicyTabProps {
  loginMode: LoginMode;
  providers: ProviderResponse[];
  domains: DomainResponse[];
  onSave: (mode: LoginMode) => Promise<void>;
}

type ConfirmKind = 'enforce' | 'disable' | 'downgrade' | null;

function getConfirmKind(from: LoginMode, to: LoginMode): ConfirmKind {
  if (to === 'sso_enforced' && from !== 'sso_enforced') return 'enforce';
  if (to === 'password_only' && from !== 'password_only') return 'disable';
  if (to === 'sso_optional' && from === 'sso_enforced') return 'downgrade';
  return null;
}

export function PolicyTab({ loginMode, providers, domains, onSave }: PolicyTabProps) {
  const [localMode, setLocalMode] = useState<LoginMode>(loginMode);
  const [isSaving, setIsSaving] = useState(false);
  const [confirmKind, setConfirmKind] = useState<ConfirmKind>(null);

  useEffect(() => {
    setLocalMode(loginMode);
  }, [loginMode]);

  // TODO(testing): hasVerifiedDomain check temporarily bypassed for SSO enforcement testing.
  // Restore: const hasVerifiedDomain = domains.some((d) => d.status === 'verified');
  const hasEnabledProvider = providers.some((p) => p.is_enabled);
  const isBlocked =
    (localMode === 'sso_enforced' && !hasEnabledProvider);

  const isDirty = localMode !== loginMode;

  const confirmConfig = useMemo(() => {
    if (confirmKind === 'enforce') {
      return {
        title: 'Enforce SSO for all users?',
        body: 'This will immediately block password-based login for all users in this tenant.',
        bullets: [
          'Active sessions are not terminated.',
          'Users without linked SSO identities may be locked out.',
          'Break-glass admin recovery remains available.',
        ],
        confirmLabel: 'Enforce SSO',
        confirmVariant: 'destructive' as const,
        requireTypedConfirmation: 'enforce',
      };
    }
    if (confirmKind === 'disable') {
      return {
        title: 'Disable SSO?',
        body: 'Switching to password-only deactivates SSO for login. SSO-only users may require a password reset.',
        confirmLabel: 'Switch to Password Only',
        confirmVariant: 'destructive' as const,
      };
    }
    if (confirmKind === 'downgrade') {
      return {
        title: 'Allow password logins again?',
        body: 'Users will be able to choose password or SSO login. SSO providers remain configured and active.',
        confirmLabel: 'Allow Passwords',
        confirmVariant: 'default' as const,
      };
    }
    return null;
  }, [confirmKind]);

  const executeSave = async () => {
    setIsSaving(true);
    try {
      await onSave(localMode);
      setConfirmKind(null);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveClick = () => {
    const kind = getConfirmKind(loginMode, localMode);
    if (kind) {
      setConfirmKind(kind);
      return;
    }
    void executeSave();
  };

  return (
    <>
      <Card className="max-w-3xl">
        <CardContent className="space-y-4 pt-6">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Control how users in this tenant authenticate.
          </p>
          <RadioGroup value={localMode} onValueChange={(v) => setLocalMode(v as LoginMode)} className="space-y-3">
            {LOGIN_MODE_OPTIONS.map((option) => (
              <RadioCard key={option.value} value={option.value}>
                <div className="font-medium text-sm">{option.label}</div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{option.description}</p>
              </RadioCard>
            ))}
          </RadioGroup>

          {/* TODO(testing): Verified domain warning temporarily hidden for SSO testing.
          {localMode === 'sso_enforced' && !hasVerifiedDomain && (
            <Alert variant="warning" title="Verified domain required">
              Enforcing SSO requires at least one verified domain.
            </Alert>
          )} */}
          {localMode === 'sso_enforced' && !hasEnabledProvider && (
            <Alert variant="warning" title="Enabled provider required">
              Enforcing SSO requires at least one enabled provider.
            </Alert>
          )}

          <div>
            <Button onClick={handleSaveClick} disabled={isBlocked || !isDirty || isSaving}>
              {isSaving && <Spinner size="sm" className="mr-2" />}
              Save Policy
            </Button>
          </div>
        </CardContent>
      </Card>

      {confirmConfig && (
        <ConfirmationModal
          open={true}
          onClose={() => setConfirmKind(null)}
          onConfirm={executeSave}
          title={confirmConfig.title}
          body={confirmConfig.body}
          bullets={confirmConfig.bullets}
          confirmLabel={confirmConfig.confirmLabel}
          confirmVariant={confirmConfig.confirmVariant}
          requireTypedConfirmation={confirmConfig.requireTypedConfirmation}
          isLoading={isSaving}
        />
      )}
    </>
  );
}

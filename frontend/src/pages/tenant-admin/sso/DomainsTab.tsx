import React, { useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  Input,
  Spinner,
} from '../../../components/ui';
import { AXIOS_INSTANCE } from '../../../services/api-client';
import { useToasts } from '../../../stores/useToasts';
import type { DomainResponse, LoginMode } from './types';
import { getApiErrorMessage } from './types';
import { ConfirmationModal } from './ConfirmationModal';

interface DomainsTabProps {
  domains: DomainResponse[];
  loginMode: LoginMode;
  onRefresh: () => Promise<void>;
}

export function DomainsTab({ domains, loginMode, onRefresh }: DomainsTabProps) {
  const { push } = useToasts();
  const [newDomain, setNewDomain] = useState('');
  const [isBusy, setIsBusy] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [confirmRemoveId, setConfirmRemoveId] = useState<number | null>(null);

  const verifiedCount = domains.filter((d) => d.status === 'verified').length;
  const targetRemoveDomain = domains.find((d) => d.id === confirmRemoveId) ?? null;

  const addDomain = async () => {
    if (!newDomain.trim()) return;
    setIsBusy(true);
    try {
      await AXIOS_INSTANCE.post('/api/v1/tenant-settings/sso/domains', {
        domain: newDomain.trim(),
      });
      setNewDomain('');
      await onRefresh();
      push({ kind: 'success', message: 'Domain added' });
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Failed to add domain') });
    } finally {
      setIsBusy(false);
    }
  };

  const verifyDomain = async (id: number) => {
    setIsBusy(true);
    try {
      await AXIOS_INSTANCE.post(`/api/v1/tenant-settings/sso/domains/${id}/verify`);
      await onRefresh();
      push({ kind: 'success', message: 'Domain verification check completed' });
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Failed to verify domain') });
    } finally {
      setIsBusy(false);
    }
  };

  const removeDomain = async (id: number) => {
    setIsBusy(true);
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/tenant-settings/sso/domains/${id}`);
      await onRefresh();
      push({ kind: 'success', message: 'Domain removed' });
      setConfirmRemoveId(null);
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Failed to remove domain') });
    } finally {
      setIsBusy(false);
    }
  };

  const onRemoveClick = (domain: DomainResponse) => {
    const lastVerified =
      loginMode === 'sso_enforced' && domain.status === 'verified' && verifiedCount === 1;
    if (lastVerified) {
      setConfirmRemoveId(domain.id);
      return;
    }
    void removeDomain(domain.id);
  };

  const copyToken = async (token: string) => {
    try {
      await navigator.clipboard.writeText(token);
      push({ kind: 'success', message: 'Copied to clipboard' });
    } catch {
      push({ kind: 'warning', message: 'Clipboard access unavailable' });
    }
  };

  const getBadgeVariant = (status: DomainResponse['status']) => {
    if (status === 'verified') return 'success' as const;
    if (status === 'failed') return 'warning' as const;
    return 'secondary' as const;
  };

  return (
    <>
      <Card className="max-w-4xl">
        <CardContent className="space-y-4 pt-6">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Add and verify domains via DNS TXT records before enforcing SSO.
          </p>

          <div className="flex gap-2">
            <Input
              value={newDomain}
              onChange={(e) => setNewDomain(e.target.value)}
              placeholder="acme.com"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void addDomain();
                }
              }}
            />
            <Button onClick={addDomain} disabled={isBusy || !newDomain.trim()}>
              {isBusy && <Spinner size="sm" className="mr-2" />}
              Add Domain
            </Button>
          </div>

          {domains.length === 0 ? (
            <Alert variant="neutral" title="No domains yet">
              Add a domain to generate a verification token.
            </Alert>
          ) : (
            <div className="space-y-3">
              {domains.map((domain) => (
                <div
                  key={domain.id}
                  className="rounded-lg border border-gray-200 dark:border-dark-border"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 p-3">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{domain.domain}</div>
                      <div className="mt-1 text-xs text-gray-500 dark:text-gray-400 break-all">
                        TXT: <code>{domain.verification_token}</code>
                      </div>
                      {domain.last_check_error && (
                        <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                          {domain.last_check_error}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={getBadgeVariant(domain.status)}>{domain.status}</Badge>
                      <Button variant="secondary" onClick={() => void verifyDomain(domain.id)} disabled={isBusy}>
                        {domain.status === 'verified' ? 'Re-verify' : 'Verify'}
                      </Button>
                      <Button variant="ghost" onClick={() => onRemoveClick(domain)} disabled={isBusy}>
                        Remove
                      </Button>
                    </div>
                  </div>

                  <div className="border-t border-gray-200 dark:border-dark-border">
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-xs text-gray-500 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-dark-surface-2"
                      onClick={() => setExpandedId(expandedId === domain.id ? null : domain.id)}
                    >
                      {expandedId === domain.id ? 'Hide DNS instructions' : 'Show DNS instructions'}
                    </button>
                    {expandedId === domain.id && (
                      <div className="px-3 pb-3 text-xs text-gray-600 dark:text-gray-400 space-y-1">
                        <p className="font-medium">Add this TXT record to your DNS provider:</p>
                        <p>
                          Host: <code>@</code> (or <code>{domain.domain}</code>)
                        </p>
                        <p>
                          Type: <code>TXT</code>
                        </p>
                        <p>
                          Value: <code>{domain.verification_token}</code>
                        </p>
                        <div className="pt-2">
                          <Button variant="secondary" onClick={() => void copyToken(domain.verification_token)}>
                            Copy token
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmationModal
        open={targetRemoveDomain !== null}
        onClose={() => setConfirmRemoveId(null)}
        onConfirm={() => (targetRemoveDomain ? removeDomain(targetRemoveDomain.id) : undefined)}
        title="Remove last verified domain?"
        body={`Removing ${targetRemoveDomain?.domain ?? 'this domain'} leaves no verified domains while SSO is enforced.`}
        bullets={['Enforced SSO requires at least one verified domain.', 'You will need to change login policy after removal.']}
        confirmLabel="Remove Domain"
        confirmVariant="destructive"
        isLoading={isBusy}
      />
    </>
  );
}

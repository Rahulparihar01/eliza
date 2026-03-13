import React, { useCallback, useEffect, useState } from 'react';
import { Page, PageBody, PageHeader, Spinner, Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui';
import { useToasts } from '../../stores/useToasts';
import { AXIOS_INSTANCE } from '../../services/api-client';

import type {
  DomainResponse,
  LoginMode,
  PolicyResponse,
  ProviderResponse,
} from './sso/types';
import { getApiErrorMessage } from './sso/types';
import { SsoStatusBar, type SsoTabKey } from './sso/SsoStatusBar';
import { PolicyTab } from './sso/PolicyTab';
import { DomainsTab } from './sso/DomainsTab';
import { ProvidersTab } from './sso/ProvidersTab';
import { ConfirmationModal } from './sso/ConfirmationModal';


export default function SsoSettingsPage() {
  const { push } = useToasts();

  const [isLoading, setIsLoading] = useState(true);
  const [loginMode, setLoginMode] = useState<LoginMode>('password_only');
  const [providers, setProviders] = useState<ProviderResponse[]>([]);
  const [domains, setDomains] = useState<DomainResponse[]>([]);
  const [activeTab, setActiveTab] = useState<SsoTabKey>('policy');
  const [providersDirty, setProvidersDirty] = useState(false);
  const [pendingTab, setPendingTab] = useState<SsoTabKey | null>(null);
  const [discardSignal, setDiscardSignal] = useState(0);

  const loadAll = useCallback(async () => {
    try {
      const [policyRes, providersRes, domainsRes] = await Promise.all([
        AXIOS_INSTANCE.get<PolicyResponse>('/api/v1/tenant-settings/sso/policy'),
        AXIOS_INSTANCE.get<ProviderResponse[]>('/api/v1/tenant-settings/sso/providers'),
        AXIOS_INSTANCE.get<DomainResponse[]>('/api/v1/tenant-settings/sso/domains'),
      ]);
      setLoginMode(policyRes.data.login_mode);
      setProviders(providersRes.data);
      setDomains(domainsRes.data);
    } catch (e: any) {
      push({ kind: 'error', message: getApiErrorMessage(e, 'Failed to load SSO settings') });
    }
  }, [push]);

  useEffect(() => {
    setIsLoading(true);
    loadAll().finally(() => setIsLoading(false));
  }, [loadAll]);

  const handleSavePolicy = useCallback(
    async (mode: LoginMode) => {
      await AXIOS_INSTANCE.put('/api/v1/tenant-settings/sso/policy', {
        login_mode: mode,
        domain_verification_required: true,
      });
      push({ kind: 'success', message: 'Login policy saved' });
      await loadAll();
    },
    [loadAll, push],
  );

  const refresh = useCallback(async () => {
    await loadAll();
  }, [loadAll]);

  const changeTab = (nextTab: SsoTabKey) => {
    if (nextTab === activeTab) return;
    if (activeTab === 'providers' && providersDirty) {
      setPendingTab(nextTab);
      return;
    }
    setActiveTab(nextTab);
  };

  const confirmDiscardAndSwitchTabs = () => {
    if (!pendingTab) return;
    setDiscardSignal((v) => v + 1);
    setProvidersDirty(false);
    setActiveTab(pendingTab);
    setPendingTab(null);
  };

  if (isLoading) {
    return (
      <Page maxWidth="xl">
        <PageBody>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner size="sm" />
            Loading SSO settings...
          </div>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="xl">
      <PageHeader
        title="SSO Settings"
        description="Manage login policy, identity providers, and verified domains."
      />
      <PageBody className="space-y-6 pb-10">
        <SsoStatusBar
          loginMode={loginMode}
          providers={providers}
          domains={domains}
          onTabChange={changeTab}
        />

        <Tabs defaultValue="policy" value={activeTab} onValueChange={(v) => changeTab(v as SsoTabKey)}>
          <TabsList variant="underline" className="w-full">
            <TabsTrigger variant="underline" value="policy">Login Policy</TabsTrigger>
            <TabsTrigger variant="underline" value="domains">Verified Domains</TabsTrigger>
            <TabsTrigger variant="underline" value="providers">SSO Providers</TabsTrigger>
          </TabsList>

          <TabsContent value="policy">
            <PolicyTab
              loginMode={loginMode}
              providers={providers}
              domains={domains}
              onSave={handleSavePolicy}
            />
          </TabsContent>
          <TabsContent value="domains">
            <DomainsTab domains={domains} loginMode={loginMode} onRefresh={refresh} />
          </TabsContent>
          <TabsContent value="providers">
            <ProvidersTab
              providers={providers}
              loginMode={loginMode}
              onRefresh={refresh}
              onDirtyChange={setProvidersDirty}
              discardSignal={discardSignal}
            />
          </TabsContent>
        </Tabs>
      </PageBody>

      <ConfirmationModal
        open={pendingTab !== null}
        onClose={() => setPendingTab(null)}
        onConfirm={confirmDiscardAndSwitchTabs}
        title="You have unsaved changes"
        body="You have unsaved changes in SSO Providers. Discard changes and switch tabs?"
        confirmLabel="Discard and Switch"
        confirmVariant="destructive"
      />
    </Page>
  );
}

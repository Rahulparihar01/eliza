/**
 * AI Providers Page
 * 
 * Platform admin page for managing AI providers.
 * 
 * Migrated to DS components (Jan 2026).
 * 
 * DS Components used:
 * - Page, PageHeader, PageBody, SectionHeader (layout)
 * - Button, Input, Select, SelectOption, Checkbox, Label (form)
 * - Badge, Spinner (feedback)
 * - Modal, ModalBackdrop, ModalContent, ModalHeader, ModalTitle, ModalDescription, ModalBody, ModalFooter (dialogs)
 */

import React, { useState, useMemo } from 'react';
import {
  CpuChipIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  TrashIcon,
  CheckIcon,
  XCircleIcon,
  GlobeAltIcon,
  ShareIcon,
  BoltIcon,
  ClockIcon,
  KeyIcon,
  ChartBarIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  PlayIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Input,
  Select,
  SelectOption,
  Checkbox,
  Label,
  Badge,
  Spinner,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
} from '../../components/ui';

interface SharedTenantInfo {
  customer_id: string;
  customer_name: string;
  is_enabled: boolean;
  shared_at: string;
}

interface PlatformProvider {
  id: number;
  customer_id: string;
  provider_type: string;
  name: string | null;
  is_enabled: boolean;
  is_healthy: boolean;
  last_health_check: string | null;
  config_summary: Record<string, any>;
  available_models: string[];
  default_model: string | null;
  is_global_shared: boolean;
  shared_with_tenants: SharedTenantInfo[];
  shared_with_count: number;
  is_adoption_source: boolean;
  chatgpt_workspace_id: string | null;
  created_at: string;
  updated_at: string | null;
  error_count: number;
  last_error: string | null;
}

interface Tenant {
  id: number;
  customer_id: string;
  name: string;
  display_name: string | null;
  is_active: boolean;
}

// Sharing Modal Component
function SharingModal({
  provider,
  allTenants,
  onClose,
  onSave,
  isSaving,
}: {
  provider: PlatformProvider;
  allTenants: Tenant[];
  onClose: () => void;
  onSave: (data: any) => void;
  isSaving: boolean;
}) {
  const [isGlobal, setIsGlobal] = useState(provider.is_global_shared);
  const [selectedTenants, setSelectedTenants] = useState<string[]>(
    provider.shared_with_tenants.map(t => t.customer_id)
  );
  const [initialTenants] = useState<string[]>(
    provider.shared_with_tenants.map(t => t.customer_id)
  );
  const [tenantSearchQuery, setTenantSearchQuery] = useState('');

  const filteredTenants = allTenants.filter((tenant) => {
    if (!tenantSearchQuery) return true;
    const query = tenantSearchQuery.toLowerCase();
    return (
      tenant.customer_id.toLowerCase().includes(query) ||
      tenant.name.toLowerCase().includes(query) ||
      (tenant.display_name || '').toLowerCase().includes(query)
    );
  });

  const handleSave = () => {
    const toShare = selectedTenants.filter(id => !initialTenants.includes(id));
    const toUnshare = initialTenants.filter(id => !selectedTenants.includes(id));
    
    onSave({
      is_global_shared: isGlobal,
      share_with_tenant_ids: toShare.length > 0 ? toShare : null,
      unshare_from_tenant_ids: toUnshare.length > 0 ? toUnshare : null,
    });
  };

  return (
    <Modal open={true} onClose={onClose}>
      <ModalBackdrop />
      <ModalContent className="max-w-lg">
        <ModalHeader>
          <ModalTitle>Manage Sharing</ModalTitle>
          <ModalDescription>{provider.name || provider.provider_type}</ModalDescription>
        </ModalHeader>

        <ModalBody className="space-y-4">
          {/* Global toggle */}
          <div 
            className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-surface-2"
            onClick={() => {
              const newValue = !isGlobal;
              setIsGlobal(newValue);
              if (newValue) setSelectedTenants([]);
            }}
          >
            <Checkbox
              checked={isGlobal}
              onChange={(e) => {
                e.stopPropagation();
                setIsGlobal(e.target.checked);
                if (e.target.checked) setSelectedTenants([]);
              }}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <GlobeAltIcon className="w-4 h-4 text-eliza-red" />
                <span className="text-sm font-medium text-charcoal dark:text-gray-100">Global AI Provider</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Available to all tenants automatically</p>
            </div>
          </div>

          {!isGlobal && (
            <div>
              <Label className="mb-2">Share with specific tenants</Label>
              <div className="relative mb-3">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search tenants..."
                  value={tenantSearchQuery}
                  onChange={(e) => setTenantSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>

              {selectedTenants.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {selectedTenants.map((tenantId) => {
                    const tenant = allTenants.find(t => t.customer_id === tenantId);
                    return (
                      <Badge key={tenantId} variant="brand" className="inline-flex items-center gap-1">
                        {tenant?.display_name || tenant?.name || tenantId}
                        <button 
                          onClick={() => setSelectedTenants(selectedTenants.filter(id => id !== tenantId))} 
                          className="hover:text-red-500 ml-1"
                        >
                          <XMarkIcon className="w-3 h-3" />
                        </button>
                      </Badge>
                    );
                  })}
                </div>
              )}

              <div className="max-h-64 overflow-y-auto border border-gray-200 dark:border-dark-border rounded-lg">
                {filteredTenants.length === 0 ? (
                  <div className="px-3 py-4 text-center text-gray-500 dark:text-gray-400 text-sm">No tenants available</div>
                ) : (
                  filteredTenants.map((tenant) => {
                    const isSelected = selectedTenants.includes(tenant.customer_id);
                    return (
                      <div 
                        key={tenant.customer_id} 
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer border-b border-gray-200 dark:border-dark-border last:border-b-0"
                        onClick={() => {
                          if (isSelected) {
                            setSelectedTenants(selectedTenants.filter(id => id !== tenant.customer_id));
                          } else {
                            setSelectedTenants([...selectedTenants, tenant.customer_id]);
                          }
                        }}
                      >
                        <Checkbox
                          checked={isSelected}
                          onChange={(e) => {
                            e.stopPropagation();
                            if (e.target.checked) {
                              setSelectedTenants([...selectedTenants, tenant.customer_id]);
                            } else {
                              setSelectedTenants(selectedTenants.filter(id => id !== tenant.customer_id));
                            }
                          }}
                        />
                        <div className="flex-1">
                          <span className="text-sm text-charcoal dark:text-gray-100">{tenant.display_name || tenant.name}</span>
                          <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">({tenant.customer_id})</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving && <Spinner size="sm" className="mr-2" />}
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

export function AIProvidersPage() {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  const [providerFilter, setProviderFilter] = useState<'all' | 'global' | 'shared'>('all');
  const [showProviderModal, setShowProviderModal] = useState(false);
  const [showSharingModal, setShowSharingModal] = useState(false);
  const [sharingProvider, setSharingProvider] = useState<PlatformProvider | null>(null);
  const [allTenants, setAllTenants] = useState<Tenant[]>([]);
  const [showAdoptionWarningModal, setShowAdoptionWarningModal] = useState(false);
  const [pendingSharingProvider, setPendingSharingProvider] = useState<PlatformProvider | null>(null);
  const [expandedProviderId, setExpandedProviderId] = useState<number | null>(null);
  const [testingProviderId, setTestingProviderId] = useState<number | null>(null);
  const [createTenantSearchQuery, setCreateTenantSearchQuery] = useState('');
  const [providerFormData, setProviderFormData] = useState({
    provider_type: 'openai',
    name: '',
    is_enabled: true,
    api_key: '',
    organization_id: '',
    aws_region: 'us-west-2',
    aws_access_key_id: '',
    aws_secret_access_key: '',
    available_models: [] as string[],
    default_model: '',
    is_global_shared: false,
    share_with_tenant_ids: [] as string[],
  });

  // Fetch all providers once (client-side filtering for smooth UX)
  const { data: providersData, isLoading } = useQuery({
    queryKey: ['platform-providers'],
    queryFn: async () => {
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/ai-providers');
      return response.data;
    },
  });

  // Client-side filtering - instant, no flash
  const filteredProviders = useMemo(() => {
    const providers = providersData?.providers || [];
    if (providerFilter === 'all') return providers;
    if (providerFilter === 'global') return providers.filter((p: PlatformProvider) => p.is_global_shared);
    if (providerFilter === 'shared') return providers.filter((p: PlatformProvider) => !p.is_global_shared && p.shared_with_count > 0);
    return providers;
  }, [providersData?.providers, providerFilter]);

  const fetchTenants = async () => {
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/tenants');
      setAllTenants(response.data.tenants || []);
    } catch (err) {
      console.error('Error fetching tenants:', err);
    }
  };

  // Create provider mutation
  const createProvider = useMutation({
    mutationFn: async (data: any) => {
      const response = await AXIOS_INSTANCE.post('/api/v1/platform-admin/ai-providers', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['platform-providers'] });
      addToast({ kind: 'success', message: 'AI provider created successfully' });
      setShowProviderModal(false);
      resetProviderForm();
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to create AI provider' });
    },
  });

  // Update sharing mutation
  const updateSharing = useMutation({
    mutationFn: async ({ providerId, data }: { providerId: number; data: any }) => {
      const response = await AXIOS_INSTANCE.put(`/api/v1/platform-admin/ai-providers/${providerId}/sharing`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['platform-providers'] });
      addToast({ kind: 'success', message: 'Sharing settings updated successfully' });
      setShowSharingModal(false);
      setSharingProvider(null);
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to update sharing settings' });
    },
  });

  // Delete provider mutation
  const deleteProvider = useMutation({
    mutationFn: async (providerId: number) => {
      await AXIOS_INSTANCE.delete(`/api/v1/platform-admin/ai-providers/${providerId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['platform-providers'] });
      addToast({ kind: 'success', message: 'AI provider deleted successfully' });
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to delete AI provider' });
    },
  });

  // Test provider connection mutation
  const testConnection = useMutation({
    mutationFn: async (providerId: number) => {
      const response = await AXIOS_INSTANCE.post(`/api/v1/platform-admin/ai-providers/${providerId}/test`);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['platform-providers'] });
      if (data.success) {
        addToast({ kind: 'success', message: `Connection test passed: ${data.message}` });
      } else {
        addToast({ kind: 'error', message: `Connection test failed: ${data.error_details || data.message}` });
      }
      setTestingProviderId(null);
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to test connection' });
      setTestingProviderId(null);
    },
  });

  const resetProviderForm = () => {
    setProviderFormData({
      provider_type: 'openai',
      name: '',
      is_enabled: true,
      api_key: '',
      organization_id: '',
      aws_region: 'us-west-2',
      aws_access_key_id: '',
      aws_secret_access_key: '',
      available_models: [],
      default_model: '',
      is_global_shared: false,
      share_with_tenant_ids: [],
    });
    setCreateTenantSearchQuery('');
  };

  // Filtered tenants for creation modal
  const filteredTenantsForCreate = allTenants.filter((tenant) => {
    if (!createTenantSearchQuery) return true;
    const query = createTenantSearchQuery.toLowerCase();
    return (
      tenant.customer_id.toLowerCase().includes(query) ||
      tenant.name.toLowerCase().includes(query) ||
      (tenant.display_name || '').toLowerCase().includes(query)
    );
  });

  const handleCreateProvider = () => {
    const config: any = {};
    
    if (['openai', 'anthropic', 'groq'].includes(providerFormData.provider_type)) {
      config.api_key = providerFormData.api_key;
      if (providerFormData.organization_id) config.organization_id = providerFormData.organization_id;
    } else if (providerFormData.provider_type === 'bedrock') {
      config.aws_region = providerFormData.aws_region;
      config.aws_access_key_id = providerFormData.aws_access_key_id;
      config.aws_secret_access_key = providerFormData.aws_secret_access_key;
    }
    
    if (providerFormData.available_models.length > 0) config.available_models = providerFormData.available_models;
    if (providerFormData.default_model) config.default_model = providerFormData.default_model;

    createProvider.mutate({
      provider_type: providerFormData.provider_type,
      name: providerFormData.name || null,
      is_enabled: providerFormData.is_enabled,
      config,
      is_global_shared: providerFormData.is_global_shared,
      share_with_tenant_ids: providerFormData.share_with_tenant_ids.length > 0 ? providerFormData.share_with_tenant_ids : null,
    });
  };

  const handleOpenSharingModal = (provider: PlatformProvider) => {
    if (provider.is_adoption_source) {
      setPendingSharingProvider(provider);
      setShowAdoptionWarningModal(true);
    } else {
      setSharingProvider(provider);
      fetchTenants();
      setShowSharingModal(true);
    }
  };

  const handleConfirmAdoptionDisable = () => {
    if (pendingSharingProvider) {
      setSharingProvider(pendingSharingProvider);
      fetchTenants();
      setShowSharingModal(true);
    }
    setShowAdoptionWarningModal(false);
    setPendingSharingProvider(null);
  };

  const headerActions = (
    <Button onClick={() => { resetProviderForm(); fetchTenants(); setShowProviderModal(true); }}>
      <PlusIcon className="w-4 h-4 mr-2" />
      Add Provider
    </Button>
  );

  if (isLoading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="AI Providers"
          description="Manage platform AI provider configurations"
          actions={headerActions}
        />
        <PageBody>
          <div className="flex items-center justify-center h-64">
            <Spinner size="lg" />
          </div>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="xl">
      <PageHeader
        title="AI Providers"
        description="Manage platform AI provider configurations"
        actions={headerActions}
      />
      <PageBody>
        {/* Filter Pills */}
        <div className="flex items-center gap-2 mb-6">
          <span className="text-sm text-gray-500 dark:text-gray-400 mr-2">Filter:</span>
          {(['all', 'global', 'shared'] as const).map((filter) => (
            <Button
              key={filter}
              onClick={() => setProviderFilter(filter)}
              variant={providerFilter === filter ? 'default' : 'outline'}
              size="sm"
            >
              {filter === 'all' ? 'All Providers' : filter === 'global' ? 'Global' : 'Shared'}
            </Button>
          ))}
        </div>

        {/* Providers List */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
          {filteredProviders.length === 0 ? (
            <div className="px-4 py-12 text-center text-gray-500 dark:text-gray-400 text-sm">
              {providerFilter === 'all' 
                ? 'No AI providers configured yet. Click "Add Provider" to get started.'
                : `No ${providerFilter} providers found.`
              }
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-dark-border">
              {filteredProviders.map((provider: PlatformProvider) => {
                const isExpanded = expandedProviderId === provider.id;
                return (
                  <div key={provider.id} className="transition-colors">
                    {/* Provider Row */}
                    <div
                      className="px-4 py-4 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer"
                      onClick={() => setExpandedProviderId(isExpanded ? null : provider.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          {/* Expand/Collapse Icon */}
                          <div className="mt-1 text-gray-400 dark:text-gray-500">
                            {isExpanded ? <ChevronDownIcon className="w-4 h-4" /> : <ChevronRightIcon className="w-4 h-4" />}
                          </div>
                          
                          {/* Provider Icon */}
                          <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-gray-100 dark:bg-dark-surface-2">
                            <CpuChipIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                          </div>
                          
                          {/* Provider Info */}
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium text-charcoal dark:text-gray-100">
                                {provider.name || provider.provider_type}
                              </span>
                              <Badge variant="secondary" className="uppercase">
                                {provider.provider_type}
                              </Badge>
                              {provider.is_global_shared && (
                                <Badge variant="brand" className="inline-flex items-center gap-1">
                                  <GlobeAltIcon className="w-3 h-3" />
                                  Global
                                </Badge>
                              )}
                              {provider.shared_with_count > 0 && !provider.is_global_shared && (
                                <Badge variant="info" className="inline-flex items-center gap-1">
                                  <ShareIcon className="w-3 h-3" />
                                  Shared ({provider.shared_with_count})
                                </Badge>
                              )}
                              <Badge variant={provider.is_enabled ? 'success' : 'secondary'}>
                                {provider.is_enabled ? 'Enabled' : 'Disabled'}
                              </Badge>
                            </div>
                            <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                              {provider.available_models?.length > 0 ? (
                                <span>
                                  {provider.available_models.slice(0, 3).join(', ')}
                                  {provider.available_models.length > 3 ? ` +${provider.available_models.length - 3} more` : ''}
                                </span>
                              ) : (
                                <span>No models configured</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleOpenSharingModal(provider)} 
                            title="Manage sharing"
                          >
                            <ShareIcon className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => { 
                              if (window.confirm('Delete this provider?')) {
                                deleteProvider.mutate(provider.id); 
                              }
                            }} 
                            title="Delete provider"
                          >
                            <TrashIcon className="w-4 h-4 text-eliza-red" />
                          </Button>
                        </div>
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="px-4 pb-4">
                        <div className="ml-[72px] grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Left Column */}
                          <div className="space-y-4">
                            {/* Configuration */}
                            <div>
                              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2 flex items-center gap-1.5">
                                <KeyIcon className="w-3.5 h-3.5" />
                                Configuration
                              </h4>
                              <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3 space-y-2">
                                <div className="flex items-center justify-between text-sm">
                                  <span className="text-gray-500 dark:text-gray-400">Provider Type</span>
                                  <span className="text-charcoal dark:text-gray-100 font-medium uppercase">{provider.provider_type}</span>
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                  <span className="text-gray-500 dark:text-gray-400">Default Model</span>
                                  <span className="text-charcoal dark:text-gray-100">{provider.default_model || 'Not set'}</span>
                                </div>
                              </div>
                            </div>
                            
                            {/* Available Models */}
                            <div>
                              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">Available Models</h4>
                              <div className="flex flex-wrap gap-1.5">
                                {provider.available_models?.length > 0 ? (
                                  provider.available_models.map((model) => (
                                    <Badge 
                                      key={model} 
                                      variant={model === provider.default_model ? 'brand' : 'secondary'}
                                    >
                                      {model}
                                    </Badge>
                                  ))
                                ) : (
                                  <span className="text-xs text-gray-500 dark:text-gray-400">No models configured</span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Right Column */}
                          <div className="space-y-4">
                            {/* Health & Status */}
                            <div>
                              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2 flex items-center gap-1.5">
                                <BoltIcon className="w-3.5 h-3.5" />
                                Health & Status
                              </h4>
                              <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3 space-y-3">
                                <div className="flex items-center justify-between text-sm">
                                  <span className="text-gray-500 dark:text-gray-400">Status</span>
                                  {!provider.last_health_check ? (
                                    <span className="flex items-center gap-1 text-gray-400">
                                      <ClockIcon className="w-3.5 h-3.5" /> Not tested
                                    </span>
                                  ) : provider.is_healthy ? (
                                    <span className="flex items-center gap-1 text-green-500">
                                      <CheckIcon className="w-3.5 h-3.5" /> Healthy
                                    </span>
                                  ) : (
                                    <span className="flex items-center gap-1 text-eliza-red">
                                      <XCircleIcon className="w-3.5 h-3.5" /> Unhealthy
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center justify-between text-sm">
                                  <span className="text-gray-500 dark:text-gray-400">Error Count</span>
                                  <span className={provider.error_count > 0 ? 'text-eliza-red' : 'text-charcoal dark:text-gray-100'}>
                                    {provider.error_count}
                                  </span>
                                </div>
                                {provider.last_health_check && (
                                  <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-500 dark:text-gray-400">Last Check</span>
                                    <span className="text-charcoal dark:text-gray-100 flex items-center gap-1">
                                      <ClockIcon className="w-3.5 h-3.5 text-gray-400" />
                                      {new Date(provider.last_health_check).toLocaleString()}
                                    </span>
                                  </div>
                                )}
                                {/* Test Connection Button */}
                                <div className="pt-2 border-t border-gray-200 dark:border-dark-border">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="w-full"
                                    disabled={testingProviderId === provider.id}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setTestingProviderId(provider.id);
                                      testConnection.mutate(provider.id);
                                    }}
                                  >
                                    {testingProviderId === provider.id ? (
                                      <>
                                        <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                                        Testing...
                                      </>
                                    ) : (
                                      <>
                                        <PlayIcon className="w-4 h-4 mr-2" />
                                        Test Connection
                                      </>
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>

                            {/* Sharing */}
                            <div>
                              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2 flex items-center gap-1.5">
                                <ShareIcon className="w-3.5 h-3.5" />
                                Sharing
                              </h4>
                              <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-3">
                                {provider.is_global_shared ? (
                                  <div className="flex items-center gap-2 text-sm text-eliza-red">
                                    <GlobeAltIcon className="w-4 h-4" />
                                    Available to all tenants
                                  </div>
                                ) : provider.shared_with_tenants.length > 0 ? (
                                  <div className="space-y-2">
                                    <span className="text-sm text-gray-500 dark:text-gray-400">
                                      Shared with {provider.shared_with_tenants.length} tenant(s)
                                    </span>
                                    <div className="flex flex-wrap gap-1.5">
                                      {provider.shared_with_tenants.map((t) => (
                                        <Badge key={t.customer_id} variant="secondary">
                                          {t.customer_name}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                ) : (
                                  <span className="text-sm text-gray-500 dark:text-gray-400">Not shared with any tenants</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </PageBody>

      {/* Create Provider Modal */}
      <Modal open={showProviderModal} onClose={() => setShowProviderModal(false)}>
        <ModalBackdrop />
        <ModalContent className="max-w-2xl">
          <ModalHeader>
            <ModalTitle>Add AI Provider</ModalTitle>
          </ModalHeader>
          
          <ModalBody className="space-y-4">
            {/* Provider Type */}
            <div>
              <Label className="mb-2">Provider Type</Label>
              <Select 
                value={providerFormData.provider_type} 
                onValueChange={(value) => setProviderFormData({ ...providerFormData, provider_type: value })}
              >
                <SelectOption value="openai">OpenAI</SelectOption>
                <SelectOption value="anthropic">Anthropic</SelectOption>
                <SelectOption value="groq">Groq</SelectOption>
                <SelectOption value="bedrock">AWS Bedrock</SelectOption>
              </Select>
            </div>

            {/* Display Name */}
            <div>
              <Label className="mb-2">Display Name</Label>
              <Input 
                type="text" 
                value={providerFormData.name} 
                onChange={(e) => setProviderFormData({ ...providerFormData, name: e.target.value })} 
                placeholder="e.g., OpenAI Production" 
              />
            </div>

            {/* API Key for OpenAI/Anthropic/Groq */}
            {['openai', 'anthropic', 'groq'].includes(providerFormData.provider_type) && (
              <div>
                <Label className="mb-2">API Key</Label>
                <Input 
                  type="password" 
                  value={providerFormData.api_key} 
                  onChange={(e) => setProviderFormData({ ...providerFormData, api_key: e.target.value })} 
                  placeholder="sk-..." 
                />
              </div>
            )}

            {/* AWS Bedrock Fields */}
            {providerFormData.provider_type === 'bedrock' && (
              <>
                <div>
                  <Label className="mb-2">AWS Region</Label>
                  <Input 
                    type="text" 
                    value={providerFormData.aws_region} 
                    onChange={(e) => setProviderFormData({ ...providerFormData, aws_region: e.target.value })} 
                    placeholder="us-west-2" 
                  />
                </div>
                <div>
                  <Label className="mb-2">AWS Access Key ID</Label>
                  <Input 
                    type="text" 
                    value={providerFormData.aws_access_key_id} 
                    onChange={(e) => setProviderFormData({ ...providerFormData, aws_access_key_id: e.target.value })} 
                    placeholder="AKIA..." 
                  />
                </div>
                <div>
                  <Label className="mb-2">AWS Secret Access Key</Label>
                  <Input 
                    type="password" 
                    value={providerFormData.aws_secret_access_key} 
                    onChange={(e) => setProviderFormData({ ...providerFormData, aws_secret_access_key: e.target.value })} 
                  />
                </div>
              </>
            )}

            {/* Sharing Settings */}
            <div className="pt-4 border-t border-gray-200 dark:border-dark-border space-y-4">
              <Label className="text-sm font-medium">Sharing Settings</Label>
              
              {/* Global toggle */}
              <div 
                className="flex items-center gap-3 cursor-pointer p-3 rounded-lg border border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-surface-2"
                onClick={() => {
                  const newValue = !providerFormData.is_global_shared;
                  setProviderFormData({
                    ...providerFormData,
                    is_global_shared: newValue,
                    share_with_tenant_ids: newValue ? [] : providerFormData.share_with_tenant_ids
                  });
                }}
              >
                <Checkbox
                  checked={providerFormData.is_global_shared}
                  onChange={(e) => {
                    e.stopPropagation();
                    setProviderFormData({
                      ...providerFormData,
                      is_global_shared: e.target.checked,
                      share_with_tenant_ids: e.target.checked ? [] : providerFormData.share_with_tenant_ids
                    });
                  }}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <GlobeAltIcon className="w-4 h-4 text-eliza-red" />
                    <span className="text-sm font-medium text-charcoal dark:text-gray-100">Global AI Provider</span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Available to all tenants automatically</p>
                </div>
              </div>

              {/* Tenant selection when not global */}
              {!providerFormData.is_global_shared && (
                <div>
                  <Label className="mb-2">Share with specific tenants</Label>
                  <div className="relative mb-3">
                    <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="Search tenants..."
                      value={createTenantSearchQuery}
                      onChange={(e) => setCreateTenantSearchQuery(e.target.value)}
                      className="pl-9"
                    />
                  </div>

                  {providerFormData.share_with_tenant_ids.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-3">
                      {providerFormData.share_with_tenant_ids.map((tenantId) => {
                        const tenant = allTenants.find(t => t.customer_id === tenantId);
                        return (
                          <Badge key={tenantId} variant="brand" className="inline-flex items-center gap-1">
                            {tenant?.display_name || tenant?.name || tenantId}
                            <button 
                              onClick={() => setProviderFormData({
                                ...providerFormData,
                                share_with_tenant_ids: providerFormData.share_with_tenant_ids.filter(id => id !== tenantId)
                              })} 
                              className="hover:text-red-500 ml-1"
                            >
                              <XMarkIcon className="w-3 h-3" />
                            </button>
                          </Badge>
                        );
                      })}
                    </div>
                  )}

                  <div className="max-h-48 overflow-y-auto border border-gray-200 dark:border-dark-border rounded-lg">
                    {filteredTenantsForCreate.length === 0 ? (
                      <div className="px-3 py-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                        {allTenants.length === 0 ? 'Loading tenants...' : 'No tenants found'}
                      </div>
                    ) : (
                      filteredTenantsForCreate.map((tenant) => {
                        const isSelected = providerFormData.share_with_tenant_ids.includes(tenant.customer_id);
                        return (
                          <div 
                            key={tenant.customer_id} 
                            className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer border-b border-gray-200 dark:border-dark-border last:border-b-0"
                            onClick={() => {
                              if (isSelected) {
                                setProviderFormData({
                                  ...providerFormData,
                                  share_with_tenant_ids: providerFormData.share_with_tenant_ids.filter(id => id !== tenant.customer_id)
                                });
                              } else {
                                setProviderFormData({
                                  ...providerFormData,
                                  share_with_tenant_ids: [...providerFormData.share_with_tenant_ids, tenant.customer_id]
                                });
                              }
                            }}
                          >
                            <Checkbox
                              checked={isSelected}
                              onChange={(e) => {
                                e.stopPropagation();
                                if (e.target.checked) {
                                  setProviderFormData({
                                    ...providerFormData,
                                    share_with_tenant_ids: [...providerFormData.share_with_tenant_ids, tenant.customer_id]
                                  });
                                } else {
                                  setProviderFormData({
                                    ...providerFormData,
                                    share_with_tenant_ids: providerFormData.share_with_tenant_ids.filter(id => id !== tenant.customer_id)
                                  });
                                }
                              }}
                            />
                            <div className="flex-1">
                              <span className="text-sm text-charcoal dark:text-gray-100">{tenant.display_name || tenant.name}</span>
                              <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">({tenant.customer_id})</span>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    {providerFormData.share_with_tenant_ids.length === 0 
                      ? 'Provider will only be available to the platform tenant unless shared.'
                      : `Will be shared with ${providerFormData.share_with_tenant_ids.length} tenant(s)`
                    }
                  </p>
                </div>
              )}
            </div>
          </ModalBody>

          <ModalFooter>
            <Button variant="ghost" onClick={() => setShowProviderModal(false)}>Cancel</Button>
            <Button onClick={handleCreateProvider} disabled={createProvider.isPending}>
              {createProvider.isPending && <Spinner size="sm" className="mr-2" />}
              {createProvider.isPending ? 'Creating...' : 'Create Provider'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Adoption Warning Modal */}
      <Modal 
        open={showAdoptionWarningModal} 
        onClose={() => { setShowAdoptionWarningModal(false); setPendingSharingProvider(null); }}
      >
        <ModalBackdrop />
        <ModalContent className="max-w-md">
          <ModalHeader>
            <div className="flex items-center gap-2">
              <ChartBarIcon className="w-5 h-5 text-amber-500" />
              <ModalTitle>Adoption Tracking Warning</ModalTitle>
            </div>
          </ModalHeader>
          
          <ModalBody>
            <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg mb-4">
              <XCircleIcon className="w-6 h-6 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-charcoal dark:text-gray-100 font-medium">
                  This API key is currently used for adoption metrics tracking.
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Sharing this key will <strong>automatically disable</strong> adoption tracking for it.
                </p>
              </div>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Do you want to continue and disable adoption tracking for this key?
            </p>
          </ModalBody>

          <ModalFooter>
            <Button variant="ghost" onClick={() => { setShowAdoptionWarningModal(false); setPendingSharingProvider(null); }}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmAdoptionDisable}>
              Continue & Disable Adoption
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Sharing Modal */}
      {showSharingModal && sharingProvider && (
        <SharingModal 
          provider={sharingProvider} 
          allTenants={allTenants} 
          onClose={() => { setShowSharingModal(false); setSharingProvider(null); }} 
          onSave={(data) => updateSharing.mutate({ providerId: sharingProvider.id, data })} 
          isSaving={updateSharing.isPending} 
        />
      )}
    </Page>
  );
}

export default AIProvidersPage;

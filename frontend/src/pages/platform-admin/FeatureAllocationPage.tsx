/**
 * Feature Allocation Page
 * 
 * Platform admin page for allocating features to tenants.
 * Uses DS Chip components for feature toggle selection.
 * 
 * Migrated to DS components (Jan 2026).
 * 
 * DS Components used:
 * - Page, PageHeader, PageBody (layout)
 * - Button, Input (form)
 * - Alert, Spinner (feedback)
 * - Chip, ChipGroup (feature toggles)
 */

import React, { useState, useEffect } from 'react';
import {
  ShieldCheckIcon,
  BuildingOffice2Icon,
  MagnifyingGlassIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Input,
  Alert,
  Spinner,
  Chip,
  ChipGroup,
} from '../../components/ui';

interface PlatformFeature {
  id: number;
  feature_key: string;
  display_name: string;
  description: string | null;
  category: string | null;
  icon: string | null;
  sort_order: number;
  is_active: boolean;
  permission_count: number;
}

interface Tenant {
  id: number;
  customer_id: string;
  name: string;
  display_name: string | null;
  is_active: boolean;
}

interface FeatureAllocation {
  id: number;
  customer_id: string;
  feature_id: number;
  feature_key: string;
  feature_display_name: string;
  is_enabled: boolean;
}

export function FeatureAllocationPage() {
  const [features, setFeatures] = useState<PlatformFeature[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [enabledFeatures, setEnabledFeatures] = useState<Set<number>>(new Set());
  const [originalEnabledFeatures, setOriginalEnabledFeatures] = useState<Set<number>>(new Set());
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (selectedTenant) {
      fetchTenantFeatures(selectedTenant);
    }
  }, [selectedTenant]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [featuresRes, tenantsRes] = await Promise.all([
        AXIOS_INSTANCE.get('/api/v1/platform-admin/features'),
        AXIOS_INSTANCE.get('/api/v1/platform-admin/tenants'),
      ]);
      setFeatures(featuresRes.data);
      setTenants(tenantsRes.data.tenants);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching data:', err);
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchTenantFeatures = async (customerId: string) => {
    try {
      const response = await AXIOS_INSTANCE.get(`/api/v1/platform-admin/tenants/${customerId}/features`);
      
      // Track which features are currently enabled
      const enabled = new Set<number>(
        response.data.filter((a: FeatureAllocation) => a.is_enabled).map((a: FeatureAllocation) => a.feature_id)
      );
      setEnabledFeatures(enabled);
      setOriginalEnabledFeatures(new Set(enabled));
      setHasUnsavedChanges(false);
    } catch (err: any) {
      console.error('Error fetching tenant features:', err);
    }
  };

  const handleToggleFeature = (featureId: number) => {
    if (!selectedTenant) return;
    
    // Toggle local state only - no API call
    setEnabledFeatures(prev => {
      const newSet = new Set(prev);
      if (newSet.has(featureId)) {
        newSet.delete(featureId);
      } else {
        newSet.add(featureId);
      }
      
      // Check if we have unsaved changes
      const hasChanges = !setsAreEqual(newSet, originalEnabledFeatures);
      setHasUnsavedChanges(hasChanges);
      
      return newSet;
    });
  };
  
  // Helper to compare sets
  const setsAreEqual = (a: Set<number>, b: Set<number>) => {
    if (a.size !== b.size) return false;
    const aArray = Array.from(a);
    for (let i = 0; i < aArray.length; i++) {
      if (!b.has(aArray[i])) return false;
    }
    return true;
  };
  
  const handleSaveChanges = async () => {
    if (!selectedTenant || !hasUnsavedChanges) return;
    
    setSaving(true);
    setError(null);
    
    try {
      // Get the list of feature IDs that should be enabled
      const featureIds = Array.from(enabledFeatures);
      
      await AXIOS_INSTANCE.put(`/api/v1/platform-admin/tenants/${selectedTenant}/features`, {
        feature_ids: featureIds
      });
      
      // Update original state to match current
      setOriginalEnabledFeatures(new Set(enabledFeatures));
      setHasUnsavedChanges(false);
      
      // Refresh allocations from server
      await fetchTenantFeatures(selectedTenant);
    } catch (err: any) {
      console.error('Error saving features:', err);
      setError(err.response?.data?.detail || 'Failed to save feature changes');
    } finally {
      setSaving(false);
    }
  };
  
  const handleDiscardChanges = () => {
    setEnabledFeatures(new Set(originalEnabledFeatures));
    setHasUnsavedChanges(false);
  };

  const filteredTenants = tenants.filter(tenant =>
    tenant.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tenant.customer_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const groupedFeatures = features.reduce((acc, feature) => {
    const category = feature.category || 'other';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(feature);
    return acc;
  }, {} as Record<string, PlatformFeature[]>);

  const categoryNames: Record<string, string> = {
    assistant: 'Assistant',
    admin: 'Administration',
    labs: 'Labs',
    recruiter: 'Recruiter',
    analytics: 'Analytics',
    data: 'Data & Documents',
    config: 'Configuration',
    intelligence: 'AI Intelligence',
    other: 'Other'
  };

  if (loading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Feature Allocation"
          description="Allocate platform features to tenants"
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
        title="Feature Allocation"
        description="Allocate platform features to tenants"
      />
      <PageBody>
        {error && (
          <Alert variant="error" onDismiss={() => setError(null)} className="mb-6">
            {error}
          </Alert>
        )}

        <div className="grid grid-cols-3 gap-8">
          {/* Tenant List */}
          <div className="col-span-1">
            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border">
              <div className="p-4 border-b border-gray-200 dark:border-dark-border">
                <h2 className="font-medium text-charcoal dark:text-gray-100 mb-3">Select Tenant</h2>
                <div className="relative">
                  <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 pointer-events-none z-10" />
                  <Input
                    type="text"
                    placeholder="Search tenants..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
              <div className="max-h-[600px] overflow-y-auto">
                {filteredTenants.length === 0 ? (
                  <p className="p-4 text-gray-500 dark:text-gray-400 text-sm">No tenants found</p>
                ) : (
                  filteredTenants.map((tenant, index) => (
                    <button
                      key={tenant.id}
                      onClick={() => setSelectedTenant(tenant.customer_id)}
                      className={`
                        w-full px-4 py-3 text-left flex items-center gap-3 border-b border-gray-200 dark:border-dark-border last:border-b-0 transition-colors
                        ${index === filteredTenants.length - 1 ? 'rounded-b-lg' : ''}
                        ${selectedTenant === tenant.customer_id 
                          ? 'bg-eliza-red/5' 
                          : 'hover:bg-gray-50 dark:hover:bg-dark-surface-2'}
                      `}
                    >
                      <div className={`
                        w-8 h-8 rounded-lg flex items-center justify-center
                        ${selectedTenant === tenant.customer_id 
                          ? 'bg-eliza-red/20' 
                          : 'bg-gray-100 dark:bg-dark-surface-2'}
                      `}>
                        <BuildingOffice2Icon className={`w-4 h-4 ${selectedTenant === tenant.customer_id ? 'text-eliza-red' : 'text-gray-500 dark:text-gray-400'}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className={`font-medium truncate ${selectedTenant === tenant.customer_id ? 'text-eliza-red' : 'text-charcoal dark:text-gray-100'}`}>
                          {tenant.name}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{tenant.customer_id}</div>
                      </div>
                      {selectedTenant === tenant.customer_id && (
                        <CheckIcon className="w-5 h-5 text-eliza-red" />
                      )}
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Feature Allocation */}
          <div className="col-span-2">
            {!selectedTenant ? (
              <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border p-12 text-center">
                <ShieldCheckIcon className="w-12 h-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-charcoal dark:text-gray-100 mb-2">Select a Tenant</h3>
                <p className="text-gray-500 dark:text-gray-400">Choose a tenant from the list to manage their feature allocations.</p>
              </div>
            ) : (
              <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
                <div className="p-4 border-b border-gray-200 dark:border-dark-border flex items-center justify-between">
                  <div>
                    <h2 className="font-medium text-charcoal dark:text-gray-100">
                      Features for {tenants.find(t => t.customer_id === selectedTenant)?.name}
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Click features to enable or disable them</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      {enabledFeatures.size} / {features.length} enabled
                    </div>
                    {hasUnsavedChanges && (
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleDiscardChanges}
                        >
                          Discard
                        </Button>
                        <Button
                          size="sm"
                          onClick={handleSaveChanges}
                          disabled={saving}
                        >
                          {saving && <Spinner size="sm" className="mr-2" />}
                          {saving ? 'Saving...' : (
                            <>
                              <CheckIcon className="w-4 h-4 mr-1" />
                              Save Changes
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-6 space-y-6">
                  {Object.entries(groupedFeatures).map(([category, categoryFeatures]) => (
                    <ChipGroup key={category} label={categoryNames[category] || category}>
                      {categoryFeatures.map((feature) => {
                        const isEnabled = enabledFeatures.has(feature.id);
                        
                        return (
                          <Chip
                            key={feature.id}
                            selected={isEnabled}
                            onClick={() => handleToggleFeature(feature.id)}
                            title={feature.description || feature.feature_key}
                          >
                            {feature.display_name}
                          </Chip>
                        );
                      })}
                    </ChipGroup>
                  ))}
                </div>

                <div className="p-4 border-t border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    <strong className="text-eliza-red">Enabled Features:</strong>{' '}
                    {features.filter(f => enabledFeatures.has(f.id)).map(f => f.display_name).join(', ') || 'None'}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </PageBody>
    </Page>
  );
}

export default FeatureAllocationPage;

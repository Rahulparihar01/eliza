/**
 * Adoption Access Management Page
 * 
 * Platform admin page for managing cross-tenant adoption data access grants.
 * Allows admins to grant/revoke access for tenants to view other tenants' adoption metrics.
 * 
 * Migrated to Design System (Jan 2026)
 */

import React, { useState, useEffect } from 'react';
import {
  BuildingOffice2Icon,
  PlusIcon,
  TrashIcon,
  ArrowRightIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Select,
  SelectOption,
  Switch,
  Badge,
  Label,
  Alert,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  Panel,
  PanelHeader,
  PanelTitle,
  PanelDescription,
  PanelBody,
  PanelFooter,
  Spinner,
} from '../../components/ui';

interface AdoptionGrant {
  id: number;
  source_customer_id: string;
  source_customer_name: string | null;
  target_customer_id: string;
  target_customer_name: string | null;
  share_level: 'read' | 'admin';
  is_enabled: boolean;
  created_by_user_id: number | null;
  created_by_name: string | null;
  created_at: string;
  expires_at: string | null;
}

interface Tenant {
  id: number;
  customer_id: string;
  name: string;
  display_name: string | null;
  is_active: boolean;
}

export function AdoptionAccessPage() {
  const [grants, setGrants] = useState<AdoptionGrant[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal state (changed from inline form)
  const [showModal, setShowModal] = useState(false);
  const [sourceCustomerId, setSourceCustomerId] = useState('');
  const [targetCustomerId, setTargetCustomerId] = useState('');
  const [saving, setSaving] = useState(false);
  
  // Delete confirmation
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [grantsRes, tenantsRes] = await Promise.all([
        AXIOS_INSTANCE.get('/api/v1/platform-admin/adoption/grants'),
        AXIOS_INSTANCE.get('/api/v1/platform-admin/tenants'),
      ]);
      setGrants(grantsRes.data.grants);
      setTenants(tenantsRes.data.tenants);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching data:', err);
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGrant = async () => {
    if (!sourceCustomerId || !targetCustomerId) {
      return;
    }
    
    if (sourceCustomerId === targetCustomerId) {
      setError('Source and target tenant cannot be the same');
      return;
    }
    
    try {
      setSaving(true);
      await AXIOS_INSTANCE.post('/api/v1/platform-admin/adoption/grants', {
        source_customer_id: sourceCustomerId,
        target_customer_id: targetCustomerId,
        share_level: 'read',  // Always read-only; refresh is managed by source tenant
      });
      
      setShowModal(false);
      setSourceCustomerId('');
      setTargetCustomerId('');
      await fetchData();
    } catch (err: any) {
      console.error('Error creating grant:', err);
      setError(err.response?.data?.detail || 'Failed to create grant');
    } finally {
      setSaving(false);
    }
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setSourceCustomerId('');
    setTargetCustomerId('');
  };

  const handleToggleEnabled = async (grant: AdoptionGrant) => {
    try {
      await AXIOS_INSTANCE.patch(`/api/v1/platform-admin/adoption/grants/${grant.id}`, null, {
        params: { is_enabled: !grant.is_enabled }
      });
      await fetchData();
    } catch (err: any) {
      console.error('Error updating grant:', err);
      setError(err.response?.data?.detail || 'Failed to update grant');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      setDeleting(true);
      await AXIOS_INSTANCE.delete(`/api/v1/platform-admin/adoption/grants/${id}`);
      setDeleteConfirm(null);
      await fetchData();
    } catch (err: any) {
      console.error('Error deleting grant:', err);
      setError(err.response?.data?.detail || 'Failed to delete grant');
    } finally {
      setDeleting(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Adoption Access"
          description="Grant tenants access to view other tenants' adoption metrics"
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
    <>
      <Page maxWidth="xl">
        <PageHeader
          title="Adoption Access"
          description="Grant tenants access to view other tenants' adoption metrics"
          actions={
            <Button onClick={() => setShowModal(true)}>
              <PlusIcon className="w-4 h-4 mr-2" />
              Add Grant
            </Button>
          }
        />
        <PageBody>
          {/* Error Alert */}
          {error && (
            <Alert variant="error" className="mb-6">
              <div className="flex items-center justify-between w-full">
                <span>{error}</span>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => setError(null)}
                  className="ml-4 -mr-2"
                >
                  <XMarkIcon className="h-4 w-4" />
                </Button>
              </div>
            </Alert>
          )}

          {/* Grants Table */}
          <Panel>
            <PanelHeader>
              <PanelTitle>Active Grants</PanelTitle>
              <PanelDescription>
                {grants.length} grant{grants.length !== 1 ? 's' : ''} configured
              </PanelDescription>
            </PanelHeader>
            
            {grants.length === 0 ? (
              /* Empty State */
              <div className="p-12 text-center">
                <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 dark:bg-dark-surface-2 rounded-full flex items-center justify-center">
                  <BuildingOffice2Icon className="h-8 w-8 text-gray-400 dark:text-gray-500" />
                </div>
                <h3 className="text-sm font-medium text-charcoal dark:text-gray-100">
                  No grants configured
                </h3>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                  Get started by creating your first access grant.
                </p>
                <Button className="mt-4" onClick={() => setShowModal(true)}>
                  <PlusIcon className="h-4 w-4 mr-2" />
                  Create Grant
                </Button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50 dark:bg-dark-surface-2">
                      <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Source (Data Owner)
                      </th>
                      <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        →
                      </th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Target (Viewer)
                      </th>
                      <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Level
                      </th>
                      <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Active
                      </th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Created
                      </th>
                      <th className="text-right px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-dark-border">
                    {grants.map((grant) => (
                      <tr key={grant.id} className="hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-gray-100 dark:bg-dark-surface-2 rounded-lg flex items-center justify-center">
                              <BuildingOffice2Icon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                            </div>
                            <div>
                              <div className="font-medium text-charcoal dark:text-gray-100">
                                {grant.source_customer_name || grant.source_customer_id}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">{grant.source_customer_id}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <ArrowRightIcon className="h-4 w-4 text-gray-400 dark:text-gray-500 inline" />
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-gray-100 dark:bg-dark-surface-2 rounded-lg flex items-center justify-center">
                              <BuildingOffice2Icon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                            </div>
                            <div>
                              <div className="font-medium text-charcoal dark:text-gray-100">
                                {grant.target_customer_name || grant.target_customer_id}
                              </div>
                              <div className="text-xs text-gray-500 dark:text-gray-400">{grant.target_customer_id}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <Badge variant="info">Read Only</Badge>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-center gap-2">
                            <Switch
                              checked={grant.is_enabled}
                              onCheckedChange={() => handleToggleEnabled(grant)}
                            />
                            <Badge variant={grant.is_enabled ? 'success' : 'default'}>
                              {grant.is_enabled ? 'Yes' : 'No'}
                            </Badge>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm text-charcoal dark:text-gray-100">
                            {new Date(grant.created_at).toLocaleDateString()}
                          </div>
                          {grant.created_by_name && (
                            <div className="text-xs text-gray-500 dark:text-gray-400">by {grant.created_by_name}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right">
                          {deleteConfirm === grant.id ? (
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => handleDelete(grant.id)}
                                disabled={deleting}
                              >
                                {deleting ? 'Deleting...' : 'Confirm'}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setDeleteConfirm(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteConfirm(grant.id)}
                              className="text-gray-500 hover:text-red-500"
                            >
                              <TrashIcon className="h-4 w-4" />
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Help Text Panel */}
          <Panel className="mt-6 bg-gray-50 dark:bg-dark-surface-2">
            <PanelBody>
              <h4 className="font-medium text-charcoal dark:text-gray-100 mb-2">
                How Adoption Grants Work
              </h4>
              <ul className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
                <li>• <span className="font-medium text-eliza-red">Source Tenant</span> is the company whose adoption data will be shared</li>
                <li>• <span className="font-medium text-eliza-red">Target Tenant</span> is the company that will be able to view the data</li>
                <li>• All grants are <strong className="text-charcoal dark:text-gray-100">Read Only</strong> - target tenants can view but not modify data</li>
                <li>• Data refresh is handled by the source tenant, platform admins, or automated sync</li>
                <li>• The <strong className="text-charcoal dark:text-gray-100">Active</strong> toggle enables or disables the grant without deleting it</li>
              </ul>
            </PanelBody>
          </Panel>
        </PageBody>
      </Page>

      {/* Add Grant Modal */}
      <Modal open={showModal} onClose={handleCloseModal}>
        <ModalBackdrop />
        <ModalContent size="lg">
          <ModalHeader>
            <ModalTitle>New Access Grant</ModalTitle>
          </ModalHeader>
          <ModalBody>
            <div className="space-y-6">
              {/* Source and Target Tenant Selection */}
              <div className="flex flex-col md:flex-row gap-4 items-start">
                {/* Source Tenant */}
                <div className="flex-1 w-full">
                  <Label className="block mb-1.5">Source Tenant (Data Owner)</Label>
                  <Select
                    value={sourceCustomerId}
                    onValueChange={setSourceCustomerId}
                    placeholder="Select tenant..."
                  >
                    {tenants.filter(t => t.is_active).map((tenant) => (
                      <SelectOption key={tenant.customer_id} value={tenant.customer_id}>
                        {tenant.display_name || tenant.name} ({tenant.customer_id})
                      </SelectOption>
                    ))}
                  </Select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Whose adoption data will be shared</p>
                </div>

                {/* Arrow - aligned with select boxes */}
                <div className="hidden md:flex items-center justify-center pt-7">
                  <ArrowRightIcon className="h-5 w-5 text-gray-400 dark:text-gray-500" />
                </div>

                {/* Target Tenant */}
                <div className="flex-1 w-full">
                  <Label className="block mb-1.5">Target Tenant (Viewer)</Label>
                  <Select
                    value={targetCustomerId}
                    onValueChange={setTargetCustomerId}
                    placeholder="Select tenant..."
                  >
                    {tenants.filter(t => t.is_active && t.customer_id !== sourceCustomerId).map((tenant) => (
                      <SelectOption key={tenant.customer_id} value={tenant.customer_id}>
                        {tenant.display_name || tenant.name} ({tenant.customer_id})
                      </SelectOption>
                    ))}
                  </Select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Who gets to view the data</p>
                </div>
              </div>

              {/* Access Level Info */}
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-sm text-charcoal dark:text-gray-100">
                  <span className="font-medium">Access Level:</span> Read Only
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Target tenant can view adoption metrics. Data refresh is managed by the source tenant or platform admins.
                </p>
              </div>
            </div>
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" onClick={handleCloseModal}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateGrant}
              disabled={!sourceCustomerId || !targetCustomerId || saving}
            >
              {saving ? 'Creating...' : 'Create Grant'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
}

export default AdoptionAccessPage;

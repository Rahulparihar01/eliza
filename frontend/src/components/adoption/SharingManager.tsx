/**
 * Sharing Manager Component for Adoption Dashboard
 * 
 * Allows users to manage who they share their adoption data with.
 * Migrated to Eliza Forge Design System.
 */

import React, { useState } from 'react';
import {
  ShareIcon,
  TrashIcon,
  PlusIcon,
  XMarkIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import {
  AdoptionShare,
  useAdoptionShares,
  useCreateAdoptionShare,
  useUpdateAdoptionShare,
  useDeleteAdoptionShare,
} from '../../hooks/useAdoption';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Switch } from '../ui/switch';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';

interface SharingManagerProps {
  onClose?: () => void;
}

export function SharingManager({ onClose }: SharingManagerProps) {
  const { data: shares, isLoading } = useAdoptionShares();
  const createShare = useCreateAdoptionShare();
  const updateShare = useUpdateAdoptionShare();
  const deleteShare = useDeleteAdoptionShare();

  const [showAddForm, setShowAddForm] = useState(false);
  const [newTargetCompany, setNewTargetCompany] = useState('');
  const [newPermissionLevel, setNewPermissionLevel] = useState<'read' | 'admin'>('read');
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const handleCreateShare = async () => {
    if (!newTargetCompany.trim()) return;

    try {
      await createShare.mutateAsync({
        target_company_id: newTargetCompany.trim(),
        permission_level: newPermissionLevel,
      });
      setShowAddForm(false);
      setNewTargetCompany('');
      setNewPermissionLevel('read');
    } catch (error) {
      console.error('Failed to create share:', error);
    }
  };

  const handleToggleActive = async (share: AdoptionShare) => {
    try {
      await updateShare.mutateAsync({
        id: share.id,
        is_active: !share.is_active,
      });
    } catch (error) {
      console.error('Failed to update share:', error);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteShare.mutateAsync(id);
      setDeleteConfirm(null);
    } catch (error) {
      console.error('Failed to delete share:', error);
    }
  };

  return (
    <div className="bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-dark-border overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-eliza-red/10 rounded-lg">
            <ShareIcon className="h-5 w-5 text-eliza-red" />
          </div>
          <div>
            <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">Data Sharing</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Control who can view your adoption metrics
            </p>
          </div>
        </div>
        {onClose && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
          >
            <XMarkIcon className="h-5 w-5" />
          </Button>
        )}
      </div>

      {/* Content */}
      <div className="p-6">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2].map((i) => (
              <Skeleton key={i} variant="rounded" height={64} />
            ))}
          </div>
        ) : shares && shares.length > 0 ? (
          <div className="space-y-3">
            {shares.map((share) => (
              <div
                key={share.id}
                className={`flex items-center justify-between p-4 rounded-lg border transition-colors ${
                  share.is_active
                    ? 'bg-gray-50 dark:bg-dark-surface-2 border-gray-200 dark:border-dark-border'
                    : 'bg-white dark:bg-dark-surface border-gray-200/50 dark:border-dark-border/50 opacity-60'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-charcoal dark:text-gray-100">
                      {share.target_company_id}
                    </span>
                    <Badge variant={share.permission_level === 'admin' ? 'warning' : 'info'}>
                      {share.permission_level}
                    </Badge>
                    {!share.is_active && (
                      <Badge variant="default">Inactive</Badge>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Shared on {new Date(share.created_at).toLocaleDateString()}
                    {share.expires_at && (
                      <> · Expires {new Date(share.expires_at).toLocaleDateString()}</>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Toggle Active */}
                  <Switch
                    checked={share.is_active}
                    onCheckedChange={() => handleToggleActive(share)}
                    disabled={updateShare.isPending}
                  />

                  {/* Delete */}
                  {deleteConfirm === share.id ? (
                    <div className="flex items-center gap-1">
                      <Button
                        onClick={() => handleDelete(share.id)}
                        variant="destructive"
                        size="sm"
                        disabled={deleteShare.isPending}
                      >
                        Confirm
                      </Button>
                      <Button
                        onClick={() => setDeleteConfirm(null)}
                        variant="ghost"
                        size="sm"
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      onClick={() => setDeleteConfirm(share.id)}
                      variant="ghost"
                      size="icon-sm"
                      className="text-gray-400 hover:text-red-500 hover:bg-red-500/10"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 dark:bg-dark-surface-2 rounded-full flex items-center justify-center">
              <ShareIcon className="h-8 w-8 text-gray-400 dark:text-gray-500" />
            </div>
            <p className="text-gray-500 dark:text-gray-400 mb-4">
              You haven't shared your adoption data with anyone yet
            </p>
          </div>
        )}

        {/* Add Share Form */}
        {showAddForm ? (
          <div className="mt-4 p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-lg border border-gray-200 dark:border-dark-border">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  Company ID
                </label>
                <Input
                  type="text"
                  value={newTargetCompany}
                  onChange={(e) => setNewTargetCompany(e.target.value)}
                  placeholder="Enter company ID to share with..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  Permission Level
                </label>
                <div className="flex gap-3">
                  <button
                    onClick={() => setNewPermissionLevel('read')}
                    className={`flex-1 px-4 py-2.5 rounded-lg border transition-colors ${
                      newPermissionLevel === 'read'
                        ? 'bg-blue-500/10 border-blue-500 text-blue-600 dark:text-blue-400'
                        : 'bg-white dark:bg-dark-surface border-gray-200 dark:border-dark-border text-gray-500 dark:text-gray-400 hover:border-blue-500/50'
                    }`}
                  >
                    Read Only
                  </button>
                  <button
                    onClick={() => setNewPermissionLevel('admin')}
                    className={`flex-1 px-4 py-2.5 rounded-lg border transition-colors ${
                      newPermissionLevel === 'admin'
                        ? 'bg-amber-500/10 border-amber-500 text-amber-600 dark:text-amber-400'
                        : 'bg-white dark:bg-dark-surface border-gray-200 dark:border-dark-border text-gray-500 dark:text-gray-400 hover:border-amber-500/50'
                    }`}
                  >
                    Admin
                  </button>
                </div>
              </div>

              <div className="flex gap-3">
                <Button
                  onClick={handleCreateShare}
                  disabled={!newTargetCompany.trim() || createShare.isPending}
                  variant="brand"
                  className="flex-1"
                >
                  {createShare.isPending ? 'Creating...' : 'Create Share'}
                </Button>
                <Button
                  onClick={() => {
                    setShowAddForm(false);
                    setNewTargetCompany('');
                    setNewPermissionLevel('read');
                  }}
                  variant="secondary"
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowAddForm(true)}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 border border-dashed border-gray-300 dark:border-dark-border rounded-lg text-gray-500 dark:text-gray-400 hover:border-eliza-red hover:text-eliza-red transition-colors"
          >
            <PlusIcon className="h-5 w-5" />
            <span>Share with another company</span>
          </button>
        )}
      </div>
    </div>
  );
}

export default SharingManager;


/**
 * Admin Management Page
 * 
 * Platform admin page for managing platform administrators.
 * Fully migrated to DS components (Jan 2026).
 * 
 * DS Components used:
 * - Page, PageHeader, PageBody (layout)
 * - DataTable, DataTableActions, DataTableActionButton (data display)
 * - Button, Input, Badge, Avatar, Spinner (form/display)
 * - Modal, ModalBackdrop, ModalContent, ModalHeader, ModalTitle, ModalBody, ModalFooter (dialogs)
 */

import React, { useState, useEffect } from 'react';
import {
  UsersIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';
import {
  Button,
  Input,
  Badge,
  Spinner,
  Avatar,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  DataTable,
  DataTableActions,
  DataTableActionButton,
  Page,
  PageHeader,
  PageBody,
} from '../../components/ui';
import type { Column } from '../../components/ui';

interface PlatformAdmin {
  id: number;
  user_id: number;
  user_email: string | null;
  user_name: string | null;
  admin_level: string;
  can_create_tenants: boolean;
  can_allocate_features: boolean;
  can_manage_platform_admins: boolean;
  can_impersonate: boolean;
  is_active: boolean;
  created_at: string;
}

interface AllUser {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  customer_id: string | null;
  is_active: boolean;
}

export function AdminManagementPage() {
  const { push: addToast } = useToasts();
  
  // Platform Admins state
  const [admins, setAdmins] = useState<PlatformAdmin[]>([]);
  const [allUsers, setAllUsers] = useState<AllUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [saving, setSaving] = useState(false);

  // Fetch platform admins
  const fetchAdmins = async () => {
    try {
      setLoading(true);
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/admins');
      setAdmins(response.data.admins || []);
    } catch (err: any) {
      console.error('Error fetching platform admins:', err);
      addToast({
        kind: 'error',
        message: err.response?.data?.detail || 'Failed to load platform admins',
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchAllUsers = async () => {
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/users');
      setAllUsers(response.data.users || []);
    } catch (err: any) {
      console.error('Error fetching users:', err);
    }
  };

  useEffect(() => {
    fetchAdmins();
  }, []);

  const handleOpenAddModal = () => {
    fetchAllUsers();
    setShowAddModal(true);
    setSelectedUserId(null);
    setUserSearchQuery('');
  };

  const handleAddAdmin = async () => {
    if (!selectedUserId) return;
    
    setSaving(true);
    try {
      await AXIOS_INSTANCE.post('/api/v1/platform-admin/admins', {
        user_id: selectedUserId,
        admin_level: 'admin',
        can_create_tenants: true,
        can_allocate_features: true,
        can_manage_platform_admins: false,
        can_impersonate: false,
      });
      setShowAddModal(false);
      fetchAdmins();
      addToast({
        kind: 'success',
        message: 'Platform admin added successfully',
      });
    } catch (err: any) {
      console.error('Error adding platform admin:', err);
      addToast({
        kind: 'error',
        message: err.response?.data?.detail || 'Failed to add platform admin',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveAdmin = async (admin: PlatformAdmin) => {
    if (!window.confirm('Are you sure you want to remove this user as a platform admin?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/platform-admin/admins/${admin.user_id}`);
      fetchAdmins();
      addToast({
        kind: 'success',
        message: 'Platform admin removed successfully',
      });
    } catch (err: any) {
      console.error('Error removing platform admin:', err);
      addToast({
        kind: 'error',
        message: err.response?.data?.detail || 'Failed to remove platform admin',
      });
    }
  };

  const filteredAdmins = admins.filter(admin =>
    (admin.user_email?.toLowerCase().includes(searchQuery.toLowerCase())) ||
    (admin.user_name?.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const adminUserIds = new Set(admins.map(a => a.user_id));
  const availableUsers = allUsers.filter(user => 
    !adminUserIds.has(user.id) &&
    (user.email.toLowerCase().includes(userSearchQuery.toLowerCase()) ||
     user.full_name?.toLowerCase().includes(userSearchQuery.toLowerCase()))
  );

  // DataTable columns
  const columns: Column<PlatformAdmin>[] = [
    {
      id: 'user_name',
      header: 'Name',
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Avatar 
            fallback={row.user_name?.charAt(0).toUpperCase() || '?'} 
            size="sm"
          />
          <div>
            <div className="font-medium text-charcoal dark:text-gray-100 text-sm">
              {row.user_name || 'Unknown'}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {row.user_email}
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'admin_level',
      header: 'Level',
      cell: ({ row }) => (
        <Badge variant="brand" className="capitalize">
          {row.admin_level.replace('_', ' ')}
        </Badge>
      ),
    },
    {
      id: 'is_active',
      header: 'Status',
      cell: ({ row }) => (
        row.is_active ? (
          <Badge variant="success" className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-500 rounded-full" />
            Active
          </Badge>
        ) : (
          <Badge variant="danger" className="inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-red-500 rounded-full" />
            Inactive
          </Badge>
        )
      ),
    },
    {
      id: 'created_at',
      header: 'Added',
      cell: ({ row }) => (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      cell: ({ row }) => (
        <DataTableActions>
          <DataTableActionButton
            icon={<TrashIcon className="w-4 h-4" />}
            label="Remove admin"
            onClick={() => handleRemoveAdmin(row)}
            variant="danger"
          />
        </DataTableActions>
      ),
    },
  ];

  const headerActions = (
    <Button onClick={handleOpenAddModal}>
      <PlusIcon className="w-4 h-4 mr-2" />
      Add Admin
    </Button>
  );

  if (loading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Admin Management"
          description="Manage platform administrators"
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
        title="Admin Management"
        description="Manage platform administrators"
        actions={headerActions}
      />
      <PageBody>
        {/* Search */}
        <div className="mb-4">
          <div className="relative w-72">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              type="text"
              placeholder="Search admins..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Data Table */}
        <DataTable
          columns={columns}
          data={filteredAdmins}
          loading={loading}
          emptyMessage={searchQuery ? 'No admins match your search' : 'No platform admins yet'}
          emptyIcon={<UsersIcon className="w-12 h-12" />}
        />
      </PageBody>

      {/* Add Admin Modal */}
      <Modal open={showAddModal} onClose={() => setShowAddModal(false)}>
        <ModalBackdrop />
        <ModalContent className="max-w-lg">
          <ModalHeader>
            <ModalTitle>Add Platform Admin</ModalTitle>
          </ModalHeader>
          <ModalBody>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Select a user to grant platform administrator access.
            </p>

            {/* Search Input */}
            <div className="relative mb-4">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search users..."
                value={userSearchQuery}
                onChange={(e) => setUserSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* User List */}
            <div className="max-h-64 overflow-y-auto border border-gray-200 dark:border-dark-border rounded-lg">
              {availableUsers.length === 0 ? (
                <div className="px-4 py-8 text-center text-gray-500 dark:text-gray-400 text-sm">
                  {userSearchQuery ? 'No users match your search' : 'No users available'}
                </div>
              ) : (
                availableUsers.map((user) => (
                  <button
                    key={user.id}
                    onClick={() => setSelectedUserId(user.id)}
                    className={`
                      w-full px-4 py-3 flex items-center gap-3 text-left transition-colors
                      ${selectedUserId === user.id
                        ? 'bg-eliza-red/10 border-l-2 border-eliza-red'
                        : 'hover:bg-gray-50 dark:hover:bg-dark-surface-2 border-l-2 border-transparent'
                      }
                    `}
                  >
                    <Avatar 
                      fallback={(user.full_name?.charAt(0) || user.username.charAt(0)).toUpperCase()} 
                      size="sm"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-charcoal dark:text-gray-100 text-sm truncate">
                        {user.full_name || user.username}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {user.email}
                      </div>
                    </div>
                    {user.customer_id && (
                      <Badge variant="secondary" className="text-xs">
                        {user.customer_id}
                      </Badge>
                    )}
                  </button>
                ))
              )}
            </div>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddAdmin}
              disabled={!selectedUserId || saving}
            >
              {saving && <Spinner size="sm" className="mr-2" />}
              {saving ? 'Adding...' : 'Add as Admin'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Page>
  );
}

export default AdminManagementPage;

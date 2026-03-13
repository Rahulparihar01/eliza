/**
 * Users & Roles Page
 * 
 * Consolidated tenant admin page for managing users, roles, and invitations.
 * All actions are handled via modals (no sub-page navigation).
 * Users and pending invites are shown in a single table with status filtering.
 * 
 * Permission-gated:
 * - Users tab: requires users:read or invitations:read
 * - Roles tab: requires roles:read
 * - Invite User button: requires users:invite (or invitations:create/invites:create)
 * - Create Role button: requires roles:create
 * - Edit User Roles: requires roles:assign
 * - Delete Role: requires roles:delete
 * - Resend Invite: requires invitations:resend or invites:resend
 * - Revoke Invite: requires invitations:revoke or invites:revoke
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  UsersIcon,
  ShieldCheckIcon,
  PlusIcon,
  MagnifyingGlassIcon,
  TrashIcon,
  UserCircleIcon,
  UserPlusIcon,
  ClockIcon,
  ClipboardDocumentIcon,
  ArrowPathIcon,
  CheckIcon,
  LockClosedIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';
import { usePermissions } from '../../contexts/AuthContext';
import {
  Button,
  Input,
  Badge,
  Alert,
  Spinner,
  Tabs,
  TabsList,
  TabsTrigger,
  Page,
  PageHeader,
  PageBody,
} from '../../components/ui';
import {
  EditUserRolesModal,
  InviteUserModal,
  RoleEditorModal,
} from '../../components/users-roles';

interface TenantRole {
  id: number;
  customer_id: string;
  role_name: string;
  display_name: string | null;
  description: string | null;
  is_system_role: boolean;
  is_active: boolean;
  permission_count: number;
  user_count: number;
  created_at: string;
}

interface TenantUser {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  customer_id: string;
  is_active: boolean;
  department: string | null;
  team: string | null;
  last_login: string | null;
  created_at: string;
  roles: { role_id: number; role_name: string; display_name: string | null }[];
}

interface UserInvite {
  id: number;
  email: string;
  full_name: string | null;
  invite_url: string;
  role_ids: number[] | null;
  status: string;
  expires_at: string;
}

// Combined type for unified table
type UserOrInvite = 
  | { type: 'user'; data: TenantUser }
  | { type: 'invite'; data: UserInvite };

type Tab = 'users' | 'roles';
type StatusFilter = 'all' | 'active' | 'pending' | 'expired';

export function UsersRolesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { push: addToast } = useToasts();
  const { hasPermission, hasAnyPermission } = usePermissions();
  
  // Permission checks
  const canViewUsers = hasAnyPermission(['users:read', 'platform:admin']);
  const canViewInvitations = hasAnyPermission(['invitations:read', 'invites:read', 'platform:admin']);
  const canViewRoles = hasAnyPermission(['roles:read', 'platform:admin']);
  // users:invite is the primary permission, invitations:create and invites:create are alternatives
  const canCreateInvitation = hasAnyPermission(['users:invite', 'invitations:create', 'invites:create', 'platform:admin']);
  const canResendInvitation = hasAnyPermission(['invitations:resend', 'invites:resend', 'platform:admin']);
  const canRevokeInvitation = hasAnyPermission(['invitations:revoke', 'invites:revoke', 'platform:admin']);
  const canCreateRole = hasAnyPermission(['roles:create', 'platform:admin']);
  const canUpdateRole = hasAnyPermission(['roles:update', 'platform:admin']);
  const canDeleteRole = hasAnyPermission(['roles:delete', 'platform:admin']);
  const canAssignRoles = hasAnyPermission(['roles:assign', 'platform:admin']);
  
  // Determine which tabs are available
  const canViewUsersTab = canViewUsers || canViewInvitations;
  const canViewRolesTab = canViewRoles;
  
  // Determine initial tab based on permissions
  const getInitialTab = (): Tab => {
    const requestedTab = searchParams.get('tab') as Tab;
    
    if (requestedTab === 'roles' && canViewRolesTab) {
      return 'roles';
    }
    if (requestedTab === 'users' && canViewUsersTab) {
      return 'users';
    }
    
    // Default to first available tab
    if (canViewUsersTab) return 'users';
    if (canViewRolesTab) return 'roles';
    return 'users'; // Fallback (shouldn't happen due to route protection)
  };
  
  const [activeTab, setActiveTab] = useState<Tab>(getInitialTab());
  
  // Data state
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [roles, setRoles] = useState<TenantRole[]>([]);
  const [invites, setInvites] = useState<UserInvite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  
  // Modal states
  const [showEditUserRolesModal, setShowEditUserRolesModal] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  
  // Selected items for editing
  const [selectedUser, setSelectedUser] = useState<TenantUser | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null);
  const [userRoleIds, setUserRoleIds] = useState<number[]>([]);
  const [savingUserRoles, setSavingUserRoles] = useState(false);
  
  // Copy state for invites
  const [copiedInviteId, setCopiedInviteId] = useState<number | null>(null);

  const handleTabChange = (value: string) => {
    const tab = value as Tab;
    
    // Check if user has permission for the requested tab
    if (tab === 'roles' && !canViewRolesTab) {
      addToast({ kind: 'error', message: 'You do not have permission to view roles' });
      return;
    }
    if (tab === 'users' && !canViewUsersTab) {
      addToast({ kind: 'error', message: 'You do not have permission to view users' });
      return;
    }
    
    setActiveTab(tab);
    setSearchParams({ tab });
    setSearchQuery('');
  };

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Only fetch data the user has permission to see
      const promises: Promise<any>[] = [];
      
      if (canViewUsers) {
        promises.push(AXIOS_INSTANCE.get('/api/v1/admin/users'));
      } else {
        promises.push(Promise.resolve({ data: { users: [] } }));
      }
      
      // Always fetch roles (needed for invite modal and user roles display)
      promises.push(AXIOS_INSTANCE.get('/api/v1/admin/roles?scoped_to_allocated_features=true'));
      
      if (canViewInvitations) {
        promises.push(AXIOS_INSTANCE.get('/api/v1/admin/invites'));
      } else {
        promises.push(Promise.resolve({ data: { invites: [] } }));
      }
      
      const [usersRes, rolesRes, invitesRes] = await Promise.all(promises);
      
      setUsers(usersRes.data.users || []);
      setRoles(rolesRes.data || []);
      setInvites(invitesRes.data.invites || []);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching data:', err);
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  // User role editing
  const handleEditUserRoles = (user: TenantUser) => {
    if (!canAssignRoles) {
      addToast({ kind: 'error', message: 'You do not have permission to assign roles' });
      return;
    }
    setSelectedUser(user);
    setUserRoleIds(user.roles.map(r => r.role_id));
    setShowEditUserRolesModal(true);
  };

  const handleToggleUserRole = (roleId: number) => {
    setUserRoleIds(prev =>
      prev.includes(roleId)
        ? prev.filter(id => id !== roleId)
        : [...prev, roleId]
    );
  };

  const handleSaveUserRoles = async () => {
    if (!selectedUser) return;
    setSavingUserRoles(true);
    
    try {
      await AXIOS_INSTANCE.post(`/api/v1/admin/users/${selectedUser.id}/roles`, {
        role_ids: userRoleIds,
      });
      setShowEditUserRolesModal(false);
      addToast({ kind: 'success', message: 'User roles updated successfully' });
      fetchData();
    } catch (err: any) {
      console.error('Error saving user roles:', err);
      setError(err.response?.data?.detail || 'Failed to update user roles');
    } finally {
      setSavingUserRoles(false);
    }
  };

  // Role management
  const handleCreateRole = () => {
    if (!canCreateRole) {
      addToast({ kind: 'error', message: 'You do not have permission to create roles' });
      return;
    }
    setSelectedRoleId(null);
    setShowRoleModal(true);
  };

  const handleEditRole = (roleId: number) => {
    if (!canUpdateRole) {
      addToast({ kind: 'error', message: 'You do not have permission to edit roles' });
      return;
    }
    setSelectedRoleId(roleId);
    setShowRoleModal(true);
  };

  const handleDeleteRole = async (roleId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (!canDeleteRole) {
      addToast({ kind: 'error', message: 'You do not have permission to delete roles' });
      return;
    }
    
    if (!window.confirm('Are you sure you want to delete this role?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/admin/roles/${roleId}`);
      addToast({ kind: 'success', message: 'Role deleted successfully' });
      fetchData();
    } catch (err: any) {
      console.error('Error deleting role:', err);
      setError(err.response?.data?.detail || 'Failed to delete role');
    }
  };

  // Invite management
  const handleCreateInvite = async (data: { email: string; full_name: string; role_ids: number[] }) => {
    const response = await AXIOS_INSTANCE.post('/api/v1/admin/invites', data);
    return response.data.invite_url;
  };

  const handleInviteSuccess = (email: string, inviteUrl: string) => {
    addToast({ kind: 'success', message: `Invite sent to ${email}` });
    navigator.clipboard.writeText(inviteUrl);
    fetchData();
  };

  const handleCopyInviteUrl = (invite: UserInvite) => {
    navigator.clipboard.writeText(invite.invite_url);
    setCopiedInviteId(invite.id);
    addToast({ kind: 'success', message: 'Invite link copied to clipboard' });
    setTimeout(() => setCopiedInviteId(null), 2000);
  };

  const handleResendInvite = async (inviteId: number) => {
    if (!canResendInvitation) {
      addToast({ kind: 'error', message: 'You do not have permission to resend invitations' });
      return;
    }
    
    try {
      await AXIOS_INSTANCE.post(`/api/v1/admin/invites/${inviteId}/resend`);
      addToast({ kind: 'success', message: 'Invite resent successfully' });
      fetchData();
    } catch (err: any) {
      console.error('Error resending invite:', err);
      setError(err.response?.data?.detail || 'Failed to resend invite');
    }
  };

  const handleRevokeInvite = async (inviteId: number) => {
    if (!canRevokeInvitation) {
      addToast({ kind: 'error', message: 'You do not have permission to revoke invitations' });
      return;
    }
    
    if (!window.confirm('Are you sure you want to revoke this invite?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/admin/invites/${inviteId}`);
      addToast({ kind: 'success', message: 'Invite revoked' });
      fetchData();
    } catch (err: any) {
      console.error('Error revoking invite:', err);
      setError(err.response?.data?.detail || 'Failed to revoke invite');
    }
  };

  // Get role names for invite
  const getRoleNamesForInvite = (invite: UserInvite): string[] => {
    if (!invite.role_ids) return [];
    return invite.role_ids
      .map(id => {
        const role = roles.find(r => r.id === id);
        return role?.display_name || role?.role_name || '';
      })
      .filter(Boolean);
  };

  // Combined and filtered list
  const combinedList = useMemo((): UserOrInvite[] => {
    const userItems: UserOrInvite[] = canViewUsers 
      ? users.map(u => ({ type: 'user' as const, data: u }))
      : [];
    const inviteItems: UserOrInvite[] = canViewInvitations
      ? invites.map(i => ({ type: 'invite' as const, data: i }))
      : [];
    return [...userItems, ...inviteItems];
  }, [users, invites, canViewUsers, canViewInvitations]);

  const filteredList = useMemo(() => {
    return combinedList.filter(item => {
      // Search filter
      const searchLower = searchQuery.toLowerCase();
      let matchesSearch = true;
      if (searchQuery) {
        if (item.type === 'user') {
          matchesSearch = 
            item.data.email.toLowerCase().includes(searchLower) ||
            (item.data.full_name?.toLowerCase().includes(searchLower) ?? false);
        } else {
          matchesSearch = 
            item.data.email.toLowerCase().includes(searchLower) ||
            (item.data.full_name?.toLowerCase().includes(searchLower) ?? false);
        }
      }

      // Status filter
      let matchesStatus = true;
      if (statusFilter !== 'all') {
        if (item.type === 'user') {
          matchesStatus = statusFilter === 'active' && item.data.is_active;
        } else {
          matchesStatus = item.data.status === statusFilter;
        }
      }

      return matchesSearch && matchesStatus;
    });
  }, [combinedList, searchQuery, statusFilter]);

  const filteredRoles = roles.filter(role =>
    role.role_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (role.display_name?.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Computed counts
  const pendingInvites = invites.filter(i => i.status === 'pending');
  const expiredInvites = invites.filter(i => i.status === 'expired');
  const activeUsers = users.filter(u => u.is_active);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
    });
  };

  // Header actions - conditional based on active tab
  // Must be defined before any early returns to maintain hook order
  const headerActions = useMemo(() => {
    if (activeTab === 'users' && canCreateInvitation) {
      return (
        <Button onClick={() => setShowInviteModal(true)}>
          <UserPlusIcon className="w-4 h-4 mr-2" />
          Invite User
        </Button>
      );
    }
    if (activeTab === 'roles' && canCreateRole) {
      return (
        <Button onClick={handleCreateRole}>
          <PlusIcon className="w-4 h-4 mr-2" />
          Create Role
        </Button>
      );
    }
    return null;
  }, [activeTab, canCreateInvitation, canCreateRole]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 dark:bg-dark-bg">
        <Spinner size="lg" />
      </div>
    );
  }

  // No access to any tab
  if (!canViewUsersTab && !canViewRolesTab) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Users & Roles"
          description="Manage user accounts, roles, and permissions for your organization"
        />
        <PageBody>
          <Alert variant="warning">
            <div className="flex items-center gap-2">
              <LockClosedIcon className="w-5 h-5" />
              You do not have permission to access this page.
            </div>
          </Alert>
        </PageBody>
      </Page>
    );
  }

  return (
    <Page maxWidth="xl">
      {/* Page Header */}
      <PageHeader
        title="Users & Roles"
        description="Manage user accounts, roles, and permissions for your organization"
        actions={headerActions}
      />

      <PageBody>
        {/* Tabs - only show tabs the user has access to */}
        <Tabs defaultValue={getInitialTab()} value={activeTab} onValueChange={handleTabChange}>
          <TabsList className="mb-4">
            {canViewUsersTab && (
              <TabsTrigger value="users">
                <UsersIcon className="w-4 h-4" />
                Users
              </TabsTrigger>
            )}
            {canViewRolesTab && (
              <TabsTrigger value="roles">
                <ShieldCheckIcon className="w-4 h-4" />
                Roles
              </TabsTrigger>
            )}
          </TabsList>
        </Tabs>

        {error && (
          <Alert variant="warning" onDismiss={() => setError(null)} className="mb-4">
            {error}
          </Alert>
        )}

        {/* Users Tab */}
        {activeTab === 'users' && canViewUsersTab && (
          <>
            {/* Stats Cards - only show counts the user can see */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              {canViewUsers && (
                <button
                  onClick={() => setStatusFilter(statusFilter === 'active' ? 'all' : 'active')}
                  className={`bg-white dark:bg-dark-surface rounded-lg border p-4 text-left transition-all ${
                    statusFilter === 'active' 
                      ? 'border-green-500 ring-1 ring-green-500' 
                      : 'border-gray-200 dark:border-dark-border hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                      <UsersIcon className="w-5 h-5 text-green-500" />
                    </div>
                    <div>
                      <div className="text-2xl font-semibold text-charcoal dark:text-gray-100">
                        {activeUsers.length}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        Active Users
                      </div>
                    </div>
                  </div>
                </button>
              )}
              {canViewInvitations && (
                <>
                  <button
                    onClick={() => setStatusFilter(statusFilter === 'pending' ? 'all' : 'pending')}
                    className={`bg-white dark:bg-dark-surface rounded-lg border p-4 text-left transition-all ${
                      statusFilter === 'pending' 
                        ? 'border-amber-500 ring-1 ring-amber-500' 
                        : 'border-gray-200 dark:border-dark-border hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center">
                        <ClockIcon className="w-5 h-5 text-amber-500" />
                      </div>
                      <div>
                        <div className="text-2xl font-semibold text-charcoal dark:text-gray-100">
                          {pendingInvites.length}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          Pending Invites
                        </div>
                      </div>
                    </div>
                  </button>
                  <button
                    onClick={() => setStatusFilter(statusFilter === 'expired' ? 'all' : 'expired')}
                    className={`bg-white dark:bg-dark-surface rounded-lg border p-4 text-left transition-all ${
                      statusFilter === 'expired' 
                        ? 'border-red-500 ring-1 ring-red-500' 
                        : 'border-gray-200 dark:border-dark-border hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-red-500/10 rounded-lg flex items-center justify-center">
                        <ClockIcon className="w-5 h-5 text-red-500" />
                      </div>
                      <div>
                        <div className="text-2xl font-semibold text-charcoal dark:text-gray-100">
                          {expiredInvites.length}
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          Expired Invites
                        </div>
                      </div>
                    </div>
                  </button>
                </>
              )}
            </div>

            {/* Users Table */}
            <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
              {/* Header */}
              <div className="px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-medium text-charcoal dark:text-gray-100">
                    {statusFilter === 'all' ? 'All Users & Invites' : 
                     statusFilter === 'active' ? 'Active Users' :
                     statusFilter === 'pending' ? 'Pending Invites' : 'Expired Invites'}
                  </h2>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {filteredList.length} {filteredList.length === 1 ? 'result' : 'results'}
                  </span>
                  {statusFilter !== 'all' && (
                    <Button variant="ghost" size="sm" onClick={() => setStatusFilter('all')}>
                      Clear filter
                    </Button>
                  )}
                </div>
                <div className="relative w-56">
                  <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 pointer-events-none z-10" />
                  <Input
                    type="text"
                    placeholder="Search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
              
              {/* Table */}
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 dark:bg-dark-surface-2/50">
                    <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Name</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Roles</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
                    <th className="text-right px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-dark-border/50">
                  {filteredList.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-12 text-center text-gray-500 dark:text-gray-400 text-sm">
                        {searchQuery ? 'No results match your search' : 'No users or invites yet'}
                      </td>
                    </tr>
                  ) : (
                    filteredList.map((item) => {
                      if (item.type === 'user') {
                        const user = item.data;
                        return (
                          <tr 
                            key={`user-${user.id}`} 
                            className="hover:bg-gray-50/50 dark:hover:bg-dark-surface-2/30 transition-colors"
                          >
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 bg-eliza-red/10 rounded-full flex items-center justify-center">
                                  <UserCircleIcon className="w-5 h-5 text-eliza-red" />
                                </div>
                                <div>
                                  <div className="text-sm font-medium text-charcoal dark:text-gray-100">
                                    {user.full_name || user.username}
                                  </div>
                                  <div className="text-xs text-gray-500 dark:text-gray-400">
                                    {user.email}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-1">
                                {user.roles.length === 0 ? (
                                  <span className="text-gray-500 dark:text-gray-400 text-xs">No roles</span>
                                ) : (
                                  user.roles.map((role) => (
                                    <Badge key={role.role_id} variant="brand">
                                      {role.display_name || role.role_name}
                                    </Badge>
                                  ))
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant={user.is_active ? 'success' : 'danger'}>
                                {user.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                              {user.last_login ? `Last login: ${formatDate(user.last_login)}` : 'Never logged in'}
                            </td>
                            <td className="px-4 py-3 text-right">
                              {canAssignRoles && (
                                <Button
                                  variant="link"
                                  size="sm"
                                  onClick={() => handleEditUserRoles(user)}
                                >
                                  Edit Roles
                                </Button>
                              )}
                            </td>
                          </tr>
                        );
                      } else {
                        const invite = item.data;
                        const roleNames = getRoleNamesForInvite(invite);
                        const isExpired = invite.status === 'expired';
                        
                        return (
                          <tr 
                            key={`invite-${invite.id}`} 
                            className={`transition-colors ${isExpired ? 'bg-red-50/30 dark:bg-red-900/5' : 'hover:bg-gray-50/50 dark:hover:bg-dark-surface-2/30'}`}
                          >
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${isExpired ? 'bg-red-500/10' : 'bg-amber-500/10'}`}>
                                  <ClockIcon className={`w-5 h-5 ${isExpired ? 'text-red-500' : 'text-amber-500'}`} />
                                </div>
                                <div>
                                  <div className="text-sm font-medium text-charcoal dark:text-gray-100">
                                    {invite.full_name || 'Pending User'}
                                  </div>
                                  <div className="text-xs text-gray-500 dark:text-gray-400">
                                    {invite.email}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap gap-1">
                                {roleNames.length === 0 ? (
                                  <span className="text-gray-500 dark:text-gray-400 text-xs">No roles</span>
                                ) : (
                                  roleNames.map((name) => (
                                    <Badge key={name} variant="brand">
                                      {name}
                                    </Badge>
                                  ))
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <Badge variant={isExpired ? 'danger' : 'warning'}>
                                {isExpired ? 'Expired' : 'Pending'}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                              Expires: {formatDate(invite.expires_at)}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handleCopyInviteUrl(invite)}
                                  title="Copy invite link"
                                >
                                  {copiedInviteId === invite.id ? (
                                    <CheckIcon className="w-4 h-4 text-green-500" />
                                  ) : (
                                    <ClipboardDocumentIcon className="w-4 h-4" />
                                  )}
                                </Button>
                                {!isExpired && canResendInvitation && (
                                  <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={() => handleResendInvite(invite.id)}
                                    title="Resend invite"
                                  >
                                    <ArrowPathIcon className="w-4 h-4" />
                                  </Button>
                                )}
                                {canRevokeInvitation && (
                                  <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={() => handleRevokeInvite(invite.id)}
                                    title="Revoke invite"
                                    className="hover:text-red-500 hover:bg-red-500/10"
                                  >
                                    <TrashIcon className="w-4 h-4" />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      }
                    })
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Roles Tab */}
        {activeTab === 'roles' && canViewRolesTab && (
          <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-medium text-charcoal dark:text-gray-100">Roles</h2>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Showing {filteredRoles.length} of {roles.length}
                </span>
              </div>
              <div className="relative w-56">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500 pointer-events-none z-10" />
                <Input
                  type="text"
                  placeholder="Search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            
            {/* Table */}
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 dark:bg-dark-surface-2/50">
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Name</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Users</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Permissions</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">Created</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-dark-border/50">
                {filteredRoles.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-gray-500 dark:text-gray-400 text-sm">
                      {searchQuery ? 'No roles match your search' : 'No roles yet. Create your first role to get started.'}
                    </td>
                  </tr>
                ) : (
                  filteredRoles.map((role) => {
                    const isPlatformAdminRole = role.role_name === 'platform_admin';
                    const canClickRow = canUpdateRole && !isPlatformAdminRole;
                    
                    return (
                      <tr 
                        key={role.id} 
                        className={`
                          transition-colors
                          ${isPlatformAdminRole 
                            ? 'bg-gray-50 dark:bg-dark-surface-2/30' 
                            : canClickRow
                              ? 'hover:bg-gray-50/50 dark:hover:bg-dark-surface-2/30 cursor-pointer'
                              : 'hover:bg-gray-50/50 dark:hover:bg-dark-surface-2/30'
                          }
                        `}
                        onClick={() => {
                          if (canClickRow) {
                            handleEditRole(role.id);
                          }
                        }}
                      >
                        <td className="px-4 py-3">
                          <div>
                            <div className="text-sm font-medium text-charcoal dark:text-gray-100 flex items-center gap-2">
                              {role.display_name || role.role_name}
                              {isPlatformAdminRole && (
                                <Badge variant="info">Platform</Badge>
                              )}
                              {role.is_system_role && !isPlatformAdminRole && (
                                <Badge variant="default">System</Badge>
                              )}
                            </div>
                            {isPlatformAdminRole ? (
                              <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                Managed via Platform Admin → Manage Admins
                              </div>
                            ) : role.description && (
                              <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate max-w-md">
                                {role.description}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                            <UsersIcon className="w-3.5 h-3.5" />
                            {role.user_count}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {isPlatformAdminRole ? 'All' : `${role.permission_count}`} permissions
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                          {formatDate(role.created_at)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {!role.is_system_role && !isPlatformAdminRole && canDeleteRole && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => handleDeleteRole(role.id, e)}
                              title="Delete role"
                              className="h-8 w-8 p-0 hover:text-red-500 hover:bg-red-500/10"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </PageBody>

      {/* Modals */}
      {canAssignRoles && (
        <EditUserRolesModal
          open={showEditUserRolesModal}
          onClose={() => setShowEditUserRolesModal(false)}
          user={selectedUser}
          roles={roles}
          selectedRoleIds={userRoleIds}
          onToggleRole={handleToggleUserRole}
          onSave={handleSaveUserRoles}
          saving={savingUserRoles}
        />
      )}

      {canCreateInvitation && (
        <InviteUserModal
          open={showInviteModal}
          onClose={() => setShowInviteModal(false)}
          roles={roles}
          onSubmit={handleCreateInvite}
          onSuccess={handleInviteSuccess}
        />
      )}

      {(canCreateRole || canUpdateRole) && (
        <RoleEditorModal
          open={showRoleModal}
          onClose={() => setShowRoleModal(false)}
          roleId={selectedRoleId}
          onSuccess={fetchData}
        />
      )}
    </Page>
  );
}

export default UsersRolesPage;

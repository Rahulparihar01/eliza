/**
 * Role Editor Modal
 * 
 * Modal for creating or editing roles with permission assignment.
 * Features collapsible permission sections with sub-groups and pill-style toggles.
 * Uses DS Modal, Input, Label, Textarea, Chip, and Button components.
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  CheckIcon,
  XMarkIcon,
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  LinkIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  BeakerIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import {
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  Button,
  Input,
  Textarea,
  Label,
  Chip,
  Spinner,
  Alert,
} from '../ui';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Permission structure
interface Permission {
  id: number;
  name: string;
  resource: string;
  action: string;
  description: string | null;
}

interface TenantRole {
  id: number;
  customer_id: string;
  role_name: string;
  display_name: string | null;
  description: string | null;
  is_system_role: boolean;
  is_active: boolean;
  permission_ids: number[];
}

export interface RoleEditorModalProps {
  open: boolean;
  onClose: () => void;
  roleId?: number | null; // null = new role, number = edit existing
  onSuccess?: () => void;
}

// Permission labels for display
const permissionLabels: Record<string, string> = {
  // AI Assistant
  'assistant:access': 'Access',
  'assistant:documents:read': 'Read',
  'assistant:documents:upload': 'Upload',
  'assistant:documents:delete': 'Delete',
  'assistant:questions:read': 'Read',
  'assistant:questions:ask': 'Ask',
  'assistant:questions:delete': 'Delete',
  'assistant:chat:access': 'Access',
  'assistant:domains:onboard': 'Onboard',
  'assistant:domains:configure': 'Configure',
  'assistant:domains:publish': 'Publish',
  'assistant:domains:delete': 'Delete',
  'assistant:domains:insurance_analytics:access': 'Insurance Analytics',
  
  // AI Recruiter
  'recruiter:access': 'Access',
  'recruiter:config:read': 'Read',
  'recruiter:config:create': 'Create',
  'recruiter:config:update': 'Update',
  'recruiter:config:delete': 'Delete',
  'recruiter:results:read': 'Read',
  'recruiter:results:email': 'Email',
  'recruiter:results:feedback': 'Feedback',
  'recruiter:email_templates:read': 'Read',
  'recruiter:email_templates:create': 'Create',
  'recruiter:email_templates:update': 'Update',
  'recruiter:email_templates:delete': 'Delete',
  'recruiter:email_templates:set_default': 'Set Default',
  'recruiter:blueprints:read': 'Read',
  'recruiter:blueprints:create': 'Create',
  'recruiter:blueprints:update': 'Update',
  'recruiter:blueprints:delete': 'Delete',
  'recruiter:dna:read': 'Read',
  'recruiter:dna:update': 'Update',
  'recruiter:history:read': 'Read',
  'recruiter:history:delete': 'Delete',
  'recruiter:reference_checks:access': 'Access',
  'recruiter:reference_checks:create': 'Create',
  'recruiter:reference_checks:read': 'Read',
  'recruiter:reference_checks:manage': 'Manage',
  'recruiter:section_library:read': 'Read',
  'recruiter:section_library:create': 'Create',
  'recruiter:section_library:update': 'Update',
  'recruiter:section_library:delete': 'Delete',
  
  // Administration
  'admin:settings:read': 'Read',
  'admin:settings:update': 'Update',
  'admin:settings:providers:manage': 'Manage Providers',
  'admin:email:read': 'Read',
  'admin:email:configure': 'Configure',
  'admin:email:disconnect': 'Disconnect',
  
  // Connections
  'connections:read': 'Read',
  'connections:create': 'Create',
  'connections:update': 'Update',
  'connections:delete': 'Delete',
  'connections:test': 'Test',
  'connections:sync': 'Sync',
  
  // Users
  'users:read': 'Read',
  'users:invite': 'Invite',
  'users:update': 'Update',
  'users:deactivate': 'Deactivate',
  'users:delete': 'Delete',
  
  // Roles
  'roles:read': 'Read',
  'roles:create': 'Create',
  'roles:update': 'Update',
  'roles:delete': 'Delete',
  'roles:assign': 'Assign',
  
  // Invites
  'invites:read': 'Read',
  'invites:create': 'Create',
  'invites:resend': 'Resend',
  'invites:revoke': 'Revoke',
  
  // Adoption Analytics
  'adoption:view_dashboard': 'View Dashboard',
  'adoption:read:company:*': 'Read Company Data',
  'adoption:admin:company:*': 'Admin Company Data',
  'adoption:manage_sharing': 'Manage Sharing',
  'adoption:manage_jobs': 'Manage Jobs',
  
  // Audit
  'audit:read': 'Read',
  'audit:export': 'Export',
  'audit:filter': 'Filter',
  
  // Labs
  'labs:agents:access': 'Access',
  'labs:agents:configure': 'Configure',
  'labs:agents:test': 'Test',
  'labs:resume_parsing:access': 'Access',
  'labs:resume_parsing:upload': 'Upload',
  'labs:resume_parsing:analyze': 'Analyze',
};

function getPermissionLabel(permName: string): string {
  return permissionLabels[permName] || permName.split(':').pop() || permName;
}

// Section icons
const sectionIcons: Record<string, React.ReactNode> = {
  assistant: <ChatBubbleLeftRightIcon className="w-5 h-5" />,
  recruiter: <UserGroupIcon className="w-5 h-5" />,
  admin: <Cog6ToothIcon className="w-5 h-5" />,
  connections: <LinkIcon className="w-5 h-5" />,
  users_roles: <UsersIcon className="w-5 h-5" />,
  adoption: <ChartBarIcon className="w-5 h-5" />,
  audit: <ClipboardDocumentListIcon className="w-5 h-5" />,
  labs: <BeakerIcon className="w-5 h-5" />,
};

interface PermissionGroup {
  label: string;
  permissions: Permission[];
}

interface PermissionSection {
  id: string;
  label: string;
  icon: React.ReactNode;
  groups: PermissionGroup[];
}

function organizePermissions(permissions: Permission[]): PermissionSection[] {
  const sections: PermissionSection[] = [];
  
  const findPerms = (prefix: string) => 
    permissions.filter(p => p.name.startsWith(prefix));
  
  // AI Assistant
  const assistantPerms = findPerms('assistant:');
  if (assistantPerms.length > 0) {
    sections.push({
      id: 'assistant',
      label: 'AI Assistant',
      icon: sectionIcons.assistant,
      groups: [
        { label: 'General', permissions: assistantPerms.filter(p => p.name === 'assistant:access') },
        { label: 'Documents', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:documents:')) },
        { label: 'Questions', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:questions:')) },
        { label: 'Chat', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:chat:')) },
        { label: 'Domains', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:domains:') && !p.name.includes(':access') || p.name === 'assistant:domains:access') },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // AI Recruiter
  const recruiterPerms = findPerms('recruiter:');
  if (recruiterPerms.length > 0) {
    sections.push({
      id: 'recruiter',
      label: 'AI Recruiter',
      icon: sectionIcons.recruiter,
      groups: [
        { label: 'General', permissions: recruiterPerms.filter(p => p.name === 'recruiter:access') },
        { label: 'Search Config', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:config:')) },
        { label: 'Results', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:results:')) },
        { label: 'Email Templates', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:email_templates:')) },
        { label: 'Section Library', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:section_library:')) },
        { label: 'Blueprints', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:blueprints:')) },
        { label: 'Company DNA', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:dna:')) },
        { label: 'History', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:history:')) },
        { label: 'Reference Checks', permissions: recruiterPerms.filter(p => p.name.startsWith('recruiter:reference_checks:')) },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // Administration
  const adminPerms = findPerms('admin:');
  if (adminPerms.length > 0) {
    sections.push({
      id: 'admin',
      label: 'Administration',
      icon: sectionIcons.admin,
      groups: [
        { label: 'Settings', permissions: adminPerms.filter(p => p.name.startsWith('admin:settings:')) },
        { label: 'Email Integration', permissions: adminPerms.filter(p => p.name.startsWith('admin:email:')) },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // Data Connections
  const connectionPerms = findPerms('connections:');
  if (connectionPerms.length > 0) {
    sections.push({
      id: 'connections',
      label: 'Data Connections',
      icon: sectionIcons.connections,
      groups: [
        { label: 'Manage', permissions: connectionPerms },
      ],
    });
  }
  
  // Users & Roles
  const userPerms = findPerms('users:');
  const rolePerms = findPerms('roles:');
  const invitePerms = findPerms('invites:');
  if (userPerms.length > 0 || rolePerms.length > 0 || invitePerms.length > 0) {
    sections.push({
      id: 'users_roles',
      label: 'Users & Roles',
      icon: sectionIcons.users_roles,
      groups: [
        { label: 'Users', permissions: userPerms },
        { label: 'Roles', permissions: rolePerms },
        { label: 'Invitations', permissions: invitePerms },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // Adoption Analytics
  const adoptionPerms = findPerms('adoption:');
  if (adoptionPerms.length > 0) {
    sections.push({
      id: 'adoption',
      label: 'Adoption Analytics',
      icon: sectionIcons.adoption,
      groups: [
        { label: 'Dashboard', permissions: adoptionPerms.filter(p => p.name.includes('dashboard') || p.name.includes('view')) },
        { label: 'Management', permissions: adoptionPerms.filter(p => !p.name.includes('dashboard') && !p.name.includes('view')) },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // Audit
  const auditPerms = findPerms('audit:');
  if (auditPerms.length > 0) {
    sections.push({
      id: 'audit',
      label: 'Audit & Logging',
      icon: sectionIcons.audit,
      groups: [
        { label: 'General', permissions: auditPerms },
      ],
    });
  }
  
  // Labs
  const labsPerms = findPerms('labs:');
  if (labsPerms.length > 0) {
    sections.push({
      id: 'labs',
      label: 'Labs (Coming Soon)',
      icon: sectionIcons.labs,
      groups: [
        { label: 'Agent Configuration', permissions: labsPerms.filter(p => p.name.startsWith('labs:agents:')) },
        { label: 'Resume Parsing', permissions: labsPerms.filter(p => p.name.startsWith('labs:resume_parsing:')) },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  return sections;
}

export function RoleEditorModal({
  open,
  onClose,
  roleId,
  onSuccess,
}: RoleEditorModalProps) {
  const isNewRole = !roleId;
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<number[]>([]);
  
  const [form, setForm] = useState({
    role_name: '',
    display_name: '',
    description: '',
  });
  
  const [existingRole, setExistingRole] = useState<TenantRole | null>(null);
  
  const sections = useMemo(() => organizePermissions(allPermissions), [allPermissions]);

  // Fetch data when modal opens
  useEffect(() => {
    if (open) {
      fetchData();
    }
  }, [open, roleId]);

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        setForm({ role_name: '', display_name: '', description: '' });
        setSelectedPermissionIds([]);
        setExistingRole(null);
        setError(null);
      }, 200);
    }
  }, [open]);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch permissions
      const permsRes = await AXIOS_INSTANCE.get('/api/v1/admin/permissions/all?scope=tenant');
      setAllPermissions(permsRes.data.permissions || []);
      
      // If editing, fetch role details
      if (roleId) {
        const roleRes = await AXIOS_INSTANCE.get(`/api/v1/admin/roles/${roleId}`);
        const role = roleRes.data;
        setExistingRole(role);
        setForm({
          role_name: role.role_name,
          display_name: role.display_name || '',
          description: role.description || '',
        });
        setSelectedPermissionIds(role.permission_ids || []);
      }
      
      setError(null);
    } catch (err: any) {
      console.error('Error fetching data:', err);
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!form.role_name.trim() && isNewRole) {
      setError('Role name is required');
      return;
    }
    
    setSaving(true);
    try {
      if (isNewRole) {
        await AXIOS_INSTANCE.post('/api/v1/admin/roles', {
          role_name: form.role_name.toLowerCase().replace(/\s+/g, '_'),
          display_name: form.display_name || null,
          description: form.description || null,
          permission_ids: selectedPermissionIds,
        });
      } else {
        await AXIOS_INSTANCE.put(`/api/v1/admin/roles/${roleId}`, {
          display_name: form.display_name || null,
          description: form.description || null,
        });
        await AXIOS_INSTANCE.put(`/api/v1/admin/roles/${roleId}/permissions`, {
          permission_ids: selectedPermissionIds,
        });
      }
      
      onSuccess?.();
      onClose();
    } catch (err: any) {
      console.error('Error saving role:', err);
      setError(err.response?.data?.detail || 'Failed to save role');
    } finally {
      setSaving(false);
    }
  };

  const togglePermission = (permId: number) => {
    setSelectedPermissionIds(prev =>
      prev.includes(permId)
        ? prev.filter(id => id !== permId)
        : [...prev, permId]
    );
  };

  const getSectionPermissionIds = (section: PermissionSection): number[] => {
    return section.groups.flatMap(g => g.permissions.map(p => p.id));
  };

  const selectAllInSection = (section: PermissionSection) => {
    const sectionIds = getSectionPermissionIds(section);
    setSelectedPermissionIds(prev => Array.from(new Set([...prev, ...sectionIds])));
  };

  const clearSection = (section: PermissionSection) => {
    const sectionIds = getSectionPermissionIds(section);
    setSelectedPermissionIds(prev => prev.filter(id => !sectionIds.includes(id)));
  };

  const modalTitle = isNewRole 
    ? 'Create Role' 
    : `Edit Role: ${existingRole?.display_name || existingRole?.role_name || 'Role'}`;

  return (
    <Modal open={open} onClose={onClose}>
      <ModalBackdrop />
      <ModalContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <ModalHeader>
          <ModalTitle>{modalTitle}</ModalTitle>
        </ModalHeader>

        <ModalBody className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : (
            <div className="space-y-6">
              {error && (
                <Alert variant="error" onDismiss={() => setError(null)}>
                  {error}
                </Alert>
              )}

              {/* Role Details */}
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100">
                  Role Details
                </h3>
                
                {isNewRole && (
                  <div className="space-y-2">
                    <Label htmlFor="role-name">
                      Role name <span className="text-red-500">*</span>
                    </Label>
                    <Input
                      id="role-name"
                      value={form.role_name}
                      onChange={(e) => setForm(prev => ({ ...prev, role_name: e.target.value }))}
                      placeholder="e.g., content-editor"
                    />
                  </div>
                )}
                
                <div className="space-y-2">
                  <Label htmlFor="display-name">Display Name</Label>
                  <Input
                    id="display-name"
                    value={form.display_name}
                    onChange={(e) => setForm(prev => ({ ...prev, display_name: e.target.value }))}
                    placeholder="e.g., Content Editor"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={form.description}
                    onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="What can users with this role do?"
                    rows={2}
                  />
                </div>
              </div>

              {/* Permissions */}
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100">
                    Permissions
                  </h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {selectedPermissionIds.length} of {allPermissions.length} selected
                  </p>
                </div>

                {/* Permission Sections */}
                <div className="space-y-3">
                  {sections.map((section) => {
                    const sectionIds = getSectionPermissionIds(section);
                    const selectedCount = sectionIds.filter(id => selectedPermissionIds.includes(id)).length;
                    const isFullySelected = selectedCount === sectionIds.length && sectionIds.length > 0;

                    return (
                      <div
                        key={section.id}
                        className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden"
                      >
                        {/* Section Header */}
                        <div className="px-4 py-2.5 bg-gray-100/50 dark:bg-dark-surface flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500 dark:text-gray-400">{section.icon}</span>
                            <span className="font-medium text-sm text-charcoal dark:text-gray-100">
                              {section.label}
                            </span>
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                              ({selectedCount}/{sectionIds.length})
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => selectAllInSection(section)}
                              className={`text-xs h-6 px-2 ${isFullySelected ? 'text-eliza-red' : ''}`}
                            >
                              Select all
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => clearSection(section)}
                              className="text-xs h-6 px-2"
                            >
                              Clear
                            </Button>
                          </div>
                        </div>

                        {/* Section Content */}
                        <div className="p-3 space-y-2">
                          {section.groups.map((group, groupIdx) => (
                            <div key={group.label} className={groupIdx > 0 ? 'pt-2 border-t border-gray-200/50 dark:border-dark-border/50' : ''}>
                              <div className="flex items-start gap-3">
                                <div className="w-24 flex-shrink-0 pt-1">
                                  <span className="text-xs text-gray-500 dark:text-gray-400">
                                    {group.label}
                                  </span>
                                </div>
                                <div className="flex flex-wrap gap-1.5 flex-1">
                                  {group.permissions.map((permission) => {
                                    const isSelected = selectedPermissionIds.includes(permission.id);
                                    return (
                                      <Chip
                                        key={permission.id}
                                        selected={isSelected}
                                        onClick={() => togglePermission(permission.id)}
                                        title={permission.description || permission.name}
                                        className="px-3 py-1 text-xs"
                                        selectedIcon={<CheckIcon className="w-3 h-3" />}
                                        unselectedIcon={<XMarkIcon className="w-3 h-3 opacity-40" />}
                                      >
                                        {getPermissionLabel(permission.name)}
                                      </Chip>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={saving || loading || (isNewRole && !form.role_name.trim())}
          >
            {saving ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Saving...
              </>
            ) : (
              isNewRole ? 'Create Role' : 'Save Changes'
            )}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

export default RoleEditorModal;

/**
 * Permission Section Selector
 * 
 * Northflank-style permission selection with collapsible sections,
 * sub-groups, and pill-style toggles.
 */

import React, { useMemo } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import {
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  LinkIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  BeakerIcon,
  ShieldCheckIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';

// Permission structure based on our comprehensive spec
export interface Permission {
  id: number;
  name: string;  // e.g., 'assistant:documents:read'
  resource: string;
  action: string;
  description: string | null;
}

// Organized structure for display
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

interface PermissionSectionSelectorProps {
  permissions: Permission[];
  selectedPermissionIds: number[];
  onTogglePermission: (permissionId: number) => void;
  onSelectAllInSection: (sectionId: string) => void;
  onClearSection: (sectionId: string) => void;
  disabledSections?: string[];  // Sections not available for tenant
}

// Map permission names to human-readable labels
const permissionLabels: Record<string, string> = {
  // AI Assistant
  'assistant:access': 'Access',
  'assistant:documents:read': 'Read',
  'assistant:documents:upload': 'Upload',
  'assistant:documents:delete': 'Delete',
  'assistant:questions:read': 'Read',
  'assistant:questions:ask': 'Ask',
  'assistant:questions:delete': 'Delete',
  'assistant:chat:access': 'Access Chat',
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
  
  // NOTE: platform:admin is NOT listed here - it's managed only via Platform Admin > Manage Admins
};

// Get label for permission
function getPermissionLabel(permName: string): string {
  return permissionLabels[permName] || permName.split(':').pop() || permName;
}

// Group permissions by their structure
function organizePermissions(permissions: Permission[]): PermissionSection[] {
  const sections: PermissionSection[] = [];
  
  // Helper to find permissions matching a pattern
  const findPerms = (prefix: string) => 
    permissions.filter(p => p.name.startsWith(prefix));
  
  // AI Assistant
  const assistantPerms = findPerms('assistant:');
  if (assistantPerms.length > 0) {
    sections.push({
      id: 'assistant',
      label: 'AI Assistant',
      icon: <ChatBubbleLeftRightIcon className="w-5 h-5" />,
      groups: [
        { label: 'General', permissions: assistantPerms.filter(p => p.name === 'assistant:access') },
        { label: 'Documents', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:documents:')) },
        { label: 'Questions', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:questions:')) },
        { label: 'Chat', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:chat:')) },
        { label: 'Domains', permissions: assistantPerms.filter(p => p.name.startsWith('assistant:domains:')) },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // AI Recruiter
  const recruiterPerms = findPerms('recruiter:');
  if (recruiterPerms.length > 0) {
    sections.push({
      id: 'recruiter',
      label: 'AI Recruiter',
      icon: <UserGroupIcon className="w-5 h-5" />,
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
      icon: <Cog6ToothIcon className="w-5 h-5" />,
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
      icon: <LinkIcon className="w-5 h-5" />,
      groups: [
        { label: 'General', permissions: connectionPerms },
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
      icon: <UsersIcon className="w-5 h-5" />,
      groups: [
        { label: 'User Management', permissions: userPerms },
        { label: 'Role Management', permissions: rolePerms },
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
      icon: <ChartBarIcon className="w-5 h-5" />,
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
      icon: <ClipboardDocumentListIcon className="w-5 h-5" />,
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
      icon: <BeakerIcon className="w-5 h-5" />,
      groups: [
        { label: 'Agent Configuration', permissions: labsPerms.filter(p => p.name.startsWith('labs:agents:')) },
        { label: 'Resume Parsing', permissions: labsPerms.filter(p => p.name.startsWith('labs:resume_parsing:')) },
      ].filter(g => g.permissions.length > 0),
    });
  }
  
  // NOTE: platform:admin permission is intentionally excluded from role editor
  // It can only be managed through Platform Admin > Manage Admins
  // This ensures tenant admins cannot grant themselves platform admin access
  
  return sections;
}

export function PermissionSectionSelector({
  permissions,
  selectedPermissionIds,
  onTogglePermission,
  onSelectAllInSection,
  onClearSection,
  disabledSections = [],
}: PermissionSectionSelectorProps) {
  const sections = useMemo(() => organizePermissions(permissions), [permissions]);
  
  // Get all permission IDs for a section
  const getSectionPermissionIds = (section: PermissionSection): number[] => {
    return section.groups.flatMap(g => g.permissions.map(p => p.id));
  };
  
  // Check if all permissions in a section are selected
  const isSectionFullySelected = (section: PermissionSection): boolean => {
    const sectionIds = getSectionPermissionIds(section);
    return sectionIds.length > 0 && sectionIds.every(id => selectedPermissionIds.includes(id));
  };
  
  // Check if any permissions in a section are selected
  const isSectionPartiallySelected = (section: PermissionSection): boolean => {
    const sectionIds = getSectionPermissionIds(section);
    return sectionIds.some(id => selectedPermissionIds.includes(id)) && !isSectionFullySelected(section);
  };
  
  return (
    <div className="space-y-4">
      {sections.map((section) => {
        const isDisabled = disabledSections.includes(section.id);
        const sectionPermIds = getSectionPermissionIds(section);
        const selectedCount = sectionPermIds.filter(id => selectedPermissionIds.includes(id)).length;
        
        return (
          <div
            key={section.id}
            className={`
              bg-surface rounded-lg border border-border overflow-hidden
              ${isDisabled ? 'opacity-50' : ''}
            `}
          >
            {/* Section Header */}
            <div className="px-4 py-3 bg-surface-2 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-muted">{section.icon}</span>
                <span className="font-medium text-text">{section.label}</span>
                {selectedCount > 0 && (
                  <span className="text-xs text-muted">
                    ({selectedCount}/{sectionPermIds.length})
                  </span>
                )}
              </div>
              
              {!isDisabled && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onSelectAllInSection(section.id)}
                    className={`
                      px-3 py-1 text-sm rounded transition-colors
                      ${isSectionFullySelected(section)
                        ? 'bg-brand/10 text-brand'
                        : 'bg-surface text-muted hover:text-text hover:bg-surface-2'
                      }
                    `}
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    onClick={() => onClearSection(section.id)}
                    className="px-3 py-1 text-sm bg-surface text-muted hover:text-text rounded transition-colors"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
            
            {/* Section Content */}
            <div className="p-4 space-y-4">
              {isDisabled ? (
                <p className="text-sm text-muted italic">
                  This feature is not available for your tenant
                </p>
              ) : (
                section.groups.map((group) => (
                  <div key={group.label}>
                    <div className="text-sm text-muted mb-2 font-medium">
                      {group.label}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {group.permissions.map((permission) => {
                        const isSelected = selectedPermissionIds.includes(permission.id);
                        return (
                          <button
                            key={permission.id}
                            type="button"
                            onClick={() => onTogglePermission(permission.id)}
                            title={permission.description || permission.name}
                            className={`
                              inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm
                              transition-all duration-150
                              ${isSelected
                                ? 'bg-brand/15 text-brand border border-brand/40 shadow-sm'
                                : 'bg-surface-2 text-muted border border-border hover:border-brand/30 hover:text-text'
                              }
                            `}
                          >
                            {isSelected && (
                              <XMarkIcon className="w-3.5 h-3.5" />
                            )}
                            {getPermissionLabel(permission.name)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default PermissionSectionSelector;


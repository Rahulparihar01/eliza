/**
 * Edit User Roles Modal
 * 
 * Modal for assigning/removing roles from a user.
 * Uses DS Modal and Chip components.
 */

import React from 'react';
import {
  UserCircleIcon,
  CheckIcon,
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
  Chip,
} from '../ui';

interface TenantRole {
  id: number;
  role_name: string;
  display_name: string | null;
  description: string | null;
}

interface TenantUser {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
}

export interface EditUserRolesModalProps {
  open: boolean;
  onClose: () => void;
  user: TenantUser | null;
  roles: TenantRole[];
  selectedRoleIds: number[];
  onToggleRole: (roleId: number) => void;
  onSave: () => void;
  saving?: boolean;
}

export function EditUserRolesModal({
  open,
  onClose,
  user,
  roles,
  selectedRoleIds,
  onToggleRole,
  onSave,
  saving = false,
}: EditUserRolesModalProps) {
  if (!user) return null;

  // Filter out platform_admin role - can only be assigned via Platform Admin > Manage Admins
  const assignableRoles = roles.filter((role) => role.role_name !== 'platform_admin');

  return (
    <Modal open={open} onClose={onClose}>
      <ModalBackdrop />
      <ModalContent className="max-w-md">
        <ModalHeader>
          <ModalTitle>Edit User Roles</ModalTitle>
        </ModalHeader>
        
        <ModalBody>
          {/* User Info */}
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 bg-eliza-red/10 rounded-full flex items-center justify-center">
              <UserCircleIcon className="w-6 h-6 text-eliza-red" />
            </div>
            <div>
              <div className="font-medium text-charcoal dark:text-gray-100 text-sm">
                {user.full_name || user.username}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {user.email}
              </div>
            </div>
          </div>

          {/* Role Selection */}
          <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3">
            Assign Roles
          </h3>
          <div className="flex flex-wrap gap-2">
            {assignableRoles.map((role) => {
              const isAssigned = selectedRoleIds.includes(role.id);
              return (
                <Chip
                  key={role.id}
                  selected={isAssigned}
                  onClick={() => onToggleRole(role.id)}
                  selectedIcon={<CheckIcon className="w-4 h-4" />}
                >
                  {role.display_name || role.role_name}
                </Chip>
              );
            })}
          </div>
        </ModalBody>
        
        <ModalFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

export default EditUserRolesModal;

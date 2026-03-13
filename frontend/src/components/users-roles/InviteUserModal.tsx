/**
 * Invite User Modal
 * 
 * Modal for inviting new users to the organization.
 * Shows a form to enter email, name, and assign roles.
 * Closes on success and notifies parent to show toast.
 * Uses DS Modal, Input, Label, Chip, and Button components.
 */

import React, { useState, useEffect } from 'react';
import {
  UserPlusIcon,
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
  Input,
  Label,
  Chip,
  Spinner,
  Alert,
} from '../ui';

interface TenantRole {
  id: number;
  role_name: string;
  display_name: string | null;
  description: string | null;
}

export interface InviteUserModalProps {
  open: boolean;
  onClose: () => void;
  roles: TenantRole[];
  onSubmit: (data: { email: string; full_name: string; role_ids: number[] }) => Promise<string>;
  onSuccess?: (email: string, inviteUrl: string) => void;
}

export function InviteUserModal({
  open,
  onClose,
  roles,
  onSubmit,
  onSuccess,
}: InviteUserModalProps) {
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-populate with viewer role when roles are loaded
  useEffect(() => {
    if (roles.length > 0 && selectedRoleIds.length === 0) {
      const viewerRole = roles.find(r => r.role_name === 'viewer');
      if (viewerRole) {
        setSelectedRoleIds([viewerRole.id]);
      }
    }
  }, [roles, selectedRoleIds.length]);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setError(null);
    }
  }, [open]);

  const handleToggleRole = (roleId: number) => {
    setSelectedRoleIds(prev =>
      prev.includes(roleId)
        ? prev.filter(id => id !== roleId)
        : [...prev, roleId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (selectedRoleIds.length === 0) {
      setError('Please select at least one role for the invited user');
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const inviteUrl = await onSubmit({
        email,
        full_name: fullName,
        role_ids: selectedRoleIds,
      });
      
      // Close modal and notify parent
      const invitedEmail = email;
      handleClose();
      onSuccess?.(invitedEmail, inviteUrl);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create invite');
    } finally {
      setCreating(false);
    }
  };

  const handleClose = () => {
    onClose();
    // Reset form after close animation
    setTimeout(() => {
      setEmail('');
      setFullName('');
      setError(null);
      const viewerRole = roles.find(r => r.role_name === 'viewer');
      setSelectedRoleIds(viewerRole ? [viewerRole.id] : []);
    }, 200);
  };

  // Filter out platform_admin role
  const assignableRoles = roles.filter(r => r.role_name !== 'platform_admin');

  return (
    <Modal open={open} onClose={handleClose}>
      <ModalBackdrop />
      <ModalContent className="max-w-lg">
        <ModalHeader>
          <ModalTitle>Invite New User</ModalTitle>
        </ModalHeader>

        <form onSubmit={handleSubmit}>
          <ModalBody className="space-y-4">
            {error && (
              <Alert variant="error" onDismiss={() => setError(null)}>
                {error}
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="invite-email">
                Email Address <span className="text-red-500">*</span>
              </Label>
              <Input
                id="invite-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="invite-name">Full Name</Label>
              <Input
                id="invite-name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="John Smith"
              />
            </div>

            <div className="space-y-2">
              <Label>
                Assign Role <span className="text-red-500">*</span>
              </Label>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Select the role(s) the user will have when they accept the invite.
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {assignableRoles.length === 0 ? (
                  <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                    No roles available. Create roles first.
                  </p>
                ) : (
                  assignableRoles.map((role) => {
                    const isSelected = selectedRoleIds.includes(role.id);
                    return (
                      <Chip
                        key={role.id}
                        selected={isSelected}
                        onClick={() => handleToggleRole(role.id)}
                        selectedIcon={<CheckIcon className="w-4 h-4" />}
                      >
                        {role.display_name || role.role_name}
                      </Chip>
                    );
                  })
                )}
              </div>
              {assignableRoles.length > 0 && selectedRoleIds.length === 0 && (
                <p className="text-xs text-amber-500">
                  Please select at least one role
                </p>
              )}
            </div>
          </ModalBody>

          <ModalFooter>
            <Button type="button" variant="ghost" onClick={handleClose}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              disabled={creating || selectedRoleIds.length === 0}
            >
              {creating ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Sending...
                </>
              ) : (
                <>
                  <UserPlusIcon className="w-4 h-4" />
                  Send Invite
                </>
              )}
            </Button>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
}

export default InviteUserModal;

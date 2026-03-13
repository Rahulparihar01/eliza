/**
 * Email Integration Page
 * 
 * Platform admin page for managing Google Email OAuth integration.
 * 
 * Migrated to DS components (Jan 2026).
 * 
 * DS Components used:
 * - Page, PageHeader, PageBody (layout)
 * - Button, Input, Label (form)
 * - Spinner (feedback)
 * - Modal, ModalContent, ModalHeader, ModalTitle, ModalDescription, ModalBody, ModalFooter (dialogs)
 */

import React, { useState } from 'react';
import {
  EnvelopeIcon,
  PlusIcon,
  CheckIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettingsApi } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Input,
  Label,
  Spinner,
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
} from '../../components/ui';

export function EmailIntegrationPage() {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  const [showConfigModal, setShowConfigModal] = useState(false);
  const [formData, setFormData] = useState({
    client_id: '',
    client_secret: '',
    redirect_uri: '',
  });

  // Fetch Google email configuration
  const { data: googleEmailConfig, isLoading } = useQuery({
    queryKey: ['settings', 'google-email'],
    queryFn: async () => {
      const response = await getSettingsApi().get('/v1/settings/google-email/config');
      return response.data;
    },
  });

  // Mutation to update Google email configuration
  const updateGoogleEmailConfig = useMutation({
    mutationFn: async (data: { client_id?: string; client_secret?: string; redirect_uri?: string }) => {
      const response = await getSettingsApi().put('/v1/settings/google-email/config', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'google-email'] });
      addToast({ kind: 'success', message: 'Google email configuration updated successfully' });
      setShowConfigModal(false);
      setFormData({ client_id: '', client_secret: '', redirect_uri: '' });
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to update Google email configuration' });
    },
  });

  // Mutation to disconnect Google email
  const disconnectGoogleEmail = useMutation({
    mutationFn: async () => {
      const response = await getSettingsApi().post('/v1/settings/google-email/disconnect');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'google-email'] });
      addToast({ kind: 'success', message: 'Google email account disconnected successfully' });
    },
    onError: (error: any) => {
      addToast({ kind: 'error', message: error.response?.data?.detail || 'Failed to disconnect Google email account' });
    },
  });

  // Open modal with prefilled data
  const handleOpenConfigModal = () => {
    setFormData({
      client_id: googleEmailConfig?.client_id || '',
      client_secret: '',
      redirect_uri: googleEmailConfig?.redirect_uri || window.location.origin + '/auth/google/callback',
    });
    setShowConfigModal(true);
  };

  // Handle save
  const handleSave = () => {
    updateGoogleEmailConfig.mutate({
      client_id: formData.client_id || undefined,
      client_secret: formData.client_secret || undefined,
      redirect_uri: formData.redirect_uri || undefined,
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Email Integration"
          description="Configure Google Email OAuth for candidate outreach"
        />
        <PageBody className="pt-0">
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
        title="Email Integration"
        description="Configure Google Email OAuth for candidate outreach"
        actions={
          <Button onClick={handleOpenConfigModal}>
            <PlusIcon className="w-4 h-4 mr-2" />
            {googleEmailConfig?.is_connected ? 'Update' : 'Configure'}
          </Button>
        }
      />
      <PageBody className="pt-0">
        {/* Status Card */}
        <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
            {/* Card Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
              <div className="flex items-center gap-3">
                <EnvelopeIcon className="w-5 h-5 text-eliza-red" />
                <div>
                  <h2 className="text-base font-medium text-charcoal dark:text-gray-100">
                    Google Email Integration
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Connect a Google account to enable email composition from candidate outreach
                  </p>
                </div>
              </div>
            </div>

            {/* Card Body */}
            <div className="px-6 py-4">
              <div className="space-y-4">
                {/* Connection Status */}
                {googleEmailConfig?.is_connected ? (
                  <div className="flex items-center justify-between p-4 bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <CheckIcon className="w-5 h-5 text-green-500" />
                      <div>
                        <p className="text-sm font-medium text-charcoal dark:text-gray-100">
                          Google account connected
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {googleEmailConfig.connected_email}
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        if (window.confirm('Are you sure you want to disconnect the Google email account?')) {
                          disconnectGoogleEmail.mutate();
                        }
                      }}
                      disabled={disconnectGoogleEmail.isPending}
                    >
                      <XCircleIcon className="w-4 h-4 mr-1.5" />
                      {disconnectGoogleEmail.isPending ? 'Disconnecting...' : 'Disconnect'}
                    </Button>
                  </div>
                ) : (
                  <div className="p-4 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg">
                    <p className="text-sm text-gray-600 dark:text-gray-300">
                      No Google account connected. Click "Configure" above to set up email integration.
                    </p>
                  </div>
                )}

                {/* Configuration Summary */}
                {googleEmailConfig?.client_id && (
                  <div className="space-y-2 pt-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Client ID:</span>
                      <span className="font-mono text-charcoal dark:text-gray-100 text-xs">
                        {googleEmailConfig.client_id}
                      </span>
                    </div>
                    {googleEmailConfig.redirect_uri && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500 dark:text-gray-400">Redirect URI:</span>
                        <span className="font-mono text-charcoal dark:text-gray-100 text-xs">
                          {googleEmailConfig.redirect_uri}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
      </PageBody>

      {/* Configuration Modal */}
      <Modal open={showConfigModal} onClose={() => setShowConfigModal(false)}>
        <ModalContent className="max-w-lg">
          <ModalHeader>
            <ModalTitle>Configure Google Email Integration</ModalTitle>
            <ModalDescription>
              Set up OAuth credentials to enable email outreach from the platform
            </ModalDescription>
          </ModalHeader>

          <ModalBody className="space-y-4">
            {/* Client ID */}
            <div>
              <Label className="mb-2">Google OAuth Client ID</Label>
              <Input
                type="text"
                value={formData.client_id}
                onChange={(e) => setFormData({ ...formData, client_id: e.target.value })}
                placeholder="123456789-abcdefghijklmnop.apps.googleusercontent.com"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Get this from Google Cloud Console → APIs & Services → Credentials
              </p>
            </div>

            {/* Client Secret */}
            <div>
              <Label className="mb-2">Google OAuth Client Secret</Label>
              <Input
                type="password"
                value={formData.client_secret}
                onChange={(e) => setFormData({ ...formData, client_secret: e.target.value })}
                placeholder={googleEmailConfig?.client_secret ? '••••••••••••••••' : 'Enter client secret'}
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Leave blank to keep existing secret unchanged
              </p>
            </div>

            {/* Redirect URI */}
            <div>
              <Label className="mb-2">Redirect URI</Label>
              <Input
                type="text"
                value={formData.redirect_uri}
                onChange={(e) => setFormData({ ...formData, redirect_uri: e.target.value })}
                placeholder={window.location.origin + '/auth/google/callback'}
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Must match the authorized redirect URI in Google Cloud Console
              </p>
            </div>

            {/* Setup Instructions */}
            <div className="p-4 bg-eliza-red/5 border border-eliza-red/20 rounded-lg">
              <h4 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-2">
                Setup Instructions:
              </h4>
              <ol className="list-decimal list-inside space-y-1.5 text-sm text-gray-500 dark:text-gray-400">
                <li>
                  Go to{' '}
                  <a
                    href="https://console.cloud.google.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-eliza-red hover:underline"
                  >
                    Google Cloud Console
                  </a>
                </li>
                <li>Create a new project or select an existing one</li>
                <li>Enable the Gmail API</li>
                <li>Create OAuth 2.0 credentials (Web application)</li>
                <li>Add the redirect URI above to authorized redirect URIs</li>
                <li>Copy the Client ID and Client Secret here</li>
              </ol>
            </div>
          </ModalBody>

          <ModalFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setShowConfigModal(false);
                setFormData({ client_id: '', client_secret: '', redirect_uri: '' });
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={updateGoogleEmailConfig.isPending}>
              {updateGoogleEmailConfig.isPending && <Spinner size="sm" className="mr-2" />}
              {updateGoogleEmailConfig.isPending ? 'Saving...' : 'Save Configuration'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Page>
  );
}

export default EmailIntegrationPage;

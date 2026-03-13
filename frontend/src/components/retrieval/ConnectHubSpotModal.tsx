/**
 * ConnectHubSpotModal – Lets a user connect their HubSpot account
 * via OAuth or by pasting a private-app token.
 *
 * The token is validated against the HubSpot API before being saved.
 */

import React, { useState } from 'react';
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
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
  Alert,
  Spinner,
} from '../../components/ui';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { CheckCircleIcon } from '@heroicons/react/24/outline';

interface Props {
  open: boolean;
  onClose: () => void;
  onConnected: () => void;
}

export default function ConnectHubSpotModal({ open, onClose, onConnected }: Props) {
  const [tab, setTab] = useState<string>('token');
  const [token, setToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validated, setValidated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetState = () => {
    setToken('');
    setValidated(false);
    setError(null);
    setSaving(false);
    setValidating(false);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  // --- Validate token against HubSpot API ---
  const handleValidate = async () => {
    if (!token.trim()) return;
    setValidating(true);
    setError(null);
    setValidated(false);
    try {
      await AXIOS_INSTANCE.post('/api/retrieval/connections/validate', {
        source_type: 'hubspot',
        token: token.trim(),
      });
      setValidated(true);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Invalid token. Please check and try again.');
    } finally {
      setValidating(false);
    }
  };

  // --- Save validated token ---
  const handleSaveToken = async () => {
    if (!token.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await AXIOS_INSTANCE.post('/api/retrieval/connections', {
        source_type: 'hubspot',
        token: token.trim(),
      });
      onConnected();
      handleClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to save token');
    } finally {
      setSaving(false);
    }
  };

  // --- OAuth flow ---
  const handleOAuth = async () => {
    setError(null);
    try {
      const { data } = await AXIOS_INSTANCE.get('/oauth/authorize/hubspot');
      const popup = window.open(data.authorize_url, 'hubspot_oauth', 'width=600,height=700');
      const handler = (event: MessageEvent) => {
        if (event.data?.type === 'oauth_complete' && event.data?.source === 'hubspot') {
          window.removeEventListener('message', handler);
          onConnected();
          handleClose();
        }
      };
      window.addEventListener('message', handler);

      const interval = setInterval(() => {
        if (popup?.closed) {
          clearInterval(interval);
          window.removeEventListener('message', handler);
        }
      }, 1000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to initiate OAuth');
    }
  };

  // Reset validation when token changes
  const handleTokenChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setToken(e.target.value);
    setValidated(false);
    setError(null);
  };

  if (!open) return null;

  const isProcessing = saving || validating;

  return (
    <Modal open={open} onClose={handleClose}>
      <ModalBackdrop />
      <ModalContent className="max-w-lg">
        <ModalHeader>
          <ModalTitle>Connect HubSpot</ModalTitle>
        </ModalHeader>
        <ModalBody>
          <Tabs defaultValue="token" value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="token">Private App Token</TabsTrigger>
              <TabsTrigger value="oauth">OAuth</TabsTrigger>
            </TabsList>

            <TabsContent value="token" className="mt-4 space-y-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Paste a HubSpot private-app access token. It will be validated against the HubSpot API before saving.
              </p>
              <Input
                placeholder="pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={token}
                onChange={handleTokenChange}
                type="password"
              />
              {validated && (
                <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                  <CheckCircleIcon className="h-5 w-5" />
                  <span className="text-sm font-medium">Token is valid</span>
                </div>
              )}
            </TabsContent>

            <TabsContent value="oauth" className="mt-4 space-y-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Sign in with your HubSpot account to authorize access to contacts, companies, and deals.
              </p>
              <Button onClick={handleOAuth} className="w-full">
                Connect with HubSpot
              </Button>
            </TabsContent>
          </Tabs>

          {error && (
            <Alert variant="error" className="mt-4">
              {error}
            </Alert>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" onClick={handleClose}>
            Cancel
          </Button>
          {tab === 'token' && !validated && (
            <Button onClick={handleValidate} disabled={isProcessing || !token.trim()}>
              {validating ? <Spinner className="mr-2 h-4 w-4" /> : null}
              Validate Token
            </Button>
          )}
          {tab === 'token' && validated && (
            <Button onClick={handleSaveToken} disabled={isProcessing}>
              {saving ? <Spinner className="mr-2 h-4 w-4" /> : null}
              Save & Connect
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

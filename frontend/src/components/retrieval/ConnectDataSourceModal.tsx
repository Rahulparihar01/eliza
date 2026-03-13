/**
 * ConnectDataSourceModal – Generic modal for connecting data sources
 * (HubSpot, Fathom, etc.) via API key / token.
 *
 * The token is validated against the source API before being saved.
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
  Alert,
  Spinner,
} from '../../components/ui';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { CheckCircleIcon } from '@heroicons/react/24/outline';

/** Configuration for each data source type */
const SOURCE_CONFIG: Record<
  string,
  {
    label: string;
    placeholder: string;
    description: string;
    icon?: string;
  }
> = {
  hubspot: {
    label: 'HubSpot',
    placeholder: 'pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
    description:
      'Paste a HubSpot private-app access token or developer API key. It will be validated against the HubSpot API before saving.',
  },
  fathom: {
    label: 'Fathom',
    placeholder: 'fathom_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    description:
      'Paste your Fathom API key (from User Settings → API Access). It will be validated against the Fathom API before saving.',
  },
};

interface Props {
  open: boolean;
  sourceType: string;
  onClose: () => void;
  onConnected: () => void;
}

export default function ConnectDataSourceModal({
  open,
  sourceType,
  onClose,
  onConnected,
}: Props) {
  const [token, setToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validated, setValidated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const config = SOURCE_CONFIG[sourceType] || {
    label: sourceType,
    placeholder: 'Enter API key...',
    description: 'Paste your API key. It will be validated before saving.',
  };

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

  // --- Validate token against source API ---
  const handleValidate = async () => {
    if (!token.trim()) return;
    setValidating(true);
    setError(null);
    setValidated(false);
    try {
      await AXIOS_INSTANCE.post('/api/retrieval/connections/validate', {
        source_type: sourceType,
        token: token.trim(),
      });
      setValidated(true);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : 'Invalid token. Please check and try again.'
      );
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
        source_type: sourceType,
        token: token.trim(),
      });
      onConnected();
      handleClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(
        typeof detail === 'string' ? detail : 'Failed to save token'
      );
    } finally {
      setSaving(false);
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
          <ModalTitle>Connect {config.label}</ModalTitle>
        </ModalHeader>
        <ModalBody>
          <div className="space-y-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">{config.description}</p>
            <Input
              placeholder={config.placeholder}
              value={token}
              onChange={handleTokenChange}
              type="password"
            />
            {validated && (
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircleIcon className="h-5 w-5" />
                <span className="text-sm font-medium">
                  Token is valid
                </span>
              </div>
            )}
          </div>

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
          {!validated && (
            <Button
              onClick={handleValidate}
              disabled={isProcessing || !token.trim()}
            >
              {validating ? (
                <Spinner className="mr-2 h-4 w-4" />
              ) : null}
              Validate Token
            </Button>
          )}
          {validated && (
            <Button onClick={handleSaveToken} disabled={isProcessing}>
              {saving ? (
                <Spinner className="mr-2 h-4 w-4" />
              ) : null}
              Save & Connect
            </Button>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

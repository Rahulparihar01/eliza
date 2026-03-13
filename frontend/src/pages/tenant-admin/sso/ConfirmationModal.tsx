import React, { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalTitle,
  Spinner,
} from '../../../components/ui';

interface ConfirmationModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
  title: string;
  body: string;
  bullets?: string[];
  confirmLabel: string;
  confirmVariant?: 'default' | 'destructive';
  requireTypedConfirmation?: string;
  isLoading?: boolean;
}

export function ConfirmationModal({
  open,
  onClose,
  onConfirm,
  title,
  body,
  bullets,
  confirmLabel,
  confirmVariant = 'default',
  requireTypedConfirmation,
  isLoading = false,
}: ConfirmationModalProps) {
  const [typedValue, setTypedValue] = useState('');

  const canConfirm = useMemo(() => {
    if (!requireTypedConfirmation) return true;
    return typedValue.trim().toLowerCase() === requireTypedConfirmation.toLowerCase();
  }, [typedValue, requireTypedConfirmation]);

  const handleClose = () => {
    setTypedValue('');
    onClose();
  };

  const handleConfirm = async () => {
    await onConfirm();
    setTypedValue('');
  };

  return (
    <Modal open={open} onClose={handleClose}>
      <ModalContent size="md">
        <ModalHeader>
          <ModalTitle>{title}</ModalTitle>
        </ModalHeader>
        <ModalBody className="space-y-3">
          <Alert variant={confirmVariant === 'destructive' ? 'warning' : 'info'}>
            {body}
          </Alert>
          {bullets && bullets.length > 0 && (
            <ul className="space-y-1 text-sm text-gray-600 dark:text-gray-400">
              {bullets.map((bullet) => (
                <li key={bullet} className="flex items-start gap-2">
                  <span className="mt-0.5">•</span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          )}
          {requireTypedConfirmation && (
            <div className="space-y-2">
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Type <code>{requireTypedConfirmation}</code> to confirm:
              </p>
              <Input
                value={typedValue}
                onChange={(e) => setTypedValue(e.target.value)}
                autoFocus
              />
            </div>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="secondary" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant={confirmVariant === 'destructive' ? 'destructive' : 'default'}
            onClick={handleConfirm}
            disabled={!canConfirm || isLoading}
          >
            {isLoading && <Spinner size="sm" className="mr-2" />}
            {confirmLabel}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

/**
 * Multi-Tenant Welcome Popup
 * 
 * Shown to users who have access to multiple tenants
 * on their first login to a new tenant or when they first
 * become a multi-tenant user.
 * 
 * Highlights the tenant switcher feature.
 * Uses DS Modal components.
 */

import React, { useEffect, useState } from 'react';
import { 
  BuildingOffice2Icon,
  ChevronDownIcon,
  ArrowsRightLeftIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '../../stores/useAuth';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  Button,
} from '../ui';

export function MultiTenantWelcome() {
  const { user, showWelcomePopup, dismissWelcomePopup } = useAuth();
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (showWelcomePopup && user?.has_multiple_tenants) {
      // Delay showing for smoother appearance
      const timer = setTimeout(() => {
        setIsVisible(true);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [showWelcomePopup, user?.has_multiple_tenants]);

  const handleDismiss = () => {
    setIsVisible(false);
    setTimeout(() => {
      dismissWelcomePopup();
    }, 200);
  };

  if (!showWelcomePopup || !user?.has_multiple_tenants) {
    return null;
  }

  const tenantCount = user.tenant_memberships?.length || 0;

  return (
    <Modal open={isVisible} onClose={handleDismiss}>
      <ModalContent size="md">
        <ModalHeader showCloseButton={true}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-eliza-red/10 rounded-lg flex items-center justify-center">
              <ArrowsRightLeftIcon className="w-5 h-5 text-eliza-red" />
            </div>
            <div>
              <ModalTitle>You're in {tenantCount} Organizations</ModalTitle>
              <ModalDescription>Here's how to switch between them</ModalDescription>
            </div>
          </div>
        </ModalHeader>

        <ModalBody className="space-y-4">
          {/* Visual instruction */}
          <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border">
                <span className="text-sm font-semibold text-charcoal dark:text-white">Eliza Forge</span>
                <span className="text-xs text-gray-500 dark:text-gray-400">for</span>
                <span className="text-sm font-medium text-charcoal dark:text-white">{user.customer_name}</span>
                <ChevronDownIcon className="w-4 h-4 text-gray-400" />
              </div>
              <span className="text-xs text-eliza-red font-medium animate-pulse">← Click here!</span>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Click the organization name in the header to see all your organizations and switch between them.
            </p>
          </div>

          {/* Organization list preview */}
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Your organizations:</p>
            <div className="space-y-1">
              {user.tenant_memberships?.slice(0, 3).map((membership) => {
                const isCurrent = membership.customer_id === user.customer_id;
                const isDefault = membership.is_default && !isCurrent;
                
                return (
                  <div 
                    key={membership.customer_id}
                    className={`
                      flex items-center gap-2 px-3 py-2 rounded-lg
                      ${isCurrent 
                        ? 'bg-eliza-red/10 border border-eliza-red/20' 
                        : 'bg-gray-50 dark:bg-dark-surface-2'
                      }
                    `}
                  >
                    <BuildingOffice2Icon 
                      className={`w-4 h-4 ${isCurrent ? 'text-eliza-red' : 'text-gray-400 dark:text-gray-500'}`} 
                    />
                    <span 
                      className={`text-sm ${isCurrent ? 'text-eliza-red font-medium' : 'text-charcoal dark:text-white'}`}
                    >
                      {membership.customer_name}
                    </span>
                    {isCurrent && (
                      <span className="text-xs text-eliza-red ml-auto">Current</span>
                    )}
                    {isDefault && (
                      <span className="text-xs text-amber-500 ml-auto">Default</span>
                    )}
                  </div>
                );
              })}
              {(user.tenant_memberships?.length || 0) > 3 && (
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-1">
                  +{(user.tenant_memberships?.length || 0) - 3} more
                </p>
              )}
            </div>
          </div>
        </ModalBody>

        <ModalFooter>
          <Button onClick={handleDismiss} className="w-full">
            Got it!
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

export default MultiTenantWelcome;

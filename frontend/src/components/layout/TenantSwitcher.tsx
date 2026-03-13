/**
 * Tenant Switcher Component
 * 
 * Dropdown for multi-tenant users to switch between tenants.
 * Shown when user belongs to multiple tenants.
 */

import React, { useState } from 'react';
import { Menu, Transition } from '@headlessui/react';
import { 
  ChevronDownIcon, 
  CheckIcon, 
  BuildingOffice2Icon,
  StarIcon
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import { useAuth, TenantMembership } from '../../stores/useAuth';
import { AXIOS_INSTANCE } from '../../services/api-client';

interface TenantSwitcherProps {
  className?: string;
}

export function TenantSwitcher({ className = '' }: TenantSwitcherProps) {
  const { user, setUser } = useAuth();
  const [switching, setSwitching] = useState(false);
  const [settingDefault, setSettingDefault] = useState<string | null>(null);

  // Don't render if user doesn't have multiple tenants
  if (!user?.has_multiple_tenants || !user.tenant_memberships?.length) {
    // Just show static tenant name
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <span className="text-text font-semibold text-base">Eliza Forge</span>
        {user?.customer_name && (
          <>
            <span className="text-muted text-sm">for</span>
            <span className="text-text font-medium text-sm">{user.customer_name}</span>
          </>
        )}
      </div>
    );
  }

  const handleSwitchTenant = async (customerId: string) => {
    if (customerId === user.customer_id || switching) return;
    
    setSwitching(true);
    try {
      const response = await AXIOS_INSTANCE.post('/v1/auth/switch-tenant', {
        customer_id: customerId
      });
      
      const { access_token, refresh_token, user: newUserProfile, show_welcome_popup } = response.data;
      
      // Update tokens (API client reads auth_token)
      localStorage.setItem('auth_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      localStorage.removeItem('access_token');
      
      // Update user state
      setUser(newUserProfile);
      
      // Show welcome popup if first time in this tenant
      if (show_welcome_popup) {
        // This will be handled by the auth store
      }
      
      // Reload the page to reset all state
      window.location.reload();
    } catch (err) {
      console.error('Failed to switch tenant:', err);
    } finally {
      setSwitching(false);
    }
  };

  const handleSetDefault = async (customerId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (settingDefault) return;
    
    setSettingDefault(customerId);
    try {
      await AXIOS_INSTANCE.put('/v1/auth/default-tenant', {
        customer_id: customerId
      });
      
      // Update local state to reflect new default
      if (user.tenant_memberships) {
        const updatedMemberships = user.tenant_memberships.map(m => ({
          ...m,
          is_default: m.customer_id === customerId
        }));
        setUser({
          ...user,
          tenant_memberships: updatedMemberships
        });
      }
    } catch (err) {
      console.error('Failed to set default tenant:', err);
    } finally {
      setSettingDefault(null);
    }
  };

  const currentTenant = user.tenant_memberships.find(m => m.customer_id === user.customer_id);

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      <Menu as="div" className="relative">
        <Menu.Button 
          className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-surface-2 transition-colors group"
          disabled={switching}
        >
          <span className="text-text font-semibold text-base">Eliza Forge</span>
          <span className="text-muted text-sm">for</span>
          <span className="text-text font-medium text-sm flex items-center gap-1">
            {user.customer_name || currentTenant?.customer_name}
            {currentTenant?.is_default && (
              <StarIconSolid className="w-3 h-3 text-amber-500" title="Default tenant" />
            )}
          </span>
          <ChevronDownIcon className={`w-4 h-4 text-muted transition-transform ${switching ? 'animate-spin' : 'group-hover:translate-y-0.5'}`} />
        </Menu.Button>

      <Transition
        enter="transition ease-out duration-100"
        enterFrom="transform opacity-0 scale-95"
        enterTo="transform opacity-100 scale-100"
        leave="transition ease-in duration-75"
        leaveFrom="transform opacity-100 scale-100"
        leaveTo="transform opacity-0 scale-95"
      >
        <Menu.Items className="absolute left-0 mt-2 w-72 bg-surface border border-border rounded-lg shadow-lg focus:outline-none z-50">
          <div className="p-2 border-b border-border">
            <p className="text-xs text-muted px-2">Switch Organization</p>
          </div>
          
          <div className="py-1 max-h-64 overflow-y-auto">
            {user.tenant_memberships.map((membership) => {
              const isActive = membership.customer_id === user.customer_id;
              const isDefault = membership.is_default;
              
              return (
                <Menu.Item key={membership.customer_id}>
                  {({ active }) => (
                    <button
                      onClick={() => handleSwitchTenant(membership.customer_id)}
                      disabled={isActive || switching}
                      className={`
                        w-full flex items-center justify-between px-3 py-2.5 text-sm
                        ${active && !isActive ? 'bg-surface-2' : ''}
                        ${isActive ? 'bg-brand/10' : ''}
                        ${switching ? 'opacity-50 cursor-wait' : ''}
                      `}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isActive ? 'bg-brand/20' : 'bg-surface-2'}`}>
                          <BuildingOffice2Icon className={`w-4 h-4 ${isActive ? 'text-brand' : 'text-muted'}`} />
                        </div>
                        <div className="text-left">
                          <div className={`font-medium ${isActive ? 'text-brand' : 'text-text'}`}>
                            {membership.customer_name}
                          </div>
                          <div className="text-xs text-muted">
                            {membership.customer_id}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {/* Default star */}
                        <button
                          onClick={(e) => handleSetDefault(membership.customer_id, e)}
                          className={`p-1 rounded hover:bg-surface-3 ${settingDefault === membership.customer_id ? 'animate-pulse' : ''}`}
                          title={isDefault ? 'Default tenant' : 'Set as default'}
                        >
                          {isDefault ? (
                            <StarIconSolid className="w-4 h-4 text-amber-500" />
                          ) : (
                            <StarIcon className="w-4 h-4 text-muted hover:text-amber-500" />
                          )}
                        </button>
                        
                        {/* Active check */}
                        {isActive && (
                          <CheckIcon className="w-5 h-5 text-brand" />
                        )}
                      </div>
                    </button>
                  )}
                </Menu.Item>
              );
            })}
          </div>
          
          <div className="p-2 border-t border-border">
            <p className="text-xs text-muted px-2">
              <StarIconSolid className="w-3 h-3 text-amber-500 inline mr-1" />
              Default tenant is used on login
            </p>
          </div>
        </Menu.Items>
      </Transition>
    </Menu>
      
    </div>
  );
}

export default TenantSwitcher;

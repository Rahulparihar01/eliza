/**
 * Auth Store - Zustand
 * Manages authentication state and user context
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Tenant membership for multi-tenant users
export interface TenantMembership {
  customer_id: string;
  customer_name: string;
  is_default: boolean;
  first_login_completed: boolean;
  created_at: string;
}

export interface User {
  id: number;
  email: string;
  first_name?: string;  // Extracted from full_name or username (from backend)
  last_name?: string;   // Legacy field
  full_name?: string;
  username?: string;
  is_active: boolean;
  roles: string[];
  permissions: string[];
  primary_role?: string;
  last_login_at?: string;
  created_at: string;
  customer_id?: string;
  customer_name?: string;  // Display name of the tenant/organization
  allocated_features?: string[];  // Feature keys allocated to user's tenant
  tenant_memberships?: TenantMembership[];  // All tenants user belongs to
  has_multiple_tenants?: boolean;  // Quick flag for UI
}

// Tenant viewing context for platform admins
export interface TenantViewContext {
  tenantId: string;
  tenantName: string;
}

interface AuthState {
  // State
  user: User | null;
  org: string | null;
  space: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Platform Admin Tenant Viewing State
  viewingAsTenant: TenantViewContext | null;  // When viewing as a specific tenant
  crossTenantAccess: boolean;                  // When viewing all tenants for reports
  
  // Multi-tenant UI State
  showLoginBanner: boolean;          // Show "Logged into [Tenant]" banner (every login)
  showWelcomePopup: boolean;         // Show first-time multi-tenant welcome (only once)
  welcomePopupDismissed: boolean;    // Track if user dismissed the welcome popup (persisted)
  
  // Actions
  setUser: (user: User | null) => void;
  setContext: (context: Partial<Pick<AuthState, 'org' | 'space'>>) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  
  // Platform Admin Tenant Viewing Actions
  setViewingAsTenant: (tenant: TenantViewContext | null) => void;
  setCrossTenantAccess: (enabled: boolean) => void;
  clearTenantView: () => void;
  
  // Multi-tenant Actions
  setShowLoginBanner: (show: boolean) => void;
  setShowWelcomePopup: (show: boolean) => void;
  dismissWelcomePopup: () => void;
  
  // Permission helpers
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
  hasRole: (role: string) => boolean;
  isPlatformAdmin: () => boolean;
  
  // Feature allocation helpers
  hasFeature: (featureKey: string) => boolean;
  hasAnyFeature: (featureKeys: string[]) => boolean;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      org: null,
      space: null,
      isAuthenticated: false,
      isLoading: true,
      
      // Platform Admin Tenant Viewing State
      viewingAsTenant: null,
      crossTenantAccess: false,
      
      // Multi-tenant UI State
      showLoginBanner: false,
      showWelcomePopup: false,
      welcomePopupDismissed: false,
      
      // Actions
      setUser: (user) => {
        const currentState = get();
        // Detect fresh login (user was null or different user)
        const isFreshLogin = !currentState.user || (user !== null && currentState.user.id !== user.id);
        const hasMultipleTenants = user?.has_multiple_tenants === true;
        
        set({ 
          user, 
          isAuthenticated: !!user,
          isLoading: false,
          // Show login banner every time user logs in
          showLoginBanner: isFreshLogin && user !== null,
          // Show welcome popup ONLY ONCE for multi-tenant users (check welcomePopupDismissed which is persisted)
          showWelcomePopup: isFreshLogin && user !== null && hasMultipleTenants && !currentState.welcomePopupDismissed
        });
      },
      
      setContext: (context) => set((state) => ({
        ...state,
        ...context
      })),
      
      setLoading: (loading) => set({ isLoading: loading }),
      
      logout: () => set({
        user: null,
        org: null,
        space: null,
        isAuthenticated: false,
        isLoading: false,
        viewingAsTenant: null,
        crossTenantAccess: false,
        showLoginBanner: false,
        showWelcomePopup: false
        // Note: welcomePopupDismissed is NOT reset on logout - it persists across sessions
      }),
      
      // Platform Admin Tenant Viewing Actions
      setViewingAsTenant: (tenant) => set({ 
        viewingAsTenant: tenant,
        // When viewing as a specific tenant, disable cross-tenant access
        crossTenantAccess: false 
      }),
      
      setCrossTenantAccess: (enabled) => set({ 
        crossTenantAccess: enabled,
        // When enabling cross-tenant, clear specific tenant view
        viewingAsTenant: enabled ? null : get().viewingAsTenant
      }),
      
      clearTenantView: () => set({
        viewingAsTenant: null,
        crossTenantAccess: false
      }),
      
      // Multi-tenant Actions
      setShowLoginBanner: (show) => set({ showLoginBanner: show }),
      
      setShowWelcomePopup: (show) => set({ showWelcomePopup: show }),
      
      dismissWelcomePopup: () => set({ 
        showWelcomePopup: false, 
        welcomePopupDismissed: true 
      }),
      
      // Permission helpers
      hasPermission: (permission) => {
        const { user } = get();
        return user?.permissions?.includes(permission) ?? false;
      },
      
      hasAnyPermission: (permissions) => {
        const { user } = get();
        if (!user?.permissions) return false;
        return permissions.some(permission => user.permissions.includes(permission));
      },
      
      hasAllPermissions: (permissions) => {
        const { user } = get();
        if (!user?.permissions) return false;
        return permissions.every(permission => user.permissions.includes(permission));
      },
      
      hasRole: (role) => {
        const { user } = get();
        return user?.roles?.includes(role) ?? false;
      },
      
      isPlatformAdmin: () => {
        const { user } = get();
        return user?.permissions?.includes('platform:admin') ?? false;
      },
      
      // Feature allocation helpers
      hasFeature: (featureKey) => {
        const { user } = get();
        // Platform admins have access to all features
        if (user?.permissions?.includes('platform:admin')) return true;
        return user?.allocated_features?.includes(featureKey) ?? false;
      },
      
      hasAnyFeature: (featureKeys) => {
        const { user } = get();
        // Platform admins have access to all features
        if (user?.permissions?.includes('platform:admin')) return true;
        if (!user?.allocated_features) return false;
        return featureKeys.some(key => user.allocated_features?.includes(key));
      }
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        org: state.org,
        space: state.space,
        isAuthenticated: state.isAuthenticated,
        // Persist welcomePopupDismissed so the popup only shows once ever
        welcomePopupDismissed: state.welcomePopupDismissed,
        // Don't persist tenant viewing state - should reset on page refresh
      })
    }
  )
);

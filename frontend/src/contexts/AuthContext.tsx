/**
 * Authentication Context for AI Enablement Platform
 *
 * Provides authentication state management and RBAC functionality
 * following the Single-Tenant RBAC Specification.
 *
 * Note: This context now wraps the Zustand auth store for backward compatibility
 */

import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import {
  useLoginV1AuthLoginPost,
  useLogoutV1AuthLogoutPost,
  useGetCurrentUserProfileV1AuthMeGet,
  useCreateUserV1AuthUsersPost,
  useChangePasswordV1AuthMePasswordPut,
} from '../generated/authentication/authentication';
import { LoginRequest } from '../generated/models/loginRequest';
import { CreateUserRequest } from '../generated/models/createUserRequest';
import { ChangePasswordRequest } from '../generated/models/changePasswordRequest';
import { queryKeys } from '../lib/query-keys';
import { useAuth as useAuthStore, User } from '../stores/useAuth';
import { useToasts } from '../stores/useToasts';
import { useTheme } from '../stores/useTheme';
import { useQueryClient } from '@tanstack/react-query';

// Auth context interface - now wraps Zustand store
interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  createUser: (userData: CreateUserRequest) => Promise<User>;
  changePassword: (passwordData: ChangePasswordRequest) => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
  hasRole: (role: string) => boolean;
  hasFeature: (featureKey: string) => boolean;
  hasAnyFeature: (featureKeys: string[]) => boolean;
  refreshUser: () => Promise<void>;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Auth provider component
interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const authStore = useAuthStore();
  const { push } = useToasts();
  const queryClient = useQueryClient();
  const loadTheme = useTheme((s) => s.loadTheme);
  const resetTheme = useTheme((s) => s.resetTheme);

  // Get current user with generated hook
  const { refetch: refetchUser } = useGetCurrentUserProfileV1AuthMeGet({
    query: {
      queryKey: queryKeys.auth.currentUser(),
      enabled: !!localStorage.getItem('auth_token'),
      retry: false,
    },
  });

  // Initialize auth state on mount
  useEffect(() => {
    initializeAuth();
  }, []);

  const initializeAuth = async () => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      authStore.setUser(null);
      resetTheme();
      return;
    }

    try {
      authStore.setLoading(true);
      const result = await refetchUser();
      if (result.data) {
        // UserProfile and User are compatible, cast via unknown for type safety
        authStore.setUser(result.data as unknown as User);
      }
    } catch (error: any) {
      authStore.setUser(null);
      push({ kind: 'error', message: error.message || 'Authentication failed' });
    } finally {
      authStore.setLoading(false);
    }
  };

  // Login mutation with generated hook
  const { mutateAsync: loginMutation } = useLoginV1AuthLoginPost();

  const login = async (credentials: LoginRequest) => {
    try {
      authStore.setLoading(true);
      const response = await loginMutation({ data: credentials });
      
      // Store tokens
      localStorage.setItem('auth_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);
      
      authStore.setUser(response.user as unknown as User);
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.currentUser() });
      push({ kind: 'success', message: 'Welcome back!' });
      
      // Load tenant theme after successful login
      resetTheme();
      loadTheme();
    } catch (error: any) {
      authStore.setUser(null);
      authStore.setLoading(false);
      
      // Extract meaningful error message from API response
      let errorMessage = 'Login failed. Please try again.';
      
      // Try to get the error from the API response (check both 'message' and 'detail' fields)
      if (error?.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error?.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          errorMessage = detail.map((d: any) => (typeof d === 'string' ? d : d?.msg || 'Validation error')).join('. ');
        }
      } else if (error?.message) {
        // Fallback to error message if no detail is available
        if (error.message.includes('Network Error') || error.message.includes('Network')) {
          errorMessage = 'Unable to connect to the server. Please check your internet connection.';
        } else if (error.message.includes('timeout')) {
          errorMessage = 'Request timed out. Please try again.';
        } else {
          errorMessage = error.message;
        }
      }
      
      // Don't show toast for login errors - let the form handle it
      // This prevents duplicate error messages
      
      // Create a new error with the extracted message to throw to the component
      const loginError = new Error(errorMessage);
      throw loginError;
    } finally {
      authStore.setLoading(false);
    }
  };

  // Logout mutation with generated hook
  const { mutateAsync: logoutMutation } = useLogoutV1AuthLogoutPost();

  const logout = async () => {
    try {
      await logoutMutation();
    } catch (error) {
      // Ignore logout errors
      console.warn('Logout error:', error);
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      resetTheme();
      authStore.logout();
      queryClient.clear();
      push({ kind: 'info', message: 'Logged out successfully' });
    }
  };

  // Create user mutation with generated hook
  const { mutateAsync: createUserMutation } = useCreateUserV1AuthUsersPost();

  const createUser = async (userData: CreateUserRequest): Promise<User> => {
    try {
      const newUser = await createUserMutation({ data: userData });
      return newUser as unknown as User;
    } catch (error: any) {
      push({ kind: 'error', message: error.message || 'Failed to create user' });
      throw error;
    }
  };

  // Change password mutation with generated hook
  const { mutateAsync: changePasswordMutation } = useChangePasswordV1AuthMePasswordPut();

  const changePassword = async (passwordData: ChangePasswordRequest) => {
    try {
      await changePasswordMutation({ data: passwordData });
      push({ kind: 'success', message: 'Password changed successfully' });
    } catch (error: any) {
      push({ kind: 'error', message: error.message || 'Failed to change password' });
      throw error;
    }
  };

  const refreshUser = async () => {
    try {
      const result = await refetchUser();
      if (result.data) {
        authStore.setUser(result.data as unknown as User);
      }
    } catch (error: any) {
      authStore.setUser(null);
      push({ kind: 'error', message: error.message || 'Failed to refresh user data' });
    }
  };

  // Create context value using Zustand store
  const contextValue: AuthContextType = {
    user: authStore.user,
    isAuthenticated: authStore.isAuthenticated,
    isLoading: authStore.isLoading,
    login,
    logout,
    createUser,
    changePassword,
    hasPermission: authStore.hasPermission,
    hasAnyPermission: authStore.hasAnyPermission,
    hasAllPermissions: authStore.hasAllPermissions,
    hasRole: authStore.hasRole,
    hasFeature: authStore.hasFeature,
    hasAnyFeature: authStore.hasAnyFeature,
    refreshUser,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// Custom hook to use auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// HOC for permission-based rendering
interface WithPermissionProps {
  permission?: string;
  permissions?: string[];
  requireAll?: boolean;
  role?: string;
  fallback?: ReactNode;
  children: ReactNode;
}

export function WithPermission({
  permission,
  permissions = [],
  requireAll = false,
  role,
  fallback = null,
  children,
}: WithPermissionProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions, hasRole, isLoading, user } = useAuth();

  // Wait for auth to load before checking permissions
  // This prevents race conditions where permissions haven't loaded yet
  if (isLoading || !user) {
    return <>{fallback}</>;
  }

  // Check role if specified
  if (role && !hasRole(role)) {
    return <>{fallback}</>;
  }

  // Check single permission
  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>;
  }

  // Check multiple permissions
  if (permissions.length > 0) {
    const hasRequiredPermissions = requireAll
      ? hasAllPermissions(permissions)
      : hasAnyPermission(permissions);

    if (!hasRequiredPermissions) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}

// Hook for permission checking
export function usePermissions() {
  const { hasPermission, hasAnyPermission, hasAllPermissions, hasRole } = useAuth();

  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
  };
}

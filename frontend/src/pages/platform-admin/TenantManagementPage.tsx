/**
 * Tenant Management Page
 * 
 * Platform admin page for managing tenants (customer organizations).
 * Following the spec from MULTI_TENANT_ADMIN_SPECIFICATION.md
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BuildingOffice2Icon,
  PlusIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  CheckIcon,
  UserPlusIcon,
  ClipboardDocumentIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PencilIcon,
  EnvelopeIcon,
  EyeIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';
import { useAuth } from '../../stores/useAuth';

// Design System Components
import {
  // Layout
  Page,
  PageHeader,
  PageBody,
  
  // Form Components
  Button,
  Input,
  Select,
  SelectOption,
  Textarea,
  Label,
  
  // Feedback
  Alert,
  Badge,
  Spinner,
  
  // Modal
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
} from '../../components/ui';

// Simple debounce utility
function debounce<T extends (...args: any[]) => any>(fn: T, ms: number): T {
  let timeoutId: ReturnType<typeof setTimeout>;
  return ((...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), ms);
  }) as T;
}

interface Tenant {
  id: number;
  customer_id: string;
  name: string;
  display_name: string | null;
  contact_email: string | null;
  is_active: boolean;
  subscription_tier: string | null;
  current_users: number;
  max_users: number | null;
  created_at: string;
  updated_at: string;
  // Admin info
  admin_name: string | null;
  admin_email: string | null;
  admin_status: string | null; // 'active', 'pending_invite', 'no_admin'
  // Deactivation info
  deactivated_at: string | null;
  deactivation_reason: string | null;
  deactivated_by_name: string | null;
}

interface TenantWithAdmin extends Tenant {
  admin_invite_url: string | null;
  allocated_features: string[];
}

interface PlatformFeature {
  id: number;
  feature_key: string;
  display_name: string;
  description: string | null;
  category: string | null;
  is_active: boolean;
}

// Features that should be enabled by default for new tenants
// These are essential for tenant admins to manage their organization
const DEFAULT_FEATURE_KEYS = ['users_roles', 'settings', 'invites'];

interface PlatformProvider {
  id: number;
  provider_type: string;
  name: string | null;
  is_enabled: boolean;
  is_healthy: boolean;
  is_global_shared: boolean;
  available_models: string[];
  default_model: string | null;
}

interface CreateTenantForm {
  customer_id: string;
  name: string;
  display_name: string;
  admin_email: string;
  admin_full_name: string;
  subscription_tier: string;
  max_users: number;
  feature_ids: number[];
  shared_provider_ids: number[];
  // Adoption sharing: which existing tenants can this new tenant view?
  adoption_inbound_from: string[];
  // Adoption sharing: which existing tenants can view this new tenant's data?
  adoption_outbound_to: string[];
}

export function TenantManagementPage() {
  const navigate = useNavigate();
  const { 
    setViewingAsTenant, 
    setCrossTenantAccess, 
    crossTenantAccess,
    viewingAsTenant,
    clearTenantView 
  } = useAuth();
  
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [features, setFeatures] = useState<PlatformFeature[]>([]);
  const [platformProviders, setPlatformProviders] = useState<PlatformProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [expandedTenantId, setExpandedTenantId] = useState<string | null>(null);
  const [tenantDetails, setTenantDetails] = useState<TenantWithAdmin | null>(null);
  const [createdInviteUrl, setCreatedInviteUrl] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState(false);
  
  // Handle "View As" tenant - opens app as if logged in as that tenant's admin
  const handleViewAsTenant = (tenant: Tenant) => {
    setViewingAsTenant({
      tenantId: tenant.customer_id,
      tenantName: tenant.display_name || tenant.name,
    });
    // Navigate to dashboard as that tenant
    navigate('/');
  };
  
  // Handle "View All Tenants" - enables cross-tenant access mode
  const handleToggleCrossTenantAccess = () => {
    if (crossTenantAccess) {
      clearTenantView();
    } else {
      setCrossTenantAccess(true);
    }
  };
  
  // Admin modification state
  const [isEditingAdmin, setIsEditingAdmin] = useState(false);
  const [adminForm, setAdminForm] = useState({ email: '', full_name: '' });
  const [savingAdmin, setSavingAdmin] = useState(false);
  const [resendingInvite, setResendingInvite] = useState(false);
  
  // Feature allocation modal state
  const [showFeatureModal, setShowFeatureModal] = useState(false);
  const [featureModalTenant, setFeatureModalTenant] = useState<Tenant | null>(null);
  const [selectedFeatureIds, setSelectedFeatureIds] = useState<Set<number>>(new Set());
  const [savingFeatures, setSavingFeatures] = useState(false);
  
  // Deactivation modal state
  const [showDeactivateModal, setShowDeactivateModal] = useState(false);
  const [deactivateTenant, setDeactivateTenant] = useState<Tenant | null>(null);
  const [deactivateConfirmation, setDeactivateConfirmation] = useState('');
  const [deactivateReason, setDeactivateReason] = useState('');
  const [deactivating, setDeactivating] = useState(false);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);
  
  // Reactivation state
  const [showReactivateModal, setShowReactivateModal] = useState(false);
  const [reactivateTenant, setReactivateTenant] = useState<Tenant | null>(null);
  const [reactivateConfirmation, setReactivateConfirmation] = useState('');
  const [reactivating, setReactivating] = useState(false);
  
  const [createForm, setCreateForm] = useState<CreateTenantForm>({
    customer_id: '',
    name: '',
    display_name: '',
    admin_email: '',
    admin_full_name: '',
    subscription_tier: 'standard',
    max_users: 10,
    feature_ids: [],
    shared_provider_ids: [],
    adoption_inbound_from: [],
    adoption_outbound_to: [],
  });
  const [creating, setCreating] = useState(false);
  
  // Form validation state
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [fieldTouched, setFieldTouched] = useState<Record<string, boolean>>({});
  const [checkingCustomerId, setCheckingCustomerId] = useState(false);
  const [customerIdAvailable, setCustomerIdAvailable] = useState<boolean | null>(null);
  
  // Validation rules
  const CUSTOMER_ID_PATTERN = /^[a-z0-9-]+$/;
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  
  // Validate customer_id format with specific error messages
  const validateCustomerId = (value: string): string | null => {
    if (!value) return 'Customer ID is required';
    if (value.length < 3) return 'Must be at least 3 characters';
    if (value.length > 100) return 'Must be less than 100 characters';
    
    // Check for specific invalid characters and give helpful messages
    if (/[A-Z]/.test(value)) return 'Uppercase letters not allowed - use lowercase only';
    if (/\s/.test(value)) return 'Spaces not allowed - use hyphens instead';
    if (/[^a-z0-9-]/.test(value)) return 'Only lowercase letters (a-z), numbers (0-9), and hyphens (-) allowed';
    if (!CUSTOMER_ID_PATTERN.test(value)) return 'Invalid format';
    
    return null;
  };
  
  // Validate email format
  const validateEmail = (value: string, required: boolean = true): string | null => {
    if (!value && required) return 'Email is required';
    if (!value) return null;
    
    // Trim whitespace for validation
    const trimmed = value.trim();
    if (!trimmed.includes('@')) return 'Email must contain @ symbol';
    if (!EMAIL_PATTERN.test(trimmed)) return 'Invalid email format (e.g., user@example.com)';
    return null;
  };
  
  // Validate name
  const validateName = (value: string, fieldName: string): string | null => {
    if (!value) return `${fieldName} is required`;
    if (value.length > 255) return `${fieldName} must be less than 255 characters`;
    return null;
  };
  
  // Check customer_id uniqueness (debounced)
  const checkCustomerIdUniqueness = useCallback(
    debounce(async (customerId: string) => {
      if (!customerId || validateCustomerId(customerId)) {
        setCustomerIdAvailable(null);
        return;
      }
      
      setCheckingCustomerId(true);
      try {
        // Check if customerId exists in current tenants list
        const exists = tenants.some(t => t.customer_id.toLowerCase() === customerId.toLowerCase());
        setCustomerIdAvailable(!exists);
        if (exists) {
          setFieldErrors(prev => ({ ...prev, customer_id: 'This Customer ID is already taken' }));
        } else {
          setFieldErrors(prev => {
            const newErrors = { ...prev };
            if (newErrors.customer_id === 'This Customer ID is already taken') {
              delete newErrors.customer_id;
            }
            return newErrors;
          });
        }
      } catch (err) {
        console.error('Error checking customer_id:', err);
      } finally {
        setCheckingCustomerId(false);
      }
    }, 500),
    [tenants]
  );
  
  // Handle field blur (mark as touched and validate)
  const handleFieldBlur = (fieldName: string, value: string) => {
    setFieldTouched(prev => ({ ...prev, [fieldName]: true }));
    
    let error: string | null = null;
    switch (fieldName) {
      case 'customer_id':
        error = validateCustomerId(value);
        break;
      case 'name':
        error = validateName(value, 'Organization Name');
        break;
      case 'admin_email':
        error = validateEmail(value, true);
        break;
      case 'admin_full_name':
        error = validateName(value, 'Admin Full Name');
        break;
    }
    
    if (error) {
      setFieldErrors(prev => ({ ...prev, [fieldName]: error! }));
    } else {
      setFieldErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldName];
        return newErrors;
      });
    }
  };
  
  // Handle customer_id change with live validation (no auto-correction - show errors instead)
  const handleCustomerIdChange = (value: string) => {
    // Don't auto-correct - let user see what they typed and show clear errors
    setCreateForm(prev => ({ ...prev, customer_id: value }));
    
    // Validate format immediately if field has been touched or has content
    const formatError = validateCustomerId(value);
    if (formatError) {
      setFieldErrors(prev => ({ ...prev, customer_id: formatError }));
      setCustomerIdAvailable(null);
    } else {
      setFieldErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors.customer_id;
        return newErrors;
      });
      // Check uniqueness with debounce only if format is valid
      checkCustomerIdUniqueness(value);
    }
  };
  
  // Check if form is valid for submission
  const isFormValid = () => {
    const errors: Record<string, string> = {};
    
    const customerIdError = validateCustomerId(createForm.customer_id);
    if (customerIdError) errors.customer_id = customerIdError;
    
    const nameError = validateName(createForm.name, 'Organization Name');
    if (nameError) errors.name = nameError;
    
    const adminEmailError = validateEmail(createForm.admin_email, true);
    if (adminEmailError) errors.admin_email = adminEmailError;
    
    const adminNameError = validateName(createForm.admin_full_name, 'Admin Full Name');
    if (adminNameError) errors.admin_full_name = adminNameError;
    
    if (customerIdAvailable === false) {
      errors.customer_id = 'This Customer ID is already taken';
    }
    
    return Object.keys(errors).length === 0;
  };

  useEffect(() => {
    fetchTenants();
    fetchFeatures();
    fetchPlatformProviders();
  }, []);

  const fetchTenants = async () => {
    try {
      setLoading(true);
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/tenants');
      setTenants(response.data.tenants);
      setError(null);
    } catch (err: any) {
      console.error('Error fetching tenants:', err);
      setError(err.response?.data?.detail || 'Failed to load tenants');
    } finally {
      setLoading(false);
    }
  };

  const fetchFeatures = async () => {
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/features');
      setFeatures(response.data);
    } catch (err: any) {
      console.error('Error fetching features:', err);
    }
  };

  const fetchPlatformProviders = async () => {
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/platform-admin/ai-providers');
      // Filter to only show non-global providers (global ones are auto-shared)
      const providers = response.data.providers || [];
      setPlatformProviders(providers.filter((p: PlatformProvider) => !p.is_global_shared));
    } catch (err: any) {
      console.error('Error fetching platform providers:', err);
    }
  };

  const fetchTenantDetails = async (customerId: string) => {
    try {
      const response = await AXIOS_INSTANCE.get(`/api/v1/platform-admin/tenants/${customerId}`);
      setTenantDetails(response.data);
    } catch (err: any) {
      console.error('Error fetching tenant details:', err);
    }
  };

  const handleToggleExpand = (customerId: string) => {
    if (expandedTenantId === customerId) {
      setExpandedTenantId(null);
      setTenantDetails(null);
      setIsEditingAdmin(false);
    } else {
      setExpandedTenantId(customerId);
      fetchTenantDetails(customerId);
      setIsEditingAdmin(false);
    }
  };

  const handleStartEditAdmin = (tenant: Tenant) => {
    setAdminForm({
      email: tenant.admin_email || '',
      full_name: tenant.admin_name || '',
    });
    setIsEditingAdmin(true);
  };

  const handleCancelEditAdmin = () => {
    setIsEditingAdmin(false);
    setAdminForm({ email: '', full_name: '' });
  };

  const handleSaveAdmin = async (customerId: string) => {
    if (!adminForm.email) {
      setError('Admin email is required');
      return;
    }
    
    setSavingAdmin(true);
    setError(null);
    
    try {
      await AXIOS_INSTANCE.post(`/api/v1/platform-admin/tenants/${customerId}/admin`, {
        admin_email: adminForm.email,
        admin_name: adminForm.full_name || null,
      });
      
      // Refresh tenants and details
      await fetchTenants();
      await fetchTenantDetails(customerId);
      setIsEditingAdmin(false);
    } catch (err: any) {
      console.error('Error updating admin:', err);
      setError(err.response?.data?.detail || 'Failed to update tenant admin');
    } finally {
      setSavingAdmin(false);
    }
  };

  const handleResendInvite = async (customerId: string) => {
    setResendingInvite(true);
    setError(null);
    
    try {
      const response = await AXIOS_INSTANCE.post(`/api/v1/platform-admin/tenants/${customerId}/resend-invite`);
      setCreatedInviteUrl(response.data.invite_url);
      
      // Refresh tenant details
      await fetchTenantDetails(customerId);
    } catch (err: any) {
      console.error('Error resending invite:', err);
      setError(err.response?.data?.detail || 'Failed to resend admin invite');
    } finally {
      setResendingInvite(false);
    }
  };

  // Deactivation handlers
  const handleOpenDeactivateModal = (tenant: Tenant) => {
    setDeactivateTenant(tenant);
    setDeactivateConfirmation('');
    setDeactivateReason('');
    setDeactivateError(null);
    setShowDeactivateModal(true);
  };

  const handleCloseDeactivateModal = () => {
    setShowDeactivateModal(false);
    setDeactivateTenant(null);
    setDeactivateConfirmation('');
    setDeactivateReason('');
    setDeactivateError(null);
  };

  const handleDeactivateTenant = async () => {
    if (!deactivateTenant) return;
    if (deactivateConfirmation !== 'DEACTIVATE') {
      setDeactivateError('Please type DEACTIVATE to confirm');
      return;
    }
    if (deactivateReason.length < 10) {
      setDeactivateError('Please provide a reason (at least 10 characters)');
      return;
    }

    setDeactivating(true);
    setDeactivateError(null);

    try {
      await AXIOS_INSTANCE.post(`/api/v1/platform-admin/tenants/${deactivateTenant.customer_id}/deactivate`, {
        confirmation: deactivateConfirmation,
        reason: deactivateReason,
      });
      
      // Refresh tenants list
      await fetchTenants();
      handleCloseDeactivateModal();
    } catch (err: any) {
      console.error('Error deactivating tenant:', err);
      setDeactivateError(err.response?.data?.detail || 'Failed to deactivate tenant');
    } finally {
      setDeactivating(false);
    }
  };

  // Reactivation handlers
  const handleOpenReactivateModal = (tenant: Tenant) => {
    setReactivateTenant(tenant);
    setReactivateConfirmation('');
    setShowReactivateModal(true);
  };

  const handleCloseReactivateModal = () => {
    setShowReactivateModal(false);
    setReactivateTenant(null);
    setReactivateConfirmation('');
  };

  const handleReactivateTenant = async () => {
    if (!reactivateTenant) return;
    if (reactivateConfirmation !== 'REACTIVATE') {
      setError('Please type REACTIVATE to confirm');
      return;
    }

    setReactivating(true);
    setError(null);

    try {
      await AXIOS_INSTANCE.post(`/api/v1/platform-admin/tenants/${reactivateTenant.customer_id}/reactivate`, {
        confirmation: reactivateConfirmation,
      });
      
      // Refresh tenants list
      await fetchTenants();
      handleCloseReactivateModal();
    } catch (err: any) {
      console.error('Error reactivating tenant:', err);
      setError(err.response?.data?.detail || 'Failed to reactivate tenant');
    } finally {
      setReactivating(false);
    }
  };

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Mark all fields as touched to show any validation errors
    setFieldTouched({
      customer_id: true,
      name: true,
      admin_email: true,
      admin_full_name: true,
    });
    
    // Validate all required fields
    const errors: Record<string, string> = {};
    
    const customerIdError = validateCustomerId(createForm.customer_id);
    if (customerIdError) errors.customer_id = customerIdError;
    else if (customerIdAvailable === false) errors.customer_id = 'This Customer ID is already taken';
    
    const nameError = validateName(createForm.name, 'Organization Name');
    if (nameError) errors.name = nameError;
    
    const adminEmailError = validateEmail(createForm.admin_email, true);
    if (adminEmailError) errors.admin_email = adminEmailError;
    
    const adminNameError = validateName(createForm.admin_full_name, 'Admin Full Name');
    if (adminNameError) errors.admin_full_name = adminNameError;
    
    // If there are validation errors, show them and don't submit
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setModalError('Please fix the validation errors above');
      return;
    }
    
    setCreating(true);
    setModalError(null);
    
    try {
      // Create the tenant - map frontend fields to backend schema
      const { shared_provider_ids, admin_full_name, max_users, ...restForm } = createForm;
      const tenantData = {
        ...restForm,
        admin_name: admin_full_name, // Backend expects admin_name, not admin_full_name
      };
      const response = await AXIOS_INSTANCE.post('/api/v1/platform-admin/tenants', tenantData);
      const newTenant = response.data;
      setTenants(prev => [...prev, newTenant]);
      setCreatedInviteUrl(newTenant.admin_invite_url);
      
      // Share selected providers with the new tenant
      if (shared_provider_ids.length > 0) {
        for (const providerId of shared_provider_ids) {
          try {
            await AXIOS_INSTANCE.put(`/api/v1/platform-admin/ai-providers/${providerId}/sharing`, {
              share_with_tenant_ids: [newTenant.customer_id],
            });
          } catch (err) {
            console.error(`Error sharing provider ${providerId}:`, err);
            // Don't fail the whole operation if one provider share fails
          }
        }
      }
      
      // Create adoption data sharing grants
      // Inbound: source tenant → this new tenant (new tenant can VIEW source tenant's data)
      for (const sourceCustomerId of createForm.adoption_inbound_from) {
        try {
          await AXIOS_INSTANCE.post('/api/v1/platform-admin/adoption/grants', {
            source_customer_id: sourceCustomerId,
            target_customer_id: newTenant.customer_id,
            share_level: 'read',
            notes: `Auto-created during tenant creation`,
          });
        } catch (err) {
          console.error(`Error creating inbound adoption grant from ${sourceCustomerId}:`, err);
        }
      }
      
      // Outbound: this new tenant → target tenants (target tenants can VIEW new tenant's data)
      for (const targetCustomerId of createForm.adoption_outbound_to) {
        try {
          await AXIOS_INSTANCE.post('/api/v1/platform-admin/adoption/grants', {
            source_customer_id: newTenant.customer_id,
            target_customer_id: targetCustomerId,
            share_level: 'read',
            notes: `Auto-created during tenant creation`,
          });
        } catch (err) {
          console.error(`Error creating outbound adoption grant to ${targetCustomerId}:`, err);
        }
      }
      
      setShowCreateModal(false);
      setModalError(null);
      setCreateForm({
        customer_id: '',
        name: '',
        display_name: '',
        admin_email: '',
        admin_full_name: '',
        subscription_tier: 'standard',
        max_users: 10,
        feature_ids: [],
        shared_provider_ids: [],
        adoption_inbound_from: [],
        adoption_outbound_to: [],
      });
    } catch (err: any) {
      console.error('Error creating tenant:', err);
      // Parse error message for better user feedback
      let errorMessage = 'Failed to create tenant';
      const detail = err.response?.data?.detail;
      if (detail) {
        // Handle Pydantic validation errors (array of {type, loc, msg, input, ctx})
        if (Array.isArray(detail)) {
          errorMessage = detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (typeof detail === 'object' && detail.msg) {
          errorMessage = detail.msg;
        } else {
          errorMessage = JSON.stringify(detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      // Add hint for common issues
      if (errorMessage.includes('Network Error') || errorMessage.includes('CORS')) {
        errorMessage = 'Network error: Unable to connect to the server. Please ensure the backend is running.';
      }
      setModalError(errorMessage);
    } finally {
      setCreating(false);
    }
  };

  // Get the IDs for default features that should be pre-selected
  const getDefaultFeatureIds = useCallback(() => {
    return features
      .filter(f => DEFAULT_FEATURE_KEYS.includes(f.feature_key))
      .map(f => f.id);
  }, [features]);

  const handleOpenCreateModal = () => {
    // Pre-select default features for new tenant
    const defaultIds = getDefaultFeatureIds();
    setCreateForm({
      customer_id: '',
      name: '',
      display_name: '',
      admin_email: '',
      admin_full_name: '',
      subscription_tier: 'standard',
      max_users: 10,
      feature_ids: defaultIds,
      shared_provider_ids: [],
      adoption_inbound_from: [],
      adoption_outbound_to: [],
    });
    setShowCreateModal(true);
  };

  const handleCloseCreateModal = () => {
    setShowCreateModal(false);
    setModalError(null);
    // Reset validation state
    setFieldErrors({});
    setFieldTouched({});
    setCustomerIdAvailable(null);
    setCreateForm({
      customer_id: '',
      name: '',
      display_name: '',
      admin_email: '',
      admin_full_name: '',
      subscription_tier: 'standard',
      max_users: 10,
      feature_ids: [],
      shared_provider_ids: [],
      adoption_inbound_from: [],
      adoption_outbound_to: [],
    });
  };

  const handleToggleFeature = (featureId: number) => {
    setCreateForm(prev => ({
      ...prev,
      feature_ids: prev.feature_ids.includes(featureId)
        ? prev.feature_ids.filter(id => id !== featureId)
        : [...prev.feature_ids, featureId]
    }));
  };

  const handleToggleProvider = (providerId: number) => {
    setCreateForm(prev => ({
      ...prev,
      shared_provider_ids: prev.shared_provider_ids.includes(providerId)
        ? prev.shared_provider_ids.filter(id => id !== providerId)
        : [...prev.shared_provider_ids, providerId]
    }));
  };

  const copyInviteUrl = () => {
    if (createdInviteUrl) {
      navigator.clipboard.writeText(createdInviteUrl);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    }
  };

  const handleOpenFeatureModal = async (tenant: Tenant) => {
    setFeatureModalTenant(tenant);
    setShowFeatureModal(true);
    
    // Fetch current allocations and set selected features
    try {
      const response = await AXIOS_INSTANCE.get(`/api/v1/platform-admin/tenants/${tenant.customer_id}/features`);
      const enabledIds = new Set<number>(
        response.data.filter((a: any) => a.is_enabled).map((a: any) => a.feature_id)
      );
      setSelectedFeatureIds(enabledIds);
    } catch (err) {
      console.error('Error fetching tenant features:', err);
      setSelectedFeatureIds(new Set());
    }
  };

  const handleCloseFeatureModal = () => {
    setShowFeatureModal(false);
    setFeatureModalTenant(null);
    setSelectedFeatureIds(new Set());
  };

  const handleToggleFeatureInModal = (featureId: number) => {
    setSelectedFeatureIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(featureId)) {
        newSet.delete(featureId);
      } else {
        newSet.add(featureId);
      }
      return newSet;
    });
  };

  const handleSaveFeatures = async () => {
    if (!featureModalTenant) return;
    
    setSavingFeatures(true);
    setError(null);
    
    try {
      await AXIOS_INSTANCE.put(`/api/v1/platform-admin/tenants/${featureModalTenant.customer_id}/features`, {
        feature_ids: Array.from(selectedFeatureIds)
      });
      
      // Refresh tenant details if expanded
      if (expandedTenantId === featureModalTenant.customer_id) {
        await fetchTenantDetails(featureModalTenant.customer_id);
      }
      
      handleCloseFeatureModal();
    } catch (err: any) {
      console.error('Error saving features:', err);
      setError(err.response?.data?.detail || 'Failed to save feature allocations');
    } finally {
      setSavingFeatures(false);
    }
  };

  const filteredTenants = tenants.filter(tenant =>
    tenant.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tenant.customer_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (tenant.contact_email?.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Header actions
  const headerActions = (
    <>
      {/* Cross-Tenant Access Toggle */}
      <Button
        variant={crossTenantAccess ? 'default' : 'outline'}
        onClick={handleToggleCrossTenantAccess}
        className={crossTenantAccess ? 'bg-violet-600 hover:bg-violet-700 text-white' : ''}
      >
        <GlobeAltIcon className="w-5 h-5" />
        {crossTenantAccess ? 'Exit Cross-Tenant Mode' : 'View All Tenants'}
      </Button>
      
      <Button onClick={handleOpenCreateModal}>
        <PlusIcon className="w-5 h-5" />
        Create Tenant
      </Button>
    </>
  );

  if (loading) {
    return (
      <Page maxWidth="xl">
        <PageHeader
          title="Tenant Management"
          description="Create and manage customer organizations"
          actions={headerActions}
        />
        <PageBody>
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
        title="Tenant Management"
        description="Create and manage customer organizations"
        actions={headerActions}
      />
      <PageBody>
      
      {/* Cross-Tenant Mode Info */}
      {crossTenantAccess && (
        <Alert variant="info" className="mb-4" hideIcon>
          <div className="flex gap-3">
            <GlobeAltIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <strong>Cross-Tenant Access Mode is active.</strong> You can now view data from all tenants 
              in reports and dashboards. This mode is for compliance reporting and debugging only.
            </div>
          </div>
        </Alert>
      )}

      {/* Error display */}
      {error && (
        <Alert variant="error" className="mb-6">
          {error}
        </Alert>
      )}

      {/* Invite URL Success Banner */}
      {createdInviteUrl && (
        <Alert variant="success" className="mb-6" onDismiss={() => setCreatedInviteUrl(null)}>
          <div>
            <p className="font-medium">Tenant created successfully!</p>
            <p className="opacity-80 mt-1">Share this invite URL with the tenant admin:</p>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 px-3 py-2 bg-white/20 dark:bg-black/20 rounded text-sm font-mono truncate">
              {createdInviteUrl}
            </code>
            <Button size="sm" onClick={copyInviteUrl}>
              {copiedUrl ? <CheckIcon className="w-4 h-4" /> : <ClipboardDocumentIcon className="w-4 h-4" />}
              {copiedUrl ? 'Copied!' : 'Copy'}
            </Button>
          </div>
        </Alert>
      )}

      {/* Search */}
      <div className="mb-4">
        <div className="relative max-w-sm">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 dark:text-gray-500 z-10" />
          <Input
            type="text"
            placeholder="Search tenants..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Tenants List */}
      <div className="bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
              <th className="w-8 px-2 py-2.5"></th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Tenant</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Customer ID</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Admin</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Contact</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider text-center">Users</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-dark-border">
            {filteredTenants.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
                  {searchQuery ? 'No tenants match your search' : 'No tenants yet. Create your first tenant!'}
                </td>
              </tr>
            ) : (
              filteredTenants.map((tenant) => (
                <React.Fragment key={tenant.id}>
                  <tr 
                    className={`hover:bg-gray-50 dark:hover:bg-dark-surface-2/50 transition-colors cursor-pointer ${
                      expandedTenantId === tenant.customer_id ? 'bg-white dark:bg-dark-surface/30' : ''
                    }`}
                    onClick={() => handleToggleExpand(tenant.customer_id)}
                  >
                    <td className="px-2 py-3">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleExpand(tenant.customer_id);
                        }}
                      >
                        {expandedTenantId === tenant.customer_id ? (
                          <ChevronUpIcon className="w-4 h-4" />
                        ) : (
                          <ChevronDownIcon className="w-4 h-4" />
                        )}
                      </Button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-eliza-red/10 rounded-lg flex items-center justify-center flex-shrink-0">
                          <BuildingOffice2Icon className="w-4 h-4 text-eliza-red" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-medium text-charcoal dark:text-gray-100 text-sm truncate">{tenant.name}</div>
                          {tenant.display_name && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{tenant.display_name}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <code className="px-1.5 py-0.5 bg-gray-50 dark:bg-dark-surface-2 rounded text-xs text-charcoal dark:text-gray-100">{tenant.customer_id}</code>
                    </td>
                    <td className="px-4 py-3">
                      {tenant.admin_email ? (
                        <div>
                          <div className="text-charcoal dark:text-gray-100 text-sm">{tenant.admin_name || 'Admin'}</div>
                          <div className="text-gray-500 dark:text-gray-400 text-xs">{tenant.admin_email}</div>
                          {tenant.admin_status === 'pending_invite' && (
                            <Badge variant="warning" className="mt-0.5">
                              <UserPlusIcon className="w-3 h-3" />
                              Pending
                            </Badge>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-500 dark:text-gray-400 text-sm">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-charcoal dark:text-gray-100 text-sm">
                      {tenant.contact_email || <span className="text-gray-500 dark:text-gray-400">—</span>}
                    </td>
                    <td className="px-4 py-3 text-charcoal dark:text-gray-100 text-sm text-center">
                      {tenant.current_users}
                    </td>
                    <td className="px-4 py-3">
                      {tenant.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <div>
                          <Badge variant="danger">Deactivated</Badge>
                          {tenant.deactivated_at && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              {new Date(tenant.deactivated_at).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewAsTenant(tenant);
                        }}
                        className={viewingAsTenant?.tenantId === tenant.customer_id
                          ? 'bg-amber-500 text-amber-950 hover:bg-amber-600'
                          : 'text-amber-600 bg-amber-500/10 hover:bg-amber-500/20'
                        }
                        title={`View application as ${tenant.name} admin`}
                      >
                        <EyeIcon className="w-3.5 h-3.5" />
                        {viewingAsTenant?.tenantId === tenant.customer_id ? 'Viewing' : 'View As'}
                      </Button>
                    </td>
                  </tr>
                  
                  {/* Expanded Row - Tenant Details */}
                  {expandedTenantId === tenant.customer_id && (
                    <tr className="bg-white dark:bg-dark-surface/20">
                      <td colSpan={8} className="px-6 py-4">
                        <div className="grid grid-cols-3 gap-6">
                          {/* Tenant Info */}
                          <div className="space-y-4">
                            <h4 className="text-sm font-medium text-charcoal dark:text-gray-100">Tenant Information</h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-gray-500 dark:text-gray-400">Customer ID</span>
                                <code className="text-charcoal dark:text-gray-100">{tenant.customer_id}</code>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-500 dark:text-gray-400">Created</span>
                                <span className="text-charcoal dark:text-gray-100">{new Date(tenant.created_at).toLocaleDateString()}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-500 dark:text-gray-400">Subscription</span>
                                <span className="text-charcoal dark:text-gray-100 capitalize">{tenant.subscription_tier || 'standard'}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-500 dark:text-gray-400">Max Users</span>
                                <span className="text-charcoal dark:text-gray-100">{tenant.max_users || 'Unlimited'}</span>
                              </div>
                            </div>
                          </div>
                          
                          {/* Admin Management */}
                          <div className="space-y-4">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-medium text-charcoal dark:text-gray-100">Tenant Admin</h4>
                              {!isEditingAdmin && (
                                <Button
                                  variant="link"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleStartEditAdmin(tenant);
                                  }}
                                  className="text-xs h-auto p-0"
                                >
                                  <PencilIcon className="w-3 h-3" />
                                  Edit
                                </Button>
                              )}
                            </div>
                            
                            {isEditingAdmin ? (
                              <div className="space-y-3" onClick={(e) => e.stopPropagation()}>
                                <div>
                                  <Label className="text-xs mb-1">Admin Email *</Label>
                                  <Input
                                    type="email"
                                    value={adminForm.email}
                                    onChange={(e) => setAdminForm(prev => ({ ...prev, email: e.target.value }))}
                                    placeholder="admin@company.com"
                                  />
                                </div>
                                <div>
                                  <Label className="text-xs mb-1">Admin Name</Label>
                                  <Input
                                    type="text"
                                    value={adminForm.full_name}
                                    onChange={(e) => setAdminForm(prev => ({ ...prev, full_name: e.target.value }))}
                                    placeholder="John Doe"
                                  />
                                </div>
                                <div className="flex items-center gap-2 pt-1">
                                  <Button
                                    size="sm"
                                    onClick={() => handleSaveAdmin(tenant.customer_id)}
                                    disabled={savingAdmin}
                                  >
                                    {savingAdmin && <Spinner size="sm" className="mr-1" />}
                                    {savingAdmin ? 'Saving...' : 'Save & Send Invite'}
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={handleCancelEditAdmin}
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-2 text-sm">
                                {tenant.admin_email ? (
                                  <>
                                    <div className="flex justify-between">
                                      <span className="text-gray-500 dark:text-gray-400">Name</span>
                                      <span className="text-charcoal dark:text-gray-100">{tenant.admin_name || '—'}</span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-gray-500 dark:text-gray-400">Email</span>
                                      <span className="text-charcoal dark:text-gray-100">{tenant.admin_email}</span>
                                    </div>
                                    <div className="flex justify-between items-center">
                                      <span className="text-gray-500 dark:text-gray-400">Status</span>
                                      {tenant.admin_status === 'active' ? (
                                        <Badge variant="success">
                                          <CheckIcon className="w-3 h-3" />
                                          Active
                                        </Badge>
                                      ) : (
                                        <Badge variant="warning">
                                          <UserPlusIcon className="w-3 h-3" />
                                          Invite Pending
                                        </Badge>
                                      )}
                                    </div>
                                    {tenant.admin_status === 'pending_invite' && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="mt-2 w-full"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleResendInvite(tenant.customer_id);
                                        }}
                                        disabled={resendingInvite}
                                      >
                                        {resendingInvite ? <Spinner size="sm" className="mr-1" /> : <EnvelopeIcon className="w-3 h-3" />}
                                        {resendingInvite ? 'Sending...' : 'Resend Invite'}
                                      </Button>
                                    )}
                                  </>
                                ) : (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleStartEditAdmin(tenant);
                                    }}
                                    className="w-full text-center py-4 rounded-lg border border-dashed border-gray-200 dark:border-dark-border hover:border-eliza-red dark:hover:border-eliza-red/50 hover:bg-eliza-red/5 transition-colors cursor-pointer"
                                  >
                                    <UserPlusIcon className="w-8 h-8 mx-auto mb-2 text-gray-500 dark:text-gray-400" />
                                    <p className="text-gray-500 dark:text-gray-400 text-sm">No admin assigned</p>
                                    <p className="mt-1 text-eliza-red text-xs">Click to add admin</p>
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                          
                          {/* Features */}
                          <div className="space-y-4">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-medium text-charcoal dark:text-gray-100">Allocated Features</h4>
                              <Button
                                variant="link"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenFeatureModal(tenant);
                                }}
                                className="text-xs h-auto p-0"
                              >
                                <PencilIcon className="w-3 h-3" />
                                Edit
                              </Button>
                            </div>
                            {tenantDetails?.allocated_features && tenantDetails.allocated_features.length > 0 ? (
                              <div className="flex flex-wrap gap-2">
                                {tenantDetails.allocated_features.map((feature) => (
                                  <span
                                    key={feature}
                                    className="inline-flex items-center px-2.5 py-1 bg-gray-50 dark:bg-dark-surface-2 text-charcoal dark:text-gray-100 border border-gray-200 dark:border-dark-border rounded-full text-xs font-medium"
                                  >
                                    {feature.replace(/_/g, ' ')}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenFeatureModal(tenant);
                                }}
                                className="w-full text-center py-4 rounded-lg border border-dashed border-gray-200 dark:border-dark-border hover:border-eliza-red dark:hover:border-eliza-red/50 hover:bg-eliza-red/5 transition-colors cursor-pointer"
                              >
                                <PlusIcon className="w-8 h-8 mx-auto mb-2 text-gray-500 dark:text-gray-400" />
                                <p className="text-gray-500 dark:text-gray-400 text-sm">No features allocated</p>
                                <p className="mt-1 text-eliza-red text-xs">Click to allocate features</p>
                              </button>
                            )}
                          </div>
                        </div>
                        
                        {/* Danger Zone - Full Width */}
                        <div className="col-span-3 pt-4 mt-4 border-t border-gray-200 dark:border-dark-border">
                          <div className="flex items-center justify-between">
                            <div>
                              <h4 className="text-sm font-medium text-charcoal dark:text-gray-100">Tenant Status</h4>
                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                {tenant.is_active 
                                  ? 'This tenant is currently active. Deactivating will prevent all users from accessing the platform.' 
                                  : `Deactivated on ${tenant.deactivated_at ? new Date(tenant.deactivated_at).toLocaleDateString() : 'Unknown'}`
                                }
                              </p>
                              {!tenant.is_active && tenant.deactivation_reason && (
                                <p className="text-xs text-red-500 mt-1">
                                  Reason: {tenant.deactivation_reason}
                                </p>
                              )}
                              {!tenant.is_active && tenant.deactivated_by_name && (
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                  Deactivated by: {tenant.deactivated_by_name}
                                </p>
                              )}
                            </div>
                            {tenant.is_active ? (
                              <Button
                                variant="outline"
                                className="text-red-600 border-red-300 hover:bg-red-50 dark:hover:bg-red-900/20"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenDeactivateModal(tenant);
                                }}
                              >
                                Deactivate Tenant
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                className="text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-900/20"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenReactivateModal(tenant);
                                }}
                              >
                                Reactivate Tenant
                              </Button>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Deactivate Tenant Modal */}
      <Modal open={showDeactivateModal && !!deactivateTenant} onClose={handleCloseDeactivateModal}>
        <ModalBackdrop />
        <ModalContent size="md">
          <ModalHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                <XMarkIcon className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <ModalTitle>Deactivate Tenant</ModalTitle>
                <p className="text-sm text-gray-500 dark:text-gray-400">{deactivateTenant?.display_name || deactivateTenant?.name}</p>
              </div>
            </div>
          </ModalHeader>
          <ModalBody>
            <Alert variant="warning" className="mb-4">
              <strong>Warning:</strong> Deactivating this tenant will immediately prevent all users from accessing the platform. This action is logged and can be reversed.
            </Alert>
            
            {deactivateError && (
              <Alert variant="error" className="mb-4">
                {deactivateError}
              </Alert>
            )}
            
            <div className="space-y-4">
              <div>
                <Label className="mb-1">Reason for Deactivation *</Label>
                <Textarea
                  value={deactivateReason}
                  onChange={(e) => setDeactivateReason(e.target.value)}
                  rows={3}
                  placeholder="Please provide a reason for deactivating this tenant..."
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{deactivateReason.length}/10 characters minimum</p>
              </div>
              
              <div>
                <Label className="mb-1">Type DEACTIVATE to confirm *</Label>
                <Input
                  type="text"
                  value={deactivateConfirmation}
                  onChange={(e) => setDeactivateConfirmation(e.target.value)}
                  placeholder="DEACTIVATE"
                />
              </div>
            </div>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="outline"
              className="flex-1"
              onClick={handleCloseDeactivateModal}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              className="flex-1"
              onClick={handleDeactivateTenant}
              disabled={deactivating || deactivateConfirmation !== 'DEACTIVATE' || deactivateReason.length < 10}
            >
              {deactivating && <Spinner size="sm" className="mr-2" />}
              {deactivating ? 'Deactivating...' : 'Deactivate Tenant'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Reactivate Tenant Modal */}
      <Modal open={showReactivateModal && !!reactivateTenant} onClose={handleCloseReactivateModal}>
        <ModalBackdrop />
        <ModalContent size="md">
          <ModalHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                <CheckIcon className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <ModalTitle>Reactivate Tenant</ModalTitle>
                <p className="text-sm text-gray-500 dark:text-gray-400">{reactivateTenant?.display_name || reactivateTenant?.name}</p>
              </div>
            </div>
          </ModalHeader>
          <ModalBody>
            <Alert variant="success" className="mb-4">
              Reactivating this tenant will restore access for all users. They will be able to log in and use the platform immediately.
            </Alert>
            
            {reactivateTenant?.deactivation_reason && (
              <div className="bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 mb-4 text-sm">
                <p className="text-gray-500 dark:text-gray-400">Previous deactivation reason:</p>
                <p className="text-charcoal dark:text-gray-100 mt-1">{reactivateTenant.deactivation_reason}</p>
              </div>
            )}
            
            <div>
              <Label className="mb-1">Type REACTIVATE to confirm *</Label>
              <Input
                type="text"
                value={reactivateConfirmation}
                onChange={(e) => setReactivateConfirmation(e.target.value)}
                placeholder="REACTIVATE"
              />
            </div>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="outline"
              className="flex-1"
              onClick={handleCloseReactivateModal}
            >
              Cancel
            </Button>
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700 text-white"
              onClick={handleReactivateTenant}
              disabled={reactivating || reactivateConfirmation !== 'REACTIVATE'}
            >
              {reactivating && <Spinner size="sm" className="mr-2" />}
              {reactivating ? 'Reactivating...' : 'Reactivate Tenant'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create Tenant Modal */}
      <Modal open={showCreateModal} onClose={handleCloseCreateModal}>
        <ModalBackdrop />
        <ModalContent size="lg" className="max-h-[90vh] overflow-hidden flex flex-col">
          <ModalHeader>
            <ModalTitle>Create New Tenant</ModalTitle>
            {modalError && (
              <Alert variant="error" className="mt-4">
                <div>
                  <p className="font-medium">Unable to create tenant</p>
                  <p className="mt-0.5 opacity-80 text-xs">{modalError}</p>
                </div>
              </Alert>
            )}
          </ModalHeader>
          <ModalBody className="overflow-y-auto">
            <form id="create-tenant-form" onSubmit={handleCreateTenant} className="space-y-6">

              {/* Organization Details */}
              <div>
                <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4">Organization Details</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className={fieldErrors.customer_id ? 'text-red-500 font-medium' : ''}>Customer ID *</Label>
                    <div className="relative mt-1">
                      <Input
                        type="text"
                        required
                        value={createForm.customer_id}
                        onChange={(e) => handleCustomerIdChange(e.target.value)}
                        onBlur={() => handleFieldBlur('customer_id', createForm.customer_id)}
                        placeholder="acme-corp"
                        className={`pr-10 ${
                          fieldErrors.customer_id
                            ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                            : customerIdAvailable === true && createForm.customer_id
                            ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                            : ''
                        }`}
                      />
                      {/* Status indicator */}
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        {checkingCustomerId && (
                          <Spinner size="sm" />
                        )}
                        {!checkingCustomerId && customerIdAvailable === true && createForm.customer_id && !fieldErrors.customer_id && (
                          <CheckIcon className="w-5 h-5 text-green-500" />
                        )}
                        {!checkingCustomerId && (customerIdAvailable === false || fieldErrors.customer_id) && (
                          <XMarkIcon className="w-5 h-5 text-red-500" />
                        )}
                      </div>
                    </div>
                    {fieldErrors.customer_id ? (
                      <p className="text-xs text-red-500 font-medium mt-1">{fieldErrors.customer_id}</p>
                    ) : customerIdAvailable === true && createForm.customer_id ? (
                      <p className="text-xs text-success mt-1">✓ Customer ID is available</p>
                    ) : (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Use lowercase letters, numbers, and hyphens only (e.g., acme-corp)</p>
                    )}
                  </div>
                  <div>
                    <Label className={fieldErrors.name && fieldTouched.name ? 'text-red-500 font-medium' : ''}>Organization Name *</Label>
                    <Input
                      type="text"
                      required
                      value={createForm.name}
                      onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                      onBlur={() => handleFieldBlur('name', createForm.name)}
                      placeholder="Acme Corporation"
                      className={`mt-1 ${
                        fieldErrors.name && fieldTouched.name
                          ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                          : ''
                      }`}
                    />
                    {fieldErrors.name && fieldTouched.name && (
                      <p className="text-xs text-red-500 font-medium mt-1">{fieldErrors.name}</p>
                    )}
                  </div>
                  <div>
                    <Label className="mb-1">Display Name</Label>
                    <Input
                      type="text"
                      value={createForm.display_name}
                      onChange={(e) => setCreateForm(prev => ({ ...prev, display_name: e.target.value }))}
                      placeholder="Acme Corp"
                    />
                  </div>
                </div>
              </div>

              {/* Admin Details */}
              <div>
                <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4 flex items-center gap-2">
                  <UserPlusIcon className="w-4 h-4" />
                  Tenant Admin
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className={fieldErrors.admin_email && fieldTouched.admin_email ? 'text-red-500 font-medium' : ''}>Admin Email *</Label>
                    <Input
                      type="email"
                      required
                      value={createForm.admin_email}
                      onChange={(e) => setCreateForm(prev => ({ ...prev, admin_email: e.target.value }))}
                      onBlur={() => handleFieldBlur('admin_email', createForm.admin_email)}
                      placeholder="admin@acme.com"
                      className={`mt-1 ${
                        fieldErrors.admin_email && fieldTouched.admin_email
                          ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                          : ''
                      }`}
                    />
                    {fieldErrors.admin_email && fieldTouched.admin_email && (
                      <p className="text-xs text-red-500 font-medium mt-1">{fieldErrors.admin_email}</p>
                    )}
                  </div>
                  <div>
                    <Label className={fieldErrors.admin_full_name && fieldTouched.admin_full_name ? 'text-red-500 font-medium' : ''}>Admin Full Name *</Label>
                    <Input
                      type="text"
                      required
                      value={createForm.admin_full_name}
                      onChange={(e) => setCreateForm(prev => ({ ...prev, admin_full_name: e.target.value }))}
                      onBlur={() => handleFieldBlur('admin_full_name', createForm.admin_full_name)}
                      placeholder="John Smith"
                      className={`mt-1 ${
                        fieldErrors.admin_full_name && fieldTouched.admin_full_name
                          ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                          : ''
                      }`}
                    />
                    {fieldErrors.admin_full_name && fieldTouched.admin_full_name && (
                      <p className="text-xs text-red-500 font-medium mt-1">{fieldErrors.admin_full_name}</p>
                    )}
                  </div>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">An invite link will be generated for the admin to set up their account.</p>
              </div>

              {/* Subscription */}
              <div>
                <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4">Subscription</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="mb-1">Tier</Label>
                    <Select
                      value={createForm.subscription_tier}
                      onValueChange={(value) => setCreateForm(prev => ({ ...prev, subscription_tier: value }))}
                    >
                      <SelectOption value="starter">Starter</SelectOption>
                      <SelectOption value="standard">Standard</SelectOption>
                      <SelectOption value="professional">Professional</SelectOption>
                      <SelectOption value="enterprise">Enterprise</SelectOption>
                    </Select>
                  </div>
                  <div>
                    <Label className="mb-1">Max Users</Label>
                    <Input
                      type="number"
                      min={1}
                      value={createForm.max_users}
                      onChange={(e) => setCreateForm(prev => ({ ...prev, max_users: parseInt(e.target.value) || 10 }))}
                    />
                  </div>
                </div>
              </div>

              {/* Features */}
              <div>
                <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4">Allocated Features</h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Select which features this tenant will have access to.</p>
                <div className="flex flex-wrap gap-2">
                  {features.map((feature) => {
                    const isSelected = createForm.feature_ids.includes(feature.id);
                    return (
                      <button
                        key={feature.id}
                        type="button"
                        onClick={() => handleToggleFeature(feature.id)}
                        className={`
                          px-3 py-1.5 rounded-full text-sm flex items-center gap-2 transition-colors border-2
                          ${isSelected
                            ? 'bg-eliza-red/10 text-eliza-red border-eliza-red'
                            : 'bg-gray-50 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:border-eliza-red dark:hover:border-eliza-red/50'
                          }
                        `}
                      >
                        {isSelected ? (
                          <XMarkIcon className="w-4 h-4" />
                        ) : (
                          <PlusIcon className="w-4 h-4" />
                        )}
                        {feature.display_name}
                      </button>
                    );
                  })}
                </div>
                {createForm.feature_ids.length === 0 && (
                  <p className="text-xs text-warning mt-2">No features selected. The tenant won't have access to any features.</p>
                )}
              </div>

              {/* AI Providers */}
              {platformProviders.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4">Share AI Providers</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Select AI providers from your organization to share with this tenant. Global providers are automatically shared.</p>
                  <div className="flex flex-wrap gap-2">
                    {platformProviders.map((provider) => {
                      const isSelected = createForm.shared_provider_ids.includes(provider.id);
                      return (
                        <button
                          key={provider.id}
                          type="button"
                          onClick={() => handleToggleProvider(provider.id)}
                          className={`
                            px-3 py-1.5 rounded-full text-sm flex items-center gap-2 transition-colors border-2
                            ${isSelected
                              ? 'bg-eliza-red/10 text-eliza-red border-eliza-red'
                              : 'bg-gray-50 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:border-eliza-red/50'
                            }
                          `}
                        >
                          {isSelected ? (
                            <XMarkIcon className="w-4 h-4" />
                          ) : (
                            <PlusIcon className="w-4 h-4" />
                          )}
                          {provider.name || provider.provider_type}
                          <span className="text-xs opacity-60">({provider.provider_type})</span>
                        </button>
                      );
                    })}
                  </div>
                  {createForm.shared_provider_ids.length > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">{createForm.shared_provider_ids.length} provider(s) will be shared with this tenant.</p>
                  )}
                </div>
              )}

              {/* Adoption Data Sharing */}
              {tenants.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-charcoal dark:text-gray-100 mb-4">Adoption Data Sharing</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Configure which tenants can view each other's AI adoption metrics.</p>
                  
                  {/* Inbound: This tenant can view data FROM these tenants */}
                  <div className="mb-4">
                    <Label className="text-xs font-medium mb-2 block">
                      This tenant can VIEW adoption data from:
                    </Label>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Select existing tenants whose adoption metrics this new tenant should be able to view.</p>
                    <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface">
                      {tenants.filter(t => t.is_active).map((tenant) => {
                        const isSelected = createForm.adoption_inbound_from.includes(tenant.customer_id);
                        return (
                          <button
                            key={tenant.customer_id}
                            type="button"
                            onClick={() => {
                              setCreateForm(prev => ({
                                ...prev,
                                adoption_inbound_from: isSelected
                                  ? prev.adoption_inbound_from.filter(id => id !== tenant.customer_id)
                                  : [...prev.adoption_inbound_from, tenant.customer_id]
                              }));
                            }}
                            className={`
                              px-3 py-1.5 rounded-full text-xs flex items-center gap-2 transition-colors border
                              ${isSelected
                                ? 'bg-eliza-red/10 text-eliza-red border-eliza-red'
                                : 'bg-white dark:bg-dark-surface text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:border-eliza-red dark:hover:border-eliza-red/50'
                              }
                            `}
                          >
                            {isSelected ? (
                              <CheckIcon className="w-3 h-3" />
                            ) : (
                              <PlusIcon className="w-3 h-3" />
                            )}
                            {tenant.display_name || tenant.name}
                          </button>
                        );
                      })}
                    </div>
                    {createForm.adoption_inbound_from.length > 0 && (
                      <p className="text-xs text-eliza-red mt-2">
                        ← This tenant can view data from {createForm.adoption_inbound_from.length} tenant(s)
                      </p>
                    )}
                  </div>
                  
                  {/* Outbound: These tenants can view data FROM this tenant */}
                  <div>
                    <Label className="text-xs font-medium mb-2 block">
                      These tenants can VIEW this tenant's adoption data:
                    </Label>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Select existing tenants that should be able to view this new tenant's adoption metrics.</p>
                    <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface">
                      {tenants.filter(t => t.is_active).map((tenant) => {
                        const isSelected = createForm.adoption_outbound_to.includes(tenant.customer_id);
                        return (
                          <button
                            key={tenant.customer_id}
                            type="button"
                            onClick={() => {
                              setCreateForm(prev => ({
                                ...prev,
                                adoption_outbound_to: isSelected
                                  ? prev.adoption_outbound_to.filter(id => id !== tenant.customer_id)
                                  : [...prev.adoption_outbound_to, tenant.customer_id]
                              }));
                            }}
                            className={`
                              px-3 py-1.5 rounded-full text-xs flex items-center gap-2 transition-colors border
                              ${isSelected
                                ? 'bg-info/10 text-info border-info'
                                : 'bg-white dark:bg-dark-surface text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:border-info/50'
                              }
                            `}
                          >
                            {isSelected ? (
                              <CheckIcon className="w-3 h-3" />
                            ) : (
                              <PlusIcon className="w-3 h-3" />
                            )}
                            {tenant.display_name || tenant.name}
                          </button>
                        );
                      })}
                    </div>
                    {createForm.adoption_outbound_to.length > 0 && (
                      <p className="text-xs text-info mt-2">
                        → {createForm.adoption_outbound_to.length} tenant(s) can view this tenant's data
                      </p>
                    )}
                  </div>
                  
                  {/* Summary */}
                  {(createForm.adoption_inbound_from.length > 0 || createForm.adoption_outbound_to.length > 0) && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                      {createForm.adoption_inbound_from.length + createForm.adoption_outbound_to.length} adoption grant(s) will be created. All grants are <span className="text-eliza-red font-medium">Read Only</span>.
                    </p>
                  )}
                </div>
              )}

            </form>
          </ModalBody>
          <ModalFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={handleCloseCreateModal}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="create-tenant-form"
              disabled={creating}
            >
              {creating ? (
                <>
                  <Spinner size="sm" className="text-on-brand" />
                  Creating...
                </>
              ) : (
                <>
                  <PlusIcon className="w-4 h-4" />
                  Create Tenant
                </>
              )}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Feature Allocation Modal */}
      <Modal open={showFeatureModal && !!featureModalTenant} onClose={handleCloseFeatureModal}>
        <ModalBackdrop />
        <ModalContent size="lg" className="max-h-[80vh] overflow-hidden flex flex-col">
          <ModalHeader>
            <ModalTitle>Allocate Features</ModalTitle>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {featureModalTenant?.name} ({featureModalTenant?.customer_id})
            </p>
          </ModalHeader>
          <ModalBody className="overflow-y-auto">
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              Select the features this tenant should have access to. Click a feature to toggle it on/off.
            </p>
            
            {/* Group features by category */}
            {Object.entries(
              features.reduce((acc, feature) => {
                const category = feature.category || 'other';
                if (!acc[category]) acc[category] = [];
                acc[category].push(feature);
                return acc;
              }, {} as Record<string, PlatformFeature[]>)
            ).map(([category, categoryFeatures]) => (
              <div key={category} className="mb-6">
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
                  {category === 'data' && 'Data & Documents'}
                  {category === 'config' && 'Configuration'}
                  {category === 'intelligence' && 'AI Intelligence'}
                  {category === 'admin' && 'Administration'}
                  {!['data', 'config', 'intelligence', 'admin'].includes(category) && category}
                </h4>
                <div className="flex flex-wrap gap-2">
                  {categoryFeatures.map((feature) => {
                    const isSelected = selectedFeatureIds.has(feature.id);
                    return (
                      <button
                        key={feature.id}
                        type="button"
                        onClick={() => handleToggleFeatureInModal(feature.id)}
                        className={`
                          px-3 py-1.5 rounded-full text-sm flex items-center gap-2 transition-all border-2
                          ${isSelected
                            ? 'bg-eliza-red/10 text-eliza-red border-eliza-red hover:bg-eliza-red/20'
                            : 'bg-gray-50 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-dark-border hover:border-eliza-red dark:hover:border-eliza-red/50 hover:text-charcoal dark:hover:text-gray-100'
                          }
                        `}
                      >
                        {isSelected ? (
                          <XMarkIcon className="w-4 h-4" />
                        ) : (
                          <PlusIcon className="w-4 h-4" />
                        )}
                        {feature.display_name}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            
            {selectedFeatureIds.size === 0 && (
              <p className="text-xs text-warning mt-2">No features selected. The tenant won't have access to any features.</p>
            )}
          </ModalBody>
          <ModalFooter className="justify-between">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {selectedFeatureIds.size} feature{selectedFeatureIds.size !== 1 ? 's' : ''} selected
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                onClick={handleCloseFeatureModal}
              >
                Cancel
              </Button>
              <Button
                onClick={handleSaveFeatures}
                disabled={savingFeatures}
              >
                {savingFeatures ? (
                  <>
                    <Spinner size="sm" className="text-white" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckIcon className="w-4 h-4" />
                    Save Changes
                  </>
                )}
              </Button>
            </div>
          </ModalFooter>
        </ModalContent>
      </Modal>

      </PageBody>
    </Page>
  );
}

export default TenantManagementPage;


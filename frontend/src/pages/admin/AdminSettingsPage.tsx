/**
 * AI Providers Page
 * Allows tenant admins to configure AI model providers for their organization
 */

import React, { useState } from 'react';
import { Layout } from '../../components/layout/Layout';
import {
  CheckIcon,
  CheckCircleIcon,
  XMarkIcon,
  CpuChipIcon,
  PlusIcon,
  TrashIcon,
  BoltIcon,
  ExclamationTriangleIcon,
  CloudIcon,
  ShareIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettingsApi } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';

// Design System Components
import {
  Button,
  Input,
  Select,
  SelectOption,
  Switch,
  Badge,
  Label,
  Alert,
  Spinner,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  Checkbox,
  Page,
  PageHeader,
  PageBody,
  DataTable,
  DataTableActions,
  DataTableActionButton,
} from '../../components/ui';
import type { Column } from '../../components/ui';

export default function AdminSettingsPage() {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  // Provider configuration state
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [selectedProviderType, setSelectedProviderType] = useState<string>('');
  const [providerFormData, setProviderFormData] = useState<any>({
    name: '',
    api_key: '',
    organization_id: '',
    base_url: '',
    aws_region: 'us-west-2',
    aws_access_key_id: '',
    aws_secret_access_key: '',
    aws_session_token: '',
    auth_method: 'api_keys',
    available_models: [],
    default_model: '',
    // Adoption settings (OpenAI only)
    enable_adoption: false,
    chatgpt_workspace_id: '',
  });
  const [testingProvider, setTestingProvider] = useState<number | null>(null);
  const [expandedProviderIds, setExpandedProviderIds] = useState<Set<string | number>>(new Set());
  const [showAdoptionWarningModal, setShowAdoptionWarningModal] = useState(false);
  const [pendingAdoptionConfig, setPendingAdoptionConfig] = useState<{ configId: number; workspaceId?: string } | null>(null);
  
  // Multi-step provider form state
  const [fetchingModels, setFetchingModels] = useState(false);
  const [availableModelsFromAPI, setAvailableModelsFromAPI] = useState<any[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [modelsFetched, setModelsFetched] = useState(false);
  
  // Compliance API test state (for new provider creation)
  const [testingCompliance, setTestingCompliance] = useState(false);
  const [complianceTestResult, setComplianceTestResult] = useState<{
    success: boolean;
    message: string;
    error_code?: string;
    instructions?: string;
  } | null>(null);
  
  // Compliance API test state for existing providers (keyed by config id)
  const [testingComplianceForProvider, setTestingComplianceForProvider] = useState<number | null>(null);
  const [providerComplianceStatus, setProviderComplianceStatus] = useState<Record<number, {
    success: boolean;
    message: string;
    error_code?: string;
    instructions?: string;
    tested_at: Date;
  }>>({});

  // Fetch available provider types
  const { data: availableProvidersData } = useQuery({
    queryKey: ['providers', 'available'],
    queryFn: async () => {
      const response = await getSettingsApi().get('/v1/providers/available');
      return response.data;
    },
  });

  // Fetch all provider configurations (including shared from platform)
  const { data: providerConfigsData, isLoading: providersLoading } = useQuery({
    queryKey: ['providers', 'configurations-with-shared'],
    queryFn: async () => {
      const response = await getSettingsApi().get('/v1/providers/configurations/with-shared');
      return response.data;
    },
  });

  // Mutation to create provider configuration
  const createProviderConfig = useMutation({
    mutationFn: async (data: any) => {
      const response = await getSettingsApi().post('/v1/providers/configurations', data);
      return response.data;
    },
    onSuccess: async (createdProvider: any) => {
      try {
        // If user validated compliance access before save and enabled adoption,
        // persist that status on the newly created provider record.
        const shouldPersistComplianceStatus =
          selectedProviderType === 'openai' &&
          providerFormData.enable_adoption &&
          complianceTestResult?.success === true &&
          createdProvider?.id;

        if (shouldPersistComplianceStatus) {
          await getSettingsApi().post(`/v1/providers/configurations/${createdProvider.id}/test-compliance`);
        }
      } catch (error) {
        console.error('Failed to persist compliance status after create:', error);
      } finally {
        queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
        addToast({
          kind: 'success',
          message: 'Provider configuration created successfully',
        });
        setShowProviderForm(false);
        resetProviderForm();
      }
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to create provider configuration',
      });
    },
  });

  // Mutation to test provider connection
  const testProviderConnection = useMutation({
    mutationFn: async (configId: number) => {
      const response = await getSettingsApi().post(`/v1/providers/configurations/${configId}/test`);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
      if (data.success) {
        addToast({
          kind: 'success',
          message: `Connection test successful! Response time: ${data.response_time_ms?.toFixed(0)}ms`,
        });
      } else {
        addToast({
          kind: 'error',
          message: `Connection test failed: ${data.error_details}`,
        });
      }
      setTestingProvider(null);
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to test connection',
      });
      setTestingProvider(null);
    },
  });

  // Mutation to toggle provider enabled status (for own providers)
  const toggleProviderEnabled = useMutation({
    mutationFn: async ({ configId, isEnabled }: { configId: number; isEnabled: boolean }) => {
      const response = await getSettingsApi().put(`/v1/providers/configurations/${configId}`, {
        is_enabled: isEnabled,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
      addToast({
        kind: 'success',
        message: 'Provider status updated successfully',
      });
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to update provider status',
      });
    },
  });

  // Mutation to toggle shared provider enabled status
  const toggleSharedProviderEnabled = useMutation({
    mutationFn: async ({ configId, isEnabled }: { configId: number; isEnabled: boolean }) => {
      const response = await getSettingsApi().put(`/v1/providers/shared/${configId}/toggle?is_enabled=${isEnabled}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
      addToast({
        kind: 'success',
        message: 'Shared provider status updated successfully',
      });
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to update shared provider status',
      });
    },
  });

  // Mutation to delete provider configuration
  const deleteProviderConfig = useMutation({
    mutationFn: async (configId: number) => {
      await getSettingsApi().delete(`/v1/providers/configurations/${configId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
      addToast({
        kind: 'success',
        message: 'Provider configuration deleted successfully',
      });
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to delete provider configuration',
      });
    },
  });

  // Mutation to update adoption settings
  const updateAdoptionSettings = useMutation({
    mutationFn: async ({ configId, data }: { configId: number; data: { is_adoption_source: boolean; chatgpt_workspace_id?: string } }) => {
      const response = await getSettingsApi().put(`/v1/providers/configurations/${configId}/adoption`, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
      addToast({
        kind: 'success',
        message: 'Adoption settings updated successfully',
      });
    },
    onError: (error: any) => {
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to update adoption settings',
      });
    },
  });

  // Handler for enabling adoption - checks if another key is already enabled
  const handleEnableAdoption = (configId: number, currentlyEnabled: boolean, workspaceId?: string) => {
    if (currentlyEnabled) {
      // Disabling - just do it directly
      updateAdoptionSettings.mutate({
        configId,
        data: { is_adoption_source: false, chatgpt_workspace_id: workspaceId }
      });
      return;
    }

    // Enabling - check if another OpenAI key already has adoption enabled
    const existingAdoptionKey = providerConfigs.find(
      (p: any) => p.provider_type === 'openai' && p.is_adoption_source && p.id !== configId
    );

    if (existingAdoptionKey) {
      // Show warning modal
      setPendingAdoptionConfig({ configId, workspaceId });
      setShowAdoptionWarningModal(true);
    } else {
      // No conflict, enable directly
      updateAdoptionSettings.mutate({
        configId,
        data: { is_adoption_source: true, chatgpt_workspace_id: workspaceId }
      });
    }
  };

  const handleConfirmAdoptionSwitch = () => {
    if (pendingAdoptionConfig) {
      updateAdoptionSettings.mutate({
        configId: pendingAdoptionConfig.configId,
        data: { is_adoption_source: true, chatgpt_workspace_id: pendingAdoptionConfig.workspaceId }
      });
    }
    setShowAdoptionWarningModal(false);
    setPendingAdoptionConfig(null);
  };

  const handleCancelAdoptionSwitch = () => {
    setShowAdoptionWarningModal(false);
    setPendingAdoptionConfig(null);
  };

  // Fallback to hardcoded providers if API doesn't return them
  const defaultProviders = [
    {
      type: 'openai',
      name: 'OpenAI',
      description: 'GPT-4, GPT-3.5 Turbo and other OpenAI models',
    },
    {
      type: 'anthropic',
      name: 'Anthropic',
      description: 'Claude 3 Opus, Sonnet, and Haiku models',
    },
    {
      type: 'groq',
      name: 'Groq',
      description: 'Fast inference with Llama and Mixtral models',
    },
    {
      type: 'bedrock',
      name: 'AWS Bedrock',
      description: 'Access foundation models via AWS Bedrock',
    },
  ];
  
  const availableProviders = availableProvidersData?.available_providers || defaultProviders;
  const providerConfigs = providerConfigsData?.providers || [];

  // Helper functions
  const resetProviderForm = () => {
    setProviderFormData({
      name: '',
      api_key: '',
      organization_id: '',
      base_url: '',
      aws_region: 'us-west-2',
      aws_access_key_id: '',
      aws_secret_access_key: '',
      aws_session_token: '',
      auth_method: 'api_keys',
      available_models: [],
      default_model: '',
      enable_adoption: false,
      chatgpt_workspace_id: '',
    });
    setSelectedProviderType('');
    setAvailableModelsFromAPI([]);
    setSelectedModels([]);
    setModelsFetched(false);
    setComplianceTestResult(null);
    setTestingCompliance(false);
  };
  
  const handleFetchModels = async () => {
    setFetchingModels(true);
    try {
      const payload: any = {
        provider_type: selectedProviderType,
      };
      
      // Add credentials based on provider type
      if (selectedProviderType === 'bedrock') {
        payload.aws_region = providerFormData.aws_region;
        payload.aws_access_key_id = providerFormData.aws_access_key_id;
        payload.aws_secret_access_key = providerFormData.aws_secret_access_key;
        if (providerFormData.aws_session_token) {
          payload.aws_session_token = providerFormData.aws_session_token;
        }
      } else {
        if (!providerFormData.api_key) {
          addToast({
            kind: 'error',
            message: 'Please enter your API key first',
          });
          setFetchingModels(false);
          return;
        }
        payload.api_key = providerFormData.api_key;
        if (providerFormData.organization_id) {
          payload.organization_id = providerFormData.organization_id;
        }
      }
      
      const response = await getSettingsApi().post('/v1/providers/fetch-models', payload);
      
      if (response.data.success) {
        setAvailableModelsFromAPI(response.data.models);
        setModelsFetched(true);
        addToast({
          kind: 'success',
          message: `Found ${response.data.models.length} available models`,
        });
      } else {
        addToast({
          kind: 'error',
          message: response.data.error_message || 'Failed to fetch models',
        });
      }
    } catch (error: any) {
      console.error('Error fetching models:', error);
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to fetch available models',
      });
    } finally {
      setFetchingModels(false);
    }
  };

  const getProviderIcon = (providerType: string) => {
    switch (providerType) {
      case 'openai':
        return <CpuChipIcon className="h-5 w-5" />;
      case 'anthropic':
        return <BoltIcon className="h-5 w-5" />;
      case 'groq':
        return <BoltIcon className="h-5 w-5" />;
      case 'bedrock':
        return <CloudIcon className="h-5 w-5" />;
      default:
        return <CpuChipIcon className="h-5 w-5" />;
    }
  };

  const getProviderColor = (_providerType: string) => {
    // Design System: Use monochromatic icons for consistency
    // All provider icons use the same neutral styling
    return 'text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2';
  };

  const handleProviderTypeSelect = (providerType: string) => {
    setSelectedProviderType(providerType);
    setProviderFormData({
      ...providerFormData,
      available_models: [],
      default_model: '',
    });
    setShowProviderForm(true);
    // Reset compliance test state when changing provider
    setComplianceTestResult(null);
  };

  // Test Compliance API access (for new provider creation form)
  const handleTestComplianceApi = async () => {
    if (!providerFormData.api_key || !providerFormData.chatgpt_workspace_id) {
      addToast({
        kind: 'error',
        message: 'Please enter both API key and Workspace ID to test compliance access',
      });
      return;
    }

    setTestingCompliance(true);
    setComplianceTestResult(null);

    try {
      const response = await getSettingsApi().post('/v1/providers/test-compliance-api', {
        api_key: providerFormData.api_key,
        workspace_id: providerFormData.chatgpt_workspace_id,
      });
      setComplianceTestResult(response.data);
    } catch (error: any) {
      setComplianceTestResult({
        success: false,
        message: error.response?.data?.message || 'Failed to test compliance API',
        error_code: 'REQUEST_FAILED',
        instructions: 'Could not reach the server. Please try again.',
      });
    } finally {
      setTestingCompliance(false);
    }
  };

  // Test Compliance API access for an existing saved provider
  const handleTestComplianceForProvider = async (configId: number) => {
    setTestingComplianceForProvider(configId);

    try {
      const response = await getSettingsApi().post(`/v1/providers/configurations/${configId}/test-compliance`);
      setProviderComplianceStatus(prev => ({
        ...prev,
        [configId]: {
          ...response.data,
          tested_at: new Date(),
        }
      }));
      // Invalidate the provider list cache to update the badge in the table
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
    } catch (error: any) {
      setProviderComplianceStatus(prev => ({
        ...prev,
        [configId]: {
          success: false,
          message: error.response?.data?.message || 'Failed to test compliance API',
          error_code: 'REQUEST_FAILED',
          instructions: 'Could not reach the server. Please try again.',
          tested_at: new Date(),
        }
      }));
      // Still invalidate on error since the status is saved to DB
      queryClient.invalidateQueries({ queryKey: ['providers', 'configurations-with-shared'] });
    } finally {
      setTestingComplianceForProvider(null);
    }
  };

  const handleProviderFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate that models have been fetched and selected
    if (!modelsFetched) {
      addToast({
        kind: 'error',
        message: 'Please fetch available models first',
      });
      return;
    }
    
    if (selectedModels.length === 0) {
      addToast({
        kind: 'error',
        message: 'Please select at least one model',
      });
      return;
    }
    
    if (!providerFormData.default_model) {
      addToast({
        kind: 'error',
        message: 'Please select a default model',
      });
      return;
    }
    
    // Build config based on provider type
    let config: any = {};
    
    if (selectedProviderType === 'bedrock') {
      config = {
        auth_method: providerFormData.auth_method,
        aws_region: providerFormData.aws_region,
        available_models: selectedModels,
        default_model: providerFormData.default_model,
      };
      if (providerFormData.auth_method === 'api_keys') {
        config.aws_access_key_id = providerFormData.aws_access_key_id;
        config.aws_secret_access_key = providerFormData.aws_secret_access_key;
        if (providerFormData.aws_session_token) {
          config.aws_session_token = providerFormData.aws_session_token;
        }
      }
    } else {
      config = {
        api_key: providerFormData.api_key,
        available_models: selectedModels,
        default_model: providerFormData.default_model,
      };
      if (providerFormData.organization_id) {
        config.organization_id = providerFormData.organization_id;
      }
      if (providerFormData.base_url) {
        config.base_url = providerFormData.base_url;
      }
    }
    
    const createPayload: any = {
      provider_type: selectedProviderType,
      name: providerFormData.name || `${selectedProviderType.toUpperCase()} Configuration`,
      is_enabled: true,
      config,
    };
    
    // Include adoption settings for OpenAI providers
    if (selectedProviderType === 'openai' && providerFormData.enable_adoption) {
      createPayload.is_adoption_source = true;
      if (providerFormData.chatgpt_workspace_id) {
        createPayload.chatgpt_workspace_id = providerFormData.chatgpt_workspace_id;
      }
    }
    
    createProviderConfig.mutate(createPayload);
  };

  const handleTestConnection = (configId: number) => {
    setTestingProvider(configId);
    testProviderConnection.mutate(configId);
  };

  const handleDeleteConfig = (configId: number, providerName: string) => {
    if (window.confirm(`Are you sure you want to delete this ${providerName} configuration? This action cannot be undone.`)) {
      deleteProviderConfig.mutate(configId);
    }
  };

  if (providersLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <Spinner size="lg" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">Loading settings...</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <Page maxWidth="xl">
        <PageHeader
          title="AI Providers"
          description="Configure your own API keys for OpenAI, Anthropic, Groq, and AWS Bedrock"
          actions={
            !showProviderForm && (
              <Button onClick={() => setShowProviderForm(true)}>
                <PlusIcon className="h-4 w-4 mr-2" />
                Add Provider
              </Button>
            )
          }
        />

        <PageBody>
            {/* AI Model Provider Configuration */}
            <div>
              <div>
                {/* Add Provider Form */}
                {showProviderForm && (
                  <div className="mb-6 bg-white dark:bg-dark-surface rounded-lg p-6 border border-gray-200 dark:border-dark-border shadow-md">
                    {!selectedProviderType ? (
                      <div>
                        <div className="flex items-center justify-between mb-6">
                          <div>
                            <h3 className="text-lg font-semibold text-charcoal dark:text-gray-100">Select Provider Type</h3>
                            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Choose an AI model provider to configure</p>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowProviderForm(false)}
                            title="Cancel"
                          >
                            <XMarkIcon className="h-5 w-5" />
                          </Button>
                        </div>
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                          {availableProviders.map((provider: any) => (
                            <button
                              key={provider.type}
                              onClick={() => handleProviderTypeSelect(provider.type)}
                              className="p-5 bg-gray-50 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border rounded-lg text-left hover:border-eliza-red hover:shadow-md transition-all duration-200 group"
                            >
                              <div className="flex items-center mb-3">
                                <div className={`p-2 rounded-md ${getProviderColor(provider.type)}`}>
                                  {getProviderIcon(provider.type)}
                                </div>
                                <span className="ml-3 font-bold text-charcoal dark:text-gray-100 text-base transition-colors">
                                  {provider.name}
                                </span>
                              </div>
                              <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">{provider.description}</p>
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <form onSubmit={handleProviderFormSubmit}>
                        <div className="flex items-center justify-between mb-6">
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-md ${getProviderColor(selectedProviderType)}`}>
                              {getProviderIcon(selectedProviderType)}
                            </div>
                            <div>
                              <h3 className="text-lg font-semibold text-charcoal dark:text-gray-100">
                                Configure {selectedProviderType.toUpperCase()}
                              </h3>
                              <p className="text-sm text-gray-500 dark:text-gray-400">Enter your API credentials below</p>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setShowProviderForm(false);
                              resetProviderForm();
                            }}
                            title="Cancel"
                          >
                            <XMarkIcon className="h-5 w-5" />
                          </Button>
                        </div>

                        <div className="space-y-4">
                          {/* Common Fields */}
                          <div className="space-y-1.5">
                            <Label htmlFor="config-name">Configuration Name (Optional)</Label>
                            <Input
                              id="config-name"
                              type="text"
                              value={providerFormData.name}
                              onChange={(e) => setProviderFormData({ ...providerFormData, name: e.target.value })}
                              placeholder={`My ${selectedProviderType.toUpperCase()} Configuration`}
                            />
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              A friendly name to identify this configuration. If not provided, a default name will be used.
                            </p>
                          </div>

                          {/* Bedrock-specific fields */}
                          {selectedProviderType === 'bedrock' ? (
                            <>
                              <div className="space-y-1.5">
                                <Label>Authentication Method</Label>
                                <Select
                                  value={providerFormData.auth_method}
                                  onValueChange={(value) => setProviderFormData({ ...providerFormData, auth_method: value })}
                                >
                                  <SelectOption value="api_keys">API Keys</SelectOption>
                                  <SelectOption value="iam_role">IAM Role</SelectOption>
                                </Select>
                              </div>

                              <div className="space-y-1.5">
                                <Label>AWS Region *</Label>
                                <Select
                                  value={providerFormData.aws_region}
                                  onValueChange={(value) => setProviderFormData({ ...providerFormData, aws_region: value })}
                                >
                                  <SelectOption value="us-east-1">US East (N. Virginia)</SelectOption>
                                  <SelectOption value="us-west-2">US West (Oregon)</SelectOption>
                                  <SelectOption value="ap-southeast-1">Asia Pacific (Singapore)</SelectOption>
                                  <SelectOption value="ap-northeast-1">Asia Pacific (Tokyo)</SelectOption>
                                  <SelectOption value="eu-central-1">Europe (Frankfurt)</SelectOption>
                                  <SelectOption value="eu-west-1">Europe (Ireland)</SelectOption>
                                </Select>
                              </div>

                              {providerFormData.auth_method === 'api_keys' && (
                                <>
                                  <div className="space-y-1.5">
                                    <Label htmlFor="aws-access-key">AWS Access Key ID *</Label>
                                    <Input
                                      id="aws-access-key"
                                      type="password"
                                      value={providerFormData.aws_access_key_id}
                                      onChange={(e) => setProviderFormData({ ...providerFormData, aws_access_key_id: e.target.value })}
                                      placeholder="AKIA..."
                                      required
                                      autoComplete="off"
                                    />
                                  </div>

                                  <div className="space-y-1.5">
                                    <Label htmlFor="aws-secret-key">AWS Secret Access Key *</Label>
                                    <Input
                                      id="aws-secret-key"
                                      type="password"
                                      value={providerFormData.aws_secret_access_key}
                                      onChange={(e) => setProviderFormData({ ...providerFormData, aws_secret_access_key: e.target.value })}
                                      placeholder="wJalr..."
                                      required
                                      autoComplete="off"
                                    />
                                  </div>

                                  <div className="space-y-1.5">
                                    <Label htmlFor="aws-session-token">AWS Session Token (Optional)</Label>
                                    <Input
                                      id="aws-session-token"
                                      type="password"
                                      value={providerFormData.aws_session_token}
                                      onChange={(e) => setProviderFormData({ ...providerFormData, aws_session_token: e.target.value })}
                                      placeholder="For temporary credentials"
                                      autoComplete="off"
                                    />
                                  </div>
                                </>
                              )}

                              {/* Fetch Models Button for Bedrock */}
                              <div className="border-t border-gray-200 dark:border-dark-border pt-4 mt-4">
                                <div className="flex items-center justify-between mb-4">
                                  <div>
                                    <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100">Step 2: Fetch Available Models</h4>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                      Retrieve the list of models available for your AWS credentials
                                    </p>
                                  </div>
                                  <Button
                                    type="button"
                                    onClick={handleFetchModels}
                                    disabled={fetchingModels || modelsFetched}
                                  >
                                    {fetchingModels ? (
                                      <>
                                        <Spinner size="sm" className="mr-2" />
                                        Fetching...
                                      </>
                                    ) : modelsFetched ? (
                                      <>
                                        <CheckIcon className="h-4 w-4 mr-2" />
                                        Models Loaded
                                      </>
                                    ) : (
                                      'Fetch Models'
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </>
                          ) : (
                            <>
                              {/* OpenAI/Anthropic/Groq fields */}
                              <div className="space-y-1.5">
                                <Label htmlFor="api-key">API Key *</Label>
                                <Input
                                  id="api-key"
                                  type="password"
                                  value={providerFormData.api_key}
                                  onChange={(e) => setProviderFormData({ ...providerFormData, api_key: e.target.value })}
                                  placeholder={selectedProviderType === 'openai' ? 'sk-...' : selectedProviderType === 'anthropic' ? 'sk-ant-...' : 'gsk_...'}
                                  required
                                  autoComplete="off"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  {selectedProviderType === 'openai' && (
                                    <>
                                      Get your API key from{' '}
                                      <a 
                                        href="https://platform.openai.com/settings/organization/api-keys" 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="text-eliza-red hover:underline"
                                      >
                                        OpenAI Platform
                                      </a>
                                    </>
                                  )}
                                  {selectedProviderType === 'anthropic' && (
                                    <>
                                      Get your API key from{' '}
                                      <a 
                                        href="https://console.anthropic.com/settings/keys" 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="text-eliza-red hover:underline"
                                      >
                                        Anthropic Console
                                      </a>
                                    </>
                                  )}
                                  {selectedProviderType === 'groq' && (
                                    <>
                                      Get your API key from{' '}
                                      <a 
                                        href="https://console.groq.com/keys" 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="text-eliza-red hover:underline"
                                      >
                                        Groq Console
                                      </a>
                                    </>
                                  )}
                                </p>
                              </div>

                              {selectedProviderType === 'openai' && (
                                <div className="space-y-1.5">
                                  <Label htmlFor="org-id">Organization ID (Optional)</Label>
                                  <Input
                                    id="org-id"
                                    type="text"
                                    value={providerFormData.organization_id}
                                    onChange={(e) => setProviderFormData({ ...providerFormData, organization_id: e.target.value })}
                                    placeholder="org-..."
                                  />
                                  <p className="text-xs text-gray-500 dark:text-gray-400">
                                    For users who belong to multiple organizations, specify which organization is used for API requests.
                                  </p>
                                </div>
                              )}

                              {/* Fetch Models Button */}
                              <div className="border-t border-gray-200 dark:border-dark-border pt-4 mt-4">
                                <div className="flex items-center justify-between mb-4">
                                  <div>
                                    <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100">Step 2: Fetch Available Models</h4>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                      Retrieve the list of models available for your API credentials
                                    </p>
                                  </div>
                                  <Button
                                    type="button"
                                    onClick={handleFetchModels}
                                    disabled={fetchingModels || modelsFetched}
                                  >
                                    {fetchingModels ? (
                                      <>
                                        <Spinner size="sm" className="mr-2" />
                                        Fetching...
                                      </>
                                    ) : modelsFetched ? (
                                      <>
                                        <CheckIcon className="h-4 w-4 mr-2" />
                                        Models Loaded
                                      </>
                                    ) : (
                                      'Fetch Models'
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </>
                          )}

                          {/* Model Selection (shared between all provider types) */}
                          {modelsFetched && availableModelsFromAPI.length > 0 && (
                            <div className="space-y-4">
                              <div>
                                <label className="block text-sm font-semibold text-charcoal dark:text-gray-100 mb-3">
                                  Step 3: Select Models to Enable *
                                </label>
                                <div className="max-h-64 overflow-y-auto border border-gray-200 dark:border-dark-border rounded-xl bg-gray-50 dark:bg-dark-surface-2 divide-y divide-gray-200 dark:divide-dark-border">
                                  {availableModelsFromAPI.map((model: any) => (
                                    <div
                                      key={model.name}
                                      className="flex items-center px-3 py-2.5 bg-white dark:bg-dark-surface hover:bg-gray-50 dark:hover:bg-dark-surface-2 cursor-pointer transition-colors group"
                                      onClick={() => {
                                        if (selectedModels.includes(model.name)) {
                                          setSelectedModels(selectedModels.filter(m => m !== model.name));
                                          if (providerFormData.default_model === model.name) {
                                            setProviderFormData({ ...providerFormData, default_model: '' });
                                          }
                                        } else {
                                          setSelectedModels([...selectedModels, model.name]);
                                        }
                                      }}
                                    >
                                      <Checkbox
                                        checked={selectedModels.includes(model.name)}
                                        className="flex-shrink-0"
                                      />
                                      <div className="ml-3 flex-1 min-w-0 flex items-center gap-3">
                                        <span className="text-sm font-medium text-charcoal dark:text-gray-100 truncate flex-shrink-0" title={model.name}>
                                          {model.name}
                                        </span>
                                        <div className="flex items-center gap-2 flex-shrink-0">
                                          {model.context_length && (
                                            <Badge variant="secondary">
                                              {model.context_length.toLocaleString()}k
                                            </Badge>
                                          )}
                                          {model.supports_functions && (
                                            <Badge variant="success">
                                              Fn
                                            </Badge>
                                          )}
                                          {model.supports_vision && (
                                            <Badge variant="info">
                                              Vision
                                            </Badge>
                                          )}
                                        </div>
                                        {model.description && (
                                          <span className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1 min-w-0" title={model.description}>
                                            {model.description}
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                                <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                                  Select the models you want to make available in Eliza Forge. You can select multiple models.
                                </p>
                              </div>

                              {/* Default Model Selection */}
                              {selectedModels.length > 0 && (
                                <div className="space-y-1.5">
                                  <Label className="font-semibold">Step 4: Choose Default Model *</Label>
                                  <Select
                                    value={providerFormData.default_model}
                                    onValueChange={(value) => setProviderFormData({ ...providerFormData, default_model: value })}
                                    placeholder="Select a default model..."
                                  >
                                    {selectedModels.map((modelName: string) => (
                                      <SelectOption key={modelName} value={modelName}>{modelName}</SelectOption>
                                    ))}
                                  </Select>
                                  <p className="text-xs text-gray-500 dark:text-gray-400">
                                    The model that will be used by default for AI operations. You can only choose from your selected models.
                                  </p>
                                </div>
                              )}
                            </div>
                          )}

                          {modelsFetched && availableModelsFromAPI.length === 0 && (
                            <Alert variant="warning">
                              <ExclamationTriangleIcon className="h-5 w-5" />
                              <div>
                                <p className="font-medium">No models found</p>
                                <p className="text-sm opacity-80 mt-1">Please check your credentials and try again</p>
                              </div>
                            </Alert>
                          )}

                          {/* Adoption Settings (OpenAI only) */}
                          {selectedProviderType === 'openai' && modelsFetched && selectedModels.length > 0 && (
                            <div className="mt-6 pt-6 border-t border-gray-200 dark:border-dark-border">
                              <div className="flex items-center gap-2 mb-4">
                                <ChartBarIcon className="h-5 w-5 text-gray-500 dark:text-gray-400" />
                                <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100">Adoption Tracking (Optional)</h4>
                              </div>
                              <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                                Enable this to use this API key for ChatGPT Enterprise adoption metrics.
                                Only one OpenAI provider per tenant can be used for adoption tracking.
                              </p>
                              
                              <div className="flex items-center justify-between mb-4">
                                <Label htmlFor="enable-adoption" className="text-sm font-normal">Enable Adoption Tracking</Label>
                                <Switch
                                  id="enable-adoption"
                                  checked={providerFormData.enable_adoption}
                                  onCheckedChange={(checked) => setProviderFormData({ ...providerFormData, enable_adoption: checked })}
                                />
                              </div>
                              
                              {providerFormData.enable_adoption && (
                                <div className="space-y-4">
                                  <div className="space-y-1.5">
                                    <Label htmlFor="workspace-id">ChatGPT Workspace ID</Label>
                                    <Input
                                      id="workspace-id"
                                      type="text"
                                      value={providerFormData.chatgpt_workspace_id}
                                      onChange={(e) => {
                                        setProviderFormData({ ...providerFormData, chatgpt_workspace_id: e.target.value });
                                        setComplianceTestResult(null); // Reset test when workspace ID changes
                                      }}
                                      placeholder="Enter workspace ID from ChatGPT Enterprise admin"
                                    />
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                      Find this in your ChatGPT Enterprise admin console (Settings → Workspace ID)
                                    </p>
                                  </div>
                                  
                                  {/* Test Compliance API Button */}
                                  <div className="flex items-center gap-3">
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={handleTestComplianceApi}
                                      disabled={testingCompliance || !providerFormData.api_key || !providerFormData.chatgpt_workspace_id}
                                    >
                                      {testingCompliance ? (
                                        <>
                                          <Spinner size="sm" className="mr-2" />
                                          Testing...
                                        </>
                                      ) : (
                                        <>
                                          <BoltIcon className="h-4 w-4 mr-1.5" />
                                          Test Compliance API Access
                                        </>
                                      )}
                                    </Button>
                                  </div>

                                  {/* Compliance Test Results */}
                                  {complianceTestResult && !complianceTestResult.success && (
                                    <Alert variant="error">
                                      <ExclamationTriangleIcon className="h-5 w-5" />
                                      <div className="flex-1">
                                        <p className="font-medium">{complianceTestResult.message}</p>
                                        {complianceTestResult.instructions && (
                                          <div className="mt-3 p-3 bg-white dark:bg-dark-surface rounded-md">
                                            <pre className="text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap font-mono">
                                              {complianceTestResult.instructions}
                                            </pre>
                                          </div>
                                        )}
                                      </div>
                                    </Alert>
                                  )}

                                  {complianceTestResult && complianceTestResult.success && (
                                    <Alert variant="success" className="items-center">
                                      <span>Compliance API access confirmed.</span>
                                    </Alert>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="mt-6 flex gap-3">
                          <Button
                            type="submit"
                            disabled={createProviderConfig.isPending}
                          >
                            {createProviderConfig.isPending ? (
                              <>
                                <Spinner size="sm" className="mr-2" />
                                Creating...
                              </>
                            ) : (
                              <>
                                <CheckIcon className="h-4 w-4 mr-2" />
                                Create Configuration
                              </>
                            )}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => {
                              setShowProviderForm(false);
                              resetProviderForm();
                            }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </form>
                    )}
                  </div>
                )}

                {/* Provider Configuration List */}
                <DataTable
                  data={providerConfigs}
                  columns={[
                    // Provider Column
                    {
                      id: 'provider',
                      header: 'Provider',
                      cell: ({ row: config }) => (
                        <div className="flex items-center">
                          <div className={`p-2 rounded-lg flex-shrink-0 ${getProviderColor(config.provider_type)}`}>
                            {getProviderIcon(config.provider_type)}
                          </div>
                          <span className="ml-3 text-sm font-medium text-charcoal dark:text-gray-100">
                            {config.provider_type === 'openai' ? 'OpenAI' : 
                             config.provider_type === 'anthropic' ? 'Anthropic' :
                             config.provider_type === 'groq' ? 'Groq' :
                             config.provider_type === 'bedrock' ? 'AWS Bedrock' :
                             config.provider_type.toUpperCase()}
                          </span>
                          {config.is_adoption_source && (
                            <Badge 
                              variant={
                                config.adoption_compliance_status === 'success' 
                                  ? 'success'
                                  : config.adoption_compliance_status === 'failed'
                                  ? 'danger'
                                  : 'warning'
                              } 
                              className="ml-2"
                            >
                              {config.adoption_compliance_status === 'success' ? (
                                <ChartBarIcon className="w-3 h-3 mr-1" />
                              ) : (
                                <ExclamationTriangleIcon className="w-3 h-3 mr-1" />
                              )}
                              Adoption
                              {config.adoption_compliance_status !== 'success' && (
                                <span className="text-[10px] ml-0.5">
                                  {config.adoption_compliance_status === 'failed' ? '(Error)' : '(Not Tested)'}
                                </span>
                              )}
                            </Badge>
                          )}
                        </div>
                      ),
                    },
                    // Name Column
                    {
                      id: 'name',
                      header: 'Name',
                      cell: ({ row: config }) => (
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-charcoal dark:text-gray-100 max-w-xs truncate" title={config.name}>
                              {config.name || `${config.provider_type.charAt(0).toUpperCase() + config.provider_type.slice(1)} Configuration`}
                            </span>
                            {config.is_shared_from_platform && (
                              <Badge variant="brand">
                                <ShareIcon className="w-3 h-3 mr-1" />
                                Platform
                              </Badge>
                            )}
                          </div>
                          {config.config_summary?.aws_region && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              Region: {config.config_summary.aws_region}
                            </div>
                          )}
                        </div>
                      ),
                    },
                    // Default Model Column
                    {
                      id: 'default_model',
                      header: 'Default Model',
                      cell: ({ row: config }) => config.default_model ? (
                        <span className="text-sm font-mono text-charcoal dark:text-gray-100">{config.default_model}</span>
                      ) : (
                        <span className="text-sm text-gray-500 dark:text-gray-400">—</span>
                      ),
                    },
                    // Model Status Column
                    {
                      id: 'status',
                      header: 'Model Status',
                      cell: ({ row: config }) => (
                        <div>
                          {config.is_healthy ? (
                            <Badge variant="success">
                              <CheckIcon className="h-3 w-3 mr-1" />
                              Healthy
                            </Badge>
                          ) : config.last_error ? (
                            <Badge variant="danger">
                              <ExclamationTriangleIcon className="h-3 w-3 mr-1" />
                              Error
                            </Badge>
                          ) : (
                            <Badge variant="secondary">
                              Not Tested
                            </Badge>
                          )}
                          {config.last_error && (
                            <div className="mt-1 text-xs text-red-500 dark:text-red-400 max-w-xs truncate" title={config.last_error}>
                              {config.last_error}
                            </div>
                          )}
                        </div>
                      ),
                    },
                    // Enabled Column
                    {
                      id: 'enabled',
                      header: 'Enabled',
                      align: 'center' as const,
                      cell: ({ row: config }) => (
                        <div onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={config.is_enabled}
                            onChange={(e) => {
                              if (config.is_shared_from_platform) {
                                toggleSharedProviderEnabled.mutate({ 
                                  configId: config.id, 
                                  isEnabled: e.target.checked 
                                });
                              } else {
                                toggleProviderEnabled.mutate({ 
                                  configId: config.id, 
                                  isEnabled: e.target.checked 
                                });
                              }
                            }}
                          />
                        </div>
                      ),
                    },
                    // Actions Column
                    {
                      id: 'actions',
                      header: '',
                      align: 'right' as const,
                      cell: ({ row: config }) => (
                        <DataTableActions>
                          {!config.is_shared_from_platform && (
                            <DataTableActionButton
                              icon={testingProvider === config.id ? <Spinner size="sm" /> : <BoltIcon className="h-4 w-4" />}
                              label="Test Connection"
                              onClick={() => handleTestConnection(config.id)}
                              disabled={testingProvider === config.id}
                            />
                          )}
                          {config.is_shared_from_platform ? (
                            <span onClick={(e) => e.stopPropagation()}>
                              <Badge variant="secondary">Read-only</Badge>
                            </span>
                          ) : (
                            <DataTableActionButton
                              icon={<TrashIcon className="h-4 w-4" />}
                              label="Delete Configuration"
                              onClick={() => handleDeleteConfig(config.id, config.provider_type)}
                              variant="danger"
                            />
                          )}
                        </DataTableActions>
                      ),
                    },
                  ] as Column<any>[]}
                  getRowId={(row) => row.id}
                  expandable
                  allowMultipleExpanded={false}
                  expandedRows={expandedProviderIds}
                  onExpandedChange={setExpandedProviderIds}
                  renderExpandedRow={(config) => (
                    <div className="space-y-4">
                      {/* Adoption Tracking Section */}
                      {!config.is_shared_from_platform && config.provider_type === 'openai' ? (
                        <div className="bg-white dark:bg-dark-surface rounded-lg p-4 border border-gray-200 dark:border-dark-border">
                          <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100 flex items-center gap-2 mb-3">
                            <ChartBarIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                            Adoption Tracking
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                            Enable this provider as the source for ChatGPT Enterprise adoption metrics. 
                            Only one OpenAI provider per tenant can be used for adoption tracking.
                          </p>
                          
                          <div className="flex items-center justify-between mb-4">
                            <Label className="text-sm font-normal">Enable Adoption Tracking</Label>
                            <div onClick={(e) => e.stopPropagation()}>
                              <Switch
                                checked={config.is_adoption_source}
                                onCheckedChange={() => {
                                  handleEnableAdoption(
                                    config.id, 
                                    config.is_adoption_source, 
                                    config.chatgpt_workspace_id
                                  );
                                }}
                              />
                            </div>
                          </div>
                          
                          {config.is_adoption_source && (
                            <div className="space-y-4">
                              <div>
                                <label className="block text-sm font-medium text-charcoal dark:text-gray-100 mb-1">
                                  ChatGPT Workspace ID
                                </label>
                                <div className="flex gap-2">
                                  <Input
                                    type="text"
                                    defaultValue={config.chatgpt_workspace_id || ''}
                                    placeholder="Enter workspace ID from ChatGPT Enterprise admin"
                                    onClick={(e) => e.stopPropagation()}
                                    onBlur={(e) => {
                                      if (e.target.value !== config.chatgpt_workspace_id) {
                                        setProviderComplianceStatus(prev => {
                                          const newStatus = { ...prev };
                                          delete newStatus[config.id];
                                          return newStatus;
                                        });
                                        updateAdoptionSettings.mutate({
                                          configId: config.id,
                                          data: {
                                            is_adoption_source: config.is_adoption_source,
                                            chatgpt_workspace_id: e.target.value,
                                          }
                                        });
                                      }
                                    }}
                                  />
                                </div>
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                  Find this in your ChatGPT Enterprise admin console (Settings → Workspace ID)
                                </p>
                              </div>
                              
                              {/* Compliance API Status & Test Button */}
                              <div className="pt-3 border-t border-gray-200 dark:border-dark-border/50">
                                <div className="flex items-center justify-between mb-3">
                                  <span className="text-sm font-medium text-charcoal dark:text-gray-100">Compliance API Status</span>
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleTestComplianceForProvider(config.id);
                                    }}
                                    disabled={testingComplianceForProvider === config.id || !config.chatgpt_workspace_id}
                                  >
                                    {testingComplianceForProvider === config.id ? (
                                      <>
                                        <Spinner size="sm" className="mr-2" />
                                        Testing...
                                      </>
                                    ) : (
                                      <>
                                        <BoltIcon className="h-4 w-4 mr-1.5" />
                                        Test Compliance Access
                                      </>
                                    )}
                                  </Button>
                                </div>
                                
                                {/* Status Display */}
                                {(() => {
                                  const localResult = providerComplianceStatus[config.id];
                                  const storedStatus = config.adoption_compliance_status;
                                  const storedLastChecked = config.adoption_compliance_last_checked;
                                  const storedError = config.adoption_compliance_error;
                                  
                                  if (localResult) {
                                    if (localResult.success) {
                                      return (
                                        <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                                          <div className="flex items-center gap-2">
                                            <CheckCircleIcon className="h-5 w-5 text-green-500" />
                                            <div>
                                              <p className="text-sm text-green-400">
                                                Compliance API access confirmed. Your API key has the required scope.
                                              </p>
                                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                                Tested: {localResult.tested_at.toLocaleString()}
                                              </p>
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    } else {
                                      return (
                                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                                          <div className="flex items-start gap-2">
                                            <ExclamationTriangleIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                                            <div className="flex-1">
                                              <p className="text-sm font-medium text-red-400">{localResult.message}</p>
                                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                                Tested: {localResult.tested_at.toLocaleString()}
                                              </p>
                                              {localResult.instructions && (
                                                <div className="mt-3 p-3 bg-white dark:bg-dark-surface rounded-md">
                                                  <pre className="text-xs text-gray-500 dark:text-gray-400 whitespace-pre-wrap font-mono">
                                                    {localResult.instructions}
                                                  </pre>
                                                </div>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    }
                                  }
                                  
                                  if (storedStatus === 'success') {
                                    return (
                                      <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                                        <div className="flex items-center gap-2">
                                          <CheckCircleIcon className="h-5 w-5 text-green-500" />
                                          <div>
                                            <p className="text-sm text-green-400">
                                              Compliance API access confirmed. Your API key has the required scope.
                                            </p>
                                            {storedLastChecked && (
                                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                                Last verified: {new Date(storedLastChecked).toLocaleString()}
                                              </p>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  } else if (storedStatus === 'failed') {
                                    return (
                                      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                                        <div className="flex items-start gap-2">
                                          <ExclamationTriangleIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                                          <div className="flex-1">
                                            <p className="text-sm font-medium text-red-400">{storedError || 'Compliance API test failed'}</p>
                                            {storedLastChecked && (
                                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                                Last checked: {new Date(storedLastChecked).toLocaleString()}
                                              </p>
                                            )}
                                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                                              Click "Test Compliance Access" to see detailed error information.
                                            </p>
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  } else {
                                    return (
                                      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                                        <div className="flex items-center gap-2">
                                          <ExclamationTriangleIcon className="h-5 w-5 text-amber-500" />
                                          <p className="text-sm text-amber-400">
                                            Not tested — Click "Test Compliance Access" to verify your API key can access adoption metrics
                                          </p>
                                        </div>
                                      </div>
                                    );
                                  }
                                })()}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : config.is_shared_from_platform ? (
                        <div className="bg-white dark:bg-dark-surface rounded-lg p-4 border border-gray-200 dark:border-dark-border">
                          <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100 flex items-center gap-2 mb-2">
                            <ChartBarIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                            Adoption Tracking
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Shared providers cannot be used for adoption tracking. 
                            Create your own OpenAI provider to enable adoption metrics.
                          </p>
                        </div>
                      ) : config.provider_type !== 'openai' ? (
                        <div className="bg-white dark:bg-dark-surface rounded-lg p-4 border border-gray-200 dark:border-dark-border">
                          <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100 flex items-center gap-2 mb-2">
                            <ChartBarIcon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                            Adoption Tracking
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            Adoption tracking is currently only available for OpenAI providers.
                          </p>
                        </div>
                      ) : null}
                      
                      {/* Configuration Details */}
                      <div className="bg-white dark:bg-dark-surface rounded-lg p-4 border border-gray-200 dark:border-dark-border">
                        <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100 mb-3">Configuration Details</h4>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Created:</span>
                            <span className="ml-2 text-charcoal dark:text-gray-100">{new Date(config.created_at).toLocaleDateString()}</span>
                          </div>
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Last Updated:</span>
                            <span className="ml-2 text-charcoal dark:text-gray-100">{config.updated_at ? new Date(config.updated_at).toLocaleDateString() : 'Never'}</span>
                          </div>
                          {config.available_models?.length > 0 && (
                            <div className="col-span-2">
                              <span className="text-gray-500 dark:text-gray-400">Available Models:</span>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {config.available_models.map((model: string) => (
                                  <Badge key={model} variant="secondary">
                                    {model}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                  emptyIcon={<CpuChipIcon className="w-12 h-12" />}
                  emptyMessage="No provider configurations. Get started by adding your first AI model provider using the button above."
                  hoverable
                />
              </div>
            </div>
        </PageBody>
      </Page>

      {/* Adoption Switch Warning Modal */}
      <Modal open={showAdoptionWarningModal} onClose={handleCancelAdoptionSwitch}>
        <ModalBackdrop />
        <ModalContent size="md">
          <ModalHeader>
            <div className="flex items-center gap-2">
              <ChartBarIcon className="w-5 h-5 text-amber-500" />
              <ModalTitle>Switch Adoption Key</ModalTitle>
            </div>
          </ModalHeader>
          
          <ModalBody>
            <Alert variant="warning" className="mb-4">
              <ExclamationTriangleIcon className="w-5 h-5" />
              <div>
                <p className="font-medium">
                  Another API key is already enabled for adoption tracking.
                </p>
                <p className="text-sm opacity-80 mt-1">
                  Only one OpenAI API key per tenant can be used for adoption metrics.
                  Enabling this key will automatically disable adoption on the currently enabled key.
                </p>
              </div>
            </Alert>
            
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Do you want to switch adoption tracking to this API key?
            </p>
          </ModalBody>
          
          <ModalFooter>
            <Button variant="ghost" onClick={handleCancelAdoptionSwitch}>
              Cancel
            </Button>
            <Button onClick={handleConfirmAdoptionSwitch}>
              Switch Adoption Key
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Layout>
  );
}

import React, { useState, useEffect } from 'react';
import { Layout } from '../../components/layout/Layout';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { FlowDiagram } from '../../components/agent-configuration/FlowDiagram';
import { 
  CpuChipIcon, 
  Cog6ToothIcon,
  ChevronRightIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

// Generated types and hooks from Orval
import type { 
  FlowInfo, 
  AgentInfo, 
  AgentConfigResponse as AgentConfig,
  AgentConfigUpdateRequest,
} from '../../generated/models';
import { 
  useListFlowsV1AgentsFlowsGet,
  useListAgentsInFlowV1AgentsFlowsFlowIdAgentsGet,
  useGetAgentConfigurationV1AgentsConfigurationsFlowIdAgentIdGet,
  useUpdateAgentConfigurationV1AgentsConfigurationsFlowIdAgentIdPut,
  useResetAgentConfigurationV1AgentsConfigurationsFlowIdAgentIdDelete,
} from '../../generated/agent-configuration/agent-configuration';
import { useListProviderConfigurationsV1ProvidersConfigurationsGet } from '../../generated/ai-providers/ai-providers';
import type { ProviderConfigurationResponse as ProviderConfig } from '../../generated/models';

export const AgentConfigurationPage: React.FC = () => {
  // State for selected flow/agent
  const [selectedFlow, setSelectedFlow] = useState<FlowInfo | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  
  // Form state
  const [editedConfig, setEditedConfig] = useState<Partial<AgentConfigUpdateRequest>>({});
  const [hasChanges, setHasChanges] = useState(false);
  
  // Fetch flows using Orval-generated hook
  const { data: flows, isLoading: flowsLoading, error: flowsError } = useListFlowsV1AgentsFlowsGet();
  
  // Fetch agents for selected flow
  const { 
    data: agents, 
    isLoading: agentsLoading 
  } = useListAgentsInFlowV1AgentsFlowsFlowIdAgentsGet(
    selectedFlow?.flow_identifier || '', 
    { query: { enabled: !!selectedFlow } }
  );
  
  // Fetch agent configuration
  const { 
    data: agentConfig, 
    isLoading: configLoading,
    refetch: refetchConfig
  } = useGetAgentConfigurationV1AgentsConfigurationsFlowIdAgentIdGet(
    selectedFlow?.flow_identifier || '',
    selectedAgent?.agent_identifier || '',
    { query: { enabled: !!(selectedFlow && selectedAgent) } }
  );
  
  // Fetch providers
  const { data: providersData } = useListProviderConfigurationsV1ProvidersConfigurationsGet();
  const providers = providersData?.providers?.filter((p: ProviderConfig) => p.is_enabled) || [];
  
  // Mutations
  const updateMutation = useUpdateAgentConfigurationV1AgentsConfigurationsFlowIdAgentIdPut();
  const resetMutation = useResetAgentConfigurationV1AgentsConfigurationsFlowIdAgentIdDelete();
  
  // Auto-select first flow and agent
  useEffect(() => {
    if (flows && flows.length > 0 && !selectedFlow) {
      setSelectedFlow(flows[0]);
    }
  }, [flows, selectedFlow]);
  
  useEffect(() => {
    if (agents && agents.length > 0 && !selectedAgent) {
      setSelectedAgent(agents[0]);
    }
  }, [agents, selectedAgent]);
  
  // Update form when config loads
  useEffect(() => {
    if (agentConfig) {
      setEditedConfig({
        role: agentConfig.role,
        goal: agentConfig.goal,
        backstory: agentConfig.backstory,
        model_id: agentConfig.model_id,
        provider_config_id: agentConfig.provider_config_id,
        temperature: agentConfig.temperature,
        max_tokens: agentConfig.max_tokens,
        enabled_tools: agentConfig.enabled_tools,
      });
      setHasChanges(false);
    }
  }, [agentConfig]);
  
  // Handlers
  const handleFlowSelect = (flow: FlowInfo) => {
    setSelectedFlow(flow);
    setSelectedAgent(null);
  };
  
  const handleAgentSelect = (agent: AgentInfo) => {
    setSelectedAgent(agent);
  };
  
  const handleFieldChange = (field: keyof AgentConfigUpdateRequest, value: any) => {
    setEditedConfig(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };
  
  const handleSaveConfig = async () => {
    if (!selectedFlow || !selectedAgent) return;
    
    try {
      await updateMutation.mutateAsync({
        flowId: selectedFlow.flow_identifier,
        agentId: selectedAgent.agent_identifier,
        data: editedConfig as AgentConfigUpdateRequest
      });
      
      // Refetch to get updated config
      await refetchConfig();
      setHasChanges(false);
    } catch (err: any) {
      console.error('Failed to save configuration:', err);
    }
  };
  
  const handleResetConfig = async () => {
    if (!selectedFlow || !selectedAgent) return;
    
    if (!window.confirm('Reset this agent to default configuration? This will remove any custom settings.')) {
      return;
    }
    
    try {
      await resetMutation.mutateAsync({
        flowId: selectedFlow.flow_identifier,
        agentId: selectedAgent.agent_identifier
      });
      
      // Refetch to get default config
      await refetchConfig();
      setHasChanges(false);
    } catch (err: any) {
      console.error('Failed to reset configuration:', err);
    }
  };
  
  const loading = flowsLoading || agentsLoading || configLoading;
  const isSaving = updateMutation.isPending || resetMutation.isPending;
  
  return (
    <Layout>
      <div className="h-full w-full flex flex-col">
        {/* Header */}
        <div className="h-10 bg-surface border-b border-border flex items-center px-6 flex-shrink-0">
          <CpuChipIcon className="h-5 w-5 text-brand mr-2" />
          <h1 className="text-base font-medium text-text">Agent Configuration</h1>
          <div className="ml-auto flex items-center gap-2 text-xs text-muted">
            <span>Runtime Configuration Management</span>
          </div>
        </div>

      {/* Main Content - Vertical Split (Top: Config Panes, Bottom: Flow Diagram) */}
      <div className="h-full w-full flex flex-col">
        <PanelGroup direction="vertical" className="flex-1">
          
          {/* Top Panel: 3 Resizable Horizontal Panes */}
          <Panel defaultSize={50} minSize={30}>
            <div className="h-full overflow-hidden">
        <PanelGroup direction="horizontal">
          
          {/* Left Pane: Flows */}
          <Panel defaultSize={20} minSize={15} maxSize={30}>
            <div className="h-full flex flex-col bg-surface-2">
              <div className="h-10 border-b border-border px-4 flex items-center flex-shrink-0">
                <h2 className="text-sm font-medium text-text">Flows</h2>
                {flowsLoading && (
                  <ArrowPathIcon className="h-4 w-4 ml-auto animate-spin text-muted" />
                )}
              </div>
              <div className="flex-1 overflow-y-auto scroll-slim ios-momentum">
                {flowsError ? (
                  <div className="p-4 text-sm text-red-500">
                    Failed to load flows
                  </div>
                ) : null}
                {flows?.map((flow) => (
                  <button
                    key={flow.flow_identifier}
                    onClick={() => handleFlowSelect(flow)}
                    className={`w-full px-4 py-3 text-left border-b border-border transition-colors ${
                      selectedFlow?.flow_identifier === flow.flow_identifier
                        ? 'bg-brand/10 border-l-2 border-l-brand'
                        : 'hover:bg-surface'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-text">
                        {flow.flow_name}
                      </span>
                      <span className="text-xs text-muted">
                        {flow.agent_count} agents
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Panel>

          <PanelResizeHandle className="w-px bg-border hover:bg-brand transition-colors cursor-col-resize" />

          {/* Middle Pane: Agents */}
          <Panel defaultSize={20} minSize={15} maxSize={30}>
            <div className="h-full flex flex-col bg-surface-2">
              <div className="h-10 border-b border-border px-4 flex items-center flex-shrink-0">
                <h2 className="text-sm font-medium text-text">Agents</h2>
                {agentsLoading && (
                  <ArrowPathIcon className="h-4 w-4 ml-auto animate-spin text-muted" />
                )}
              </div>
              <div className="flex-1 overflow-y-auto scroll-slim ios-momentum">
                {!selectedFlow && (
                  <div className="p-4 text-sm text-muted">
                    Select a flow to view agents
                  </div>
                )}
                {agents?.map((agent) => (
                  <button
                    key={agent.agent_identifier}
                    onClick={() => handleAgentSelect(agent)}
                    className={`w-full px-4 py-3 text-left border-b border-border transition-colors ${
                      selectedAgent?.agent_identifier === agent.agent_identifier
                        ? 'bg-brand/10 border-l-2 border-l-brand'
                        : 'hover:bg-surface'
                    }`}
                  >
                    <div className="text-sm font-medium text-text mb-1">
                      {agent.agent_name}
                    </div>
                    <div className="text-xs text-muted">
                      {agent.current_model}
                    </div>
                    <div className="text-xs text-muted mt-0.5">
                      {agent.current_provider}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Panel>

          <PanelResizeHandle className="w-px bg-border hover:bg-brand transition-colors cursor-col-resize" />

          {/* Right Pane: Configuration Editor */}
          <Panel defaultSize={60} minSize={40}>
            <div className="h-full flex flex-col bg-surface">
          {!selectedAgent ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-muted">
                <Cog6ToothIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select an agent to configure</p>
              </div>
            </div>
          ) : (
            <>
              {/* Configuration Header */}
              <div className="h-14 border-b border-border px-6 flex items-center justify-between bg-surface-2">
                <div>
                  <h3 className="text-base font-medium text-text">
                    {agentConfig?.role || selectedAgent.agent_name}
                  </h3>
                  <div className="text-xs text-muted mt-0.5">
                    {selectedFlow?.flow_name} → {selectedAgent.agent_identifier}
                    {agentConfig && (
                      <span className="ml-2 px-2 py-0.5 rounded text-xs bg-brand/10 text-brand">
                        {agentConfig.source}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleResetConfig}
                    disabled={isSaving || agentConfig?.source === 'default'}
                    className="px-3 py-1.5 text-sm border border-border rounded hover:bg-surface-2 disabled:opacity-50 disabled:cursor-not-allowed text-text"
                  >
                    Reset to Defaults
                  </button>
                  <button
                    onClick={handleSaveConfig}
                    disabled={!hasChanges || isSaving}
                    className="px-3 py-1.5 text-sm bg-brand text-on-brand rounded hover:bg-brand/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                  >
                    {isSaving ? (
                      <>
                        <ArrowPathIcon className="h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                </div>
              </div>

              {/* Configuration Form */}
              <div className="flex-1 overflow-y-auto scroll-slim ios-momentum p-6">
                {configLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <ArrowPathIcon className="h-8 w-8 animate-spin text-muted" />
                  </div>
                ) : (
                  <div className="max-w-3xl space-y-6">
                    {/* Role */}
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Role
                      </label>
                      <input
                        type="text"
                        value={editedConfig.role || ''}
                        onChange={(e) => handleFieldChange('role', e.target.value)}
                        className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-1 focus:ring-brand"
                        placeholder="Agent role name"
                      />
                    </div>

                    {/* Goal */}
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Goal
                      </label>
                      <textarea
                        value={editedConfig.goal || ''}
                        onChange={(e) => handleFieldChange('goal', e.target.value)}
                        rows={3}
                        className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-1 focus:ring-brand"
                        placeholder="What this agent aims to accomplish"
                      />
                    </div>

                    {/* Backstory */}
                    <div>
                      <label className="block text-sm font-medium text-text mb-2">
                        Backstory
                      </label>
                      <textarea
                        value={editedConfig.backstory || ''}
                        onChange={(e) => handleFieldChange('backstory', e.target.value)}
                        rows={4}
                        className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-1 focus:ring-brand"
                        placeholder="Agent's background and expertise"
                      />
                    </div>

                    {/* Model Configuration */}
                    <div className="border-t border-border pt-6">
                      <h4 className="text-sm font-medium text-text mb-4">Model Configuration</h4>
                      
                      <div className="grid grid-cols-2 gap-4">
                        {/* Provider */}
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Provider
                          </label>
                          <select
                            value={editedConfig.provider_config_id || ''}
                            onChange={(e) => handleFieldChange('provider_config_id', parseInt(e.target.value))}
                            className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-1 focus:ring-brand"
                          >
                            <option value="">Select Provider</option>
                            {providers.map((provider: ProviderConfig) => (
                              <option key={provider.id} value={provider.id}>
                                {provider.name || provider.provider_type}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Model */}
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Model
                          </label>
                          <input
                            type="text"
                            value={editedConfig.model_id || ''}
                            onChange={(e) => handleFieldChange('model_id', e.target.value)}
                            className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-1 focus:ring-brand"
                            placeholder="e.g., gpt-4o-mini"
                          />
                          <p className="text-xs text-muted mt-1">
                            Leave empty to use provider's default model
                          </p>
                        </div>

                        {/* Temperature */}
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Temperature: {editedConfig.temperature?.toFixed(2) || '0.00'}
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={editedConfig.temperature || 0}
                            onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value))}
                            className="w-full"
                          />
                        </div>

                        {/* Max Tokens */}
                        <div>
                          <label className="block text-sm font-medium text-text mb-2">
                            Max Tokens
                          </label>
                          <input
                            type="number"
                            value={editedConfig.max_tokens || 2000}
                            onChange={(e) => handleFieldChange('max_tokens', parseInt(e.target.value))}
                            className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-1 focus:ring-brand"
                            min="100"
                            max="16000"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Tools */}
                    {agentConfig && agentConfig.enabled_tools.length > 0 && (
                      <div className="border-t border-border pt-6">
                        <h4 className="text-sm font-medium text-text mb-4">Enabled Tools</h4>
                        <div className="flex flex-wrap gap-2">
                          {agentConfig.enabled_tools.map((tool) => (
                            <span
                              key={tool}
                              className="px-3 py-1 bg-brand/10 text-brand rounded-full text-xs"
                            >
                              {tool}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Metadata */}
                    {agentConfig && (
                      <div className="border-t border-border pt-6">
                        <h4 className="text-sm font-medium text-text mb-4">Metadata</h4>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="text-muted">Version:</span>
                            <span className="ml-2 text-text">{agentConfig.version}</span>
                          </div>
                          <div>
                            <span className="text-muted">Source:</span>
                            <span className="ml-2 text-text capitalize">{agentConfig.source}</span>
                          </div>
                          <div>
                            <span className="text-muted">Current Provider:</span>
                            <span className="ml-2 text-text">{agentConfig.provider_name}</span>
                          </div>
                          <div>
                            <span className="text-muted">Status:</span>
                            <span className="ml-2">
                              {agentConfig.is_enabled ? (
                                <CheckCircleIcon className="h-4 w-4 inline text-green-500" />
                              ) : (
                                <XCircleIcon className="h-4 w-4 inline text-red-500" />
                              )}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
            </div>
          </Panel>

        </PanelGroup>
            </div>
          </Panel>

          <PanelResizeHandle className="h-1 bg-border hover:bg-brand transition-colors cursor-row-resize" />

          {/* Bottom Panel: Flow Diagram */}
          <Panel defaultSize={50} minSize={20}>
            <div className="h-full w-full">
              <FlowDiagram 
                flow={selectedFlow}
                agents={agents || []}
                selectedAgent={selectedAgent}
                onAgentSelect={handleAgentSelect}
              />
            </div>
          </Panel>

        </PanelGroup>
      </div>
      </div>
    </Layout>
  );
};

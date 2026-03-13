/**
 * ChatPage - Main chat interface for workspaces
 * 
 * URL Structure:
 * - /chat - Workspace picker (no workspace selected)
 * - /chat/:workspaceId - New conversation with workspace
 * - /chat/:workspaceId/:conversationId - Continue existing conversation
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ChatBubbleLeftRightIcon, 
  PlusIcon,
  MagnifyingGlassIcon,
  DocumentTextIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';
import { Layout } from '../../components/layout/Layout';
import { Input, Button, Spinner } from '../../components/ui';
import RAGFlowConversationView from '../../components/data-analyst/RAGFlowConversationView';
import ConversationView from '../../components/data-analyst/ConversationView';
import { ChatProvider } from '../../components/ui/chat';
import { BiConversationsProvider, useBiConversations } from '../../contexts/BiConversationsContext';
import { DataSourceType } from '../../generated/models';
import { useToasts } from '../../stores/useToasts';
import { AXIOS_INSTANCE } from '../../services/api-client';

interface WorkspacePickerItem {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
  icon: string;
  color: string;
  template_name: string | null;
  template_display_name: string | null;
  document_count: number;
  is_available: boolean;
}

function WorkspacePicker({ 
  onSelect 
}: { 
  onSelect: (workspace: WorkspacePickerItem) => void 
}) {
  const { push: addToast } = useToasts();
  
  const [workspaces, setWorkspaces] = useState<WorkspacePickerItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    async function fetchWorkspaces() {
      try {
        const res = await AXIOS_INSTANCE.get('/v1/chat/workspaces', {
          params: search ? { search } : undefined,
        });
        setWorkspaces(res.data?.workspaces || []);
      } catch (e) {
        console.error('Failed to fetch workspaces:', e);
        addToast({ kind: 'error', message: 'Failed to load workspaces' });
      } finally {
        setIsLoading(false);
      }
    }
    
    const debounce = setTimeout(fetchWorkspaces, search ? 300 : 0);
    return () => clearTimeout(debounce);
  }, [search, addToast]);

  const availableWorkspaces = workspaces.filter(w => w.is_available);
  const unavailableWorkspaces = workspaces.filter(w => !w.is_available);

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-gray-50 dark:bg-dark-bg">
      <div className="max-w-xl w-full mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="w-14 h-14 mx-auto mb-5 rounded-full bg-gray-100 dark:bg-dark-surface-2 flex items-center justify-center">
            <ChatBubbleLeftRightIcon className="w-7 h-7 text-gray-400 dark:text-gray-500" />
          </div>
          <h1 className="font-title text-h1 text-charcoal dark:text-gray-100 mb-2">
            Start a New Chat
          </h1>
          <p className="text-body text-gray-500 dark:text-gray-400">
            Select a workspace to begin
          </p>
        </div>

        {/* Search */}
        <div className="relative mb-8">
          <MagnifyingGlassIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search workspaces..."
            className="pl-11 h-12 text-body"
          />
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : workspaces.length === 0 ? (
          /* Empty State */
          <div className="text-center py-16">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
            <h3 className="mt-4 font-subtitle text-h3 text-charcoal dark:text-gray-100">
              No workspaces available
            </h3>
            <p className="mt-2 text-small text-gray-500 dark:text-gray-400">
              Create a workspace and upload documents to start chatting
            </p>
            <Button className="mt-6" onClick={() => window.location.href = '/workspaces'}>
              <PlusIcon className="w-4 h-4 mr-2" />
              Create Workspace
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Available Workspaces */}
            {availableWorkspaces.length > 0 && (
              <div className="space-y-2">
                {availableWorkspaces.map((workspace) => (
                  <button
                    key={workspace.id}
                    onClick={() => onSelect(workspace)}
                    className="w-full group flex items-center gap-4 p-4 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-xl hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm transition-all text-left"
                  >
                    {/* Icon - Monochromatic */}
                    <div className="w-11 h-11 rounded-lg bg-gray-100 dark:bg-dark-surface-2 flex items-center justify-center flex-shrink-0">
                      <DocumentTextIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
                    </div>
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-charcoal dark:text-gray-100 group-hover:text-eliza-red transition-colors">
                        {workspace.display_name}
                      </h3>
                      {workspace.description && (
                        <p className="text-small text-gray-500 dark:text-gray-400 line-clamp-1 mt-0.5">
                          {workspace.description}
                        </p>
                      )}
                      <div className="flex items-center gap-3 mt-1.5">
                        {workspace.template_display_name && (
                          <span className="text-micro text-gray-400 dark:text-gray-500">
                            {workspace.template_display_name}
                          </span>
                        )}
                        <span className="text-micro text-gray-400 dark:text-gray-500">
                          {workspace.document_count} {workspace.document_count === 1 ? 'document' : 'documents'}
                        </span>
                      </div>
                    </div>
                    
                    {/* Arrow */}
                    <ArrowRightIcon className="w-5 h-5 text-gray-300 dark:text-gray-600 group-hover:text-gray-400 dark:group-hover:text-gray-500 transition-colors flex-shrink-0" />
                  </button>
                ))}
              </div>
            )}

            {/* Unavailable Workspaces (no documents yet) */}
            {unavailableWorkspaces.length > 0 && (
              <div>
                <h4 className="text-micro font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">
                  Setup Required
                </h4>
                <div className="space-y-2">
                  {unavailableWorkspaces.map((workspace) => (
                    <div
                      key={workspace.id}
                      className="flex items-center gap-4 p-3 bg-gray-50 dark:bg-dark-surface-2 border border-gray-100 dark:border-dark-border rounded-lg"
                    >
                      <div className="w-9 h-9 rounded-lg bg-gray-100 dark:bg-dark-border flex items-center justify-center flex-shrink-0">
                        <DocumentTextIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-gray-500 dark:text-gray-400 text-small">
                          {workspace.display_name}
                        </h3>
                        <p className="text-micro text-gray-400 dark:text-gray-500">
                          No documents yet
                        </p>
                      </div>
                      <a 
                        href={`/workspaces/${workspace.id}`} 
                        className="text-micro text-eliza-red hover:text-eliza-red-light font-medium"
                      >
                        Configure
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { workspaceId, conversationId } = useParams<{ workspaceId?: string; conversationId?: string }>();
  const navigate = useNavigate();
  const { push: addToast } = useToasts();
  
  const [workspace, setWorkspace] = useState<WorkspacePickerItem | null>(null);
  const [isLoading, setIsLoading] = useState(!!workspaceId);

  // Fetch workspace info when workspaceId is provided
  useEffect(() => {
    if (!workspaceId) {
      setWorkspace(null);
      setIsLoading(false);
      return;
    }

    async function fetchWorkspace() {
      try {
        const res = await AXIOS_INSTANCE.get(`/v1/workspaces/${workspaceId}`);
        const data = res.data;
        // Handle both API response formats
        const ws = data.workspace || data;
        setWorkspace({
          id: ws.id,
          name: ws.name,
          display_name: ws.display_name,
          description: ws.description,
          icon: ws.icon,
          color: ws.color,
          template_name: ws.template_name,
          template_display_name: ws.template_display_name,
          document_count: ws.document_count,
          is_available: true,
        });
      } catch (e) {
        console.error('Failed to fetch workspace:', e);
        addToast({ kind: 'error', message: 'Workspace not found' });
        navigate('/chat');
      } finally {
        setIsLoading(false);
      }
    }

    fetchWorkspace();
  }, [workspaceId, navigate, addToast]);

  // Handle workspace selection from picker
  const handleSelectWorkspace = useCallback((ws: WorkspacePickerItem) => {
    navigate(`/chat/${ws.id}`);
  }, [navigate]);

  // Handle back to workspace picker
  const handleBack = useCallback(() => {
    navigate('/chat');
  }, [navigate]);

  // Handle when a new conversation is created - update URL to include conversation UUID
  const handleConversationCreated = useCallback((uuid: string) => {
    // Replace current URL to avoid creating history entries for the intermediate state
    navigate(`/chat/${workspaceId}/${uuid}`, { replace: true });
  }, [navigate, workspaceId]);

  if (isLoading) {
    return (
      <Layout>
        <div className="flex-1 flex items-center justify-center">
          <Spinner size="lg" />
        </div>
      </Layout>
    );
  }

  // No workspace selected - show picker
  if (!workspaceId || !workspace) {
    return (
      <Layout>
        <WorkspacePicker onSelect={handleSelectWorkspace} />
      </Layout>
    );
  }

  // Workspace selected - show chat interface based on template type
  const isDataAnalytics = workspace.template_name === 'data_analytics';
  
  // Map workspace name to DataSourceType for analytics workspaces
  const dataSourceType = workspace.name as DataSourceType;
  
  return (
    <Layout>
      {isDataAnalytics ? (
        <BiConversationsProvider>
          <ChatProvider>
            <DataAnalyticsChat
              workspaceId={parseInt(workspaceId, 10)}
              workspaceName={workspace.display_name}
              dataSourceType={dataSourceType}
              onBack={handleBack}
            />
          </ChatProvider>
        </BiConversationsProvider>
      ) : (
            <RAGFlowConversationView
              domainId={parseInt(workspaceId, 10)}
              domainName={workspace.display_name}
              conversationId={conversationId}
              enableAgentMeshLiveProgress={workspace.template_name === 'agent_mesh_retrieval'}
              onBack={handleBack}
              onConversationCreated={handleConversationCreated}
            />
      )}
    </Layout>
  );
}

/**
 * DataAnalyticsChat - Wrapper component for data analytics conversations
 * Manages conversation state via BiConversationsContext
 */
function DataAnalyticsChat({
  workspaceId,
  workspaceName,
  dataSourceType,
  onBack,
}: {
  workspaceId: number;
  workspaceName: string;
  dataSourceType: DataSourceType;
  onBack: () => void;
}) {
  const {
    selectedConversationId,
    setSelectedDataSource,
    createConversation,
    isCreating,
  } = useBiConversations();
  
  const [initialized, setInitialized] = useState(false);
  const createGuard = useRef(false);

  // Set data source and create conversation on mount
  useEffect(() => {
    if (!initialized) {
      setSelectedDataSource(dataSourceType);
      setInitialized(true);
    }
  }, [dataSourceType, setSelectedDataSource, initialized]);

  // Auto-create conversation once data source is set
  // Uses createGuard ref to prevent double-creation from React StrictMode
  useEffect(() => {
    if (initialized && !selectedConversationId && !isCreating && !createGuard.current) {
      createGuard.current = true;
      createConversation(false);
    }
  }, [initialized, selectedConversationId, createConversation, isCreating]);

  // Show loading while creating conversation
  if (!selectedConversationId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <ConversationView
      conversationId={selectedConversationId}
      dataSourceType={dataSourceType}
    />
  );
}

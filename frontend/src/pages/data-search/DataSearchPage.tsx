/**
 * DataSearchPage – Chat-based interface for searching connected data sources.
 *
 * Features:
 * - Sidebar with conversation history (auto-titled with emojis)
 * - Persistent conversations stored in the database
 * - New Chat button
 * - DS Chat components for conversational experience
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChatProvider,
  ChatContainer,
  ChatMessagesPane,
  ChatScrollArea,
  ChatInputArea,
  MessageBubble,
  MessageContent,
  ThinkingIndicator,
  PromptBar,
  Badge,
  Button,
  Alert,
  SidebarProvider,
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarConversationList,
  useSidebar,
} from '../../components/ui';
import type { SidebarConversation } from '../../components/ui/sidebar-conversation-list';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  CheckCircleIcon,
  XCircleIcon,
  LinkIcon,
  SparklesIcon,
  Cog6ToothIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ConnectionStatus {
  source_type: string;
  connected: boolean;
  auth_method?: string;
  status?: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: string[];
  followUps?: string[];
  timestamp: string;
  runId?: string;
  status?: string;
}

interface ConversationSummary {
  id: string;
  workspace_id?: number | null;
  title: string | null;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  preview: string | null;
}

interface WorkspaceSummary {
  id: number;
  name: string;
  display_name: string;
  template_name?: string | null;
}

const SOURCE_LABELS: Record<string, string> = {
  hubspot: 'HubSpot',
  fathom: 'Fathom',
};

const SOURCE_ICONS: Record<string, string> = {
  hubspot: '🔶',
  fathom: '🎙️',
};

/* ------------------------------------------------------------------ */
/*  Markdown component overrides for proper table/list/link rendering  */
/* ------------------------------------------------------------------ */

const markdownComponents: Record<string, React.FC<any>> = {
  h1: ({ node, children, ...props }: any) => (
    <h1 className="text-xl font-bold text-charcoal dark:text-gray-100 mb-4 mt-6 first:mt-0 border-b border-gray-200 dark:border-dark-border pb-2" {...props}>
      {children}
    </h1>
  ),
  h2: ({ node, children, ...props }: any) => (
    <h2 className="text-lg font-semibold text-charcoal dark:text-gray-100 mb-3 mt-5 first:mt-0" {...props}>
      {children}
    </h2>
  ),
  h3: ({ node, children, ...props }: any) => (
    <h3 className="text-base font-semibold text-charcoal dark:text-gray-100 mb-2 mt-4 first:mt-0" {...props}>
      {children}
    </h3>
  ),
  p: ({ node, children, ...props }: any) => (
    <p className="mb-3 last:mb-0 leading-relaxed text-charcoal dark:text-gray-100" {...props}>
      {children}
    </p>
  ),
  ul: ({ node, ...props }: any) => (
    <ul className="list-disc list-outside ml-5 space-y-1.5 my-3 text-charcoal dark:text-gray-100" {...props} />
  ),
  ol: ({ node, ...props }: any) => (
    <ol className="list-decimal list-outside ml-5 space-y-1.5 my-3 text-charcoal dark:text-gray-100" {...props} />
  ),
  li: ({ node, children, ...props }: any) => (
    <li className="leading-relaxed text-charcoal dark:text-gray-100" {...props}>
      {children}
    </li>
  ),
  table: ({ node, ...props }: any) => (
    <div className="overflow-x-auto my-4 rounded-lg border border-gray-200 dark:border-dark-border">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-dark-border" {...props} />
    </div>
  ),
  thead: ({ node, ...props }: any) => (
    <thead className="bg-gray-50 dark:bg-dark-surface-2" {...props} />
  ),
  tbody: ({ node, ...props }: any) => (
    <tbody className="divide-y divide-gray-200 dark:divide-dark-border bg-white dark:bg-dark-surface" {...props} />
  ),
  tr: ({ node, ...props }: any) => (
    <tr className="hover:bg-gray-50 dark:hover:bg-dark-surface-2/50 transition-colors" {...props} />
  ),
  th: ({ node, ...props }: any) => (
    <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider" {...props} />
  ),
  td: ({ node, ...props }: any) => (
    <td className="px-4 py-2.5 text-sm text-charcoal dark:text-gray-200 whitespace-nowrap" {...props} />
  ),
  code: ({ node, className, children, ...props }: any) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="px-1.5 py-0.5 bg-gray-100 dark:bg-dark-surface-2 rounded text-sm font-mono text-eliza-red" {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className={`${className} block`} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ node, ...props }: any) => (
    <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto my-4 text-sm" {...props} />
  ),
  a: ({ node, children, ...props }: any) => (
    <a
      className="text-eliza-red hover:text-eliza-red-light underline underline-offset-2"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),
  blockquote: ({ node, ...props }: any) => (
    <blockquote className="border-l-4 border-eliza-red/40 pl-4 py-2 my-4 bg-gray-50 dark:bg-dark-surface-2 rounded-r-lg italic text-gray-500 dark:text-gray-400" {...props} />
  ),
  hr: ({ node, ...props }: any) => (
    <hr className="my-6 border-gray-200 dark:border-dark-border" {...props} />
  ),
  strong: ({ node, ...props }: any) => (
    <strong className="font-semibold text-charcoal dark:text-gray-100" {...props} />
  ),
  em: ({ node, ...props }: any) => (
    <em className="italic" {...props} />
  ),
};

/* ------------------------------------------------------------------ */
/*  Main page (with sidebar)                                           */
/* ------------------------------------------------------------------ */

export default function DataSearchPage() {
  return (
    <SidebarProvider>
      <ChatProvider>
        <DataSearchLayout />
      </ChatProvider>
    </SidebarProvider>
  );
}

function DataSearchLayout() {
  const navigate = useNavigate();
  const { conversationId: routeConversationId } = useParams<{ conversationId?: string }>();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(true);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);
  // Track the active conversation separately so sidebar updates without remount
  const [activeId, setActiveId] = useState<string | null>(routeConversationId || null);

  const fetchWorkspaces = useCallback(async () => {
    try {
      const { data } = await AXIOS_INSTANCE.get('/v1/workspaces', {
        params: { template: 'agent_mesh_retrieval', limit: 100 },
      });
      const loaded = (data?.workspaces || []) as WorkspaceSummary[];
      setWorkspaces(loaded);
      setSelectedWorkspaceId((prev) => {
        if (prev && loaded.some((w) => w.id === prev)) {
          return prev;
        }
        return loaded.length > 0 ? loaded[0].id : null;
      });
    } catch {
      setWorkspaces([]);
      setSelectedWorkspaceId(null);
    } finally {
      setLoadingWorkspaces(false);
    }
  }, []);

  // Fetch conversation list
  const fetchConversations = useCallback(async () => {
    if (!selectedWorkspaceId) {
      setConversations([]);
      setLoadingConversations(false);
      return;
    }
    try {
      const { data } = await AXIOS_INSTANCE.get('/api/retrieval/conversations', {
        params: { workspace_id: selectedWorkspaceId },
      });
      setConversations(data);
    } catch {
      // silent
    } finally {
      setLoadingConversations(false);
    }
  }, [selectedWorkspaceId]);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  useEffect(() => {
    setLoadingConversations(true);
    fetchConversations();
  }, [fetchConversations]);

  // Sync activeId when route changes (sidebar click / new chat)
  useEffect(() => {
    setActiveId(routeConversationId || null);
  }, [routeConversationId]);

  // Sidebar handlers
  const handleNewChat = useCallback(() => {
    navigate('/data-search');
  }, [navigate]);

  const handleSelectConversation = useCallback((id: string) => {
    navigate(`/data-search/${id}`);
  }, [navigate]);

  const handleDeleteConversation = useCallback(async (id: string) => {
    try {
      await AXIOS_INSTANCE.delete(`/api/retrieval/conversations/${id}`);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      // If we just deleted the active conversation, go to new chat
      if (activeId === id) {
        navigate('/data-search');
      }
    } catch {
      // silent
    }
  }, [activeId, navigate]);

  // Map to sidebar format (no preview subtitle)
  const sidebarConversations: SidebarConversation[] = conversations.map((c) => ({
    id: c.id,
    title: c.title,
    messageCount: c.message_count,
    lastActivityAt: c.updated_at,
  }));

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar */}
      <ChatSidebar
        conversations={sidebarConversations}
        activeId={activeId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        isLoading={loadingConversations}
      />

      {/* Main chat area */}
      <div className="flex-1 min-w-0">
        <DataSearchChat
          key={`${routeConversationId || '__new__'}:${selectedWorkspaceId || 'no_workspace'}`}
          conversationId={routeConversationId || null}
          workspaces={workspaces}
          selectedWorkspaceId={selectedWorkspaceId}
          onWorkspaceChange={setSelectedWorkspaceId}
          loadingWorkspaces={loadingWorkspaces}
          onConversationCreated={(newId: string) => {
            setActiveId(newId);
            fetchConversations();
            // Update URL without triggering remount
            window.history.replaceState(null, '', `/data-search/${newId}`);
          }}
          onMessageComplete={() => {
            // Refresh conversation list to update titles/previews
            fetchConversations();
          }}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Chat panel                                                         */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Collapsible sidebar                                                */
/* ------------------------------------------------------------------ */

interface ChatSidebarProps {
  conversations: SidebarConversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  isLoading: boolean;
}

function ChatSidebar({ conversations, activeId, onSelect, onNewChat, onDelete, isLoading }: ChatSidebarProps) {
  const { collapsed, toggleCollapsed } = useSidebar();

  return (
    <Sidebar expandedWidth={280} collapsedWidth={48}>
      <SidebarHeader className="border-b border-gray-200 dark:border-dark-border">
        <div className="flex items-center justify-between w-full px-1">
          {!collapsed && (
            <div className="flex items-center gap-2">
              <SparklesIcon className="h-5 w-5 text-gray-500 dark:text-gray-400 flex-shrink-0" />
              <span className="font-subtitle text-sm text-charcoal dark:text-gray-100 truncate">
                Your Chats
              </span>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="h-7 w-7"
          >
            {collapsed ? (
              <ChevronRightIcon className="h-4 w-4" />
            ) : (
              <ChevronLeftIcon className="h-4 w-4" />
            )}
          </Button>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarConversationList
          conversations={conversations}
          selectedId={activeId}
          onSelect={onSelect}
          onNewChat={onNewChat}
          onDelete={onDelete}
          isLoading={isLoading}
          collapsed={collapsed}
        />
      </SidebarContent>
    </Sidebar>
  );
}

/* ------------------------------------------------------------------ */
/*  Chat panel                                                         */
/* ------------------------------------------------------------------ */

interface DataSearchChatProps {
  conversationId: string | null;
  workspaces: WorkspaceSummary[];
  selectedWorkspaceId: number | null;
  onWorkspaceChange: (workspaceId: number | null) => void;
  loadingWorkspaces: boolean;
  onConversationCreated: (id: string) => void;
  onMessageComplete: () => void;
}

function DataSearchChat({
  conversationId,
  workspaces,
  selectedWorkspaceId,
  onWorkspaceChange,
  loadingWorkspaces,
  onConversationCreated,
  onMessageComplete,
}: DataSearchChatProps) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connections, setConnections] = useState<ConnectionStatus[]>([]);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(conversationId);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // --- Fetch connections ---
  const fetchConnections = useCallback(async () => {
    try {
      const { data } = await AXIOS_INSTANCE.get('/api/connectors/configurations', {
        params: { is_enabled: true },
      });

      const connectorTypes = new Set(
        (data?.connectors || [])
          .map((c: any) => c.connector_type)
          .filter((value: string | undefined) => !!value)
      );

      const statuses: ConnectionStatus[] = ['hubspot', 'fathom'].map((sourceType) => ({
        source_type: sourceType,
        connected: connectorTypes.has(sourceType),
        auth_method: connectorTypes.has(sourceType) ? 'managed' : undefined,
        status: connectorTypes.has(sourceType) ? 'connected' : 'disconnected',
      }));
      setConnections(statuses);
    } catch {
      setConnections([
        { source_type: 'hubspot', connected: false },
        { source_type: 'fathom', connected: false },
      ]);
    }
  }, []);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  // --- Load conversation history ---
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setActiveConversationId(null);
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);

    (async () => {
      try {
        const { data } = await AXIOS_INSTANCE.get(`/api/retrieval/conversations/${conversationId}`);
        if (cancelled) return;
        if (
          typeof data.workspace_id === 'number' &&
          data.workspace_id !== selectedWorkspaceId
        ) {
          onWorkspaceChange(data.workspace_id);
        }

        const loaded: ChatMessage[] = (data.messages || []).map((m: any) => ({
          id: `db-${m.id}`,
          role: m.role,
          content: m.content,
          sources: m.sources,
          followUps: m.follow_ups,
          runId: m.run_id,
          status: 'completed',
          timestamp: m.created_at || new Date().toISOString(),
        }));
        setMessages(loaded);
        setActiveConversationId(conversationId);
      } catch {
        // conversation might not exist or error
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    })();

    return () => { cancelled = true; };
  }, [conversationId, selectedWorkspaceId, onWorkspaceChange]);

  const isConnected = (src: string) =>
    connections.some((c) => c.source_type === src && c.connected);
  const connectedSources = connections.filter((c) => c.connected);
  const anyConnected = connectedSources.length > 0;

  // --- Submit query ---
  const handleSubmit = useCallback(
    async (query: string) => {
      if (!query.trim() || isSubmitting || !selectedWorkspaceId) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: query.trim(),
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsSubmitting(true);

      try {
        const { data } = await AXIOS_INSTANCE.post('/api/retrieval/search', {
          query: query.trim(),
          workspace_id: selectedWorkspaceId,
          conversation_id: activeConversationId,
        });

        // If we didn't have a conversation yet, the API created one
        if (!activeConversationId && data.conversation_id) {
          setActiveConversationId(data.conversation_id);
          onConversationCreated(data.conversation_id);
        }

        // Add a placeholder assistant message
        const assistantMsg: ChatMessage = {
          id: `asst-${data.run_id}`,
          role: 'assistant',
          content: '',
          runId: data.run_id,
          status: 'queued',
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setPendingRunId(data.run_id);
      } catch (err: any) {
        const errMsg: ChatMessage = {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content:
            err?.response?.data?.detail || 'Failed to submit search. Please try again.',
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errMsg]);
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, selectedWorkspaceId, activeConversationId, onConversationCreated]
  );

  // --- Poll for results ---
  useEffect(() => {
    if (!pendingRunId) return;

    const interval = setInterval(async () => {
      try {
        const { data } = await AXIOS_INSTANCE.get(
          `/api/retrieval/runs/${pendingRunId}`
        );

        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.runId !== pendingRunId) return msg;

            if (data.status === 'completed') {
              return {
                ...msg,
                status: 'completed',
                content: formatResults(data.results),
                sources: data.sources,
                followUps: data.follow_ups || [],
              };
            }
            if (data.status === 'failed') {
              const errorText =
                data.results?.error ||
                data.auth_required?.message ||
                'Search failed. Please try again.';
              return {
                ...msg,
                status: 'failed',
                content: errorText,
              };
            }
            return { ...msg, status: data.status };
          })
        );

        if (['completed', 'failed'].includes(data.status)) {
          clearInterval(interval);
          setPendingRunId(null);
          onMessageComplete();
        }
      } catch {
        clearInterval(interval);
        setPendingRunId(null);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [pendingRunId, onMessageComplete]);

  // --- Auto-scroll ---
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // --- Format results ---
  function formatResults(results: any): string {
    if (!results) return 'No results found.';
    if (typeof results === 'string') return results;
    if (results.raw && typeof results.raw === 'string') return results.raw;
    return JSON.stringify(results, null, 2);
  }

  const showWelcome = messages.length === 0 && !loadingHistory;

  return (
    <div className="flex flex-col h-full">
      <ChatContainer>
        <ChatMessagesPane>
          {/* Header bar with source status */}
          <div className="flex-shrink-0 flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface">
            <div className="flex items-center gap-3 min-w-0">
              <SparklesIcon className="h-5 w-5 text-gray-500 dark:text-gray-400" />
              <h1 className="font-subtitle text-base text-charcoal dark:text-gray-100">
                Data Search
              </h1>
              <div className="ml-2">
                <select
                  value={selectedWorkspaceId ?? ''}
                  onChange={(e) => {
                    const nextWorkspaceId = e.target.value ? Number(e.target.value) : null;
                    onWorkspaceChange(nextWorkspaceId);
                    navigate('/data-search');
                  }}
                  disabled={loadingWorkspaces || workspaces.length === 0}
                  className="h-8 px-2 pr-7 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface text-charcoal dark:text-gray-100 text-xs focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red transition-colors appearance-none bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw2IDZMMTEgMSIgc3Ryb2tlPSIjOEIzQTUyIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==')] bg-[length:10px] bg-[position:right_0.5rem_center] bg-no-repeat"
                >
                  {workspaces.length === 0 && <option value="">No Agent Mesh workspace</option>}
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.display_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-1.5 ml-2">
                {connectedSources.map((c) => (
                  <Badge key={c.source_type} variant="success" className="text-xs">
                    {SOURCE_ICONS[c.source_type]} {SOURCE_LABELS[c.source_type] || c.source_type}
                  </Badge>
                ))}
                {connections
                  .filter((c) => !c.connected)
                  .map((c) => (
                    <Button
                      key={c.source_type}
                      variant="outline"
                      size="sm"
                      onClick={() => navigate('/data-connections')}
                      className="h-6 px-2 text-xs rounded-full border-dashed text-gray-400 dark:text-gray-500"
                    >
                      + {SOURCE_LABELS[c.source_type] || c.source_type}
                    </Button>
                  ))}
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSources(!showSources)}
            >
              <Cog6ToothIcon className="h-4 w-4 mr-1.5" />
              Sources
            </Button>
          </div>

          {/* Sources panel (collapsible) */}
          {showSources && (
            <div className="flex-shrink-0 px-6 py-4 bg-gray-50 dark:bg-dark-bg border-b border-gray-200 dark:border-dark-border">
              <div className="max-w-3xl mx-auto">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {['hubspot', 'fathom'].map((src) => {
                    const connected = isConnected(src);
                    return (
                      <div
                        key={src}
                        className="flex items-center justify-between p-3 bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border"
                      >
                        <div className="flex items-center gap-2.5">
                          {connected ? (
                            <CheckCircleIcon className="h-5 w-5 text-green-500" />
                          ) : (
                            <XCircleIcon className="h-5 w-5 text-gray-400" />
                          )}
                          <div>
                            <p className="text-sm font-medium text-charcoal dark:text-gray-100">
                              {SOURCE_ICONS[src]} {SOURCE_LABELS[src]}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              {connected ? 'Connected' : 'Not connected'}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant={connected ? 'ghost' : 'default'}
                          size="sm"
                          onClick={() => navigate('/data-connections')}
                        >
                          {connected ? 'Reconnect' : 'Connect'}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Messages area */}
          <ChatScrollArea ref={scrollRef}>
            {/* Loading history */}
            {loadingHistory && (
              <div className="text-center py-16">
                <div className="animate-pulse text-sm text-gray-400">Loading conversation...</div>
              </div>
            )}

            {/* Welcome state */}
            {showWelcome && (
              <div className="text-center py-16">
                <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gray-100 dark:bg-dark-surface-2 flex items-center justify-center">
                  <SparklesIcon className="w-8 h-8 text-gray-400 dark:text-gray-500" />
                </div>
                <h2 className="font-title text-h2 text-charcoal dark:text-gray-100 mb-2">
                  Search your data
                </h2>
                <p className="text-body text-gray-500 dark:text-gray-400 mb-8 max-w-md mx-auto">
                  Ask questions about your CRM contacts, meeting transcripts, and more across all connected sources.
                </p>

                {!selectedWorkspaceId && (
                  <Alert variant="warning" className="max-w-md mx-auto mb-4 text-left">
                    Create an Agent Mesh workspace before starting a chat.
                  </Alert>
                )}

                {!anyConnected && (
                  <Alert variant="warning" className="max-w-md mx-auto mb-8 text-left">
                    No data sources connected yet. Connect at least one source to start searching.
                  </Alert>
                )}

                {anyConnected && (
                  <div className="flex flex-wrap justify-center gap-2 max-w-lg mx-auto">
                    {connectedSources.some((c) => c.source_type === 'fathom') && (
                      <>
                        <SuggestionChip text="List my recent meetings" onClick={handleSubmit} />
                        <SuggestionChip text="Meetings with external participants this week" onClick={handleSubmit} />
                        <SuggestionChip text="Get the transcript of the last demo" onClick={handleSubmit} />
                      </>
                    )}
                    {connectedSources.some((c) => c.source_type === 'hubspot') && (
                      <>
                        <SuggestionChip text="Show contacts at Acme Corp" onClick={handleSubmit} />
                        <SuggestionChip text="Recent deals over $50k" onClick={handleSubmit} />
                      </>
                    )}
                  </div>
                )}

                {!anyConnected && (
                  <div className="flex justify-center gap-3 mt-4">
                    {['hubspot', 'fathom'].map((src) => (
                      <Button
                        key={src}
                        variant="outline"
                        onClick={() => navigate('/data-connections')}
                      >
                        <LinkIcon className="h-4 w-4 mr-2" />
                        Connect {SOURCE_LABELS[src]}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Chat messages */}
            {messages.map((msg, idx) => (
              <React.Fragment key={msg.id}>
                <MessageBubble role={msg.role}>
                  {msg.role === 'user' ? (
                    <span>{msg.content}</span>
                  ) : msg.status && !['completed', 'failed'].includes(msg.status) ? (
                    <ThinkingIndicator hideAvatar label={`Searching ${connectedSources.map((c) => SOURCE_LABELS[c.source_type] || c.source_type).join(', ')}...`} />
                  ) : msg.status === 'failed' ? (
                    <div>
                      <Alert variant="error" className="text-sm">
                        {msg.content}
                      </Alert>
                    </div>
                  ) : (
                    <div>
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="flex items-center gap-1.5 mb-3">
                          <span className="text-xs text-gray-400 dark:text-gray-500">Sources:</span>
                          {msg.sources.map((s) => (
                            <Badge key={s} variant="default" className="text-xs">
                              {SOURCE_ICONS[s]} {SOURCE_LABELS[s] || s}
                            </Badge>
                          ))}
                        </div>
                      )}
                      <MessageContent>
                        <Markdown
                          remarkPlugins={[remarkGfm]}
                          components={markdownComponents}
                        >
                          {msg.content}
                        </Markdown>
                      </MessageContent>
                    </div>
                  )}
                </MessageBubble>

                {/* Follow-up question chips (only on the last assistant message) */}
                {msg.role === 'assistant' &&
                  msg.status === 'completed' &&
                  msg.followUps &&
                  msg.followUps.length > 0 &&
                  idx === messages.length - 1 && (
                    <div className="flex flex-wrap gap-2 mt-1 ml-0">
                      {msg.followUps.map((q, i) => (
                        <FollowUpChip key={i} text={q} onClick={handleSubmit} />
                      ))}
                    </div>
                  )}
              </React.Fragment>
            ))}
          </ChatScrollArea>

          {/* Input area */}
          <ChatInputArea>
            <PromptBar
              placeholder={
                !selectedWorkspaceId
                  ? 'Select an Agent Mesh workspace to start...'
                  : anyConnected
                  ? 'Ask about your CRM contacts, meetings, transcripts...'
                  : 'Connect a data source to start searching...'
              }
              onSubmit={handleSubmit}
              disabled={!selectedWorkspaceId}
              loading={isSubmitting || !!pendingRunId}
            />
          </ChatInputArea>
        </ChatMessagesPane>
      </ChatContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Suggestion chip                                                    */
/* ------------------------------------------------------------------ */

function SuggestionChip({
  text,
  onClick,
}: {
  text: string;
  onClick: (text: string) => void;
}) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => onClick(text)}
      className="rounded-full"
    >
      {text}
    </Button>
  );
}

/* ------------------------------------------------------------------ */
/*  Follow-up question chip                                            */
/* ------------------------------------------------------------------ */

function FollowUpChip({
  text,
  onClick,
}: {
  text: string;
  onClick: (text: string) => void;
}) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => onClick(text)}
      className="group rounded-xl text-left hover:border-eliza-red/40 hover:bg-eliza-red/5 dark:hover:bg-eliza-red/10"
    >
      <SparklesIcon className="h-3.5 w-3.5 flex-shrink-0 text-gray-400 dark:text-gray-500 group-hover:text-eliza-red transition-colors" />
      <span>{text}</span>
    </Button>
  );
}

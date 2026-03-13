/**
 * RAGFlow Conversation View
 * 
 * Chat interface for RAGFlow-powered knowledge domains.
 * Uses RAGFlow API for retrieval and chat.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  SparklesIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline';
import { useToasts } from '../../stores/useToasts';
import { Spinner } from '../ui';
import {
  ChatContainer,
  ChatMessagesPane,
  ChatScrollArea,
  ChatInputArea,
  MessageBubble,
  MessageContent,
  ThinkingIndicator,
  ChatProvider,
  CanvasPanel,
  useChat,
  type ExecutionStep,
} from '../ui/chat';
import { PdfCanvasViewer } from '../ui/pdf-canvas-viewer';
import { PromptBar } from '../ui/prompt-bar';
import { InlineCitation } from '../ui/inline-citation';
import { 
  SourcesAccordion, 
  parseSourcesFromSummary,
  buildSourcesFromChunks,
  type Source,
  type CitationValidationResult,
} from '../ui/sources-accordion';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

interface RetrievedChunk {
  content: string;
  document_name: string;
  similarity: number;
  kind?: string;
  metadata?: {
    source?: string;
    follow_ups?: string[];
    tool_calls?: AgentMeshToolCall[];
    failed_tools?: string[];
    sources?: string[];
    [key: string]: any;
  };
}

interface AgentMeshToolCall {
  id?: string;
  tool?: string;
  action?: string | null;
  label?: string;
  status?: 'completed' | 'failed' | 'pending' | 'active';
  description?: string;
  phase?: string;
  iteration?: number;
  step_index?: number;
}

interface AgentMeshMessageMeta {
  followUps: string[];
  toolCalls: AgentMeshToolCall[];
  failedTools: string[];
}

const AGENT_MESH_META_DOC = '__AGENT_MESH_META__';

interface AgentMeshLiveEvent {
  event_id?: string;
  event_type?: string;
  message?: string;
  metadata?: Record<string, any>;
  sequence?: number;
  timestamp?: string;
}

const BASE_STEP_IDS = {
  submitted: 'submitted',
  planning: 'planning',
  tools: 'tools',
  generating: 'generating',
} as const;

function toTitleCase(raw: string): string {
  return raw
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function getFriendlySourceName(raw?: string): string {
  const value = String(raw || '').trim();
  const lower = value.toLowerCase();
  if (!lower) return 'connected data';
  if (lower.includes('hubspot')) return 'HubSpot CRM';
  if (lower.includes('fathom')) return 'meeting notes';
  if (lower.includes('salesforce')) return 'Salesforce CRM';
  return toTitleCase(value);
}

function getFriendlyToolLabel(
  tool?: string,
  action?: string | null,
  sourceHint?: string,
  params?: Record<string, any>,
  rawDescription?: string,
): string {
  const source = getFriendlySourceName(sourceHint || tool);
  const normalizedAction = String(action || '').toLowerCase();
  const normalizedTool = String(tool || '').toLowerCase();
  const hints = getToolCallHints(params, rawDescription);

  if (normalizedTool.includes('fathom')) {
    if (normalizedAction === 'list_meetings') {
      if (hints.query) {
        return `Finding meetings about "${hints.query}"`;
      }
      return 'Finding relevant meetings';
    }
    if (normalizedAction === 'get_summary') {
      if (hints.recordingId) {
        return `Reviewing highlights for meeting #${hints.recordingId}`;
      }
      return 'Reviewing meeting highlights';
    }
    if (normalizedAction === 'get_transcript') return 'Reviewing meeting transcript';
    return 'Checking meeting notes';
  }

  if (normalizedTool.includes('hubspot')) {
    if (hints.query) {
      return `Checking CRM records for "${hints.query}"`;
    }
    return 'Checking HubSpot records';
  }

  return `Checking ${source}`;
}

function getFriendlyToolDescription(
  tool?: string,
  action?: string | null,
  status: 'active' | 'completed' | 'failed' = 'active',
  params?: Record<string, any>,
  rawDescription?: string,
): string {
  const normalizedAction = String(action || '').toLowerCase();
  const normalizedTool = String(tool || '').toLowerCase();
  const hints = getToolCallHints(params, rawDescription);

  if (status === 'failed') {
    if (hints.query) {
      return `Could not fully check "${hints.query}". Continuing with available context.`;
    }
    if (hints.recordingId) {
      return `Could not fully read meeting #${hints.recordingId}. Continuing with available context.`;
    }
    return 'This source could not be read fully. I continued with available context.';
  }

  if (normalizedTool.includes('fathom')) {
    if (normalizedAction === 'list_meetings') {
      if (hints.query) {
        return status === 'completed'
          ? `Meeting notes checked for "${hints.query}".`
          : `Looking through meeting notes for "${hints.query}".`;
      }
      return status === 'completed'
        ? 'Meeting notes checked.'
        : 'Scanning meeting notes for relevant conversations.';
    }
    if (normalizedAction === 'get_summary') {
      if (hints.recordingId) {
        return status === 'completed'
          ? `Highlights captured from meeting #${hints.recordingId}.`
          : `Reading highlights from meeting #${hints.recordingId}.`;
      }
      return status === 'completed'
        ? 'Meeting highlights captured.'
        : 'Reading key highlights from the selected meeting.';
    }
    if (normalizedAction === 'get_transcript') {
      return status === 'completed'
        ? 'Transcript details captured.'
        : 'Reading transcript details for exact context.';
    }
    return status === 'completed'
      ? 'Meeting context captured.'
      : 'Reviewing meeting notes for context.';
  }

  if (normalizedTool.includes('hubspot')) {
    if (hints.query) {
      return status === 'completed'
        ? `CRM context captured for "${hints.query}".`
        : `Looking through CRM records for "${hints.query}".`;
    }
    return status === 'completed'
      ? 'CRM context captured.'
      : 'Looking through CRM data for relevant context.';
  }

  return status === 'completed'
    ? 'Source check complete.'
    : 'Checking connected source data.';
}

function extractQueryFromSearchRequestJson(raw: unknown): string | undefined {
  if (typeof raw !== 'string' || !raw.trim()) {
    return undefined;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') {
      return undefined;
    }
    const queryCandidateKeys = ['query', 'q', 'search', 'term'];
    for (const key of queryCandidateKeys) {
      const value = (parsed as Record<string, any>)[key];
      if (typeof value === 'string' && value.trim()) {
        return value.trim();
      }
    }
    const filterGroups = (parsed as Record<string, any>).filterGroups;
    if (Array.isArray(filterGroups)) {
      for (const group of filterGroups) {
        if (!group || typeof group !== 'object') {
          continue;
        }
        const filters = (group as Record<string, any>).filters;
        if (!Array.isArray(filters)) {
          continue;
        }
        for (const filter of filters) {
          if (!filter || typeof filter !== 'object') {
            continue;
          }
          const value = (filter as Record<string, any>).value;
          if (typeof value === 'string' && value.trim()) {
            return value.trim();
          }
        }
      }
    }
  } catch {
    return undefined;
  }
  return undefined;
}

function getToolCallHints(
  params?: Record<string, any>,
  rawDescription?: string,
): { query?: string; recordingId?: string } {
  let query: string | undefined;
  let recordingId: string | undefined;

  if (params && typeof params === 'object') {
    if (typeof params.search_query === 'string' && params.search_query.trim()) {
      query = params.search_query.trim();
    }
    if (!query) {
      query = extractQueryFromSearchRequestJson(params.search_request_json);
    }
    if (params.recording_id !== undefined && params.recording_id !== null) {
      const candidate = String(params.recording_id).trim();
      if (candidate) {
        recordingId = candidate;
      }
    }
  }

  if (typeof rawDescription === 'string' && rawDescription.trim()) {
    if (!query) {
      const queryMatch = rawDescription.match(/(?:^|\|)\s*query=(.+?)(?:\s*\|\s*|$)/i);
      if (queryMatch?.[1]) {
        query = queryMatch[1].trim();
      }
    }
    if (!recordingId) {
      const recordingMatch = rawDescription.match(/recording_id=(\d+)/i);
      if (recordingMatch?.[1]) {
        recordingId = recordingMatch[1].trim();
      }
    }
  }

  if (query && query.length > 80) {
    query = `${query.slice(0, 77)}...`;
  }

  return { query, recordingId };
}

function getFriendlyLiveProgressLabel(
  eventType: string,
  metadata: Record<string, any>,
): string {
  switch (eventType) {
    case 'submitted':
    case 'run_started':
      return 'Understanding your question';
    case 'planning_started':
      return 'Figuring out where to look';
    case 'planning_completed':
      return 'Plan ready, starting data checks';
    case 'execution_started':
      return 'Gathering details from connected sources';
    case 'tool_started':
      return getFriendlyToolLabel(
        String(metadata.tool || ''),
        typeof metadata.params?.action === 'string' ? metadata.params.action : undefined,
        String(metadata.source || ''),
      );
    case 'tool_completed':
      return 'Captured relevant details';
    case 'tool_failed':
      return 'One source had an issue, continuing with others';
    case 'evaluation_started':
      return 'Checking if the collected context is enough';
    case 'evaluation_completed':
      return metadata.done ? 'Great, we have enough context' : 'Getting a bit more context';
    case 'synthesis_started':
      return 'Putting the answer together';
    case 'synthesis_completed':
      return 'Finalizing the response';
    case 'followups_started':
      return 'Preparing next-question suggestions';
    case 'followups_completed':
      return 'Answer is ready';
    case 'completed':
      return 'Done';
    case 'failed':
      return 'Could not complete this request';
    default:
      return 'Working on your answer';
  }
}

function getToolGroupKey(tool?: string, action?: string | null): string {
  const normalizedTool = String(tool || '').toLowerCase();
  const normalizedAction = String(action || '').toLowerCase();
  if (normalizedTool.includes('fathom') && normalizedAction === 'list_meetings') {
    return 'fathom:list_meetings';
  }
  if (normalizedTool.includes('fathom') && normalizedAction === 'get_summary') {
    return 'fathom:get_summary';
  }
  if (normalizedTool.includes('fathom') && normalizedAction === 'get_transcript') {
    return 'fathom:get_transcript';
  }
  if (normalizedTool.includes('hubspot')) {
    return 'hubspot:search';
  }
  return `${normalizedTool || 'tool'}:${normalizedAction || 'default'}`;
}

function getGroupedLabel(baseLabel: string, count: number): string {
  if (count <= 1) {
    return baseLabel;
  }
  return `${baseLabel} (${count} checks)`;
}

function getGroupedToolDescription(
  queries: string[],
  recordingIds: string[],
  count: number,
  failedCount: number,
  fallbackDescription: string,
): string {
  const prefix =
    failedCount > 0
      ? 'Some checks could not be completed, but available context was used. '
      : '';

  if (recordingIds.length > 0) {
    const preview = recordingIds.slice(0, 4).map((id) => `#${id}`).join(', ');
    const more = recordingIds.length > 4 ? ` +${recordingIds.length - 4} more` : '';
    return `${prefix}Meetings checked: ${preview}${more}.`;
  }

  if (queries.length > 0) {
    const preview = queries.slice(0, 3).map((q) => `"${q}"`).join(', ');
    const more = queries.length > 3 ? ` +${queries.length - 3} more` : '';
    return `${prefix}Focus: ${preview}${more}.`;
  }

  if (count > 1) {
    return `${prefix}Ran ${count} related checks for complete context.`;
  }

  return `${prefix}${fallbackDescription}`;
}

function createInitialLiveSteps(): ExecutionStep[] {
  return [
    {
      id: BASE_STEP_IDS.submitted,
      label: 'Understanding your question',
      status: 'active',
    },
    {
      id: BASE_STEP_IDS.planning,
      label: 'Finding where the answer is',
      status: 'pending',
      description: 'Choosing the best sources to check first.',
    },
    {
      id: BASE_STEP_IDS.tools,
      label: 'Gathering details from your data',
      status: 'pending',
      description: 'Reading connected records and notes.',
    },
    {
      id: BASE_STEP_IDS.generating,
      label: 'Writing your answer',
      status: 'pending',
      description: 'Combining findings into a clear response.',
    },
  ];
}

function updateStepById(
  steps: ExecutionStep[],
  stepId: string,
  patch: Partial<ExecutionStep>,
): ExecutionStep[] {
  return steps.map((step) => (step.id === stepId ? { ...step, ...patch } : step));
}

function upsertStep(
  steps: ExecutionStep[],
  nextStep: ExecutionStep,
  insertBeforeStepId?: string,
): ExecutionStep[] {
  const existingIndex = steps.findIndex((step) => step.id === nextStep.id);
  if (existingIndex === -1) {
    if (insertBeforeStepId) {
      const insertIndex = steps.findIndex((step) => step.id === insertBeforeStepId);
      if (insertIndex >= 0) {
        return [
          ...steps.slice(0, insertIndex),
          nextStep,
          ...steps.slice(insertIndex),
        ];
      }
    }
    return [...steps, nextStep];
  }
  const updated = [...steps];
  updated[existingIndex] = { ...updated[existingIndex], ...nextStep };
  return updated;
}

function markPipelineCompleted(steps: ExecutionStep[]): ExecutionStep[] {
  return steps.map((step) => {
    if (
      step.id === BASE_STEP_IDS.submitted ||
      step.id === BASE_STEP_IDS.planning ||
      step.id === BASE_STEP_IDS.tools ||
      step.id === BASE_STEP_IDS.generating
    ) {
      return {
        ...step,
        status: step.status === 'failed' ? 'failed' : 'completed',
      };
    }
    return step.status === 'active' ? { ...step, status: 'completed' } : step;
  });
}

function getToolStepId(metadata?: Record<string, any>): string {
  const tool = String(metadata?.tool || 'tool');
  const phase = String(metadata?.phase || 'initial');
  const iteration = Number.isFinite(Number(metadata?.iteration)) ? Number(metadata?.iteration) : 0;
  const stepIndex = Number.isFinite(Number(metadata?.step_index)) ? Number(metadata?.step_index) : 0;
  return `tool-${tool}-${phase}-${iteration}-${stepIndex}`;
}

function extractAgentMeshMeta(chunks?: RetrievedChunk[]): AgentMeshMessageMeta {
  const meta: AgentMeshMessageMeta = {
    followUps: [],
    toolCalls: [],
    failedTools: [],
  };

  if (!chunks || chunks.length === 0) {
    return meta;
  }

  for (const chunk of chunks) {
    const chunkMeta = chunk.metadata;
    if (!chunkMeta) {
      continue;
    }

    if (Array.isArray(chunkMeta.follow_ups)) {
      meta.followUps = chunkMeta.follow_ups
        .filter((item) => typeof item === 'string')
        .map((item) => item.trim())
        .filter(Boolean);
    }
    if (Array.isArray(chunkMeta.tool_calls)) {
      meta.toolCalls = chunkMeta.tool_calls.filter((item) => !!item && typeof item === 'object');
    }
    if (Array.isArray(chunkMeta.failed_tools)) {
      meta.failedTools = chunkMeta.failed_tools
        .filter((item) => typeof item === 'string')
        .map((item) => item.trim())
        .filter(Boolean);
    }
  }

  return meta;
}

function buildFallbackFollowUps(
  mainContent: string,
  sourceCount: number,
): string[] {
  const topic = (() => {
    const firstSentence = mainContent
      .replace(/\s+/g, ' ')
      .split(/[.!?]/)
      .map((part) => part.trim())
      .find(Boolean);
    return firstSentence ? firstSentence.slice(0, 64) : 'this';
  })();

  const sourceHint = sourceCount > 0 ? `from the ${sourceCount} cited source${sourceCount === 1 ? '' : 's'}` : 'from connected sources';
  return [
    `Can you verify that ${topic} ${sourceHint}?`,
    `What is the strongest counterpoint to this answer?`,
    `Which next question would reduce uncertainty the most?`,
  ];
}

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  retrieved_chunks?: RetrievedChunk[];
  created_at: string;
}

interface Conversation {
  id: number;
  uuid: string;
  title?: string;
  message_count: number;
}

interface RAGFlowConversationViewProps {
  domainId: number;
  domainName: string;
  /** Optional conversation UUID to load - if not provided, creates a new conversation */
  conversationId?: string;
  /** Enables live Agent Mesh tool-call progress streaming via SSE. */
  enableAgentMeshLiveProgress?: boolean;
  headerContent?: React.ReactNode;
  onBack: () => void;
  /** Called when a new conversation is created, with the UUID */
  onConversationCreated?: (uuid: string) => void;
}

export default function RAGFlowConversationView(props: RAGFlowConversationViewProps) {
  return (
    <ChatProvider>
      <RAGFlowConversationViewInner {...props} />
    </ChatProvider>
  );
}

function RAGFlowConversationViewInner({
  domainId,
  domainName,
  conversationId,
  enableAgentMeshLiveProgress = false,
  headerContent,
  onBack,
  onConversationCreated,
}: RAGFlowConversationViewProps) {
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();
  const chatEndRef = useRef<HTMLDivElement>(null);
  const { setCanvasOpen, setCanvasContent, setCanvasTitle, canvasOpen } = useChat();

  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageInput, setMessageInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [liveExecutionSteps, setLiveExecutionSteps] = useState<ExecutionStep[]>([]);
  const [liveProgressLabel, setLiveProgressLabel] = useState('Processing question...');
  const eventSourceRef = useRef<EventSource | null>(null);

  // Handler for opening PDF in canvas panel.
  // Uses the unified ragflow document endpoint which handles both FASB on-disk
  // PDFs and native RAG documents from object storage.
  const handleShowPdf = useCallback((docId: string, pageNumber: string, highlightText?: string) => {
    setCanvasTitle(`Document ${docId} - Page ${pageNumber}`);
    setCanvasContent(
      <PdfCanvasViewer 
        docId={docId} 
        pageNumber={pageNumber} 
        highlightText={highlightText}
        pdfEndpoint="generic"
      />
    );
    setCanvasOpen(true);
  }, [setCanvasTitle, setCanvasContent, setCanvasOpen]);

  // Scroll to bottom when messages change
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup live stream connection on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  // Initialize conversation - either load existing or create new
  // Uses AbortController + isCancelled flag to prevent double-creation from React StrictMode
  useEffect(() => {
    const abortController = new AbortController();
    let isCancelled = false;

    const initConversation = async () => {
      setIsLoading(true);
      try {
        if (conversationId) {
          // Load specific conversation by UUID
          const res = await fetch(`${API_BASE}/v1/ragflow/conversations/by-uuid/${conversationId}`, {
            headers: { Authorization: `Bearer ${token}` },
            signal: abortController.signal,
          });
          
          if (!isCancelled && res.ok) {
            const data = await res.json();
            setConversation(data.conversation);
            setMessages(data.messages || []);
          } else if (!isCancelled) {
            addToast({ kind: 'error', message: 'Conversation not found' });
            onBack();
          }
        } else {
          // Create a new conversation when no conversationId provided
          const createRes = await fetch(`${API_BASE}/v1/ragflow/domains/${domainId}/conversations`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({}),
            signal: abortController.signal,
          });
          if (!isCancelled && createRes.ok) {
            const newConv = await createRes.json();
            setConversation(newConv);
            setMessages([]);
            // Notify parent to update URL with the new conversation UUID
            if (newConv.uuid && onConversationCreated) {
              onConversationCreated(newConv.uuid);
            }
          } else if (!isCancelled) {
            addToast({ kind: 'error', message: 'Failed to create conversation' });
          }
        }
      } catch (e) {
        // Ignore AbortError from cleanup — this is expected during StrictMode remount
        if (isCancelled || (e instanceof DOMException && e.name === 'AbortError')) {
          return;
        }
        console.error('Failed to initialize conversation:', e);
        addToast({ kind: 'error', message: 'Failed to start conversation' });
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    initConversation();

    // Cleanup: abort in-flight fetch and prevent state updates after unmount
    return () => {
      isCancelled = true;
      abortController.abort();
    };
  }, [domainId, conversationId, token, addToast, onBack, onConversationCreated]);

  // Send message
  const sendMessage = useCallback(async (content: string) => {
    if (!conversation || !content.trim()) return;

    const userContent = content.trim();
    const requestId = enableAgentMeshLiveProgress
      ? (
        typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
          ? crypto.randomUUID()
          : `agent-mesh-${Date.now()}-${Math.random().toString(16).slice(2)}`
      )
      : undefined;

    setMessageInput('');
    setIsSending(true);
    setLiveExecutionSteps(
      enableAgentMeshLiveProgress
        ? createInitialLiveSteps()
        : [
          {
            id: 'submitted',
            label: 'Working on your request',
            status: 'active',
          },
        ]
    );
    setLiveProgressLabel(enableAgentMeshLiveProgress ? 'Understanding your question' : 'Working on your request...');

    // Add optimistic user message
    const tempUserMsg: Message = {
      id: Date.now(),
      role: 'user',
      content: userContent,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      if (enableAgentMeshLiveProgress && token && requestId) {
        const streamUrl =
          `${API_BASE}/v1/ragflow/domains/${domainId}/conversations/${conversation.id}/agent-mesh/stream` +
          `?token=${encodeURIComponent(token)}` +
          `&request_id=${encodeURIComponent(requestId)}`;

        const eventSource = new EventSource(streamUrl);
        eventSourceRef.current = eventSource;

        eventSource.onmessage = (event) => {
          try {
            const liveEvent = JSON.parse(event.data) as AgentMeshLiveEvent;
            const eventType = typeof liveEvent.event_type === 'string' ? liveEvent.event_type : 'progress';
            const metadata = liveEvent.metadata && typeof liveEvent.metadata === 'object' ? liveEvent.metadata : {};
            setLiveProgressLabel(getFriendlyLiveProgressLabel(eventType, metadata));

            setLiveExecutionSteps((prev) => {
              let next = prev.length > 0 ? [...prev] : createInitialLiveSteps();
              switch (eventType) {
                case 'submitted':
                case 'run_started':
                  next = createInitialLiveSteps();
                  break;
                case 'planning_started':
                  next = updateStepById(next, BASE_STEP_IDS.submitted, { status: 'completed' });
                  next = updateStepById(next, BASE_STEP_IDS.planning, { status: 'active' });
                  break;
                case 'planning_completed':
                  next = updateStepById(next, BASE_STEP_IDS.submitted, { status: 'completed' });
                  next = updateStepById(next, BASE_STEP_IDS.planning, { status: 'completed' });
                  next = updateStepById(next, BASE_STEP_IDS.tools, { status: 'pending' });
                  break;
                case 'execution_started':
                  next = updateStepById(next, BASE_STEP_IDS.submitted, { status: 'completed' });
                  next = updateStepById(next, BASE_STEP_IDS.planning, { status: 'completed' });
                  next = updateStepById(next, BASE_STEP_IDS.tools, {
                    status: 'active',
                    description: 'Checking connected records and notes.',
                  });
                  break;
                case 'tool_started': {
                  next = updateStepById(next, BASE_STEP_IDS.tools, { status: 'active' });
                  const params = metadata.params && typeof metadata.params === 'object' ? metadata.params : {};
                  const stepId = getToolStepId(metadata);
                  next = upsertStep(next, {
                    id: stepId,
                    label: getFriendlyToolLabel(
                      String(metadata.tool || ''),
                      typeof params.action === 'string' ? params.action : undefined,
                      String(metadata.source || ''),
                      params,
                      typeof metadata.description === 'string' ? metadata.description : undefined,
                    ),
                    status: 'active',
                    description: getFriendlyToolDescription(
                      String(metadata.tool || ''),
                      typeof params.action === 'string' ? params.action : undefined,
                      'active',
                      params,
                      typeof metadata.description === 'string' ? metadata.description : undefined,
                    ),
                  }, BASE_STEP_IDS.generating);
                  break;
                }
                case 'tool_completed': {
                  const params = metadata.params && typeof metadata.params === 'object' ? metadata.params : {};
                  const stepId = getToolStepId(metadata);
                  next = upsertStep(next, {
                    id: stepId,
                    label: getFriendlyToolLabel(
                      String(metadata.tool || ''),
                      typeof params.action === 'string' ? params.action : undefined,
                      String(metadata.source || ''),
                      params,
                      typeof metadata.description === 'string' ? metadata.description : undefined,
                    ),
                    status: 'completed',
                    description: getFriendlyToolDescription(
                      String(metadata.tool || ''),
                      typeof params.action === 'string' ? params.action : undefined,
                      'completed',
                      params,
                      typeof metadata.description === 'string' ? metadata.description : undefined,
                    ),
                  }, BASE_STEP_IDS.generating);
                  break;
                }
                case 'tool_failed': {
                  const params = metadata.params && typeof metadata.params === 'object' ? metadata.params : {};
                  const stepId = getToolStepId(metadata);
                  next = upsertStep(next, {
                    id: stepId,
                    label: getFriendlyToolLabel(
                      String(metadata.tool || ''),
                      typeof params.action === 'string' ? params.action : undefined,
                      String(metadata.source || ''),
                      params,
                      typeof metadata.description === 'string' ? metadata.description : undefined,
                    ),
                    status: 'failed',
                    description: getFriendlyToolDescription(
                      String(metadata.tool || ''),
                      typeof params.action === 'string' ? params.action : undefined,
                      'failed',
                      params,
                      typeof metadata.description === 'string' ? metadata.description : undefined,
                    ),
                  }, BASE_STEP_IDS.generating);
                  break;
                }
                case 'synthesis_started':
                  next = updateStepById(next, BASE_STEP_IDS.tools, {
                    status: 'completed',
                    description: 'Tool calls finished',
                  });
                  next = updateStepById(next, BASE_STEP_IDS.generating, {
                    status: 'active',
                    description: 'Combining everything into a clear answer.',
                  });
                  break;
                case 'synthesis_completed':
                  next = updateStepById(next, BASE_STEP_IDS.generating, { status: 'completed' });
                  break;
                case 'completed':
                  next = markPipelineCompleted(next);
                  break;
                case 'failed': {
                  const activeStep = next.find((step) => step.status === 'active');
                  if (activeStep) {
                    next = updateStepById(next, activeStep.id, {
                      status: 'failed',
                      description: 'Could not complete this step.',
                    });
                  } else {
                    next = upsertStep(next, {
                      id: 'agent-mesh-failed',
                      label: 'Could not complete request',
                      status: 'failed',
                      description: 'Please retry or narrow the question.',
                    });
                  }
                  break;
                }
                default:
                  break;
              }
              return next;
            });

            if (eventType === 'completed' || eventType === 'failed') {
              eventSource.close();
              if (eventSourceRef.current === eventSource) {
                eventSourceRef.current = null;
              }
            }
          } catch (error) {
            console.error('Failed to parse Agent Mesh SSE event:', error);
          }
        };

        eventSource.onerror = () => {
          if (eventSource.readyState === EventSource.CLOSED) {
            eventSource.close();
            if (eventSourceRef.current === eventSource) {
              eventSourceRef.current = null;
            }
          }
        };
      }

      const res = await fetch(
        `${API_BASE}/v1/ragflow/domains/${domainId}/conversations/${conversation.id}/messages`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            content: userContent,
            ...(requestId ? { request_id: requestId } : {}),
          }),
        }
      );

      if (res.ok) {
        const data = await res.json();
        // Replace optimistic message and add response
        setMessages(prev => [
          ...prev.slice(0, -1),
          data.user_message,
          data.assistant_message,
        ]);
      } else {
        let errorMsg = 'Failed to send message';
        try {
          const error = await res.json();
          errorMsg = error.detail || errorMsg;
          // Check for specific errors
          if (res.status === 404 || errorMsg.includes('not found')) {
            errorMsg = 'Documents are still being indexed. Please wait a moment and try again.';
          } else if (errorMsg.includes('RAGFlow')) {
            errorMsg = 'RAG service error. Documents may still be processing.';
          }
        } catch {
          if (res.status === 404) {
            errorMsg = 'Documents are still being indexed. Please wait a moment and try again.';
          }
        }
        addToast({ kind: 'error', message: errorMsg });
        // Remove optimistic message
        setMessages(prev => prev.slice(0, -1));
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to send message' });
      setMessages(prev => prev.slice(0, -1));
      setLiveProgressLabel('Could not complete your request');
      setLiveExecutionSteps((prev) => {
        const activeStep = prev.find((step) => step.status === 'active');
        if (activeStep) {
          return updateStepById(prev, activeStep.id, {
            status: 'failed',
            description: 'The request failed before completion.',
          });
        }
        return prev;
      });
    } finally {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsSending(false);
      setTimeout(() => {
        setLiveExecutionSteps([]);
      }, 150);
    }
  }, [conversation, domainId, token, addToast, enableAgentMeshLiveProgress]);

  // Handle submit from PromptBar
  const handleSubmit = (value: string) => {
    if (!value.trim() || isSending) return;
    sendMessage(value);
  };

  const latestAssistantMessageId = React.useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'assistant') {
        return messages[i].id;
      }
    }
    return null;
  }, [messages]);

  if (isLoading) {
    return (
      <ChatContainer className="bg-gray-50 dark:bg-dark-bg">
        <ChatMessagesPane>
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <Spinner size="lg" />
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading conversation...</p>
          </div>
        </ChatMessagesPane>
      </ChatContainer>
    );
  }

  return (
    <ChatContainer className="bg-gray-50 dark:bg-dark-bg">
      <ChatMessagesPane>
        {/* Minimal header with back button */}
        <div className="absolute top-0 left-0 right-0 z-20 px-4 py-2.5 bg-white/80 dark:bg-dark-surface/80 backdrop-blur-sm border-b border-gray-100 dark:border-dark-border/20">
          <div className="flex items-center gap-2">
            <button
              onClick={onBack}
              className="p-1.5 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-surface-2 rounded-md transition-colors"
            >
              <ArrowLeftIcon className="w-4 h-4" />
            </button>
            <span className="text-small font-medium text-gray-600 dark:text-gray-300">{domainName}</span>
            {headerContent && (
              <div className="ml-auto pointer-events-auto">{headerContent}</div>
            )}
          </div>
        </div>

        {/* Messages */}
        <ChatScrollArea>
          {/* Spacer for header */}
          <div className="h-12 flex-shrink-0" />

          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center max-w-md">
                <SparklesIcon className="w-12 h-12 mb-4 mx-auto opacity-20" />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Ask questions about your documents and I'll provide answers with sources.
                </p>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} role={msg.role} showAvatar={msg.role === 'assistant'}>
                <MessageContent>
                  {msg.role === 'assistant' ? (
                    <AssistantMessageContent 
                      content={msg.content} 
                      chunks={msg.retrieved_chunks}
                      onShowPdf={handleShowPdf}
                      onFollowUpClick={handleSubmit}
                      isLatestAssistant={msg.id === latestAssistantMessageId}
                    />
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </MessageContent>
              </MessageBubble>
            ))
          )}

          {/* Thinking indicator with RAG flow stages */}
          {isSending && (
            <MessageBubble role="assistant" showAvatar>
              <ThinkingIndicator 
                label={liveProgressLabel || 'Processing question...'}
                hideAvatar 
                steps={liveExecutionSteps}
                stepsDefaultExpanded={true}
              />
            </MessageBubble>
          )}

          <div ref={chatEndRef} />
        </ChatScrollArea>

        {/* Input */}
        <ChatInputArea>
          <PromptBar
            value={messageInput}
            onChange={setMessageInput}
            onSubmit={handleSubmit}
            placeholder={`Ask a question about ${domainName}...`}
            loading={isSending}
            disabled={!conversation}
          />
        </ChatInputArea>
      </ChatMessagesPane>

      {/* PDF Canvas Panel */}
      {canvasOpen && <CanvasPanel />}
    </ChatContainer>
  );
}

/**
 * Assistant message content with parsed sources and validation.
 * Works uniformly for FASB and native RAG workspaces.
 */
function AssistantMessageContent({ 
  content, 
  chunks,
  onShowPdf,
  onFollowUpClick,
  isLatestAssistant,
}: { 
  content: string; 
  chunks?: RetrievedChunk[];
  onShowPdf?: (docId: string, pageNumber: string, highlightText?: string) => void;
  onFollowUpClick?: (value: string) => void;
  isLatestAssistant?: boolean;
}) {
  const token = localStorage.getItem('auth_token');
  
  // Parse sources from the text content (FASB format: "\n\nSources:\n[1] doc:...")
  const { mainContent, sources: textParsedSources } = React.useMemo(
    () => parseSourcesFromSummary(content),
    [content]
  );

  // Build full sources list, then filter to only those cited in the answer
  const sources: Source[] = React.useMemo(() => {
    const allSources = textParsedSources.length > 0
      ? textParsedSources
      : (!chunks || chunks.length === 0 ? [] : buildSourcesFromChunks(chunks));

    // Extract citation indices referenced in the answer text, e.g. [1], [3]
    const citedIndices = new Set<number>();
    const citationRe = /\[(\d+)\]/g;
    let m: RegExpExecArray | null;
    while ((m = citationRe.exec(mainContent)) !== null) {
      citedIndices.add(parseInt(m[1], 10));
    }

    if (citedIndices.size === 0) return allSources;
    return allSources.filter(s => citedIndices.has(s.index));
  }, [textParsedSources, chunks, mainContent]);
  
  const agentMeshMeta = React.useMemo(
    () => extractAgentMeshMeta(chunks),
    [chunks]
  );

  const hasAgentMeshMeta = React.useMemo(() => {
    if (!chunks || chunks.length === 0) {
      return false;
    }
    return chunks.some(
      (chunk) =>
        chunk.kind === 'agent_mesh_meta' ||
        chunk.document_name === AGENT_MESH_META_DOC
    );
  }, [chunks]);

  const executionSteps = React.useMemo(() => {
    const sortedCalls = [...agentMeshMeta.toolCalls].sort((a, b) => {
      const aIteration = typeof a.iteration === 'number' ? a.iteration : 0;
      const bIteration = typeof b.iteration === 'number' ? b.iteration : 0;
      if (aIteration !== bIteration) {
        return aIteration - bIteration;
      }
      const aStep = typeof a.step_index === 'number' ? a.step_index : 0;
      const bStep = typeof b.step_index === 'number' ? b.step_index : 0;
      return aStep - bStep;
    });

    type GroupedToolStep = {
      groupKey: string;
      toolName: string;
      actionName?: string;
      count: number;
      completedCount: number;
      failedCount: number;
      firstLabel: string;
      firstDescription: string;
      queries: Set<string>;
      recordingIds: Set<string>;
      firstIndex: number;
    };

    const groupedSteps = new Map<string, GroupedToolStep>();
    const orderedGroupKeys: string[] = [];

    sortedCalls.forEach((call, index) => {
      const callStatus = call.status === 'failed' ? 'failed' : 'completed';
      const fallbackToolFromLabel =
        typeof call.label === 'string' && call.label.includes('.')
          ? call.label.split('.')[0]
          : call.label;
      const fallbackActionFromLabel =
        typeof call.label === 'string' && call.label.includes('.')
          ? call.label.split('.').slice(1).join('.')
          : undefined;
      const toolName = call.tool || fallbackToolFromLabel || '';
      const actionName = call.action || fallbackActionFromLabel || undefined;
      const hints = getToolCallHints(undefined, call.description);
      const groupKey = getToolGroupKey(toolName, actionName);

      const specificLabel = getFriendlyToolLabel(
        toolName,
        actionName,
        toolName,
        undefined,
        call.description,
      );
      const specificDescription = getFriendlyToolDescription(
        toolName,
        actionName,
        callStatus === 'failed' ? 'failed' : 'completed',
        undefined,
        call.description,
      );

      const existing = groupedSteps.get(groupKey);
      if (!existing) {
        groupedSteps.set(groupKey, {
          groupKey,
          toolName,
          actionName,
          count: 1,
          completedCount: callStatus === 'completed' ? 1 : 0,
          failedCount: callStatus === 'failed' ? 1 : 0,
          firstLabel: specificLabel,
          firstDescription: specificDescription,
          queries: new Set(hints.query ? [hints.query] : []),
          recordingIds: new Set(hints.recordingId ? [hints.recordingId] : []),
          firstIndex: index,
        });
        orderedGroupKeys.push(groupKey);
        return;
      }

      existing.count += 1;
      if (callStatus === 'completed') {
        existing.completedCount += 1;
      } else {
        existing.failedCount += 1;
      }
      if (hints.query) {
        existing.queries.add(hints.query);
      }
      if (hints.recordingId) {
        existing.recordingIds.add(hints.recordingId);
      }
    });

    return orderedGroupKeys
      .map((groupKey) => groupedSteps.get(groupKey))
      .filter((group): group is GroupedToolStep => Boolean(group))
      .sort((a, b) => a.firstIndex - b.firstIndex)
      .map((group, index) => {
        const baseLabel = getFriendlyToolLabel(
          group.toolName,
          group.actionName,
          group.toolName,
        );
        const status: ExecutionStep['status'] =
          group.completedCount > 0 ? 'completed' : 'failed';

        if (group.count === 1) {
          return {
            id: `group-${group.groupKey}-${index + 1}`,
            label: group.firstLabel,
            status,
            description: group.firstDescription,
          } as ExecutionStep;
        }

        return {
          id: `group-${group.groupKey}-${index + 1}`,
          label: getGroupedLabel(baseLabel, group.count),
          status,
          description: getGroupedToolDescription(
            Array.from(group.queries),
            Array.from(group.recordingIds),
            group.count,
            group.failedCount,
            group.firstDescription,
          ),
        } as ExecutionStep;
      });
  }, [agentMeshMeta.toolCalls]);

  const executionSummaryLabel = React.useMemo(() => {
    if (executionSteps.length === 0) {
      return 'Answer ready';
    }
    const failedCount = executionSteps.filter((step) => step.status === 'failed').length;
    if (failedCount > 0) {
      return 'Answer prepared with partial source coverage';
    }
    return `Checked ${executionSteps.length} data step${executionSteps.length === 1 ? '' : 's'} to build this answer`;
  }, [executionSteps]);

  const followUpSuggestions = React.useMemo(() => {
    if (agentMeshMeta.followUps.length > 0) {
      return agentMeshMeta.followUps.slice(0, 3);
    }
    if (!hasAgentMeshMeta) {
      return [];
    }
    return buildFallbackFollowUps(mainContent, sources.length);
  }, [agentMeshMeta.followUps, hasAgentMeshMeta, mainContent, sources.length]);

  // Build a map from citation index to chunk text for validation
  const chunkTextMap = React.useMemo(() => {
    const map: Record<number, string> = {};
    if (chunks) {
      const nonMetaChunks = chunks.filter(
        (chunk) => !(chunk.kind === 'agent_mesh_meta' || chunk.document_name === AGENT_MESH_META_DOC)
      );
      nonMetaChunks.forEach((chunk, idx) => {
        map[idx + 1] = chunk.content;
      });
    }
    return map;
  }, [chunks]);
  
  // Citation validation handler - uses fallback mode with citation + chunk_text
  const handleValidateCitation = useCallback(async (citationIndex: number): Promise<CitationValidationResult> => {
    if (!token) {
      throw new Error('Not authenticated');
    }
    
    const source = sources.find(s => s.index === citationIndex);
    if (!source) {
      throw new Error('Citation not found');
    }
    
    const chunkText = chunkTextMap[citationIndex] || source.highlightText;
    if (!chunkText) {
      throw new Error('Chunk text not available for validation');
    }
    
    const pages = source.pages || "1-1";
    const citation = source.rawCitation || 
      `doc:${source.docId} pages:${pages} chunk:${source.chunkId} section:${source.sectionTitle}`;
    
    const response = await fetch(`${API_BASE}/api/v1/rag-eval/citations/validate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        citation: citation,
        chunk_text: chunkText,
        question: '',
        answer: mainContent,
      }),
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Validation failed (${response.status})`);
    }
    
    const data = await response.json();
    return data.result;
  }, [token, sources, chunkTextMap, mainContent]);
  
  // Build a map from citation index to source data for quick lookup
  const sourcesMap = React.useMemo(() => {
    const map: Record<number, Source> = {};
    sources.forEach(s => { map[s.index] = s; });
    return map;
  }, [sources]);
  
  // Helper to render text with clickable citation badges
  const renderWithCitations = React.useCallback((text: string): React.ReactNode => {
    const parts = text.split(/(\[\d+\])/g);
    if (parts.length === 1) return text;
    
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const citationIndex = parseInt(match[1], 10);
        const source = sourcesMap[citationIndex];
        
        return (
          <InlineCitation
            key={i}
            number={citationIndex}
            docId={source?.docId}
            pageNumber={source?.pages}
            sectionTitle={source?.sectionTitle}
            interactive={!!source && !!onShowPdf}
            onClick={() => {
              if (source && onShowPdf) {
                onShowPdf(source.docId, source.pages || "1", source.highlightText || source.sectionTitle);
              }
            }}
          />
        );
      }
      return part;
    });
  }, [sourcesMap, onShowPdf]);

  // Process all text nodes recursively to add citation styling
  const processNode = React.useCallback((node: React.ReactNode): React.ReactNode => {
    if (typeof node === 'string') {
      return renderWithCitations(node);
    }
    if (Array.isArray(node)) {
      return node.map((child, i) => <React.Fragment key={i}>{processNode(child)}</React.Fragment>);
    }
    if (React.isValidElement(node)) {
      const children = (node.props as { children?: React.ReactNode }).children;
      if (children) {
        return React.cloneElement(node, {}, processNode(children));
      }
    }
    return node;
  }, [renderWithCitations]);
  
  return (
    <div className="space-y-3">
      {/* Keep execution trace near the top so the position is stable from live to final */}
      {executionSteps.length > 0 && (
        <div className="pt-1">
          <ThinkingIndicator
            hideAvatar
            label="How this answer was built"
            isComplete={true}
            completeLabel={executionSummaryLabel}
            steps={executionSteps}
            stepsDefaultExpanded={true}
          />
        </div>
      )}

      {/* Main content with markdown rendering */}
      <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-pre:my-2 prose-code:text-pink-600 dark:prose-code:text-pink-400 prose-code:bg-gray-100 dark:prose-code:bg-dark-surface-2 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:before:content-none prose-code:after:content-none prose-pre:bg-gray-900 dark:prose-pre:bg-black prose-pre:text-gray-100 prose-a:text-violet-600 dark:prose-a:text-violet-400 prose-strong:text-charcoal dark:prose-strong:text-white">
        <ReactMarkdown
          components={{
            p: ({ children }) => <p>{processNode(children)}</p>,
            li: ({ children }) => <li>{processNode(children)}</li>,
            strong: ({ children }) => <strong>{processNode(children)}</strong>,
            em: ({ children }) => <em>{processNode(children)}</em>,
          }}
        >
          {mainContent}
        </ReactMarkdown>
      </div>
      
      {/* Sources accordion with validation */}
      {sources.length > 0 && (
        <SourcesAccordion
          sources={sources}
          onValidateCitation={handleValidateCitation}
          onShowPdf={onShowPdf}
          showPdfButtons={!!onShowPdf}
          showValidateButtons={true}
        />
      )}

      {/* Agent Mesh follow-up suggestions */}
      {isLatestAssistant && onFollowUpClick && followUpSuggestions.length > 0 && (
        <div className="pt-2">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
            Suggested follow-up questions
          </p>
          <div className="flex flex-wrap gap-2">
            {followUpSuggestions.map((question, index) => (
              <button
                key={`${question}-${index}`}
                onClick={() => onFollowUpClick(question)}
                className="text-xs px-3 py-1.5 rounded-full border border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface-2 text-gray-600 dark:text-gray-300 hover:border-violet-300 dark:hover:border-violet-500 hover:text-violet-700 dark:hover:text-violet-300 transition-colors text-left"
              >
                {question}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * DomainChatPage - RAG Chat with URL structure /:domainName/:conversationUuid
 * 
 * Handles both new conversations (no UUID) and existing ones.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  PaperAirplaneIcon,
  ArrowLeftIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import { Layout } from '../../components/layout/Layout';
import { useToasts } from '../../stores/useToasts';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { AXIOS_INSTANCE } from '../../services/api-client';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  retrieved_chunks?: any[];
}

interface Conversation {
  id: number;
  uuid: string;
  domain_id: number;
  title: string;
  message_count: number;
}

interface Domain {
  id: number;
  name: string;
  display_name: string;
  description?: string;
}

export default function DomainChatPage() {
  const { domainName, conversationUuid } = useParams<{ domainName: string; conversationUuid?: string }>();
  const navigate = useNavigate();
  const { push: addToast } = useToasts();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [domain, setDomain] = useState<Domain | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);

  // Fetch domain by name
  const fetchDomain = useCallback(async () => {
    if (!domainName) return null;

    try {
      const res = await AXIOS_INSTANCE.get(`/v1/ragflow/domains/by-name/${domainName}`);
      return res.data;
    } catch (e) {
      console.error('Failed to fetch domain:', e);
      addToast({ kind: 'error', message: 'Domain not found' });
      navigate('/domains');
      return null;
    }
  }, [domainName, navigate, addToast]);

  // Fetch conversation by UUID
  const fetchConversation = useCallback(async () => {
    if (!conversationUuid) return null;

    try {
      const res = await AXIOS_INSTANCE.get(`/v1/ragflow/conversations/by-uuid/${conversationUuid}`);
      return {
        conversation: res.data?.conversation,
        messages: res.data?.messages || [],
      };
    } catch (e) {
      console.error('Failed to fetch conversation:', e);
      return null;
    }
  }, [conversationUuid]);

  // Create new conversation
  const createConversation = useCallback(async (domainId: number): Promise<Conversation | null> => {
    try {
      const res = await AXIOS_INSTANCE.post(`/v1/ragflow/domains/${domainId}/conversations`, {
        title: 'New Chat',
      });
      return res.data;
    } catch (e) {
      console.error('Failed to create conversation:', e);
      return null;
    }
  }, []);

  // Initialize
  useEffect(() => {
    const init = async () => {
      setIsLoading(true);

      const domainData = await fetchDomain();
      if (!domainData) {
        setIsLoading(false);
        return;
      }
      setDomain(domainData);

      if (conversationUuid) {
        // Load existing conversation
        const convData = await fetchConversation();
        if (convData) {
          setConversation(convData.conversation);
          setMessages(convData.messages);
        } else {
          addToast({ kind: 'error', message: 'Conversation not found' });
          navigate(`/${domainName}`);
        }
      }

      setIsLoading(false);
    };

    init();
  }, [domainName, conversationUuid, fetchDomain, fetchConversation, navigate, addToast]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message
  const handleSend = async () => {
    if (!inputValue.trim() || isSending || !domain) return;

    const messageContent = inputValue.trim();
    setInputValue('');
    setIsSending(true);

    // Add user message optimistically
    const tempUserMsg: Message = {
      id: Date.now(),
      role: 'user',
      content: messageContent,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      let activeConversation = conversation;

      // Create conversation if this is the first message
      if (!activeConversation) {
        activeConversation = await createConversation(domain.id);
        if (!activeConversation) {
          addToast({ kind: 'error', message: 'Failed to create conversation' });
          setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
          setIsSending(false);
          return;
        }
        setConversation(activeConversation);
        // Update URL to include the new conversation UUID
        navigate(`/${domainName}/${activeConversation.uuid}`, { replace: true });
      }

      // Send message
      const res = await AXIOS_INSTANCE.post(
        `/v1/ragflow/domains/${domain.id}/conversations/${activeConversation.id}/messages`,
        { content: messageContent }
      );
      const data = res.data;
      // Replace temp message and add assistant response
      setMessages(prev => [
        ...prev.filter(m => m.id !== tempUserMsg.id),
        {
          id: data.user_message.id,
          role: 'user',
          content: data.user_message.content,
          created_at: data.user_message.created_at,
        },
        {
          id: data.assistant_message.id,
          role: 'assistant',
          content: data.assistant_message.content,
          created_at: data.assistant_message.created_at,
          retrieved_chunks: data.assistant_message.retrieved_chunks,
        },
      ]);
    } catch (e) {
      console.error('Send failed:', e);
      addToast({ kind: 'error', message: 'Failed to send message' });
      setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id));
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  // Handle Enter key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isLoading) {
    return (
      <Layout pageTitle="Chat">
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner size="lg" message="Loading chat..." />
        </div>
      </Layout>
    );
  }

  return (
    <Layout pageTitle={domain?.display_name || 'Chat'}>
      <div className="flex-1 flex flex-col h-full bg-gray-50 dark:bg-dark-bg">
        {/* Header */}
        <div className="bg-white dark:bg-dark-surface border-b border-gray-200 dark:border-dark-border px-6 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/domains')}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-dark-surface-2 rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-semibold text-charcoal dark:text-white">
                {domain?.display_name || domain?.name}
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {conversation?.title || 'New conversation'}
              </p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <h3 className="text-lg font-medium text-gray-500 dark:text-gray-400">
                Start a conversation
              </h3>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                Ask questions about documents in {domain?.display_name}
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-violet-600 text-white'
                      : 'bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border'
                  }`}
                >
                  <p className={`text-sm whitespace-pre-wrap ${
                    msg.role === 'assistant' ? 'text-charcoal dark:text-white' : ''
                  }`}>
                    {msg.content}
                  </p>
                  {msg.retrieved_chunks && msg.retrieved_chunks.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200 dark:border-dark-border">
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                        Sources ({msg.retrieved_chunks.length})
                      </p>
                      <div className="space-y-1">
                        {msg.retrieved_chunks.slice(0, 3).map((chunk, i) => (
                          <div key={i} className="text-xs text-gray-400 dark:text-gray-500 truncate">
                            • {chunk.metadata?.filename || chunk.metadata?.source || chunk.document_name || `Chunk ${i + 1}`}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-white dark:bg-dark-surface border-t border-gray-200 dark:border-dark-border p-4">
          <div className="flex items-end gap-3 max-w-4xl mx-auto">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question..."
              rows={1}
              className="flex-1 resize-none rounded-lg border border-gray-300 dark:border-dark-border bg-white dark:bg-dark-surface-2 px-4 py-3 text-sm text-charcoal dark:text-white placeholder-gray-400 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 outline-none"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isSending}
              className="p-3 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSending ? (
                <LoadingSpinner size="xs" variant="white" />
              ) : (
                <PaperAirplaneIcon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
}

/**
 * Message Thread Component
 * Displays messages within a selected conversation
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  useSubmitQuestionV1DataAnalystQuestionsPost,
  useListQuestionsV1DataAnalystQuestionsGet,
} from '../../generated/data-analyst/data-analyst';
import { DataSourceType } from '../../generated/models';
import { ChatBubbleLeftIcon, CheckCircleIcon, XCircleIcon, ClockIcon } from '@heroicons/react/24/outline';

interface MessageThreadProps {
  conversationId: string | null;
  dataSourceType: DataSourceType;
  onMessageSelected: (messageId: string) => void;
  selectedMessageId: string | null;
}

export default function MessageThread({
  conversationId,
  dataSourceType,
  onMessageSelected,
  selectedMessageId,
}: MessageThreadProps) {
  const [message, setMessage] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const { mutate: submitQuestion, isPending } = useSubmitQuestionV1DataAnalystQuestionsPost();
  
  // Fetch messages for this conversation
  const { data: messagesData } = useListQuestionsV1DataAnalystQuestionsGet({
    data_source_type: dataSourceType,
    conversation_id: conversationId || undefined,
    page: 1,
    page_size: 100,
  }, {
    query: {
      refetchInterval: 3000, // Poll for status updates
      enabled: !!conversationId, // Only fetch if conversation is selected
    },
  });

  // Scroll to bottom when new messages are added
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messagesData?.questions]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isPending || !conversationId) return;

    submitQuestion(
      {
        data: {
          data_source_type: dataSourceType,
          question: message.trim(),
          conversation_id: conversationId,
        },
      },
      {
        onSuccess: (response) => {
          onMessageSelected(response.question_id);
          setMessage('');
        },
        onError: (error) => {
          console.error('Failed to submit question:', error);
        },
      }
    );
  };

  const messages = messagesData?.questions || [];

  // Status icon helper
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircleIcon className="w-4 h-4 text-red-500" />;
      case 'processing':
        return <ClockIcon className="w-4 h-4 text-blue-500 animate-pulse" />;
      default:
        return <ClockIcon className="w-4 h-4 text-gray-500" />;
    }
  };

  // No conversation selected state
  if (!conversationId) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-bg text-muted/50">
        <ChatBubbleLeftIcon className="w-12 h-12 mb-3 opacity-20" />
        <p className="text-sm">No conversation selected</p>
        <p className="text-xs mt-1 text-muted/40">Select or create one to get started</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted/50">
            <div className="text-center">
              <p className="text-sm mb-1">Start the conversation</p>
              <p className="text-xs text-muted/40">Ask a question about your data below</p>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.question_id}
              onClick={() => onMessageSelected(msg.question_id)}
              className={`group cursor-pointer transition-all ${
                selectedMessageId === msg.question_id
                  ? 'pl-4 border-l-2 border-brand'
                  : 'pl-4 border-l-2 border-transparent hover:border-border/40'
              }`}
            >
              {/* Question */}
              <div className="space-y-3">
                <p className="text-sm text-text leading-relaxed">
                  {msg.original_question}
                </p>

                {/* Status and Timestamp */}
                <div className="flex items-center gap-3 text-xs">
                  <div className={`flex items-center gap-1.5 ${
                    msg.status === 'completed' ? 'text-green-600' :
                    msg.status === 'processing' ? 'text-blue-600' :
                    msg.status === 'failed' ? 'text-red-600' :
                    'text-gray-600'
                  }`}>
                    {getStatusIcon(msg.status)}
                    <span className="font-medium capitalize">{msg.status}</span>
                  </div>
                  <span className="text-muted/50">
                    {new Date(msg.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                  </span>
                </div>

                {/* Show result preview if completed */}
                {msg.status === 'completed' && (
                  <div className="pt-2">
                    <p className="text-xs text-brand/70">
                      View results →
                    </p>
                  </div>
                )}

                {/* Show error if failed */}
                {msg.status === 'failed' && (
                  <div className="pt-2">
                    <p className="text-xs text-red-500/70">
                      View error details →
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Message Input */}
      <form onSubmit={handleSubmit} className="p-6 border-t border-border/20 bg-bg">
        <div className="flex gap-3">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask a question about your data..."
            className="flex-1 px-4 py-3 border-0 rounded-lg bg-bg/50 text-text placeholder-muted/50 focus:outline-none focus:ring-1 focus:ring-brand/30 focus:bg-bg transition-all text-sm"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={isPending || !message.trim()}
            className="px-6 py-3 bg-brand text-white rounded-lg font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-brand/90 transition-all text-sm shadow-sm"
          >
            {isPending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  );
}


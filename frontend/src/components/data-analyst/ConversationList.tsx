/**
 * Conversation List Component
 * Displays list of conversations with "New Conversation" buttons
 */
import React, { useState } from 'react';
import { DataSourceType } from '../../generated/models';
import {
  useListConversationsV1DataAnalystConversationsGet,
  useCreateConversationV1DataAnalystConversationsPost,
  useDeleteConversationV1DataAnalystConversationsConversationIdDelete,
} from '../../generated/data-analyst/data-analyst';
import {  ChatBubbleLeftEllipsisIcon, PlusIcon, UsersIcon, TrashIcon } from '@heroicons/react/24/outline';
import Card from '../../shared/ui/Card';

interface ConversationListProps {
  dataSourceType: DataSourceType;
  selectedConversationId: string | null;
  onConversationSelected: (conversationId: string) => void;
}

export default function ConversationList({
  dataSourceType,
  selectedConversationId,
  onConversationSelected,
}: ConversationListProps) {
  const { data: conversationsData, refetch } = useListConversationsV1DataAnalystConversationsGet({
    data_source_type: dataSourceType,
    page: 1,
    page_size: 50,
  }, {
    query: {
      refetchInterval: 5000, // Refresh list every 5 seconds
    },
  });

  const { mutate: createConversation, isPending: isCreatingConversation } = 
    useCreateConversationV1DataAnalystConversationsPost();
  
  const { mutate: deleteConversation } = 
    useDeleteConversationV1DataAnalystConversationsConversationIdDelete();

  const handleCreateConversation = (isGroup: boolean) => {
    createConversation(
      {
        data: {
          data_source_type: dataSourceType,
          conversation_type: isGroup ? 'group' : 'user',
          title: undefined,
          participant_ids: undefined,
        },
      },
      {
        onSuccess: (response) => {
          refetch();
          onConversationSelected(response.conversation_id);
        },
        onError: (error) => {
          console.error('Failed to create conversation:', error);
        },
      }
    );
  };

  const handleDeleteConversation = (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent conversation selection
    
    if (!window.confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    deleteConversation(
      { conversationId },
      {
        onSuccess: () => {
          refetch();
          // If the deleted conversation was selected, clear selection
          if (selectedConversationId === conversationId) {
            onConversationSelected('');
          }
        },
        onError: (error) => {
          console.error('Failed to delete conversation:', error);
        },
      }
    );
  };

  const conversations = conversationsData?.conversations || [];

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* Header with action buttons */}
      <div className="p-4 space-y-2">
        <h2 className="text-[10px] font-semibold text-muted uppercase tracking-wider mb-3">Conversations</h2>
        
        {/* Compact pill buttons */}
        <div className="flex gap-2">
          {/* New Conversation Button - Compact pill */}
          <button
            onClick={() => handleCreateConversation(false)}
            disabled={isCreatingConversation}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-brand text-white rounded-full hover:bg-brand/90 transition-all text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <PlusIcon className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>

          {/* New Group Button - Compact pill */}
          <button
            onClick={() => handleCreateConversation(true)}
            disabled={isCreatingConversation}
            className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-surface-2 text-muted hover:text-text rounded-full hover:bg-surface-3 transition-all text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            title="New Group Conversation"
          >
            <UsersIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-4 py-2">
        {conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted/50 px-4">
            <ChatBubbleLeftEllipsisIcon className="w-10 h-10 mb-3 opacity-30" />
            <p className="text-center text-xs">No conversations yet</p>
            <p className="text-center text-xs mt-1 text-muted/40">
              Create one to get started
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {conversations.map((conv) => (
              <div
                key={conv.conversation_id}
                onClick={() => onConversationSelected(conv.conversation_id)}
                className={`group relative px-4 py-3 rounded-xl cursor-pointer transition-all ${
                  selectedConversationId === conv.conversation_id
                    ? 'bg-brand/10 text-brand shadow-sm'
                    : 'hover:bg-surface-2 text-text'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    {/* Conversation Title */}
                    <div className="flex items-center gap-2 mb-1">
                      {conv.conversation_type === 'group' && (
                        <UsersIcon className="w-3.5 h-3.5 text-muted/60 flex-shrink-0" />
                      )}
                      <h3 className="text-sm font-medium truncate">
                        {conv.title || `Conversation ${conv.conversation_id.slice(-6)}`}
                      </h3>
                    </div>

                    {/* Latest Message Preview */}
                    {conv.latest_message && (
                      <p className="text-xs text-muted truncate mb-1.5">
                        {conv.latest_message}
                      </p>
                    )}

                    {/* Metadata */}
                    <div className="flex items-center gap-3 text-[10px] text-muted/50 uppercase tracking-wider">
                      <span>{conv.message_count} msg</span>
                      {conv.last_activity_at && (
                        <span>
                          {new Date(conv.last_activity_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={(e) => handleDeleteConversation(conv.conversation_id, e)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 hover:bg-red-500/10 rounded-full"
                    title="Delete conversation"
                  >
                    <TrashIcon className="w-3.5 h-3.5 text-red-500/70" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


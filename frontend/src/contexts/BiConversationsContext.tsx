/**
 * BI Conversations Context
 * 
 * Manages conversation state for the Business Intelligence / Data Analyst feature.
 * Allows the sidebar and main page to share conversation selection state.
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import { DataSourceType } from '../generated/models';
import {
  useListConversationsV1DataAnalystConversationsGet,
  useCreateConversationV1DataAnalystConversationsPost,
  useDeleteConversationV1DataAnalystConversationsConversationIdDelete,
} from '../generated/data-analyst/data-analyst';

/* ============================================
   Types
   ============================================ */

interface Conversation {
  conversation_id: string;
  title?: string | null;
  latest_message?: string | null;
  message_count?: number;
  last_activity_at?: string | null;
  conversation_type?: string | null;
  data_source_type?: string | null;
}

interface BiConversationsContextValue {
  // State
  selectedDataSource: DataSourceType | null;
  selectedConversationId: string | null;
  conversations: Conversation[];
  isLoading: boolean;
  isCreating: boolean;

  // Actions
  setSelectedDataSource: (source: DataSourceType | null) => void;
  setSelectedConversationId: (id: string | null) => void;
  createConversation: (isGroup?: boolean) => void;
  deleteConversation: (id: string) => void;
  clearSelection: () => void;
  refetchConversations: () => void;
}

/* ============================================
   Context
   ============================================ */

const BiConversationsContext = createContext<BiConversationsContextValue | undefined>(undefined);

/* ============================================
   Provider
   ============================================ */

interface BiConversationsProviderProps {
  children: ReactNode;
}

export function BiConversationsProvider({ children }: BiConversationsProviderProps) {
  const [selectedDataSource, setSelectedDataSource] = useState<DataSourceType | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const hasInitialized = useRef(false);

  // Fetch ALL conversations on initial load (to auto-select most recent)
  const { data: allConversationsData, isLoading: isLoadingAll } = useListConversationsV1DataAnalystConversationsGet(
    {
      page: 1,
      page_size: 50,
    },
    {
      query: {
        enabled: !hasInitialized.current, // Only on initial load
      },
    }
  );

  // Auto-select most recent conversation on initial load
  useEffect(() => {
    if (!hasInitialized.current && allConversationsData?.conversations && allConversationsData.conversations.length > 0) {
      hasInitialized.current = true;
      
      // Sort by last_activity_at descending and pick the first one
      const sortedConversations = [...allConversationsData.conversations].sort((a, b) => {
        const dateA = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
        const dateB = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
        return dateB - dateA;
      });
      
      const mostRecent = sortedConversations[0];
      if (mostRecent) {
        // Set the data source type from the conversation
        if (mostRecent.data_source_type) {
          setSelectedDataSource(mostRecent.data_source_type as DataSourceType);
        } else {
          // Fallback to insurance_analytics if not found
          setSelectedDataSource('insurance_analytics' as DataSourceType);
        }
        setSelectedConversationId(mostRecent.conversation_id);
      }
    } else if (!hasInitialized.current && allConversationsData?.conversations?.length === 0) {
      // No conversations exist, mark as initialized
      hasInitialized.current = true;
    }
  }, [allConversationsData]);

  // Fetch conversations when data source is selected (for sidebar list)
  const { data: conversationsData, refetch, isLoading } = useListConversationsV1DataAnalystConversationsGet(
    {
      data_source_type: selectedDataSource || undefined,
      page: 1,
      page_size: 50,
    },
    {
      query: {
        enabled: !!selectedDataSource,
        refetchInterval: 5000,
      },
    }
  );

  const { mutate: createConversationMutation, isPending: isCreating } =
    useCreateConversationV1DataAnalystConversationsPost();

  const { mutate: deleteConversationMutation } =
    useDeleteConversationV1DataAnalystConversationsConversationIdDelete();

  const conversations = conversationsData?.conversations || [];
  const isLoadingConversations = isLoading || isLoadingAll;

  const createConversation = useCallback(
    (isGroup = false) => {
      if (!selectedDataSource) return;

      createConversationMutation(
        {
          data: {
            data_source_type: selectedDataSource,
            conversation_type: isGroup ? 'group' : 'user',
            title: undefined,
            participant_ids: undefined,
          },
        },
        {
          onSuccess: (response) => {
            refetch();
            setSelectedConversationId(response.conversation_id);
          },
          onError: (error) => {
            console.error('Failed to create conversation:', error);
          },
        }
      );
    },
    [selectedDataSource, createConversationMutation, refetch]
  );

  const deleteConversation = useCallback(
    (id: string) => {
      deleteConversationMutation(
        { conversationId: id },
        {
          onSuccess: () => {
            refetch();
            if (selectedConversationId === id) {
              setSelectedConversationId(null);
            }
          },
          onError: (error) => {
            console.error('Failed to delete conversation:', error);
          },
        }
      );
    },
    [deleteConversationMutation, refetch, selectedConversationId]
  );

  const clearSelection = useCallback(() => {
    setSelectedDataSource(null);
    setSelectedConversationId(null);
  }, []);

  const refetchConversations = useCallback(() => {
    refetch();
  }, [refetch]);

  return (
    <BiConversationsContext.Provider
      value={{
        selectedDataSource,
        selectedConversationId,
        conversations,
        isLoading: isLoadingConversations,
        isCreating,
        setSelectedDataSource,
        setSelectedConversationId,
        createConversation,
        deleteConversation,
        clearSelection,
        refetchConversations,
      }}
    >
      {children}
    </BiConversationsContext.Provider>
  );
}

/* ============================================
   Hook
   ============================================ */

export function useBiConversations() {
  const context = useContext(BiConversationsContext);
  if (!context) {
    throw new Error('useBiConversations must be used within a BiConversationsProvider');
  }
  return context;
}

export default BiConversationsContext;

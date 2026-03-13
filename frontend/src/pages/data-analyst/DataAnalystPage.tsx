/**
 * Data Analyst Agent Main Page
 * 
 * Chat interface for Business Intelligence with optional domain selection.
 * Domains are managed separately in /domains page.
 * 
 * URL params:
 * - ?domain={id} - Pre-select a RAGFlow domain for chat
 */
import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Layout } from '../../components/layout/Layout';
import DataSourceSelector from '../../components/data-analyst/DataSourceSelector';
import ConversationView from '../../components/data-analyst/ConversationView';
import RAGFlowConversationView from '../../components/data-analyst/RAGFlowConversationView';
import { ChatProvider } from '../../components/ui/chat';
import { DomainContextPill, DEFAULT_DOMAINS } from '../../components/ui';
import { useBiConversations } from '../../contexts/BiConversationsContext';
import { DataSourceType } from '../../generated/models';

export default function DataAnalystPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    selectedDataSource,
    selectedConversationId,
    setSelectedDataSource,
    createConversation,
    clearSelection,
    isCreating,
  } = useBiConversations();

  // Track if we just selected a domain (to auto-create conversation)
  const shouldCreateConversation = useRef(false);
  
  // RAGFlow domain from URL parameter
  const domainIdParam = searchParams.get('domain');
  const [ragflowDomainId, setRagflowDomainId] = useState<number | null>(
    domainIdParam ? parseInt(domainIdParam, 10) : null
  );
  const [ragflowDomainName, setRagflowDomainName] = useState<string>('');

  // Handle domain from URL param on mount
  useEffect(() => {
    if (domainIdParam) {
      const id = parseInt(domainIdParam, 10);
      if (!isNaN(id)) {
        setRagflowDomainId(id);
        setSelectedDataSource(DataSourceType.knowledge_base);
        // Fetch domain name
        const token = localStorage.getItem('auth_token');
        fetch(`${process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001')}/v1/ragflow/domains/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
          .then(res => res.json())
          .then(data => setRagflowDomainName(data.display_name || data.name || 'Domain'))
          .catch(() => {});
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainIdParam]);

  // Listen for "New Chat" event from sidebar to clear RAG domain
  useEffect(() => {
    const handleNewChat = () => {
      setRagflowDomainId(null);
      setRagflowDomainName('');
      searchParams.delete('domain');
      setSearchParams(searchParams);
    };
    
    window.addEventListener('bi-new-chat', handleNewChat);
    return () => window.removeEventListener('bi-new-chat', handleNewChat);
  }, [searchParams, setSearchParams]);

  // Handle domain selection from cards
  const handleDomainSelect = (domain: DataSourceType) => {
    setSelectedDataSource(domain);
    setRagflowDomainId(null);
    setRagflowDomainName('');
    // Remove domain param from URL
    searchParams.delete('domain');
    setSearchParams(searchParams);
    // Don't auto-create for knowledge_base
    if (domain !== DataSourceType.knowledge_base) {
      shouldCreateConversation.current = true;
    }
  };

  // Auto-create conversation when domain is selected
  useEffect(() => {
    if (selectedDataSource && selectedDataSource !== DataSourceType.knowledge_base && !selectedConversationId && shouldCreateConversation.current && !isCreating) {
      shouldCreateConversation.current = false;
      createConversation(false);
    }
  }, [selectedDataSource, selectedConversationId, createConversation, isCreating]);


  // Handle domain change from pill (creates new conversation)
  const handleDomainChange = (domain: DataSourceType | string, ragDomainId?: number, ragDomainName?: string) => {
    clearSelection();
    
    // Check if it's a RAG domain
    if (ragDomainId && ragDomainName) {
      setRagflowDomainId(ragDomainId);
      setRagflowDomainName(ragDomainName);
      setSelectedDataSource(null);
      searchParams.set('domain', String(ragDomainId));
      setSearchParams(searchParams);
    } else {
      // Built-in domain
      setRagflowDomainId(null);
      setRagflowDomainName('');
      searchParams.delete('domain');
      setSearchParams(searchParams);
      setSelectedDataSource(domain as DataSourceType);
      shouldCreateConversation.current = true;
    }
  };

  // Handle back from RAGFlow chat
  const handleBackFromRagflow = () => {
    setRagflowDomainId(null);
    setRagflowDomainName('');
    searchParams.delete('domain');
    setSearchParams(searchParams);
    clearSelection();
  };

  // Create header element to pass to ConversationView
  // Show pill for both built-in domains and RAG domains
  const currentDomain = ragflowDomainId ? `rag_${ragflowDomainId}` : selectedDataSource;
  const domainHeader = currentDomain ? (
    <DomainContextPill
      domains={DEFAULT_DOMAINS}
      selectedDomain={currentDomain}
      onDomainChange={handleDomainChange}
      confirmOnSwitch={true}
      confirmMessage="Switching domains will start a new conversation. Continue?"
    />
  ) : null;

  return (
    <Layout>
      <ChatProvider>
        <div className="flex flex-col h-full w-full min-w-0 overflow-hidden">
          {!selectedDataSource && !ragflowDomainId ? (
            /* Zero State: Domain Selection Cards */
            <DataSourceSelector 
              onSelect={handleDomainSelect} 
              onSelectRagDomain={(id, name) => {
                setRagflowDomainId(id);
                setRagflowDomainName(name);
              }}
            />
          ) : ragflowDomainId ? (
            /* RAGFlow Domain Chat */
            <RAGFlowConversationView
              domainId={ragflowDomainId}
              domainName={ragflowDomainName}
              headerContent={domainHeader}
              onBack={handleBackFromRagflow}
            />
          ) : (
            /* Active State: Chat */
            <ConversationView
              conversationId={selectedConversationId}
              dataSourceType={selectedDataSource!}
              headerContent={domainHeader}
            />
          )}
        </div>
      </ChatProvider>
    </Layout>
  );
}

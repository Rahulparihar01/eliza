/**
 * SectionNavContent - Section Navigation Content
 * 
 * The content portion of the sidebar when drilling into a section.
 * Shows a back button and section-specific navigation items.
 * Designed to work within AppSidebar with content switching.
 */

import React, { useMemo } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, TrashIcon, PlusIcon } from '@heroicons/react/24/outline';
import type { ActiveSection } from '../../contexts/NavigationContext';
import { getSectionConfig, type SectionConfig } from './sectionConfigs';
import { SidebarSection } from '../ui/sidebar';
import { Button } from '../ui/button';
import { cn } from '../../shared/lib/cn';
import { isFrontendPageEnabled } from '../../shared/lib/applets';
import { useAuth } from '../../stores/useAuth';
import { AXIOS_INSTANCE } from '../../services/api-client';


/* ============================================
   Types
   ============================================ */

interface SectionNavContentProps {
  /** The active section to display */
  section: ActiveSection;
  /** Callback when back button is clicked */
  onBack: () => void;
  /** Whether the sidebar is collapsed */
  collapsed?: boolean;
}

/* ============================================
   SectionNavItem Component
   ============================================ */

interface SectionNavItemProps {
  item: SectionConfig['items'][0];
  collapsed: boolean;
}

function SectionNavItem({ item, collapsed }: SectionNavItemProps) {
  const ItemIcon = item.icon;
  const location = useLocation();
  
  // Check if this item should be active (matches current path or is a parent of current path)
  const isItemActive = location.pathname === item.path || 
    location.pathname.startsWith(item.path + '/');

  // Section header (sub-section title)
  if (item.sectionHeader) {
    if (collapsed) return null; // Don't show headers when collapsed
    return (
      <div className="pt-4 pb-1 px-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
          {item.label}
        </span>
      </div>
    );
  }

  // Coming soon state
  if (item.comingSoon) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm",
          "text-gray-400 dark:text-gray-500 cursor-not-allowed",
          collapsed && "justify-center px-2"
        )}
        title={collapsed ? `${item.label} (Coming Soon)` : undefined}
      >
        {ItemIcon && <ItemIcon className="w-5 h-5 flex-shrink-0" />}
        {!collapsed && (
          <>
            <span className="flex-1 truncate">{item.label}</span>
            <span className="text-[10px] bg-gray-100 dark:bg-dark-surface-2 px-1.5 py-0.5 rounded text-gray-500">
              Soon
            </span>
          </>
        )}
      </div>
    );
  }

  // Disabled state
  if (item.disabled) {
    return (
      <div
        className={cn(
          "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm",
          "text-gray-400 dark:text-gray-500 cursor-not-allowed",
          collapsed && "justify-center px-2"
        )}
        title={collapsed ? `${item.label} (Disabled)` : undefined}
      >
        {ItemIcon && <ItemIcon className="w-5 h-5 flex-shrink-0" />}
        {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
        {!collapsed && item.badge && (
          <span className="text-xs bg-gray-100 dark:bg-dark-surface-2 px-1.5 py-0.5 rounded">
            {item.badge}
          </span>
        )}
      </div>
    );
  }

  // Active link - use custom isItemActive check to support subpaths
  return (
    <NavLink
      to={item.path}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium",
        "transition-colors duration-150",
        "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
        isItemActive
          ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20"
          : "text-charcoal dark:text-gray-300",
        collapsed && "justify-center px-2"
      )}
      title={collapsed ? item.label : undefined}
    >
      {ItemIcon && (
        <ItemIcon
          className={cn(
            "w-5 h-5 flex-shrink-0",
            isItemActive ? "text-eliza-red" : "text-gray-500 dark:text-gray-400"
          )}
        />
      )}
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {item.badge && (
            <span
              className={cn(
                "flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold",
                "bg-eliza-red text-white"
              )}
            >
              {item.badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}

/* ============================================
   Chat Conversations Sidebar Section (NEW)
   ============================================ */

interface ChatConversation {
  id: number;
  uuid: string;
  workspace_id: number;
  workspace_name: string;
  workspace_display_name: string;
  workspace_color: string;
  title: string | null;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
}

/**
 * Individual conversation item with inline rename capability
 */
function ConversationItem({
  conv,
  isActive,
  showWorkspace,
  onSelect,
  onRename,
  onDelete,
}: {
  conv: ChatConversation;
  isActive: boolean;
  showWorkspace: boolean;
  onSelect: () => void;
  onRename: (uuid: string, newTitle: string) => void;
  onDelete: (uuid: string) => void;
}) {
  const [isEditing, setIsEditing] = React.useState(false);
  const [editTitle, setEditTitle] = React.useState(conv.title || '');
  const [isSaving, setIsSaving] = React.useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const deleteRef = React.useRef<HTMLDivElement>(null);

  // --- Typewriter reveal animation ---
  const prevTitleRef = React.useRef(conv.title);
  const [revealChars, setRevealChars] = React.useState<number | null>(null);
  const revealTitle = React.useRef<string>('');

  // Detect title transition from "New conversation" → real title
  React.useEffect(() => {
    const prev = prevTitleRef.current;
    const next = conv.title;
    prevTitleRef.current = next;

    if (
      prev === 'New conversation' &&
      next &&
      next !== 'New conversation'
    ) {
      // Start typewriter reveal
      revealTitle.current = next;
      setRevealChars(0);
    }
  }, [conv.title]);

  // Advance the reveal one character at a time
  React.useEffect(() => {
    if (revealChars === null) return;
    if (revealChars >= revealTitle.current.length) {
      // Animation complete — reset
      const timer = setTimeout(() => setRevealChars(null), 200);
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => setRevealChars(c => (c !== null ? c + 1 : null)), 30);
    return () => clearTimeout(timer);
  }, [revealChars]);

  const isRevealing = revealChars !== null && revealChars < revealTitle.current.length;

  // Focus input when editing starts
  React.useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Close delete confirm when clicking outside
  React.useEffect(() => {
    if (!showDeleteConfirm) return;
    
    const handleClickOutside = (e: MouseEvent) => {
      if (deleteRef.current && !deleteRef.current.contains(e.target as Node)) {
        setShowDeleteConfirm(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showDeleteConfirm]);

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setEditTitle(conv.title || `Chat ${conv.uuid.slice(-6)}`);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!editTitle.trim() || editTitle === conv.title) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      await AXIOS_INSTANCE.patch(`/v1/ragflow/conversations/${conv.uuid}/title`, {
        title: editTitle.trim(),
      });
      // Update parent state via callback instead of mutating directly
      onRename(conv.uuid, editTitle.trim());
    } catch (e) {
      console.error('Failed to rename conversation:', e);
    } finally {
      setIsSaving(false);
      setIsEditing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setShowDeleteConfirm(true);
  };

  const handleConfirmDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setShowDeleteConfirm(false);
    onDelete(conv.uuid);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setShowDeleteConfirm(false);
  };

  return (
    <div
      onClick={isEditing ? undefined : onSelect}
      onDoubleClick={isEditing ? undefined : handleDoubleClick}
      className={cn(
        "w-full text-left px-2 py-1.5 rounded-md transition-colors group cursor-pointer relative",
        isActive
          ? "bg-gray-100 dark:bg-dark-surface-2"
          : "hover:bg-gray-50 dark:hover:bg-dark-surface-2/50"
      )}
      title={isEditing ? undefined : "Double-click to rename"}
    >
      {/* Workspace label */}
      {showWorkspace && (
        <div className="text-[9px] text-gray-400 dark:text-gray-500 mb-0.5 truncate leading-tight uppercase tracking-wide">
          {conv.workspace_display_name}
        </div>
      )}
      {/* Conversation title row with delete button */}
      <div className="flex items-center">
        {/* Conversation title - inline editable */}
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={handleSave}
            onKeyDown={handleKeyDown}
            disabled={isSaving}
            className={cn(
              "flex-1 bg-transparent border-0 p-0 m-0 text-[11px] leading-tight focus:outline-none focus:ring-0",
              "text-charcoal dark:text-gray-100 font-medium",
              "selection:bg-eliza-red/20"
            )}
            style={{ caretColor: '#C41E3A' }}
          />
        ) : isRevealing ? (
          /* Typewriter reveal animation */
          <div className={cn(
            "flex-1 text-[11px] leading-tight pr-1 overflow-hidden whitespace-nowrap",
            isActive
              ? "font-medium"
              : ""
          )}>
            {/* Revealed characters */}
            <span
              className={cn(
                isActive
                  ? "text-charcoal dark:text-gray-100"
                  : "text-gray-600 dark:text-gray-400"
              )}
            >
              {revealTitle.current.slice(0, Math.max(0, (revealChars ?? 0) - 2))}
            </span>
            {/* Shimmer edge (last 2 revealed chars) */}
            <span
              style={{
                background: "linear-gradient(90deg, #9ca3af 0%, #d1d5db 50%, #6b7280 100%)",
                backgroundSize: "200% 100%",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
                animation: "shimmer-text 1s ease-in-out infinite",
              }}
            >
              {revealTitle.current.slice(
                Math.max(0, (revealChars ?? 0) - 2),
                revealChars ?? 0
              )}
            </span>
            {/* Unrevealed portion (invisible but reserves space) */}
            <span className="invisible">
              {revealTitle.current.slice(revealChars ?? 0)}
            </span>
          </div>
        ) : (
          <div className={cn(
            "flex-1 text-[11px] truncate leading-tight pr-1",
            isActive 
              ? "text-charcoal dark:text-gray-100 font-medium" 
              : "text-gray-600 dark:text-gray-400 group-hover:text-charcoal dark:group-hover:text-gray-300"
          )}>
            {conv.title || `Chat ${conv.uuid.slice(-6)}`}
          </div>
        )}
        {/* Delete button container - right aligned */}
        {!isEditing && (
          <div ref={deleteRef} className="relative flex-shrink-0">
            <button
              onClick={handleDeleteClick}
              className={cn(
                "p-1.5 rounded-md transition-all",
                showDeleteConfirm 
                  ? "opacity-100 bg-red-50 dark:bg-red-950/30" 
                  : "opacity-0 group-hover:opacity-100 hover:bg-red-50 dark:hover:bg-red-950/30"
              )}
              title="Delete conversation"
            >
              <TrashIcon className="w-3.5 h-3.5 text-red-500" />
            </button>
            
            {/* Delete confirmation popup */}
            {showDeleteConfirm && (
              <div className="absolute right-0 top-full mt-1 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
                <div className="bg-white dark:bg-dark-surface rounded-lg shadow-lg border border-gray-200 dark:border-dark-border p-3 min-w-[140px]">
                  {/* Small triangle pointer */}
                  <div className="absolute -top-1.5 right-3 w-3 h-3 bg-white dark:bg-dark-surface border-l border-t border-gray-200 dark:border-dark-border transform rotate-45" />
                  
                  <p className="text-xs text-gray-600 dark:text-gray-300 mb-2.5 font-medium">
                    Delete this chat?
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={handleCancelDelete}
                      className="flex-1 px-2.5 py-1 text-[11px] font-medium rounded-md border border-gray-200 dark:border-dark-border text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
                    >
                      No
                    </button>
                    <button
                      onClick={handleConfirmDelete}
                      className="flex-1 px-2.5 py-1 text-[11px] font-medium rounded-md bg-red-500 text-white hover:bg-red-600 transition-colors"
                    >
                      Yes
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ChatConversationsSidebar({ collapsed }: { collapsed: boolean }) {
  const [conversations, setConversations] = React.useState<ChatConversation[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [selectedWorkspaces, setSelectedWorkspaces] = React.useState<Set<number>>(new Set());
  const [filterText, setFilterText] = React.useState('');
  const [isPickerOpen, setIsPickerOpen] = React.useState(false);
  const pickerRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const suppressRefreshUntil = React.useRef<number>(0);
  const fetchedNewConvRef = React.useRef<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  // Get current conversation from URL
  const pathParts = location.pathname.split('/');
  const currentConversationId = pathParts.length > 3 ? pathParts[3] : null;
  const currentWorkspaceId = pathParts.length > 2 ? pathParts[2] : null;

  // Close picker when clicking outside
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(event.target as Node)) {
        setIsPickerOpen(false);
        setFilterText('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch conversations function (stable reference)
  const fetchConversations = React.useCallback(async (force = false) => {
    // Skip fetch if we recently renamed (prevents overwriting local state)
    if (!force && Date.now() < suppressRefreshUntil.current) {
      return;
    }
    
    try {
      const res = await AXIOS_INSTANCE.get('/v1/chat/history', {
        params: {
          page: 1,
          page_size: 50,
        },
      });
      setConversations(res.data?.conversations || []);
    } catch (e) {
      console.error('Failed to fetch conversations:', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch and periodic refresh
  React.useEffect(() => {
    fetchConversations();
    const interval = setInterval(() => fetchConversations(), 30000);
    return () => clearInterval(interval);
  }, [fetchConversations]);

  // Refresh when navigating to a conversation not in our list (new conversation created)
  React.useEffect(() => {
    // Only fetch if this is a new conversation ID we haven't tried yet
    if (
      currentConversationId && 
      currentConversationId !== fetchedNewConvRef.current &&
      !conversations.some(c => c.uuid === currentConversationId)
    ) {
      fetchedNewConvRef.current = currentConversationId;
      // New conversation - fetch to pick it up (after a small delay for DB to sync)
      const timer = setTimeout(() => fetchConversations(true), 500);
      return () => clearTimeout(timer);
    }
  }, [currentConversationId, conversations, fetchConversations]);

  // Fast-poll for auto-title: when the active conversation has "New conversation",
  // poll every 5s for up to 30s to pick up the LLM-generated title quickly.
  React.useEffect(() => {
    if (!currentConversationId) return;
    const activeConv = conversations.find(c => c.uuid === currentConversationId);
    if (!activeConv || activeConv.title !== 'New conversation') return;

    let elapsed = 0;
    const interval = setInterval(() => {
      elapsed += 5000;
      if (elapsed > 30000) {
        clearInterval(interval);
        return;
      }
      fetchConversations(true);
    }, 5000);

    return () => clearInterval(interval);
  }, [currentConversationId, conversations, fetchConversations]);

  // Get unique workspaces from conversations
  const workspaces = React.useMemo(() => {
    const unique = new Map<number, { id: number; name: string }>();
    conversations.forEach(c => {
      if (!unique.has(c.workspace_id)) {
        unique.set(c.workspace_id, { id: c.workspace_id, name: c.workspace_display_name });
      }
    });
    return Array.from(unique.values());
  }, [conversations]);

  // Filter workspaces by search text (exclude already selected)
  const availableWorkspaces = React.useMemo(() => {
    const unselected = workspaces.filter(ws => !selectedWorkspaces.has(ws.id));
    if (!filterText.trim()) return unselected;
    const search = filterText.toLowerCase();
    return unselected.filter(ws => ws.name.toLowerCase().includes(search));
  }, [workspaces, filterText, selectedWorkspaces]);

  // Get selected workspace objects for pill display
  const selectedWorkspaceObjects = React.useMemo(() => {
    return workspaces.filter(ws => selectedWorkspaces.has(ws.id));
  }, [workspaces, selectedWorkspaces]);

  // Filter conversations by selected workspaces
  const filteredConversations = React.useMemo(() => {
    if (selectedWorkspaces.size === 0) return conversations;
    return conversations.filter(c => selectedWorkspaces.has(c.workspace_id));
  }, [conversations, selectedWorkspaces]);

  // Add workspace to filter
  const addWorkspace = (id: number) => {
    setSelectedWorkspaces(prev => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
    setFilterText('');
    setIsPickerOpen(false);
  };

  // Remove workspace from filter
  const removeWorkspace = (id: number) => {
    setSelectedWorkspaces(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  // Navigate to conversation
  const handleSelect = (conv: ChatConversation) => {
    navigate(`/chat/${conv.workspace_id}/${conv.uuid}`);
  };

  // Handle rename - update local state and suppress refresh briefly
  const handleRename = (uuid: string, newTitle: string) => {
    // Suppress background refresh for 5 seconds to prevent overwriting
    suppressRefreshUntil.current = Date.now() + 5000;
    setConversations(prev => 
      prev.map(c => c.uuid === uuid ? { ...c, title: newTitle } : c)
    );
  };

  // Handle delete - remove conversation
  const handleDelete = async (uuid: string) => {
    const conv = conversations.find(c => c.uuid === uuid);
    if (!conv) return;

    try {
      await AXIOS_INSTANCE.delete(
        `/v1/ragflow/domains/${conv.workspace_id}/conversations/${conv.id}`
      );

      // Remove from local state
      setConversations(prev => prev.filter(c => c.uuid !== uuid));
      // If we're viewing this conversation, navigate back to chat
      if (location.pathname.includes(uuid)) {
        navigate('/chat');
      }
    } catch (e) {
      console.error('Failed to delete conversation:', e);
    }
  };

  // New Chat - navigate to workspace picker to start fresh
  const handleNewChat = () => {
    navigate('/chat');
  };

  // Open picker and focus input
  const openPicker = () => {
    setIsPickerOpen(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  if (collapsed) {
    return (
      <div className="px-2 py-3">
        <Button
          onClick={handleNewChat}
          size="sm"
          className="w-full justify-center px-2"
          title="New Chat"
        >
          <PlusIcon className="w-4 h-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* New Chat Button */}
      <div className="px-3 pt-3 pb-2">
        <Button
          onClick={handleNewChat}
          className="w-full justify-center"
        >
          <PlusIcon className="w-4 h-4 mr-2" />
          New Chat
        </Button>
      </div>

      {/* Workspace Tag Filter */}
      <div className="px-3 pb-2" ref={pickerRef}>
        {/* Selected Pills + Add Button */}
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Selected workspace pills */}
          {selectedWorkspaceObjects.map(ws => (
            <button
              key={ws.id}
              onClick={() => removeWorkspace(ws.id)}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-charcoal dark:bg-gray-200 text-white dark:text-charcoal hover:bg-gray-700 dark:hover:bg-gray-300 transition-colors"
              title={`Remove ${ws.name}`}
            >
              <span className="truncate max-w-[80px]">{ws.name}</span>
              <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ))}
          
          {/* Add filter button / input */}
          {!isPickerOpen ? (
            <button
              onClick={openPicker}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-surface-2 transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              {selectedWorkspaces.size === 0 ? 'Filter' : 'Add'}
            </button>
          ) : (
            <div className="relative flex-1 min-w-[100px]">
              <input
                ref={inputRef}
                type="text"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="Type to filter..."
                className="w-full px-2 py-0.5 text-[11px] bg-transparent border-0 border-b border-gray-200 dark:border-dark-border text-charcoal dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-gray-400 dark:focus:border-gray-500"
              />
              
              {/* Dropdown with available workspaces */}
              {availableWorkspaces.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-1 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg shadow-lg z-50 overflow-hidden">
                  <div className="max-h-32 overflow-y-auto py-1">
                    {availableWorkspaces.map(ws => (
                      <button
                        key={ws.id}
                        onClick={() => addWorkspace(ws.id)}
                        className="w-full text-left px-3 py-1.5 text-[11px] text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-dark-surface-2 transition-colors"
                      >
                        {ws.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {/* No results */}
              {filterText && availableWorkspaces.length === 0 && (
                <div className="absolute left-0 right-0 top-full mt-1 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg shadow-lg z-50 px-3 py-2 text-[11px] text-gray-400">
                  No workspaces match
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="py-8 text-center">
            <div className="inline-block w-4 h-4 border-2 border-gray-200 dark:border-gray-600 border-t-gray-400 dark:border-t-gray-400 rounded-full animate-spin" />
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="py-6 px-4 text-center">
            <p className="text-micro text-gray-400 dark:text-gray-500">
              {selectedWorkspaces.size > 0 ? 'No conversations match filter' : 'No conversations yet'}
            </p>
          </div>
        ) : (
          <div className="px-2 space-y-0.5 pb-20">
            {filteredConversations.map((conv) => {
              // Only mark as active if this specific conversation is selected
              // Don't mark all workspace conversations as active when workspace is selected
              const isActive = currentConversationId === conv.uuid;
              
              return (
                <ConversationItem
                  key={conv.uuid}
                  conv={conv}
                  isActive={isActive}
                  showWorkspace={true}
                  onSelect={() => handleSelect(conv)}
                  onRename={handleRename}
                  onDelete={handleDelete}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================
   Section Navigation Content Component
   ============================================ */

export function SectionNavContent({ section, onBack, collapsed = false }: SectionNavContentProps) {
  const sectionConfig = getSectionConfig(section);
  const { user, hasAnyPermission } = useAuth();

  // Memoize filtered items based on user permissions
  const filteredItems = useMemo(() => {
    if (!sectionConfig) return [];
    if (!user) return [];
    
    // Filter items based on permissions
    // Items without requiredPermissions are shown to everyone
    const accessibleItems = sectionConfig.items.filter((item) => {
      // Section headers: keep them (we'll filter orphans below)
      if (item.sectionHeader) return true;
      // Applet/page-level visibility check (if item declares page key)
      if (item.pageKey && !isFrontendPageEnabled(item.pageKey)) return false;
      // No permissions required: show to everyone
      if (!item.requiredPermissions || item.requiredPermissions.length === 0) return true;
      // Check if user has any of the required permissions
      return hasAnyPermission(item.requiredPermissions);
    });

    // Remove orphan section headers (headers with no items after them)
    return accessibleItems.filter((item, index) => {
      if (!item.sectionHeader) return true;
      // Check if there's at least one non-header item after this header
      const hasItemsAfter = accessibleItems.slice(index + 1).some(i => !i.sectionHeader);
      return hasItemsAfter;
    });
  }, [sectionConfig, user?.permissions, hasAnyPermission]);

  if (!sectionConfig) {
    return null;
  }

  // Check section type for specialized content
  const isChat = section === 'chat';

  return (
    <div className="flex flex-col h-full">
      {/* Back Button */}
      <div className={cn("px-2 py-2", collapsed && "px-1")}>
        <button
          onClick={onBack}
          className={cn(
            "flex items-center gap-2 w-full rounded-lg",
            "text-gray-600 dark:text-gray-300",
            "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
            "transition-colors duration-150",
            "focus:outline-none focus:ring-2 focus:ring-eliza-red focus:ring-offset-1",
            collapsed ? "justify-center p-2" : "px-3 py-2"
          )}
          title="Go back to main menu"
          aria-label="Go back to main menu"
        >
          <ArrowLeftIcon className="w-4 h-4 flex-shrink-0" />
          {!collapsed && <span className="text-sm font-medium">Back</span>}
        </button>
      </div>

      {/* Chat Section: Show conversations directly (no nav items) */}
      {isChat && (
        <div className="flex-1 overflow-y-auto">
          <ChatConversationsSidebar collapsed={collapsed} />
        </div>
      )}

      {/* Other Sections: Show navigation items */}
      {!isChat && (
        <>
          <SidebarSection title={sectionConfig.title.toUpperCase()} collapsed={collapsed}>
            {filteredItems.map((item) => (
              <SectionNavItem key={item.path} item={item} collapsed={collapsed} />
            ))}
          </SidebarSection>

        </>
      )}
    </div>
  );
}

export default SectionNavContent;

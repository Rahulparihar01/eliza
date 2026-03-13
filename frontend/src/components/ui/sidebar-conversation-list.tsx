/**
 * SidebarConversationList - Conversation List for Sidebar
 * 
 * A DS component for rendering conversation history in the sidebar.
 * Designed to work within the BI Assistant sidebar section.
 * 
 * Features:
 * - New Chat button
 * - List of conversations with selection
 * - Delete on hover
 * - Empty state
 */

import * as React from 'react'
import {
  PlusIcon,
  ChatBubbleLeftEllipsisIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { cn } from '../../shared/lib/cn'
import { SidebarSection } from './sidebar'
import { Button } from './button'

/* ============================================
   Types
   ============================================ */

export interface SidebarConversation {
  id: string
  title?: string | null
  preview?: string | null
  messageCount?: number
  lastActivityAt?: string | null
  isGroup?: boolean
}

interface SidebarConversationListProps {
  /** List of conversations */
  conversations: SidebarConversation[]
  /** Currently selected conversation ID */
  selectedId?: string | null
  /** Callback when conversation is selected */
  onSelect?: (id: string) => void
  /** Callback when new chat is clicked */
  onNewChat?: () => void
  /** Callback when delete is clicked */
  onDelete?: (id: string) => void
  /** Whether conversations are loading */
  isLoading?: boolean
  /** Whether new chat is being created */
  isCreating?: boolean
  /** Whether the sidebar is collapsed */
  collapsed?: boolean
  /** Additional className */
  className?: string
}

/* ============================================
   ConversationItem Component
   ============================================ */

interface ConversationItemProps {
  conversation: SidebarConversation
  isSelected: boolean
  onSelect: () => void
  onDelete?: () => void
  collapsed: boolean
}

function ConversationItem({
  conversation,
  isSelected,
  onSelect,
  onDelete,
  collapsed,
}: ConversationItemProps) {
  const displayTitle = conversation.title || `Chat ${conversation.id.slice(-6)}`

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'group relative w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-pointer',
        'transition-colors duration-150',
        'hover:bg-gray-100 dark:hover:bg-dark-surface-2',
        isSelected
          ? 'bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/20'
          : 'text-charcoal dark:text-gray-300',
        collapsed && 'justify-center px-2'
      )}
      title={collapsed ? displayTitle : undefined}
    >
      <ChatBubbleLeftEllipsisIcon
        className={cn(
          'w-4 h-4 flex-shrink-0',
          isSelected ? 'text-eliza-red' : 'text-gray-400 dark:text-gray-500'
        )}
      />

      {!collapsed && (
        <>
          <div className="flex-1 min-w-0 text-left">
            <p className="truncate font-medium">{displayTitle}</p>
            {conversation.preview && (
              <p className="truncate text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                {conversation.preview}
              </p>
            )}
          </div>

          {/* Delete button - show on hover */}
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              className={cn(
                'h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity',
                'hover:bg-red-50 dark:hover:bg-red-950/30'
              )}
              title="Delete conversation"
            >
              <TrashIcon className="w-3.5 h-3.5 text-red-500" />
            </Button>
          )}
        </>
      )}
    </button>
  )
}

/* ============================================
   SidebarConversationList Component
   ============================================ */

export function SidebarConversationList({
  conversations,
  selectedId,
  onSelect,
  onNewChat,
  onDelete,
  isLoading = false,
  isCreating = false,
  collapsed = false,
  className,
}: SidebarConversationListProps) {
  return (
    <div className={cn('flex flex-col', className)}>
      {/* New Chat Button */}
      {onNewChat && (
        <div className={cn('px-2 mb-2', collapsed && 'px-1')}>
          <Button
            variant="default"
            size="sm"
            onClick={onNewChat}
            disabled={isCreating}
            className={cn(
              'w-full justify-center',
              collapsed && 'px-2'
            )}
          >
            <PlusIcon className="w-4 h-4" />
            {!collapsed && <span className="ml-2">New Chat</span>}
          </Button>
        </div>
      )}

      {/* Conversations Section */}
      <SidebarSection
        title={collapsed ? '' : 'CONVERSATIONS'}
        collapsed={collapsed}
        className="flex-1 min-h-0"
      >
        {isLoading ? (
          <div className="px-3 py-4 text-center">
            <div className="animate-pulse text-sm text-gray-400">Loading...</div>
          </div>
        ) : conversations.length === 0 ? (
          <div className={cn('px-3 py-4 text-center', collapsed && 'px-1')}>
            {!collapsed && (
              <>
                <ChatBubbleLeftEllipsisIcon className="w-8 h-8 mx-auto mb-2 text-gray-300 dark:text-gray-600" />
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  No conversations yet
                </p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-0.5">
            {conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isSelected={selectedId === conv.id}
                onSelect={() => onSelect?.(conv.id)}
                onDelete={onDelete ? () => onDelete(conv.id) : undefined}
                collapsed={collapsed}
              />
            ))}
          </div>
        )}
      </SidebarSection>
    </div>
  )
}

export default SidebarConversationList

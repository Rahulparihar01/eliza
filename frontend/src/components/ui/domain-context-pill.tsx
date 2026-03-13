/**
 * DomainContextPill - Domain Context Indicator with Switcher
 * 
 * A pill-shaped dropdown that shows the current analytics domain
 * and allows switching to a different domain.
 * 
 * Features:
 * - Shows current domain with icon
 * - Dropdown to switch domains (built-in + user-created RAG domains)
 * - Optional confirmation before switching
 * - Compact design for header placement
 */

import * as React from 'react'
import {
  ChevronDownIcon,
  ChartBarIcon,
  BookOpenIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'
import { cn } from '../../shared/lib/cn'
import { DataSourceType } from '../../generated/models'

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

/* ============================================
   Types
   ============================================ */

export interface DomainOption {
  type: DataSourceType | string  // string for RAGFlow domain IDs
  label: string
  icon: React.ComponentType<{ className?: string }>
  color?: string
  isRagDomain?: boolean
  ragDomainId?: number
}

interface DomainContextPillProps {
  /** Available domains (built-in only, RAG domains loaded dynamically) */
  domains: DomainOption[]
  /** Currently selected domain */
  selectedDomain: DataSourceType | string | null
  /** Callback when domain is changed */
  onDomainChange: (domain: DataSourceType | string, ragDomainId?: number, ragDomainName?: string) => void
  /** Whether to confirm before switching (shows warning) */
  confirmOnSwitch?: boolean
  /** Custom confirmation message */
  confirmMessage?: string
  /** Additional className */
  className?: string
}

/* ============================================
   Default Built-in Domains
   ============================================ */

export const DEFAULT_DOMAINS: DomainOption[] = [
  {
    type: DataSourceType.insurance,
    label: 'Insurance Analytics',
    icon: ChartBarIcon,
    color: 'text-eliza-red',
  },
  {
    type: DataSourceType.fasb,
    label: 'FASB Standards',
    icon: BookOpenIcon,
    color: 'text-emerald-600',
  },
]

/* ============================================
   RAG Domain Interface
   ============================================ */

interface RAGFlowDomain {
  id: number
  name: string
  display_name?: string
  status: string
  color?: string
}

/* ============================================
   Component
   ============================================ */

export function DomainContextPill({
  domains = DEFAULT_DOMAINS,
  selectedDomain,
  onDomainChange,
  confirmOnSwitch = true,
  confirmMessage = 'Switching domains will start a new conversation. Continue?',
  className,
}: DomainContextPillProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const [ragDomains, setRagDomains] = React.useState<RAGFlowDomain[]>([])
  const dropdownRef = React.useRef<HTMLDivElement>(null)

  // Fetch RAG domains
  React.useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) return

    fetch(`${API_BASE}/v1/ragflow/domains`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => res.json())
      .then(data => {
        // Only show ready domains in the chat dropdown
        const readyDomains = (data || []).filter((d: RAGFlowDomain) => d.status === 'ready')
        setRagDomains(readyDomains)
      })
      .catch(() => {})
  }, [])

  // Combine built-in domains with user RAG domains
  const allDomains: DomainOption[] = React.useMemo(() => {
    const ragOptions: DomainOption[] = ragDomains.map(d => ({
      type: `rag_${d.id}`,
      label: d.display_name || d.name,
      icon: FolderIcon,
      color: d.color ? `text-${d.color}-600` : 'text-violet-600',
      isRagDomain: true,
      ragDomainId: d.id,
    }))
    return [...domains, ...ragOptions]
  }, [domains, ragDomains])

  // Find selected domain info (check both built-in and RAG domains)
  const selected = React.useMemo(() => {
    // Check if it's a RAG domain ID (number)
    if (typeof selectedDomain === 'number' || (typeof selectedDomain === 'string' && selectedDomain.startsWith('rag_'))) {
      const ragId = typeof selectedDomain === 'number' ? selectedDomain : parseInt(selectedDomain.replace('rag_', ''), 10)
      const ragDomain = ragDomains.find(d => d.id === ragId)
      if (ragDomain) {
        return {
          type: `rag_${ragDomain.id}`,
          label: ragDomain.display_name || ragDomain.name,
          icon: FolderIcon,
          color: 'text-violet-600',
          isRagDomain: true,
          ragDomainId: ragDomain.id,
        } as DomainOption
      }
    }
    return allDomains.find(d => d.type === selectedDomain)
  }, [selectedDomain, allDomains, ragDomains])

  // Close dropdown on outside click
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle domain selection
  const handleSelect = (domain: DomainOption) => {
    if (domain.type === selectedDomain) {
      setIsOpen(false)
      return
    }

    const doChange = () => {
      if (domain.isRagDomain && domain.ragDomainId) {
        onDomainChange(domain.type, domain.ragDomainId, domain.label)
      } else {
        onDomainChange(domain.type as DataSourceType)
      }
    }

    if (confirmOnSwitch) {
      if (window.confirm(confirmMessage)) {
        doChange()
      }
    } else {
      doChange()
    }
    setIsOpen(false)
  }

  if (!selected) {
    return null
  }

  const SelectedIcon = selected.icon

  return (
    <div ref={dropdownRef} className={cn('relative', className)}>
      {/* Pill Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-full',
          'bg-gray-100 dark:bg-dark-surface-2',
          'border border-gray-200 dark:border-dark-border/50',
          'hover:bg-gray-200 dark:hover:bg-dark-surface-3',
          'transition-colors duration-150',
          'text-sm font-medium text-charcoal dark:text-gray-200'
        )}
      >
        <SelectedIcon className={cn('w-4 h-4', selected.color || 'text-eliza-red')} />
        <span className="truncate max-w-[150px]">{selected.label}</span>
        <ChevronDownIcon
          className={cn(
            'w-3.5 h-3.5 text-gray-400 transition-transform duration-150',
            isOpen && 'rotate-180'
          )}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className={cn(
            'absolute top-full left-0 mt-1 z-50',
            'min-w-[220px] py-1',
            'bg-white dark:bg-dark-surface',
            'border border-gray-200 dark:border-dark-border/50',
            'rounded-lg shadow-lg',
            'animate-in fade-in slide-in-from-top-2 duration-150',
            'max-h-80 overflow-y-auto'
          )}
        >
          {/* Built-in domains section */}
          <div className="px-3 py-1.5 text-xs font-medium text-gray-400 uppercase tracking-wide">
            Built-in
          </div>
          {domains.map((domain) => {
            const DomainIcon = domain.icon
            const isSelected = domain.type === selectedDomain

            return (
              <button
                key={String(domain.type)}
                onClick={() => handleSelect(domain)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2',
                  'text-sm text-left',
                  'hover:bg-gray-50 dark:hover:bg-dark-surface-2',
                  'transition-colors duration-100',
                  isSelected && 'bg-eliza-red/5 dark:bg-eliza-red/10'
                )}
              >
                <DomainIcon
                  className={cn(
                    'w-4 h-4 flex-shrink-0',
                    isSelected ? 'text-eliza-red' : 'text-gray-400 dark:text-gray-500'
                  )}
                />
                <span
                  className={cn(
                    'flex-1',
                    isSelected
                      ? 'text-eliza-red font-medium'
                      : 'text-charcoal dark:text-gray-200'
                  )}
                >
                  {domain.label}
                </span>
                {isSelected && (
                  <span className="text-eliza-red text-xs">✓</span>
                )}
              </button>
            )
          })}

          {/* User domains section */}
          {ragDomains.length > 0 && (
            <>
              <div className="border-t border-gray-100 dark:border-dark-border/50 my-1" />
              <div className="px-3 py-1.5 text-xs font-medium text-gray-400 uppercase tracking-wide">
                Your Domains
              </div>
              {ragDomains.map((domain) => {
                const isSelected = selectedDomain === `rag_${domain.id}` || 
                  (typeof selectedDomain === 'number' && selectedDomain === domain.id)

                return (
                  <button
                    key={domain.id}
                    onClick={() => handleSelect({
                      type: `rag_${domain.id}`,
                      label: domain.display_name || domain.name,
                      icon: FolderIcon,
                      color: 'text-violet-600',
                      isRagDomain: true,
                      ragDomainId: domain.id,
                    })}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2',
                      'text-sm text-left',
                      'hover:bg-gray-50 dark:hover:bg-dark-surface-2',
                      'transition-colors duration-100',
                      isSelected && 'bg-eliza-red/5 dark:bg-eliza-red/10'
                    )}
                  >
                    <FolderIcon
                      className={cn(
                        'w-4 h-4 flex-shrink-0',
                        isSelected ? 'text-eliza-red' : 'text-violet-500'
                      )}
                    />
                    <span
                      className={cn(
                        'flex-1 truncate',
                        isSelected
                          ? 'text-eliza-red font-medium'
                          : 'text-charcoal dark:text-gray-200'
                      )}
                    >
                      {domain.display_name || domain.name}
                    </span>
                    {isSelected && (
                      <span className="text-eliza-red text-xs">✓</span>
                    )}
                  </button>
                )
              })}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default DomainContextPill

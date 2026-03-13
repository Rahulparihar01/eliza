/**
 * Tenant Switcher - Multi-tenant Organization Selector
 * 
 * Dropdown component for switching between organizations/tenants.
 * Shows elizaforge logo + "for [Organization]" with a dropdown menu.
 */

import * as React from "react"
import { ChevronDownIcon, BuildingOffice2Icon, StarIcon, CheckIcon } from "@heroicons/react/24/outline"
import { StarIcon as StarIconSolid } from "@heroicons/react/24/solid"
import { cn } from "../../shared/lib/cn"

/* ============================================
   TYPES
   ============================================ */

export interface Tenant {
  id: string
  name: string
  slug: string
  isDefault?: boolean
}

interface TenantSwitcherProps {
  tenants: Tenant[]
  currentTenant: Tenant
  onTenantChange: (tenant: Tenant) => void
  onSetDefault?: (tenant: Tenant) => void
  className?: string
}

/* ============================================
   TENANT SWITCHER
   ============================================ */

export function TenantSwitcher({
  tenants,
  currentTenant,
  onTenantChange,
  onSetDefault,
  className,
}: TenantSwitcherProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const dropdownRef = React.useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Close on escape
  React.useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false)
    }
    document.addEventListener("keydown", handleEscape)
    return () => document.removeEventListener("keydown", handleEscape)
  }, [])

  return (
    <div ref={dropdownRef} className={cn("relative", className)}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-2 py-1 rounded-lg transition-colors",
          "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
          isOpen && "bg-gray-100 dark:bg-dark-surface-2"
        )}
      >
        {/* Logo + Text */}
        <div className="flex items-baseline">
          <span className="font-sans text-lg font-bold text-charcoal dark:text-white tracking-tight">eliza</span>
          <span className="font-title text-lg italic text-eliza-red">forge</span>
        </div>
        <span className="text-gray-400 dark:text-gray-500 text-sm">for</span>
        <span className="font-medium text-charcoal dark:text-white">{currentTenant.name}</span>
        {currentTenant.isDefault && (
          <StarIconSolid className="h-4 w-4 text-amber-400" />
        )}
        <ChevronDownIcon 
          className={cn(
            "h-4 w-4 text-gray-400 transition-transform duration-200",
            isOpen && "rotate-180"
          )} 
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className={cn(
          "absolute top-full left-0 mt-1 w-72 z-50",
          "bg-white dark:bg-dark-surface rounded-xl shadow-lg border border-gray-200 dark:border-dark-border/50",
          "py-1"
        )}>
          {/* Header */}
          <div className="px-3 py-1.5 border-b border-gray-100 dark:border-dark-border/30">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Switch Organization
            </span>
          </div>

          {/* Tenant List */}
          <div className="py-1 max-h-64 overflow-y-auto">
            {tenants.map((tenant) => {
              const isSelected = tenant.id === currentTenant.id
              
              return (
                <div
                  key={tenant.id}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors",
                    isSelected 
                      ? "bg-eliza-red/5 dark:bg-eliza-red/20" 
                      : "hover:bg-gray-50 dark:hover:bg-dark-surface-2"
                  )}
                  onClick={() => {
                    onTenantChange(tenant)
                    setIsOpen(false)
                  }}
                >
                  {/* Building Icon */}
                  <div className={cn(
                    "w-8 h-8 rounded-lg border flex items-center justify-center flex-shrink-0",
                    isSelected 
                      ? "bg-eliza-red/10 border-eliza-red/20 dark:bg-eliza-red/20 dark:border-eliza-red/30"
                      : "bg-gray-50 border-gray-200 dark:bg-dark-surface-2 dark:border-dark-border/30"
                  )}>
                    <BuildingOffice2Icon className={cn(
                      "h-4 w-4",
                      isSelected ? "text-eliza-red dark:text-white" : "text-gray-500 dark:text-gray-400"
                    )} />
                  </div>

                  {/* Tenant Info */}
                  <div className="flex-1 min-w-0">
                    <div className={cn(
                      "text-sm font-medium truncate",
                      isSelected ? "text-eliza-red dark:text-white" : "text-charcoal dark:text-white"
                    )}>
                      {tenant.name}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {tenant.slug}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {/* Star (Default indicator / Set default button) */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onSetDefault?.(tenant)
                      }}
                      className={cn(
                        "p-0.5 rounded transition-colors",
                        tenant.isDefault
                          ? "text-amber-400"
                          : "text-gray-300 hover:text-amber-400 dark:text-gray-600 dark:hover:text-amber-400"
                      )}
                      title={tenant.isDefault ? "Default organization" : "Set as default"}
                    >
                      {tenant.isDefault ? (
                        <StarIconSolid className="h-4 w-4" />
                      ) : (
                        <StarIcon className="h-4 w-4" />
                      )}
                    </button>

                    {/* Checkmark for selected */}
                    {isSelected && (
                      <CheckIcon className="h-4 w-4 text-eliza-red dark:text-white" />
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Footer */}
          <div className="px-3 py-1.5 border-t border-gray-100 dark:border-dark-border/30">
            <div className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
              <StarIconSolid className="h-3 w-3 text-amber-400" />
              <span>Default tenant is used on login</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ============================================
   COMPACT VARIANT (For sidebar headers)
   ============================================ */

interface TenantSwitcherCompactProps {
  tenants: Tenant[]
  currentTenant: Tenant
  onTenantChange: (tenant: Tenant) => void
  className?: string
}

export function TenantSwitcherCompact({
  tenants,
  currentTenant,
  onTenantChange,
  className,
}: TenantSwitcherCompactProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const dropdownRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  return (
    <div ref={dropdownRef} className={cn("relative", className)}>
      {/* Compact Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition-colors",
          "hover:bg-gray-100 dark:hover:bg-dark-surface-2",
          "text-charcoal dark:text-gray-200"
        )}
      >
        <BuildingOffice2Icon className="h-4 w-4 text-gray-500 dark:text-gray-400" />
        <span className="font-medium truncate max-w-[120px]">{currentTenant.name}</span>
        <ChevronDownIcon className={cn(
          "h-3.5 w-3.5 text-gray-400 transition-transform",
          isOpen && "rotate-180"
        )} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className={cn(
          "absolute top-full left-0 mt-1 w-56 z-50",
          "bg-white dark:bg-dark-surface rounded-xl shadow-lg border border-gray-200 dark:border-dark-border/50",
          "py-1"
        )}>
          {tenants.map((tenant) => {
            const isSelected = tenant.id === currentTenant.id
            return (
              <button
                key={tenant.id}
                onClick={() => {
                  onTenantChange(tenant)
                  setIsOpen(false)
                }}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors",
                  isSelected 
                    ? "bg-eliza-red/10 text-eliza-red dark:bg-eliza-red/25 dark:text-white" 
                    : "text-charcoal dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-dark-surface-2"
                )}
              >
                <BuildingOffice2Icon className={cn(
                  "h-4 w-4 flex-shrink-0",
                  isSelected ? "text-eliza-red dark:text-white" : "text-gray-500 dark:text-gray-400"
                )} />
                <span className="flex-1 truncate">{tenant.name}</span>
                {isSelected && <CheckIcon className="h-4 w-4" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export type { TenantSwitcherProps, TenantSwitcherCompactProps }

/**
 * SubNav Component
 * 
 * Vertical sub-navigation for admin sections.
 * Shows active state based on current route.
 * 
 * Usage:
 * <SubNav 
 *   items={[
 *     { label: 'Tenants', path: '/platform-admin/tenants', icon: BuildingIcon },
 *     { label: 'Feature Allocation', path: '/platform-admin/tenants/features' },
 *     { label: 'Adoption Access', path: '/platform-admin/tenants/adoption' },
 *   ]}
 * />
 */

import React from 'react';
import { NavLink } from 'react-router-dom';

export interface SubNavItem {
  label: string;
  path: string;
  icon?: React.ComponentType<{ className?: string }>;
  badge?: string | number;
  disabled?: boolean;
}

interface SubNavProps {
  items: SubNavItem[];
  className?: string;
}

export function SubNav({ items, className = '' }: SubNavProps) {
  return (
    <nav 
      className={`w-48 flex-shrink-0 border-r border-border bg-surface-2/30 ${className}`}
      aria-label="Section navigation"
    >
      <ul className="py-2 px-2 space-y-1">
        {items.map((item) => {
          const IconComponent = item.icon;

          if (item.disabled) {
            return (
              <li key={item.path}>
                <span className="flex items-center gap-2 px-3 py-2 text-sm text-muted cursor-not-allowed opacity-50">
                  {IconComponent && <IconComponent className="w-4 h-4" />}
                  <span className="flex-1">{item.label}</span>
                  {item.badge && (
                    <span className="text-xs bg-surface-2 text-muted px-1.5 py-0.5 rounded">
                      {item.badge}
                    </span>
                  )}
                </span>
              </li>
            );
          }

          return (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={true}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors ${
                    isActive
                      ? 'bg-brand/10 text-brand font-medium'
                      : 'text-muted hover:text-text hover:bg-surface-2'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {/* Active indicator */}
                    <span 
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors ${
                        isActive ? 'bg-brand' : 'bg-transparent'
                      }`}
                      aria-hidden="true"
                    />
                    
                    {/* Icon (optional) */}
                    {IconComponent && (
                      <IconComponent className="w-4 h-4 flex-shrink-0" />
                    )}
                    
                    {/* Label */}
                    <span className="flex-1 truncate">{item.label}</span>
                    
                    {/* Badge (optional) */}
                    {item.badge && (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        isActive 
                          ? 'bg-brand/20 text-brand' 
                          : 'bg-surface-2 text-muted'
                      }`}>
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default SubNav;


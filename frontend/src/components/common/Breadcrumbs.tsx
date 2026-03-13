/**
 * Breadcrumbs Component
 * 
 * Consistent breadcrumb navigation for admin pages.
 * 
 * Usage:
 * <Breadcrumbs items={[
 *   { label: 'Platform Admin', path: '/platform-admin/tenants', icon: ShieldCheckIcon },
 *   { label: 'Tenant Management', path: '/platform-admin/tenants' },
 *   { label: 'Feature Allocation' },  // Current page, no link
 * ]} />
 */

import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRightIcon } from '@heroicons/react/24/outline';

export interface BreadcrumbItem {
  label: string;
  path?: string;  // If undefined, not clickable (current page)
  icon?: React.ComponentType<{ className?: string }>;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function Breadcrumbs({ items, className = '' }: BreadcrumbsProps) {
  const location = useLocation();

  if (items.length === 0) return null;

  return (
    <nav 
      className={`flex items-center gap-2 text-sm ${className}`}
      aria-label="Breadcrumb"
    >
      <ol className="flex items-center gap-2">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          const isClickable = !!item.path && item.path !== location.pathname;
          const IconComponent = item.icon;

          return (
            <li key={index} className="flex items-center gap-2">
              {/* Separator (not on first item) */}
              {index > 0 && (
                <ChevronRightIcon className="w-4 h-4 text-muted flex-shrink-0" aria-hidden="true" />
              )}

              {/* Breadcrumb item */}
              {isClickable ? (
                <Link
                  to={item.path!}
                  className="flex items-center gap-1.5 text-muted hover:text-text transition-colors"
                >
                  {IconComponent && index === 0 && (
                    <IconComponent className="w-4 h-4" aria-hidden="true" />
                  )}
                  <span>{item.label}</span>
                </Link>
              ) : (
                <span 
                  className={`flex items-center gap-1.5 ${isLast ? 'text-text font-medium' : 'text-muted'}`}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {IconComponent && index === 0 && (
                    <IconComponent className="w-4 h-4" aria-hidden="true" />
                  )}
                  <span>{item.label}</span>
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Breadcrumbs;


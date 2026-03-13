/**
 * Analysis Nav Item
 * 
 * Navigation item for the analysis modal sidebar.
 * Shows completion state, required indicator, and info tooltip.
 */

import React from 'react';
import { CheckIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import { Tooltip } from '../ui';
import { cn } from '../../shared/lib/cn';

interface AnalysisNavItemProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  isActive: boolean;
  isComplete: boolean;
  isRequired: boolean;
  isDisabled?: boolean;
  disabledReason?: string;
  infoTooltip: string;
  onClick: () => void;
}

export function AnalysisNavItem({
  icon: Icon,
  label,
  isActive,
  isComplete,
  isRequired,
  isDisabled = false,
  disabledReason,
  infoTooltip,
  onClick,
}: AnalysisNavItemProps) {
  const handleClick = () => {
    if (!isDisabled) {
      onClick();
    }
  };

  const content = (
    <button
      type="button"
      onClick={handleClick}
      disabled={isDisabled}
      className={cn(
        'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-all duration-150',
        'group relative',
        'border-l-2',
        // Base state
        !isActive && !isDisabled && [
          'border-transparent',
          'hover:bg-gray-50 dark:hover:bg-dark-surface-2',
        ],
        // Active state - prominent left border + background
        isActive && [
          'border-eliza-red',
          'bg-eliza-red/10 dark:bg-eliza-red/20',
        ],
        // Disabled state
        isDisabled && [
          'border-transparent',
          'opacity-50 cursor-not-allowed',
        ]
      )}
    >
      {/* Icon - shows checkmark when complete */}
      <span
        className={cn(
          'flex-shrink-0 w-5 h-5',
          isComplete
            ? 'text-green-500'
            : isActive
              ? 'text-eliza-red'
              : 'text-gray-400 dark:text-gray-500'
        )}
      >
        {isComplete ? (
          <CheckIcon className="w-5 h-5" />
        ) : (
          <Icon className="w-5 h-5" />
        )}
      </span>

      {/* Label with required indicator */}
      <span
        className={cn(
          'flex-1 text-sm truncate',
          isActive
            ? 'text-eliza-red font-medium'
            : 'text-gray-600 dark:text-gray-400'
        )}
      >
        {label}
        {isRequired && (
          <span className={cn(
            'ml-0.5',
            isActive ? 'text-eliza-red' : 'text-gray-400'
          )}>*</span>
        )}
      </span>

      {/* Info tooltip icon */}
      <Tooltip content={infoTooltip} position="right">
        <span
          className={cn(
            'flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity',
            'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
          )}
          onClick={(e) => e.stopPropagation()} // Prevent triggering nav item click
        >
          <InformationCircleIcon className="w-4 h-4" />
        </span>
      </Tooltip>
    </button>
  );

  // Wrap in tooltip if disabled with reason
  if (isDisabled && disabledReason) {
    return (
      <Tooltip content={disabledReason} position="right">
        <div>{content}</div>
      </Tooltip>
    );
  }

  return content;
}

export default AnalysisNavItem;

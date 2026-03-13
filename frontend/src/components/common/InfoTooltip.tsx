/**
 * Info Tooltip Component
 * 
 * A small info icon that shows explanatory text on hover
 */

import React, { useState, useRef, useEffect } from 'react';
import { InformationCircleIcon } from '@heroicons/react/24/outline';

interface InfoTooltipProps {
  content: string | React.ReactNode;
  title?: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
  iconClassName?: string;
}

export function InfoTooltip({
  content,
  title,
  position = 'top',
  className = '',
  iconClassName = 'h-4 w-4',
}: InfoTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const iconRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isVisible && iconRef.current && tooltipRef.current) {
      const iconRect = iconRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      
      let top = 0;
      let left = 0;

      switch (position) {
        case 'top':
          top = iconRect.top - tooltipRect.height - 8;
          left = iconRect.left + iconRect.width / 2 - tooltipRect.width / 2;
          break;
        case 'bottom':
          top = iconRect.bottom + 8;
          left = iconRect.left + iconRect.width / 2 - tooltipRect.width / 2;
          break;
        case 'left':
          top = iconRect.top + iconRect.height / 2 - tooltipRect.height / 2;
          left = iconRect.left - tooltipRect.width - 8;
          break;
        case 'right':
          top = iconRect.top + iconRect.height / 2 - tooltipRect.height / 2;
          left = iconRect.right + 8;
          break;
      }

      // Keep tooltip in viewport
      const padding = 16;
      left = Math.max(padding, Math.min(left, window.innerWidth - tooltipRect.width - padding));
      top = Math.max(padding, Math.min(top, window.innerHeight - tooltipRect.height - padding));

      setTooltipPosition({ top, left });
    }
  }, [isVisible, position]);

  return (
    <>
      <div
        ref={iconRef}
        className={`inline-flex items-center cursor-help text-gray-400 dark:text-gray-500 hover:text-charcoal dark:hover:text-gray-100 transition-colors ${className}`}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        <InformationCircleIcon className={iconClassName} />
      </div>

      {isVisible && (
        <div
          ref={tooltipRef}
          className="fixed z-50 max-w-xs bg-charcoal dark:bg-gray-700 border border-gray-700 dark:border-gray-600 rounded-lg shadow-lg p-3"
          style={{
            top: tooltipPosition.top,
            left: tooltipPosition.left,
          }}
        >
          {title && (
            <div className="text-sm font-semibold text-white mb-1">{title}</div>
          )}
          <div className="text-sm text-gray-300">{content}</div>
        </div>
      )}
    </>
  );
}

export default InfoTooltip;


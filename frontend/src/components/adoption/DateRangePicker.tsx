/**
 * Date Range Picker Component
 * 
 * Provides preset date ranges (7d, 30d, 90d) plus custom date selection.
 * Migrated to Eliza Forge Design System.
 */

import React, { useState, useRef, useEffect } from 'react';
import { CalendarIcon, ChevronDownIcon } from '@heroicons/react/24/outline';
import { format, subDays, startOfDay, endOfDay } from 'date-fns';
import { Button } from '../ui/button';

export type DateRangePreset = '7d' | '30d' | '90d' | 'custom';

export interface DateRange {
  startDate: Date;
  endDate: Date;
  preset: DateRangePreset;
}

interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
}

const PRESETS: { value: DateRangePreset; label: string; days?: number }[] = [
  { value: '7d', label: 'Last 7 days', days: 7 },
  { value: '30d', label: 'Last 30 days', days: 30 },
  { value: '90d', label: 'Last 90 days', days: 90 },
  { value: 'custom', label: 'Custom range' },
];

export function getDefaultDateRange(preset: DateRangePreset = '30d'): DateRange {
  const end = endOfDay(new Date());
  let start: Date;
  
  switch (preset) {
    case '7d':
      start = startOfDay(subDays(new Date(), 7));
      break;
    case '30d':
      start = startOfDay(subDays(new Date(), 30));
      break;
    case '90d':
      start = startOfDay(subDays(new Date(), 90));
      break;
    default:
      start = startOfDay(subDays(new Date(), 30));
  }
  
  return { startDate: start, endDate: end, preset };
}

export function DateRangePicker({ value, onChange, className = '' }: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showCustom, setShowCustom] = useState(value.preset === 'custom');
  const [customStart, setCustomStart] = useState(format(value.startDate, 'yyyy-MM-dd'));
  const [customEnd, setCustomEnd] = useState(format(value.endDate, 'yyyy-MM-dd'));
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handlePresetSelect = (preset: DateRangePreset) => {
    if (preset === 'custom') {
      setShowCustom(true);
      return;
    }
    
    const newRange = getDefaultDateRange(preset);
    onChange(newRange);
    setIsOpen(false);
    setShowCustom(false);
  };

  const handleCustomApply = () => {
    const start = startOfDay(new Date(customStart));
    const end = endOfDay(new Date(customEnd));
    
    if (start > end) {
      // Swap if invalid
      onChange({ startDate: end, endDate: start, preset: 'custom' });
    } else {
      onChange({ startDate: start, endDate: end, preset: 'custom' });
    }
    setIsOpen(false);
  };

  const getDisplayText = () => {
    if (value.preset !== 'custom') {
      const preset = PRESETS.find(p => p.value === value.preset);
      return preset?.label || 'Select range';
    }
    return `${format(value.startDate, 'MMM d, yyyy')} - ${format(value.endDate, 'MMM d, yyyy')}`;
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg hover:border-eliza-red/50 transition-colors text-sm"
      >
        <CalendarIcon className="h-4 w-4 text-gray-400 dark:text-gray-500" />
        <span className="text-charcoal dark:text-gray-100 font-medium">{getDisplayText()}</span>
        <ChevronDownIcon className={`h-4 w-4 text-gray-400 dark:text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-2 w-72 bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg shadow-lg overflow-hidden">
          {/* Presets */}
          <div className="p-2 border-b border-gray-200 dark:border-dark-border">
            <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider px-2 py-1">
              Quick Select
            </div>
            <div className="space-y-0.5">
              {PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => handlePresetSelect(preset.value)}
                  className={`w-full text-left px-3 py-2 text-sm rounded-md transition-colors ${
                    value.preset === preset.value && preset.value !== 'custom'
                      ? 'bg-eliza-red/10 text-eliza-red font-medium'
                      : 'text-charcoal dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-dark-surface-2'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Date Inputs */}
          {showCustom && (
            <div className="p-3 space-y-3">
              <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Custom Range
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Start Date</label>
                  <input
                    type="date"
                    value={customStart}
                    onChange={(e) => setCustomStart(e.target.value)}
                    className="w-full px-2 py-1.5 text-sm bg-gray-50 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border rounded-md focus:border-eliza-red focus:outline-none text-charcoal dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">End Date</label>
                  <input
                    type="date"
                    value={customEnd}
                    onChange={(e) => setCustomEnd(e.target.value)}
                    max={format(new Date(), 'yyyy-MM-dd')}
                    className="w-full px-2 py-1.5 text-sm bg-gray-50 dark:bg-dark-surface-2 border border-gray-200 dark:border-dark-border rounded-md focus:border-eliza-red focus:outline-none text-charcoal dark:text-gray-100"
                  />
                </div>
              </div>
              <Button
                onClick={handleCustomApply}
                className="w-full"
                variant="brand"
                size="sm"
              >
                Apply Range
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DateRangePicker;


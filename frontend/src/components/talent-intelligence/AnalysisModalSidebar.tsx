/**
 * Analysis Modal Sidebar
 * 
 * Left sidebar navigation for the analysis modal.
 * Pure navigation - all configuration moved to respective section content areas.
 */

import React from 'react';
import { AnalysisNavItem } from './AnalysisNavItem';
import { ANALYSIS_SECTIONS, AnalysisSection } from './analysisConfig';

interface AnalysisModalSidebarProps {
  // Navigation
  activeSection: AnalysisSection | null;
  onSectionChange: (section: AnalysisSection | null) => void;

  // Completion state per section
  completionState: Record<AnalysisSection, boolean>;
}

export function AnalysisModalSidebar({
  activeSection,
  onSectionChange,
  completionState,
}: AnalysisModalSidebarProps) {
  return (
    <div className="w-60 flex-shrink-0 border-r border-gray-200 dark:border-dark-border flex flex-col bg-white dark:bg-dark-surface">
      {/* Configuration Section */}
      <div className="flex-1 py-4 overflow-y-auto">
        <div className="px-4 py-2">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            Configuration
          </span>
        </div>

        <nav className="space-y-0.5">
          {ANALYSIS_SECTIONS.map((section) => (
            <AnalysisNavItem
              key={section.id}
              icon={section.icon}
              label={section.label}
              isActive={activeSection === section.id}
              isComplete={completionState[section.id]}
              isRequired={section.isRequired}
              infoTooltip={section.infoTooltip}
              onClick={() => onSectionChange(section.id)}
            />
          ))}
        </nav>
      </div>

      {/* Required legend */}
      <div className="flex-shrink-0 border-t border-gray-200 dark:border-dark-border px-4 py-3">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          <span className="text-gray-400">*</span> Required to run
        </span>
      </div>
    </div>
  );
}

export default AnalysisModalSidebar;

/**
 * Analysis Configuration Component
 * 
 * Form for configuring the ML talent analysis with job description
 * and ideal candidate criteria.
 */

import React from 'react';
import {
  DocumentTextIcon,
  UserIcon,
  ArrowLeftIcon,
  PlayIcon,
} from '@heroicons/react/24/outline';

interface AnalysisConfigurationProps {
  jobDescription: string;
  idealCandidate: string;
  onJobDescriptionChange: (value: string) => void;
  onIdealCandidateChange: (value: string) => void;
  onRunAnalysis: () => void;
  onBack: () => void;
  isRunning: boolean;
}

export function AnalysisConfiguration({
  jobDescription,
  idealCandidate,
  onJobDescriptionChange,
  onIdealCandidateChange,
  onRunAnalysis,
  onBack,
  isRunning,
}: AnalysisConfigurationProps) {
  const canRun = jobDescription.trim().length > 0 && idealCandidate.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* Job Description */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-text mb-2">
          <DocumentTextIcon className="w-4 h-4" />
          Job Description
        </label>
        <textarea
          value={jobDescription}
          onChange={(e) => onJobDescriptionChange(e.target.value)}
          placeholder="Paste the job description here..."
          rows={8}
          className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-text placeholder-muted-2 focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent resize-none"
        />
        <p className="text-xs text-muted-2 mt-1">
          Include responsibilities, required skills, and qualifications
        </p>
      </div>

      {/* Ideal Candidate Description */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-text mb-2">
          <UserIcon className="w-4 h-4" />
          Ideal Candidate Description
        </label>
        <textarea
          value={idealCandidate}
          onChange={(e) => onIdealCandidateChange(e.target.value)}
          placeholder="Describe your ideal candidate in natural language..."
          rows={6}
          className="w-full px-4 py-3 bg-surface border border-border rounded-lg text-text placeholder-muted-2 focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent resize-none"
        />
        <p className="text-xs text-muted-2 mt-1">
          Example: "Someone with 5+ years of experience in deep learning, has worked at top tech companies,
          strong Python and TensorFlow skills, published research is a plus"
        </p>
      </div>

      {/* Quick Tips */}
      <div className="p-4 bg-brand/5 border border-brand/20 rounded-lg">
        <h4 className="text-sm font-semibold text-text mb-2">💡 Tips for Best Results</h4>
        <ul className="text-sm text-muted-2 space-y-1">
          <li>• Be specific about required technical skills and frameworks</li>
          <li>• Mention preferred company backgrounds or industries</li>
          <li>• Include soft skills and cultural fit criteria</li>
          <li>• Specify education requirements if important</li>
        </ul>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4 border-t border-border">
        <button
          onClick={onBack}
          disabled={isRunning}
          className="flex items-center gap-2 px-4 py-2 text-muted-2 hover:text-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          <span>Back</span>
        </button>

        <button
          onClick={onRunAnalysis}
          disabled={!canRun || isRunning}
          className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-colors ${
            canRun && !isRunning
              ? 'bg-brand text-white hover:bg-brand-strong'
              : 'bg-surface-3 text-muted-2 cursor-not-allowed'
          }`}
        >
          {isRunning ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Starting Analysis...</span>
            </>
          ) : (
            <>
              <PlayIcon className="w-5 h-5" />
              <span>Run Analysis</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}



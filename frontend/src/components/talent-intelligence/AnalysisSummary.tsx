/**
 * Analysis Summary Component
 * 
 * Shows a summary of all inputs before running the analysis.
 * Allows users to adjust market search limit and confirms all settings.
 */

import React, { useEffect, useState } from 'react';
import { 
  CheckCircleIcon, 
  UserGroupIcon, 
  FolderIcon, 
  DocumentTextIcon,
  Cog6ToothIcon,
  PlayIcon,
  EnvelopeIcon
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

interface EmailTemplate {
  id: number;
  name: string;
  description: string | null;
  category: string;
  is_active: boolean;
}

interface AnalysisSummaryProps {
  linkedInProfileCount: number;
  connectorName: string;
  jobDescription: string;
  idealCandidateDescription: string;
  pdlQueryLimit: number;
  selectedEmailTemplateId: string | null;
  onPdlQueryLimitChange: (limit: number) => void;
  onEmailTemplateChange: (templateId: string) => void;
  onRunAnalysis: () => void;
  onBack: () => void;
}

export function AnalysisSummary({
  linkedInProfileCount,
  connectorName,
  jobDescription,
  idealCandidateDescription,
  pdlQueryLimit,
  selectedEmailTemplateId,
  onPdlQueryLimitChange,
  onEmailTemplateChange,
  onRunAnalysis,
  onBack,
}: AnalysisSummaryProps) {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  // Fetch email templates from API
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await AXIOS_INSTANCE.get('/api/v1/email-templates');
        // API returns { templates: [...], total: N }
        const templateList = response.data.templates || response.data || [];
        setTemplates(templateList.filter((t: EmailTemplate) => t.is_active));
      } catch (error) {
        console.error('Failed to load email templates:', error);
      } finally {
        setLoadingTemplates(false);
      }
    };
    fetchTemplates();
  }, []);

  // Group templates by category
  const templatesByCategory = templates.reduce((acc, template) => {
    const category = template.category || 'general';
    if (!acc[category]) acc[category] = [];
    acc[category].push(template);
    return acc;
  }, {} as Record<string, EmailTemplate[]>);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-surface rounded-lg border border-border p-6">
        <div className="flex items-start gap-4 mb-6">
          <div className="p-3 bg-primary/10 rounded-lg">
            <CheckCircleIcon className="w-6 h-6 text-primary" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-foreground mb-2">
              Review & Run Analysis
            </h2>
            <p className="text-sm text-muted">
              Review your configuration below. When ready, click "Run Analysis" to start the AI-powered talent search.
            </p>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="space-y-4">
          {/* LinkedIn Profiles */}
          <div className="bg-surface-2 rounded-lg p-4 border border-border">
            <div className="flex items-center gap-3 mb-2">
              <UserGroupIcon className="w-5 h-5 text-brand" />
              <h3 className="font-medium text-foreground">Look-Alike Profiles</h3>
            </div>
            <p className="text-sm text-text ml-8">
              {linkedInProfileCount} LinkedIn profile{linkedInProfileCount !== 1 ? 's' : ''} enriched for look-alike analysis
            </p>
          </div>

          {/* Candidate Source */}
          <div className="bg-surface-2 rounded-lg p-4 border border-border">
            <div className="flex items-center gap-3 mb-2">
              <FolderIcon className="w-5 h-5 text-brand" />
              <h3 className="font-medium text-foreground">Candidate Source</h3>
            </div>
            <p className="text-sm text-text ml-8">
              {connectorName}
            </p>
          </div>

          {/* Requirements */}
          <div className="bg-surface-2 rounded-lg p-4 border border-border">
            <div className="flex items-center gap-3 mb-2">
              <DocumentTextIcon className="w-5 h-5 text-brand" />
              <h3 className="font-medium text-foreground">Job Requirements</h3>
            </div>
            <div className="ml-8 space-y-2">
              <div>
                <p className="text-xs text-muted-2 font-medium">Job Description:</p>
                <p className="text-sm text-text line-clamp-2">{jobDescription || 'Not provided'}</p>
              </div>
              {idealCandidateDescription && (
                <div>
                  <p className="text-xs text-muted-2 font-medium mt-2">Ideal Candidate:</p>
                  <p className="text-sm text-text line-clamp-2">{idealCandidateDescription}</p>
                </div>
              )}
            </div>
          </div>

          {/* Analysis Settings */}
          <div className="bg-surface-2 rounded-lg p-4 border border-border">
            <div className="flex items-center gap-3 mb-4">
              <Cog6ToothIcon className="w-5 h-5 text-brand" />
              <h3 className="font-medium text-foreground">Analysis Settings</h3>
            </div>
            <div className="ml-8 space-y-6">
              {/* Market Search Limit */}
              <div>
                <label className="block text-sm font-medium text-text mb-2">
                  Market Search Limit
                </label>
                <div className="flex items-center gap-4">
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={pdlQueryLimit}
                    onChange={(e) => onPdlQueryLimitChange(parseInt(e.target.value, 10))}
                    className="w-32 px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-2 focus:ring-brand"
                  />
                  <p className="text-xs text-muted">
                    Number of market candidates to search via Eliza People Search. 
                    <span className="text-muted-2 block mt-1">
                      💡 Use 1 for testing (minimal cost), 50 for production
                    </span>
                  </p>
                </div>
              </div>

              {/* Email Template Selector */}
              <div>
                <label className="block text-sm font-medium text-text mb-2 flex items-center gap-2">
                  <EnvelopeIcon className="w-4 h-4 text-brand" />
                  Candidate Outreach Email Template
                </label>
                <select
                  value={selectedEmailTemplateId || ''}
                  onChange={(e) => onEmailTemplateChange(e.target.value)}
                  className="w-full px-3 py-2 bg-surface border border-border rounded text-text focus:outline-none focus:ring-2 focus:ring-brand"
                  disabled={loadingTemplates}
                >
                  <option value="">
                    {loadingTemplates ? 'Loading templates...' : 'Select an email template (optional)'}
                  </option>
                  {Object.entries(templatesByCategory).map(([category, categoryTemplates]) => (
                    <optgroup key={category} label={category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}>
                      {categoryTemplates.map(template => (
                        <option key={template.id} value={template.id.toString()}>
                          {template.name}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                  {!loadingTemplates && templates.length === 0 && (
                    <option disabled>No templates available - create one first</option>
                  )}
                </select>
                <p className="text-xs text-muted mt-2">
                  Select a template for follow-up emails to matched candidates. 
                  <span className="text-muted-2 block mt-1">
                    💡 You can customize templates in the <a href="/talent/email-templates" className="text-brand hover:underline">Email Templates</a> page
                  </span>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={onBack}
          className="px-6 py-3 rounded-lg border border-border text-text hover:bg-surface-2 transition-colors"
        >
          Back to Requirements
        </button>
        
        <button
          onClick={onRunAnalysis}
          className="px-8 py-3 rounded-lg bg-brand text-on-brand hover:bg-brand-hover transition-colors flex items-center gap-2 font-medium"
        >
          <PlayIcon className="w-5 h-5" />
          Run Analysis
        </button>
      </div>

      {/* Info Box */}
      <div className="bg-brand/5 border border-brand/20 rounded-lg p-4">
        <h4 className="font-medium text-brand mb-2 text-sm">What happens next?</h4>
        <ul className="text-sm text-text space-y-1 list-disc list-inside">
          <li>AI agents will analyze your job requirements</li>
          <li>Parse and score resumes from your candidate source</li>
          <li>Search for {pdlQueryLimit} market candidate{pdlQueryLimit !== 1 ? 's' : ''} via Eliza People Search</li>
          <li>Compare all candidates against your baseline employees</li>
          <li>Generate insights and recommendations</li>
        </ul>
        <p className="text-xs text-muted mt-3">
          ⏱️ Analysis typically takes 2-5 minutes depending on the number of applicants and market candidates.
        </p>
      </div>
    </div>
  );
}



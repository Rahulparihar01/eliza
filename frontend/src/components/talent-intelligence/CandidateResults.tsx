/**
 * Candidate Results Component (Dual Pipeline)
 * 
 * Displays:
 * 1. Top 3 Overall (hero section)
 * 2. Top 5 Applicants with dimension scores
 * 3. Top 10 Market Candidates
 */

import React, { useState } from 'react';
import {
  UserCircleIcon,
  BuildingOfficeIcon,
  TrophyIcon,
  ChartBarIcon,
  ArrowDownTrayIcon,
  EnvelopeIcon,
  ClipboardDocumentIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';

interface DimensionScores {
  skills_score?: number;
  experience_score?: number;
  career_trajectory_score?: number;
  company_fit_score?: number;
  education_score?: number;
  embedding_similarity?: number;
}

interface Candidate {
  // Common fields
  name: string;
  email?: string;
  overall_score?: number;
  score?: number;  // Normalized score field
  source?: string;  // "applicant" or "market"
  category?: string;  // "Applicant" or "Market"
  
  // Applicant-specific
  applicant_id?: number;
  dimension_scores?: DimensionScores;
  reasoning?: string;
  
  // Market-specific (from PDL)
  person_id?: number;
  current_title?: string;
  current_company?: string;
  skills?: string[];
  experience_years?: number;
  linkedin_url?: string;
  github_url?: string;
  
  // Fit data from AI agents
  fit_scores?: {
    overall?: number;
    skills_match?: number;
    experience_fit?: number;
    career_trajectory?: number;
    company_background?: number;
  };
  why_great_fit?: string;
}

interface CandidateResultsProps {
  topOverall: Candidate[];
  applicants: Candidate[];
  marketCandidates: Candidate[];
}

export function CandidateResults({ topOverall, applicants, marketCandidates }: CandidateResultsProps) {
  const [activeTab, setActiveTab] = useState<'all' | 'applicants' | 'market'>('all');
  const [sortBy, setSortBy] = useState<'score' | 'skills' | 'experience'>('score');
  const [copied, setCopied] = useState(false);

  const handleExport = () => {
    // Prepare CSV data
    const allCandidates = [...topOverall, ...applicants, ...marketCandidates];
    const csv = [
      ['Name', 'Email', 'Score', 'Source', 'Current Title', 'Company'].join(','),
      ...allCandidates.map(c => [
        c.name,
        c.email || '',
        c.score || c.overall_score || 0,
        c.category || c.source || '',
        c.current_title || '',
        c.current_company || ''
      ].join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `talent-analysis-${Date.now()}.csv`;
    a.click();
  };

  const handleCopy = () => {
    const allCandidates = [...topOverall, ...applicants, ...marketCandidates];
    const text = allCandidates
      .map((c, i) => `${i + 1}. ${c.name} - ${c.score || c.overall_score || 0}/100 (${c.category || c.source})`)
      .join('\n');
    
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-success';
    if (score >= 75) return 'text-primary';
    if (score >= 60) return 'text-warning';
    return 'text-muted-2';
  };

  const getScoreLabel = (score: number) => {
    if (score >= 90) return 'Excellent Match';
    if (score >= 75) return 'Strong Match';
    if (score >= 60) return 'Good Match';
    return 'Moderate Match';
  };

  return (
    <div className="space-y-8">
      {/* Header with Export Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Analysis Results</h2>
          <p className="text-muted">
            {topOverall.length + applicants.length + marketCandidates.length} total candidates analyzed
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleCopy} className="btn-secondary">
            {copied ? (
              <>
                <CheckCircleIcon className="w-4 h-4 mr-2" />
                Copied!
              </>
            ) : (
              <>
                <ClipboardDocumentIcon className="w-4 h-4 mr-2" />
                Copy
              </>
            )}
          </button>
          <button onClick={handleExport} className="btn-secondary">
            <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Top 3 Overall - Hero Section */}
      {topOverall && topOverall.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <TrophyIcon className="w-6 h-6 text-warning" />
            <h3 className="text-xl font-bold text-foreground">Top 3 Overall Matches</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {topOverall.map((candidate, idx) => {
              const score = candidate.score || candidate.overall_score || 0;
              return (
                <div
                  key={idx}
                  className={`card p-6 relative overflow-hidden ${
                    idx === 0 ? 'ring-2 ring-warning' : ''
                  }`}
                >
                  {/* Medal */}
                  <div className="absolute top-4 right-4">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                      idx === 0 ? 'bg-warning/20' : idx === 1 ? 'bg-muted/20' : 'bg-primary/10'
                    }`}>
                      <span className="text-2xl">
                        {idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉'}
                      </span>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="pr-16">
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`text-3xl font-bold ${getScoreColor(score)}`}>
                        {score}
                      </div>
                      <div className="text-xs text-muted-2">/100</div>
                    </div>
                    <div className="text-xs text-muted-2 mb-4">{getScoreLabel(score)}</div>

                    <div className="mb-4">
                      <h4 className="font-semibold text-foreground text-lg mb-1">
                        {candidate.name}
                      </h4>
                      {candidate.current_title && (
                        <p className="text-sm text-muted">{candidate.current_title}</p>
                      )}
                      {candidate.current_company && (
                        <div className="flex items-center gap-1 mt-1">
                          <BuildingOfficeIcon className="w-4 h-4 text-muted-2" />
                          <span className="text-sm text-muted-2">{candidate.current_company}</span>
                        </div>
                      )}
                    </div>

                    {/* Source Badge */}
                    <div className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-surface-3 text-muted">
                      {candidate.category || candidate.source || 'Unknown'}
                    </div>

                    {/* Why Great Fit */}
                    {candidate.why_great_fit && (
                      <p className="mt-4 text-sm text-muted line-clamp-3">
                        {candidate.why_great_fit}
                      </p>
                    )}
                    {candidate.reasoning && (
                      <p className="mt-4 text-sm text-muted line-clamp-3">
                        {candidate.reasoning}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tabs for Applicants vs Market */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 border-b border-border">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-4 py-2 font-medium transition-colors border-b-2 ${
              activeTab === 'all'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-foreground'
            }`}
          >
            All Candidates ({applicants.length + marketCandidates.length})
          </button>
          <button
            onClick={() => setActiveTab('applicants')}
            className={`px-4 py-2 font-medium transition-colors border-b-2 ${
              activeTab === 'applicants'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-foreground'
            }`}
          >
            Applicants ({applicants.length})
          </button>
          <button
            onClick={() => setActiveTab('market')}
            className={`px-4 py-2 font-medium transition-colors border-b-2 ${
              activeTab === 'market'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-foreground'
            }`}
          >
            Market Candidates ({marketCandidates.length})
          </button>
        </div>

        {/* Sort Controls */}
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="input text-sm"
          >
            <option value="score">Overall Score</option>
            <option value="skills">Skills Match</option>
            <option value="experience">Experience Fit</option>
          </select>
        </div>

        {/* Applicants List */}
        {(activeTab === 'all' || activeTab === 'applicants') && applicants.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-lg font-bold text-foreground">
              Top Applicants ({applicants.length})
            </h3>
            <div className="space-y-3">
              {applicants.map((candidate, idx) => (
                <CandidateCard
                  key={idx}
                  candidate={candidate}
                  rank={idx + 1}
                  showDimensionScores={true}
                />
              ))}
            </div>
          </div>
        )}

        {/* Market Candidates List */}
        {(activeTab === 'all' || activeTab === 'market') && marketCandidates.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-lg font-bold text-foreground">
              Market Candidates ({marketCandidates.length})
            </h3>
            <div className="space-y-3">
              {marketCandidates.map((candidate, idx) => (
                <CandidateCard
                  key={idx}
                  candidate={candidate}
                  rank={idx + 1}
                  showDimensionScores={false}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Candidate Card Component
function CandidateCard({
  candidate,
  rank,
  showDimensionScores
}: {
  candidate: Candidate;
  rank: number;
  showDimensionScores: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const score = candidate.score || candidate.overall_score || 0;

  return (
    <div className="card p-6 hover:shadow-lg transition-all">
      <div className="flex items-start gap-4">
        {/* Rank Badge */}
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-surface-3 flex items-center justify-center">
          <span className="font-bold text-muted">#{rank}</span>
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1">
              <h4 className="font-semibold text-foreground text-lg">{candidate.name}</h4>
              {candidate.email && (
                <p className="text-sm text-muted-2">{candidate.email}</p>
              )}
              {candidate.current_title && (
                <p className="text-sm text-muted mt-1">{candidate.current_title}</p>
              )}
              {candidate.current_company && (
                <div className="flex items-center gap-1 mt-1">
                  <BuildingOfficeIcon className="w-4 h-4 text-muted-2" />
                  <span className="text-sm text-muted-2">{candidate.current_company}</span>
                </div>
              )}
            </div>

            {/* Score */}
            <div className="text-right">
              <div className={`text-3xl font-bold ${
                score >= 90 ? 'text-success' : score >= 75 ? 'text-primary' : 'text-muted'
              }`}>
                {score}
              </div>
              <div className="text-xs text-muted-2">Overall Score</div>
            </div>
          </div>

          {/* Dimension Scores (Applicants Only) */}
          {showDimensionScores && candidate.dimension_scores && (
            <div className="mb-4">
              <div className="grid grid-cols-3 gap-3">
                {candidate.dimension_scores.skills_score !== undefined && (
                  <div className="bg-surface-2 p-2 rounded">
                    <div className="text-xs text-muted-2 mb-1">Skills</div>
                    <div className="text-sm font-semibold text-success">
                      {candidate.dimension_scores.skills_score}/100
                    </div>
                  </div>
                )}
                {candidate.dimension_scores.experience_score !== undefined && (
                  <div className="bg-surface-2 p-2 rounded">
                    <div className="text-xs text-muted-2 mb-1">Experience</div>
                    <div className="text-sm font-semibold text-info">
                      {candidate.dimension_scores.experience_score}/100
                    </div>
                  </div>
                )}
                {candidate.dimension_scores.career_trajectory_score !== undefined && (
                  <div className="bg-surface-2 p-2 rounded">
                    <div className="text-xs text-muted-2 mb-1">Career</div>
                    <div className="text-sm font-semibold text-primary">
                      {candidate.dimension_scores.career_trajectory_score}/100
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Skills (Market Candidates) */}
          {candidate.skills && candidate.skills.length > 0 && (
            <div className="mb-4">
              <div className="flex flex-wrap gap-2">
                {candidate.skills.slice(0, 8).map((skill, idx) => (
                  <span key={idx} className="px-2 py-1 bg-success/10 text-success rounded text-xs">
                    {skill}
                  </span>
                ))}
                {candidate.skills.length > 8 && (
                  <span className="px-2 py-1 bg-surface-3 text-muted-2 rounded text-xs">
                    +{candidate.skills.length - 8} more
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Reasoning / Why Great Fit */}
          {(candidate.reasoning || candidate.why_great_fit) && (
            <div className="mb-4">
              <p className={`text-sm text-muted ${expanded ? '' : 'line-clamp-2'}`}>
                {candidate.reasoning || candidate.why_great_fit}
              </p>
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-xs text-primary hover:underline mt-1"
              >
                {expanded ? 'Show less' : 'Show more'}
              </button>
            </div>
          )}

          {/* Links */}
          <div className="flex items-center gap-4 text-sm">
            {candidate.linkedin_url && (
              <a
                href={candidate.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                LinkedIn →
              </a>
            )}
            {candidate.github_url && (
              <a
                href={candidate.github_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                GitHub →
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Persona Summary Component
 * 
 * Displays AI-generated ideal persona and insights report
 */

import React from 'react';
import { 
  SparklesIcon, 
  UserGroupIcon, 
  ChartBarIcon, 
  LightBulbIcon,
  ArrowPathIcon 
} from '@heroicons/react/24/outline';

interface PersonaSummaryProps {
  persona: any;
  insights: any;
  onStartOver: () => void;
}

export function PersonaSummary({ persona, insights, onStartOver }: PersonaSummaryProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SparklesIcon className="w-6 h-6 text-primary" />
          <div>
            <h2 className="text-xl font-bold text-foreground">Analysis Complete</h2>
            <p className="text-muted">AI-generated insights and recommendations</p>
          </div>
        </div>
        <button onClick={onStartOver} className="btn-secondary">
          <ArrowPathIcon className="w-4 h-4 mr-2" />
          New Analysis
        </button>
      </div>

      {/* Executive Summary */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
            <ChartBarIcon className="w-5 h-5 text-success" />
          </div>
          <h3 className="text-lg font-semibold text-foreground">Executive Summary</h3>
        </div>
        
        <div className="space-y-4">
          {insights?.executive_summary?.overview && (
            <p className="text-foreground">{insights.executive_summary.overview}</p>
          )}
          
          {insights?.executive_summary?.key_insights && (
            <div>
              <h4 className="font-semibold text-foreground mb-2">Key Insights:</h4>
              <ul className="space-y-2">
                {insights.executive_summary.key_insights.map((insight: string, idx: number) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-primary mt-1">•</span>
                    <span className="text-foreground">{insight}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {insights?.executive_summary?.bottom_line && (
            <div className="p-4 bg-success/10 rounded-lg border border-success/30">
              <div className="flex items-start gap-2">
                <LightBulbIcon className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-success mb-1">Recommendation:</p>
                  <p className="text-foreground">{insights.executive_summary.bottom_line}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Ideal Persona */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <UserGroupIcon className="w-5 h-5 text-primary" />
          </div>
          <h3 className="text-lg font-semibold text-foreground">Ideal Candidate Profile</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Skills */}
          {persona?.required_qualifications?.technical_skills && (
            <div>
              <h4 className="font-semibold text-foreground mb-3">Required Skills</h4>
              <div className="flex flex-wrap gap-2">
                {persona.required_qualifications.technical_skills.map((skill: any, idx: number) => (
                  <span key={idx} className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm">
                    {typeof skill === 'string' ? skill : skill.skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Experience */}
          {persona?.required_qualifications?.years_experience && (
            <div>
              <h4 className="font-semibold text-foreground mb-3">Experience Level</h4>
              <p className="text-muted">
                {persona.required_qualifications.years_experience.minimum}-{persona.required_qualifications.years_experience.ideal} years
              </p>
            </div>
          )}

          {/* Target Companies */}
          {persona?.ideal_background?.target_companies && (
            <div>
              <h4 className="font-semibold text-foreground mb-3">Target Companies</h4>
              <div className="flex flex-wrap gap-2">
                {persona.ideal_background.target_companies.slice(0, 6).map((company: string, idx: number) => (
                  <span key={idx} className="px-3 py-1 bg-info/10 text-info rounded text-sm">
                    {company}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Previous Titles */}
          {persona?.ideal_background?.previous_titles && (
            <div>
              <h4 className="font-semibold text-foreground mb-3">Previous Roles</h4>
              <div className="flex flex-wrap gap-2">
                {persona.ideal_background.previous_titles.slice(0, 4).map((title: string, idx: number) => (
                  <span key={idx} className="px-3 py-1 bg-surface-3 text-foreground rounded text-sm">
                    {title}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Market Analysis */}
      {insights?.market_analysis && (
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Market Analysis</h3>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-surface-2 rounded-lg">
              <div className="text-2xl font-bold text-primary">
                {insights.market_analysis.total_qualified_candidates || 0}
              </div>
              <div className="text-sm text-muted">Total Candidates</div>
            </div>
            
            <div className="p-4 bg-surface-2 rounded-lg">
              <div className="text-2xl font-bold text-success">
                {insights.market_analysis.candidate_distribution ? 
                  Object.keys(insights.market_analysis.candidate_distribution.by_current_company || {}).length : 0}
              </div>
              <div className="text-sm text-muted">Companies</div>
            </div>
            
            <div className="p-4 bg-surface-2 rounded-lg">
              <div className="text-2xl font-bold text-info">
                {insights.market_analysis.skills_availability?.common_skills?.length || 0}
              </div>
              <div className="text-sm text-muted">Common Skills</div>
            </div>
            
            <div className="p-4 bg-surface-2 rounded-lg">
              <div className="text-2xl font-bold text-warning">
                {insights.market_analysis.skills_availability?.rare_skills?.length || 0}
              </div>
              <div className="text-sm text-muted">Rare Skills</div>
            </div>
          </div>
        </div>
      )}

      {/* Sourcing Recommendations */}
      {insights?.sourcing_recommendations && (
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-foreground mb-4">Sourcing Recommendations</h3>
          
          <div className="space-y-4">
            {insights.sourcing_recommendations.priority_companies_to_target && (
              <div>
                <h4 className="font-medium text-foreground mb-2">Priority Companies to Target:</h4>
                <div className="flex flex-wrap gap-2">
                  {insights.sourcing_recommendations.priority_companies_to_target.map((company: string, idx: number) => (
                    <span key={idx} className="px-3 py-1 bg-success/10 text-success rounded text-sm">
                      {company}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {insights.sourcing_recommendations.effective_search_keywords && (
              <div>
                <h4 className="font-medium text-foreground mb-2">Effective Search Keywords:</h4>
                <div className="flex flex-wrap gap-2">
                  {insights.sourcing_recommendations.effective_search_keywords.map((keyword: string, idx: number) => (
                    <span key={idx} className="px-2 py-1 bg-surface-3 text-muted rounded text-xs font-mono">
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


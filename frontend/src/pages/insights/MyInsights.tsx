import React from 'react';
import Layout from '../../components/layout/Layout';
import {
  SparklesIcon,
  UserGroupIcon,
  BriefcaseIcon,
  TrophyIcon,
  ChartBarIcon,
  LightBulbIcon,
} from '@heroicons/react/24/outline';

export default function MyInsights() {
  // Sample ML Talent Analysis Result - Using realistic applicant names (not current employees)
  const sampleAnalysis = {
    analysis_id: "ml_ta_sample_demo",
    created_at: "2025-10-14T09:00:00Z",
    role: "Machine Learning Engineer",
    applicant_count: 50,
    market_count: 50,
    overall_confidence: 0.87,
    
    executive_summary: `Based on the analysis of 50 applicants and 50 market candidates, we've identified three exceptional candidates who demonstrate strong alignment with the ML Engineer role requirements. The candidate pool shows a consistent pattern of PyTorch expertise combined with startup experience at Series B/C companies, suggesting these are the most critical attributes for success in this role.

Top candidates universally exhibit 5-7 years of ML experience with strong fundamentals in deep learning and production ML systems. The market search revealed several high-caliber candidates from FAANG companies who are actively seeking new opportunities, indicating a favorable hiring environment.`,

    // Look-alike matches to current employees (baseline)
    baseline_matches: [
      {
        employee_name: "Alex Thompson",
        role: "Senior ML Engineer",
        match_score: 0.92,
        key_attributes: ["PyTorch", "MLOps", "Series B Startup", "Stanford CS"]
      },
      {
        employee_name: "Jordan Kim",
        role: "ML Platform Engineer",
        match_score: 0.89,
        key_attributes: ["Kubernetes", "Model Serving", "AWS", "Production ML"]
      },
      {
        employee_name: "Taylor Martinez",
        role: "ML Engineer",
        match_score: 0.85,
        key_attributes: ["Deep Learning", "NLP", "PyTorch", "Research → Production"]
      }
    ],

    top_candidates: [
      {
        rank: 1,
        name: "Michael Zhang",
        source: "applicant",
        overall_score: 9.2,
        baseline_match: "Alex Thompson (92% similarity)",
        explanation: "Exceptional PyTorch expertise with 6 years of ML experience at two Series B startups. Led ML infrastructure migration to Kubernetes, built real-time recommendation systems serving 10M+ users. PhD in Computer Science from Stanford with focus on deep learning optimization. Strong track record of taking models from research to production. Profile closely matches top-performing ML engineers on the team.",
        highlights: [
          "PyTorch + MLOps expert",
          "PhD Stanford CS",
          "10M+ users production ML",
          "Startup → Scale experience"
        ]
      },
      {
        rank: 2,
        name: "Priya Desai",
        source: "market",
        overall_score: 9.0,
        baseline_match: "Jordan Kim (89% similarity)",
        explanation: "Senior ML Engineer at Meta with 7 years experience building large-scale recommendation systems. Extensive PyTorch background, contributed to core PyTorch libraries. Looking to join a high-growth startup. MS in ML from MIT. Excellent communication skills demonstrated through technical blog and conference talks. Career trajectory mirrors successful team members.",
        highlights: [
          "FAANG experience (Meta)",
          "PyTorch core contributor",
          "MIT ML degree",
          "Public technical presence"
        ]
      },
      {
        rank: 3,
        name: "David Park",
        source: "applicant",
        overall_score: 8.8,
        baseline_match: "Taylor Martinez (85% similarity)",
        explanation: "ML Engineer with unique combination of research and production experience. 5 years at Google Research working on NLP models, then 2 years at a Series C startup building MLOps platform. Strong fundamentals in transformer architectures and model optimization. Experience with both TensorFlow and PyTorch. Background aligns with high-performing team members who successfully transitioned from research to production roles.",
        highlights: [
          "Google Research + Startup",
          "NLP/Transformers expert",
          "Dual framework fluency",
          "MLOps platform builder"
        ]
      }
    ],
    
    key_patterns: [
      {
        type: "SKILL_COMBO",
        title: "PyTorch + MLOps Dominance",
        description: "80% of top-scoring candidates have deep PyTorch expertise combined with production MLOps experience. This combination appears in both applicant and market pools, suggesting it's a key differentiator.",
        strength: "STRONG"
      },
      {
        type: "CAREER_PATH",
        title: "Startup → FAANG → Startup Trajectory",
        description: "Top candidates often show a pattern of starting at startups, gaining scale experience at FAANG companies, then returning to high-growth startups. This indicates comfort with both rapid iteration and large-scale systems.",
        strength: "MODERATE"
      },
      {
        type: "EXPERIENCE_LEVEL",
        title: "5-7 Year Sweet Spot",
        description: "The highest-scoring candidates cluster around 5-7 years of ML experience. Less experienced candidates lack production expertise, while more senior candidates often seek management roles.",
        strength: "STRONG"
      },
      {
        type: "COMPANY_CLUSTER",
        title: "Series B/C Startup Background",
        description: "Candidates with Series B/C startup experience consistently score higher, likely due to exposure to scaling challenges and cross-functional collaboration in resource-constrained environments.",
        strength: "MODERATE"
      }
    ],
    
    sourcing_recommendations: [
      {
        priority: "HIGH",
        action: "Target PyTorch contributors and conference speakers",
        rationale: "Candidates with public technical presence (GitHub contributions, blog posts, conference talks) consistently score higher. They demonstrate both expertise and communication skills."
      },
      {
        priority: "HIGH",
        action: "Emphasize MLOps and production ML in job descriptions",
        rationale: "The market has abundant ML researchers but fewer production ML engineers. Highlighting MLOps, Kubernetes, and production systems will attract the right candidates."
      },
      {
        priority: "MEDIUM",
        action: "Recruit from Series B/C startups in similar growth stage",
        rationale: "Candidates from companies at similar growth stages understand your challenges and are more likely to thrive. Target companies like Scale AI, Hugging Face, Weights & Biases."
      },
      {
        priority: "MEDIUM",
        action: "Offer remote/hybrid options",
        rationale: "45% of top market candidates specifically search for remote-friendly roles. This is especially important for candidates outside SF/NYC."
      }
    ]
  };

  return (
    <Layout>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="max-w-7xl mx-auto space-y-6 p-6 pb-12">
        {/* Header */}
        <div className="glass-surface p-6 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-text">My Insights</h1>
              <p className="text-muted mt-2">Recent analyses and saved insights</p>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-brand/10 text-brand rounded-lg">
              <SparklesIcon className="w-5 h-5" />
              <span className="text-sm font-medium">Sample Analysis Preview</span>
            </div>
          </div>
        </div>

        {/* Sample ML Talent Analysis */}
        <div className="glass-surface p-6 rounded-lg space-y-6">
          {/* Analysis Header */}
          <div className="border-b border-border pb-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h2 className="text-xl font-semibold text-text flex items-center gap-2">
                  <BriefcaseIcon className="w-6 h-6 text-brand" />
                  {sampleAnalysis.role} - Talent Analysis
                </h2>
                <p className="text-sm text-muted mt-1">
                  Analysis ID: {sampleAnalysis.analysis_id}
                </p>
                <p className="text-xs text-muted">
                  Completed: {new Date(sampleAnalysis.created_at).toLocaleString()}
                </p>
              </div>
              <div className="px-4 py-2 bg-success/10 text-success rounded-lg">
                <span className="text-sm font-medium">Completed</span>
              </div>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-surface rounded-lg p-4 border border-border">
              <div className="flex items-center gap-3">
                <UserGroupIcon className="w-8 h-8 text-brand" />
                <div>
                  <p className="text-2xl font-bold text-text">{sampleAnalysis.applicant_count}</p>
                  <p className="text-sm text-muted">Applicants Analyzed</p>
                </div>
              </div>
            </div>
            <div className="bg-surface rounded-lg p-4 border border-border">
              <div className="flex items-center gap-3">
                <ChartBarIcon className="w-8 h-8 text-brand" />
                <div>
                  <p className="text-2xl font-bold text-text">{sampleAnalysis.market_count}</p>
                  <p className="text-sm text-muted">Market Candidates</p>
                </div>
              </div>
            </div>
            <div className="bg-surface rounded-lg p-4 border border-border">
              <div className="flex items-center gap-3">
                <TrophyIcon className="w-8 h-8 text-success" />
                <div>
                  <p className="text-2xl font-bold text-success">
                    {Math.round(sampleAnalysis.overall_confidence * 100)}%
                  </p>
                  <p className="text-sm text-muted">Confidence Score</p>
                </div>
              </div>
            </div>
          </div>

          {/* Executive Summary */}
          <div className="bg-surface/50 rounded-lg p-5 border border-border">
            <h3 className="text-lg font-semibold text-text mb-3 flex items-center gap-2">
              <SparklesIcon className="w-5 h-5 text-brand" />
              Executive Summary
            </h3>
            <p className="text-text leading-relaxed whitespace-pre-line">
              {sampleAnalysis.executive_summary}
            </p>
          </div>

          {/* Baseline Employee Matches */}
          <div>
            <h3 className="text-lg font-semibold text-text mb-3 flex items-center gap-2">
              <UserGroupIcon className="w-5 h-5 text-brand" />
              Look-Alike Analysis
            </h3>
            <p className="text-sm text-muted mb-4">
              Top candidates were matched against current high-performing employees to identify similar profiles.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {sampleAnalysis.baseline_matches.map((match, idx) => (
                <div
                  key={idx}
                  className="bg-surface rounded-lg p-4 border border-border"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-md font-semibold text-text">{match.employee_name}</h4>
                    <span className="px-2 py-1 bg-success/20 text-success rounded text-xs font-bold">
                      {Math.round(match.match_score * 100)}%
                    </span>
                  </div>
                  <p className="text-sm text-muted mb-2">{match.role}</p>
                  <div className="flex flex-wrap gap-1">
                    {match.key_attributes.map((attr, aidx) => (
                      <span
                        key={aidx}
                        className="px-2 py-0.5 bg-brand/10 text-brand rounded text-xs"
                      >
                        {attr}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top 3 Candidates */}
          <div>
            <h3 className="text-lg font-semibold text-text mb-4 flex items-center gap-2">
              <TrophyIcon className="w-5 h-5 text-brand" />
              Top 3 Candidates
            </h3>
            <div className="space-y-4">
              {sampleAnalysis.top_candidates.map((candidate) => (
                <div
                  key={candidate.rank}
                  className="bg-surface rounded-lg p-5 border border-border hover:border-brand/50 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`
                        w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold
                        ${candidate.rank === 1 ? 'bg-brand text-white' : 'bg-surface-3 text-text border-2 border-border'}
                      `}>
                        #{candidate.rank}
                      </div>
                      <div>
                        <h4 className="text-lg font-semibold text-text">{candidate.name}</h4>
                        <p className="text-sm text-muted capitalize">
                          {candidate.source === 'applicant' ? '📄 Applicant' : '🔍 Market Search'}
                        </p>
                        <p className="text-xs text-success font-medium mt-1">
                          ✓ Similar to: {candidate.baseline_match}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-success">
                        {candidate.overall_score.toFixed(1)}
                      </div>
                      <p className="text-xs text-muted">Match Score</p>
                    </div>
                  </div>

                  <p className="text-text mb-3 leading-relaxed">
                    {candidate.explanation}
                  </p>

                  <div className="flex flex-wrap gap-2">
                    {candidate.highlights.map((highlight, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-brand/10 text-brand rounded-full text-sm font-medium"
                      >
                        {highlight}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Key Patterns */}
          <div>
            <h3 className="text-lg font-semibold text-text mb-4 flex items-center gap-2">
              <LightBulbIcon className="w-5 h-5 text-brand" />
              Key Patterns Identified
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sampleAnalysis.key_patterns.map((pattern, idx) => (
                <div
                  key={idx}
                  className="bg-surface rounded-lg p-4 border border-border"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="text-md font-semibold text-text">{pattern.title}</h4>
                    <span className={`
                      px-2 py-1 rounded text-xs font-medium
                      ${pattern.strength === 'STRONG' ? 'bg-success/20 text-success' : 'bg-warning/20 text-warning'}
                    `}>
                      {pattern.strength}
                    </span>
                  </div>
                  <p className="text-sm text-muted leading-relaxed">
                    {pattern.description}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Sourcing Recommendations */}
          <div>
            <h3 className="text-lg font-semibold text-text mb-4 flex items-center gap-2">
              <ChartBarIcon className="w-5 h-5 text-brand" />
              Sourcing Recommendations
            </h3>
            <div className="space-y-3">
              {sampleAnalysis.sourcing_recommendations.map((rec, idx) => (
                <div
                  key={idx}
                  className="bg-surface rounded-lg p-4 border-l-4 border-border hover:border-brand transition-colors"
                  style={{
                    borderLeftColor: rec.priority === 'HIGH' ? '#10b981' : '#f59e0b'
                  }}
                >
                  <div className="flex items-start gap-3">
                    <span className={`
                      px-2 py-1 rounded text-xs font-bold uppercase tracking-wide
                      ${rec.priority === 'HIGH' ? 'bg-success/20 text-success' : 'bg-warning/20 text-warning'}
                    `}>
                      {rec.priority}
                    </span>
                    <div className="flex-1">
                      <h4 className="text-md font-semibold text-text mb-1">{rec.action}</h4>
                      <p className="text-sm text-muted">{rec.rationale}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer Note */}
          <div className="bg-brand/5 border border-brand/20 rounded-lg p-4 mt-6">
            <p className="text-sm text-muted-2">
              <strong className="text-text">Note:</strong> This is sample data to demonstrate the ML Talent Intelligence analysis output format. 
              Run a real analysis from the <a href="/talent-intelligence" className="text-brand hover:underline">Talent Intelligence</a> page to see actual results from your data.
            </p>
          </div>
        </div>
        </div>
      </div>
    </Layout>
  );
}

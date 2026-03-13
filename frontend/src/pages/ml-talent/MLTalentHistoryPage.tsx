import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { Layout } from '../../components/layout/Layout';
import { ClockIcon, CheckCircleIcon, XCircleIcon, ClockIcon as PendingIcon } from '@heroicons/react/24/outline';
import { useNavigate } from 'react-router-dom';

// TODO: Replace with Orval-generated hooks once OpenAPI spec is updated
interface Analysis {
  analysis_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  job_description_preview?: string;
  candidate_count: number;
  top_candidate_fit_score?: number;
  average_fit_score?: number;
  error_message?: string;
  version: string;
}

interface AnalysesResponse {
  analyses: Analysis[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface CandidateScore {
  candidate_id: string;
  full_name?: string;
  overall_score: number;
  dimensions: {
    name: string;
    score: number;
    rationale: string;
  }[];
}

interface FullAnalysisResult {
  analysis_id: string;
  status: string;
  job_description: string;
  ideal_candidate_description: string;
  diagnostic_report?: any;
  baseline_profile?: any;
  synthesis?: any;
  applicant_results: CandidateScore[];
  market_results: CandidateScore[];
  top_overall: CandidateScore[];
  patterns?: any[];
  created_at: string;
  completed_at?: string;
  error_message?: string;
}

// Layout constants matching BI page
const MIN_LIST_WIDTH = 240;
const MAX_LIST_WIDTH = 420;
const MIN_DETAIL_WIDTH = 400;

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

export const TalentAnalysisHistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const splitRef = useRef<HTMLDivElement>(null);
  const detailPaneRef = useRef<HTMLDivElement>(null);
  
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);
  
  // Full analysis details
  const [fullAnalysis, setFullAnalysis] = useState<FullAnalysisResult | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  
  // Split pane state
  const [listWidth, setListWidth] = useState(320);
  const [detailPaneWidth, setDetailPaneWidth] = useState(500);
  const [isDragging, setIsDragging] = useState(false);

  // Fetch analyses
  useEffect(() => {
    const fetchAnalyses = async () => {
      setLoading(true);
      try {
        const statusParam = selectedStatus ? `&status=${selectedStatus}` : '';
        const response = await fetch(
          `/api/v1/ml-talent/analyses?page=${currentPage}&page_size=20${statusParam}`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          }
        );

        if (response.ok) {
          const data: AnalysesResponse = await response.json();
          setAnalyses(data.analyses);
          setTotal(data.total);
          setPages(data.pages);
          
          // Auto-select first analysis if none selected
          if (!selectedAnalysisId && data.analyses.length > 0) {
            setSelectedAnalysisId(data.analyses[0].analysis_id);
          }
        }
      } catch (error) {
        console.error('Failed to fetch analyses:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalyses();
  }, [currentPage, selectedStatus]);

  // Fetch full analysis details when selected
  useEffect(() => {
    if (!selectedAnalysisId) {
      setFullAnalysis(null);
      return;
    }

    const fetchAnalysisDetails = async () => {
      setLoadingDetails(true);
      try {
        const response = await fetch(
          `/api/v1/ml-talent/analysis/${selectedAnalysisId}`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          }
        );

        if (response.ok) {
          const data: FullAnalysisResult = await response.json();
          setFullAnalysis(data);
        }
      } catch (error) {
        console.error('Failed to fetch analysis details:', error);
      } finally {
        setLoadingDetails(false);
      }
    };

    fetchAnalysisDetails();
  }, [selectedAnalysisId]);

  // Handle drag resize
  useLayoutEffect(() => {
    if (!isDragging) return;
    const handleMouseMove = (event: MouseEvent) => {
      const rect = splitRef.current?.getBoundingClientRect();
      if (!rect) return;
      const maxLeft = rect.width - MIN_DETAIL_WIDTH;
      const proposed = event.clientX - rect.left;
      const clampedLeft = clamp(proposed, MIN_LIST_WIDTH, Math.max(MIN_LIST_WIDTH, maxLeft));
      setListWidth(clampedLeft);
    };
    const handleMouseUp = () => setIsDragging(false);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  useEffect(() => {
    const detailNode = detailPaneRef.current;
    if (!detailNode) return;
    const rect = detailNode.getBoundingClientRect();
    setDetailPaneWidth(rect.width);
  }, [listWidth]);

  const selectedAnalysis = analyses.find(a => a.analysis_id === selectedAnalysisId);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-success" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-danger" />;
      case 'processing':
        return <ClockIcon className="w-5 h-5 text-warning animate-spin" />;
      default:
        return <PendingIcon className="w-5 h-5 text-muted" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const baseClasses = 'px-2 py-1 rounded text-xs font-medium';
    switch (status) {
      case 'completed':
        return `${baseClasses} bg-success/10 text-success`;
      case 'failed':
        return `${baseClasses} bg-danger/10 text-danger`;
      case 'processing':
        return `${baseClasses} bg-warning/10 text-warning`;
      default:
        return `${baseClasses} bg-muted/10 text-muted`;
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getDuration = (created: string, completed?: string) => {
    if (!completed) return null;
    const start = new Date(created);
    const end = new Date(completed);
    const durationMs = end.getTime() - start.getTime();
    const minutes = Math.floor(durationMs / 60000);
    const seconds = Math.floor((durationMs % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  };

  return (
    <Layout>
      <div className="h-full flex flex-col px-0 overflow-x-hidden">
        {/* Slim Header Bar */}
        <div className="relative z-10 flex items-center justify-between h-10 px-3 bg-surface-2 border-b border-border">
          <div className="flex items-center gap-2">
            <ClockIcon className="w-5 h-5 text-brand" />
            <h1 className="text-sm font-semibold text-text">Talent Analysis History</h1>
          </div>
          <button
            onClick={() => navigate('/talent-intelligence')}
            className="px-3 py-1 rounded-md text-sm bg-brand text-on-brand hover:bg-brand/90 transition-colors"
          >
            + New Analysis
          </button>
        </div>

        {/* Status Filters Bar */}
        <div className="px-3 py-2 border-b border-border bg-surface-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedStatus(null)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedStatus === null
                  ? 'bg-brand text-on-brand'
                  : 'bg-surface text-muted hover:text-text hover:bg-surface'
              }`}
            >
              All ({total})
            </button>
            <button
              onClick={() => setSelectedStatus('completed')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedStatus === 'completed'
                  ? 'bg-brand text-on-brand'
                  : 'bg-surface text-muted hover:text-text hover:bg-surface'
              }`}
            >
              Completed
            </button>
            <button
              onClick={() => setSelectedStatus('processing')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedStatus === 'processing'
                  ? 'bg-brand text-on-brand'
                  : 'bg-surface text-muted hover:text-text hover:bg-surface'
              }`}
            >
              Processing
            </button>
            <button
              onClick={() => setSelectedStatus('failed')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                selectedStatus === 'failed'
                  ? 'bg-brand text-on-brand'
                  : 'bg-surface text-muted hover:text-text hover:bg-surface'
              }`}
            >
              Failed
            </button>
          </div>
        </div>

        {/* Split Pane View */}
        <div ref={splitRef} className="flex flex-1 min-h-0">
          {/* Analysis List */}
          <div 
            className="pt-0 relative z-0 h-full flex flex-col overflow-y-auto bg-surface border-r border-border" 
            style={{ width: clamp(listWidth, MIN_LIST_WIDTH, MAX_LIST_WIDTH) }}
          >
            {loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-muted text-sm">Loading...</div>
              </div>
            ) : analyses.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center px-4">
                <ClockIcon className="w-12 h-12 text-muted mb-3" />
                <h3 className="text-sm font-medium text-text mb-1">No analyses yet</h3>
                <p className="text-xs text-muted mb-3">Start your first analysis</p>
                <button
                  onClick={() => navigate('/talent/analysis-config?new=true')}
                  className="px-3 py-1.5 bg-brand text-on-brand rounded text-xs font-medium hover:bg-brand/90 transition-colors"
                >
                  Create Analysis
                </button>
              </div>
            ) : (
              <div className="space-y-0">
                {analyses.map((analysis) => (
                  <div
                    key={analysis.analysis_id}
                    onClick={() => setSelectedAnalysisId(analysis.analysis_id)}
                    className={`px-3 py-3 border-b border-border cursor-pointer transition-colors ${
                      selectedAnalysisId === analysis.analysis_id
                        ? 'bg-surface-2 border-l-2 border-l-brand'
                        : 'hover:bg-surface-2/50'
                    }`}
                  >
                    <div className="flex items-start gap-2 mb-2">
                      {getStatusIcon(analysis.status)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={getStatusBadge(analysis.status)}>
                            {analysis.status.toUpperCase()}
                          </span>
                        </div>
                        <div className="text-xs text-muted">
                          {formatDate(analysis.created_at)}
                        </div>
                      </div>
                    </div>
                    {analysis.job_description_preview && (
                      <div className="text-xs text-muted line-clamp-2 mt-2">
                        {analysis.job_description_preview}
                      </div>
                    )}
                    {analysis.status === 'completed' && (
                      <div className="text-xs text-text mt-2 font-medium">
                        {analysis.candidate_count} candidates
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {!loading && analyses.length > 0 && pages > 1 && (
              <div className="mt-auto p-3 border-t border-border bg-surface-2">
                <div className="flex items-center justify-between text-xs">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="px-2 py-1 rounded bg-surface text-text disabled:opacity-50 disabled:cursor-not-allowed hover:bg-surface-2 transition-colors"
                  >
                    Prev
                  </button>
                  <span className="text-muted">
                    {currentPage} / {pages}
                  </span>
                  <button
                    onClick={() => setCurrentPage((p) => Math.min(pages, p + 1))}
                    disabled={currentPage === pages}
                    className="px-2 py-1 rounded bg-surface text-text disabled:opacity-50 disabled:cursor-not-allowed hover:bg-surface-2 transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Divider */}
          <div
            className="relative w-px -mx-px cursor-col-resize z-20 bg-border"
            onMouseDown={() => setIsDragging(true)}
            title="Drag to resize"
          />

          {/* Detail Pane */}
          <div
            ref={detailPaneRef}
            className="flex-1 min-h-0 overflow-y-auto bg-surface-darker"
          >
            {loadingDetails ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-sm text-muted">Loading details...</div>
              </div>
            ) : fullAnalysis ? (
              <div className="p-6">
                <div className="max-w-5xl mx-auto space-y-6">
                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusIcon(fullAnalysis.status)}
                        <h2 className="text-2xl font-bold text-text">Analysis Results</h2>
                      </div>
                      <div className="font-mono text-xs text-muted">
                        {fullAnalysis.analysis_id}
                      </div>
                    </div>
                    <span className={getStatusBadge(fullAnalysis.status)}>
                      {fullAnalysis.status.toUpperCase()}
                    </span>
                  </div>

                  {/* Top Candidates Summary */}
                  {fullAnalysis.status === 'completed' && fullAnalysis.top_overall && fullAnalysis.top_overall.length > 0 && (
                    <div className="bg-gradient-to-br from-brand/10 to-brand/5 border border-brand/20 rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-text mb-4">🏆 Top Candidates</h3>
                      <div className="space-y-3">
                        {fullAnalysis.top_overall.slice(0, 5).map((candidate, idx) => (
                          <div key={candidate.candidate_id} className="bg-surface/50 border border-divider rounded-lg p-4">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-brand/20 flex items-center justify-center text-brand font-bold text-sm">
                                  #{idx + 1}
                                </div>
                                <div>
                                  <div className="font-medium text-text">{candidate.full_name || candidate.candidate_id}</div>
                                  <div className="text-xs text-muted">Overall Score</div>
                                </div>
                              </div>
                              <div className="text-2xl font-bold text-brand">
                                {(candidate.overall_score * 100).toFixed(1)}%
                              </div>
                            </div>
                            {candidate.dimensions && candidate.dimensions.length > 0 && (
                              <div className="mt-3 space-y-2">
                                {candidate.dimensions.slice(0, 3).map((dim) => (
                                  <div key={dim.name} className="flex items-center gap-2">
                                    <span className="text-xs text-muted w-32 truncate">{dim.name}</span>
                                    <div className="flex-1 bg-divider rounded-full h-1.5">
                                      <div
                                        className="bg-brand h-1.5 rounded-full"
                                        style={{ width: `${dim.score * 100}%` }}
                                      />
                                    </div>
                                    <span className="text-xs text-text font-medium w-12 text-right">
                                      {(dim.score * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Statistics Grid */}
                  {fullAnalysis.status === 'completed' && (
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-surface border border-divider rounded-lg p-4">
                        <div className="text-xs text-muted mb-1">Applicant Pool</div>
                        <div className="text-2xl font-bold text-text">{fullAnalysis.applicant_results?.length || 0}</div>
                        <div className="text-xs text-muted mt-1">candidates analyzed</div>
                      </div>
                      <div className="bg-surface border border-divider rounded-lg p-4">
                        <div className="text-xs text-muted mb-1">Market Search</div>
                        <div className="text-2xl font-bold text-text">{fullAnalysis.market_results?.length || 0}</div>
                        <div className="text-xs text-muted mt-1">candidates found</div>
                      </div>
                      <div className="bg-surface border border-divider rounded-lg p-4">
                        <div className="text-xs text-muted mb-1">Duration</div>
                        <div className="text-xl font-bold text-text">
                          {getDuration(fullAnalysis.created_at, fullAnalysis.completed_at) || 'N/A'}
                        </div>
                        <div className="text-xs text-muted mt-1">processing time</div>
                      </div>
                    </div>
                  )}

                  {/* Applicant Results */}
                  {fullAnalysis.applicant_results && fullAnalysis.applicant_results.length > 0 && (
                    <div className="bg-surface border border-divider rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-text mb-4">📋 Applicant Pool Results</h3>
                      <div className="space-y-3">
                        {fullAnalysis.applicant_results.map((candidate) => (
                          <div key={candidate.candidate_id} className="bg-surface-darker border border-divider rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <div className="font-medium text-text">{candidate.full_name || candidate.candidate_id}</div>
                              <div className="text-lg font-bold text-brand">
                                {(candidate.overall_score * 100).toFixed(1)}%
                              </div>
                            </div>
                            {candidate.dimensions && candidate.dimensions.length > 0 && (
                              <div className="space-y-2">
                                {candidate.dimensions.map((dim) => (
                                  <div key={dim.name}>
                                    <div className="flex items-center justify-between mb-1">
                                      <span className="text-xs text-muted">{dim.name}</span>
                                      <span className="text-xs text-text font-medium">{(dim.score * 100).toFixed(0)}%</span>
                                    </div>
                                    <div className="flex-1 bg-divider rounded-full h-1.5 mb-1">
                                      <div
                                        className="bg-brand h-1.5 rounded-full"
                                        style={{ width: `${dim.score * 100}%` }}
                                      />
                                    </div>
                                    {dim.rationale && (
                                      <p className="text-xs text-muted mt-1">{dim.rationale}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Market Results */}
                  {fullAnalysis.market_results && fullAnalysis.market_results.length > 0 && (
                    <div className="bg-surface border border-divider rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-text mb-4">🔍 Market Search Results</h3>
                      <div className="space-y-3">
                        {fullAnalysis.market_results.slice(0, 10).map((candidate) => (
                          <div key={candidate.candidate_id} className="bg-surface-darker border border-divider rounded-lg p-4">
                            <div className="flex items-center justify-between">
                              <div className="font-medium text-text">{candidate.full_name || candidate.candidate_id}</div>
                              <div className="text-lg font-bold text-brand">
                                {(candidate.overall_score * 100).toFixed(1)}%
                              </div>
                            </div>
                          </div>
                        ))}
                        {fullAnalysis.market_results.length > 10 && (
                          <div className="text-center text-sm text-muted pt-2">
                            + {fullAnalysis.market_results.length - 10} more candidates
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Job Description */}
                  {fullAnalysis.job_description && (
                    <div className="bg-surface border border-divider rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-text mb-3">📄 Job Description</h3>
                      <p className="text-sm text-muted whitespace-pre-wrap leading-relaxed">
                        {fullAnalysis.job_description}
                      </p>
                    </div>
                  )}

                  {/* Error State */}
                  {fullAnalysis.status === 'failed' && fullAnalysis.error_message && (
                    <div className="bg-danger/10 border border-danger/20 rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-danger mb-2">❌ Analysis Failed</h3>
                      <p className="text-sm text-danger">{fullAnalysis.error_message}</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-sm text-muted">
                Select an analysis to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ClockIcon, 
  CheckCircleIcon, 
  XCircleIcon, 
  ClockIcon as PendingIcon, 
  ChevronDownIcon, 
  ChevronRightIcon,
  ChartBarIcon,
  UserGroupIcon,
  DocumentTextIcon,
  StarIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  BriefcaseIcon
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

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

// Collapsible Section Component
interface CollapsibleSectionProps {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({ title, icon, children, defaultOpen = false }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-surface border border-divider rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-2 transition-colors"
      >
        <div className="flex items-center gap-3">
          {icon && <div className="text-brand">{icon}</div>}
          <h3 className="text-base font-semibold text-text">{title}</h3>
        </div>
        {isOpen ? (
          <ChevronDownIcon className="w-5 h-5 text-muted flex-shrink-0" />
        ) : (
          <ChevronRightIcon className="w-5 h-5 text-muted flex-shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="p-4 border-t border-divider bg-surface-darker">
          {children}
        </div>
      )}
    </div>
  );
};

export const TalentAnalysisHistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const splitRef = useRef<HTMLDivElement>(null);
  const detailPaneRef = useRef<HTMLDivElement>(null);
  
  // Get analysis_id from URL query parameter
  const searchParams = new URLSearchParams(window.location.search);
  const initialAnalysisId = searchParams.get('analysis_id');
  
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(initialAnalysisId);
  
  // Full analysis details
  const [fullAnalysis, setFullAnalysis] = useState<FullAnalysisResult | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  
  // Modal state for job description
  const [showJobDescriptionModal, setShowJobDescriptionModal] = useState(false);
  
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
        const response = await AXIOS_INSTANCE.get(
          `/api/v1/ml-talent/analyses?page=${currentPage}&page_size=20${statusParam}`
        );
        
        const data: AnalysesResponse = response.data;
        setAnalyses(data.analyses);
        setTotal(data.total);
        setPages(data.pages);
        
        // Auto-select analysis from URL or first analysis if none selected
        if (!selectedAnalysisId && data.analyses.length > 0) {
          // If we have an initialAnalysisId from URL and it exists in the list, use it
          // Otherwise, use the first analysis
          if (initialAnalysisId && data.analyses.some(a => a.analysis_id === initialAnalysisId)) {
            setSelectedAnalysisId(initialAnalysisId);
          } else if (initialAnalysisId) {
            // Analysis ID from URL but not in current page - select it anyway
            setSelectedAnalysisId(initialAnalysisId);
          } else {
            setSelectedAnalysisId(data.analyses[0].analysis_id);
          }
        }
      } catch (error: any) {
        console.error('Failed to fetch analyses:', error);
        // Log more details about the error
        if (error.response) {
          console.error(`API request failed: ${error.response.status} ${error.response.statusText}`);
          console.error('Response data:', error.response.data);
        } else if (error.message) {
          console.error('Error message:', error.message);
        }
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
        const response = await AXIOS_INSTANCE.get(
          `/api/v1/ml-talent/analysis/${selectedAnalysisId}`
        );
        
        const data: FullAnalysisResult = response.data;
        setFullAnalysis(data);
      } catch (error: any) {
        console.error('Failed to fetch analysis details:', error);
        if (error.response) {
          console.error(`API request failed: ${error.response.status} ${error.response.statusText}`);
          console.error('Response data:', error.response.data);
        }
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
    <div className="h-full flex flex-col overflow-hidden">
        {/* Page Header */}
        <div className="px-8 pt-8 pb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-text">Talent Search History</h1>
              <p className="text-muted text-sm mt-1">{total} searches • Review past talent analyses and their results</p>
            </div>
            <button
              onClick={() => navigate('/talent/analysis-config')}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-brand text-on-brand hover:bg-brand/90 transition-colors flex items-center gap-2"
            >
              <SparklesIcon className="w-4 h-4" />
              New Analysis
            </button>
          </div>

          {/* Status Filter Pills */}
          <div className="flex items-center gap-2 mt-5">
            <span className="text-xs text-muted uppercase tracking-wider mr-2">Filter:</span>
            <button
              onClick={() => setSelectedStatus(null)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
                selectedStatus === null
                  ? 'bg-brand text-on-brand border-brand'
                  : 'bg-surface border-border text-muted hover:text-text hover:bg-surface-2'
              }`}
            >
              All ({total})
            </button>
            <button
              onClick={() => setSelectedStatus('completed')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-1.5 ${
                selectedStatus === 'completed'
                  ? 'bg-brand text-on-brand border-brand'
                  : 'bg-surface border-border text-muted hover:text-text hover:bg-surface-2'
              }`}
            >
              <CheckCircleIcon className="w-3.5 h-3.5" />
              Completed
            </button>
            <button
              onClick={() => setSelectedStatus('processing')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-1.5 ${
                selectedStatus === 'processing'
                  ? 'bg-brand text-on-brand border-brand'
                  : 'bg-surface border-border text-muted hover:text-text hover:bg-surface-2'
              }`}
            >
              <ClockIcon className="w-3.5 h-3.5" />
              Processing
            </button>
            <button
              onClick={() => setSelectedStatus('failed')}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-1.5 ${
                selectedStatus === 'failed'
                  ? 'bg-brand text-on-brand border-brand'
                  : 'bg-surface border-border text-muted hover:text-text hover:bg-surface-2'
              }`}
            >
              <XCircleIcon className="w-3.5 h-3.5" />
              Failed
            </button>
          </div>
        </div>

        {/* Split Pane View */}
        <div ref={splitRef} className="flex flex-1 min-h-0">
          {/* Analysis List */}
          <div 
            className="h-full flex flex-col overflow-y-auto border-r border-border" 
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
                    className={`px-4 py-4 border-b border-border cursor-pointer transition-colors ${
                      selectedAnalysisId === analysis.analysis_id
                        ? 'bg-surface-2/50 border-l-2 border-l-brand'
                        : 'hover:bg-surface-2/30'
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

                  {/* Top 3 Candidates Summary */}
                  {fullAnalysis.status === 'completed' && fullAnalysis.top_overall && fullAnalysis.top_overall.length > 0 && (
                    <div className="bg-gradient-to-br from-brand/10 to-brand/5 border border-brand/20 rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-text">🏆 Top 3 Candidates</h3>
                        <button
                          onClick={() => {
                            // Scroll to Stage 7 and expand it
                            const stage7Element = document.getElementById('stage-7-synthesis');
                            if (stage7Element) {
                              stage7Element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                              // Trigger click to expand if collapsed
                              const button = stage7Element.querySelector('button');
                              if (button && !button.getAttribute('aria-expanded')) {
                                button.click();
                              }
                            }
                          }}
                          className="px-4 py-2 bg-brand text-on-brand rounded-md text-sm font-medium hover:bg-brand/90 transition-colors"
                        >
                          View Full Analysis
                        </button>
                      </div>
                      <div className="space-y-3">
                        {fullAnalysis.top_overall.slice(0, 3).map((candidate, idx) => (
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

                  {/* Summary Statistics */}
                  <div className="bg-surface border border-divider rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-text mb-4">Analysis Summary</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-surface-darker border border-divider rounded-lg p-4">
                        <div className="text-xs text-muted mb-1">Status</div>
                        <div className="text-lg font-bold text-text capitalize">{fullAnalysis.status}</div>
                      </div>
                      <div className="bg-surface-darker border border-divider rounded-lg p-4">
                        <div className="text-xs text-muted mb-1">Applicants</div>
                        <div className="text-lg font-bold text-text">{fullAnalysis.applicant_results?.length || 0}</div>
                        <div className="text-xs text-muted mt-1">candidates</div>
                      </div>
                      <div className="bg-surface-darker border border-divider rounded-lg p-4">
                        <div className="text-xs text-muted mb-1">Market Search</div>
                        <div className="text-lg font-bold text-text">{fullAnalysis.market_results?.length || 0}</div>
                        <div className="text-xs text-muted mt-1">candidates</div>
                      </div>
                    </div>
                  </div>

                  {/* Configuration Inputs */}
                  <div className="bg-surface border border-divider rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-text mb-4">Analysis Configuration</h3>
                    <div className="space-y-4">
                      {/* Job Description - Collapsible Button */}
                      {fullAnalysis.job_description && (
                        <div>
                          <button
                            onClick={() => setShowJobDescriptionModal(true)}
                            className="flex items-center gap-2 text-brand hover:text-brand/80 transition-colors"
                          >
                            <BriefcaseIcon className="w-4 h-4" />
                            <h4 className="font-semibold text-sm">View Job Description</h4>
                            <ChevronRightIcon className="w-4 h-4" />
                          </button>
                        </div>
                      )}

                      {/* Ideal Candidate Description */}
                      {fullAnalysis.ideal_candidate_description && (
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <StarIcon className="w-4 h-4 text-brand" />
                            <h4 className="font-semibold text-text text-sm">Ideal Candidate Profile</h4>
                          </div>
                          <p className="text-sm text-muted whitespace-pre-wrap leading-relaxed pl-6">
                            {fullAnalysis.ideal_candidate_description}
                          </p>
                        </div>
                      )}

                      {/* Analysis Metadata */}
                      <div className="grid grid-cols-2 gap-4 pt-2 border-t border-divider">
                        <div>
                          <div className="text-xs text-muted mb-1">Created</div>
                          <div className="text-sm text-text">{new Date(fullAnalysis.created_at).toLocaleString()}</div>
                        </div>
                        {fullAnalysis.completed_at && (
                          <div>
                            <div className="text-xs text-muted mb-1">Completed</div>
                            <div className="text-sm text-text">{new Date(fullAnalysis.completed_at).toLocaleString()}</div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Processing Stages - Collapsible Sections */}
                  <div className="space-y-4">
                    {/* Stage 1-2: Diagnostic Report */}
                    <CollapsibleSection 
                      title="Stage 1-2: Diagnostic Analysis" 
                      icon={<ChartBarIcon className="w-5 h-5" />} 
                      defaultOpen={false}
                    >
                      {fullAnalysis.diagnostic_report ? (
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold text-text mb-2">Role Competencies</h4>
                            {fullAnalysis.diagnostic_report.ml_competencies && (
                              <div className="space-y-2">
                                {Object.entries(fullAnalysis.diagnostic_report.ml_competencies).map(([key, value]) => (
                                  <div key={key} className="text-sm">
                                    <span className="text-muted">{key}:</span> <span className="text-text">{JSON.stringify(value)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          {fullAnalysis.diagnostic_report.attribute_weights && (
                            <div>
                              <h4 className="font-semibold text-text mb-2">Attribute Weights</h4>
                              <div className="space-y-2">
                                {fullAnalysis.diagnostic_report.attribute_weights.map((attr: any) => (
                                  <div key={attr.attribute} className="flex items-center gap-2">
                                    <span className="text-sm text-muted w-32">{attr.attribute}</span>
                                    <div className="flex-1 bg-divider rounded-full h-2">
                                      <div
                                        className="bg-brand h-2 rounded-full"
                                        style={{ width: `${attr.weight * 100}%` }}
                                      />
                                    </div>
                                    <span className="text-sm text-text font-medium">{(attr.weight * 100).toFixed(0)}%</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-sm text-muted italic">
                          {fullAnalysis.status === 'processing' ? 'Analysis in progress...' : 
                           fullAnalysis.status === 'failed' ? 'Stage did not complete' : 
                           'No diagnostic data available'}
                        </div>
                      )}
                    </CollapsibleSection>

                    {/* Stage 3: Baseline Profile */}
                    <CollapsibleSection 
                      title="Stage 3: Baseline Profile Analysis" 
                      icon={<UserGroupIcon className="w-5 h-5" />} 
                      defaultOpen={false}
                    >
                      {fullAnalysis.baseline_profile ? (
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold text-text mb-2">Profile Summary</h4>
                            <pre className="text-sm text-muted bg-surface-darker p-3 rounded border border-divider overflow-x-auto">
                              {JSON.stringify(fullAnalysis.baseline_profile, null, 2)}
                            </pre>
                          </div>
                        </div>
                      ) : (
                        <div className="text-sm text-muted italic">
                          {fullAnalysis.status === 'processing' ? 'Analysis in progress...' : 
                           fullAnalysis.status === 'failed' ? 'Stage did not complete' : 
                           'No baseline profile data available'}
                        </div>
                      )}
                    </CollapsibleSection>

                    {/* Stage 4: Applicant Scoring */}
                    <CollapsibleSection 
                      title={`Stage 4: Applicant Scoring${fullAnalysis.applicant_results ? ` (${fullAnalysis.applicant_results.length} candidates)` : ''}`}
                      icon={<StarIcon className="w-5 h-5" />} 
                      defaultOpen={true}
                    >
                      {fullAnalysis.applicant_results && fullAnalysis.applicant_results.length > 0 ? (
                        <div className="space-y-3">
                          {fullAnalysis.applicant_results.map((candidate) => (
                            <div key={candidate.candidate_id} className="bg-surface border border-divider rounded-lg p-4">
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
                      ) : (
                        <div className="text-sm text-muted italic">
                          {fullAnalysis.status === 'processing' ? 'Scoring in progress...' : 
                           fullAnalysis.status === 'failed' ? 'Stage did not complete' : 
                           'No applicant results available'}
                        </div>
                      )}
                    </CollapsibleSection>

                    {/* Stage 5-6: Market Search & Scoring */}
                    <CollapsibleSection 
                      title={`Stage 5-6: Market Search & Scoring${fullAnalysis.market_results ? ` (${fullAnalysis.market_results.length} candidates)` : ''}`}
                      icon={<MagnifyingGlassIcon className="w-5 h-5" />} 
                      defaultOpen={true}
                    >
                      {fullAnalysis.market_results && fullAnalysis.market_results.length > 0 ? (
                        <div className="space-y-3">
                          {fullAnalysis.market_results.slice(0, 10).map((candidate) => (
                            <div key={candidate.candidate_id} className="bg-surface border border-divider rounded-lg p-4">
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
                      ) : (
                        <div className="text-sm text-muted italic">
                          {fullAnalysis.status === 'processing' ? 'Market search in progress...' : 
                           fullAnalysis.status === 'failed' ? 'Stage did not complete' : 
                           'No market results available'}
                        </div>
                      )}
                    </CollapsibleSection>

                    {/* Stage 7: Synthesis Report */}
                    <div id="stage-7-synthesis">
                      <CollapsibleSection 
                        title="Stage 7: Synthesis & Insights" 
                        icon={<SparklesIcon className="w-5 h-5" />} 
                        defaultOpen={false}
                      >
                      {fullAnalysis.synthesis ? (
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold text-text mb-2">Analysis Summary</h4>
                            <pre className="text-sm text-muted bg-surface-darker p-3 rounded border border-divider overflow-x-auto">
                              {JSON.stringify(fullAnalysis.synthesis, null, 2)}
                            </pre>
                          </div>
                        </div>
                      ) : (
                        <div className="text-sm text-muted italic">
                          {fullAnalysis.status === 'processing' ? 'Analysis in progress...' : 
                           fullAnalysis.status === 'failed' ? 'Stage did not complete' : 
                           'No synthesis data available'}
                        </div>
                      )}
                      </CollapsibleSection>
                    </div>
                  </div>

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

        {/* Job Description Modal */}
        {showJobDescriptionModal && fullAnalysis?.job_description && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-surface rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
              <div className="flex items-center justify-between p-6 border-b border-divider">
                <div className="flex items-center gap-3">
                  <BriefcaseIcon className="w-6 h-6 text-brand" />
                  <h2 className="text-xl font-semibold text-text">Job Description</h2>
                </div>
                <button
                  onClick={() => setShowJobDescriptionModal(false)}
                  className="text-muted hover:text-text transition-colors"
                >
                  <XCircleIcon className="w-6 h-6" />
                </button>
              </div>
              <div className="p-6 overflow-y-auto max-h-[calc(80vh-88px)]">
                <p className="text-sm text-text whitespace-pre-wrap leading-relaxed">
                  {fullAnalysis.job_description}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
  );
};

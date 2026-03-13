/**
 * Home Page - Customizable Widget Dashboard
 * 
 * Users can pin and reorder widgets to customize their home experience.
 * Default widget shows AI Recruiter statistics.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Layout } from '../../components/layout/Layout';
import { 
  PlusIcon,
  ChartBarIcon,
  UserGroupIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  XMarkIcon,
  Bars3Icon,
  EnvelopeIcon
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Widget types for future extensibility
type WidgetType = 'ai_recruiter_stats' | 'email_templates' | 'business_intelligence' | 'custom';

interface Widget {
  id: string;
  type: WidgetType;
  title: string;
  order: number;
  pinned: boolean;
}

interface AIRecruiterStats {
  total_analyses: number;
  analyses_this_week: number;
  total_candidates_scored: number;
  candidates_this_week: number;
  emails_generated: number;
  emails_sent: number;
  average_score: number;
  configs_count: number;
}

interface EmailTemplate {
  id: number;
  name: string;
  category: string;
  is_default: boolean;
}

interface DefaultTemplateInfo {
  candidateType: string;
  candidateTypeLabel: string;
  templateName: string | null;
  templateId: number | null;
}

// Candidate types with their template categories
const CANDIDATE_TYPE_MAPPING = [
  { type: 'applicant', label: 'Applicants', category: 'applicant_followup' },
  { type: 'previous_candidate', label: 'Previous Candidates', category: 'previous_candidate' },
  { type: 'market', label: 'Market Candidates', category: 'market_outreach' },
];

// Default widgets configuration
const defaultWidgets: Widget[] = [
  {
    id: 'ai-recruiter-stats',
    type: 'ai_recruiter_stats',
    title: 'AI Recruiter Overview',
    order: 0,
    pinned: true
  },
  {
    id: 'email-templates',
    type: 'email_templates',
    title: 'Email Templates',
    order: 1,
    pinned: false
  }
];

// LocalStorage key for widget preferences
const WIDGETS_STORAGE_KEY = 'home-widgets-config';

// Load widgets from localStorage, merging in any new default widgets
const loadWidgetsFromStorage = (): Widget[] => {
  try {
    const stored = localStorage.getItem(WIDGETS_STORAGE_KEY);
    if (stored) {
      const savedWidgets: Widget[] = JSON.parse(stored);
      
      // Check for new default widgets that don't exist in saved config
      const savedIds = new Set(savedWidgets.map(w => w.id));
      const newDefaults = defaultWidgets.filter(dw => !savedIds.has(dw.id));
      
      if (newDefaults.length > 0) {
        // Add new default widgets at the end with proper ordering
        const maxOrder = Math.max(...savedWidgets.map(w => w.order), -1);
        const mergedWidgets = [
          ...savedWidgets,
          ...newDefaults.map((w, idx) => ({ ...w, order: maxOrder + 1 + idx }))
        ];
        // Save the merged config back to storage
        localStorage.setItem(WIDGETS_STORAGE_KEY, JSON.stringify(mergedWidgets));
        return mergedWidgets;
      }
      
      return savedWidgets;
    }
  } catch (e) {
    console.error('Error loading widgets from storage:', e);
  }
  return defaultWidgets;
};

// Save widgets to localStorage
const saveWidgetsToStorage = (widgets: Widget[]) => {
  try {
    localStorage.setItem(WIDGETS_STORAGE_KEY, JSON.stringify(widgets));
  } catch (e) {
    console.error('Error saving widgets to storage:', e);
  }
};

export default function HomePage() {
  const [widgets, setWidgets] = useState<Widget[]>(loadWidgetsFromStorage);
  const [stats, setStats] = useState<AIRecruiterStats | null>(null);
  const [defaultTemplates, setDefaultTemplates] = useState<DefaultTemplateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Drag and drop state - only use state for drop target highlight (doesn't affect dragged element)
  const [dragOverWidget, setDragOverWidget] = useState<string | null>(null);

  // Save widgets whenever they change
  useEffect(() => {
    saveWidgetsToStorage(widgets);
  }, [widgets]);

  // Fetch AI Recruiter stats from live data
  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        
        // Fetch data from multiple endpoints
        const [configsRes, candidatesRes] = await Promise.all([
          // Get analysis configurations
          AXIOS_INSTANCE.get('/api/v1/talent/analysis-configs').catch((err) => {
            console.log('Failed to fetch configs:', err.response?.status);
            return { data: [] };
          }),
          // Get scored candidates (just need totals, so minimal page size)
          AXIOS_INSTANCE.get('/api/v1/outreach/scored-candidates', {
            params: { page: 1, page_size: 1 }
          }).catch((err) => {
            console.log('Failed to fetch candidates:', err.response?.status);
            return { data: { total: 0, analysis_count: 0, candidates: [] } };
          })
        ]);

        // API returns { configs: [...], total: int } - extract the configs array
        const configs = configsRes.data?.configs || [];
        const candidatesData = candidatesRes.data || {};
        
        // Get total analyses run by counting runs from configs
        let totalAnalysesRun = 0;
        let analysesThisWeek = 0;
        let avgScore = 0;
        
        const now = new Date();
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        
        // If we have configs, fetch runs for each to get accurate analysis counts
        if (configs.length > 0) {
          const runsPromises = configs.slice(0, 10).map((config: any) => 
            AXIOS_INSTANCE.get(`/api/v1/talent/analysis-configs/${config.id}/runs`).catch(() => ({ data: { runs: [] } }))
          );
          
          const runsResponses = await Promise.all(runsPromises);
          
          runsResponses.forEach((res: any) => {
            const runs = res.data?.runs || [];
            totalAnalysesRun += runs.length;
            
            runs.forEach((run: any) => {
              // Check if run is from this week
              const runDate = new Date(run.started_at || run.created_at);
              if (runDate > weekAgo) {
                analysesThisWeek++;
              }
            });
          });
        }
        
        // Calculate average from candidates if available
        if (candidatesData.candidates?.length > 0) {
          const scores = candidatesData.candidates.map((c: any) => c.score).filter((s: any) => s > 0);
          if (scores.length > 0) {
            avgScore = scores.reduce((a: number, b: number) => a + b, 0) / scores.length;
          }
        }

        setStats({
          total_analyses: totalAnalysesRun || candidatesData.analysis_count || 0,
          analyses_this_week: analysesThisWeek,
          total_candidates_scored: candidatesData.total || 0,
          candidates_this_week: 0, // Would need separate query for this
          emails_generated: 0, // TODO: Add email tracking endpoint
          emails_sent: 0,
          average_score: Math.round(avgScore * 10) / 10,
          configs_count: configs.length
        });
        
        setError(null);
      } catch (err: any) {
        console.error('Error fetching stats:', err);
        setError('Unable to load statistics');
        setStats({
          total_analyses: 0,
          analyses_this_week: 0,
          total_candidates_scored: 0,
          candidates_this_week: 0,
          emails_generated: 0,
          emails_sent: 0,
          average_score: 0,
          configs_count: 0
        });
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  // Fetch email templates to show defaults per candidate type
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setTemplatesLoading(true);
        const res = await AXIOS_INSTANCE.get('/api/v1/email-templates').catch(() => ({ data: { templates: [] } }));
        // API returns { templates: [...], total: int }
        const templates: EmailTemplate[] = res.data?.templates || [];
        
        // Map candidate types to their default templates
        const defaults: DefaultTemplateInfo[] = CANDIDATE_TYPE_MAPPING.map(({ type, label, category }) => {
          const defaultTemplate = templates.find(t => t.category === category && t.is_default);
          return {
            candidateType: type,
            candidateTypeLabel: label,
            templateName: defaultTemplate?.name || null,
            templateId: defaultTemplate?.id || null,
          };
        });
        
        setDefaultTemplates(defaults);
      } catch (err) {
        console.error('Error fetching templates:', err);
      } finally {
        setTemplatesLoading(false);
      }
    };

    fetchTemplates();
  }, []);

  // Store refs to widget containers for drag image and direct DOM manipulation
  const widgetRefs = useRef<Record<string, HTMLDivElement | null>>({});
  // Track dragged widget ID in ref (NO state to avoid re-renders during drag)
  const draggedWidgetRef = useRef<string | null>(null);

  // Drag and drop handlers - use DIRECT DOM manipulation for visual feedback
  const handleDragStart = useCallback((e: React.DragEvent, widgetId: string) => {
    // Store dragged widget ID in ref (NOT state - avoids re-render)
    draggedWidgetRef.current = widgetId;
    
    // Set data transfer for the drag operation
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', widgetId);
    
    // Use the full widget container as the drag image
    const widgetEl = widgetRefs.current[widgetId];
    if (widgetEl) {
      const rect = widgetEl.getBoundingClientRect();
      e.dataTransfer.setDragImage(widgetEl, rect.width / 2, 40);
      // Apply visual feedback directly to DOM (NO re-render)
      widgetEl.style.opacity = '0.4';
    }
  }, []);

  const handleDragEnd = useCallback((e: React.DragEvent) => {
    // Get the widget ID from ref
    const widgetId = draggedWidgetRef.current;
    draggedWidgetRef.current = null;
    
    // Remove visual feedback directly from DOM
    if (widgetId) {
      const widgetEl = widgetRefs.current[widgetId];
      if (widgetEl) {
        widgetEl.style.opacity = '';
      }
    }
    
    // Clear drop target
    setDragOverWidget(null);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, widgetId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (draggedWidgetRef.current && draggedWidgetRef.current !== widgetId) {
      setDragOverWidget(widgetId);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    const relatedTarget = e.relatedTarget as HTMLElement;
    if (!e.currentTarget.contains(relatedTarget)) {
      setDragOverWidget(null);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, targetWidgetId: string) => {
    e.preventDefault();
    e.stopPropagation();
    
    const draggedId = draggedWidgetRef.current;
    
    // Clear visual feedback directly from DOM
    if (draggedId) {
      const widgetEl = widgetRefs.current[draggedId];
      if (widgetEl) {
        widgetEl.style.opacity = '';
      }
    }
    
    // Clear refs and state
    draggedWidgetRef.current = null;
    setDragOverWidget(null);
    
    if (!draggedId || draggedId === targetWidgetId) {
      return;
    }

    setWidgets(prev => {
      const newWidgets = [...prev];
      const draggedIndex = newWidgets.findIndex(w => w.id === draggedId);
      const targetIndex = newWidgets.findIndex(w => w.id === targetWidgetId);
      
      if (draggedIndex === -1 || targetIndex === -1) return prev;
      
      // Remove dragged widget and insert at target position
      const [removed] = newWidgets.splice(draggedIndex, 1);
      newWidgets.splice(targetIndex, 0, removed);
      
      // Update order values
      return newWidgets.map((widget, index) => ({
        ...widget,
        order: index
      }));
    });
  }, []);

  const handleRemoveWidget = (widgetId: string) => {
    setWidgets(prev => {
      const filtered = prev.filter(w => w.id !== widgetId);
      // Re-order remaining widgets
      return filtered.map((widget, index) => ({
        ...widget,
        order: index
      }));
    });
  };

  const handleTogglePin = (widgetId: string) => {
    setWidgets(prev => prev.map(w => 
      w.id === widgetId ? { ...w, pinned: !w.pinned } : w
    ));
  };

  // Render stat item
  const StatItem = ({ 
    icon: Icon, 
    label, 
    value, 
    subValue,
    highlight = false 
  }: { 
    icon: React.ElementType; 
    label: string; 
    value: string | number;
    subValue?: string;
    highlight?: boolean;
  }) => (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-2/50 hover:bg-surface-2 transition-colors">
      <div className={`p-2 rounded-lg ${highlight ? 'bg-brand/10' : 'bg-surface'}`}>
        <Icon className={`h-5 w-5 ${highlight ? 'text-brand' : 'text-muted'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-muted truncate">{label}</div>
        <div className="text-lg font-semibold text-text">{value}</div>
        {subValue && <div className="text-xs text-muted">{subValue}</div>}
      </div>
    </div>
  );

  // Render AI Recruiter Stats Widget
  const AIRecruiterWidget = ({ widget }: { widget: Widget }) => {
    // Only use state for drop target highlight (dragging visual is handled via direct DOM manipulation)
    const isDragOver = dragOverWidget === widget.id && draggedWidgetRef.current !== widget.id;

    return (
      <div 
        ref={(el) => { widgetRefs.current[widget.id] = el; }}
        className={`
          bg-surface border rounded-xl overflow-hidden h-full flex flex-col
          transition-[border-color,box-shadow] duration-150
          ${isDragOver ? 'border-brand ring-2 ring-brand/20' : 'border-border'}
        `}
        onDragOver={(e) => handleDragOver(e, widget.id)}
        onDragLeave={handleDragLeave}
        onDrop={(e) => handleDrop(e, widget.id)}
      >
        {/* Widget Header - entire header is draggable */}
        <div 
          className="px-4 py-3 border-b border-border flex items-center justify-between bg-surface-2/30 cursor-grab active:cursor-grabbing select-none"
          draggable
          onDragStart={(e) => handleDragStart(e, widget.id)}
          onDragEnd={(e) => handleDragEnd(e)}
        >
          <div className="flex items-center gap-2">
            <div className="p-1">
              <Bars3Icon className="h-4 w-4 text-muted" />
            </div>
            <h3 className="text-sm font-semibold text-text">{widget.title}</h3>
          </div>
          <div 
            className="flex items-center gap-1"
            onMouseDown={(e) => e.stopPropagation()}
            onDragStart={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => handleTogglePin(widget.id)}
              draggable={false}
              className={`p-1.5 rounded hover:bg-surface-2 transition-colors ${widget.pinned ? 'text-brand' : 'text-muted'}`}
              title={widget.pinned ? 'Unpin widget (pinned widgets stay in place)' : 'Pin widget'}
            >
              <svg className="h-4 w-4" fill={widget.pinned ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
            </button>
            {!widget.pinned && (
              <button
                onClick={() => handleRemoveWidget(widget.id)}
                draggable={false}
                className="p-1.5 rounded hover:bg-surface-2 text-muted hover:text-red-400 transition-colors"
                title="Remove widget"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Widget Content */}
        <div className="p-4 flex-1">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <div className="animate-spin h-8 w-8 border-2 border-brand/30 border-t-brand rounded-full" />
            </div>
          ) : error ? (
            <div className="h-full flex items-center justify-center text-muted text-sm">
              {error}
            </div>
          ) : stats ? (
            <div className="grid grid-cols-2 gap-3">
              <StatItem 
                icon={DocumentTextIcon}
                label="Analysis Configs"
                value={stats.configs_count}
                highlight
              />
              <StatItem 
                icon={ChartBarIcon}
                label="Total Analyses"
                value={stats.total_analyses}
                subValue={`${stats.analyses_this_week} this week`}
              />
              <StatItem 
                icon={UserGroupIcon}
                label="Candidates Scored"
                value={stats.total_candidates_scored.toLocaleString()}
                subValue={`${stats.candidates_this_week} this week`}
              />
              <StatItem 
                icon={CheckCircleIcon}
                label="Avg Score"
                value={stats.average_score > 0 ? `${stats.average_score}%` : '—'}
              />
            </div>
          ) : null}
        </div>

        {/* Widget Footer */}
        <div className="px-4 py-2 border-t border-border bg-surface-2/20">
          <a 
            href="/talent/analysis-config" 
            className="text-xs text-brand hover:text-brand-hover transition-colors"
          >
            View Analysis Config →
          </a>
        </div>
      </div>
    );
  };

  // Render Email Templates Widget
  const EmailTemplatesWidget = ({ widget }: { widget: Widget }) => {
    return (
      <div
        ref={(el) => { widgetRefs.current[widget.id] = el; }}
        className={`rounded-xl border transition-all duration-200 bg-surface h-full flex flex-col
          ${widget.pinned ? 'border-brand/30' : 'border-border'}
          ${dragOverWidget === widget.id ? 'ring-2 ring-brand/50 border-brand/50' : ''}
        `}
        onDragOver={(e) => handleDragOver(e, widget.id)}
        onDragLeave={handleDragLeave}
        onDrop={(e) => handleDrop(e, widget.id)}
      >
        {/* Widget Header */}
        <div 
          className="flex items-center justify-between px-4 py-3 border-b border-border cursor-grab active:cursor-grabbing select-none"
          draggable
          onDragStart={(e) => handleDragStart(e, widget.id)}
          onDragEnd={(e) => handleDragEnd(e)}
        >
          <div className="flex items-center gap-2">
            <Bars3Icon className="h-4 w-4 text-muted" />
            <EnvelopeIcon className="h-5 w-5 text-brand" />
            <h3 className="font-semibold text-text">{widget.title}</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); handleTogglePin(widget.id); }}
              onMouseDown={(e) => e.stopPropagation()}
              draggable={false}
              className={`p-1.5 rounded hover:bg-surface-2 transition-colors ${widget.pinned ? 'text-brand' : 'text-muted'}`}
              title={widget.pinned ? 'Unpin widget' : 'Pin widget'}
            >
              <svg className="h-4 w-4" fill={widget.pinned ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
            </button>
            {!widget.pinned && (
              <button
                onClick={(e) => { e.stopPropagation(); handleRemoveWidget(widget.id); }}
                onMouseDown={(e) => e.stopPropagation()}
                draggable={false}
                className="p-1.5 rounded hover:bg-surface-2 text-muted hover:text-red-400 transition-colors"
                title="Remove widget"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Widget Content */}
        <div className="flex-1 p-4">
          {templatesLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="animate-spin h-8 w-8 border-2 border-brand/30 border-t-brand rounded-full" />
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-xs text-muted mb-3">Default templates by candidate type</p>
              {defaultTemplates.map((item) => (
                <div 
                  key={item.candidateType}
                  className="flex items-center justify-between py-3 px-1"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      item.candidateType === 'applicant' ? 'bg-green-500' :
                      item.candidateType === 'previous_candidate' ? 'bg-blue-500' :
                      'bg-purple-500'
                    }`} />
                    <span className="text-sm text-muted">{item.candidateTypeLabel}</span>
                  </div>
                  <div className="text-right">
                    {item.templateName ? (
                      <span className="text-sm font-medium text-text">{item.templateName}</span>
                    ) : (
                      <span className="text-sm text-muted/60 italic">Not configured</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Widget Footer */}
        <div className="px-4 py-2 border-t border-border bg-surface-2/20">
          <a 
            href="/talent/email-templates" 
            className="text-xs text-brand hover:text-brand-hover transition-colors"
          >
            Manage Templates →
          </a>
        </div>
      </div>
    );
  };

  // Render Add Widget Button
  const AddWidgetButton = () => (
    <div
      className="w-full h-full min-h-[280px] rounded-xl border-2 border-dashed border-border flex flex-col items-center justify-center gap-3"
    >
      <p className="text-lg font-semibold text-muted">Custom Widgets Coming Soon</p>
      <div className="p-4 rounded-full bg-surface-2">
        <PlusIcon className="h-8 w-8 text-muted/50" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-muted">Add Widget</p>
        <p className="text-xs text-muted/70 mt-1">Customize your dashboard</p>
      </div>
    </div>
  );

  // Sort widgets by order, with pinned widgets maintaining their positions
  const sortedWidgets = [...widgets].sort((a, b) => a.order - b.order);

  return (
    <Layout
      pageTitle="Home"
      breadcrumbs={[{ label: 'Home' }]}
    >
      <div className="h-full overflow-y-auto">
        <div className="pb-8">
          {/* Page Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-text">Welcome to your Dashboard</h1>
            <p className="text-muted mt-1">
              Drag widgets to reorder • Pin widgets to keep them in place • Customize your dashboard
            </p>
          </div>

          {/* Widgets Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {/* Render existing widgets */}
            {sortedWidgets.map(widget => (
              <div 
                key={widget.id}
                style={{ minHeight: '280px' }}
              >
                {widget.type === 'ai_recruiter_stats' && (
                  <AIRecruiterWidget widget={widget} />
                )}
                {widget.type === 'email_templates' && (
                  <EmailTemplatesWidget widget={widget} />
                )}
              </div>
            ))}
            
            {/* Add Widget Button */}
            <div style={{ minHeight: '280px' }}>
              <AddWidgetButton />
            </div>
          </div>

          {/* Tips Section */}
          <div className="mt-8 p-4 bg-surface border border-border rounded-lg">
            <h3 className="text-sm font-semibold text-text mb-2">💡 Tips</h3>
            <ul className="text-sm text-muted space-y-1">
              <li>• <strong>Drag</strong> the grip handle to reorder widgets</li>
              <li>• <strong>Pin</strong> widgets with the bookmark icon to keep them in place</li>
              <li>• <strong>Remove</strong> unpinned widgets with the X button</li>
              <li>• Your layout is automatically saved</li>
            </ul>
          </div>
        </div>
      </div>
    </Layout>
  );
}

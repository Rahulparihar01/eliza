/**
 * Content Research Page - Web Search Based Content Generation
 * 
 * Features:
 * - Topic input with format selection
 * - OpenAI web search for source discovery (HIGH RECALL)
 * - Source multi-selection (like POV selection)
 * - Strict grounding - content uses ONLY selected sources
 * - Citation tracking - every claim must be sourced
 * - No fabricated information
 * 
 * Uses Eliza Forge Design System components
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Layout } from '../../components/layout/Layout';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Input,
  Spinner,
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  Page,
  PageHeader,
  PageBody,
  Textarea,
  Checkbox,
  Label,
} from '../../components/ui';
import {
  SparklesIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  LightBulbIcon,
  BookOpenIcon,
  MagnifyingGlassIcon,
  GlobeAltIcon,
  LinkIcon,
  CheckIcon,
  XMarkIcon,
  ExclamationCircleIcon,
  DocumentArrowDownIcon,
  PencilIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  EyeIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline';

import { AXIOS_INSTANCE } from '../../services/api-client';
import { useToasts } from '../../stores/useToasts';

const API_BASE = '/v1/content-research';

// Types
type RunStatus = 'pending' | 'researching' | 'source_selection' | 'pov_selection' | 'hook_selection' | 'generating' | 'completed' | 'failed';

interface WebSource {
  id: string;
  url: string;
  title: string;
  snippet: string;
  relevance_score?: number;
  query_origin: string;
  source_type: string;
  retrieved_at?: string;
}

interface Citation {
  marker: string;
  source_id: string;
  url: string;
  title: string;
}

interface GeneratedContent {
  run_id: string;
  content: string;
  formatted_content: string;
  word_count: number;
  target_word_count: number;
  sources_cited: string[];
  citations: Citation[];
  uncited_claims: string[];
  generated_at: string;
}

interface ResearchRun {
  run_id: string;
  topic: string;
  target_word_count: number;
  status: RunStatus;
  queries_executed?: string[];
  total_sources_found?: number;
  sources?: WebSource[];
  selected_source_ids?: string[];
  selected_sources?: WebSource[];
  content?: GeneratedContent;
  error_message?: string;
  created_at: string;
}

interface POVOption {
  index: number;
  label: string;
  description: string;
  key_concepts: string[];
  source_refs?: string[];
}

interface HookOption {
  index: number;
  title?: string;
  lede: string;
  line1?: string;
  pattern?: string;
  why_it_works?: string;
}

// Word count presets
const WORD_COUNT_PRESETS = [
  { value: 500, label: 'Short', description: '~500 words' },
  { value: 1000, label: 'Medium', description: '~1000 words' },
  { value: 1500, label: 'Long', description: '~1500 words' },
  { value: 2000, label: 'Very Long', description: '~2000 words' },
];

export default function ContentResearchPage() {
  // Create state
  const [topic, setTopic] = useState('');
  const [targetWordCount, setTargetWordCount] = useState(1000);
  const [numQueries, setNumQueries] = useState(6);
  const [isCreating, setIsCreating] = useState(false);
  
  // Current run state
  const [currentRun, setCurrentRun] = useState<ResearchRun | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  
  // Sources state
  const [sources, setSources] = useState<WebSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [isSelectingSources, setIsSelectingSources] = useState(false);
  
  // POV state
  const [povOptions, setPovOptions] = useState<POVOption[]>([]);
  const [selectedPov, setSelectedPov] = useState<POVOption | null>(null);
  const [isGeneratingPovs, setIsGeneratingPovs] = useState(false);
  
  // Hook state
  const [hookOptions, setHookOptions] = useState<HookOption[]>([]);
  const [selectedHook, setSelectedHook] = useState<HookOption | null>(null);
  const [isGeneratingHooks, setIsGeneratingHooks] = useState(false);
  
  // Content state
  const [generatedContent, setGeneratedContent] = useState<GeneratedContent | null>(null);
  const [isGeneratingContent, setIsGeneratingContent] = useState(false);
  const [isEditingContent, setIsEditingContent] = useState(false);
  const [editedContent, setEditedContent] = useState('');
  const [viewMode, setViewMode] = useState<'raw' | 'rendered'>('rendered');
  
  // Selection-based regeneration state
  const [selectedText, setSelectedText] = useState('');
  const [selectionFeedback, setSelectionFeedback] = useState('');
  const [isRegenerateModalOpen, setIsRegenerateModalOpen] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  
  // Source expansion state
  const [expandedSourceIds, setExpandedSourceIds] = useState<Set<string>>(new Set());
  
  // Research progress state
  const [researchProgress, setResearchProgress] = useState<{
    queriesExecuted: number;
    totalQueries: number;
    sourcesFound: number;
    currentPhase: string;
  }>({ queriesExecuted: 0, totalQueries: numQueries, sourcesFound: 0, currentPhase: 'Initializing research...' });
  
  // Error state
  const [error, setError] = useState<string | null>(null);
  
  // Toast
  const { push: addToast } = useToasts();
  
  // Polling interval ref
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const selectionRangeRef = useRef<Range | null>(null);
  
  // Section refs for auto-scroll
  const sourceSectionRef = useRef<HTMLDivElement>(null);
  const povSectionRef = useRef<HTMLDivElement>(null);
  const contentSectionRef = useRef<HTMLDivElement>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Poll for updates when run is in progress
  useEffect(() => {
    if (currentRun && isPolling && currentRun.status === 'researching') {
      pollingRef.current = setInterval(() => {
        pollRunStatus();
      }, 2000);
      
      return () => {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
        }
      };
    }
  }, [currentRun?.run_id, isPolling]);

  // Auto-scroll to source selection when sources are loaded
  useEffect(() => {
    if (currentRun?.status === 'source_selection' && sources.length > 0) {
      setTimeout(() => {
        sourceSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);
    }
  }, [currentRun?.status, sources.length]);

  // Auto-scroll to POV section
  useEffect(() => {
    if (currentRun?.status === 'pov_selection') {
      setTimeout(() => {
        povSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);
    }
  }, [currentRun?.status]);

  // Auto-scroll to generated content
  useEffect(() => {
    if (generatedContent) {
      setTimeout(() => {
        contentSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 300);
    }
  }, [generatedContent]);

  // Restore text selection highlight after React re-render
  useEffect(() => {
    if (selectedText && selectionRangeRef.current) {
      requestAnimationFrame(() => {
        try {
          const sel = window.getSelection();
          if (sel) {
            sel.removeAllRanges();
            sel.addRange(selectionRangeRef.current!);
          }
        } catch {
          // Range may be invalid if DOM nodes were replaced
        }
      });
    }
  }, [selectedText]);

  const createRun = async () => {
    if (!topic.trim()) {
      setError('Please enter a topic');
      return;
    }
    
    setError(null);
    setIsCreating(true);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${API_BASE}/runs`, {
        topic,
        target_word_count: targetWordCount,
        num_search_queries: numQueries,
      });
      
      const runId = response.data.run_id;
      
      // Load the full run
      const runResponse = await AXIOS_INSTANCE.get(`${API_BASE}/runs/${runId}`);
      setCurrentRun(runResponse.data);
      setIsPolling(true);
      
    } catch (err) {
      console.error('Failed to create run:', err);
      setError('Failed to create run. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  const pollRunStatus = async () => {
    if (!currentRun) return;
    
    try {
      const response = await AXIOS_INSTANCE.get(`${API_BASE}/runs/${currentRun.run_id}`);
      const updatedRun = response.data;
      setCurrentRun(updatedRun);
      
      // Update research progress telemetry
      if (updatedRun.status === 'researching') {
        const queriesExecuted = updatedRun.queries_executed?.length || 0;
        const sourcesFound = updatedRun.total_sources_found || 0;
        const phases = [
          'Generating search queries...',
          'Searching the web...',
          'Analyzing search results...',
          'Discovering additional sources...',
          'Evaluating source relevance...',
          'Finalizing source collection...',
        ];
        const phaseIndex = Math.min(queriesExecuted, phases.length - 1);
        setResearchProgress({
          queriesExecuted,
          totalQueries: numQueries,
          sourcesFound,
          currentPhase: phases[phaseIndex],
        });
      }
      
      // Stop polling when ready for source selection
      if (updatedRun.status === 'source_selection') {
        setIsPolling(false);
        
        // Load sources
        const sourcesResponse = await AXIOS_INSTANCE.get(`${API_BASE}/runs/${currentRun.run_id}/sources`);
        setSources(sourcesResponse.data.sources || []);
      }
      
      if (['completed', 'failed'].includes(updatedRun.status)) {
        setIsPolling(false);
        if (updatedRun.content) {
          setGeneratedContent(updatedRun.content);
          setEditedContent(updatedRun.content.content);
        }
      }
    } catch (err) {
      console.error('Failed to poll run status:', err);
    }
  };

  const toggleSourceSelection = (sourceId: string) => {
    setSelectedSourceIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sourceId)) {
        newSet.delete(sourceId);
      } else {
        newSet.add(sourceId);
      }
      return newSet;
    });
  };

  const selectAllSources = () => {
    setSelectedSourceIds(new Set(sources.map(s => s.id)));
  };

  const clearSourceSelection = () => {
    setSelectedSourceIds(new Set());
  };

  const selectTopSources = (n: number) => {
    const topIds = sources.slice(0, n).map(s => s.id);
    setSelectedSourceIds(new Set(topIds));
  };

  const confirmSourceSelection = async () => {
    if (!currentRun || selectedSourceIds.size === 0) {
      setError('Please select at least one source');
      return;
    }
    
    setIsSelectingSources(true);
    setError(null);
    
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/select-sources`, {
        source_ids: Array.from(selectedSourceIds),
      });
      
      // Refresh run status
      const response = await AXIOS_INSTANCE.get(`${API_BASE}/runs/${currentRun.run_id}`);
      setCurrentRun(response.data);
      
    } catch (err) {
      console.error('Failed to select sources:', err);
      setError('Failed to select sources');
    } finally {
      setIsSelectingSources(false);
    }
  };

  const generatePovs = async () => {
    if (!currentRun) return;
    
    setIsGeneratingPovs(true);
    setError(null);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/generate-povs`);
      setPovOptions(response.data);
    } catch (err) {
      console.error('Failed to generate POVs:', err);
      setError('Failed to generate POV options');
    } finally {
      setIsGeneratingPovs(false);
    }
  };

  const selectPov = async (pov: POVOption) => {
    if (!currentRun) return;
    
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/select-pov`, {
        pov_index: pov.index,
      });
      setSelectedPov(pov);
    } catch (err) {
      console.error('Failed to select POV:', err);
      setError('Failed to select POV');
    }
  };

  const generateHooks = async () => {
    if (!currentRun) return;
    
    setIsGeneratingHooks(true);
    setError(null);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/generate-hooks`);
      setHookOptions(response.data);
    } catch (err) {
      console.error('Failed to generate hooks:', err);
      setError('Failed to generate hook options');
    } finally {
      setIsGeneratingHooks(false);
    }
  };

  const selectHook = async (hook: HookOption) => {
    if (!currentRun) return;
    
    try {
      await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/select-hook`, {
        hook_index: hook.index,
      });
      setSelectedHook(hook);
    } catch (err) {
      console.error('Failed to select hook:', err);
      setError('Failed to select hook');
    }
  };

  const generateContent = async () => {
    if (!currentRun) return;
    
    setIsGeneratingContent(true);
    setError(null);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/generate`, {
        use_selected_pov: !!selectedPov,
        use_selected_hook: !!selectedHook,
        strict_grounding: true,
      });
      
      setGeneratedContent(response.data.content);
      setEditedContent(response.data.content.content);
      
      // Check for warnings
      if (response.data.warnings?.uncited_claims?.length > 0) {
        setError(`Warning: ${response.data.warnings.uncited_claims.length} claims may not be fully sourced`);
      }
      
      // Refresh run
      const runResponse = await AXIOS_INSTANCE.get(`${API_BASE}/runs/${currentRun.run_id}`);
      setCurrentRun(runResponse.data);
      
    } catch (err) {
      console.error('Failed to generate content:', err);
      setError('Failed to generate content');
    } finally {
      setIsGeneratingContent(false);
    }
  };

  const resetToCreate = () => {
    setCurrentRun(null);
    setSources([]);
    setSelectedSourceIds(new Set());
    setPovOptions([]);
    setSelectedPov(null);
    setHookOptions([]);
    setSelectedHook(null);
    setGeneratedContent(null);
    setIsEditingContent(false);
    setEditedContent('');
    setExpandedSourceIds(new Set());
    setViewMode('rendered');
    setSelectedText('');
    setSelectionFeedback('');
    selectionRangeRef.current = null;
    setIsRegenerateModalOpen(false);
    setIsPolling(false);
    setError(null);
  };

  // Handle text selection for regeneration
  const handleTextSelection = () => {
    const selection = window.getSelection();
    if (selection && selection.toString().trim().length > 5 && selection.rangeCount > 0) {
      // Save the range before state update causes re-render
      selectionRangeRef.current = selection.getRangeAt(0).cloneRange();
      setSelectedText(selection.toString().trim());
    } else {
      selectionRangeRef.current = null;
      setSelectedText('');
    }
  };

  // Open regenerate modal with selected text
  const openRegenerateModal = () => {
    // Check if we already have selected text
    if (selectedText && selectedText.trim().length > 5) {
      setSelectionFeedback('');
      setIsRegenerateModalOpen(true);
      return;
    }
    
    // Otherwise, try to get current selection
    const selection = window.getSelection();
    if (selection && selection.toString().trim().length > 5) {
      setSelectedText(selection.toString().trim());
      setSelectionFeedback('');
      setIsRegenerateModalOpen(true);
    } else {
      // Show a helpful message if no text is selected
      alert('Please select some text (at least 5 characters) to improve. Click and drag over the text you want to improve.');
    }
  };

  // Regenerate selected portion of content
  // Helper function to find and replace text even when markdown formatting differs
  const smartReplace = (content: string, searchText: string, replacement: string): string | null => {
    // First, try exact match
    if (content.includes(searchText)) {
      return content.replace(searchText, replacement);
    }
    
    // Strip markdown formatting from both for fuzzy matching
    const stripMarkdown = (text: string) => text
      .replace(/\*\*/g, '')  // bold
      .replace(/\*/g, '')    // italic
      .replace(/__/g, '')    // bold alt
      .replace(/_/g, '')     // italic alt
      .replace(/`/g, '')     // code
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // links
      .replace(/#+\s/g, '')  // headers
      .replace(/>\s/g, '')   // blockquotes
      .trim();
    
    const strippedSearch = stripMarkdown(searchText);
    
    // Find where the stripped text appears in the stripped content
    const strippedContent = stripMarkdown(content);
    const strippedIndex = strippedContent.indexOf(strippedSearch);
    
    if (strippedIndex === -1) {
      return null; // Can't find the text
    }
    
    // Find the actual start/end positions in the original content
    // by counting characters while accounting for stripped markdown
    let actualStart = 0;
    let strippedPos = 0;
    
    for (let i = 0; i < content.length && strippedPos < strippedIndex; i++) {
      const char = content[i];
      const nextChar = content[i + 1] || '';
      
      // Skip markdown characters
      if ((char === '*' && nextChar === '*') || (char === '_' && nextChar === '_')) {
        actualStart = i + 2;
        i++; // Skip next char too
      } else if (char === '*' || char === '_' || char === '`') {
        actualStart = i + 1;
      } else if (char === '#' && (i === 0 || content[i - 1] === '\n')) {
        while (content[actualStart] === '#' || content[actualStart] === ' ') actualStart++;
      } else {
        actualStart = i + 1;
        strippedPos++;
      }
    }
    
    // Fallback: find the closest match by searching for key phrases
    const words = strippedSearch.split(/\s+/).filter(w => w.length > 3);
    if (words.length > 0) {
      // Find a section that contains all the key words
      for (let i = 0; i < content.length - 50; i++) {
        const chunk = content.slice(i, i + strippedSearch.length + 100);
        const chunkStripped = stripMarkdown(chunk);
        if (chunkStripped.includes(strippedSearch)) {
          // Found it! Now extract the actual markdown portion
          const startIdx = i;
          const endIdx = i + chunk.indexOf(stripMarkdown(chunk.slice(chunk.length - 50))) + strippedSearch.length;
          
          // Find the end by matching character counts
          let matchedChars = 0;
          let endPos = startIdx;
          for (let j = startIdx; j < content.length && matchedChars < strippedSearch.length; j++) {
            const c = content[j];
            if (c !== '*' && c !== '_' && c !== '`' && c !== '#' && c !== '[' && c !== ']' && c !== '(' && c !== ')') {
              matchedChars++;
            }
            endPos = j + 1;
          }
          
          const originalSection = content.slice(startIdx, endPos);
          return content.slice(0, startIdx) + replacement + content.slice(endPos);
        }
      }
    }
    
    return null;
  };

  const regenerateSelection = async () => {
    if (!currentRun || !selectedText || !selectionFeedback.trim()) return;
    
    setIsRegenerating(true);
    setError(null);
    
    try {
      // Get the current content (use editedContent if available, otherwise use generatedContent)
      const currentContent = editedContent || generatedContent?.content || '';
      
      if (!currentContent) {
        setError('No content available to regenerate');
        return;
      }
      
      const response = await AXIOS_INSTANCE.post(`${API_BASE}/runs/${currentRun.run_id}/regenerate-section`, {
        original_text: selectedText,
        feedback: selectionFeedback,
        full_content: currentContent,
      });
      
      // Replace the selected text in the content using smart matching
      const newContent = smartReplace(currentContent, selectedText, response.data.regenerated_text);
      
      if (!newContent) {
        console.warn('Could not find text to replace. Selected:', selectedText.slice(0, 100));
        setError('Could not locate the selected text in the content. Try selecting in Raw mode or select a longer passage.');
        return;
      }
      
      // Update both editedContent and generatedContent so both views show the update
      setEditedContent(newContent);
      
      if (generatedContent) {
        setGeneratedContent({
          ...generatedContent,
          content: newContent,
          word_count: newContent.split(/\s+/).filter(Boolean).length,
        });
      }
      
      setIsRegenerateModalOpen(false);
      setSelectedText('');
      setSelectionFeedback('');
      selectionRangeRef.current = null;
      
    } catch (err) {
      console.error('Failed to regenerate section:', err);
      setError('Failed to regenerate section');
    } finally {
      setIsRegenerating(false);
    }
  };

  // Helper functions
  const getStatusBadgeVariant = (status: RunStatus): 'default' | 'success' | 'warning' | 'danger' | 'secondary' => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'danger';
      case 'researching':
      case 'generating': return 'warning';
      default: return 'secondary';
    }
  };

  const getStatusLabel = (status: RunStatus): string => {
    switch (status) {
      case 'pending': return 'Pending';
      case 'researching': return 'Searching Web...';
      case 'source_selection': return 'Select Sources';
      case 'pov_selection': return 'Select POV';
      case 'hook_selection': return 'Select Hook';
      case 'generating': return 'Generating...';
      case 'completed': return 'Completed';
      case 'failed': return 'Failed';
      default: return status;
    }
  };

  const getRelevanceColor = (score?: number): string => {
    if (!score) return 'text-gray-400';
    if (score >= 0.8) return 'text-emerald-500';
    if (score >= 0.6) return 'text-amber-500';
    return 'text-gray-400';
  };

  // Determine current step
  const getCurrentStep = (): number => {
    if (!currentRun) return 0;
    if (currentRun.status === 'researching') return 1;
    if (currentRun.status === 'source_selection' || (sources.length > 0 && selectedSourceIds.size === 0)) return 2;
    if (!generatedContent) return 3;
    return 4;
  };

  // Memoize ReactMarkdown components to prevent DOM recreation on unrelated re-renders
  // This preserves text selection highlights when selectedText state changes
  const markdownComponents = useMemo(() => ({
    h1: ({ children }: any) => <h1 className="text-2xl font-bold mt-6 mb-4 text-charcoal dark:text-white">{children}</h1>,
    h2: ({ children }: any) => <h2 className="text-xl font-bold mt-5 mb-3 text-charcoal dark:text-white">{children}</h2>,
    h3: ({ children }: any) => <h3 className="text-lg font-semibold mt-4 mb-2 text-charcoal dark:text-white">{children}</h3>,
    p: ({ children }: any) => <p className="mb-4 leading-relaxed text-gray-700 dark:text-gray-300">{children}</p>,
    ul: ({ children }: any) => <ul className="list-disc list-inside mb-4 space-y-1">{children}</ul>,
    ol: ({ children }: any) => <ol className="list-decimal list-inside mb-4 space-y-1">{children}</ol>,
    li: ({ children }: any) => <li className="text-gray-700 dark:text-gray-300">{children}</li>,
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-4 border-eliza-red pl-4 italic text-gray-600 dark:text-gray-400 my-4">
        {children}
      </blockquote>
    ),
    strong: ({ children }: any) => <strong className="font-semibold text-charcoal dark:text-white">{children}</strong>,
    em: ({ children }: any) => <em className="italic">{children}</em>,
    a: ({ href, children }: any) => (
      <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
        {children}
      </a>
    ),
    hr: () => <hr className="my-6 border-gray-200 dark:border-dark-border" />,
  }), []);

  return (
    <Layout>
      <Page maxWidth="xl">
        <PageHeader
          title="Research-First Content Writer"
          description="Generate content backed by real web sources - no fabricated information"
          actions={
            currentRun ? (
              <div className="flex items-center gap-4">
                <Badge variant={getStatusBadgeVariant(currentRun.status)}>
                  {getStatusLabel(currentRun.status)}
                </Badge>
                <Button variant="secondary" size="sm" onClick={resetToCreate}>
                  <ArrowPathIcon className="h-4 w-4" />
                  Start New
                </Button>
              </div>
            ) : undefined
          }
        />

        <PageBody>
          {!currentRun ? (
            <div className="max-w-3xl mx-auto space-y-6">
              {/* Error */}
              {error && (
                <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-900/20">
                  <CardContent className="p-4 flex items-start gap-3">
                    <ExclamationTriangleIcon className="h-5 w-5 text-rose-500 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-rose-700 dark:text-rose-300">{error}</p>
                  </CardContent>
                </Card>
              )}

              {/* Info Banner */}
              <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <GlobeAltIcon className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-blue-800 dark:text-blue-200">Powered by OpenAI Web Search</p>
                      <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                        We search blogs, articles, and research for real sources (no e-commerce or spam), 
                        let you pick which ones to use, and generate content <strong>strictly from those sources</strong>. 
                        Every claim is cited.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Topic */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <LightBulbIcon className="h-5 w-5 text-eliza-red" />
                    Topic
                  </CardTitle>
                  <CardDescription>What do you want to research and write about?</CardDescription>
                </CardHeader>
                <CardContent>
                  <Textarea
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Enter your topic, thesis, or key message..."
                    rows={3}
                  />
                </CardContent>
              </Card>

              {/* Word Count */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <DocumentTextIcon className="h-5 w-5 text-eliza-red" />
                    Length
                  </CardTitle>
                  <CardDescription>Target word count for your content</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-4 gap-3 mb-4">
                    {WORD_COUNT_PRESETS.map((preset) => (
                      <button
                        key={preset.value}
                        onClick={() => setTargetWordCount(preset.value)}
                        className={`p-3 rounded-xl border-2 text-center transition-all ${
                          targetWordCount === preset.value
                            ? 'border-eliza-red bg-eliza-red/5'
                            : 'border-gray-200 dark:border-dark-border hover:border-eliza-red/50'
                        }`}
                      >
                        <p className="font-medium text-charcoal dark:text-gray-100">{preset.label}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{preset.description}</p>
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={300}
                      max={3000}
                      step={100}
                      value={targetWordCount}
                      onChange={(e) => setTargetWordCount(parseInt(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-sm font-medium text-charcoal dark:text-gray-100 w-28">
                      {targetWordCount} words
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Search Depth */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MagnifyingGlassIcon className="h-5 w-5 text-eliza-red" />
                    Research Depth
                  </CardTitle>
                  <CardDescription>More queries = more sources found</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={3}
                      max={10}
                      value={numQueries}
                      onChange={(e) => setNumQueries(parseInt(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-sm font-medium text-charcoal dark:text-gray-100 w-24">
                      {numQueries} queries
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                    Recommended: 6 queries for balanced coverage
                  </p>
                </CardContent>
              </Card>

              {/* Create Button */}
              <div className="flex justify-center pt-4">
                <Button
                  variant="brand"
                  size="lg"
                  onClick={createRun}
                  disabled={isCreating}
                >
                  {isCreating ? (
                    <>
                      <Spinner size="sm" />
                      Starting Research...
                    </>
                  ) : (
                    <>
                      <MagnifyingGlassIcon className="h-5 w-5" />
                      Search & Find Sources
                    </>
                  )}
                </Button>
              </div>
            </div>
          ) : (
            // ============ RUN IN PROGRESS / WORKFLOW VIEW ============
            <div className="space-y-6 pb-12">
              {/* Error */}
              {error && (
                <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-900/20">
                  <CardContent className="p-4 flex items-start gap-3">
                    <ExclamationTriangleIcon className="h-5 w-5 text-rose-500 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-rose-700 dark:text-rose-300">{error}</p>
                  </CardContent>
                </Card>
              )}

              {/* Progress Steps */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    {['Search', 'Select Sources', 'Generate', 'Done'].map((step, i) => (
                      <div key={step} className="flex items-center">
                        <div className={`flex items-center justify-center w-8 h-8 rounded-full ${
                          getCurrentStep() > i + 1 
                            ? 'bg-emerald-500 text-white'
                            : getCurrentStep() === i + 1
                            ? 'bg-eliza-red text-white'
                            : 'bg-gray-200 dark:bg-dark-surface-2 text-gray-500'
                        }`}>
                          {getCurrentStep() > i + 1 ? (
                            <CheckIcon className="h-4 w-4" />
                          ) : (
                            <span className="text-sm font-medium">{i + 1}</span>
                          )}
                        </div>
                        <span className={`ml-2 text-sm ${
                          getCurrentStep() >= i + 1 
                            ? 'text-charcoal dark:text-gray-100 font-medium' 
                            : 'text-gray-400'
                        }`}>
                          {step}
                        </span>
                        {i < 3 && (
                          <div className={`w-12 h-0.5 mx-4 ${
                            getCurrentStep() > i + 1 
                              ? 'bg-emerald-500' 
                              : 'bg-gray-200 dark:bg-dark-surface-2'
                          }`} />
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Topic Header */}
              <Card>
                <CardContent className="p-4">
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Topic</p>
                  <p className="font-medium text-lg text-charcoal dark:text-gray-100">{currentRun.topic}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="secondary">{currentRun.target_word_count} words</Badge>
                  </div>
                </CardContent>
              </Card>

              {/* Research in Progress */}
              {currentRun.status === 'researching' && (
                <Card>
                  <CardContent className="py-8">
                    <div className="text-center mb-6">
                      <Spinner size="lg" className="mb-4" />
                      <p className="text-charcoal dark:text-gray-100 font-medium">{researchProgress.currentPhase}</p>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Finding sources for your topic using OpenAI web search
                      </p>
                    </div>
                    
                    {/* Progress indicators */}
                    <div className="max-w-md mx-auto space-y-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500 dark:text-gray-400">Queries executed</span>
                        <span className="font-medium text-charcoal dark:text-gray-100">
                          {researchProgress.queriesExecuted} / {researchProgress.totalQueries}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 dark:bg-dark-surface-2 rounded-full h-2">
                        <div 
                          className="bg-eliza-red h-2 rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(5, (researchProgress.queriesExecuted / researchProgress.totalQueries) * 100)}%` }}
                        />
                      </div>
                      {researchProgress.sourcesFound > 0 && (
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-gray-500 dark:text-gray-400">Sources discovered</span>
                          <Badge variant="success">{researchProgress.sourcesFound} sources</Badge>
                        </div>
                      )}
                    </div>
                    
                    {/* Queries list */}
                    {currentRun.queries_executed && currentRun.queries_executed.length > 0 && (
                      <div className="mt-6 max-w-lg mx-auto">
                        <p className="text-xs text-gray-400 dark:text-gray-500 mb-2 uppercase tracking-wide font-medium">Search Queries</p>
                        <div className="space-y-1.5">
                          {currentRun.queries_executed.map((query, i) => (
                            <div key={i} className="flex items-center gap-2 text-sm">
                              <CheckCircleIcon className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                              <span className="text-gray-600 dark:text-gray-300 truncate">{query}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* ============ SOURCE SELECTION ============ */}
              {(currentRun.status === 'source_selection' || 
                (sources.length > 0 && !generatedContent)) && (
                <div ref={sourceSectionRef}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <BookOpenIcon className="h-5 w-5 text-eliza-red" />
                      Step 2: Select Your Sources
                    </CardTitle>
                    <CardDescription>
                      Choose which sources to use. Content will be generated <strong>strictly</strong> from selected sources.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {/* Quick Actions */}
                    <div className="flex flex-wrap items-center gap-2 mb-4 pb-4 border-b border-gray-200 dark:border-dark-border">
                      <Button variant="secondary" size="sm" onClick={selectAllSources}>
                        Select All ({sources.length})
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => selectTopSources(5)}>
                        Top 5 Sources
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => selectTopSources(10)}>
                        Top 10 Sources
                      </Button>
                      <Button variant="secondary" size="sm" onClick={clearSourceSelection}>
                        Clear Selection
                      </Button>
                      <div className="ml-auto">
                        <Badge variant={selectedSourceIds.size > 0 ? 'success' : 'secondary'}>
                          {selectedSourceIds.size} selected
                        </Badge>
                      </div>
                    </div>

                    {/* Sources List */}
                    <div className="space-y-3 max-h-[600px] overflow-y-auto">
                      {sources.map((source, index) => {
                        const isExpanded = expandedSourceIds.has(source.id);
                        return (
                          <div
                            key={source.id}
                            className={`rounded-xl border-2 transition-all ${
                              selectedSourceIds.has(source.id)
                                ? 'border-eliza-red bg-eliza-red/5'
                                : 'border-gray-200 dark:border-dark-border hover:border-eliza-red/50'
                            }`}
                          >
                            {/* Main clickable area for selection */}
                            <button
                              onClick={() => toggleSourceSelection(source.id)}
                              className="w-full p-4 text-left"
                            >
                              <div className="flex items-start gap-3">
                                <div className="flex-shrink-0 mt-1">
                                  <Checkbox
                                    checked={selectedSourceIds.has(source.id)}
                                    onChange={() => {}}
                                  />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs text-gray-400">#{index + 1}</span>
                                    <span className="text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded">
                                      {new URL(source.url).hostname.replace('www.', '')}
                                    </span>
                                    {source.relevance_score && (
                                      <span className={`text-xs font-medium ${getRelevanceColor(source.relevance_score)}`}>
                                        {Math.round(source.relevance_score * 100)}% match
                                      </span>
                                    )}
                                  </div>
                                  <p className="font-medium text-charcoal dark:text-gray-100">
                                    {source.title && source.title !== 'Untitled' ? source.title : source.snippet?.slice(0, 100) || 'Web Source'}
                                  </p>
                                </div>
                                {selectedSourceIds.has(source.id) && (
                                  <CheckCircleIcon className="h-6 w-6 text-eliza-red flex-shrink-0" />
                                )}
                              </div>
                            </button>
                            
                            {/* Content preview - always visible */}
                            <div className="px-4 pb-2">
                              <div className="ml-9 bg-gray-50 dark:bg-dark-surface-2 rounded-lg p-3 text-sm text-gray-700 dark:text-gray-300">
                                {(() => {
                                  // Check if snippet exists and is not JSON-like
                                  const hasValidSnippet = source.snippet && 
                                    source.snippet.length > 20 && 
                                    !source.snippet.includes('"url":') &&
                                    !source.snippet.includes('"snippet":') &&
                                    !source.snippet.startsWith('{') &&
                                    !source.snippet.startsWith('[');
                                  
                                  if (hasValidSnippet) {
                                    const isLong = source.snippet.length > 150;
                                    return (
                                      <div className="relative">
                                        <p style={isExpanded || !isLong ? undefined : { maxHeight: '6em', overflow: 'hidden' }}>
                                          {source.snippet}
                                        </p>
                                        {!isExpanded && isLong && (
                                          <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-gray-50 dark:from-dark-surface-2 to-transparent pointer-events-none" />
                                        )}
                                      </div>
                                    );
                                  } else {
                                    return (
                                      <div className="text-gray-500 dark:text-gray-400 italic">
                                        <p>Found via search: "{source.query_origin}"</p>
                                        <p className="mt-1 text-xs">Click the link below to view the full source content.</p>
                                      </div>
                                    );
                                  }
                                })()}
                              </div>
                            </div>
                            
                            {/* Expand/Collapse and Link row */}
                            <div className="px-4 pb-3 flex items-center justify-between ml-9">
                              {(() => {
                                // Only show expand button for valid, long snippets
                                const hasValidLongSnippet = source.snippet && 
                                  source.snippet.length > 150 && 
                                  !source.snippet.includes('"url":') &&
                                  !source.snippet.includes('"snippet":') &&
                                  !source.snippet.startsWith('{') &&
                                  !source.snippet.startsWith('[');
                                
                                if (hasValidLongSnippet) {
                                  return (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setExpandedSourceIds(prev => {
                                          const next = new Set(prev);
                                          if (next.has(source.id)) {
                                            next.delete(source.id);
                                          } else {
                                            next.add(source.id);
                                          }
                                          return next;
                                        });
                                      }}
                                      className="flex items-center gap-1 text-xs text-eliza-red hover:text-eliza-red/80 font-medium py-1 px-2 rounded-md hover:bg-eliza-red/5 transition-colors"
                                    >
                                      {isExpanded ? (
                                        <>
                                          <ChevronUpIcon className="h-4 w-4" />
                                          Show less
                                        </>
                                      ) : (
                                        <>
                                          <ChevronDownIcon className="h-4 w-4" />
                                          Show more
                                        </>
                                      )}
                                    </button>
                                  );
                                }
                                return null;
                              })()}
                              <a 
                                href={source.url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 text-xs text-blue-500 hover:underline ml-auto"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <LinkIcon className="h-3 w-3" />
                                <span className="truncate max-w-[250px]">{source.url}</span>
                              </a>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Confirm Selection */}
                    <div className="flex justify-center mt-6 pt-4 border-t border-gray-200 dark:border-dark-border">
                      <Button
                        variant="brand"
                        size="lg"
                        onClick={confirmSourceSelection}
                        disabled={isSelectingSources || selectedSourceIds.size === 0}
                      >
                        {isSelectingSources ? (
                          <>
                            <Spinner size="sm" />
                            Confirming...
                          </>
                        ) : (
                          <>
                            <CheckIcon className="h-5 w-5" />
                            Use {selectedSourceIds.size} Sources
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
                </div>
              )}

              {/* ============ POV SELECTION (Optional) ============ */}
              {currentRun.status === 'pov_selection' && !generatedContent && (
                <div ref={povSectionRef}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <SparklesIcon className="h-5 w-5 text-eliza-red" />
                      Step 3a: Choose POV (Optional)
                    </CardTitle>
                    <CardDescription>
                      Select a point of view, or skip to generate content directly
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {povOptions.length === 0 ? (
                      <div className="text-center py-8">
                        <Button
                          variant="secondary"
                          onClick={generatePovs}
                          disabled={isGeneratingPovs}
                        >
                          {isGeneratingPovs ? (
                            <>
                              <Spinner size="sm" />
                              Generating POV Options...
                            </>
                          ) : (
                            <>
                              <SparklesIcon className="h-4 w-4" />
                              Generate POV Options
                            </>
                          )}
                        </Button>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                          Or skip to generate content with a neutral POV
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {povOptions.map((pov) => (
                          <button
                            key={pov.index}
                            onClick={() => selectPov(pov)}
                            className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                              selectedPov?.index === pov.index
                                ? 'border-eliza-red bg-eliza-red/5'
                                : 'border-gray-200 dark:border-dark-border hover:border-eliza-red/50'
                            }`}
                          >
                            <div className="flex items-start gap-3">
                              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-eliza-red/10 flex items-center justify-center">
                                <span className="text-sm font-medium text-eliza-red">{pov.index + 1}</span>
                              </div>
                              <div className="flex-1">
                                <p className="font-medium text-charcoal dark:text-gray-100">{pov.label}</p>
                                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{pov.description}</p>
                                <div className="flex flex-wrap gap-2 mt-2">
                                  {pov.key_concepts.map((concept, i) => (
                                    <Badge key={i} variant="secondary">{concept}</Badge>
                                  ))}
                                </div>
                              </div>
                              {selectedPov?.index === pov.index && (
                                <CheckCircleIcon className="h-6 w-6 text-eliza-red flex-shrink-0" />
                              )}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Generate Content Button */}
                    <div className="flex justify-center mt-6 pt-4 border-t border-gray-200 dark:border-dark-border">
                      <Button
                        variant="brand"
                        size="lg"
                        onClick={generateContent}
                        disabled={isGeneratingContent}
                      >
                        {isGeneratingContent ? (
                          <>
                            <Spinner size="sm" />
                            Generating Content...
                          </>
                        ) : (
                          <>
                            <SparklesIcon className="h-5 w-5" />
                            Generate Content
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
                </div>
              )}

              {/* ============ GENERATED CONTENT ============ */}
              {generatedContent && (
                <div ref={contentSectionRef}>
                  <Card>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <CardTitle className="flex items-center gap-2">
                            <DocumentTextIcon className="h-5 w-5 text-eliza-red" />
                            Your Content
                          </CardTitle>
                          <CardDescription>
                            {(editedContent || generatedContent.content).split(/\s+/).filter(Boolean).length.toLocaleString()} words • 
                            {generatedContent.sources_cited.length} sources cited
                          </CardDescription>
                        </div>
                        {/* View Mode Toggle */}
                        {!isEditingContent && (
                          <div className="flex items-center gap-1 bg-gray-100 dark:bg-dark-surface-2 rounded-lg p-1">
                            <button
                              onClick={() => setViewMode('rendered')}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                                viewMode === 'rendered'
                                  ? 'bg-white dark:bg-dark-surface shadow-sm text-charcoal dark:text-white'
                                  : 'text-gray-500 hover:text-gray-700'
                              }`}
                            >
                              <EyeIcon className="h-4 w-4" />
                              Preview
                            </button>
                            <button
                              onClick={() => setViewMode('raw')}
                              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                                viewMode === 'raw'
                                  ? 'bg-white dark:bg-dark-surface shadow-sm text-charcoal dark:text-white'
                                  : 'text-gray-500 hover:text-gray-700'
                              }`}
                            >
                              <CodeBracketIcon className="h-4 w-4" />
                              Raw
                            </button>
                          </div>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent>
                      {/* Uncited Claims Warning */}
                      {generatedContent.uncited_claims.length > 0 && (
                        <div className="mb-4 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg">
                          <div className="flex items-start gap-3">
                            <ExclamationCircleIcon className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                            <div>
                              <p className="font-medium text-amber-800 dark:text-amber-200">
                                Some claims may need verification
                              </p>
                              <ul className="text-sm text-amber-700 dark:text-amber-300 mt-2 list-disc list-inside">
                                {generatedContent.uncited_claims.map((claim, i) => (
                                  <li key={i}>{claim}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Selection hint - show in both view modes */}
                      {!isEditingContent && (
                        <div className="mb-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm text-blue-700 dark:text-blue-300">
                          <strong>AI Editing:</strong> Select any text below and click "Improve Selection" to have AI rewrite just that part based on your feedback.
                        </div>
                      )}

                      {/* Content - View or Edit Mode */}
                      {isEditingContent ? (
                        <div className="space-y-3">
                          <Textarea
                            value={editedContent}
                            onChange={(e) => setEditedContent(e.target.value)}
                            rows={20}
                            className="font-serif text-base"
                            placeholder="Edit your content..."
                          />
                          <div className="flex items-center justify-between text-sm text-gray-500">
                            <span>{editedContent.split(/\s+/).filter(Boolean).length} words</span>
                            <span className="text-xs">Tip: Citation markers like [Source 1] will still work</span>
                          </div>
                        </div>
                      ) : viewMode === 'rendered' ? (
                        /* Rendered Markdown View */
                        <div 
                          className="prose prose-lg dark:prose-invert max-w-none bg-white dark:bg-dark-surface rounded-xl p-6 border border-gray-200 dark:border-dark-border"
                          ref={contentRef}
                          onMouseUp={handleTextSelection}
                        >
                          <ReactMarkdown components={markdownComponents}>
                            {editedContent || generatedContent.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        /* Raw Text View - supports selection for regeneration */
                        <div 
                          className="bg-gray-50 dark:bg-dark-surface-2 rounded-xl p-6 whitespace-pre-wrap font-mono text-sm"
                          ref={contentRef}
                          onMouseUp={handleTextSelection}
                        >
                          {editedContent || generatedContent.content}
                        </div>
                      )}

                      {/* Selection Action Bar - shown when text is selected */}
                      {selectedText && !isEditingContent && (
                        <div className="mt-3 p-3 bg-eliza-red/10 border border-eliza-red/30 rounded-lg flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-eliza-red">Text selected</p>
                            <p className="text-xs text-gray-600 dark:text-gray-400 truncate">
                              "{selectedText.slice(0, 50)}{selectedText.length > 50 ? '...' : ''}"
                            </p>
                          </div>
                          <div className="flex items-center gap-2 ml-3">
                            <Button
                              variant="brand"
                              size="sm"
                              onClick={openRegenerateModal}
                            >
                              <ArrowPathIcon className="h-4 w-4" />
                              Improve Selection
                            </Button>
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => setSelectedText('')}
                            >
                              <XMarkIcon className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-3 mt-4 flex-wrap">
                        {isEditingContent ? (
                          <>
                            <Button 
                              variant="brand" 
                              onClick={() => setIsEditingContent(false)}
                            >
                              <CheckIcon className="h-4 w-4" />
                              Done Editing
                            </Button>
                            <Button 
                              variant="secondary" 
                              onClick={() => {
                                setEditedContent(generatedContent.content);
                                setIsEditingContent(false);
                              }}
                            >
                              <XMarkIcon className="h-4 w-4" />
                              Discard Changes
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button 
                              variant="brand" 
                              onClick={openRegenerateModal}
                              disabled={!selectedText || selectedText.trim().length < 5}
                              title={!selectedText ? "Select some text first, then click to improve it" : "Improve the selected text"}
                            >
                              <ArrowPathIcon className="h-4 w-4" />
                              Improve Selection
                            </Button>
                            <Button 
                              variant="secondary" 
                              onClick={() => {
                                setEditedContent(editedContent || generatedContent.content);
                                setIsEditingContent(true);
                              }}
                            >
                              <PencilIcon className="h-4 w-4" />
                              Edit Content
                            </Button>
                            <Button 
                              variant="secondary" 
                              onClick={() => {
                                navigator.clipboard.writeText(editedContent || generatedContent.content);
                                addToast({ kind: 'success', message: 'Content copied to clipboard!' });
                              }}
                            >
                              Copy Content
                            </Button>
                            <Button 
                              variant="secondary" 
                              onClick={() => {
                                // Build formatted content with references
                                const content = editedContent || generatedContent.content;
                                const refs = generatedContent.citations.map(c => 
                                  `${c.marker}: ${c.title} - ${c.url}`
                                ).join('\n');
                                navigator.clipboard.writeText(`${content}\n\n---\nSources:\n${refs}`);
                                addToast({ kind: 'success', message: 'Content with references copied to clipboard!' });
                              }}
                            >
                              <DocumentArrowDownIcon className="h-4 w-4" />
                              Copy with References
                            </Button>
                          </>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Citations */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <LinkIcon className="h-5 w-5 text-eliza-red" />
                        Sources Used
                      </CardTitle>
                      <CardDescription>
                        All {generatedContent.citations.length} sources cited in the content
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {generatedContent.citations.map((citation) => (
                          <div 
                            key={citation.source_id}
                            className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-lg"
                          >
                            <Badge variant="secondary" className="flex-shrink-0">
                              {citation.marker}
                            </Badge>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm text-charcoal dark:text-gray-100">
                                {citation.title}
                              </p>
                              <a 
                                href={citation.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-blue-500 hover:underline truncate block"
                              >
                                {citation.url}
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* Failed State */}
              {currentRun.status === 'failed' && (
                <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-900/20">
                  <CardContent className="py-8 text-center">
                    <ExclamationTriangleIcon className="h-12 w-12 text-rose-500 mx-auto mb-4" />
                    <p className="font-medium text-rose-800 dark:text-rose-200">Research Failed</p>
                    <p className="text-sm text-rose-700 dark:text-rose-300 mt-1">
                      {currentRun.error_message || 'An error occurred'}
                    </p>
                    <Button variant="secondary" className="mt-4" onClick={resetToCreate}>
                      Try Again
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </PageBody>
      </Page>

      {/* Regenerate Selection Modal */}
      <Modal open={isRegenerateModalOpen} onClose={() => setIsRegenerateModalOpen(false)}>
        <ModalContent>
          <ModalHeader>
            <ModalTitle className="flex items-center gap-2">
              <ArrowPathIcon className="h-5 w-5 text-eliza-red" />
              Improve Selected Text
            </ModalTitle>
          </ModalHeader>
          <ModalBody>
            <div className="space-y-4">
              {/* Selected Text Preview */}
              <div>
                <Label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                  Selected Text
                </Label>
                <div className="bg-gray-100 dark:bg-dark-surface-2 rounded-lg p-3 text-sm text-gray-600 dark:text-gray-400 max-h-32 overflow-y-auto">
                  "{selectedText}"
                </div>
              </div>

              {/* Feedback Input */}
              <div>
                <Label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 block">
                  What should be improved?
                </Label>
                <Textarea
                  value={selectionFeedback}
                  onChange={(e) => setSelectionFeedback(e.target.value)}
                  placeholder="e.g., Make it more concise, add more detail, change the tone to be more professional, fix the grammar..."
                  rows={3}
                />
              </div>

              {/* Suggestions */}
              <div className="flex flex-wrap gap-2">
                <span className="text-xs text-gray-500">Quick suggestions:</span>
                {['Make it shorter', 'Add more detail', 'More professional tone', 'Simpler language', 'Add an example'].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setSelectionFeedback(suggestion)}
                    className="text-xs px-2 py-1 bg-gray-100 dark:bg-dark-surface-2 rounded-full hover:bg-gray-200 dark:hover:bg-dark-border transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="secondary"
              onClick={() => {
                setIsRegenerateModalOpen(false);
                setSelectedText('');
                setSelectionFeedback('');
              }}
            >
              Cancel
            </Button>
            <Button
              variant="brand"
              onClick={regenerateSelection}
              disabled={isRegenerating || !selectionFeedback.trim()}
            >
              {isRegenerating ? (
                <>
                  <Spinner size="sm" />
                  Regenerating...
                </>
              ) : (
                <>
                  <ArrowPathIcon className="h-4 w-4" />
                  Regenerate
                </>
              )}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Layout>
  );
}

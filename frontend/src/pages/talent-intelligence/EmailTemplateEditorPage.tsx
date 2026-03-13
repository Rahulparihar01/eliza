/**
 * Email Template Editor Page
 * 
 * Full-page editor for creating and editing email templates.
 * Uses a three-column layout: header, main canvas, and variables sidebar.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeftIcon,
  PlusIcon,
  CheckIcon,
  SparklesIcon,
  BookOpenIcon,
  DocumentTextIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  TrashIcon,
  BookmarkIcon,
  ClipboardIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Design System Components
import {
  Page,
  Button,
  Spinner,
  Alert,
  Badge,
  Tooltip,
  Input,
  Textarea,
  Label,
  Checkbox,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalBody,
  ModalFooter,
  ToastContainer,
  useToast,
} from '../../components/ui';

// Types
interface TemplateSection {
  id?: number;
  order: number;
  section_type: 'static' | 'ai_generated';
  content?: string;
  ai_prompt?: string;
  ai_context_fields?: string[];
  ai_tone?: 'professional' | 'casual' | 'enthusiastic';
  ai_max_length?: number;
  section_name?: string;
}

interface LibrarySection {
  id: number;
  name: string;
  description?: string;
  category?: string;
  tags?: string[];
  section_type: 'static' | 'ai_generated';
  content?: string;
  ai_prompt?: string;
  ai_context_fields?: string[];
  ai_tone?: 'professional' | 'casual' | 'enthusiastic';
  ai_max_length?: number;
  use_count: number;
  is_shared: boolean;
}

interface EmailTemplate {
  id: number;
  name: string;
  description?: string;
  category: string;
  subject: string;
  subject_is_ai_generated: boolean;
  subject_ai_prompt?: string;
  is_default: boolean;
  sections: TemplateSection[];
}

// Constants
const TEMPLATE_CATEGORIES = [
  { value: 'applicant_followup', label: 'Applicant Outreach' },
  { value: 'previous_candidate', label: 'Previous Candidate Outreach' },
  { value: 'market_outreach', label: 'Market Candidate Outreach' },
  { value: 'interview_invite', label: 'Interview Invite' },
  { value: 'rejection', label: 'Rejection' },
  { value: 'custom', label: 'Custom' },
];

const AI_TONES = [
  { value: 'professional', label: 'Professional' },
  { value: 'casual', label: 'Casual' },
  { value: 'enthusiastic', label: 'Enthusiastic' },
];

const AVAILABLE_VARIABLES = [
  { name: 'candidate_name', description: 'Full name of the candidate' },
  { name: 'candidate_first_name', description: 'First name only' },
  { name: 'skills', description: 'Top 5 skills' },
  { name: 'skill', description: 'Top 3 skills' },
  { name: 'company_name', description: 'Your company (the hiring company)' },
  { name: 'candidate_company', description: "Candidate's current employer" },
  { name: 'job_title', description: "Candidate's current job title" },
  { name: 'location', description: "Candidate's location" },
  { name: 'years_experience', description: 'Years of experience' },
  { name: 'your_name', description: 'Your name (from settings)' },
  { name: 'your_title', description: 'Your title (from settings)' },
  { name: 'current_date', description: "Today's date" },
];

export default function EmailTemplateEditorPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isNew = !id || id === 'new';
  const { toasts, success: showSuccessToast } = useToast();

  // Loading states
  const [isLoading, setIsLoading] = useState(!isNew);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    category: 'custom',
    subject: '',
    subject_is_ai_generated: false,
    subject_ai_prompt: '',
    is_default: false,
    sections: [] as TemplateSection[],
  });

  // Section Library
  const [showLibraryModal, setShowLibraryModal] = useState(false);
  const [librarySections, setLibrarySections] = useState<LibrarySection[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [librarySearch, setLibrarySearch] = useState('');
  const [libraryFilter, setLibraryFilter] = useState('');
  const [libraryCategories, setLibraryCategories] = useState<{ value: string; label: string }[]>([]);

  // Preview
  const [showPreview, setShowPreview] = useState(false);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [previewContent, setPreviewContent] = useState<{ subject: string; body: string } | null>(null);

  // Save to Library modal
  const [showSaveToLibrary, setShowSaveToLibrary] = useState<number | null>(null);
  const [saveToLibraryData, setSaveToLibraryData] = useState({
    name: '',
    description: '',
    category: '',
    is_shared: true,
  });

  // Unsaved changes tracking
  const [isDirty, setIsDirty] = useState(false);
  const [showUnsavedModal, setShowUnsavedModal] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const initialFormRef = useRef<string>('');

  // Resizable preview panel
  const [previewWidth, setPreviewWidth] = useState(400);
  const [isResizing, setIsResizing] = useState(false);
  const minPreviewWidth = 300;
  const maxPreviewWidth = 600;

  // Track form changes for dirty state
  useEffect(() => {
    const currentForm = JSON.stringify(formData);
    if (initialFormRef.current && currentForm !== initialFormRef.current) {
      setIsDirty(true);
    }
  }, [formData]);

  // Warn on browser close/refresh
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // Intercept all navigation clicks when dirty
  useEffect(() => {
    const handleGlobalClick = (e: MouseEvent) => {
      if (!isDirty) return;

      // Find if the click was on a link or inside a link
      const target = e.target as HTMLElement;
      const link = target.closest('a[href]') as HTMLAnchorElement | null;
      
      if (!link) return;

      const href = link.getAttribute('href');
      if (!href) return;

      // Only intercept internal navigation (same origin, not external links)
      const isInternalLink = href.startsWith('/') || href.startsWith(window.location.origin);
      
      // Don't intercept if it's the current page
      const isSamePage = href === window.location.pathname || 
        href === window.location.origin + window.location.pathname;
      
      if (isInternalLink && !isSamePage) {
        e.preventDefault();
        e.stopPropagation();
        setPendingNavigation(href.replace(window.location.origin, ''));
        setShowUnsavedModal(true);
      }
    };

    // Use capture phase to intercept before React Router handles it
    document.addEventListener('click', handleGlobalClick, true);
    return () => document.removeEventListener('click', handleGlobalClick, true);
  }, [isDirty]);

  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const newWidth = window.innerWidth - e.clientX;
      setPreviewWidth(Math.min(maxPreviewWidth, Math.max(minPreviewWidth, newWidth)));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  // Load template if editing, or set initial form ref for new
  useEffect(() => {
    if (!isNew && id) {
      loadTemplate(parseInt(id));
    } else {
      // For new templates, set initial form reference
      initialFormRef.current = JSON.stringify(formData);
    }
  }, [id, isNew]);

  const loadTemplate = async (templateId: number) => {
    try {
      setIsLoading(true);
      const response = await AXIOS_INSTANCE.get(`/api/v1/email-templates/${templateId}`);
      const template = response.data;
      const loadedFormData = {
        name: template.name || '',
        description: template.description || '',
        category: template.category || 'custom',
        subject: template.subject || '',
        subject_is_ai_generated: template.subject_is_ai_generated || false,
        subject_ai_prompt: template.subject_ai_prompt || '',
        is_default: template.is_default || false,
        sections: template.sections || [],
      };
      setFormData(loadedFormData);
      // Store initial form state for dirty tracking
      initialFormRef.current = JSON.stringify(loadedFormData);
    } catch (err: any) {
      console.error('Failed to load template:', err);
      setError(err?.response?.data?.detail || 'Failed to load template');
    } finally {
      setIsLoading(false);
    }
  };

  const loadLibrarySections = async (search = '', category = '') => {
    try {
      setLibraryLoading(true);
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (category) params.append('category', category);

      const [sectionsRes, categoriesRes] = await Promise.all([
        AXIOS_INSTANCE.get(`/api/v1/email-templates/library?${params.toString()}`),
        libraryCategories.length === 0
          ? AXIOS_INSTANCE.get('/api/v1/email-templates/library/categories')
          : Promise.resolve({ data: libraryCategories }),
      ]);

      setLibrarySections(sectionsRes.data.sections || []);
      if (Array.isArray(categoriesRes.data)) {
        setLibraryCategories(categoriesRes.data);
      }
    } catch (err) {
      console.error('Failed to load library sections:', err);
    } finally {
      setLibraryLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setError(null);

      if (isNew) {
        await AXIOS_INSTANCE.post('/api/v1/email-templates', formData);
      } else {
        await AXIOS_INSTANCE.put(`/api/v1/email-templates/${id}`, formData);
      }

      // Reset dirty state and navigate
      setIsDirty(false);
      initialFormRef.current = JSON.stringify(formData);
      navigate('/talent/email-templates');
    } catch (err: any) {
      console.error('Failed to save template:', err);
      setError(err?.response?.data?.detail || 'Failed to save template');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    if (isDirty) {
      setPendingNavigation('/talent/email-templates');
      setShowUnsavedModal(true);
    } else {
      navigate('/talent/email-templates');
    }
  };

  const handleDiscardChanges = () => {
    setIsDirty(false);
    setShowUnsavedModal(false);
    if (pendingNavigation) {
      navigate(pendingNavigation);
    }
    setPendingNavigation(null);
  };

  const handleSaveAndNavigate = async () => {
    await handleSave();
    setShowUnsavedModal(false);
    setPendingNavigation(null);
  };

  const handleCancelNavigation = () => {
    setShowUnsavedModal(false);
    setPendingNavigation(null);
  };

  // Section management
  const addSection = (type: 'static' | 'ai_generated') => {
    const newSection: TemplateSection = {
      order: formData.sections.length,
      section_type: type,
      content: type === 'static' ? '' : undefined,
      ai_prompt: type === 'ai_generated' ? '' : undefined,
      ai_tone: type === 'ai_generated' ? 'professional' : undefined,
      ai_max_length: type === 'ai_generated' ? 150 : undefined,
    };
    setFormData((prev) => ({
      ...prev,
      sections: [...prev.sections, newSection],
    }));
  };

  const updateSection = (index: number, updates: Partial<TemplateSection>) => {
    setFormData((prev) => ({
      ...prev,
      sections: prev.sections.map((s, i) => (i === index ? { ...s, ...updates } : s)),
    }));
  };

  const removeSection = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      sections: prev.sections.filter((_, i) => i !== index).map((s, i) => ({ ...s, order: i })),
    }));
  };

  const moveSection = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= formData.sections.length) return;

    const newSections = [...formData.sections];
    [newSections[index], newSections[newIndex]] = [newSections[newIndex], newSections[index]];
    setFormData((prev) => ({
      ...prev,
      sections: newSections.map((s, i) => ({ ...s, order: i })),
    }));
  };

  const addSectionFromLibrary = (librarySection: LibrarySection) => {
    const newSection: TemplateSection = {
      order: formData.sections.length,
      section_type: librarySection.section_type,
      content: librarySection.content,
      ai_prompt: librarySection.ai_prompt,
      ai_context_fields: librarySection.ai_context_fields,
      ai_tone: librarySection.ai_tone,
      ai_max_length: librarySection.ai_max_length,
      section_name: librarySection.name,
    };
    setFormData((prev) => ({
      ...prev,
      sections: [...prev.sections, newSection],
    }));

    // Track usage
    AXIOS_INSTANCE.post(`/api/v1/email-templates/library/${librarySection.id}/use`).catch(() => {});

    // Close modal and show toast
    setShowLibraryModal(false);
    showSuccessToast(`Added "${librarySection.name}" section`);
  };

  const saveToLibrary = async (sectionIndex: number) => {
    const section = formData.sections[sectionIndex];
    if (!section || !saveToLibraryData.name) return;

    try {
      await AXIOS_INSTANCE.post('/api/v1/email-templates/library', {
        name: saveToLibraryData.name,
        description: saveToLibraryData.description,
        category: saveToLibraryData.category || undefined,
        section_type: section.section_type,
        content: section.content,
        ai_prompt: section.ai_prompt,
        ai_context_fields: section.ai_context_fields,
        ai_tone: section.ai_tone,
        ai_max_length: section.ai_max_length,
        is_shared: saveToLibraryData.is_shared,
      });

      setShowSaveToLibrary(null);
      setSaveToLibraryData({ name: '', description: '', category: '', is_shared: true });
    } catch (err: any) {
      console.error('Failed to save to library:', err);
      setError(err?.response?.data?.detail || 'Failed to save to library');
    }
  };

  const copyVariable = (varName: string) => {
    navigator.clipboard.writeText(`{{${varName}}}`);
    showSuccessToast('Copied to clipboard');
  };

  const generatePreview = async () => {
    // Need at least a subject and one section
    if (!formData.subject.trim() && !formData.subject_is_ai_generated) {
      setError('Add a subject line before generating preview');
      return;
    }
    if (formData.sections.length === 0) {
      setError('Add at least one section before generating preview');
      return;
    }

    try {
      setIsGeneratingPreview(true);
      setShowPreview(true);
      setError(null);
      
      // Sample candidate data for preview
      const sampleCandidateData = {
        candidate_name: 'Alex Johnson',
        candidate_first_name: 'Alex',
        skills: 'Python, TypeScript, React, AWS, Machine Learning',
        skill: 'Python, TypeScript, React',
        company_name: 'Your Company',
        candidate_company: 'TechCorp Inc.',
        job_title: 'Senior Software Engineer',
        location: 'San Francisco, CA',
        years_experience: '8',
        your_name: 'Recruiter Name',
        your_title: 'Talent Acquisition Specialist',
        current_date: new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }),
      };
      
      const response = await AXIOS_INSTANCE.post('/api/v1/email-templates/preview', {
        subject: formData.subject || '',
        subject_is_ai_generated: formData.subject_is_ai_generated,
        subject_ai_prompt: formData.subject_ai_prompt || '',
        sections: formData.sections.map((s, i) => ({ ...s, order: i })),
        candidate_data: sampleCandidateData,
      });
      setPreviewContent(response.data);
    } catch (err: any) {
      console.error('Failed to generate preview:', err);
      // Handle FastAPI validation errors (detail can be array of objects)
      const detail = err?.response?.data?.detail;
      let errorMessage = 'Failed to generate preview';
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        // Pydantic validation error format: [{type, loc, msg, input}]
        errorMessage = detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
      }
      setError(errorMessage);
      setPreviewContent(null);
    } finally {
      setIsGeneratingPreview(false);
    }
  };

  // Validation: name required, subject OR AI prompt required, at least one section
  const hasValidSubject = formData.subject_is_ai_generated 
    ? formData.subject_ai_prompt?.trim() 
    : formData.subject.trim();
  const isValid = formData.name.trim() && hasValidSubject && formData.sections.length > 0;

  if (isLoading) {
    return (
      <Page layout="full-width">
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" />
        </div>
      </Page>
    );
  }

  return (
    <Page layout="full-width" className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface shrink-0">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <Button variant="ghost" onClick={handleCancel} className="shrink-0">
            <ArrowLeftIcon className="w-4 h-4 mr-2" />
            Back to Templates
          </Button>
          <div className="h-6 w-px bg-gray-200 dark:bg-dark-border shrink-0" />
          <Input
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="Template Name"
            className="text-lg font-semibold flex-1 min-w-0 border-0 bg-transparent focus:ring-0 px-0"
          />
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!isValid || isSaving}>
            {isSaving ? (
              <Spinner size="sm" className="mr-2" />
            ) : (
              <CheckIcon className="w-4 h-4 mr-2" />
            )}
            {isNew ? 'Create Template' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" className="mx-6 mt-4">
          {error}
        </Alert>
      )}

      {/* Main Content */}
      <div className="flex flex-1 min-h-0">
        {/* Main Canvas */}
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-3xl mx-auto space-y-8">
            {/* Category & Description */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="category">Category</Label>
                <select
                  id="category"
                  value={formData.category}
                  onChange={(e) => setFormData((prev) => ({ ...prev, category: e.target.value }))}
                  className="w-full mt-1 px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-bg text-charcoal dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-eliza-red text-sm"
                >
                  {TEMPLATE_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Input
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of when to use this template"
                  className="mt-1"
                />
              </div>
            </div>

            {/* Subject Line */}
            <div className="border-t border-gray-200 dark:border-dark-border pt-8">
              <div className="flex items-center justify-between mb-2">
                <Label>Subject Line</Label>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="subject-ai"
                    checked={formData.subject_is_ai_generated}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, subject_is_ai_generated: e.target.checked }))
                    }
                  />
                  <Label htmlFor="subject-ai" className="flex items-center gap-1 cursor-pointer">
                    <SparklesIcon className="w-4 h-4 text-purple-500" />
                    AI Generated
                  </Label>
                </div>
              </div>
              {formData.subject_is_ai_generated ? (
                <Textarea
                  value={formData.subject_ai_prompt}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, subject_ai_prompt: e.target.value }))
                  }
                  placeholder="Describe what the AI should generate for the subject line..."
                  rows={2}
                  className="border-purple-200 dark:border-purple-800 focus:ring-purple-500"
                />
              ) : (
                <Input
                  value={formData.subject}
                  onChange={(e) => setFormData((prev) => ({ ...prev, subject: e.target.value }))}
                  placeholder="e.g., Exciting opportunity at {{company_name}}"
                />
              )}
            </div>

            {/* Email Body Sections */}
            <div className="border-t border-gray-200 dark:border-dark-border pt-8">
              <div className="flex items-center justify-between mb-4">
                <Label className="text-base">Email Body Sections</Label>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      loadLibrarySections();
                      setShowLibraryModal(true);
                    }}
                  >
                    <BookOpenIcon className="w-4 h-4 mr-1" />
                    From Library
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => addSection('static')}>
                    <PlusIcon className="w-4 h-4 mr-1" />
                    Static Section
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => addSection('ai_generated')}
                    className="text-purple-600 border-purple-300 hover:bg-purple-50 dark:text-purple-400 dark:border-purple-700 dark:hover:bg-purple-900/20"
                  >
                    <SparklesIcon className="w-4 h-4 mr-1" />
                    AI Section
                  </Button>
                </div>
              </div>

              {formData.sections.length === 0 ? (
                <div className="text-center py-12 border-2 border-dashed border-gray-200 dark:border-dark-border rounded-lg">
                  <BookOpenIcon className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                  <p className="text-gray-500 dark:text-gray-400 mb-2">No sections yet</p>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mb-4">
                    Add static content, AI-generated sections, or browse from your library
                  </p>
                  <Button
                    variant="outline"
                    onClick={() => {
                      loadLibrarySections();
                      setShowLibraryModal(true);
                    }}
                  >
                    <BookOpenIcon className="w-4 h-4 mr-2" />
                    Browse Section Library
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {formData.sections.map((section, index) => (
                    <div
                      key={index}
                      className={`p-4 rounded-lg border ${
                        section.section_type === 'ai_generated'
                          ? 'border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-900/10'
                          : 'border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          {section.section_type === 'ai_generated' ? (
                            <SparklesIcon className="w-4 h-4 text-purple-500" />
                          ) : (
                            <DocumentTextIcon className="w-4 h-4 text-gray-400" />
                          )}
                          <span className="font-medium text-sm text-charcoal dark:text-gray-100">
                            Section {index + 1}
                            {section.section_name && `: ${section.section_name}`}
                          </span>
                          <Badge variant={section.section_type === 'ai_generated' ? 'info' : 'default'}>
                            {section.section_type === 'ai_generated' ? 'AI' : 'Static'}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-1">
                          <Tooltip content="Save to Library">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setShowSaveToLibrary(index);
                                setSaveToLibraryData({
                                  name: section.section_name || '',
                                  description: '',
                                  category: '',
                                  is_shared: true,
                                });
                              }}
                            >
                              <BookmarkIcon className="w-4 h-4" />
                            </Button>
                          </Tooltip>
                          <Tooltip content="Move Up">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => moveSection(index, 'up')}
                              disabled={index === 0}
                            >
                              <ChevronUpIcon className="w-4 h-4" />
                            </Button>
                          </Tooltip>
                          <Tooltip content="Move Down">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => moveSection(index, 'down')}
                              disabled={index === formData.sections.length - 1}
                            >
                              <ChevronDownIcon className="w-4 h-4" />
                            </Button>
                          </Tooltip>
                          <Tooltip content="Remove">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeSection(index)}
                              className="hover:text-red-600 dark:hover:text-red-400"
                            >
                              <TrashIcon className="w-4 h-4" />
                            </Button>
                          </Tooltip>
                        </div>
                      </div>

                      {section.section_type === 'static' ? (
                        <Textarea
                          value={section.content || ''}
                          onChange={(e) => updateSection(index, { content: e.target.value })}
                          placeholder="Enter static content with {{variables}}..."
                          rows={4}
                        />
                      ) : (
                        <div className="space-y-3">
                          <Textarea
                            value={section.ai_prompt || ''}
                            onChange={(e) => updateSection(index, { ai_prompt: e.target.value })}
                            placeholder="Describe what the AI should generate..."
                            rows={3}
                            className="border-purple-200 dark:border-purple-800"
                          />
                          <div className="flex gap-4">
                            <div className="flex-1">
                              <Label className="text-xs">Tone</Label>
                              <select
                                value={section.ai_tone || 'professional'}
                                onChange={(e) =>
                                  updateSection(index, {
                                    ai_tone: e.target.value as TemplateSection['ai_tone'],
                                  })
                                }
                                className="w-full mt-1 px-2 py-1.5 border border-gray-200 dark:border-dark-border rounded-lg text-sm bg-white dark:bg-dark-bg"
                              >
                                {AI_TONES.map((tone) => (
                                  <option key={tone.value} value={tone.value}>
                                    {tone.label}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div className="w-32">
                              <Label className="text-xs">Max Words</Label>
                              <Input
                                type="number"
                                value={section.ai_max_length || 150}
                                onChange={(e) =>
                                  updateSection(index, { ai_max_length: parseInt(e.target.value) || 150 })
                                }
                                className="mt-1 text-sm"
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Available Variables - inline with sections */}
              <div className="mt-6 p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-lg border border-gray-200 dark:border-dark-border">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-charcoal dark:text-gray-100">
                    Available Variables
                  </h4>
                  <span className="text-xs text-gray-500 dark:text-gray-400">Click to copy</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {AVAILABLE_VARIABLES.map((v) => (
                    <Tooltip key={v.name} content={v.description}>
                      <Badge
                        variant="brand"
                        className="cursor-pointer hover:bg-eliza-red/30 transition-colors"
                        onClick={() => copyVariable(v.name)}
                      >
                        {`{{${v.name}}}`}
                      </Badge>
                    </Tooltip>
                  ))}
                </div>
              </div>
            </div>

            {/* Default Template Checkbox */}
            <div className="border-t border-gray-200 dark:border-dark-border pt-8 flex items-center gap-3">
              <Checkbox
                id="is-default"
                checked={formData.is_default}
                onChange={(e) => setFormData((prev) => ({ ...prev, is_default: e.target.checked }))}
              />
              <div>
                <Label htmlFor="is-default" className="font-medium cursor-pointer">
                  Set as default template
                </Label>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  This will be the default for "{TEMPLATE_CATEGORIES.find((c) => c.value === formData.category)?.label}" emails
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Resizable Divider */}
        <div
          className="w-1 bg-gray-200 dark:bg-dark-border hover:bg-eliza-red/50 cursor-col-resize shrink-0 transition-colors"
          onMouseDown={handleMouseDown}
          style={{ cursor: isResizing ? 'col-resize' : 'col-resize' }}
        />

        {/* Right Preview Panel */}
        <div
          className="border-l border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2 overflow-y-auto shrink-0 flex flex-col"
          style={{ width: previewWidth }}
        >
          <div className="p-4 border-b border-gray-200 dark:border-dark-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-charcoal dark:text-gray-100">Email Preview</h3>
            <Button
              variant="outline"
              size="sm"
              onClick={generatePreview}
              disabled={isGeneratingPreview}
            >
              {isGeneratingPreview ? (
                <>
                  <Spinner size="sm" className="mr-1" />
                  Generating...
                </>
              ) : previewContent ? (
                <>
                  <SparklesIcon className="w-4 h-4 mr-1" />
                  Regenerate
                </>
              ) : (
                <>
                  <SparklesIcon className="w-4 h-4 mr-1" />
                  Generate
                </>
              )}
            </Button>
          </div>

          <div className="flex-1 p-4 overflow-y-auto">
            {isGeneratingPreview ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <Spinner size="lg" />
                <span className="mt-3 text-sm text-gray-500">Generating preview...</span>
                <span className="mt-1 text-xs text-gray-400">AI sections may take a moment</span>
              </div>
            ) : previewContent ? (
              <div className="space-y-4">
                {/* Subject Preview */}
                <div className="p-4 bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase tracking-wide">
                    Subject
                  </div>
                  <div className="text-base font-semibold text-charcoal dark:text-gray-100">
                    {previewContent.subject}
                  </div>
                </div>

                {/* Body Preview */}
                <div className="p-4 bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border">
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
                    Body
                  </div>
                  <div
                    className="text-sm text-charcoal dark:text-gray-100 whitespace-pre-wrap leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: previewContent.body }}
                  />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <SparklesIcon className="w-12 h-12 text-gray-300 dark:text-gray-600 mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  Click "Generate" to preview your email
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  AI sections will be generated with sample candidate data
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Section Library Modal */}
      <Modal open={showLibraryModal} onClose={() => setShowLibraryModal(false)}>
        <ModalBackdrop />
        <ModalContent size="xl" className="max-h-[80vh] flex flex-col !max-w-4xl">
          <ModalHeader>
            <div className="flex items-center gap-2">
              <BookOpenIcon className="w-5 h-5 text-eliza-red" />
              <ModalTitle>Section Library</ModalTitle>
            </div>
            <ModalDescription>Click a section to add it to your template</ModalDescription>
          </ModalHeader>

          <ModalBody className="flex-1 overflow-hidden flex flex-col p-0">
            {/* Search and Filter */}
            <div className="p-4 border-b border-gray-200 dark:border-dark-border flex gap-3">
              <div className="flex-1 relative">
                <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  value={librarySearch}
                  onChange={(e) => {
                    setLibrarySearch(e.target.value);
                    loadLibrarySections(e.target.value, libraryFilter);
                  }}
                  placeholder="Search sections..."
                  className="pl-10"
                />
              </div>
              <select
                value={libraryFilter}
                onChange={(e) => {
                  setLibraryFilter(e.target.value);
                  loadLibrarySections(librarySearch, e.target.value);
                }}
                className="px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-bg text-sm"
              >
                <option value="">All Categories</option>
                {libraryCategories.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Section List */}
            <div className="flex-1 overflow-y-auto p-4">
              {libraryLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Spinner size="lg" />
                </div>
              ) : librarySections.length === 0 ? (
                <div className="text-center py-12">
                  <BookOpenIcon className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                  <p className="text-gray-500 dark:text-gray-400 mb-2">No sections in library</p>
                  <p className="text-xs text-gray-400">Save sections from your templates to reuse them</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {librarySections.map((section) => (
                    <div
                      key={section.id}
                      className="p-4 bg-white dark:bg-dark-surface rounded-lg border border-gray-200 dark:border-dark-border hover:border-eliza-red/30 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {section.section_type === 'ai_generated' ? (
                            <SparklesIcon className="w-4 h-4 text-purple-500" />
                          ) : (
                            <DocumentTextIcon className="w-4 h-4 text-gray-400" />
                          )}
                          <span className="font-medium text-charcoal dark:text-gray-100">
                            {section.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {section.category && (
                            <Badge variant="default">{section.category}</Badge>
                          )}
                          <span className="text-xs text-gray-500">Used {section.use_count}x</span>
                        </div>
                      </div>
                      {section.description && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                          {section.description}
                        </p>
                      )}
                      <p className="text-xs text-gray-400 line-clamp-2 mb-3">
                        {section.section_type === 'static'
                          ? section.content?.slice(0, 100) + '...'
                          : `AI Prompt: ${section.ai_prompt?.slice(0, 80)}...`}
                      </p>
                      <Button size="sm" onClick={() => addSectionFromLibrary(section)}>
                        <PlusIcon className="w-4 h-4 mr-1" />
                        Add to Template
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ModalBody>
        </ModalContent>
      </Modal>

      {/* Save to Library Modal */}
      <Modal
        open={showSaveToLibrary !== null}
        onClose={() => {
          setShowSaveToLibrary(null);
          setSaveToLibraryData({ name: '', description: '', category: '', is_shared: true });
        }}
      >
        <ModalBackdrop />
        <ModalContent size="sm">
          <ModalHeader>
            <div className="flex items-center gap-2">
              <BookmarkIcon className="w-5 h-5 text-eliza-red" />
              <ModalTitle>Save to Library</ModalTitle>
            </div>
          </ModalHeader>
          <ModalBody className="space-y-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Save this section to your library to reuse it in other templates.
            </p>

            <div>
              <Label htmlFor="lib-name">Section Name *</Label>
              <Input
                id="lib-name"
                value={saveToLibraryData.name}
                onChange={(e) =>
                  setSaveToLibraryData((prev) => ({ ...prev, name: e.target.value }))
                }
                placeholder="e.g., Personalized Skills Opener"
              />
            </div>

            <div>
              <Label htmlFor="lib-description">Description</Label>
              <Input
                id="lib-description"
                value={saveToLibraryData.description}
                onChange={(e) =>
                  setSaveToLibraryData((prev) => ({ ...prev, description: e.target.value }))
                }
                placeholder="When to use this section"
              />
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="lib-shared"
                checked={saveToLibraryData.is_shared}
                onChange={(e) =>
                  setSaveToLibraryData((prev) => ({ ...prev, is_shared: e.target.checked }))
                }
              />
              <Label htmlFor="lib-shared">Share with team members</Label>
            </div>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowSaveToLibrary(null);
                setSaveToLibraryData({ name: '', description: '', category: '', is_shared: true });
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => showSaveToLibrary !== null && saveToLibrary(showSaveToLibrary)}
              disabled={!saveToLibraryData.name}
            >
              <BookmarkIcon className="w-4 h-4 mr-2" />
              Save to Library
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Unsaved Changes Modal */}
      <Modal open={showUnsavedModal} onClose={handleCancelNavigation}>
        <ModalBackdrop />
        <ModalContent size="xl">
          <ModalHeader>
            <ModalTitle>Unsaved Changes</ModalTitle>
          </ModalHeader>
          <ModalBody>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              You have unsaved changes to this email template. What would you like to do?
            </p>
          </ModalBody>
          <ModalFooter className="flex justify-end gap-3">
            <Button variant="outline" onClick={handleCancelNavigation}>
              Keep Editing
            </Button>
            <Button
              variant="outline"
              onClick={handleDiscardChanges}
              className="text-red-600 border-red-300 hover:bg-red-50 dark:text-red-400 dark:border-red-700 dark:hover:bg-red-900/20"
            >
              Discard Changes
            </Button>
            <Button onClick={handleSaveAndNavigate} disabled={isSaving}>
              {isSaving ? <Spinner size="sm" className="mr-2" /> : <CheckIcon className="w-4 h-4 mr-2" />}
              Save & Leave
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} position="top-right" />
    </Page>
  );
}

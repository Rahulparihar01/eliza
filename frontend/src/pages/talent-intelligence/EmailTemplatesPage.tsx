/**
 * Email Templates Page
 * 
 * Manage email templates with section-based content.
 * Supports both static content with variable substitution
 * and AI-generated personalized sections.
 */

import React, { useState, useEffect } from 'react';
import {
  DocumentTextIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  SparklesIcon,
  DocumentDuplicateIcon,
  CheckIcon,
  XMarkIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  EyeIcon,
  StarIcon,
  BookOpenIcon,
  BookmarkIcon,
  MagnifyingGlassIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarSolidIcon } from '@heroicons/react/24/solid';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Design System Components
import {
  Page,
  PageHeader,
  PageBody,
  Button,
  Spinner,
  Alert,
  Badge,
  Tooltip,
  DropdownMenu,
  DropdownTrigger,
  DropdownContent,
  DropdownItem,
  DropdownLabel,
  DropdownSeparator,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  Input,
  Textarea,
  Label,
  Checkbox,
  Modal,
  ModalBackdrop,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  ToastContainer,
  useToast,
} from '../../components/ui';

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
  last_used_at?: string;
  is_shared: boolean;
  created_at: string;
}

interface LibraryCategory {
  value: string;
  label: string;
  description: string;
}

interface EmailTemplate {
  id: number;
  name: string;
  description?: string;
  category: string;
  subject: string;
  subject_is_ai_generated: boolean;
  subject_ai_prompt?: string;
  use_count: number;
  last_used_at?: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  sections: TemplateSection[];
  variables: string[];
}

const TEMPLATE_CATEGORIES = [
  { value: 'applicant_followup', label: 'Applicant Outreach', candidateType: 'applicant', description: 'Default template for applicants' },
  { value: 'previous_candidate', label: 'Previous Candidate Outreach', candidateType: 'previous_candidate', description: 'Default template for previous candidates' },
  { value: 'market_outreach', label: 'Market Candidate Outreach', candidateType: 'market', description: 'Default template for market-sourced candidates' },
  { value: 'interview_invite', label: 'Interview Invite', candidateType: null, description: 'Interview scheduling emails' },
  { value: 'rejection', label: 'Rejection', candidateType: null, description: 'Rejection notifications' },
  { value: 'custom', label: 'Custom', candidateType: null, description: 'General purpose templates' },
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
  { name: 'candidate_company', description: 'Candidate\'s current employer' },
  { name: 'job_title', description: 'Candidate\'s current job title' },
  { name: 'location', description: 'Candidate\'s location' },
  { name: 'years_experience', description: 'Years of experience' },
  { name: 'your_name', description: 'Your name (from settings)' },
  { name: 'your_title', description: 'Your title (from settings)' },
  { name: 'current_date', description: 'Today\'s date' },
];

// Candidate types for default assignment
const CANDIDATE_TYPES = [
  { value: 'applicant_followup', label: 'Applicants', category: 'applicant_followup' },
  { value: 'previous_candidate', label: 'Previous Candidates', category: 'previous_candidate' },
  { value: 'market_outreach', label: 'Market Candidates', category: 'market_outreach' },
];

export default function EmailTemplatesPage() {
  const { toasts, success: showSuccessToast } = useToast();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  
  // Set Default dropdown state
  const [showDefaultDropdown, setShowDefaultDropdown] = useState<number | null>(null);
  const [confirmDefaultChange, setConfirmDefaultChange] = useState<{
    templateId: number;
    templateName: string;
    candidateType: string;
    candidateTypeLabel: string;
    currentDefault: string | null;
  } | null>(null);
  
  // Live preview state
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [livePreview, setLivePreview] = useState<{ subject: string; body: string } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  
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
  
  // Section Library state
  const [showLibraryModal, setShowLibraryModal] = useState(false);
  const [libraryMode, setLibraryMode] = useState<'browse' | 'add'>('browse'); // 'browse' = view/edit mode, 'add' = add to template mode
  const [librarySections, setLibrarySections] = useState<LibrarySection[]>([]);
  const [libraryCategories, setLibraryCategories] = useState<LibraryCategory[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [librarySearch, setLibrarySearch] = useState('');
  const [libraryFilter, setLibraryFilter] = useState<string>('');
  const [editingLibrarySection, setEditingLibrarySection] = useState<LibrarySection | null>(null);
  const [showSaveToLibrary, setShowSaveToLibrary] = useState<number | null>(null);
  const [saveToLibraryData, setSaveToLibraryData] = useState({ name: '', description: '', category: '', is_shared: true });
  
  // Get current default template for a candidate type
  const getCurrentDefault = (category: string): string | null => {
    const defaultTemplate = templates.find(t => t.category === category && t.is_default);
    return defaultTemplate ? defaultTemplate.name : null;
  };
  
  // Handle setting a template as default
  const handleSetAsDefault = async (templateId: number, category: string) => {
    try {
      // Update template with new category and set as default
      await AXIOS_INSTANCE.put(`/api/v1/email-templates/${templateId}`, {
        category: category,
        is_default: true,
      });
      
      // Reload templates to get updated state
      await loadTemplates();
      setShowDefaultDropdown(null);
      setConfirmDefaultChange(null);
    } catch (err: any) {
      console.error('Failed to set default:', err);
      setError(err?.response?.data?.detail || 'Failed to set default template');
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);
  
  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('[data-default-dropdown]')) {
        setShowDefaultDropdown(null);
      }
    };
    if (showDefaultDropdown !== null) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showDefaultDropdown]);

  const loadTemplates = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await AXIOS_INSTANCE.get('/api/v1/email-templates');
      setTemplates(response.data.templates);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load templates');
    } finally {
      setIsLoading(false);
    }
  };

  // Load library sections
  const loadLibrarySections = async (search?: string, category?: string) => {
    setLibraryLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (category) params.append('category', category);
      
      const [sectionsRes, categoriesRes] = await Promise.all([
        AXIOS_INSTANCE.get(`/api/v1/email-templates/library?${params.toString()}`),
        libraryCategories.length === 0 
          ? AXIOS_INSTANCE.get('/api/v1/email-templates/library/categories')
          : Promise.resolve({ data: libraryCategories })
      ]);
      
      setLibrarySections(sectionsRes.data.sections);
      if (categoriesRes.data !== libraryCategories) {
        setLibraryCategories(categoriesRes.data);
      }
    } catch (err: any) {
      console.error('Failed to load library sections:', err);
    } finally {
      setLibraryLoading(false);
    }
  };

  // Add a section from the library to the template
  const addSectionFromLibrary = async (librarySection: LibrarySection) => {
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
    
    setFormData(prev => ({
      ...prev,
      sections: [...prev.sections, newSection],
    }));
    
    // Track usage
    try {
      await AXIOS_INSTANCE.post(`/api/v1/email-templates/library/${librarySection.id}/use`);
    } catch (err) {
      console.error('Failed to track section usage:', err);
    }
    
    setShowLibraryModal(false);
  };

  // Save a section to the library
  const saveToLibrary = async (sectionIndex: number) => {
    const section = formData.sections[sectionIndex];
    if (!saveToLibraryData.name) {
      return;
    }
    
    try {
      await AXIOS_INSTANCE.post('/api/v1/email-templates/library', {
        name: saveToLibraryData.name,
        description: saveToLibraryData.description,
        category: saveToLibraryData.category || null,
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
      // Reload library to include the new section
      loadLibrarySections();
    } catch (err: any) {
      console.error('Failed to save to library:', err);
      setError(err.response?.data?.detail || 'Failed to save section to library');
    }
  };

  // Update a library section
  const updateLibrarySection = async () => {
    if (!editingLibrarySection) return;
    
    try {
      await AXIOS_INSTANCE.put(`/api/v1/email-templates/library/${editingLibrarySection.id}`, {
        name: editingLibrarySection.name,
        description: editingLibrarySection.description,
        category: editingLibrarySection.category || null,
        section_type: editingLibrarySection.section_type,
        content: editingLibrarySection.content,
        ai_prompt: editingLibrarySection.ai_prompt,
        ai_context_fields: editingLibrarySection.ai_context_fields,
        ai_tone: editingLibrarySection.ai_tone,
        ai_max_length: editingLibrarySection.ai_max_length,
        is_shared: editingLibrarySection.is_shared,
      });
      
      setEditingLibrarySection(null);
      loadLibrarySections(librarySearch, libraryFilter);
    } catch (err: any) {
      console.error('Failed to update library section:', err);
      setError(err.response?.data?.detail || 'Failed to update section');
    }
  };

  // Delete a library section
  const deleteLibrarySection = async (sectionId: number) => {
    if (!window.confirm('Are you sure you want to delete this section from the library?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/email-templates/library/${sectionId}`);
      loadLibrarySections(librarySearch, libraryFilter);
    } catch (err: any) {
      console.error('Failed to delete library section:', err);
      setError(err.response?.data?.detail || 'Failed to delete section');
    }
  };

  const handleCreateTemplate = async () => {
    try {
      await AXIOS_INSTANCE.post('/api/v1/email-templates', formData);
      await loadTemplates();
      setIsCreating(false);
      resetForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create template');
    }
  };

  const handleUpdateTemplate = async () => {
    if (!selectedTemplate) return;
    try {
      await AXIOS_INSTANCE.put(`/api/v1/email-templates/${selectedTemplate.id}`, formData);
      await loadTemplates();
      setIsEditing(false);
      setSelectedTemplate(null);
      resetForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update template');
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this template?')) return;
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/email-templates/${id}`);
      await loadTemplates();
      if (selectedTemplate?.id === id) {
        setSelectedTemplate(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete template');
    }
  };

  const handleDuplicateTemplate = async (template: EmailTemplate) => {
    try {
      const duplicateData = {
        name: `${template.name} (Copy)`,
        description: template.description || '',
        category: template.category,
        subject: template.subject,
        subject_is_ai_generated: template.subject_is_ai_generated,
        subject_ai_prompt: template.subject_ai_prompt || '',
        is_default: false,
        sections: template.sections.map(s => ({
          order: s.order,
          section_type: s.section_type,
          section_name: s.section_name,
          content: s.content,
          ai_prompt: s.ai_prompt,
          ai_context_fields: s.ai_context_fields,
          ai_tone: s.ai_tone,
          ai_max_length: s.ai_max_length,
        })),
      };
      await AXIOS_INSTANCE.post('/api/v1/email-templates', duplicateData);
      // Reload the list to show the new copy
      await loadTemplates();
      showSuccessToast(`Duplicated "${template.name}"`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to duplicate template');
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      category: 'custom',
      subject: '',
      subject_is_ai_generated: false,
      subject_ai_prompt: '',
      is_default: false,
      sections: [],
    });
  };

  const startEditing = (template: EmailTemplate) => {
    setSelectedTemplate(template);
    setFormData({
      name: template.name,
      description: template.description || '',
      category: template.category,
      subject: template.subject,
      subject_is_ai_generated: template.subject_is_ai_generated,
      subject_ai_prompt: template.subject_ai_prompt || '',
      is_default: template.is_default,
      sections: template.sections.map(s => ({ ...s })),
    });
    setIsEditing(true);
  };

  const addSection = (type: 'static' | 'ai_generated') => {
    const newSection: TemplateSection = {
      order: formData.sections.length,
      section_type: type,
      content: type === 'static' ? '' : undefined,
      ai_prompt: type === 'ai_generated' ? '' : undefined,
      ai_tone: 'professional',
      ai_max_length: 200,
      section_name: `Section ${formData.sections.length + 1}`,
    };
    setFormData(prev => ({
      ...prev,
      sections: [...prev.sections, newSection],
    }));
  };

  const updateSection = (index: number, updates: Partial<TemplateSection>) => {
    setFormData(prev => ({
      ...prev,
      sections: prev.sections.map((s, i) => i === index ? { ...s, ...updates } : s),
    }));
  };

  const removeSection = (index: number) => {
    setFormData(prev => ({
      ...prev,
      sections: prev.sections.filter((_, i) => i !== index).map((s, i) => ({ ...s, order: i })),
    }));
  };

  const moveSection = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= formData.sections.length) return;
    
    const newSections = [...formData.sections];
    [newSections[index], newSections[newIndex]] = [newSections[newIndex], newSections[index]];
    newSections.forEach((s, i) => s.order = i);
    
    setFormData(prev => ({ ...prev, sections: newSections }));
  };

  // Sample data for preview rendering
  // Note: company_name = YOUR company (hiring company), candidate_company = candidate's employer
  const SAMPLE_CANDIDATE_DATA = {
    id: 'sample-preview',
    full_name: 'Sarah Johnson',
    name: 'Sarah Johnson',
    first_name: 'Sarah',
    email: 'sarah.johnson@example.com',
    skills: ['Python', 'Machine Learning', 'AWS', 'Data Engineering', 'TensorFlow'],
    job_company_name: 'TechCorp Inc.',  // Candidate's current employer
    current_company: 'TechCorp Inc.',
    job_title: 'Senior Data Scientist',
    current_title: 'Senior Data Scientist',
    location_name: 'San Francisco, CA',
    location: 'San Francisco, CA',
    inferred_years_experience: 8,
  };
  
  // For simple variable substitution in template view
  const SAMPLE_CANDIDATE_DISPLAY = {
    candidate_name: 'Sarah Johnson',
    candidate_first_name: 'Sarah',
    skills: 'Python, Machine Learning, AWS, Data Engineering, TensorFlow',
    skill: 'Python, Machine Learning, AWS',
    company_name: 'Caylent',  // YOUR company (the hiring company)
    candidate_company: 'TechCorp Inc.',  // Candidate's current employer
    current_company: 'TechCorp Inc.',  // Alias for candidate_company
    job_title: 'Senior Data Scientist',
    location: 'San Francisco, CA',
    years_experience: '8',
    your_name: 'Alex Thompson',
    your_title: 'Talent Acquisition Manager',
    current_date: new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
  };
  
  // Generate a live preview by calling the AI
  const generateLivePreview = async () => {
    // Check if we have any content to preview
    if (formData.sections.length === 0 && !formData.subject && !formData.subject_ai_prompt) {
      setPreviewError('Add a subject line and at least one section to preview');
      return;
    }
    
    setIsGeneratingPreview(true);
    setPreviewError(null);
    setLivePreview(null);
    
    try {
      // Use the new /preview endpoint that doesn't require a saved template
      const response = await AXIOS_INSTANCE.post('/api/v1/email-templates/preview', {
        subject: formData.subject,
        subject_is_ai_generated: formData.subject_is_ai_generated,
        subject_ai_prompt: formData.subject_ai_prompt,
        sections: formData.sections.map(s => ({
          order: s.order,
          section_type: s.section_type,
          content: s.content,
          ai_prompt: s.ai_prompt,
          ai_context_fields: s.ai_context_fields,
          ai_tone: s.ai_tone,
          ai_max_length: s.ai_max_length,
          section_name: s.section_name,
        })),
        candidate_data: SAMPLE_CANDIDATE_DATA,
      });
      
      setLivePreview({
        subject: response.data.subject,
        body: response.data.body,
      });
    } catch (err: any) {
      console.error('Failed to generate preview:', err);
      setPreviewError(err?.response?.data?.detail || 'Failed to generate preview. Please check your template configuration.');
    } finally {
      setIsGeneratingPreview(false);
    }
  };
  
  // Clear live preview when form changes
  const clearLivePreview = () => {
    setLivePreview(null);
    setPreviewError(null);
  };

  const renderPreview = (mode: 'template' | 'sample' = 'template') => {
    let previewBody = '';
    for (const section of formData.sections.sort((a, b) => a.order - b.order)) {
      if (section.section_type === 'static') {
        previewBody += (section.content || '') + '\n\n';
      } else {
        if (mode === 'sample') {
          // Show a placeholder for AI content in sample mode
          previewBody += `[AI will generate personalized content based on: "${section.ai_prompt?.slice(0, 50) || 'prompt'}..."]\n\n`;
        } else {
          previewBody += `[AI Generated: ${section.ai_prompt || 'No prompt set'}]\n\n`;
        }
      }
    }
    
    if (mode === 'sample') {
      // Replace variables with sample data
      Object.entries(SAMPLE_CANDIDATE_DISPLAY).forEach(([key, value]) => {
        const pattern = new RegExp(`\\{\\{${key}\\}\\}`, 'gi');
        previewBody = previewBody.replace(pattern, value);
      });
      return previewBody;
    }
    
    // Template mode: Highlight variables
    previewBody = previewBody.replace(/\{\{(\w+)\}\}/g, '<span class="bg-eliza-red/20 text-eliza-red px-1 rounded">{{$1}}</span>');
    
    return previewBody;
  };

  const renderSubjectPreview = (mode: 'template' | 'sample' = 'template') => {
    if (formData.subject_is_ai_generated) {
      return mode === 'sample' 
        ? '[AI will generate subject line]'
        : `[AI: ${formData.subject_ai_prompt || 'No prompt'}]`;
    }
    
    let subject = formData.subject || '(No subject)';
    
    if (mode === 'sample') {
      Object.entries(SAMPLE_CANDIDATE_DISPLAY).forEach(([key, value]) => {
        const pattern = new RegExp(`\\{\\{${key}\\}\\}`, 'gi');
        subject = subject.replace(pattern, value);
      });
      return subject;
    }
    
    // Template mode: Highlight variables
    return subject.replace(/\{\{(\w+)\}\}/g, '<span class="bg-eliza-red/20 text-eliza-red px-1 rounded">{{$1}}</span>');
  };

  if (isLoading) {
    return (
      <Page maxWidth="2xl">
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" />
        </div>
      </Page>
    );
  }

  return (
    <Page maxWidth="2xl">
      <PageHeader
        title="Email Templates"
        description="Create and manage email templates with static content or AI-generated personalization"
        bordered
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => {
                setLibraryMode('browse');
                loadLibrarySections();
                setShowLibraryModal(true);
              }}
            >
              <BookOpenIcon className="w-4 h-4 mr-2" />
              Section Library
            </Button>
            <Button onClick={() => window.location.href = '/talent/email-templates/new'}>
              <PlusIcon className="w-4 h-4 mr-2" />
              New Template
            </Button>
          </>
        }
      />

      <PageBody className="space-y-6">
        {error && (
          <Alert variant="error">
            <ExclamationTriangleIcon className="h-5 w-5" />
            <span>{error}</span>
          </Alert>
        )}

        {/* Template List */}
        <div className="grid gap-4">
          {templates.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500" />
              <h3 className="mt-4 text-sm font-medium text-charcoal dark:text-gray-100">
                No templates yet
              </h3>
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Create your first email template to get started
              </p>
              <Button
                className="mt-4"
                onClick={() => window.location.href = '/talent/email-templates/new'}
              >
                <PlusIcon className="h-4 w-4 mr-2" />
                Create Template
              </Button>
            </div>
          ) : (
            templates.map(template => (
              <div
                key={template.id}
                className="bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-lg p-6 hover:border-eliza-red/30 transition-colors cursor-pointer"
                onClick={() => window.location.href = `/talent/email-templates/${template.id}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-charcoal dark:text-gray-100">{template.name}</h3>
                      <Badge variant="default">
                        {TEMPLATE_CATEGORIES.find(c => c.value === template.category)?.label || template.category}
                      </Badge>
                      {template.is_default && (() => {
                        const cat = TEMPLATE_CATEGORIES.find(c => c.value === template.category);
                        return (
                          <Badge variant="brand">
                            Default{cat?.candidateType ? ` for ${cat.candidateType.replace('_', ' ')}s` : ''}
                          </Badge>
                        );
                      })()}
                      {template.sections.some(s => s.section_type === 'ai_generated') && (
                        <Badge variant="info" className="flex items-center gap-1">
                          <SparklesIcon className="w-3 h-3" />
                          AI
                        </Badge>
                      )}
                    </div>
                    {template.description && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">{template.description}</p>
                    )}
                    <div className="flex items-center gap-6 text-xs text-gray-500 dark:text-gray-400">
                      <span>{template.sections.length} section{template.sections.length !== 1 ? 's' : ''}</span>
                      <span>Used {template.use_count} time{template.use_count !== 1 ? 's' : ''}</span>
                      {template.variables.length > 0 && (
                        <span>Variables: {template.variables.slice(0, 3).join(', ')}{template.variables.length > 3 ? '...' : ''}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Tooltip content="Edit">
                      <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); window.location.href = `/talent/email-templates/${template.id}`; }}>
                        <PencilIcon className="w-4 h-4" />
                      </Button>
                    </Tooltip>
                    
                    {/* Set Default Dropdown */}
                    <div onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <Tooltip content="Set as default">
                          <DropdownTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={template.is_default ? 'text-eliza-red' : ''}
                            >
                              {template.is_default ? (
                                <StarSolidIcon className="w-4 h-4" />
                              ) : (
                                <StarIcon className="w-4 h-4" />
                              )}
                            </Button>
                          </DropdownTrigger>
                        </Tooltip>
                      <DropdownContent align="end" className="w-64">
                        <DropdownLabel>Set as Default For</DropdownLabel>
                        <DropdownSeparator />
                        {CANDIDATE_TYPES.map((type) => {
                          const currentDefault = getCurrentDefault(type.category);
                          const isCurrentDefault = template.category === type.category && template.is_default;
                          
                          return (
                            <DropdownItem
                              key={type.value}
                              onClick={() => {
                                if (currentDefault && currentDefault !== template.name) {
                                  setConfirmDefaultChange({
                                    templateId: template.id,
                                    templateName: template.name,
                                    candidateType: type.category,
                                    candidateTypeLabel: type.label,
                                    currentDefault: currentDefault,
                                  });
                                } else {
                                  handleSetAsDefault(template.id, type.category);
                                }
                              }}
                              className={isCurrentDefault ? 'bg-eliza-red/10' : ''}
                            >
                              <div className="flex-1">
                                <span className={isCurrentDefault ? 'text-eliza-red font-medium' : ''}>
                                  {type.label}
                                </span>
                                {currentDefault && (
                                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                    Current: {currentDefault}
                                  </div>
                                )}
                              </div>
                              {isCurrentDefault && (
                                <CheckIcon className="w-4 h-4 text-eliza-red" />
                              )}
                            </DropdownItem>
                          );
                        })}
                        </DropdownContent>
                      </DropdownMenu>
                    </div>
                    
                    <Tooltip content="Duplicate">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDuplicateTemplate(template);
                        }}
                      >
                        <DocumentDuplicateIcon className="w-4 h-4" />
                      </Button>
                    </Tooltip>
                    <Tooltip content="Delete">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleDeleteTemplate(template.id); }}
                        className="hover:text-red-600 dark:hover:text-red-400"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </Button>
                    </Tooltip>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </PageBody>
      
      {/* Confirmation Modal for Changing Default */}
      <Modal open={!!confirmDefaultChange} onClose={() => setConfirmDefaultChange(null)}>
        <ModalBackdrop />
        <ModalContent size="sm">
          <ModalHeader>
            <ModalTitle>Change Default Template</ModalTitle>
          </ModalHeader>
          <ModalBody>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
              <span className="text-charcoal dark:text-gray-100 font-medium">"{confirmDefaultChange?.currentDefault}"</span> is currently the default template for {confirmDefaultChange?.candidateTypeLabel?.toLowerCase()}.
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Do you want to replace it with <span className="text-charcoal dark:text-gray-100 font-medium">"{confirmDefaultChange?.templateName}"</span>?
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" onClick={() => setConfirmDefaultChange(null)}>
              Cancel
            </Button>
            <Button onClick={() => confirmDefaultChange && handleSetAsDefault(confirmDefaultChange.templateId, confirmDefaultChange.candidateType)}>
              Replace Default
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Section Library Modal */}
      <Modal 
        open={showLibraryModal} 
        onClose={() => {
          setShowLibraryModal(false);
          setEditingLibrarySection(null);
        }}
      >
        <ModalBackdrop />
        <ModalContent size="xl" className="max-h-[80vh] flex flex-col !max-w-4xl">
          <ModalHeader>
            <div className="flex items-center gap-2">
              <BookOpenIcon className="w-5 h-5 text-eliza-red" />
              <ModalTitle>
                Section Library
                {libraryMode === 'add' && <span className="text-sm font-normal text-gray-500 dark:text-gray-400 ml-2">- Click to add</span>}
              </ModalTitle>
            </div>
          </ModalHeader>
          
          <ModalBody className="flex-1 overflow-hidden flex flex-col p-0">
            {/* Search and Filter */}
            <div className="p-4 border-b border-gray-200 dark:border-dark-border flex gap-3">
              <div className="flex-1 relative">
                <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 dark:text-gray-400" />
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
                className="px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-bg text-charcoal dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-eliza-red text-sm"
              >
                <option value="">All Categories</option>
                {libraryCategories.map(cat => (
                  <option key={cat.value} value={cat.value}>{cat.label}</option>
                ))}
              </select>
            </div>

            {/* Edit Section Form */}
            {editingLibrarySection && (
              <div className="p-4 border-b border-gray-200 dark:border-dark-border bg-gray-50 dark:bg-dark-surface-2">
                <Label className="text-sm font-semibold mb-3 block">Edit Section</Label>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      value={editingLibrarySection.name}
                      onChange={(e) => setEditingLibrarySection({ ...editingLibrarySection, name: e.target.value })}
                      placeholder="Section name"
                    />
                    <select
                      value={editingLibrarySection.category || ''}
                      onChange={(e) => setEditingLibrarySection({ ...editingLibrarySection, category: e.target.value || undefined })}
                      className="px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-bg text-charcoal dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-eliza-red text-sm"
                    >
                      <option value="">No Category</option>
                      {libraryCategories.map(cat => (
                        <option key={cat.value} value={cat.value}>{cat.label}</option>
                      ))}
                    </select>
                  </div>
                  <Input
                    value={editingLibrarySection.description || ''}
                    onChange={(e) => setEditingLibrarySection({ ...editingLibrarySection, description: e.target.value })}
                    placeholder="Description (optional)"
                  />
                  {editingLibrarySection.section_type === 'static' ? (
                    <Textarea
                      value={editingLibrarySection.content || ''}
                      onChange={(e) => setEditingLibrarySection({ ...editingLibrarySection, content: e.target.value })}
                      placeholder="Section content"
                      rows={4}
                    />
                  ) : (
                    <Textarea
                      value={editingLibrarySection.ai_prompt || ''}
                      onChange={(e) => setEditingLibrarySection({ ...editingLibrarySection, ai_prompt: e.target.value })}
                      placeholder="AI prompt"
                      rows={4}
                    />
                  )}
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditingLibrarySection(null)}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={updateLibrarySection}>
                      Save Changes
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Section List */}
            <div className="flex-1 overflow-y-auto p-4">
              {libraryLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Spinner size="lg" />
                </div>
              ) : librarySections.length === 0 ? (
                <div className="text-center py-12">
                  <BookOpenIcon className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                  <p className="text-gray-500 dark:text-gray-400 mb-2">No sections in library yet</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Save sections from your templates to reuse them later</p>
                </div>
              ) : (
                <div className="grid gap-3">
                  {librarySections.map(section => (
                    <div
                      key={section.id}
                      className="p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-lg border border-gray-200 dark:border-dark-border hover:border-eliza-red/30 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {section.section_type === 'ai_generated' ? (
                            <SparklesIcon className="w-4 h-4 text-purple-500" />
                          ) : (
                            <DocumentTextIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                          )}
                          <span className="font-medium text-charcoal dark:text-gray-100">{section.name}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {section.category && (
                            <span className="px-2 py-0.5 text-xs bg-white dark:bg-dark-surface rounded-full text-gray-500 dark:text-gray-400">
                              {libraryCategories.find(c => c.value === section.category)?.label || section.category}
                            </span>
                          )}
                          <span className="text-xs text-gray-500 dark:text-gray-400">Used {section.use_count}x</span>
                        </div>
                      </div>
                      {section.description && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">{section.description}</p>
                      )}
                      <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-3">
                        {section.section_type === 'static' 
                          ? section.content?.slice(0, 150) + (section.content && section.content.length > 150 ? '...' : '')
                          : `AI Prompt: ${section.ai_prompt?.slice(0, 100)}${section.ai_prompt && section.ai_prompt.length > 100 ? '...' : ''}`
                        }
                      </div>
                      {section.tags && section.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-3">
                          {section.tags.map((tag, idx) => (
                            <span key={idx} className="px-1.5 py-0.5 text-[10px] bg-eliza-red/10 text-eliza-red rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      
                      {/* Action buttons */}
                      <div className="flex items-center gap-2 pt-2 border-t border-gray-200 dark:border-dark-border">
                        {libraryMode === 'add' ? (
                          <Button size="sm" onClick={() => addSectionFromLibrary(section)}>
                            <PlusIcon className="w-4 h-4 mr-1" />
                            Add to Template
                          </Button>
                        ) : (
                          <>
                            <Button size="sm" onClick={() => setEditingLibrarySection(section)}>
                              <PencilIcon className="w-4 h-4 mr-1" />
                              Edit
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              onClick={() => deleteLibrarySection(section.id)}
                              className="text-red-600 dark:text-red-400 border-red-300 dark:border-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                            >
                              <TrashIcon className="w-4 h-4 mr-1" />
                              Delete
                            </Button>
                          </>
                        )}
                        {section.is_shared && (
                          <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">Shared with team</span>
                        )}
                      </div>
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
              <Label htmlFor="section-name">Section Name *</Label>
              <Input
                id="section-name"
                value={saveToLibraryData.name}
                onChange={(e) => setSaveToLibraryData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., Personalized Skills Opener"
              />
            </div>
            
            <div>
              <Label htmlFor="section-description">Description</Label>
              <Input
                id="section-description"
                value={saveToLibraryData.description}
                onChange={(e) => setSaveToLibraryData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="When to use this section"
              />
            </div>
            
            <div>
              <Label htmlFor="section-category">Category</Label>
              <select
                id="section-category"
                value={saveToLibraryData.category}
                onChange={(e) => setSaveToLibraryData(prev => ({ ...prev, category: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-bg text-charcoal dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-eliza-red text-sm"
              >
                <option value="">Select a category</option>
                {libraryCategories.length > 0 ? (
                  libraryCategories.map(cat => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))
                ) : (
                  <>
                    <option value="opening">Opening / Greeting</option>
                    <option value="introduction">Introduction</option>
                    <option value="skills_match">Skills Match</option>
                    <option value="value_proposition">Value Proposition</option>
                    <option value="company_pitch">Company Pitch</option>
                    <option value="call_to_action">Call to Action</option>
                    <option value="closing">Closing</option>
                    <option value="custom">Custom</option>
                  </>
                )}
              </select>
            </div>
            
            <div className="flex items-center gap-2">
              <Checkbox
                id="share-with-team"
                checked={saveToLibraryData.is_shared}
                onChange={(e) => setSaveToLibraryData(prev => ({ ...prev, is_shared: e.target.checked }))}
              />
              <Label htmlFor="share-with-team">Share with team members</Label>
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

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} position="top-right" />
    </Page>
  );
}

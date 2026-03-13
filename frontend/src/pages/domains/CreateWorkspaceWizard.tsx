/**
 * CreateWorkspaceWizard - Multi-step wizard for creating workspaces
 * 
 * Step 1: Select workspace template
 * Step 2: Configure workspace details (name, description, etc.)
 * Step 3 (optional): Configure initial knowledge base for RAG templates
 */
import React, { useState, useEffect, useRef } from 'react';
import { XMarkIcon, ArrowLeftIcon, DocumentMagnifyingGlassIcon, ChartBarIcon, CheckCircleIcon, FolderIcon } from '@heroicons/react/24/outline';
import { cn } from '../../shared/lib/cn';
import { useToasts } from '../../stores/useToasts';
import { Button, Input, Spinner } from '../../components/ui';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

interface WorkspaceTemplate {
  id: number;
  name: string;
  display_name: string;
  description: string | null;
  icon: string;
  is_available: boolean;
}

interface CreateWorkspaceWizardProps {
  onClose: () => void;
  onCreated: () => void;
}

// Preset colors for quick selection
const PRESET_COLORS = [
  { value: '#8b5cf6', label: 'Violet' },
  { value: '#10b981', label: 'Emerald' },
  { value: '#3b82f6', label: 'Blue' },
  { value: '#f97316', label: 'Orange' },
  { value: '#ec4899', label: 'Pink' },
  { value: '#06b6d4', label: 'Cyan' },
  { value: '#ef4444', label: 'Red' },
  { value: '#eab308', label: 'Yellow' },
  { value: '#84cc16', label: 'Lime' },
  { value: '#6366f1', label: 'Indigo' },
];

// Parser types with user-friendly descriptions
const PARSER_TYPES = [
  { 
    value: 'naive', 
    label: 'Quick Text',
    userDescription: 'Best for simple text documents like Word files, plain PDFs, and text files.',
    techDescription: 'Fast plain text extraction without layout analysis',
    recommended: true,
  },
  { 
    value: 'deepdoc', 
    label: 'Standard Layouts',
    userDescription: 'Best for documents with tables, text and special formatting.',
    techDescription: 'Local OCR with layout recognition (DeepDoc)',
  },
  { 
    value: 'gpt-4o', 
    label: 'Complex & Scanned',
    userDescription: 'Highest accuracy for documents with images, tables, special formatting or scans.',
    techDescription: 'GPT-4o Vision for OCR and layout analysis',
  },
  { 
    value: 'custom-vlm', 
    label: 'Custom Model',
    userDescription: 'Use your own vision AI model for specialized document types.',
    techDescription: 'OpenAI-compatible VLM endpoint for OCR/layout',
    advanced: true,
  },
];

// Get template icon component
function getTemplateIcon(iconName: string) {
  switch (iconName) {
    case 'document-search':
      return DocumentMagnifyingGlassIcon;
    case 'chart-bar':
      return ChartBarIcon;
    default:
      return DocumentMagnifyingGlassIcon;
  }
}

export default function CreateWorkspaceWizard({ onClose, onCreated }: CreateWorkspaceWizardProps) {
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();

  // Wizard state
  const [step, setStep] = useState<'template' | 'details' | 'knowledge-base'>('template');
  const [templates, setTemplates] = useState<WorkspaceTemplate[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);
  
  // Form state
  const [selectedTemplate, setSelectedTemplate] = useState<WorkspaceTemplate | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('#8b5cf6'); // Default to violet hex
  const [showColorPicker, setShowColorPicker] = useState(false);
  
  // Knowledge base state (for RAG templates)
  const [kbName, setKbName] = useState('Default');
  const [kbDescription, setKbDescription] = useState('');
  const [parserType, setParserType] = useState('naive');
  const [customVlmModel, setCustomVlmModel] = useState('deepseek-ocr2@OpenAI-API-Compatible');
  const [kbSourceType, setKbSourceType] = useState<'elasticsearch' | 's3' | 'local_directory'>('s3');
  const [kbSourceValue, setKbSourceValue] = useState('');
  const [kbStorageBackend, setKbStorageBackend] = useState<'tenant_default' | 's3' | 'minio'>('tenant_default');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Ref for color picker click outside detection
  const colorPickerRef = useRef<HTMLDivElement>(null);
  
  // Close color picker on outside click
  useEffect(() => {
    if (!showColorPicker) return;
    
    const handleClickOutside = (e: MouseEvent) => {
      if (colorPickerRef.current && !colorPickerRef.current.contains(e.target as Node)) {
        setShowColorPicker(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showColorPicker]);

  // Load templates on mount
  useEffect(() => {
    async function loadTemplates() {
      try {
        const res = await fetch(`${API_BASE}/v1/workspace-templates?include_unavailable=true`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        
        if (res.ok) {
          const data = await res.json();
          setTemplates(data.templates);
        } else {
          addToast({ kind: 'error', message: 'Failed to load workspace templates' });
        }
      } catch (e) {
        addToast({ kind: 'error', message: 'Failed to load workspace templates' });
      } finally {
        setIsLoadingTemplates(false);
      }
    }
    
    loadTemplates();
  }, [token, addToast]);

  const handleTemplateSelect = (template: WorkspaceTemplate) => {
    if (!template.is_available) return;
    setSelectedTemplate(template);
    setStep('details');
  };

  const handleDetailsNext = () => {
    if (!name.trim()) return;
    
    // For RAG templates, show optional knowledge base config step
    if (selectedTemplate?.name === 'rag_retrieval') {
      setStep('knowledge-base');
    } else {
      handleSubmit();
    }
  };

  const handleSkipKnowledgeBase = () => {
    handleSubmit(true);
  };

  const handleSubmit = async (skipKb = false) => {
    if (!selectedTemplate || !name.trim()) return;

    setIsSubmitting(true);

    try {
      const payload: any = {
        template_id: selectedTemplate.id,
        name: name.trim().toLowerCase().replace(/\s+/g, '_'),
        display_name: name.trim(),
        description: description.trim() || undefined,
        icon: 'folder',
        color,
      };

      // Add initial knowledge base for RAG templates (unless user chose to skip)
      if (selectedTemplate.name === 'rag_retrieval' && !skipKb) {
        if (kbSourceType === 's3' && !kbSourceValue.trim()) {
          addToast({ kind: 'error', message: 'S3 bucket path is required for S3 knowledge bases' });
          setIsSubmitting(false);
          return;
        }
        const sourceConfig: Record<string, unknown> = {};
        if (kbSourceValue.trim()) {
          if (kbSourceType === 'elasticsearch') {
            sourceConfig.index_name = kbSourceValue.trim();
          } else if (kbSourceType === 's3') {
            sourceConfig.prefix = kbSourceValue.trim();
          } else {
            sourceConfig.path = kbSourceValue.trim();
          }
        }

        payload.initial_knowledge_base = {
          name: kbName.trim() || 'Default',
          description: kbDescription.trim() || undefined,
          parser_type: parserType,
          parser_config: parserType === 'custom-vlm' ? { custom_vlm_model: customVlmModel.trim() } : undefined,
          source_type: kbSourceType,
          source_config: Object.keys(sourceConfig).length ? sourceConfig : undefined,
          storage_backend: kbStorageBackend,
        };
      }

      const res = await fetch(`${API_BASE}/v1/workspaces`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        addToast({ kind: 'success', message: 'Workspace created successfully' });
        onCreated();
      } else {
        const error = await res.json();
        let errorMessage = 'Failed to create workspace';
        if (Array.isArray(error.detail)) {
          errorMessage = error.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof error.detail === 'string') {
          errorMessage = error.detail;
        }
        addToast({ kind: 'error', message: errorMessage });
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to create workspace' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const goBack = () => {
    if (step === 'details') {
      setStep('template');
    } else if (step === 'knowledge-base') {
      setStep('details');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-dark-surface rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border sticky top-0 bg-white dark:bg-dark-surface z-10">
          <div className="flex items-center gap-3">
            {step !== 'template' && (
              <Button
                variant="ghost"
                size="icon"
                onClick={goBack}
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Button>
            )}
            <h2 className="font-subtitle text-h3 text-charcoal dark:text-gray-100">
              {step === 'template' && 'Select Workspace Type'}
              {step === 'details' && 'Workspace Details'}
              {step === 'knowledge-base' && 'Knowledge Base Setup'}
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
          >
            <XMarkIcon className="w-5 h-5" />
          </Button>
        </div>

        {/* Step Indicator */}
        <div className="px-6 py-3 border-b border-gray-100 dark:border-dark-border/50">
          <div className="flex items-center gap-3 text-small">
            {/* Step 1 */}
            <div className="flex items-center gap-2">
              <span className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-micro font-medium transition-colors",
                step === 'template' 
                  ? "bg-eliza-red text-white" 
                  : "bg-gray-200 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400"
              )}>
                1
              </span>
              <span className={cn(
                "font-medium transition-colors",
                step === 'template' ? "text-charcoal dark:text-gray-100" : "text-gray-400 dark:text-gray-500"
              )}>
                Template
              </span>
            </div>
            
            <div className="w-8 h-px bg-gray-200 dark:bg-dark-border" />
            
            {/* Step 2 */}
            <div className="flex items-center gap-2">
              <span className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-micro font-medium transition-colors",
                step === 'details' 
                  ? "bg-eliza-red text-white" 
                  : step === 'knowledge-base'
                    ? "bg-gray-200 dark:bg-dark-surface-2 text-gray-500 dark:text-gray-400"
                    : "bg-gray-100 dark:bg-dark-surface text-gray-400 dark:text-gray-500"
              )}>
                2
              </span>
              <span className={cn(
                "font-medium transition-colors",
                step === 'details' ? "text-charcoal dark:text-gray-100" : "text-gray-400 dark:text-gray-500"
              )}>
                Details
              </span>
            </div>
            
            <div className="w-8 h-px bg-gray-200 dark:bg-dark-border" />
            
            {/* Step 3 - Always show, but styled based on whether it's applicable */}
            <div className={cn(
              "flex items-center gap-2 transition-opacity",
              // Dim step 3 if no template selected or template doesn't need KB step
              !selectedTemplate || selectedTemplate.name !== 'rag_retrieval' 
                ? "opacity-40" 
                : "opacity-100"
            )}>
              <span className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-micro font-medium transition-colors",
                step === 'knowledge-base' 
                  ? "bg-eliza-red text-white" 
                  : "bg-gray-100 dark:bg-dark-surface text-gray-400 dark:text-gray-500"
              )}>
                3
              </span>
              <span className={cn(
                "font-medium transition-colors",
                step === 'knowledge-base' ? "text-charcoal dark:text-gray-100" : "text-gray-400 dark:text-gray-500"
              )}>
                Knowledge Base <span className="text-micro font-normal">(optional)</span>
              </span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Step 1: Template Selection */}
          {step === 'template' && (
            <div className="space-y-4">
              {isLoadingTemplates ? (
                <div className="flex items-center justify-center py-12">
                  <Spinner size="lg" />
                </div>
              ) : (
                <div className="space-y-3">
                  {templates.map((template) => {
                    const IconComponent = getTemplateIcon(template.icon);
                    return (
                      <button
                        key={template.id}
                        onClick={() => handleTemplateSelect(template)}
                        disabled={!template.is_available}
                        className={cn(
                          "w-full text-left p-4 border rounded-lg transition-all",
                          template.is_available
                            ? "border-gray-200 dark:border-dark-border hover:border-eliza-red hover:bg-eliza-red/5 dark:hover:bg-eliza-red/10 cursor-pointer"
                            : "border-gray-100 dark:border-dark-border/50 bg-gray-50 dark:bg-dark-surface-2 opacity-60 cursor-not-allowed"
                        )}
                      >
                        <div className="flex items-start gap-4">
                          <div className={cn(
                            "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                            template.is_available
                              ? "bg-gray-100 dark:bg-dark-surface-2 text-gray-600 dark:text-gray-300"
                              : "bg-gray-100 dark:bg-dark-surface text-gray-400 dark:text-gray-500"
                          )}>
                            <IconComponent className="w-6 h-6" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <h3 className={cn(
                                "font-medium text-body",
                                template.is_available
                                  ? "text-charcoal dark:text-gray-100"
                                  : "text-gray-500 dark:text-gray-400"
                              )}>
                                {template.display_name}
                              </h3>
                              {!template.is_available && (
                                <span className="text-micro px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 rounded-full">
                                  Coming Soon
                                </span>
                              )}
                            </div>
                            <p className="text-small text-gray-500 dark:text-gray-400 mt-1">
                              {template.description}
                            </p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Step 2: Workspace Details */}
          {step === 'details' && (
            <div className="space-y-6">
              {/* Preview Card */}
              <div className="p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-xl border border-gray-200 dark:border-dark-border">
                <p className="text-micro text-gray-500 dark:text-gray-400 mb-3">Preview</p>
                <div className="flex items-center gap-3">
                  <div 
                    className="w-10 h-10 rounded-lg flex items-center justify-center text-white shadow-sm"
                    style={{ backgroundColor: color }}
                  >
                    <FolderIcon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-body text-charcoal dark:text-gray-100 truncate">
                      {name || 'Workspace Name'}
                    </h4>
                    <p className="text-micro text-gray-500 dark:text-gray-400 truncate">
                      {description || 'No description'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Name */}
              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  Workspace Name <span className="text-eliza-red">*</span>
                </label>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Company Policies"
                  autoFocus
                  required
                />
                <p className="mt-1.5 text-micro text-gray-500 dark:text-gray-400">
                  Choose a memorable name for your workspace
                </p>
              </div>

              {/* Description */}
              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  Description <span className="text-gray-400 text-micro font-normal">(optional)</span>
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What kind of documents will this workspace contain?"
                  rows={2}
                  className="w-full px-3 py-2.5 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface-2 text-charcoal dark:text-gray-100 text-small focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red resize-none placeholder:text-gray-400 dark:placeholder:text-gray-500"
                />
              </div>

              {/* Color */}
              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-2">
                  Workspace Color
                </label>
                <div className="space-y-3">
                  {/* Preset Colors */}
                  <div className="flex flex-wrap gap-2">
                    {PRESET_COLORS.map((c) => (
                      <button
                        key={c.value}
                        type="button"
                        onClick={() => setColor(c.value)}
                        className={cn(
                          "w-8 h-8 rounded-full transition-all shadow-sm",
                          color === c.value 
                            ? "ring-2 ring-offset-2 ring-charcoal dark:ring-white dark:ring-offset-dark-surface scale-110" 
                            : "hover:scale-110 hover:shadow-md"
                        )}
                        style={{ backgroundColor: c.value }}
                        title={c.label}
                      />
                    ))}
                    
                    {/* Custom color button */}
                    <div className="relative" ref={colorPickerRef}>
                      <button
                        type="button"
                        onClick={() => setShowColorPicker(!showColorPicker)}
                        className={cn(
                          "w-8 h-8 rounded-full border-2 border-dashed border-gray-300 dark:border-gray-600 transition-all flex items-center justify-center",
                          "hover:border-gray-400 dark:hover:border-gray-500 hover:scale-110",
                          !PRESET_COLORS.some(c => c.value === color) && "ring-2 ring-offset-2 ring-charcoal dark:ring-white dark:ring-offset-dark-surface"
                        )}
                        style={{ 
                          backgroundColor: !PRESET_COLORS.some(c => c.value === color) ? color : 'transparent'
                        }}
                        title="Pick custom color"
                      >
                        {PRESET_COLORS.some(c => c.value === color) && (
                          <span className="text-gray-400 text-lg">+</span>
                        )}
                      </button>
                      
                      {/* Color picker popover */}
                      {showColorPicker && (
                        <div className="absolute bottom-full right-0 mb-2 p-3 bg-white dark:bg-dark-surface rounded-lg shadow-lg border border-gray-200 dark:border-dark-border z-20">
                          <p className="text-micro text-gray-500 dark:text-gray-400 mb-2">Pick any color</p>
                          <input
                            type="color"
                            value={color}
                            onChange={(e) => setColor(e.target.value)}
                            className="w-28 h-28 cursor-pointer rounded-lg border-0 p-0 block"
                          />
                          <div className="mt-2 flex items-center gap-2">
                            <div 
                              className="w-5 h-5 rounded-full shadow-inner border border-gray-200 dark:border-dark-border flex-shrink-0"
                              style={{ backgroundColor: color }}
                            />
                            <input
                              type="text"
                              value={color}
                              onChange={(e) => {
                                if (/^#[0-9A-Fa-f]{0,6}$/.test(e.target.value)) {
                                  setColor(e.target.value);
                                }
                              }}
                              className="w-20 px-2 py-1 text-micro font-mono border border-gray-200 dark:border-dark-border rounded bg-white dark:bg-dark-surface-2 text-charcoal dark:text-gray-100"
                              placeholder="#8b5cf6"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={() => setShowColorPicker(false)}
                            className="w-full mt-2 px-3 py-1.5 text-micro font-medium text-charcoal dark:text-gray-100 bg-gray-100 dark:bg-dark-surface-2 hover:bg-gray-200 dark:hover:bg-dark-border rounded-md transition-colors"
                          >
                            Done
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* Preview */}
                  <div className="flex items-center gap-2 text-micro text-gray-500 dark:text-gray-400">
                    <div 
                      className="w-4 h-4 rounded-full shadow-sm"
                      style={{ backgroundColor: color }}
                    />
                    <span>Selected: {PRESET_COLORS.find(c => c.value === color)?.label || color}</span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100 dark:border-dark-border/50">
                <Button
                  variant="ghost"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                {selectedTemplate?.name === 'rag_retrieval' ? (
                  <>
                    <Button
                      variant="outline"
                      onClick={() => handleSubmit(true)}
                      disabled={!name.trim() || isSubmitting}
                    >
                      {isSubmitting && <Spinner size="sm" className="mr-2" />}
                      Create Workspace
                    </Button>
                    <Button
                      onClick={handleDetailsNext}
                      disabled={!name.trim() || isSubmitting}
                    >
                      Next: Add Knowledge Base
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={handleDetailsNext}
                    disabled={!name.trim() || isSubmitting}
                  >
                    {isSubmitting && <Spinner size="sm" className="mr-2" />}
                    Create Workspace
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Step 3: Knowledge Base Setup (RAG templates only) */}
          {step === 'knowledge-base' && (
            <div className="space-y-5">
              <div className="p-4 bg-eliza-red/5 dark:bg-eliza-red/10 rounded-lg border border-eliza-red/20 dark:border-eliza-red/30">
                <div className="flex items-start gap-3">
                  <CheckCircleIcon className="w-5 h-5 text-eliza-red flex-shrink-0 mt-0.5" />
                  <div className="text-small">
                    <p className="font-medium text-charcoal dark:text-gray-100">Add a knowledge base</p>
                    <p className="text-gray-500 dark:text-gray-400 mt-0.5">
                      This is optional — you can always add knowledge bases later from the workspace settings.
                    </p>
                  </div>
                </div>
              </div>

              {/* KB Name */}
              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  Knowledge Base Name
                </label>
                <Input
                  type="text"
                  value={kbName}
                  onChange={(e) => setKbName(e.target.value)}
                  placeholder="Default"
                />
              </div>

              {/* KB Description */}
              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  Description
                </label>
                <Input
                  type="text"
                  value={kbDescription}
                  onChange={(e) => setKbDescription(e.target.value)}
                  placeholder="Optional description"
                />
              </div>

              {/* Source + Storage */}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                    Source Type
                  </label>
                  <select
                    value={kbSourceType}
                    onChange={(e) => setKbSourceType(e.target.value as 'elasticsearch' | 's3' | 'local_directory')}
                    className="w-full px-3 py-2.5 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface-2 text-charcoal dark:text-gray-100 text-small focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red"
                  >
                    <option value="elasticsearch">Elasticsearch</option>
                    <option value="s3">S3</option>
                    <option value="local_directory">Local Directory (virtual)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                    Storage Backend
                  </label>
                  <select
                    value={kbStorageBackend}
                    onChange={(e) => setKbStorageBackend(e.target.value as 'tenant_default' | 's3' | 'minio')}
                    className="w-full px-3 py-2.5 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface-2 text-charcoal dark:text-gray-100 text-small focus:outline-none focus:ring-2 focus:ring-eliza-red/50 focus:border-eliza-red"
                  >
                    <option value="tenant_default">Tenant Default</option>
                    <option value="s3">S3</option>
                    <option value="minio">MinIO</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                  {kbSourceType === 'elasticsearch'
                    ? 'Elasticsearch Index (optional)'
                    : kbSourceType === 's3'
                      ? 'S3 Bucket Path (required)'
                      : 'Virtual Local Path (optional)'}
                </label>
                <Input
                  type="text"
                  value={kbSourceValue}
                  onChange={(e) => setKbSourceValue(e.target.value)}
                  placeholder={
                    kbSourceType === 'elasticsearch'
                      ? 'workspace_docs_index'
                      : kbSourceType === 's3'
                        ? 's3://tenant-documents/customers/acme/workspace-a/'
                        : '/imports/hr/'
                  }
                />
              </div>

              {/* Parser Type */}
              <div>
                <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1">
                  How should documents be read?
                </label>
                <p className="text-micro text-gray-500 dark:text-gray-400 mb-3">
                  Choose based on your document types. You can change this later.
                </p>
                <div className="space-y-2">
                  {PARSER_TYPES.map((p) => (
                    <label
                      key={p.value}
                      className={cn(
                        "flex items-start gap-3 p-4 border rounded-xl cursor-pointer transition-all",
                        parserType === p.value
                          ? "border-eliza-red bg-eliza-red/5 dark:bg-eliza-red/10 shadow-sm"
                          : "border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-surface-2 hover:border-gray-300 dark:hover:border-gray-600"
                      )}
                    >
                      <input
                        type="radio"
                        name="parser"
                        value={p.value}
                        checked={parserType === p.value}
                        onChange={(e) => setParserType(e.target.value)}
                        className="mt-1 accent-eliza-red w-4 h-4"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-body text-charcoal dark:text-gray-100">
                            {p.label}
                          </span>
                          {p.recommended && (
                            <span className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-full">
                              Recommended
                            </span>
                          )}
                          {p.advanced && (
                            <span className="px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded-full">
                              Advanced
                            </span>
                          )}
                        </div>
                        <p className="text-small text-gray-600 dark:text-gray-300 mt-1">
                          {p.userDescription}
                        </p>
                        <p className="text-micro text-gray-400 dark:text-gray-500 mt-0.5 font-mono">
                          {p.techDescription}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
                {parserType === 'custom-vlm' && (
                  <div className="mt-4 p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-lg border border-gray-200 dark:border-dark-border">
                    <label className="block text-small font-medium text-charcoal dark:text-gray-100 mb-1.5">
                      Custom Model ID
                    </label>
                    <Input
                      type="text"
                      value={customVlmModel}
                      onChange={(e) => setCustomVlmModel(e.target.value)}
                      placeholder="deepseek-ocr2@OpenAI-API-Compatible"
                    />
                    <p className="mt-2 text-micro text-gray-500 dark:text-gray-400">
                      Enter the model ID configured in your RAGFlow Model Providers settings.
                    </p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t border-gray-100 dark:border-dark-border/50">
                <Button
                  variant="ghost"
                  onClick={onClose}
                >
                  Cancel
                </Button>
                <Button
                  variant="outline"
                  onClick={handleSkipKnowledgeBase}
                  disabled={isSubmitting}
                >
                  Skip
                </Button>
                <Button
                  onClick={() => handleSubmit()}
                  disabled={
                    isSubmitting
                    || (parserType === 'custom-vlm' && !customVlmModel.trim())
                    || (kbSourceType === 's3' && !kbSourceValue.trim())
                  }
                >
                  {isSubmitting && <Spinner size="sm" className="mr-2" />}
                  Create with Knowledge Base
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

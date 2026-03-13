/**
 * CreateDomainModal - Create a new RAG domain
 * 
 * Simple modal form for creating knowledge domains.
 */
import React, { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { cn } from '../../shared/lib/cn';
import { useToasts } from '../../stores/useToasts';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';

const API_BASE = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');

interface CreateDomainModalProps {
  onClose: () => void;
  onCreated: () => void;
}

const COLORS = [
  { value: 'violet', label: 'Violet', class: 'bg-violet-500' },
  { value: 'emerald', label: 'Emerald', class: 'bg-emerald-500' },
  { value: 'blue', label: 'Blue', class: 'bg-blue-500' },
  { value: 'orange', label: 'Orange', class: 'bg-orange-500' },
  { value: 'pink', label: 'Pink', class: 'bg-pink-500' },
  { value: 'cyan', label: 'Cyan', class: 'bg-cyan-500' },
];

const PARSER_TYPES = [
  { value: 'naive', label: 'General', description: 'Fast, plain text extraction' },
  { value: 'deepdoc', label: 'DeepDoc', description: 'OCR and layout recognition (local)' },
  { value: 'gpt-4o', label: 'GPT-4o Vision', description: 'Best quality - uses GPT-4o for layout/OCR' },
  { value: 'custom-vlm', label: 'Custom VLM', description: 'Hosted VLM (OpenAI-compatible) for OCR/layout' },
];

export default function CreateDomainModal({ onClose, onCreated }: CreateDomainModalProps) {
  const token = localStorage.getItem('auth_token');
  const { push: addToast } = useToasts();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('violet');
  const [parserType, setParserType] = useState('naive');
  const [customVlmModel, setCustomVlmModel] = useState('deepseek-ocr2@OpenAI-API-Compatible');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);

    try {
      const res = await fetch(`${API_BASE}/v1/ragflow/domains`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: name.trim().toLowerCase().replace(/\s+/g, '_'),
          display_name: name.trim(),
          description: description.trim() || undefined,
          icon: 'folder',
          color,
          parser_type: parserType,
          custom_vlm_model:
            parserType === 'custom-vlm' ? customVlmModel.trim() || undefined : undefined,
        }),
      });

      if (res.ok) {
        addToast({ kind: 'success', message: 'Domain created successfully' });
        onCreated();
      } else {
        const error = await res.json();
        // Handle Pydantic validation errors (array of {type, loc, msg, input, ctx})
        let errorMessage = 'Failed to create domain';
        if (Array.isArray(error.detail)) {
          errorMessage = error.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof error.detail === 'string') {
          errorMessage = error.detail;
          // Provide helpful hints for common RAGFlow errors
          if (errorMessage.toLowerCase().includes('model') && errorMessage.toLowerCase().includes('authorized')) {
            errorMessage += '. Please configure the model in RAGFlow Model Providers first.';
          }
        }
        addToast({ kind: 'error', message: errorMessage });
      }
    } catch (e) {
      addToast({ kind: 'error', message: 'Failed to create domain' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-dark-surface rounded-xl shadow-xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-dark-border">
          <h2 className="text-lg font-semibold text-charcoal dark:text-white">
            Create Knowledge Domain
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-charcoal dark:text-white mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Company Policies"
              className="w-full px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface-2 text-charcoal dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-charcoal dark:text-white mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              rows={2}
              className="w-full px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface-2 text-charcoal dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
            />
          </div>

          {/* Color */}
          <div>
            <label className="block text-sm font-medium text-charcoal dark:text-white mb-2">
              Color
            </label>
            <div className="flex gap-2">
              {COLORS.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => setColor(c.value)}
                  className={cn(
                    "w-8 h-8 rounded-full transition-all",
                    c.class,
                    color === c.value ? "ring-2 ring-offset-2 ring-violet-500" : "hover:scale-110"
                  )}
                  title={c.label}
                />
              ))}
            </div>
          </div>

          {/* Parser Type */}
          <div>
            <label className="block text-sm font-medium text-charcoal dark:text-white mb-2">
              Parsing Method
            </label>
            <div className="space-y-2">
              {PARSER_TYPES.map((p) => (
                <label
                  key={p.value}
                  className={cn(
                    "flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors",
                    parserType === p.value
                      ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
                      : "border-gray-200 dark:border-dark-border hover:bg-gray-50 dark:hover:bg-dark-surface-2"
                  )}
                >
                  <input
                    type="radio"
                    name="parser"
                    value={p.value}
                    checked={parserType === p.value}
                    onChange={(e) => setParserType(e.target.value)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="font-medium text-sm text-charcoal dark:text-white">
                      {p.label}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {p.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
            {parserType === 'custom-vlm' && (
              <div className="mt-3">
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1">
                  VLM Model ID
                </label>
                <input
                  type="text"
                  value={customVlmModel}
                  onChange={(e) => setCustomVlmModel(e.target.value)}
                  placeholder="deepseek-ocr2@OpenAI-API-Compatible"
                  className="w-full px-3 py-2 border border-gray-200 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface-2 text-charcoal dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Must match a model configured in RAGFlow Model Providers (e.g., deepseek-ocr2@OpenAI-API-Compatible).
                  <br />
                  <strong>Note:</strong> Configure the model in RAGFlow first or domain creation will fail.
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-charcoal dark:hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                !name.trim() ||
                isSubmitting ||
                (parserType === 'custom-vlm' && !customVlmModel.trim())
              }
              className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
            >
              {isSubmitting && <LoadingSpinner size="xs" variant="white" />}
              Create Domain
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

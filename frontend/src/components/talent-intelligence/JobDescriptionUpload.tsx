/**
 * Job Description Upload Component
 * 
 * Allows users to upload or paste job descriptions for AI analysis
 */

import React, { useState } from 'react';
import {
  DocumentTextIcon,
  ArrowUpTrayIcon,
  SparklesIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline';

interface JobDescriptionUploadProps {
  onSubmit: (jobDescription: string, idealCandidateDescription: string) => void;
  onBack: () => void;
  initialJobDescription?: string;
  initialIdealCandidateDescription?: string;
  initialUploadedFile?: UploadedFile | null;
  onFileUpload?: (fileInfo: UploadedFile | null) => void;
}

interface UploadedFile {
  name: string;
  type: string;
  wordCount: number;
}

export function JobDescriptionUpload({ 
  onSubmit, 
  onBack,
  initialJobDescription = '',
  initialIdealCandidateDescription = '',
  initialUploadedFile = null,
  onFileUpload
}: JobDescriptionUploadProps) {
  const [jobDescription, setJobDescription] = useState(initialJobDescription);
  const [idealCandidateDescription, setIdealCandidateDescription] = useState(initialIdealCandidateDescription);
  const [mode, setMode] = useState<'paste' | 'upload' | 'url'>('paste');
  const [url, setUrl] = useState('');
  const [isLoadingUrl, setIsLoadingUrl] = useState(false);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(initialUploadedFile);
  const [showFullText, setShowFullText] = useState(false);

  const handleSubmit = () => {
    if (!jobDescription.trim() && !idealCandidateDescription.trim()) {
      alert('Please enter either a job description or ideal candidate description');
      return;
    }
    onSubmit(jobDescription, idealCandidateDescription);
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploadingFile(true);
    
    try {
      // Get auth token from localStorage
      const token = localStorage.getItem('auth_token');
      if (!token) {
        alert('You must be logged in to upload files');
        setIsUploadingFile(false);
        return;
      }

      // Create FormData and upload to backend
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/document-parsing/parse', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to parse document');
      }

      const data = await response.json();
      
      // Set the parsed text
      setJobDescription(data.text);
      const fileInfo = {
        name: data.filename,
        type: data.file_type,
        wordCount: data.word_count
      };
      setUploadedFile(fileInfo);
      setMode('paste'); // Switch to paste mode
      setShowFullText(false); // Start with collapsed view
      
      // Notify parent of file upload
      if (onFileUpload) {
        onFileUpload(fileInfo);
      }
      
    } catch (error: any) {
      alert(`Failed to parse file: ${error.message}`);
    } finally {
      setIsUploadingFile(false);
      // Reset file input
      event.target.value = '';
    }
  };

  const handleUrlFetch = async () => {
    if (!url.trim()) {
      alert('Please enter a URL');
      return;
    }

    setIsLoadingUrl(true);
    try {
      // Simple fetch - in production, you'd want a backend endpoint to handle this
      // to avoid CORS issues
      const response = await fetch(url);
      const text = await response.text();
      
      // Basic HTML stripping - in production, use a proper HTML-to-text library
      const stripped = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
      
      setJobDescription(stripped);
      setMode('paste'); // Switch to paste mode to show the text
    } catch (error) {
      alert('Failed to fetch URL. Please check the URL or try copy/pasting the content instead.');
    } finally {
      setIsLoadingUrl(false);
    }
  };

  const wordCount = jobDescription.trim().split(/\s+/).length;

  return (
    <div className="bg-surface rounded-lg border border-border overflow-hidden flex flex-col max-h-[calc(100vh-12rem)]">
      {/* Fixed Header */}
      <div className="flex-shrink-0 p-6 border-b border-border">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 hover:bg-surface-2 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5 text-muted" />
          </button>
          <div>
            <h2 className="text-xl font-semibold text-text">Upload Job Description</h2>
            <p className="text-muted-2 text-sm">
              Provide a job description AND optionally describe your ideal candidate for the best AI analysis
            </p>
          </div>
        </div>
      </div>
      
      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">

      {/* Mode Selector */}
      <div className="flex items-center gap-2 bg-surface-2 p-1 rounded-lg w-fit border border-border">
        <button
          onClick={() => setMode('paste')}
          className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
            mode === 'paste'
              ? 'bg-primary text-white shadow-sm'
              : 'text-text hover:text-primary hover:bg-surface-3'
          }`}
        >
          Paste Text
        </button>
        <button
          onClick={() => setMode('upload')}
          className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
            mode === 'upload'
              ? 'bg-primary text-white shadow-sm'
              : 'text-text hover:text-primary hover:bg-surface-3'
          }`}
        >
          Upload File
        </button>
        <button
          onClick={() => setMode('url')}
          className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
            mode === 'url'
              ? 'bg-primary text-white shadow-sm'
              : 'text-text hover:text-primary hover:bg-surface-3'
          }`}
        >
          Fetch from URL
        </button>
      </div>

      {/* Content */}
      {mode === 'url' ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Job Posting URL
            </label>
            <div className="flex gap-2">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://company.com/careers/senior-engineer"
                className="input flex-1"
                disabled={isLoadingUrl}
              />
              <button
                onClick={handleUrlFetch}
                disabled={isLoadingUrl || !url.trim()}
                className="btn-primary whitespace-nowrap"
              >
                {isLoadingUrl ? 'Loading...' : 'Fetch Job Description'}
              </button>
            </div>
            <p className="mt-2 text-xs text-muted-2">
              We'll extract the job description text from the URL. Some sites may not work due to CORS restrictions - in that case, please use copy/paste mode.
            </p>
          </div>

          {jobDescription && (
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Fetched Content (Edit if needed)
              </label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                className="w-full h-64 px-4 py-3 bg-surface border border-border rounded-lg text-text font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Ideal Candidate Description (Optional)
            </label>
            <textarea
              value={idealCandidateDescription}
              onChange={(e) => setIdealCandidateDescription(e.target.value)}
              placeholder="Describe your ideal candidate in natural language..."
              className="w-full h-32 px-4 py-3 bg-surface border border-border rounded-lg text-text font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
            />
          </div>
        </div>
      ) : mode === 'paste' ? (
        <div className="space-y-4">
          {/* Show uploaded file preview if file was uploaded */}
          {uploadedFile && !showFullText && (
            <div className="p-4 bg-surface-2 rounded-lg border border-border space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <DocumentTextIcon className="w-8 h-8 text-brand" />
                  <div>
                    <p className="font-semibold text-text">{uploadedFile.name}</p>
                    <p className="text-sm text-muted-2">
                      {uploadedFile.type.toUpperCase()} • {uploadedFile.wordCount} words
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowFullText(true)}
                    className="px-3 py-1.5 text-sm text-brand hover:bg-brand/10 rounded transition-colors"
                  >
                    View Full Text
                  </button>
                  <button
                    onClick={() => {
                      setUploadedFile(null);
                      setJobDescription('');
                      setMode('upload');
                      
                      // Notify parent of file removal
                      if (onFileUpload) {
                        onFileUpload(null);
                      }
                    }}
                    className="px-3 py-1.5 text-sm text-muted-2 hover:text-text hover:bg-surface-3 rounded transition-colors"
                  >
                    Remove
                  </button>
                </div>
              </div>
              
              {/* Preview */}
              <div className="p-3 bg-surface rounded border border-border">
                <p className="text-sm text-muted font-mono line-clamp-3">
                  {jobDescription.substring(0, 200)}...
                </p>
              </div>
            </div>
          )}

          {/* Show full textarea if: no file uploaded, or user clicked "View Full Text" */}
          {(!uploadedFile || showFullText) && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-foreground">
                  Job Description *
                </label>
                {uploadedFile && showFullText && (
                  <button
                    onClick={() => setShowFullText(false)}
                    className="text-sm text-brand hover:underline"
                  >
                    ← Back to Preview
                  </button>
                )}
              </div>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the complete job description here...

Example:
We're looking for a Senior Software Engineer to join our backend team...

Requirements:
- 5+ years of Python experience
- Strong knowledge of AWS and microservices
- Experience with PostgreSQL and Redis
..."
                className="w-full h-96 px-4 py-3 bg-surface border border-border rounded-lg text-text font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
                required
              />
              <div className="mt-2 flex items-center justify-between text-xs text-muted-2">
                <span>{wordCount} words</span>
                <span>Minimum 50 words recommended</span>
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Ideal Candidate Description (Optional)
            </label>
            <textarea
              value={idealCandidateDescription}
              onChange={(e) => setIdealCandidateDescription(e.target.value)}
              placeholder="Describe your ideal candidate in natural language...

Example:
We're looking for someone with 5+ years of Python experience who has worked at high-growth startups. They should have strong AWS knowledge, especially with Lambda and DynamoDB. Experience leading small teams is a plus. They should be comfortable working in a fast-paced environment and have excellent communication skills. Previous work at companies like Stripe, Shopify, or similar would be ideal."
              className="w-full h-48 px-4 py-3 bg-surface border border-border rounded-lg text-text font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all placeholder:text-muted-2"
            />
            <div className="mt-2 flex items-center justify-between text-xs text-muted-2">
              <span>
                {idealCandidateDescription.trim().split(/\s+/).length} words
              </span>
              <span>Use this to add context beyond the job description</span>
            </div>
          </div>

        </div>
      ) : (
        <div className="space-y-4">
          <div className="border-2 border-dashed border-border rounded-lg p-12 text-center hover:border-primary transition-colors">
            <input
              type="file"
              id="file-upload"
              className="hidden"
              accept=".txt,.pdf"
              onChange={handleFileUpload}
              disabled={isUploadingFile}
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer flex flex-col items-center"
            >
              {isUploadingFile ? (
                <>
                  <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-brand mb-4"></div>
                  <p className="text-foreground font-medium mb-2">
                    Parsing document...
                  </p>
                  <p className="text-muted text-sm">
                    This may take a moment for PDF files
                  </p>
                </>
              ) : (
                <>
                  <DocumentTextIcon className="w-16 h-16 text-muted-2 mb-4" />
                  <p className="text-foreground font-medium mb-2">
                    Click to upload or drag and drop
                  </p>
                  <p className="text-muted text-sm">
                    Supports TXT and PDF files (Max 10MB)
                  </p>
                  <button
                    type="button"
                    className="mt-4 px-4 py-2 bg-brand text-on-brand rounded-lg hover:bg-brand-strong transition-colors flex items-center gap-2"
                    onClick={() => document.getElementById('file-upload')?.click()}
                    disabled={isUploadingFile}
                  >
                    <ArrowUpTrayIcon className="w-4 h-4" />
                    Choose File
                  </button>
                </>
              )}
            </label>
          </div>
        </div>
      )}

      </div>
      
      {/* Fixed Footer with Actions */}
      <div className="flex-shrink-0 p-6 border-t border-border bg-surface-2">
        <div className="flex items-center justify-between">
          <button 
            onClick={onBack} 
            className="px-4 py-2 text-muted-2 hover:text-text transition-colors font-medium"
          >
            ← Back
          </button>
          <button
            onClick={handleSubmit}
            disabled={
              (!jobDescription.trim() && !idealCandidateDescription.trim()) || 
              (!!jobDescription.trim() && wordCount < 20)
            }
            className={`
              flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium transition-all
              ${(!jobDescription.trim() && !idealCandidateDescription.trim()) || (!!jobDescription.trim() && wordCount < 20)
                ? 'bg-surface-3 text-muted-2 cursor-not-allowed'
                : 'bg-brand text-on-brand hover:bg-brand-strong shadow-sm hover:shadow-md'
              }
            `}
          >
            Confirm Job Description
          </button>
        </div>
      </div>
    </div>
  );
}


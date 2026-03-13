/*
 * Document Upload Modal Component
 * Supports both modal and inline panel variants for uploading documents
 */

import React, {
  useState,
  useRef,
  useImperativeHandle,
  forwardRef,
  Fragment,
  useCallback,
  useMemo,
} from 'react';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { Dialog, Transition } from '@headlessui/react';
import {
  CloudArrowUpIcon,
  DocumentTextIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  PencilIcon,
} from '@heroicons/react/24/outline';
import { queryKeys } from '../../lib/query-keys';
import { useToasts } from '../../stores/useToasts';
import { Tooltip } from '../common/Tooltip';
import CompanySelector from '../business-intelligence/CompanySelector';
import { AXIOS_INSTANCE } from '../../services/api-client';

interface UploadFile {
  id: string;
  file: File;
  displayFilename: string;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
  isDuplicate?: boolean;
  result?: any;
}

interface ProcessingOptions {
  dataSource: string;
  companyHrDataset: string | null;
  chunkingStrategy: 'semantic' | 'fixed' | 'hierarchical' | 'adaptive' | 'hybrid';
  chunkSize: number;
  chunkOverlap: number;
  qualityThreshold: number;
  enableQARAG: boolean;
}

const DEFAULT_PROCESSING_OPTIONS: ProcessingOptions = {
  dataSource: 'general',
  companyHrDataset: null,
  chunkingStrategy: 'semantic',
  chunkSize: 1024,
  chunkOverlap: 128,
  qualityThreshold: 0.85,
  enableQARAG: false,
};

interface DocumentUploadSurfaceProps {
  variant: 'modal' | 'panel';
  onClose: () => void;
  onUploadStart?: (uploadId: string) => void;
}

export interface DocumentUploadSurfaceHandle {
  requestClose: (options?: { force?: boolean }) => boolean;
  hasActiveUploads: () => boolean;
  reset: () => void;
}

const DocumentUploadSurface = forwardRef<DocumentUploadSurfaceHandle, DocumentUploadSurfaceProps>(
  ({ variant, onClose, onUploadStart }, ref) => {
    const [files, setFiles] = useState<UploadFile[]>([]);
    const [isDragOver, setIsDragOver] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [editingFileId, setEditingFileId] = useState<string | null>(null);
    const [editingFilename, setEditingFilename] = useState<string>('');
    const [processingOptions, setProcessingOptions] = useState<ProcessingOptions>(() => ({
      ...DEFAULT_PROCESSING_OPTIONS,
    }));

    const fileInputRef = useRef<HTMLInputElement>(null);
    const { push: addToast } = useToasts();
    const queryClient = useQueryClient();

    const resetState = useCallback(() => {
      setFiles([]);
      setShowAdvanced(false);
      setEditingFileId(null);
      setEditingFilename('');
      setIsDragOver(false);
      setProcessingOptions({ ...DEFAULT_PROCESSING_OPTIONS });
    }, []);

    const hasUploadingFiles = useMemo(
      () => files.some((f) => f.status === 'uploading'),
      [files]
    );

    const attemptClose = useCallback(
      (force = false) => {
        if (!force && hasUploadingFiles) {
          addToast({
            message: 'Please wait for uploads to complete before closing',
            kind: 'warning',
            duration: 3000,
          });
          return false;
        }

        resetState();
        onClose();
        return true;
      },
      [hasUploadingFiles, addToast, onClose, resetState]
    );

    useImperativeHandle(
      ref,
      () => ({
        requestClose: (options?: { force?: boolean }) => attemptClose(options?.force ?? false),
        hasActiveUploads: () => hasUploadingFiles,
        reset: resetState,
      }),
      [attemptClose, hasUploadingFiles, resetState]
    );

    const handleFileSelect = (selectedFiles: FileList | null) => {
      if (!selectedFiles || selectedFiles.length === 0) return;

      const validFiles: File[] = [];
      const maxFileSize = 50 * 1024 * 1024; // 50MB

      Array.from(selectedFiles).forEach((file) => {
        if (file.size > maxFileSize) {
          addToast({
            message: `${file.name} exceeds 50MB limit`,
            kind: 'error',
            duration: 5000,
          });
          return;
        }
        validFiles.push(file);
      });

      const uploadFiles: UploadFile[] = validFiles.map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file,
        displayFilename: file.name,
        status: 'pending',
        progress: 0,
      }));

      setFiles((prev) => [...prev, ...uploadFiles]);
    };

    const removeFile = (fileId: string) => {
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    };

    const startEditingFilename = (fileId: string, currentFilename: string) => {
      setEditingFileId(fileId);
      setEditingFilename(currentFilename);
    };

    const saveFilenameEdit = (fileId: string) => {
      const trimmedFilename = editingFilename.trim();

      if (!trimmedFilename) {
        addToast({
          message: 'Filename cannot be empty',
          kind: 'error',
          duration: 3000,
        });
        return;
      }

      const file = files.find((f) => f.id === fileId);
      if (!file) return;

      const originalExt = file.file.name.split('.').pop() || '';
      const newNameParts = trimmedFilename.split('.');
      let finalFilename = trimmedFilename;

      if (newNameParts.length === 1 || !newNameParts[newNameParts.length - 1]) {
        finalFilename = `${trimmedFilename}.${originalExt}`;
      }

      setFiles((prev) =>
        prev.map((f) =>
          f.id === fileId
            ? {
                ...f,
                displayFilename: finalFilename,
                status: 'pending',
                error: undefined,
              }
            : f
        )
      );

      setEditingFileId(null);
      setEditingFilename('');
    };

    const cancelFilenameEdit = () => {
      setEditingFileId(null);
      setEditingFilename('');
    };

    const uploadMutation = useMutation({
      mutationFn: async ({
        file,
        displayFilename,
        options,
        fileId,
      }: {
        file: File;
        displayFilename: string;
        options: ProcessingOptions;
        fileId: string;
      }) => {
        const renamedFile =
          displayFilename !== file.name
            ? new File([file], displayFilename, { type: file.type })
            : file;

        const progressInterval = setInterval(() => {
          setFiles((prev) =>
            prev.map((f) => {
              if (f.id === fileId && f.status === 'uploading' && f.progress < 85) {
                const increment = Math.floor(Math.random() * 12) + 3;
                return { ...f, progress: Math.min(f.progress + increment, 85) };
              }
              return f;
            })
          );
        }, Math.floor(Math.random() * 200) + 250);

        try {
          const formData = new FormData();
          formData.append('files', renamedFile);
          if (options.dataSource) formData.append('source_id', options.dataSource);
          if (options.companyHrDataset)
            formData.append('company_hr_dataset', options.companyHrDataset);
          formData.append('chunking_strategy', options.chunkingStrategy);
          formData.append('chunk_size', (options.chunkSize || 1024).toString());
          formData.append('chunk_overlap', (options.chunkOverlap || 128).toString());
          formData.append('similarity_threshold', (options.qualityThreshold || 0.85).toString());
          formData.append('enable_qa_rag', options.enableQARAG.toString());
          formData.append(
            'metadata',
            JSON.stringify({
              uploaded_at: new Date().toISOString(),
              frontend_version: '1.0.0',
              processing_options: options,
            })
          );

          const response = await AXIOS_INSTANCE.post('/v1/documents/upload', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });

          clearInterval(progressInterval);
          if (response.data?.upload_id && onUploadStart) {
            onUploadStart(response.data.upload_id);
          }

          return response.data;
        } catch (error) {
          clearInterval(progressInterval);
          throw error;
        }
      },
      onSuccess: (data, variables) => {
        const fileId = variables.fileId;
        if (fileId) {
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileId
                ? { ...f, status: 'completed', progress: 100, result: data }
                : f
            )
          );
        }

        addToast({
          message: `${variables.displayFilename} uploaded successfully!`,
          kind: 'success',
          duration: 5000,
        });

        queryClient.invalidateQueries({ queryKey: queryKeys.documents.all });
        queryClient.invalidateQueries({ queryKey: queryKeys.companyData.all });

        setFiles((current) => {
          const allCompleted = current.every(
            (f) => f.status === 'completed' || f.status === 'error'
          );
          if (allCompleted) {
            setTimeout(() => {
              attemptClose(true);
            }, 1500);
          }
          return current;
        });
      },
      onError: (error: any, variables) => {
        const fileId = variables.fileId;

        let errorMessage = 'Upload failed';
        let isDuplicate = false;

        if (error?.response?.status === 413) {
          errorMessage = 'File too large. Maximum file size is 50MB.';
        } else if (error?.response?.status === 422) {
          const detail = error?.response?.data?.detail || error?.message || 'Validation error';
          errorMessage = detail;
          isDuplicate = detail.toLowerCase().includes('already exists');
        } else if (error?.response?.data?.detail) {
          if (Array.isArray(error.response.data.detail)) {
            const validationErrors = error.response.data.detail.map((err: any) => {
              if (err.msg && err.loc) {
                const field = err.loc[err.loc.length - 1];
                return `${field}: ${err.msg}`;
              }
              return err.msg || 'Validation error';
            });
            errorMessage = validationErrors.join(', ');
          } else if (typeof error.response.data.detail === 'string') {
            errorMessage = error.response.data.detail;
            isDuplicate = errorMessage.toLowerCase().includes('already exists');
          }
        } else if (error?.message) {
          errorMessage = error.message;
          isDuplicate = errorMessage.toLowerCase().includes('already exists');
        }

        if (fileId) {
          setFiles((prev) =>
            prev.map((f) =>
              f.id === fileId
                ? { ...f, status: 'error', error: errorMessage, isDuplicate }
                : f
            )
          );
        }

        const duration = isDuplicate ? 15000 : 8000;
        const toastKind = isDuplicate ? 'warning' : 'error';

        if (isDuplicate) {
          errorMessage = `⚠️ Duplicate File: ${errorMessage}\n\n💡 To upload this file:\n1. Click the edit icon (✏️) next to the filename\n2. Rename the file to make it unique\n3. Click "Upload" to try again\n\nℹ️ Note: Even if you rename and upload, any exact duplicate sections of documentation will be automatically skipped to avoid redundancy.`;
        }

        addToast({
          message: errorMessage,
          kind: toastKind,
          duration,
        });
      },
    });

    const startUpload = async () => {
      const pendingFiles = files.filter((f) => f.status === 'pending');

      for (const uploadFile of pendingFiles) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === uploadFile.id
              ? { ...f, status: 'uploading', progress: 0 }
              : f
          )
        );

        try {
          await uploadMutation.mutateAsync({
            file: uploadFile.file,
            displayFilename: uploadFile.displayFilename,
            options: processingOptions,
            fileId: uploadFile.id,
          });
        } catch (error) {
          // handled in mutation
        }
      }
    };

    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(true);
    };

    const handleDragLeave = () => {
      setIsDragOver(false);
    };

    const handleDrop = (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFileSelect(e.dataTransfer.files);
    };

    const getFileExtension = (file: File) => {
      const parts = file.name.split('.');
      return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : 'FILE';
    };

    const formatFileSize = (bytes: number) => {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const allFilesCompleted = useMemo(
      () => files.length > 0 && files.every((f) => f.status === 'completed' || f.status === 'error'),
      [files]
    );

    const content = (
      <>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div>
            <h3 className="text-lg font-semibold text-text">Upload Documents</h3>
            <p className="text-sm text-muted mt-1">
              Upload and process your organization's documents
            </p>
          </div>
          <button
            onClick={() => attemptClose()}
            className="text-muted hover:text-text transition-colors"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <div className="px-4 py-3 max-h-[calc(100vh-200px)] overflow-y-auto">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
              isDragOver
                ? 'border-brand bg-brand-soft'
                : 'border-border hover:border-brand hover:bg-surface-2'
            }`}
          >
            <CloudArrowUpIcon className="w-10 h-10 text-brand mx-auto mb-3" />
            <p className="text-text font-medium mb-2">
              Drop files here or click to browse
            </p>
            <p className="text-sm text-muted mb-3">
              Supports PDF, Word, TXT, Markdown (Max 50MB per file)
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
              accept=".pdf,.doc,.docx,.txt,.md"
            />
            <span className="btn-primary px-5 py-2 rounded-lg inline-flex items-center justify-center">
              Select Files
            </span>
          </div>

          {files.length > 0 && (
            <div className="mt-6">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center text-sm text-brand hover:text-brand-hover transition-colors"
              >
                <Cog6ToothIcon className="w-4 h-4 mr-2" />
                {showAdvanced ? 'Hide' : 'Show'} Advanced Options
              </button>

              {showAdvanced && (
                <div className="mt-4 p-4 bg-surface-2 rounded-lg space-y-4">
                  <div className="mb-4">
                    <CompanySelector
                      value={processingOptions.companyHrDataset}
                      onChange={(companyId) =>
                        setProcessingOptions({ ...processingOptions, companyHrDataset: companyId })
                      }
                      showDefault={true}
                      className="mb-2"
                    />
                    <p className="text-xs text-muted mt-1">
                      Documents will be associated with this company's dataset
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-text mb-1">
                        Chunking Strategy
                      </label>
                      <select
                        value={processingOptions.chunkingStrategy}
                        onChange={(e) =>
                          setProcessingOptions({
                            ...processingOptions,
                            chunkingStrategy: e.target.value as ProcessingOptions['chunkingStrategy'],
                          })
                        }
                        className="w-full px-3 py-2 border border-border rounded-lg bg-surface text-text"
                      >
                        <option value="semantic">Semantic (Recommended)</option>
                        <option value="fixed">Fixed Size</option>
                        <option value="hierarchical">Hierarchical</option>
                        <option value="adaptive">Adaptive</option>
                        <option value="hybrid">Hybrid</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text mb-1">
                        Data Source
                      </label>
                      <input
                        type="text"
                        value={processingOptions.dataSource}
                        onChange={(e) =>
                          setProcessingOptions({
                            ...processingOptions,
                            dataSource: e.target.value,
                          })
                        }
                        className="w-full px-3 py-2 border border-border rounded-lg bg-surface text-text"
                        placeholder="general"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text mb-1">
                        Chunk Size
                      </label>
                      <input
                        type="number"
                        value={processingOptions.chunkSize}
                        onChange={(e) =>
                          setProcessingOptions({
                            ...processingOptions,
                            chunkSize: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full px-3 py-2 border border-border rounded-lg bg-surface text-text"
                        min="128"
                        max="4096"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-text mb-1">
                        Chunk Overlap
                      </label>
                      <input
                        type="number"
                        value={processingOptions.chunkOverlap}
                        onChange={(e) =>
                          setProcessingOptions({
                            ...processingOptions,
                            chunkOverlap: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full px-3 py-2 border border-border rounded-lg bg-surface text-text"
                        min="0"
                        max="512"
                      />
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="enableQARAG"
                      checked={processingOptions.enableQARAG}
                      onChange={(e) =>
                        setProcessingOptions({
                          ...processingOptions,
                          enableQARAG: e.target.checked,
                        })
                      }
                      className="w-4 h-4 text-brand border-border rounded"
                    />
                    <label htmlFor="enableQARAG" className="text-sm text-text">
                      Enable QA-RAG (Generate question-answer pairs)
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {files.length > 0 && (
            <div className="mt-6 space-y-3">
              <h4 className="text-sm font-medium text-text">Files ({files.length})</h4>
              {files.map((uploadFile) => (
                <div
                  key={uploadFile.id}
                  className="flex items-center space-x-4 p-4 border border-border rounded-lg"
                >
                  <DocumentTextIcon className="w-8 h-8 text-brand flex-shrink-0" />

                  <div className="flex-1 min-w-0">
                    {editingFileId === uploadFile.id ? (
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={editingFilename}
                          onChange={(e) => setEditingFilename(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveFilenameEdit(uploadFile.id);
                            if (e.key === 'Escape') cancelFilenameEdit();
                          }}
                          className="flex-1 px-2 py-1 border border-brand rounded text-sm text-text bg-surface"
                          autoFocus
                        />
                        <button
                          onClick={() => saveFilenameEdit(uploadFile.id)}
                          className="text-xs text-brand hover:text-brand-hover px-2 py-1"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelFilenameEdit}
                          className="text-xs text-muted hover:text-text px-2 py-1"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <p className="text-sm font-medium text-text truncate">
                          {uploadFile.displayFilename}
                        </p>
                        {uploadFile.displayFilename !== uploadFile.file.name && (
                          <span className="text-xs bg-brand-soft text-brand px-2 py-0.5 rounded">
                            renamed
                          </span>
                        )}
                        <span className="text-xs text-muted bg-surface-2 px-2 py-1 rounded">
                          {getFileExtension(uploadFile.file)}
                        </span>
                        {(uploadFile.status === 'pending' || uploadFile.status === 'error') && (
                          <button
                            onClick={() =>
                              startEditingFilename(uploadFile.id, uploadFile.displayFilename)
                            }
                            className="text-muted hover:text-brand transition-colors"
                            title="Rename file"
                          >
                            <PencilIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    )}
                    <div className="flex items-center space-x-4 text-xs text-muted mt-1">
                      <span>{formatFileSize(uploadFile.file.size)}</span>
                      {uploadFile.status === 'uploading' && (
                        <span>{uploadFile.progress}%</span>
                      )}
                    </div>
                    {uploadFile.error && (
                      <div
                        className={`mt-2 p-3 rounded-md border ${
                          uploadFile.isDuplicate
                            ? 'bg-ai-warning-soft border-ai-warning/30'
                            : 'bg-ai-danger-soft border-ai-danger/20'
                        }`}
                      >
                        <div className="flex items-start space-x-2">
                          {uploadFile.isDuplicate && (
                            <ExclamationTriangleIcon className="w-4 h-4 text-ai-warning flex-shrink-0 mt-0.5" />
                          )}
                          <p
                            className={`text-xs leading-relaxed whitespace-pre-line ${
                              uploadFile.isDuplicate ? 'text-ai-warning' : 'text-ai-danger'
                            }`}
                          >
                            {uploadFile.error}
                          </p>
                        </div>
                      </div>
                    )}
                    {uploadFile.status === 'uploading' && (
                      <div className="w-full bg-surface-2 rounded-full h-1.5 mt-2">
                        <div
                          className="bg-brand h-1.5 rounded-full transition-all w-var"
                          style={{ ['--w' as any]: `${uploadFile.progress}%` }}
                        />
                      </div>
                    )}
                  </div>

                  <div className="flex items-center space-x-2">
                    {uploadFile.status === 'completed' && (
                      <Tooltip content="Upload completed successfully" position="top">
                        <div>
                          <CheckCircleIcon className="w-5 h-5 text-ai-success" />
                        </div>
                      </Tooltip>
                    )}
                    {uploadFile.status === 'error' && (
                      <Tooltip
                        content={
                          uploadFile.isDuplicate
                            ? '⚠️ Duplicate file - click edit (✏️) to rename and retry'
                            : 'Upload failed - click edit (✏️) to rename and retry'
                        }
                        position="top"
                      >
                        <div>
                          <ExclamationTriangleIcon
                            className={`w-5 h-5 ${
                              uploadFile.isDuplicate ? 'text-ai-warning' : 'text-ai-danger'
                            }`}
                          />
                        </div>
                      </Tooltip>
                    )}
                    {uploadFile.status === 'pending' && (
                      <Tooltip content="Remove file from upload queue" position="top">
                        <button
                          onClick={() => removeFile(uploadFile.id)}
                          className="text-muted hover:text-ai-danger transition-colors"
                        >
                          <XMarkIcon className="w-5 h-5" />
                        </button>
                      </Tooltip>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-surface-2">
          <div className="text-sm text-muted">
            {files.length > 0 && (
              <span>{files.filter((f) => f.status === 'completed').length} of {files.length} completed</span>
            )}
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => attemptClose()}
              className="px-4 py-2 text-sm text-muted hover:text-text transition-colors"
            >
              {allFilesCompleted ? 'Close' : 'Cancel'}
            </button>
            {files.length > 0 && !allFilesCompleted && (
              <button
                onClick={startUpload}
                disabled={hasUploadingFiles || files.filter((f) => f.status === 'pending').length === 0}
                className="btn-primary px-6 py-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {hasUploadingFiles ? 'Uploading...' : 'Upload Files'}
              </button>
            )}
          </div>
        </div>
      </>
    );

    if (variant === 'panel') {
      return (
        <div className="rounded-2xl bg-surface border border-border shadow-xl overflow-hidden">
          {content}
        </div>
      );
    }

    return content;
  }
);

DocumentUploadSurface.displayName = 'DocumentUploadSurface';

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadStart?: (uploadId: string) => void;
}

export default function DocumentUploadModal({ isOpen, onClose, onUploadStart }: DocumentUploadModalProps) {
  const surfaceRef = useRef<DocumentUploadSurfaceHandle>(null);

  const handleDialogClose = () => {
    surfaceRef.current?.requestClose();
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleDialogClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-50" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-2xl bg-surface border border-border shadow-xl transition-all">
                <DocumentUploadSurface
                  ref={surfaceRef}
                  variant="modal"
                  onClose={onClose}
                  onUploadStart={onUploadStart}
                />
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

interface DocumentUploadPanelProps {
  onClose: () => void;
  onUploadStart?: (uploadId: string) => void;
}

export const DocumentUploadPanel = forwardRef<DocumentUploadSurfaceHandle, DocumentUploadPanelProps>(
  ({ onClose, onUploadStart }, ref) => (
    <DocumentUploadSurface
      ref={ref}
      variant="panel"
      onClose={onClose}
      onUploadStart={onUploadStart}
    />
  )
);

DocumentUploadPanel.displayName = 'DocumentUploadPanel';

import React, { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { CloudArrowUpIcon, XMarkIcon, PlayIcon } from '@heroicons/react/24/outline';
import { useDropzone } from 'react-dropzone';
import { useStartMlTalentAnalysisApiV1MlTalentAnalyzePost } from '../../generated/ml-talent-intelligence/ml-talent-intelligence';
import { useToasts } from '../../stores/useToasts';
import Button from '../../shared/ui/Button';
import Card from '../../shared/ui/Card';
import Textarea from '../../shared/ui/Textarea';

interface AnalysisInputProps {
  onAnalysisStarted: (analysisId: string) => void;
}

export const AnalysisInput: React.FC<AnalysisInputProps> = ({ onAnalysisStarted }) => {
  const [jobDescription, setJobDescription] = useState('');
  const [idealCandidate, setIdealCandidate] = useState('');
  const [resumes, setResumes] = useState<File[]>([]);
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();

  const { mutate: startAnalysis, isPending } = useStartMlTalentAnalysisApiV1MlTalentAnalyzePost({
    mutation: {
      onSuccess: (response) => {
        addToast({
          kind: 'success',
          message: 'Analysis started successfully! Processing...',
        });
        onAnalysisStarted(response.analysis_id);
        // Reset form
        setJobDescription('');
        setIdealCandidate('');
        setResumes([]);
      },
      onError: (err: any) => {
        addToast({
          kind: 'error',
          message: err?.response?.data?.detail || 'Failed to start analysis. Please try again.',
        });
      },
    },
  });

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setResumes((prev) => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    multiple: true,
    disabled: isPending,
  });

  const handleRemoveResume = (index: number) => {
    setResumes((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!jobDescription.trim()) {
      addToast({
        kind: 'error',
        message: 'Job description is required',
      });
      return;
    }
    if (!idealCandidate.trim()) {
      addToast({
        kind: 'error',
        message: 'Ideal candidate description is required',
      });
      return;
    }
    if (resumes.length === 0) {
      addToast({
        kind: 'error',
        message: 'Please upload at least one resume',
      });
      return;
    }

    startAnalysis({
      data: {
        job_description: jobDescription,
        ideal_candidate_description: idealCandidate,
        applicant_resumes: resumes,
      },
    });
  };

  return (
    <Card>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-text mb-1">Start New ML Talent Analysis</h2>
          <p className="text-sm text-muted">
            Provide the job description, ideal candidate profile, and applicant resumes to begin analysis.
          </p>
        </div>

        {/* Job Description */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Job Description <span className="text-error">*</span>
          </label>
          <Textarea
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the job description here..."
            disabled={isPending}
            rows={6}
            required
          />
        </div>

        {/* Ideal Candidate Description */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Ideal Candidate Description <span className="text-error">*</span>
          </label>
          <Textarea
            value={idealCandidate}
            onChange={(e) => setIdealCandidate(e.target.value)}
            placeholder="Describe the ideal candidate in natural language (e.g., 'Strong in deep learning, experience with PyTorch, worked at top-tier tech companies...')"
            disabled={isPending}
            rows={6}
            required
          />
        </div>

        {/* Resume Upload */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">
            Applicant Resumes <span className="text-error">*</span>
          </label>
          <div
            {...getRootProps()}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
              ${isDragActive
                ? 'border-brand bg-brand/5'
                : 'border-divider hover:border-brand hover:bg-surface'
              }
              ${isPending ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input {...getInputProps()} />
            <CloudArrowUpIcon className="w-12 h-12 text-muted mx-auto mb-3" />
            <p className="text-text font-medium mb-1">
              {isDragActive ? 'Drop the files here...' : 'Drag & drop resume files here, or click to select'}
            </p>
            <p className="text-sm text-muted">
              Supports PDF, DOCX, and TXT files
            </p>
          </div>

          {/* Uploaded Files */}
          {resumes.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-medium text-text mb-2">
                Uploaded Resumes ({resumes.length})
              </p>
              <div className="flex flex-wrap gap-2">
                {resumes.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center space-x-2 px-3 py-1.5 bg-surface border border-divider rounded-lg text-sm"
                  >
                    <span className="text-text">{file.name}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveResume(index)}
                      disabled={isPending}
                      className="text-muted hover:text-error transition-colors disabled:opacity-50"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Submit Button */}
        <div className="flex justify-end pt-4">
          <Button
            type="submit"
            disabled={isPending || !jobDescription || !idealCandidate || resumes.length === 0}
            className="px-6"
          >
            {isPending ? (
              <>
                <span className="animate-spin mr-2">⏳</span>
                Starting Analysis...
              </>
            ) : (
              <>
                <PlayIcon className="w-5 h-5 mr-2" />
                Start Analysis
              </>
            )}
          </Button>
        </div>

        {/* Progress Indicator */}
        {isPending && (
          <div className="border-t border-divider pt-4">
            <div className="w-full bg-surface rounded-full h-2 overflow-hidden">
              <div className="h-full bg-brand animate-pulse"></div>
            </div>
            <p className="text-sm text-muted text-center mt-2">
              Initializing analysis pipeline...
            </p>
          </div>
        )}
      </form>
    </Card>
  );
};

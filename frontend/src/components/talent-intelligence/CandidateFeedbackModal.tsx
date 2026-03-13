/**
 * Candidate Score Feedback Panel
 * 
 * Slide-in sheet for users to provide feedback on candidate scores.
 * Used to tune the scoring algorithm.
 */

import React, { useState, useEffect } from 'react';
import {
  StarIcon as StarOutline,
  ChatBubbleBottomCenterTextIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarSolid } from '@heroicons/react/24/solid';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  Button,
  Spinner,
  Textarea,
  Label,
  Alert,
  Chip,
} from '../ui';

// Types
interface ScoreDimension {
  dimension: string;
  score: number;
  explanation?: string;
}

interface CandidateForFeedback {
  id: string;
  score_id: number;  // The candidate_analysis_score.id
  name: string;
  score: number;
  score_breakdown?: {
    dimensions?: ScoreDimension[];
  };
  current_title?: string;
  current_company?: string;
}

interface ExistingFeedback {
  id: number;
  user_rating: number;
  would_interview: string | null;
  dimension_feedback: Record<string, string> | null;
  feedback_notes: string | null;
  action_taken: string | null;
}

interface Props {
  candidate: CandidateForFeedback;
  onClose: () => void;
  onSubmit: () => void;
}

const WOULD_INTERVIEW_OPTIONS = [
  { value: 'definitely', label: 'Definitely' },
  { value: 'probably', label: 'Probably' },
  { value: 'maybe', label: 'Maybe' },
  { value: 'no', label: 'No' },
];

const ACTION_OPTIONS = [
  { value: 'contacted', label: 'Contacted' },
  { value: 'interviewed', label: 'Interviewed' },
  { value: 'hired', label: 'Hired' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'no_action', label: 'No action yet' },
];

const DIMENSION_LABELS: Record<string, string> = {
  skill_alignment: 'Skills',
  experience_fit: 'Experience',
  trajectory_match: 'Career Path',
  company_background: 'Background',
  organizational_fit: 'Culture Fit',
};

export default function CandidateFeedbackModal({ candidate, onClose, onSubmit }: Props) {
  // State
  const [rating, setRating] = useState<number>(0);
  const [hoveredRating, setHoveredRating] = useState<number>(0);
  const [wouldInterview, setWouldInterview] = useState<string | null>(null);
  const [dimensionFeedback, setDimensionFeedback] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState('');
  const [actionTaken, setActionTaken] = useState<string | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [existingFeedback, setExistingFeedback] = useState<ExistingFeedback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Load existing feedback on mount
  useEffect(() => {
    loadExistingFeedback();
  }, [candidate.score_id]);

  const loadExistingFeedback = async () => {
    setLoadingExisting(true);
    try {
      const response = await AXIOS_INSTANCE.get(`/api/v1/candidate-feedback/score/${candidate.score_id}`);
      if (response.data) {
        setExistingFeedback(response.data);
        setRating(response.data.user_rating);
        setWouldInterview(response.data.would_interview);
        setDimensionFeedback(response.data.dimension_feedback || {});
        setNotes(response.data.feedback_notes || '');
        setActionTaken(response.data.action_taken);
      }
    } catch (err: any) {
      // 404 means no existing feedback, which is fine
      if (err.response?.status !== 404) {
        console.error('Failed to load existing feedback:', err);
      }
    } finally {
      setLoadingExisting(false);
    }
  };

  const handleSubmit = async () => {
    if (rating === 0) {
      setError('Please provide a rating');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload = {
        candidate_analysis_score_id: candidate.score_id,
        user_rating: rating,
        would_interview: wouldInterview,
        dimension_feedback: Object.keys(dimensionFeedback).length > 0 ? dimensionFeedback : null,
        feedback_notes: notes || null,
        action_taken: actionTaken,
      };

      if (existingFeedback) {
        // Update existing
        await AXIOS_INSTANCE.put(`/api/v1/candidate-feedback/${existingFeedback.id}`, payload);
      } else {
        // Create new
        await AXIOS_INSTANCE.post('/api/v1/candidate-feedback', payload);
      }

      setSuccess(true);
      setTimeout(() => {
        onSubmit();
        onClose();
      }, 1000);
    } catch (err: any) {
      console.error('Failed to submit feedback:', err);
      setError(err.response?.data?.detail || 'Failed to submit feedback');
    } finally {
      setLoading(false);
    }
  };

  const handleDimensionFeedback = (dimension: string, accuracy: string) => {
    setDimensionFeedback(prev => ({
      ...prev,
      [dimension]: accuracy
    }));
  };

  const dimensions = candidate.score_breakdown?.dimensions || [];

  return (
    <Sheet open={true} onClose={onClose}>
      <SheetContent side="right" size="lg">
        <SheetHeader>
          <SheetTitle>Rate This Candidate</SheetTitle>
          <SheetDescription>{candidate.name}</SheetDescription>
        </SheetHeader>

        <SheetBody className="space-y-6">
          {loadingExisting ? (
            <div className="flex items-center justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : success ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-16 h-16 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mb-4">
                <CheckCircleIcon className="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-lg font-semibold text-charcoal dark:text-gray-100">Feedback Submitted!</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Thank you for helping improve our scoring.</p>
            </div>
          ) : (
            <>
              {/* Candidate Summary */}
              <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-dark-surface-2 rounded-xl border border-gray-200 dark:border-dark-border">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Current Score</p>
                  <p className="text-3xl font-bold text-eliza-red">{candidate.score}</p>
                </div>
                {(candidate.current_title || candidate.current_company) && (
                  <div className="text-right">
                    {candidate.current_title && (
                      <p className="text-sm font-medium text-charcoal dark:text-gray-100">{candidate.current_title}</p>
                    )}
                    {candidate.current_company && (
                      <p className="text-sm text-gray-500 dark:text-gray-400">{candidate.current_company}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Star Rating */}
              <div>
                <Label className="mb-3">
                  How accurate was this score? <span className="text-red-500">*</span>
                </Label>
                <div className="flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      onClick={() => setRating(star)}
                      onMouseEnter={() => setHoveredRating(star)}
                      onMouseLeave={() => setHoveredRating(0)}
                      className="p-1 transition-transform hover:scale-110"
                    >
                      {(hoveredRating || rating) >= star ? (
                        <StarSolid className="w-8 h-8 text-yellow-400" />
                      ) : (
                        <StarOutline className="w-8 h-8 text-gray-400 dark:text-gray-500 hover:text-yellow-400/50" />
                      )}
                    </button>
                  ))}
                  <span className="ml-3 text-sm text-gray-500 dark:text-gray-400">
                    {rating === 1 && 'Very inaccurate'}
                    {rating === 2 && 'Somewhat inaccurate'}
                    {rating === 3 && 'Neutral'}
                    {rating === 4 && 'Mostly accurate'}
                    {rating === 5 && 'Very accurate'}
                  </span>
                </div>
              </div>

              {/* Would Interview */}
              <div>
                <Label className="mb-3">Would you interview this candidate?</Label>
                <div className="flex flex-wrap gap-2">
                  {WOULD_INTERVIEW_OPTIONS.map((option) => (
                    <Chip
                      key={option.value}
                      variant="pill"
                      selected={wouldInterview === option.value}
                      showIcon={false}
                      onClick={() => setWouldInterview(wouldInterview === option.value ? null : option.value)}
                    >
                      {option.label}
                    </Chip>
                  ))}
                </div>
              </div>

              {/* Dimension Feedback */}
              {dimensions.length > 0 && (
                <div>
                  <Label className="mb-3">Which scores were off?</Label>
                  <div className="space-y-2">
                    {dimensions.map((dim) => (
                      <div 
                        key={dim.dimension}
                        className="flex items-center justify-between p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-lg border border-gray-200 dark:border-dark-border"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-medium text-charcoal dark:text-gray-100">
                            {DIMENSION_LABELS[dim.dimension] || dim.dimension.replace(/_/g, ' ')}
                          </span>
                          <span className={`text-sm font-medium ${
                            dim.score >= 70 ? 'text-green-600 dark:text-green-400' : dim.score >= 50 ? 'text-amber-500' : 'text-red-500'
                          }`}>
                            {dim.score?.toFixed(0)}
                          </span>
                        </div>
                        <div className="flex gap-1">
                          {(['too_high', 'accurate', 'too_low'] as const).map((accuracy) => (
                            <button
                              key={accuracy}
                              onClick={() => handleDimensionFeedback(dim.dimension, accuracy)}
                              className={`
                                px-2.5 py-1 rounded text-xs font-medium transition-all
                                ${dimensionFeedback[dim.dimension] === accuracy
                                  ? accuracy === 'accurate'
                                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-300 dark:border-green-700'
                                    : accuracy === 'too_high'
                                      ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-300 dark:border-red-700'
                                      : 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-300 dark:border-amber-700'
                                  : 'bg-gray-100 dark:bg-dark-surface text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-dark-border hover:text-charcoal dark:hover:text-gray-100'
                                }
                              `}
                            >
                              {accuracy === 'too_high' ? '↑ High' : accuracy === 'too_low' ? '↓ Low' : '✓ OK'}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Taken */}
              <div>
                <Label className="mb-3">What action did you take?</Label>
                <div className="flex flex-wrap gap-2">
                  {ACTION_OPTIONS.map((option) => (
                    <Chip
                      key={option.value}
                      variant="pill"
                      selected={actionTaken === option.value}
                      showIcon={false}
                      onClick={() => setActionTaken(actionTaken === option.value ? null : option.value)}
                    >
                      {option.label}
                    </Chip>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div>
                <Label className="mb-2">
                  <ChatBubbleBottomCenterTextIcon className="w-4 h-4 inline mr-1" />
                  Additional notes (optional)
                </Label>
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any additional context about this candidate..."
                  rows={3}
                />
              </div>

              {/* Error */}
              {error && (
                <Alert variant="error">{error}</Alert>
              )}
            </>
          )}
        </SheetBody>

        {/* Footer */}
        {!success && !loadingExisting && (
          <SheetFooter className="flex items-center justify-end gap-3">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={loading || rating === 0}
            >
              {loading ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Submitting...
                </>
              ) : existingFeedback ? (
                'Update Feedback'
              ) : (
                'Submit Feedback'
              )}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}

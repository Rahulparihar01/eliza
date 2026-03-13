/**
 * Feedback Panel - Eliza Forge
 * 
 * Slide-in panel from the right side of the screen for help and feedback.
 * Uses DS Sheet component for the slide-in container.
 */

import React, { useState } from 'react';
import {
  CheckCircleIcon,
  LightBulbIcon,
  BugAntIcon,
  SparklesIcon,
  ChatBubbleBottomCenterTextIcon,
  PaperAirplaneIcon,
} from '@heroicons/react/24/outline';
import axios from 'axios';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetBody,
  SheetFooter,
  Button,
  Input,
  Textarea,
  Select,
  SelectOption,
  Label,
  Alert,
  Spinner,
} from '../ui';

interface FeedbackPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

// Feedback types with icons and descriptions
const feedbackTypes = [
  {
    value: 'feature_request',
    label: 'Feature Request',
    icon: LightBulbIcon,
    description: 'Suggest new features or enhancements'
  },
  {
    value: 'bug_report',
    label: 'Bug Report',
    icon: BugAntIcon,
    description: 'Report issues or problems you encountered'
  },
  {
    value: 'model_improvement',
    label: 'AI Improvement',
    icon: SparklesIcon,
    description: 'Suggest improvements to AI models or results'
  },
  {
    value: 'general_feedback',
    label: 'General Feedback',
    icon: ChatBubbleBottomCenterTextIcon,
    description: 'Share your thoughts and suggestions'
  }
];

const categories = [
  { value: 'ai_recruiter', label: 'AI Recruiter' },
  { value: 'business_intelligence', label: 'Business Intelligence' },
  { value: 'data_connections', label: 'Data Connections' },
  { value: 'ui_ux', label: 'User Interface / Experience' },
  { value: 'performance', label: 'Performance / Speed' },
  { value: 'accuracy', label: 'Results Accuracy' },
  { value: 'other', label: 'Other' }
];

export function FeedbackPanel({ isOpen, onClose }: FeedbackPanelProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [category, setCategory] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [rating, setRating] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedType || !title || !description) {
      setError('Please fill in all required fields');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await axios.post('/api/v1/talent/feedback/submit', {
        feedback_type: selectedType,
        category: category || null,
        title,
        description,
        rating: rating,
        metadata: {
          user_agent: navigator.userAgent,
          screen_size: `${window.screen.width}x${window.screen.height}`,
          timestamp: new Date().toISOString()
        }
      });

      setSubmitted(true);
      
      // Reset form after 2 seconds
      setTimeout(() => {
        resetForm();
      }, 2000);
    } catch (err: unknown) {
      console.error('Failed to submit feedback:', err);
      const errorMessage = err instanceof Error 
        ? err.message 
        : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to submit feedback. Please try again.';
      setError(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setSelectedType(null);
    setCategory('');
    setTitle('');
    setDescription('');
    setRating(null);
    setSubmitted(false);
    setError(null);
  };

  return (
    <Sheet open={isOpen} onClose={onClose}>
      <SheetContent side="right" size="md" topOffset={48}>
        {/* Header */}
        <SheetHeader>
          <div>
            <SheetTitle>Help & Feedback</SheetTitle>
            <SheetDescription>Share your thoughts with us</SheetDescription>
          </div>
        </SheetHeader>

        {/* Body */}
        <SheetBody>
          {submitted ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 bg-green-50 dark:bg-green-950/30 rounded-full flex items-center justify-center mb-4">
                <CheckCircleIcon className="h-8 w-8 text-green-500" />
              </div>
              <h3 className="font-subtitle text-h3 text-charcoal dark:text-gray-100 mb-2">
                Thank you!
              </h3>
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                Your feedback has been submitted successfully.
              </p>
              <Button variant="brand" onClick={resetForm}>
                Submit Another
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Error Display */}
              {error && (
                <Alert variant="error" onDismiss={() => setError(null)}>
                  {error}
                </Alert>
              )}

              {/* Feedback Type Selection */}
              <div className="space-y-2">
                <Label>
                  What type of feedback? <span className="text-red-500">*</span>
                </Label>
                <div className="grid grid-cols-2 gap-2">
                  {feedbackTypes.map((type) => {
                    const Icon = type.icon;
                    const isSelected = selectedType === type.value;
                    return (
                      <button
                        key={type.value}
                        type="button"
                        onClick={() => setSelectedType(type.value)}
                        className={`p-3 rounded-xl border-2 text-left transition-all ${
                          isSelected
                            ? 'border-eliza-red bg-eliza-red/5 dark:bg-eliza-red/10'
                            : 'border-gray-200 dark:border-dark-border/50 bg-white dark:bg-dark-surface hover:border-gray-300 dark:hover:border-dark-border'
                        }`}
                      >
                        <Icon className={`h-5 w-5 mb-1 ${
                          isSelected 
                            ? 'text-eliza-red' 
                            : 'text-gray-500 dark:text-gray-400'
                        }`} />
                        <div className="text-sm font-medium text-charcoal dark:text-gray-100">
                          {type.label}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Category */}
              <div className="space-y-2">
                <Label>Category</Label>
                <Select
                  value={category}
                  onValueChange={(value) => setCategory(value)}
                  placeholder="Select a category (optional)"
                >
                  {categories.map((cat) => (
                    <SelectOption key={cat.value} value={cat.value}>
                      {cat.label}
                    </SelectOption>
                  ))}
                </Select>
              </div>

              {/* Title */}
              <div className="space-y-2">
                <Label>
                  Title <span className="text-red-500">*</span>
                </Label>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Brief summary of your feedback"
                  required
                />
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label>
                  Description <span className="text-red-500">*</span>
                </Label>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Please provide as much detail as possible..."
                  rows={4}
                  required
                />
              </div>

              {/* Rating */}
              <div className="space-y-2">
                <Label>How would you rate your experience?</Label>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setRating(rating === value ? null : value)}
                      className={`w-10 h-10 rounded-full border font-medium transition-all ${
                        rating === value
                          ? 'border-eliza-red bg-eliza-red text-white'
                          : 'border-gray-200 dark:border-dark-border bg-white dark:bg-dark-surface text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-dark-border'
                      }`}
                    >
                      {value}
                    </button>
                  ))}
                </div>
                <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 px-1">
                  <span>Poor</span>
                  <span>Excellent</span>
                </div>
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                variant="brand"
                disabled={submitting || !selectedType || !title || !description}
                className="w-full"
              >
                {submitting ? (
                  <>
                    <Spinner size="sm" variant="white" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <>
                    <PaperAirplaneIcon className="h-4 w-4" />
                    <span>Submit Feedback</span>
                  </>
                )}
              </Button>
            </form>
          )}
        </SheetBody>

        {/* Footer */}
        <SheetFooter>
          <p className="text-xs text-gray-500 dark:text-gray-400 text-center w-full">
            Your feedback helps us improve Eliza Forge for everyone.
          </p>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export default FeedbackPanel;

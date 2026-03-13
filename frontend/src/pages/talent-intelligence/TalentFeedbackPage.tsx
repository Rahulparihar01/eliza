/**
 * Feedback & Help Page
 * 
 * Allows users to submit feedback about the platform
 * including feature requests, bug reports, and general suggestions.
 */

import React, { useState } from 'react';
import { Layout } from '../../components/layout/Layout';
import { 
  ChatBubbleLeftRightIcon, 
  PaperAirplaneIcon,
  CheckCircleIcon,
  LightBulbIcon,
  BugAntIcon,
  SparklesIcon,
  ChatBubbleBottomCenterTextIcon,
  QuestionMarkCircleIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';

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

export default function TalentFeedbackPage() {
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
        setSelectedType(null);
        setCategory('');
        setTitle('');
        setDescription('');
        setRating(null);
        setSubmitted(false);
      }, 2000);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit feedback. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // Custom input styles that work well with dark theme
  const inputStyles = `
    w-full px-4 py-3 
    bg-surface border border-border rounded-lg
    text-primary placeholder-muted
    focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand
    transition-colors duration-200
  `;

  const selectStyles = `
    w-full md:w-1/2 px-4 py-3 
    bg-surface border border-border rounded-lg
    text-primary
    focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand
    transition-colors duration-200
    cursor-pointer
  `;

  return (
    <Layout
      pageTitle="Feedback & Help"
      breadcrumbs={[
        { label: 'Feedback & Help' }
      ]}
    >
      {/* Scrollable container */}
      <div className="h-full overflow-y-auto">
        <div className="max-w-4xl mx-auto pb-12">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-3 bg-brand/10 rounded-lg">
                <ChatBubbleLeftRightIcon className="h-8 w-8 text-brand" />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-primary">Feedback & Help</h1>
                <p className="text-muted mt-1">
                  Help us improve Eliza Forge by sharing your thoughts, suggestions, and experiences.
                </p>
              </div>
            </div>
          </div>

          {/* Success Message */}
          {submitted && (
            <div className="mb-6 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
              <div className="flex items-center gap-3">
                <CheckCircleIcon className="h-6 w-6 text-green-500" />
                <div>
                  <h3 className="text-sm font-semibold text-green-400">
                    Thank you for your feedback!
                  </h3>
                  <p className="text-sm text-green-400/80">
                    We've received your submission and will review it soon.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Feedback Form */}
          <div className="bg-surface-raised border border-border rounded-xl p-6 shadow-lg">
            <form onSubmit={handleSubmit}>
              {/* Step 1: Select Feedback Type */}
              <div className="mb-8">
                <label className="block text-sm font-semibold text-primary mb-4">
                  What type of feedback do you have?
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {feedbackTypes.map((type) => {
                    const Icon = type.icon;
                    const isSelected = selectedType === type.value;
                    
                    return (
                      <button
                        key={type.value}
                        type="button"
                        onClick={() => setSelectedType(type.value)}
                        className={`
                          p-4 rounded-lg border-2 text-left transition-all
                          ${isSelected
                            ? 'border-brand bg-brand/10'
                            : 'border-border bg-surface hover:border-brand/50 hover:bg-surface-raised'
                          }
                        `}
                      >
                        <div className="flex items-start gap-3">
                          <Icon className={`h-6 w-6 flex-shrink-0 ${isSelected ? 'text-brand' : 'text-muted'}`} />
                          <div>
                            <div className={`text-sm font-semibold ${isSelected ? 'text-brand' : 'text-primary'}`}>
                              {type.label}
                            </div>
                            <div className="text-xs text-muted mt-1">
                              {type.description}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Step 2: Category (optional) */}
              {selectedType && (
                <div className="mb-6">
                  <label htmlFor="category" className="block text-sm font-semibold text-primary mb-2">
                    Category (Optional)
                  </label>
                  <select
                    id="category"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className={selectStyles}
                  >
                    <option value="">-- Select a category --</option>
                    {categories.map((cat) => (
                      <option key={cat.value} value={cat.value}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Step 3: Title */}
              {selectedType && (
                <div className="mb-6">
                  <label htmlFor="title" className="block text-sm font-semibold text-primary mb-2">
                    Title <span className="text-red-400">*</span>
                  </label>
                  <input
                    id="title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Brief summary of your feedback"
                    className={inputStyles}
                    maxLength={255}
                    required
                  />
                </div>
              )}

              {/* Step 4: Description */}
              {selectedType && (
                <div className="mb-6">
                  <label htmlFor="description" className="block text-sm font-semibold text-primary mb-2">
                    Description <span className="text-red-400">*</span>
                  </label>
                  <textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Please provide as much detail as possible. For bug reports, include steps to reproduce. For model improvements, describe what could be better and why."
                    className={`${inputStyles} resize-none`}
                    rows={6}
                    required
                  />
                  <p className="text-xs text-muted mt-2">
                    {description.length} characters
                  </p>
                </div>
              )}

              {/* Step 5: Rating (optional for general feedback) */}
              {selectedType === 'general_feedback' && (
                <div className="mb-6">
                  <label className="block text-sm font-semibold text-primary mb-2">
                    Overall Satisfaction (Optional)
                  </label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        onClick={() => setRating(star)}
                        className="group p-1 rounded hover:bg-surface-raised transition-colors"
                      >
                        <svg
                          className={`h-8 w-8 transition-colors ${
                            rating && star <= rating
                              ? 'text-yellow-400 fill-yellow-400'
                              : 'text-muted stroke-current group-hover:text-yellow-300'
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={1.5}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                          />
                        </svg>
                      </button>
                    ))}
                  </div>
                  {rating && (
                    <p className="text-xs text-muted mt-2">
                      Rating: {rating} out of 5 stars
                    </p>
                  )}
                </div>
              )}

              {/* Submit Button */}
              {selectedType && (
                <div className="flex items-center gap-4 pt-4 border-t border-border">
                  <button
                    type="submit"
                    disabled={submitting || !title || !description}
                    className="btn-primary flex items-center gap-2 px-6 py-3"
                  >
                    <PaperAirplaneIcon className="h-5 w-5" />
                    {submitting ? 'Submitting...' : 'Submit Feedback'}
                  </button>
                  
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedType(null);
                      setCategory('');
                      setTitle('');
                      setDescription('');
                      setRating(null);
                      setError(null);
                    }}
                    className="px-6 py-3 text-muted hover:text-primary transition-colors"
                  >
                    Clear Form
                  </button>
                </div>
              )}
            </form>
          </div>

          {/* Info Box */}
          <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <h3 className="text-sm font-semibold text-blue-400 mb-2">
              How Your Feedback Helps
            </h3>
            <ul className="text-sm text-blue-300/80 space-y-1">
              <li>• Your feedback directly improves our AI models and prompts</li>
              <li>• Bug reports help us fix issues faster</li>
              <li>• Feature requests guide our development roadmap</li>
              <li>• Model improvement suggestions enhance accuracy and relevance</li>
            </ul>
          </div>
        </div>
      </div>
    </Layout>
  );
}

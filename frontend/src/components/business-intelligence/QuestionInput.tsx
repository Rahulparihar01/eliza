/**
 * Question Input Component
 * Form for submitting business intelligence questions
 */

import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { PaperAirplaneIcon, SparklesIcon, LightBulbIcon } from '@heroicons/react/24/outline';
import { useSubmitQuestionV1BiQuestionsPost } from '../../generated/business-intelligence/business-intelligence';
import { useToasts } from '../../stores/useToasts';
import { queryKeys } from '../../lib/query-keys';
import Button from '../../shared/ui/Button';
import Textarea from '../../shared/ui/Textarea';
import Card from '../../shared/ui/Card';

interface QuestionInputProps {
  onQuestionSubmitted?: (questionId: string) => void;
  companyHrDataset?: string | null;
  variant?: 'card' | 'panel';
}

export default function QuestionInput({ onQuestionSubmitted, companyHrDataset, variant = 'card' }: QuestionInputProps) {
  const [question, setQuestion] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);

  const submitQuestionMutation = useSubmitQuestionV1BiQuestionsPost();

  const exampleQuestions = [
    "What is our current employee turnover rate?",
    "Which departments have the highest performance ratings?",
    "What are the most common skills across our workforce?",
    "How many employees are due for performance reviews this quarter?",
    "What is the average tenure of employees in engineering?",
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!question.trim()) {
      addToast({
        kind: 'error',
        message: 'Please enter a question',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await submitQuestionMutation.mutateAsync({
        data: {
          question: question.trim(),
          company_hr_dataset: companyHrDataset || undefined,
        },
      });

      addToast({
        kind: 'success',
        message: 'Question submitted successfully! Processing...',
      });

      // Invalidate questions list to refresh
      queryClient.invalidateQueries({ queryKey: queryKeys.businessIntelligence.questions() });

      // Notify parent component
      if (onQuestionSubmitted && response.question_id) {
        onQuestionSubmitted(response.question_id);
      }

      // Clear the input
      setQuestion('');
    } catch (error: any) {
      console.error('Failed to submit question:', error);
      addToast({
        kind: 'error',
        message: error.response?.data?.detail || 'Failed to submit question. Please try again.',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExampleClick = (exampleQuestion: string) => {
    setQuestion(exampleQuestion);
  };

  const Container: React.FC<{children: React.ReactNode}> = ({ children }) => (
    variant === 'card' ? <Card>{children}</Card> : <div className="rounded-lg bg-surface shadow-1 p-4">{children}</div>
  );

  return (
    <Container>
      {variant === 'card' && (
        <div className="flex items-center space-x-2 mb-4">
          <SparklesIcon className="w-5 h-5 text-brand" />
          <h2 className="text-lg font-semibold text-text">Ask a Question</h2>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="question" className="block text-sm font-medium text-text mb-2">
            What would you like to know about your business?
          </label>
          <Textarea
            id="question"
            rows={4}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g., What is our current employee turnover rate by department?"
            disabled={isSubmitting}
          />
          <p className="mt-2 text-sm text-muted">
            Ask questions about your HR data, documents, or business metrics
          </p>
        </div>

        <Button type="submit" disabled={isSubmitting || !question.trim()} fullWidth>
          {isSubmitting ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
              Processing...
            </>
          ) : (
            <>
              <PaperAirplaneIcon className="w-5 h-5 mr-2" />
              Submit Question
            </>
          )}
        </Button>
      </form>

      {/* Suggestions dropdown */}
      <div className={`${variant === 'card' ? 'mt-6 pt-6 border-t border-border' : 'mt-3'}`}>
        <button
          type="button"
          onClick={() => setSuggestionsOpen((v) => !v)}
          className="inline-flex items-center text-sm text-muted hover:text-text"
          aria-expanded={suggestionsOpen}
        >
          <LightBulbIcon className="w-4 h-4 mr-2" />
          Suggestions
          <span className={`ml-2 transition-transform ${suggestionsOpen ? 'rotate-180' : ''}`}>▾</span>
        </button>
        {suggestionsOpen && (
          <div className="mt-3 space-y-2">
            {exampleQuestions.map((example, index) => (
              <Button
                key={index}
                type="button"
                onClick={() => handleExampleClick(example)}
                variant="secondary"
                size="sm"
                className="w-full justify-start"
                disabled={isSubmitting}
              >
                {example}
              </Button>
            ))}
          </div>
        )}
      </div>
    </Container>
  );
}

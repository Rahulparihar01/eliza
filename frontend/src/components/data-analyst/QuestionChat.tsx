/**
 * Question Chat Component
 * Interface for submitting questions and viewing conversation history
 */
import React, { useState, useEffect, useRef } from 'react';
import { DataSourceType } from '../../generated/models';
import {
  useSubmitQuestionV1DataAnalystQuestionsPost,
  useListQuestionsV1DataAnalystQuestionsGet,
} from '../../generated/data-analyst/data-analyst';

interface QuestionChatProps {
  dataSourceType: DataSourceType;
  onQuestionSubmitted: (questionId: string) => void;
  selectedQuestionId: string | null;
}

export default function QuestionChat({ 
  dataSourceType, 
  onQuestionSubmitted,
  selectedQuestionId 
}: QuestionChatProps) {
  const [question, setQuestion] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  
  const { mutate: submitQuestion, isPending } = useSubmitQuestionV1DataAnalystQuestionsPost();
  const { data: questionsData } = useListQuestionsV1DataAnalystQuestionsGet({
    data_source_type: dataSourceType,
    page: 1,
    page_size: 50,
  }, {
    query: {
      refetchInterval: 3000, // Poll for status updates
    },
  });

  // Scroll to bottom when new questions are added
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [questionsData?.questions]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isPending) return;

    submitQuestion(
      {
        data: {
          data_source_type: dataSourceType,
          question: question.trim(),
        },
      },
      {
        onSuccess: (response) => {
          onQuestionSubmitted(response.question_id);
          setQuestion('');
        },
        onError: (error) => {
          console.error('Failed to submit question:', error);
        },
      }
    );
  };

  const questions = questionsData?.questions || [];

  return (
    <div className="flex flex-col h-full">
      {/* Question History */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {questions.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted">
            <div className="text-center">
              <p className="text-lg mb-2">No questions yet</p>
              <p className="text-sm">Ask a question to get started</p>
            </div>
          </div>
        ) : (
          questions.map((q) => (
            <div
              key={q.question_id}
              onClick={() => onQuestionSubmitted(q.question_id)}
              className={`p-4 rounded-lg cursor-pointer transition-colors ${
                selectedQuestionId === q.question_id
                  ? 'bg-primary/10 border-2 border-primary/30'
                  : 'bg-surface border border-border hover:bg-surface-hover'
              }`}
            >
              <p className="text-text font-medium">{q.original_question}</p>
              <div className="flex items-center gap-3 mt-2 text-sm">
                <span className={`px-2 py-1 rounded text-xs ${
                  q.status === 'completed' ? 'bg-green-500/20 text-green-600' :
                  q.status === 'processing' ? 'bg-blue-500/20 text-blue-600' :
                  q.status === 'failed' ? 'bg-red-500/20 text-red-600' :
                  'bg-gray-500/20 text-gray-600'
                }`}>
                  {q.status}
                </span>
                <span className="text-muted">
                  {new Date(q.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Question Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your data..."
            className="flex-1 px-4 py-2 border border-border rounded-lg bg-bg text-text focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={isPending || !question.trim()}
            className="px-6 py-2 bg-primary text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
          >
            {isPending ? 'Processing...' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  );
}


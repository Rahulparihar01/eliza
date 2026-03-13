import React, { useState } from 'react';
import { PaperAirplaneIcon, ArrowPathIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import {
  useSubmitFeedbackApiV1MlTalentAnalysisAnalysisIdFeedbackPost,
  useRefinePdlQueryApiV1MlTalentAnalysisAnalysisIdRefinePost,
} from '../../generated/ml-talent-intelligence/ml-talent-intelligence';
import { useToasts } from '../../stores/useToasts';
import Button from '../../shared/ui/Button';
import Card from '../../shared/ui/Card';
import Textarea from '../../shared/ui/Textarea';

interface AnalysisFeedbackProps {
  analysisId: string;
  onQueryRefined: () => void;
}

interface AttributeWeight {
  name: string;
  label: string;
  weight: number;
  enabled: boolean;
}

export const AnalysisFeedback: React.FC<AnalysisFeedbackProps> = ({ analysisId, onQueryRefined }) => {
  const [generalFeedback, setGeneralFeedback] = useState('');
  const [candidateFeedback, setCandidateFeedback] = useState('');
  const [patternFeedback, setPatternFeedback] = useState('');
  const [weightsExpanded, setWeightsExpanded] = useState(true);
  const [attributeWeights, setAttributeWeights] = useState<AttributeWeight[]>([
    { name: 'deep_learning_expertise', label: 'Deep Learning Expertise', weight: 0.9, enabled: true },
    { name: 'pytorch_experience', label: 'PyTorch Experience', weight: 0.85, enabled: true },
    { name: 'production_ml_systems', label: 'Production ML Systems', weight: 0.8, enabled: true },
    { name: 'research_publications', label: 'Research Publications', weight: 0.7, enabled: true },
    { name: 'top_tier_company', label: 'Top Tier Company', weight: 0.75, enabled: true },
    { name: 'phd_or_masters', label: 'PhD or Masters', weight: 0.6, enabled: true },
  ]);
  const { push: addToast } = useToasts();

  const { mutate: submitFeedback, isPending: isSubmittingFeedback } =
    useSubmitFeedbackApiV1MlTalentAnalysisAnalysisIdFeedbackPost({
      mutation: {
        onSuccess: () => {
          addToast({
            kind: 'success',
            message: 'Feedback submitted successfully!',
          });
          setGeneralFeedback('');
          setCandidateFeedback('');
          setPatternFeedback('');
        },
        onError: (err: any) => {
          addToast({
            kind: 'error',
            message: err?.response?.data?.detail || 'Failed to submit feedback',
          });
        },
      },
    });

  const { mutate: refineQuery, isPending: isRefining } = useRefinePdlQueryApiV1MlTalentAnalysisAnalysisIdRefinePost({
    mutation: {
      onSuccess: () => {
        addToast({
          kind: 'success',
          message: 'Query refined successfully! New market search initiated.',
        });
        setTimeout(() => {
          onQueryRefined();
        }, 1000);
      },
      onError: (err: any) => {
        addToast({
          kind: 'error',
          message: err?.response?.data?.detail || 'Failed to refine query',
        });
      },
    },
  });

  const handleAttributeWeightChange = (index: number, newWeight: number) => {
    const updated = [...attributeWeights];
    updated[index].weight = newWeight;
    setAttributeWeights(updated);
  };

  const handleAttributeToggle = (index: number) => {
    const updated = [...attributeWeights];
    updated[index].enabled = !updated[index].enabled;
    setAttributeWeights(updated);
  };

  const handleSubmitFeedback = (e: React.FormEvent) => {
    e.preventDefault();

    const feedbackData: any = {
      general_feedback: generalFeedback || undefined,
      candidate_feedback: candidateFeedback || undefined,
      pattern_validation: patternFeedback || undefined,
    };

    submitFeedback({
      analysisId,
      data: feedbackData,
    });
  };

  const handleRefineQuery = () => {
    // Build attribute adjustments from weights
    const attributeAdjustments: Record<string, number> = {};
    attributeWeights.forEach((attr) => {
      if (attr.enabled) {
        attributeAdjustments[attr.name] = attr.weight;
      }
    });

    const refinementData = {
      analysis_id: analysisId,
      refinement_feedback: {
        attribute_adjustments: attributeAdjustments,
        notes: generalFeedback || undefined,
      },
    };

    refineQuery({
      analysisId,
      data: refinementData,
    });
  };

  return (
    <div className="space-y-6">
      {/* General Feedback */}
      <Card>
        <h3 className="text-lg font-semibold text-text mb-1">General Feedback</h3>
        <p className="text-sm text-muted mb-4">
          Provide overall feedback on the analysis quality, candidate selection, or any observations.
        </p>
        <form onSubmit={handleSubmitFeedback}>
          <Textarea
            value={generalFeedback}
            onChange={(e) => setGeneralFeedback(e.target.value)}
            placeholder="E.g., 'The analysis focused too much on academic credentials. I'd prefer more emphasis on production experience...'"
            disabled={isSubmittingFeedback}
            rows={4}
          />
        </form>
      </Card>

      {/* Candidate-Specific Feedback */}
      <Card>
        <h3 className="text-lg font-semibold text-text mb-1">Candidate Feedback</h3>
        <p className="text-sm text-muted mb-4">
          Comment on specific candidates - which ones were great matches, which weren't, and why.
        </p>
        <Textarea
          value={candidateFeedback}
          onChange={(e) => setCandidateFeedback(e.target.value)}
          placeholder="E.g., 'Candidate #1 was excellent - strong production experience. Candidate #3 lacked the deep learning background we need...'"
          disabled={isSubmittingFeedback}
          rows={4}
        />
      </Card>

      {/* Pattern Validation */}
      <Card>
        <h3 className="text-lg font-semibold text-text mb-1">Pattern Validation</h3>
        <p className="text-sm text-muted mb-4">
          Validate or correct the patterns identified by the system (e.g., career trajectories, skill clusters).
        </p>
        <Textarea
          value={patternFeedback}
          onChange={(e) => setPatternFeedback(e.target.value)}
          placeholder="E.g., 'The pattern about top-tier companies is correct, but startup experience is equally valuable for our team...'"
          disabled={isSubmittingFeedback}
          rows={4}
        />
      </Card>

      {/* Submit Feedback Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSubmitFeedback}
          disabled={isSubmittingFeedback || (!generalFeedback && !candidateFeedback && !patternFeedback)}
        >
          {isSubmittingFeedback ? (
            <>
              <span className="animate-spin mr-2">⏳</span>
              Submitting...
            </>
          ) : (
            <>
              <PaperAirplaneIcon className="w-5 h-5 mr-2" />
              Submit Feedback
            </>
          )}
        </Button>
      </div>

      <div className="border-t border-divider my-8"></div>

      {/* Query Refinement Section */}
      <Card>
        <h2 className="text-lg font-semibold text-text mb-1">Refine Market Search Query</h2>
        <p className="text-sm text-muted mb-4">
          Adjust attribute importance and re-run the PDL market search with refined parameters.
        </p>

        {/* Attribute Weights */}
        <div className="bg-surface rounded-lg border border-divider">
          <button
            onClick={() => setWeightsExpanded(!weightsExpanded)}
            className="w-full flex items-center justify-between p-4 text-left hover:bg-bg transition-colors"
          >
            <span className="font-medium text-text">Attribute Weights</span>
            {weightsExpanded ? (
              <ChevronUpIcon className="w-5 h-5 text-muted" />
            ) : (
              <ChevronDownIcon className="w-5 h-5 text-muted" />
            )}
          </button>

          {weightsExpanded && (
            <div className="p-4 pt-0 space-y-4">
              {attributeWeights.map((attr, index) => (
                <div key={attr.name} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={attr.enabled}
                        onChange={() => handleAttributeToggle(index)}
                        disabled={isRefining}
                        className="rounded border-divider text-brand focus:ring-brand"
                      />
                      <span className="text-sm text-text">{attr.label}</span>
                    </label>
                    <span className="px-2 py-1 bg-surface border border-divider rounded text-sm text-text font-mono">
                      {attr.weight.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={attr.weight}
                    onChange={(e) => handleAttributeWeightChange(index, parseFloat(e.target.value))}
                    disabled={!attr.enabled || isRefining}
                    className="w-full h-2 bg-surface rounded-lg appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  />
                  <div className="flex justify-between text-xs text-muted">
                    <span>0.0</span>
                    <span>0.5</span>
                    <span>1.0</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-4 p-4 bg-brand/10 border border-brand/20 rounded-lg text-sm text-text">
          💡 Adjusting these weights will generate a new PDL query and search for market candidates with
          the updated criteria. The applicant analysis will remain unchanged.
        </div>

        <div className="flex justify-end mt-6">
          <Button onClick={handleRefineQuery} disabled={isRefining}>
            {isRefining ? (
              <>
                <span className="animate-spin mr-2">⏳</span>
                Refining Query...
              </>
            ) : (
              <>
                <ArrowPathIcon className="w-5 h-5 mr-2" />
                Refine & Re-Search
              </>
            )}
          </Button>
        </div>

        {isRefining && (
          <div className="mt-4">
            <div className="w-full bg-surface rounded-full h-2 overflow-hidden">
              <div className="h-full bg-brand animate-pulse"></div>
            </div>
            <p className="text-sm text-muted text-center mt-2">
              Generating new query and searching market candidates...
            </p>
          </div>
        )}
      </Card>
    </div>
  );
};

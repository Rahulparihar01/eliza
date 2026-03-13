/**
 * Talent Intelligence Page
 * 
 * AI-powered talent analysis to find ideal candidates from ingested people data.
 * Uses CrewAI flow with 3 specialized agents to analyze job descriptions and find look-alike candidates.
 */

import React, { useState } from 'react';
import { SparklesIcon, DocumentTextIcon, UserGroupIcon, FolderIcon } from '@heroicons/react/24/outline';
import { JobDescriptionUpload } from '../../components/talent-intelligence/JobDescriptionUpload';
import { PersonaDefinitionForm } from '../../components/talent-intelligence/PersonaDefinitionForm';
import { AnalysisProgress } from '../../components/talent-intelligence/AnalysisProgress';
import { CandidateResults } from '../../components/talent-intelligence/CandidateResults';
import { PersonaSummary } from '../../components/talent-intelligence/PersonaSummary';
import { AnalysisSummary } from '../../components/talent-intelligence/AnalysisSummary';
import { EmployeeSelector } from '../../components/ml-talent/EmployeeSelector';
import { DataSourceSelector } from '../../components/ml-talent/DataSourceSelector';
import { GreenhouseQueryConfig, type GreenhouseQueryParams } from '../../components/talent-intelligence/GreenhouseQueryConfig';
import { useStartMlTalentAnalysisFromConnectorApiV1MlTalentAnalyzeFromConnectorPost } from '../../generated/ml-talent-intelligence/ml-talent-intelligence';
import { useListConnectorConfigurationsApiConnectorsConfigurationsGet } from '../../generated/data-connectors/data-connectors';
import { useToasts } from '../../stores/useToasts';

type WorkflowStep = 'employees' | 'datasource' | 'greenhouse-config' | 'input' | 'analysis' | 'processing' | 'results';
type InputMethod = 'job_description' | 'manual_persona';

interface UploadedFileInfo {
  name: string;
  type: string;
  wordCount: number;
}

interface WorkflowConfig {
  // Step 1: LinkedIn profiles for look-alike matching OR existing blueprint
  linkedInUrls: string[];
  selectedBlueprintId: number | null;
  
  // Step 2: Data source
  selectedConnectorId: string | null;
  selectedConnectorType: string | null;
  
  // Step 2b: Greenhouse configuration (if Greenhouse selected)
  greenhouseQueryParams: GreenhouseQueryParams | null;
  
  // Step 3: Requirements
  inputMethod: InputMethod | null;
  jobDescription: string;
  idealCandidateDescription: string;
  uploadedFile: UploadedFileInfo | null;
  manualPersona: any | null;
  
  // Step 4: Analysis settings
  pdlQueryLimit: number;
  selectedEmailTemplateId: string | null;
}

export function TalentIntelligencePage() {
  const [workflowStep, setWorkflowStep] = useState<WorkflowStep>('employees');
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analysisResults, setAnalysisResults] = useState<any>(null);
  
  // Centralized workflow configuration state
  const [config, setConfig] = useState<WorkflowConfig>({
    linkedInUrls: [],
    selectedBlueprintId: null,
    selectedConnectorId: null,
    selectedConnectorType: null,
    greenhouseQueryParams: null,
    inputMethod: null,
    jobDescription: '',
    idealCandidateDescription: '',
    uploadedFile: null,
    manualPersona: null,
    pdlQueryLimit: 50, // Default to 50 for quality results
    selectedEmailTemplateId: null,
  });
  
  const { push: addToast } = useToasts();
  const { mutate: startAnalysis } = useStartMlTalentAnalysisFromConnectorApiV1MlTalentAnalyzeFromConnectorPost();
  const { data: connectorsData } = useListConnectorConfigurationsApiConnectorsConfigurationsGet({ is_enabled: true });

  const handleJobDescriptionSubmit = async (jobDescription: string, idealCandidateDescription: string) => {
    // Save to config and go back to method selection
    setConfig(prev => ({
      ...prev,
      jobDescription,
      idealCandidateDescription,
      inputMethod: null, // Reset to show card selection view
    }));
    
    // Show confirmation toast
    addToast({
      message: 'Job description saved! You can now continue to analysis or edit the ideal persona.',
      kind: 'success',
    });
  };

  const handlePersonaSubmit = async (persona: any) => {
    // Save to config and go back to method selection
    setConfig(prev => ({
      ...prev,
      manualPersona: persona,
      inputMethod: null, // Reset to show card selection view
    }));
    
    // Show confirmation toast
    addToast({
      message: 'Ideal persona saved! You can now continue to analysis.',
      kind: 'success',
    });
  };

  const handleAnalysisComplete = (results: any) => {
    setAnalysisResults(results);
    setWorkflowStep('results');
  };

  const handleLinkedInProfilesSelected = (linkedInUrls: string[], blueprintId?: number) => {
    setConfig(prev => ({ 
      ...prev, 
      linkedInUrls: linkedInUrls,
      selectedBlueprintId: blueprintId || null,
    }));
    setWorkflowStep('datasource');
  };

  const handleDataSourceSelected = (connectorId: string) => {
    // Get connector type
    const connector = connectorsData?.connectors?.find(c => c.connector_id === connectorId);
    const connectorType = connector?.connector_type || null;
    
    setConfig(prev => ({ 
      ...prev, 
      selectedConnectorId: connectorId,
      selectedConnectorType: connectorType,
    }));
    
    // If Greenhouse, go to configuration step, otherwise skip to input
    if (connectorType === 'greenhouse') {
      setWorkflowStep('greenhouse-config');
    } else {
      setWorkflowStep('input');
    }
  };

  const handleRunAnalysis = () => {
    // Validate required fields
    if (!config.selectedConnectorId) {
      addToast({
        message: 'Please select a data source connector',
        kind: 'error',
      });
      return;
    }
    
    if (config.linkedInUrls.length === 0 && !config.selectedBlueprintId) {
      addToast({
        message: 'Please select a blueprint or add LinkedIn profiles for look-alike matching',
        kind: 'error',
      });
      return;
    }

    if (!config.jobDescription && !config.manualPersona) {
      addToast({
        message: 'Please provide either a job description or define an ideal persona',
        kind: 'error',
      });
      return;
    }
    
    startAnalysis(
      {
        data: {
          job_description: config.jobDescription,
          ideal_candidate_description: config.idealCandidateDescription,
          data_source_connector_id: config.selectedConnectorId,
          baseline_linkedin_urls: config.linkedInUrls.length > 0 ? config.linkedInUrls : undefined,
          blueprint_id: config.selectedBlueprintId || undefined,
          greenhouse_query_params: config.greenhouseQueryParams as any || undefined,
          pdl_query_limit: config.pdlQueryLimit,
        } as any  // Type assertion until OpenAPI types are regenerated
      },
      {
        onSuccess: (response: { analysis_id: string; status: string; message: string }) => {
          setAnalysisId(response.analysis_id);
          setWorkflowStep('processing');
          addToast({
            message: 'Analysis started! Our AI agents are working on finding the best candidates.',
            kind: 'success',
          });
        },
        onError: (error: any) => {
          console.error('Failed to start analysis:', error);
          addToast({
            message: error?.response?.data?.detail || 'Failed to start analysis. Please try again.',
            kind: 'error',
          });
        },
      }
    );
  };

  // Navigation helpers - can go back to any completed step
  const canNavigateTo = (step: WorkflowStep): boolean => {
    const steps: WorkflowStep[] = ['employees', 'datasource', 'input', 'analysis', 'processing', 'results'];
    const currentIndex = steps.indexOf(workflowStep);
    const targetIndex = steps.indexOf(step);
    
    // Can't go to processing or results directly
    if (step === 'processing' || step === 'results') return false;
    
    // Can go back to any previous step
    if (targetIndex < currentIndex) return true;
    
    // Can go to next step if current is complete
    if (targetIndex === currentIndex + 1) {
        if (step === 'datasource') return config.linkedInUrls.length > 0 || config.selectedBlueprintId !== null;
      if (step === 'input') return config.selectedConnectorId !== null;
      if (step === 'analysis') return !!(config.jobDescription || config.manualPersona);
    }
    
    return false;
  };

  const navigateToStep = (step: WorkflowStep) => {
    if (canNavigateTo(step)) {
      setWorkflowStep(step);
    }
  };

  const handleStartOver = () => {
    setWorkflowStep('employees');
    setAnalysisId(null);
    setAnalysisResults(null);
    setConfig({
      linkedInUrls: [],
      selectedBlueprintId: null,
      selectedConnectorId: null,
      selectedConnectorType: null,
      greenhouseQueryParams: null,
      inputMethod: null,
      jobDescription: '',
      idealCandidateDescription: '',
      uploadedFile: null,
      manualPersona: null,
      pdlQueryLimit: 50,
      selectedEmailTemplateId: null,
    });
  };

  return (
    <div className="flex flex-1 min-h-0 flex-col bg-bg overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 bg-surface-2 border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <SparklesIcon className="w-6 h-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold text-foreground">Talent Intelligence</h1>
            <p className="text-muted">
              AI-powered talent analysis to find ideal candidates from your people data
            </p>
          </div>
        </div>

        {/* Progress Steps - Clickable Breadcrumbs */}
        <div className="flex items-center gap-2 mt-4">
          {/* Step 1: Select Baseline */}
          <button
            onClick={() => navigateToStep('employees')}
            disabled={!canNavigateTo('employees') && workflowStep !== 'employees'}
            className={`flex items-center gap-2 transition-colors ${
              workflowStep === 'employees' 
                ? 'text-primary' 
                : canNavigateTo('employees')
                ? 'text-text hover:text-primary cursor-pointer'
                : 'text-muted-2 cursor-not-allowed'
            }`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              workflowStep === 'employees' 
                ? 'bg-primary text-on-brand' 
                : (config.linkedInUrls.length > 0 || config.selectedBlueprintId)
                ? 'bg-brand/20 text-brand'
                : 'bg-surface-3 text-muted-2'
            }`}>
              {(config.linkedInUrls.length > 0 || config.selectedBlueprintId) && workflowStep !== 'employees' ? '✓' : '1'}
            </div>
            <span className="text-sm font-medium hidden sm:inline">Career Blueprint</span>
          </button>

          <div className={`flex-1 h-px ${(config.linkedInUrls.length > 0 || config.selectedBlueprintId) ? 'bg-brand/30' : 'bg-border'}`} />

          {/* Step 2: Data Source */}
          <button
            onClick={() => navigateToStep('datasource')}
            disabled={!canNavigateTo('datasource') && workflowStep !== 'datasource'}
            className={`flex items-center gap-2 transition-colors ${
              workflowStep === 'datasource'
                ? 'text-primary'
                : canNavigateTo('datasource')
                ? 'text-text hover:text-primary cursor-pointer'
                : 'text-muted-2 cursor-not-allowed'
            }`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              workflowStep === 'datasource'
                ? 'bg-primary text-on-brand'
                : config.selectedConnectorId
                ? 'bg-brand/20 text-brand'
                : 'bg-surface-3 text-muted-2'
            }`}>
              {config.selectedConnectorId && workflowStep !== 'datasource' ? '✓' : '2'}
            </div>
            <span className="text-sm font-medium hidden sm:inline">Candidate Source</span>
          </button>

          <div className={`flex-1 h-px ${config.selectedConnectorId ? 'bg-brand/30' : 'bg-border'}`} />

          {/* Step 3: Define Requirements */}
          <button
            onClick={() => navigateToStep('input')}
            disabled={!canNavigateTo('input') && workflowStep !== 'input'}
            className={`flex items-center gap-2 transition-colors ${
              workflowStep === 'input'
                ? 'text-primary'
                : canNavigateTo('input')
                ? 'text-text hover:text-primary cursor-pointer'
                : 'text-muted-2 cursor-not-allowed'
            }`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              workflowStep === 'input'
                ? 'bg-primary text-on-brand'
                : (config.jobDescription || config.manualPersona)
                ? 'bg-brand/20 text-brand'
                : 'bg-surface-3 text-muted-2'
            }`}>
              {(config.jobDescription || config.manualPersona) && workflowStep !== 'input' ? '✓' : '3'}
            </div>
            <span className="text-sm font-medium hidden sm:inline">Define Requirements</span>
          </button>

          <div className={`flex-1 h-px ${(config.jobDescription || config.manualPersona) ? 'bg-brand/30' : 'bg-border'}`} />

          {/* Step 4: Review & Configure */}
          <button
            onClick={() => navigateToStep('analysis')}
            disabled={!canNavigateTo('analysis') && workflowStep !== 'analysis'}
            className={`flex items-center gap-2 transition-colors ${
              workflowStep === 'analysis'
                ? 'text-primary'
                : canNavigateTo('analysis')
                ? 'text-text hover:text-primary cursor-pointer'
                : 'text-muted-2 cursor-not-allowed'
            }`}
          >
            <div className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              workflowStep === 'analysis'
                ? 'bg-primary text-on-brand'
                : workflowStep === 'processing' || workflowStep === 'results'
                ? 'bg-brand/20 text-brand'
                : 'bg-surface-3 text-muted-2'
            }`}>
              {workflowStep === 'processing' || workflowStep === 'results' ? '✓' : '4'}
            </div>
            <span className="text-sm font-medium hidden sm:inline">Review & Configure</span>
          </button>

          <div className={`flex-1 h-px ${workflowStep === 'processing' || workflowStep === 'results' ? 'bg-brand/30' : 'bg-border'}`} />

          {/* Step 5: AI Analysis */}
          <div className={`flex items-center gap-2 ${workflowStep === 'processing' ? 'text-primary' : 'text-muted-2'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              workflowStep === 'processing' ? 'bg-primary text-on-brand' : 'bg-surface-3'
            }`}>
              5
            </div>
            <span className="text-sm font-medium hidden sm:inline">AI Analysis</span>
          </div>

          <div className="flex-1 h-px bg-border" />

          {/* Step 6: Results */}
          <div className={`flex items-center gap-2 ${workflowStep === 'results' ? 'text-primary' : 'text-muted-2'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              workflowStep === 'results' ? 'bg-primary text-on-brand' : 'bg-surface-3'
            }`}>
              6
            </div>
            <span className="text-sm font-medium hidden sm:inline">Results & Insights</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-6 pb-24">
        {/* Step 1: Build Look-Alike Profile via LinkedIn */}
        {workflowStep === 'employees' && (
          <div className="max-w-4xl mx-auto">
            <EmployeeSelector
              linkedInUrls={config.linkedInUrls}
              onLinkedInUrlsChange={(urls) => setConfig(prev => ({ ...prev, linkedInUrls: urls }))}
              onContinue={handleLinkedInProfilesSelected}
            />
          </div>
        )}

        {/* Step 2: Choose Data Source */}
        {workflowStep === 'datasource' && (
          <div className="max-w-7xl mx-auto">
            <div className="bg-surface rounded-lg border border-border p-6">
              <div className="flex items-start gap-4 mb-6">
                <div className="p-3 bg-primary/10 rounded-lg">
                  <FolderIcon className="w-6 h-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h2 className="text-xl font-semibold text-foreground mb-2">
                    Choose Candidate Source
                  </h2>
                  <p className="text-sm text-muted">
                    Select the source containing applicant resumes. This can be a filesystem
                    connector, HR system, or uploaded files.
                  </p>
                </div>
              </div>

              <DataSourceSelector
                selectedConnectorId={config.selectedConnectorId}
                onConnectorSelect={(id) => setConfig(prev => ({ ...prev, selectedConnectorId: id }))}
                onContinue={handleDataSourceSelected}
                onBack={() => setWorkflowStep('employees')}
              />
            </div>
          </div>
        )}

        {/* Step 2b: Greenhouse Configuration (if Greenhouse selected) */}
        {workflowStep === 'greenhouse-config' && config.selectedConnectorId && (
          <div className="max-w-5xl mx-auto">
            <div className="bg-surface rounded-lg border border-border p-6">
              <GreenhouseQueryConfig
                connectorId={config.selectedConnectorId}
                initialParams={config.greenhouseQueryParams || undefined}
                onParamsChange={(params) => setConfig(prev => ({ ...prev, greenhouseQueryParams: params }))}
                onContinue={() => setWorkflowStep('input')}
                onBack={() => setWorkflowStep('datasource')}
              />
            </div>
          </div>
        )}

        {/* Step 3: Input (Job Description / Persona) */}
        {workflowStep === 'input' && (
          <div className="max-w-7xl mx-auto">
            {!config.inputMethod ? (
              // Method selection with status
              <div className="space-y-6">
                <div className="text-center mb-8">
                  <h2 className="text-xl font-semibold text-foreground mb-2">
                    Define Your Ideal Candidate
                  </h2>
                  <p className="text-muted">
                    Provide requirements through job description and/or ideal persona definition
                  </p>
                </div>

                {/* AI Analysis Preview & Tips */}
                <div className="space-y-4 mb-8">
                  {/* AI Analysis Preview */}
                  <div className="p-4 bg-info/10 rounded-lg border border-info/30">
                    <div className="flex items-start gap-3">
                      <SparklesIcon className="w-5 h-5 text-info flex-shrink-0 mt-0.5" />
                      <div className="text-sm text-foreground">
                        <p className="font-medium mb-1">AI Analysis Preview</p>
                        <p className="text-muted">
                          Our AI agents will extract requirements, search through{' '}
                          <span className="font-semibold text-foreground">thousands of candidates</span>,
                          and provide ranked results with fit scores and sourcing recommendations.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Pro Tips */}
                  <div className="p-4 bg-surface-2 rounded-lg space-y-4">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground mb-2">
                        💡 Pro Tip: Use Both Fields for Best Results
                      </h3>
                      <p className="text-sm text-muted">
                        The <strong>Job Description</strong> provides formal requirements, while the{' '}
                        <strong>Ideal Candidate Description</strong> lets you add personality, culture fit,
                        and other nuances. Our AI uses BOTH to find the perfect matches!
                      </p>
                    </div>
                    
                    <div>
                      <h3 className="text-sm font-semibold text-foreground mb-2">
                        Tips for best results:
                      </h3>
                      <ul className="text-sm text-muted space-y-1">
                        <li>• Include required skills, experience level, and qualifications</li>
                        <li>• Mention specific technologies, tools, and frameworks</li>
                        <li>• Describe company culture and team dynamics</li>
                        <li>• Specify ideal previous companies or industries</li>
                        <li>• Be specific about communication and soft skills</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Job Description Option */}
                  <button
                    onClick={() => setConfig(prev => ({ ...prev, inputMethod: 'job_description' }))}
                    className={`p-5 bg-surface rounded-lg border-2 transition-colors text-left group relative ${
                      config.jobDescription 
                        ? 'border-brand bg-brand/5' 
                        : 'border-border hover:border-primary'
                    }`}
                  >
                    {config.jobDescription && (
                      <div className="absolute top-3 right-3 w-6 h-6 bg-brand rounded-full flex items-center justify-center text-white text-xs">
                        ✓
                      </div>
                    )}
                    <DocumentTextIcon className={`w-10 h-10 mb-3 ${config.jobDescription ? 'text-brand' : 'text-primary'}`} />
                    <h3 className={`text-base font-semibold mb-1.5 group-hover:text-primary ${config.jobDescription ? 'text-brand' : 'text-foreground'}`}>
                      Job Description
                    </h3>
                    <p className="text-muted text-xs leading-relaxed">
                      {config.jobDescription ? 'Job description provided. Click to edit.' : 'Upload or paste a job description for AI analysis.'}
                    </p>
                    <div className="mt-3 text-xs text-primary font-medium">
                      {config.jobDescription ? 'Edit →' : 'Add →'}
                    </div>
                  </button>

                  {/* Manual Persona Option */}
                  <button
                    onClick={() => setConfig(prev => ({ ...prev, inputMethod: 'manual_persona' }))}
                    className={`p-5 bg-surface rounded-lg border-2 transition-colors text-left group relative ${
                      config.manualPersona 
                        ? 'border-brand bg-brand/5' 
                        : 'border-border hover:border-primary'
                    }`}
                  >
                    {config.manualPersona && (
                      <div className="absolute top-3 right-3 w-6 h-6 bg-brand rounded-full flex items-center justify-center text-white text-xs">
                        ✓
                      </div>
                    )}
                    <UserGroupIcon className={`w-10 h-10 mb-3 ${config.manualPersona ? 'text-brand' : 'text-primary'}`} />
                    <h3 className={`text-base font-semibold mb-1.5 group-hover:text-primary ${config.manualPersona ? 'text-brand' : 'text-foreground'}`}>
                      Ideal Persona
                    </h3>
                    <p className="text-muted text-xs leading-relaxed">
                      {config.manualPersona ? 'Ideal persona defined. Click to edit.' : 'Manually specify skills, experience, and criteria.'}
                    </p>
                    <div className="mt-3 text-xs text-primary font-medium">
                      {config.manualPersona ? 'Edit →' : 'Define →'}
                    </div>
                  </button>
                </div>

                {/* Continue button (shown when at least one method is complete) */}
                {(config.jobDescription || config.manualPersona) && (
                  <div className="flex justify-end gap-3 mt-6">
                    <button
                      onClick={() => setWorkflowStep('datasource')}
                      className="px-5 py-2.5 rounded-lg border border-border text-text hover:bg-surface-2 transition-colors text-sm font-medium"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => setWorkflowStep('analysis')}
                      className="px-6 py-2.5 rounded-lg bg-brand text-on-brand hover:bg-brand-hover transition-colors text-sm font-medium"
                    >
                      Continue to Analysis
                    </button>
                  </div>
                )}
              </div>
            ) : config.inputMethod === 'job_description' ? (
              <JobDescriptionUpload
                onSubmit={handleJobDescriptionSubmit}
                onBack={() => setConfig(prev => ({ ...prev, inputMethod: null }))}
                initialJobDescription={config.jobDescription}
                initialIdealCandidateDescription={config.idealCandidateDescription}
                initialUploadedFile={config.uploadedFile}
                onFileUpload={(fileInfo) => setConfig(prev => ({ ...prev, uploadedFile: fileInfo }))}
              />
            ) : (
              <PersonaDefinitionForm
                onSubmit={handlePersonaSubmit}
                onBack={() => setConfig(prev => ({ ...prev, inputMethod: null }))}
              />
            )}
          </div>
        )}

        {/* Step 4: Analysis Configuration & Review */}
        {workflowStep === 'analysis' && (
          <AnalysisSummary
            linkedInProfileCount={config.linkedInUrls.length}
            connectorName="Filesystem: Resume Uploads" 
            jobDescription={config.jobDescription}
            idealCandidateDescription={config.idealCandidateDescription}
            pdlQueryLimit={config.pdlQueryLimit}
            selectedEmailTemplateId={config.selectedEmailTemplateId}
            onPdlQueryLimitChange={(limit) => setConfig(prev => ({ ...prev, pdlQueryLimit: limit }))}
            onEmailTemplateChange={(templateId) => setConfig(prev => ({ ...prev, selectedEmailTemplateId: templateId }))}
            onRunAnalysis={handleRunAnalysis}
            onBack={() => setWorkflowStep('input')}
          />
        )}

        {/* Step 5: Processing */}
        {workflowStep === 'processing' && analysisId && (
          <div className="max-w-4xl mx-auto">
            <AnalysisProgress
              analysisId={analysisId}
              onComplete={handleAnalysisComplete}
            />
          </div>
        )}

        {/* Step 3: Results */}
        {workflowStep === 'results' && analysisResults && (
          <div className="space-y-6">
            <PersonaSummary
              persona={analysisResults.ideal_persona}
              insights={analysisResults.insights_report}
              onStartOver={handleStartOver}
            />
            <CandidateResults
              topOverall={analysisResults.top_overall || []}
              applicants={analysisResults.applicant_results || []}
              marketCandidates={analysisResults.market_results || []}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default TalentIntelligencePage;

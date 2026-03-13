/**
 * SOW Automation Page - Interactive SOW Generation from Meeting Transcripts
 * 
 * Features:
 * - Upload template (DOCX) and transcript (JSON)
 * - AI-powered field extraction with confidence scores
 * - Interactive review with dialogue and alternatives
 * - Final document generation
 * 
 * Uses Eliza Forge Design System components
 */
import React, { useState, useRef, useEffect } from 'react';
import { Layout } from '../../components/layout/Layout';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Input,
  Spinner,
  Modal,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalBody,
  ModalFooter,
  PageHeader,
  PageContent,
  Textarea,
} from '../../components/ui';
import {
  CloudArrowUpIcon,
  DocumentTextIcon,
  SparklesIcon,
  CheckCircleIcon,
  XCircleIcon,
  PencilSquareIcon,
  ChatBubbleLeftRightIcon,
  ArrowPathIcon,
  DocumentArrowDownIcon,
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  ClipboardDocumentIcon,
} from '@heroicons/react/24/outline';

import { AXIOS_INSTANCE } from '../../services/api-client';

// Use the platform's API client - SOW endpoints are at /v1/sow
const SOW_API_BASE = '/v1/sow';

// Types
interface Citation {
  speaker: string;
  text: string;
  utterance_id?: string;
  timestamp?: string;
}

interface ExtractedAnswer {
  tag: string;
  value: string | null;
  value_rendered: string | null;
  confidence: number;
  reasoning: string | null;
  citations: Citation[];
  followup_question: string | null;
  status: 'pending' | 'confirmed' | 'rejected' | 'edited';
}

interface FieldDefinition {
  tag: string;
  question: string;
  source: string;
}

interface ExtractionResult {
  session_id: string;
  fields: FieldDefinition[];
  answers: ExtractedAnswer[];
  meeting_title: string | null;
  meeting_date: string | null;
}

interface AlternativeAnswer {
  answer: string;
  confidence: number;
  reasoning: string;
}

// File upload state
type UploadStatus = 'idle' | 'uploading' | 'extracting' | 'done' | 'error';

export default function SowAutomationPage() {
  // File upload state
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  // Extraction state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [answers, setAnswers] = useState<ExtractedAnswer[]>([]);
  const [meetingTitle, setMeetingTitle] = useState<string | null>(null);
  
  // Review state
  const [expandedField, setExpandedField] = useState<string | null>(null);
  const [dialogueField, setDialogueField] = useState<string | null>(null);
  const [dialogueHistory, setDialogueHistory] = useState<Array<{role: string; content: string}>>([]);
  const [dialogueInput, setDialogueInput] = useState('');
  const [dialogueLoading, setDialogueLoading] = useState(false);
  const [alternatives, setAlternatives] = useState<AlternativeAnswer[]>([]);
  const [alternativesLoading, setAlternativesLoading] = useState(false);
  
  // Generation state
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  
  const templateInputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);
  const dialogueEndRef = useRef<HTMLDivElement>(null);

  // Scroll dialogue to bottom
  useEffect(() => {
    dialogueEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [dialogueHistory]);

  // Handle file selection
  const handleTemplateSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.name.endsWith('.docx')) {
      setTemplateFile(file);
      setUploadError(null);
    } else {
      setUploadError('Please select a .docx file for the template');
    }
  };

  const handleTranscriptSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && (file.name.endsWith('.json') || file.name.endsWith('.txt'))) {
      setTranscriptFile(file);
      setUploadError(null);
    } else {
      setUploadError('Please select a .json or .txt file for the transcript');
    }
  };

  // Start extraction
  const handleExtract = async () => {
    if (!templateFile || !transcriptFile) return;
    
    console.log('=== SOW EXTRACTION STARTING ===');
    console.log('Template:', templateFile.name, templateFile.size, 'bytes');
    console.log('Transcript:', transcriptFile.name, transcriptFile.size, 'bytes');
    
    setUploadStatus('uploading');
    setUploadError(null);
    
    const formData = new FormData();
    formData.append('template', templateFile);
    formData.append('transcript', transcriptFile);
    
    try {
      setUploadStatus('extracting');
      console.log('Sending request to:', `${SOW_API_BASE}/extract`);
      
      const response = await AXIOS_INSTANCE.post(`${SOW_API_BASE}/extract`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      console.log('Response status:', response.status, response.statusText);
      
      const result: ExtractionResult = response.data;
      
      console.log('=== EXTRACTION RESULT ===');
      console.log('Session ID:', result.session_id);
      console.log('Meeting Title:', result.meeting_title);
      console.log('Fields count:', result.fields?.length ?? 0);
      console.log('Answers count:', result.answers?.length ?? 0);
      
      setSessionId(result.session_id);
      setFields(result.fields || []);
      setAnswers(result.answers || []);
      setMeetingTitle(result.meeting_title);
      setUploadStatus('done');
      
    } catch (err) {
      console.error('Extraction failed:', err);
      setUploadError(err instanceof Error ? err.message : 'Extraction failed');
      setUploadStatus('error');
    }
  };

  // Update field status
  const updateFieldStatus = async (tag: string, value: string, status: ExtractedAnswer['status']) => {
    if (!sessionId) return;
    
    try {
      await AXIOS_INSTANCE.post(`${SOW_API_BASE}/update-field`, {
        session_id: sessionId, tag, value, status
      });
      
      setAnswers((prev: ExtractedAnswer[]) => prev.map((a: ExtractedAnswer) => 
        a.tag === tag ? { ...a, value_rendered: value, status } : a
      ));
    } catch (err) {
      console.error('Failed to update field:', err);
    }
  };

  // Dialogue message type
  type DialogueMessage = { role: string; content: string };

  // Start dialogue for a field
  const openDialogue = (tag: string) => {
    setDialogueField(tag);
    setDialogueHistory([]);
    setDialogueInput('');
    setAlternatives([]);
  };

  // Send dialogue message
  const sendDialogueMessage = async () => {
    if (!dialogueInput.trim() || !dialogueField || !sessionId) return;
    
    const userMessage = dialogueInput.trim();
    setDialogueInput('');
    setDialogueHistory((prev: DialogueMessage[]) => [...prev, { role: 'user', content: userMessage }]);
    setDialogueLoading(true);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${SOW_API_BASE}/dialogue`, {
        session_id: sessionId,
        tag: dialogueField,
        message: userMessage,
        conversation_history: dialogueHistory,
      });
      
      setDialogueHistory((prev: DialogueMessage[]) => [...prev, { role: 'assistant', content: response.data.response }]);
    } catch (err) {
      console.error('Dialogue error:', err);
      setDialogueHistory((prev: DialogueMessage[]) => [...prev, { 
        role: 'assistant', 
        content: 'Sorry, I encountered an error. Please try again.' 
      }]);
    } finally {
      setDialogueLoading(false);
    }
  };

  // Get alternatives for a field
  const fetchAlternatives = async (tag: string) => {
    if (!sessionId) return;
    
    setAlternativesLoading(true);
    setAlternatives([]);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${SOW_API_BASE}/alternatives`, {
        session_id: sessionId, tag
      });
      setAlternatives(response.data.alternatives || []);
    } catch (err) {
      console.error('Alternatives error:', err);
    } finally {
      setAlternativesLoading(false);
    }
  };

  // Generate final document
  const handleGenerate = async () => {
    if (!sessionId) return;
    
    setGenerating(true);
    
    try {
      const response = await AXIOS_INSTANCE.post(`${SOW_API_BASE}/generate/${sessionId}`);
      // Download URL is relative, combine with base URL
      const baseUrl = process.env.REACT_APP_API_URL || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001');
      // Include auth token in download URL for browser downloads
      const token = localStorage.getItem('auth_token');
      const downloadPath = response.data.download_url.replace('/v1/sow', '');
      const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
      setDownloadUrl(`${baseUrl}${SOW_API_BASE}${downloadPath}${tokenParam}`);
    } catch (err) {
      console.error('Generation error:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Reset to start over
  const handleReset = () => {
    setTemplateFile(null);
    setTranscriptFile(null);
    setUploadStatus('idle');
    setUploadError(null);
    setSessionId(null);
    setFields([]);
    setAnswers([]);
    setMeetingTitle(null);
    setDownloadUrl(null);
    setExpandedField(null);
    setDialogueField(null);
  };

  // Calculate progress
  const confirmedCount = answers.filter((a: ExtractedAnswer) => a.status === 'confirmed' || a.status === 'edited').length;
  const lowConfidenceCount = answers.filter((a: ExtractedAnswer) => a.confidence < 0.7 && a.status === 'pending').length;
  const allConfirmed = answers.length > 0 && answers.every((a: ExtractedAnswer) => a.status !== 'pending');

  // Get confidence badge variant
  const getConfidenceBadgeVariant = (confidence: number): 'success' | 'warning' | 'danger' => {
    if (confidence >= 0.8) return 'success';
    if (confidence >= 0.6) return 'warning';
    return 'danger';
  };

  // Find field question
  const getFieldQuestion = (tag: string): string => {
    return fields.find((f: FieldDefinition) => f.tag === tag)?.question || tag;
  };

  return (
    <Layout
      pageTitle="SOW Automation"
      breadcrumbs={[
        { label: 'AI Assistant' },
        { label: 'SOW Automation' },
      ]}
    >
      <div className="h-full overflow-y-auto bg-gray-50 dark:bg-dark-bg">
        <PageHeader
          title="SOW Automation"
          description="Extract information from meeting transcripts and generate Statement of Work documents."
          actions={
            sessionId ? (
              <div className="flex items-center gap-4">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {confirmedCount}/{answers.length} fields confirmed
                  {lowConfidenceCount > 0 && (
                    <span className="ml-2 text-amber-600 dark:text-amber-400">
                      ({lowConfidenceCount} need review)
                    </span>
                  )}
                </span>
                <Button variant="secondary" size="sm" onClick={handleReset}>
                  <ArrowPathIcon className="h-4 w-4" />
                  Start Over
                </Button>
              </div>
            ) : undefined
          }
        />

        <PageContent>
          <div className="flex flex-col gap-6 pb-12">
            {/* Upload Section - Only show if no session */}
            {!sessionId && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Template Upload */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">1. Template (DOCX)</CardTitle>
                    <CardDescription>Upload your SOW template with field markers</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div
                      onClick={() => templateInputRef.current?.click()}
                      className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-colors ${
                        templateFile
                          ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-900/20'
                          : 'border-gray-200 dark:border-dark-border hover:border-eliza-red hover:bg-gray-50 dark:hover:bg-dark-surface-2'
                      }`}
                    >
                      {templateFile ? (
                        <div className="flex items-center justify-center gap-3">
                          <DocumentTextIcon className="h-8 w-8 text-emerald-500" />
                          <div className="text-left">
                            <p className="font-medium text-charcoal dark:text-gray-100">{templateFile.name}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{(templateFile.size / 1024).toFixed(1)} KB</p>
                          </div>
                          <CheckCircleIcon className="h-5 w-5 text-emerald-500" />
                        </div>
                      ) : (
                        <>
                          <CloudArrowUpIcon className="h-10 w-10 text-eliza-red mx-auto mb-2" />
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            Click to upload your SOW template
                          </p>
                          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                            DOCX with [[question]]{'{{TAG}}'} markers
                          </p>
                        </>
                      )}
                    </div>
                    <input
                      ref={templateInputRef}
                      type="file"
                      accept=".docx"
                      onChange={handleTemplateSelect}
                      className="hidden"
                    />
                  </CardContent>
                </Card>

                {/* Transcript Upload */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">2. Transcript (JSON/TXT)</CardTitle>
                    <CardDescription>Upload your meeting transcript</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div
                      onClick={() => transcriptInputRef.current?.click()}
                      className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-colors ${
                        transcriptFile
                          ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-900/20'
                          : 'border-gray-200 dark:border-dark-border hover:border-eliza-red hover:bg-gray-50 dark:hover:bg-dark-surface-2'
                      }`}
                    >
                      {transcriptFile ? (
                        <div className="flex items-center justify-center gap-3">
                          <ClipboardDocumentIcon className="h-8 w-8 text-emerald-500" />
                          <div className="text-left">
                            <p className="font-medium text-charcoal dark:text-gray-100">{transcriptFile.name}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{(transcriptFile.size / 1024).toFixed(1)} KB</p>
                          </div>
                          <CheckCircleIcon className="h-5 w-5 text-emerald-500" />
                        </div>
                      ) : (
                        <>
                          <CloudArrowUpIcon className="h-10 w-10 text-eliza-red mx-auto mb-2" />
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            Click to upload meeting transcript
                          </p>
                          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                            Fathom JSON or plain text format
                          </p>
                        </>
                      )}
                    </div>
                    <input
                      ref={transcriptInputRef}
                      type="file"
                      accept=".json,.txt"
                      onChange={handleTranscriptSelect}
                      className="hidden"
                    />
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Error Display */}
            {uploadError && (
              <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-900/20">
                <CardContent className="p-4 flex items-start gap-3">
                  <ExclamationTriangleIcon className="h-5 w-5 text-rose-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-rose-800 dark:text-rose-200">Error</p>
                    <p className="text-sm text-rose-700 dark:text-rose-300">{uploadError}</p>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Extract Button */}
            {!sessionId && templateFile && transcriptFile && (
              <div className="flex justify-center">
                <Button
                  variant="brand"
                  size="lg"
                  onClick={handleExtract}
                  disabled={uploadStatus === 'uploading' || uploadStatus === 'extracting'}
                >
                  {uploadStatus === 'extracting' ? (
                    <>
                      <Spinner size="sm" />
                      Extracting fields...
                    </>
                  ) : (
                    <>
                      <SparklesIcon className="h-5 w-5" />
                      Extract SOW Fields
                    </>
                  )}
                </Button>
              </div>
            )}

            {/* Meeting Info */}
            {meetingTitle && (
              <Card>
                <CardContent className="p-4">
                  <p className="text-sm text-gray-500 dark:text-gray-400">Meeting:</p>
                  <p className="font-medium text-charcoal dark:text-gray-100">{meetingTitle}</p>
                </CardContent>
              </Card>
            )}

            {/* Extracted Fields Grid */}
            {answers.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {answers.map((answer: ExtractedAnswer) => (
                  <FieldCard
                    key={answer.tag}
                    answer={answer}
                    question={getFieldQuestion(answer.tag)}
                    isExpanded={expandedField === answer.tag}
                    onToggleExpand={() => setExpandedField(expandedField === answer.tag ? null : answer.tag)}
                    onConfirm={(value: string) => updateFieldStatus(answer.tag, value, 'confirmed')}
                    onEdit={(value: string) => updateFieldStatus(answer.tag, value, 'edited')}
                    onReject={() => updateFieldStatus(answer.tag, '', 'rejected')}
                    onOpenDialogue={() => openDialogue(answer.tag)}
                    getConfidenceBadgeVariant={getConfidenceBadgeVariant}
                  />
                ))}
              </div>
            )}

            {/* Generate Button */}
            {answers.length > 0 && (
              <div className="flex flex-col items-center gap-4 py-6">
                {!allConfirmed && (
                  <p className="text-sm text-amber-600 dark:text-amber-400">
                    Please review all fields before generating the document.
                  </p>
                )}
                <div className="flex items-center gap-4">
                  <Button
                    variant="brand"
                    size="lg"
                    onClick={handleGenerate}
                    disabled={generating || !allConfirmed}
                  >
                    {generating ? (
                      <>
                        <Spinner size="sm" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <DocumentArrowDownIcon className="h-5 w-5" />
                        Generate SOW Document
                      </>
                    )}
                  </Button>
                  {downloadUrl && (
                    <Button
                      variant="default"
                      size="lg"
                      asChild
                    >
                      <a href={downloadUrl} download>
                        <DocumentArrowDownIcon className="h-5 w-5" />
                        Download
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            )}

            {/* Dialogue Modal */}
            <DialogueModal
              isOpen={!!dialogueField}
              onClose={() => setDialogueField(null)}
              fieldTag={dialogueField || ''}
              fieldQuestion={dialogueField ? getFieldQuestion(dialogueField) : ''}
              currentAnswer={answers.find((a: ExtractedAnswer) => a.tag === dialogueField)}
              dialogueHistory={dialogueHistory}
              dialogueInput={dialogueInput}
              onInputChange={setDialogueInput}
              onSend={sendDialogueMessage}
              isLoading={dialogueLoading}
              alternatives={alternatives}
              alternativesLoading={alternativesLoading}
              onFetchAlternatives={() => dialogueField && fetchAlternatives(dialogueField)}
              onSelectAlternative={(alt) => {
                if (dialogueField) {
                  updateFieldStatus(dialogueField, alt.answer, 'edited');
                  setDialogueField(null);
                }
              }}
              onAcceptSuggested={(value) => {
                if (dialogueField) {
                  updateFieldStatus(dialogueField, value, 'edited');
                  setDialogueField(null);
                }
              }}
              dialogueEndRef={dialogueEndRef}
            />
          </div>
        </PageContent>
      </div>
    </Layout>
  );
}

// Field Card Component
interface FieldCardProps {
  answer: ExtractedAnswer;
  question: string;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onConfirm: (value: string) => void;
  onEdit: (value: string) => void;
  onReject: () => void;
  onOpenDialogue: () => void;
  getConfidenceBadgeVariant: (confidence: number) => 'success' | 'warning' | 'danger';
}

function FieldCard({
  answer,
  question,
  isExpanded,
  onToggleExpand,
  onConfirm,
  onEdit,
  onReject,
  onOpenDialogue,
  getConfidenceBadgeVariant,
}: FieldCardProps) {
  const [editValue, setEditValue] = useState(answer.value_rendered || '');
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    setEditValue(answer.value_rendered || '');
  }, [answer.value_rendered]);

  const handleSaveEdit = () => {
    onEdit(editValue);
    setIsEditing(false);
  };

  const statusBadge = () => {
    switch (answer.status) {
      case 'confirmed':
        return (
          <Badge variant="success">
            <CheckCircleIcon className="h-3 w-3 mr-1" />
            Confirmed
          </Badge>
        );
      case 'edited':
        return (
          <Badge variant="info">
            <PencilSquareIcon className="h-3 w-3 mr-1" />
            Edited
          </Badge>
        );
      case 'rejected':
        return (
          <Badge variant="danger">
            <XCircleIcon className="h-3 w-3 mr-1" />
            Rejected
          </Badge>
        );
      default:
        return (
          <Badge variant={getConfidenceBadgeVariant(answer.confidence)}>
            {Math.round(answer.confidence * 100)}% confident
          </Badge>
        );
    }
  };

  return (
    <Card className={
      answer.status === 'pending' && answer.confidence < 0.7
        ? 'border-amber-200 dark:border-amber-800'
        : ''
    }>
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-dark-surface-2 px-2 py-0.5 rounded">
                {answer.tag}
              </span>
              {statusBadge()}
            </div>
            <p className="text-sm font-medium text-charcoal dark:text-gray-100">{question}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggleExpand}
          >
            {isExpanded ? (
              <ChevronUpIcon className="h-5 w-5" />
            ) : (
              <ChevronDownIcon className="h-5 w-5" />
            )}
          </Button>
        </div>

        {/* Answer Preview/Edit */}
        {isEditing ? (
          <div className="space-y-3">
            <Textarea
              value={editValue}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditValue(e.target.value)}
              rows={3}
            />
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={handleSaveEdit}>
                Save
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setIsEditing(false);
                  setEditValue(answer.value_rendered || '');
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div
            className="text-sm text-charcoal dark:text-gray-100 bg-gray-50 dark:bg-dark-surface-2 rounded-xl p-3 mb-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-dark-surface transition"
            onClick={() => answer.status === 'pending' && setIsEditing(true)}
          >
            {answer.value_rendered || <span className="text-gray-400 dark:text-gray-500 italic">Not extracted</span>}
          </div>
        )}

        {/* Expanded Content */}
        {isExpanded && !isEditing && (
          <div className="space-y-3 mt-3 pt-3 border-t border-gray-200 dark:border-dark-border">
            {/* Reasoning */}
            {answer.reasoning && (
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">AI Reasoning:</p>
                <p className="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-dark-surface-2 rounded p-2">
                  {answer.reasoning}
                </p>
              </div>
            )}

            {/* Citations */}
            {answer.citations && answer.citations.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                  Citations ({answer.citations.length}):
                </p>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {answer.citations.slice(0, 3).map((cite, idx) => (
                    <div key={idx} className="text-xs bg-gray-50 dark:bg-dark-surface-2 rounded p-2">
                      <span className="font-medium text-eliza-red">{cite.speaker}:</span>{' '}
                      <span className="text-gray-600 dark:text-gray-300">{cite.text}</span>
                    </div>
                  ))}
                  {answer.citations.length > 3 && (
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      +{answer.citations.length - 3} more citations
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        {answer.status === 'pending' && !isEditing && (
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-200 dark:border-dark-border">
            <Button
              size="sm"
              onClick={() => onConfirm(answer.value_rendered || '')}
            >
              <CheckCircleIcon className="h-4 w-4" />
              Confirm
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsEditing(true)}
            >
              <PencilSquareIcon className="h-4 w-4" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenDialogue}
            >
              <ChatBubbleLeftRightIcon className="h-4 w-4" />
              Discuss
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={onReject}
              className="ml-auto"
            >
              <XCircleIcon className="h-4 w-4" />
              Reject
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Dialogue Modal Component
interface DialogueModalProps {
  isOpen: boolean;
  onClose: () => void;
  fieldTag: string;
  fieldQuestion: string;
  currentAnswer: ExtractedAnswer | undefined;
  dialogueHistory: Array<{role: string; content: string}>;
  dialogueInput: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
  alternatives: AlternativeAnswer[];
  alternativesLoading: boolean;
  onFetchAlternatives: () => void;
  onSelectAlternative: (alt: AlternativeAnswer) => void;
  onAcceptSuggested: (value: string) => void;
  dialogueEndRef: React.RefObject<HTMLDivElement>;
}

function DialogueModal({
  isOpen,
  onClose,
  fieldTag,
  fieldQuestion,
  currentAnswer,
  dialogueHistory,
  dialogueInput,
  onInputChange,
  onSend,
  isLoading,
  alternatives,
  alternativesLoading,
  onFetchAlternatives,
  onSelectAlternative,
  onAcceptSuggested,
  dialogueEndRef,
}: DialogueModalProps) {
  // Extract suggested answer from last assistant message
  const lastAssistantMessage = [...dialogueHistory].reverse().find(m => m.role === 'assistant');
  const suggestedAnswer = lastAssistantMessage?.content.match(/SUGGESTED ANSWER:\s*(.+?)(?:\n|$)/i)?.[1];

  return (
    <Modal open={isOpen} onClose={onClose}>
      <ModalContent size="full">
        <ModalHeader>
          <ModalTitle className="flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="h-5 w-5 text-eliza-red" />
            Interactive Review: {fieldTag}
          </ModalTitle>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{fieldQuestion}</p>
        </ModalHeader>

        <ModalBody className="space-y-4">
          {/* Current Answer */}
          <div className="p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-xl">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Current Answer:</p>
            <p className="text-sm text-charcoal dark:text-gray-100">
              {currentAnswer?.value_rendered || 'Not extracted'}
            </p>
          </div>

          {/* Dialogue History */}
          <div className="max-h-80 overflow-y-auto space-y-4 p-1">
            {dialogueHistory.length === 0 && (
              <div className="text-center py-8">
                <ChatBubbleLeftRightIcon className="h-10 w-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Ask questions to refine this answer. Try:
                </p>
                <ul className="text-xs text-gray-400 dark:text-gray-500 mt-2 space-y-1">
                  <li>"What exactly did they say about this?"</li>
                  <li>"Why did you extract this value?"</li>
                  <li>"Can you suggest a better answer?"</li>
                </ul>
              </div>
            )}
            {dialogueHistory.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-2 ${
                    msg.role === 'user'
                      ? 'bg-eliza-red/10 text-charcoal dark:text-gray-100'
                      : 'bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border text-charcoal dark:text-gray-100'
                  }`}
                >
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {msg.role === 'user' ? 'You' : 'AI Assistant'}
                  </p>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white dark:bg-dark-surface border border-gray-200 dark:border-dark-border rounded-2xl px-4 py-3">
                  <Spinner size="sm" />
                </div>
              </div>
            )}
            <div ref={dialogueEndRef} />
          </div>

          {/* Suggested Answer Banner */}
          {suggestedAnswer && (
            <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl">
              <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400 mb-1">Suggested Answer:</p>
              <p className="text-sm text-emerald-800 dark:text-emerald-300">{suggestedAnswer}</p>
              <Button
                size="sm"
                className="mt-2"
                onClick={() => onAcceptSuggested(suggestedAnswer)}
              >
                Accept This Answer
              </Button>
            </div>
          )}

          {/* Alternatives Section */}
          <div className="pt-3 border-t border-gray-200 dark:border-dark-border">
            <Button
              variant="ghost"
              size="sm"
              onClick={onFetchAlternatives}
              disabled={alternativesLoading}
            >
              {alternativesLoading ? (
                <Spinner size="sm" />
              ) : (
                <ArrowPathIcon className="h-4 w-4" />
              )}
              Get Alternative Suggestions
            </Button>
            {alternatives.length > 0 && (
              <div className="mt-3 space-y-2">
                {alternatives.map((alt, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-3 p-3 bg-gray-50 dark:bg-dark-surface-2 rounded-xl border border-gray-200 dark:border-dark-border hover:border-eliza-red/30 cursor-pointer transition"
                    onClick={() => onSelectAlternative(alt)}
                  >
                    <div className="flex-1">
                      <p className="text-sm text-charcoal dark:text-gray-100">{alt.answer}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{alt.reasoning}</p>
                    </div>
                    <Badge variant="secondary">
                      {Math.round(alt.confidence * 100)}%
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        </ModalBody>

        <ModalFooter className="border-t border-gray-200 dark:border-dark-border pt-4">
          <div className="flex items-center gap-3 w-full">
            <Input
              value={dialogueInput}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onInputChange(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent) => e.key === 'Enter' && !e.shiftKey && onSend()}
              placeholder="Ask a question or provide guidance..."
              className="flex-1"
            />
            <Button
              onClick={onSend}
              disabled={!dialogueInput.trim() || isLoading}
            >
              Send
            </Button>
          </div>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}

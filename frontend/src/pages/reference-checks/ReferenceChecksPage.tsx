/**
 * Reference Checks Page
 * 
 * Main page for managing reference check requests, templates, personas, and calls.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  PhoneIcon,
  UserGroupIcon,
  DocumentTextIcon,
  SpeakerWaveIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  PlayIcon,
  PlusIcon,
  Cog6ToothIcon,
  BeakerIcon,
} from '@heroicons/react/24/outline';
import { AXIOS_INSTANCE } from '../../services/api-client';

// Types
interface ReferenceCheckRequest {
  id: number;
  customer_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_phone?: string;
  job_id?: string;
  job_title?: string;
  status: string;
  max_references: number;
  reference_count: number;
  created_at: string;
  updated_at: string;
}

interface Reference {
  id: number;
  request_id: number;
  full_name: string;
  phone_number: string;
  relationship?: string;
  company?: string;
  title?: string;
  email?: string;
  status: string;
  created_at: string;
}

interface CallTemplate {
  id: number;
  name: string;
  description?: string;
  is_default: boolean;
  is_active: boolean;
  question_count: number;
  questions: TemplateQuestion[];
  created_at: string;
}

interface TemplateQuestion {
  id: number;
  question_text: string;
  question_type: string;
  priority: string;
  order_index: number;
  follow_up_enabled: boolean;
  max_follow_ups: number;
  expected_answer_type?: string;
}

interface VoicePersona {
  id: number;
  name: string;
  description?: string;
  voice_model: string;
  speaking_rate: number;
  tone: string;
  personality_traits?: Record<string, any>;
  is_default: boolean;
  created_at: string;
}

interface ScheduledCall {
  id: number;
  reference_id: number;
  reference_name: string;
  template_id?: number;
  template_name?: string;
  persona_id?: number;
  persona_name?: string;
  scheduled_at: string;
  status: string;
  reminder_24h_sent: boolean;
  reminder_2h_sent: boolean;
  reminder_15m_sent: boolean;
  created_at: string;
}

interface Call {
  id: number;
  scheduled_call_id?: number;
  reference_id?: number;
  reference_name?: string;
  call_type: string;
  call_status?: string;
  consent_obtained: boolean;
  started_at?: string;
  ended_at?: string;
  duration_seconds?: number;
  is_complete: boolean;
  has_recording: boolean;
  has_transcript: boolean;
  has_summary: boolean;
  created_at: string;
}

// Tab types
type TabType = 'requests' | 'templates' | 'personas' | 'scheduled' | 'calls' | 'playground' | 'settings';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  references_requested: 'bg-blue-100 text-blue-800',
  references_submitted: 'bg-purple-100 text-purple-800',
  calls_scheduled: 'bg-indigo-100 text-indigo-800',
  in_progress: 'bg-orange-100 text-orange-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-gray-100 text-gray-800',
  scheduled: 'bg-blue-100 text-blue-800',
  initiated: 'bg-orange-100 text-orange-800',
  voicemail_left: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
};

export default function ReferenceChecksPage() {
  const [activeTab, setActiveTab] = useState<TabType>('requests');
  const [loading, setLoading] = useState(false);
  
  // Data states
  const [requests, setRequests] = useState<ReferenceCheckRequest[]>([]);
  const [templates, setTemplates] = useState<CallTemplate[]>([]);
  const [personas, setPersonas] = useState<VoicePersona[]>([]);
  const [scheduledCalls, setScheduledCalls] = useState<ScheduledCall[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  
  // Modal states
  const [showCreateRequest, setShowCreateRequest] = useState(false);
  const [showCreateTemplate, setShowCreateTemplate] = useState(false);
  const [showCreatePersona, setShowCreatePersona] = useState(false);
  const [showScheduleCall, setShowScheduleCall] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<ReferenceCheckRequest | null>(null);
  const [selectedReference, setSelectedReference] = useState<Reference | null>(null);
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);

  // Load data based on active tab
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 'requests':
          const requestsRes = await AXIOS_INSTANCE.get('/api/v1/reference-checks/requests');
          setRequests(requestsRes.data);
          break;
        case 'templates':
          const templatesRes = await AXIOS_INSTANCE.get('/api/v1/reference-checks/templates');
          setTemplates(templatesRes.data);
          break;
        case 'personas':
          const personasRes = await AXIOS_INSTANCE.get('/api/v1/reference-checks/personas');
          setPersonas(personasRes.data);
          break;
        case 'scheduled':
          const scheduledRes = await AXIOS_INSTANCE.get('/api/v1/reference-checks/calls/scheduled');
          setScheduledCalls(scheduledRes.data);
          break;
        case 'calls':
          const callsRes = await AXIOS_INSTANCE.get('/api/v1/reference-checks/calls');
          setCalls(callsRes.data);
          break;
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const tabs = [
    { id: 'requests' as TabType, name: 'Requests', icon: UserGroupIcon },
    { id: 'templates' as TabType, name: 'Templates', icon: DocumentTextIcon },
    { id: 'personas' as TabType, name: 'Personas', icon: SpeakerWaveIcon },
    { id: 'scheduled' as TabType, name: 'Scheduled', icon: ClockIcon },
    { id: 'calls' as TabType, name: 'Calls', icon: PhoneIcon },
    { id: 'playground' as TabType, name: 'Playground', icon: BeakerIcon },
    { id: 'settings' as TabType, name: 'Settings', icon: Cog6ToothIcon },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Reference Checks</h1>
                <p className="mt-1 text-sm text-gray-500">
                  AI-powered voice reference checks with automated scheduling and synthesis
                </p>
              </div>
              <div className="flex items-center gap-3">
                {activeTab === 'requests' && (
                  <button
                    onClick={() => setShowCreateRequest(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors"
                  >
                    <PlusIcon className="w-5 h-5" />
                    New Request
                  </button>
                )}
                {activeTab === 'templates' && (
                  <button
                    onClick={() => setShowCreateTemplate(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors"
                  >
                    <PlusIcon className="w-5 h-5" />
                    New Template
                  </button>
                )}
                {activeTab === 'personas' && (
                  <button
                    onClick={() => setShowCreatePersona(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors"
                  >
                    <PlusIcon className="w-5 h-5" />
                    New Persona
                  </button>
                )}
              </div>
            </div>
          </div>
          
          {/* Tabs */}
          <div className="flex space-x-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-t-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-brand text-white'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                {tab.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
          </div>
        ) : (
          <>
            {activeTab === 'requests' && (
              <RequestsTab
                requests={requests}
                onSelect={setSelectedRequest}
                onRefresh={loadData}
              />
            )}
            {activeTab === 'templates' && (
              <TemplatesTab
                templates={templates}
                onRefresh={loadData}
              />
            )}
            {activeTab === 'personas' && (
              <PersonasTab
                personas={personas}
                onRefresh={loadData}
              />
            )}
            {activeTab === 'scheduled' && (
              <ScheduledCallsTab
                scheduledCalls={scheduledCalls}
                onRefresh={loadData}
              />
            )}
            {activeTab === 'calls' && (
              <CallsTab
                calls={calls}
                onSelect={setSelectedCall}
                onRefresh={loadData}
              />
            )}
            {activeTab === 'playground' && (
              <PlaygroundTab
                templates={templates}
                personas={personas}
              />
            )}
            {activeTab === 'settings' && (
              <SettingsTab />
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {showCreateRequest && (
        <CreateRequestModal
          onClose={() => setShowCreateRequest(false)}
          onCreated={() => {
            setShowCreateRequest(false);
            loadData();
          }}
        />
      )}
      {showCreateTemplate && (
        <CreateTemplateModal
          onClose={() => setShowCreateTemplate(false)}
          onCreated={() => {
            setShowCreateTemplate(false);
            loadData();
          }}
        />
      )}
      {showCreatePersona && (
        <CreatePersonaModal
          onClose={() => setShowCreatePersona(false)}
          onCreated={() => {
            setShowCreatePersona(false);
            loadData();
          }}
        />
      )}
      {selectedRequest && (
        <RequestDetailModal
          request={selectedRequest}
          onClose={() => setSelectedRequest(null)}
          onScheduleCall={(ref) => {
            setSelectedReference(ref);
            setShowScheduleCall(true);
          }}
        />
      )}
      {selectedCall && (
        <CallDetailModal
          call={selectedCall}
          onClose={() => setSelectedCall(null)}
        />
      )}
      {showScheduleCall && selectedReference && (
        <ScheduleCallModal
          reference={selectedReference}
          templates={templates}
          personas={personas}
          onClose={() => {
            setShowScheduleCall(false);
            setSelectedReference(null);
          }}
          onScheduled={() => {
            setShowScheduleCall(false);
            setSelectedReference(null);
            loadData();
          }}
        />
      )}
    </div>
  );
}

// ============================================================================
// Tab Components
// ============================================================================

function RequestsTab({
  requests,
  onSelect,
  onRefresh,
}: {
  requests: ReferenceCheckRequest[];
  onSelect: (request: ReferenceCheckRequest) => void;
  onRefresh: () => void;
}) {
  const sendForm = async (requestId: number) => {
    try {
      await AXIOS_INSTANCE.post(`/api/v1/reference-checks/requests/${requestId}/send-form`);
      onRefresh();
    } catch (error) {
      console.error('Failed to send form:', error);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Candidate
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Position
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              References
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Created
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {requests.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                No reference check requests yet. Create one to get started.
              </td>
            </tr>
          ) : (
            requests.map((request) => (
              <tr
                key={request.id}
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => onSelect(request)}
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">{request.candidate_name}</div>
                  <div className="text-sm text-gray-500">{request.candidate_email}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">{request.job_title || '-'}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    {request.reference_count} / {request.max_references}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[request.status] || 'bg-gray-100 text-gray-800'}`}>
                    {request.status.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(request.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {request.status === 'pending' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        sendForm(request.id);
                      }}
                      className="text-brand hover:text-brand-dark"
                    >
                      Send Form
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function TemplatesTab({
  templates,
  onRefresh,
}: {
  templates: CallTemplate[];
  onRefresh: () => void;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {templates.length === 0 ? (
        <div className="col-span-full text-center py-12 text-gray-500">
          No call templates yet. Create one to define the questions for reference checks.
        </div>
      ) : (
        templates.map((template) => (
          <div
            key={template.id}
            className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-medium text-gray-900">{template.name}</h3>
                {template.description && (
                  <p className="mt-1 text-sm text-gray-500">{template.description}</p>
                )}
              </div>
              {template.is_default && (
                <span className="px-2 py-1 text-xs font-medium bg-brand/10 text-brand rounded-full">
                  Default
                </span>
              )}
            </div>
            <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
              <span>{template.question_count} questions</span>
              <span>•</span>
              <span>{template.is_active ? 'Active' : 'Inactive'}</span>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-100">
              <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">Questions</h4>
              <ul className="space-y-1">
                {template.questions.slice(0, 3).map((q) => (
                  <li key={q.id} className="text-sm text-gray-600 truncate">
                    • {q.question_text}
                  </li>
                ))}
                {template.questions.length > 3 && (
                  <li className="text-sm text-gray-400">
                    +{template.questions.length - 3} more
                  </li>
                )}
              </ul>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function PersonasTab({
  personas,
  onRefresh,
}: {
  personas: VoicePersona[];
  onRefresh: () => void;
}) {
  const toneEmojis: Record<string, string> = {
    professional: '💼',
    friendly: '😊',
    empathetic: '💜',
    direct: '🎯',
    formal: '📋',
    casual: '👋',
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {personas.length === 0 ? (
        <div className="col-span-full text-center py-12 text-gray-500">
          No voice personas yet. Create one to define how the AI agent speaks.
        </div>
      ) : (
        personas.map((persona) => (
          <div
            key={persona.id}
            className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="text-3xl">{toneEmojis[persona.tone] || '🎙️'}</div>
                <div>
                  <h3 className="text-lg font-medium text-gray-900">{persona.name}</h3>
                  {persona.description && (
                    <p className="mt-1 text-sm text-gray-500">{persona.description}</p>
                  )}
                </div>
              </div>
              {persona.is_default && (
                <span className="px-2 py-1 text-xs font-medium bg-brand/10 text-brand rounded-full">
                  Default
                </span>
              )}
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Voice Model</span>
                <span className="text-gray-900">{persona.voice_model}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Tone</span>
                <span className="text-gray-900 capitalize">{persona.tone}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Speaking Rate</span>
                <span className="text-gray-900">{persona.speaking_rate}x</span>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function ScheduledCallsTab({
  scheduledCalls,
  onRefresh,
}: {
  scheduledCalls: ScheduledCall[];
  onRefresh: () => void;
}) {
  const cancelCall = async (callId: number) => {
    if (!window.confirm('Are you sure you want to cancel this scheduled call?')) return;
    
    try {
      await AXIOS_INSTANCE.delete(`/api/v1/reference-checks/calls/scheduled/${callId}`);
      onRefresh();
    } catch (error) {
      console.error('Failed to cancel call:', error);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Reference
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Template
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Persona
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Scheduled
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Reminders
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {scheduledCalls.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                No scheduled calls. Schedule a call from a reference check request.
              </td>
            </tr>
          ) : (
            scheduledCalls.map((call) => (
              <tr key={call.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">{call.reference_name}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {call.template_name || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {call.persona_name || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(call.scheduled_at).toLocaleString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex gap-1">
                    <span className={`w-2 h-2 rounded-full ${call.reminder_24h_sent ? 'bg-green-500' : 'bg-gray-300'}`} title="24h reminder" />
                    <span className={`w-2 h-2 rounded-full ${call.reminder_2h_sent ? 'bg-green-500' : 'bg-gray-300'}`} title="2h reminder" />
                    <span className={`w-2 h-2 rounded-full ${call.reminder_15m_sent ? 'bg-green-500' : 'bg-gray-300'}`} title="15m reminder" />
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[call.status] || 'bg-gray-100 text-gray-800'}`}>
                    {call.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {call.status === 'scheduled' && (
                    <button
                      onClick={() => cancelCall(call.id)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function CallsTab({
  calls,
  onSelect,
  onRefresh,
}: {
  calls: Call[];
  onSelect: (call: Call) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Reference
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Type
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Duration
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Status
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Content
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Date
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {calls.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                No calls yet. Calls will appear here once scheduled calls are initiated.
              </td>
            </tr>
          ) : (
            calls.map((call) => (
              <tr
                key={call.id}
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => onSelect(call)}
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">{call.reference_name || '-'}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 capitalize">
                  {call.call_type.replace(/_/g, ' ')}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {call.duration_seconds ? `${Math.floor(call.duration_seconds / 60)}:${String(call.duration_seconds % 60).padStart(2, '0')}` : '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[call.call_status || ''] || 'bg-gray-100 text-gray-800'}`}>
                    {call.call_status || 'unknown'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex gap-2">
                    {call.has_recording && (
                      <span className="text-green-500" title="Has recording">🎙️</span>
                    )}
                    {call.has_transcript && (
                      <span className="text-blue-500" title="Has transcript">📝</span>
                    )}
                    {call.has_summary && (
                      <span className="text-purple-500" title="Has summary">📊</span>
                    )}
                    {call.consent_obtained && (
                      <span className="text-green-500" title="Consent obtained">✓</span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(call.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function PlaygroundTab({
  templates,
  personas,
}: {
  templates: CallTemplate[];
  personas: VoicePersona[];
}) {
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [selectedPersona, setSelectedPersona] = useState<number | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [conversationHistory, setConversationHistory] = useState<{role: string; content: string}[]>([]);

  const startSession = async () => {
    if (!selectedTemplate || !selectedPersona) {
      alert('Please select a template and persona');
      return;
    }

    try {
      const res = await AXIOS_INSTANCE.post('/api/v1/reference-checks/playground/session', {
        template_id: selectedTemplate,
        persona_id: selectedPersona,
      });
      
      // Connect WebSocket
      // TODO: Implement WebSocket connection
      setIsConnected(true);
    } catch (error) {
      console.error('Failed to start session:', error);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="mb-6">
        <h2 className="text-lg font-medium text-gray-900">Voice Agent Playground</h2>
        <p className="mt-1 text-sm text-gray-500">
          Test the voice agent with different templates and personas before making real calls.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Call Template
          </label>
          <select
            value={selectedTemplate || ''}
            onChange={(e) => setSelectedTemplate(Number(e.target.value) || null)}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
          >
            <option value="">Select a template...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Voice Persona
          </label>
          <select
            value={selectedPersona || ''}
            onChange={(e) => setSelectedPersona(Number(e.target.value) || null)}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
          >
            <option value="">Select a persona...</option>
            {personas.map((p) => (
              <option key={p.id} value={p.id}>{p.name} ({p.tone})</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-6">
        {!isConnected ? (
          <button
            onClick={startSession}
            disabled={!selectedTemplate || !selectedPersona}
            className="flex items-center gap-2 px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <PlayIcon className="w-5 h-5" />
            Start Test Session
          </button>
        ) : (
          <button
            onClick={() => setIsConnected(false)}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            <XCircleIcon className="w-5 h-5" />
            End Session
          </button>
        )}
      </div>

      {isConnected && (
        <div className="border rounded-lg p-4">
          <div className="flex items-center justify-center mb-4">
            <div className={`w-16 h-16 rounded-full flex items-center justify-center ${isRecording ? 'bg-red-100 animate-pulse' : 'bg-gray-100'}`}>
              <SpeakerWaveIcon className={`w-8 h-8 ${isRecording ? 'text-red-600' : 'text-gray-400'}`} />
            </div>
          </div>
          <div className="text-center text-sm text-gray-500 mb-4">
            {isRecording ? 'Listening...' : 'Click to speak'}
          </div>
          <div className="max-h-64 overflow-y-auto space-y-2">
            {conversationHistory.map((msg, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg ${
                  msg.role === 'agent'
                    ? 'bg-brand/10 text-brand ml-4'
                    : 'bg-gray-100 text-gray-800 mr-4'
                }`}
              >
                <div className="text-xs font-medium mb-1 capitalize">{msg.role}</div>
                <div className="text-sm">{msg.content}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SettingsTab() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await AXIOS_INSTANCE.get('/api/v1/reference-checks/settings');
      setSettings(res.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateSettings = async () => {
    try {
      await AXIOS_INSTANCE.put('/api/v1/reference-checks/settings', settings);
      alert('Settings saved');
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
      <h2 className="text-lg font-medium text-gray-900 mb-6">Reference Check Settings</h2>
      
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Max Call Duration (seconds)
          </label>
          <input
            type="number"
            value={settings?.max_call_duration_seconds || 1800}
            onChange={(e) => setSettings({ ...settings, max_call_duration_seconds: parseInt(e.target.value) })}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
            min={300}
            max={3600}
          />
          <p className="mt-1 text-xs text-gray-500">
            Maximum: {settings?.hard_limit_seconds || 3600} seconds
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Max References Per Candidate
          </label>
          <input
            type="number"
            value={settings?.max_references_per_candidate || 10}
            onChange={(e) => setSettings({ ...settings, max_references_per_candidate: parseInt(e.target.value) })}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
            min={1}
            max={20}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Default Reminder Intervals (seconds)
          </label>
          <input
            type="text"
            value={(settings?.default_reminder_intervals || [86400, 7200, 900]).join(', ')}
            onChange={(e) => setSettings({
              ...settings,
              default_reminder_intervals: e.target.value.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n))
            })}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
          />
          <p className="mt-1 text-xs text-gray-500">
            Comma-separated values (e.g., 86400, 7200, 900 for 24h, 2h, 15m)
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Incomplete Call Action
          </label>
          <select
            value={settings?.incomplete_call_action || 'flag_for_review'}
            onChange={(e) => setSettings({ ...settings, incomplete_call_action: e.target.value })}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
          >
            <option value="flag_for_review">Flag for Review</option>
            <option value="auto_reschedule">Auto Reschedule</option>
            <option value="mark_incomplete">Mark as Incomplete</option>
          </select>
        </div>

        <button
          onClick={updateSettings}
          className="w-full py-2 px-4 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors"
        >
          Save Settings
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Modal Components
// ============================================================================

function CreateRequestModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    candidate_name: '',
    candidate_email: '',
    candidate_phone: '',
    job_title: '',
    max_references: 3,
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await AXIOS_INSTANCE.post('/api/v1/reference-checks/requests', form);
      onCreated();
    } catch (error) {
      console.error('Failed to create request:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">New Reference Check Request</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Candidate Name *
            </label>
            <input
              type="text"
              value={form.candidate_name}
              onChange={(e) => setForm({ ...form, candidate_name: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Candidate Email *
            </label>
            <input
              type="email"
              value={form.candidate_email}
              onChange={(e) => setForm({ ...form, candidate_email: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Candidate Phone
            </label>
            <input
              type="tel"
              value={form.candidate_phone}
              onChange={(e) => setForm({ ...form, candidate_phone: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Job Title
            </label>
            <input
              type="text"
              value={form.job_title}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max References
            </label>
            <input
              type="number"
              value={form.max_references}
              onChange={(e) => setForm({ ...form, max_references: parseInt(e.target.value) })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              min={1}
              max={10}
            />
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Request'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CreateTemplateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    is_default: false,
    questions: [
      { question_text: '', question_type: 'concept', priority: 'required', order_index: 0, follow_up_enabled: true, max_follow_ups: 2 }
    ],
  });
  const [loading, setLoading] = useState(false);

  const addQuestion = () => {
    setForm({
      ...form,
      questions: [
        ...form.questions,
        { question_text: '', question_type: 'concept', priority: 'required', order_index: form.questions.length, follow_up_enabled: true, max_follow_ups: 2 }
      ],
    });
  };

  const removeQuestion = (index: number) => {
    setForm({
      ...form,
      questions: form.questions.filter((_, i) => i !== index),
    });
  };

  const updateQuestion = (index: number, field: string, value: any) => {
    const newQuestions = [...form.questions];
    newQuestions[index] = { ...newQuestions[index], [field]: value };
    setForm({ ...form, questions: newQuestions });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await AXIOS_INSTANCE.post('/api/v1/reference-checks/templates', form);
      onCreated();
    } catch (error) {
      console.error('Failed to create template:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold text-gray-900 mb-4">New Call Template</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Template Name *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              rows={2}
            />
          </div>
          
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              className="rounded border-gray-300 text-brand focus:ring-brand"
            />
            <label className="text-sm text-gray-700">Set as default template</label>
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Questions
              </label>
              <button
                type="button"
                onClick={addQuestion}
                className="text-sm text-brand hover:text-brand-dark"
              >
                + Add Question
              </button>
            </div>
            
            <div className="space-y-3">
              {form.questions.map((q, idx) => (
                <div key={idx} className="p-3 border rounded-lg bg-gray-50">
                  <div className="flex items-start gap-2">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={q.question_text}
                        onChange={(e) => updateQuestion(idx, 'question_text', e.target.value)}
                        placeholder="Question text..."
                        className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm"
                        required
                      />
                    </div>
                    {form.questions.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeQuestion(idx)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <XCircleIcon className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    <select
                      value={q.question_type}
                      onChange={(e) => updateQuestion(idx, 'question_type', e.target.value)}
                      className="rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm"
                    >
                      <option value="concept">Concept</option>
                      <option value="verbatim">Verbatim</option>
                    </select>
                    <select
                      value={q.priority}
                      onChange={(e) => updateQuestion(idx, 'priority', e.target.value)}
                      className="rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand text-sm"
                    >
                      <option value="required">Required</option>
                      <option value="preferred">Preferred</option>
                      <option value="optional">Optional</option>
                    </select>
                    <div className="flex items-center gap-1">
                      <input
                        type="checkbox"
                        checked={q.follow_up_enabled}
                        onChange={(e) => updateQuestion(idx, 'follow_up_enabled', e.target.checked)}
                        className="rounded border-gray-300 text-brand focus:ring-brand"
                      />
                      <span className="text-xs text-gray-500">Follow-ups</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CreatePersonaModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    voice_model: 'alloy',
    speaking_rate: 1.0,
    tone: 'professional',
    introduction_script: '',
    closing_script: '',
    is_default: false,
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await AXIOS_INSTANCE.post('/api/v1/reference-checks/personas', form);
      onCreated();
    } catch (error) {
      console.error('Failed to create persona:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">New Voice Persona</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Persona Name *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              rows={2}
            />
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Voice Model
              </label>
              <select
                value={form.voice_model}
                onChange={(e) => setForm({ ...form, voice_model: e.target.value })}
                className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              >
                <option value="alloy">Alloy</option>
                <option value="echo">Echo</option>
                <option value="fable">Fable</option>
                <option value="onyx">Onyx</option>
                <option value="nova">Nova</option>
                <option value="shimmer">Shimmer</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tone
              </label>
              <select
                value={form.tone}
                onChange={(e) => setForm({ ...form, tone: e.target.value })}
                className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              >
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="empathetic">Empathetic</option>
                <option value="direct">Direct</option>
                <option value="formal">Formal</option>
                <option value="casual">Casual</option>
              </select>
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Speaking Rate: {form.speaking_rate}x
            </label>
            <input
              type="range"
              value={form.speaking_rate}
              onChange={(e) => setForm({ ...form, speaking_rate: parseFloat(e.target.value) })}
              className="w-full"
              min={0.5}
              max={2.0}
              step={0.1}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Introduction Script
            </label>
            <textarea
              value={form.introduction_script}
              onChange={(e) => setForm({ ...form, introduction_script: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              rows={2}
              placeholder="Hello, this is [Name] calling on behalf of..."
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Closing Script
            </label>
            <textarea
              value={form.closing_script}
              onChange={(e) => setForm({ ...form, closing_script: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              rows={2}
              placeholder="Thank you for your time..."
            />
          </div>
          
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              className="rounded border-gray-300 text-brand focus:ring-brand"
            />
            <label className="text-sm text-gray-700">Set as default persona</label>
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Persona'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RequestDetailModal({
  request,
  onClose,
  onScheduleCall,
}: {
  request: ReferenceCheckRequest;
  onClose: () => void;
  onScheduleCall: (reference: Reference) => void;
}) {
  const [references, setReferences] = useState<Reference[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReferences();
  }, [request.id]);

  const loadReferences = async () => {
    try {
      const res = await AXIOS_INSTANCE.get(`/api/v1/reference-checks/requests/${request.id}/references`);
      setReferences(res.data);
    } catch (error) {
      console.error('Failed to load references:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{request.candidate_name}</h2>
            <p className="text-sm text-gray-500">{request.candidate_email}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XCircleIcon className="w-6 h-6" />
          </button>
        </div>
        
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <span className="text-xs text-gray-500">Position</span>
            <p className="text-sm font-medium">{request.job_title || '-'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-500">Status</span>
            <p>
              <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[request.status]}`}>
                {request.status.replace(/_/g, ' ')}
              </span>
            </p>
          </div>
        </div>
        
        <div className="border-t pt-4">
          <h3 className="text-lg font-medium text-gray-900 mb-3">
            References ({references.length} / {request.max_references})
          </h3>
          
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand"></div>
            </div>
          ) : references.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">
              No references submitted yet.
            </p>
          ) : (
            <div className="space-y-3">
              {references.map((ref) => (
                <div key={ref.id} className="p-3 border rounded-lg">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{ref.full_name}</p>
                      <p className="text-sm text-gray-500">{ref.phone_number}</p>
                      {ref.company && (
                        <p className="text-sm text-gray-500">{ref.title} at {ref.company}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[ref.status]}`}>
                        {ref.status}
                      </span>
                      {ref.status === 'pending' && (
                        <button
                          onClick={() => onScheduleCall(ref)}
                          className="text-brand hover:text-brand-dark"
                        >
                          <PhoneIcon className="w-5 h-5" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ScheduleCallModal({
  reference,
  templates,
  personas,
  onClose,
  onScheduled,
}: {
  reference: Reference;
  templates: CallTemplate[];
  personas: VoicePersona[];
  onClose: () => void;
  onScheduled: () => void;
}) {
  const [form, setForm] = useState({
    reference_id: reference.id,
    scheduled_at: '',
    template_id: templates.find(t => t.is_default)?.id || null,
    persona_id: personas.find(p => p.is_default)?.id || null,
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      await AXIOS_INSTANCE.post('/api/v1/reference-checks/calls/schedule', {
        ...form,
        scheduled_at: new Date(form.scheduled_at).toISOString(),
      });
      onScheduled();
    } catch (error) {
      console.error('Failed to schedule call:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Schedule Call</h2>
        <p className="text-sm text-gray-500 mb-4">
          Scheduling call with <strong>{reference.full_name}</strong>
        </p>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Date & Time *
            </label>
            <input
              type="datetime-local"
              value={form.scheduled_at}
              onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Call Template
            </label>
            <select
              value={form.template_id || ''}
              onChange={(e) => setForm({ ...form, template_id: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
            >
              <option value="">Select template...</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name} {t.is_default ? '(default)' : ''}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Voice Persona
            </label>
            <select
              value={form.persona_id || ''}
              onChange={(e) => setForm({ ...form, persona_id: e.target.value ? parseInt(e.target.value) : null })}
              className="w-full rounded-lg border-gray-300 shadow-sm focus:border-brand focus:ring-brand"
            >
              <option value="">Select persona...</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.tone}) {p.is_default ? '(default)' : ''}</option>
              ))}
            </select>
          </div>
          
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-brand text-white rounded-lg hover:bg-brand-dark transition-colors disabled:opacity-50"
            >
              {loading ? 'Scheduling...' : 'Schedule Call'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CallDetailModal({
  call,
  onClose,
}: {
  call: Call;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDetail();
  }, [call.id]);

  const loadDetail = async () => {
    try {
      const res = await AXIOS_INSTANCE.get(`/api/v1/reference-checks/calls/${call.id}`);
      setDetail(res.data);
    } catch (error) {
      console.error('Failed to load call detail:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Call Details</h2>
            <p className="text-sm text-gray-500">
              Reference: {call.reference_name || 'Unknown'}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XCircleIcon className="w-6 h-6" />
          </button>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand"></div>
          </div>
        ) : detail ? (
          <div className="space-y-6">
            {/* Summary */}
            {detail.summary && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Summary</h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700">{detail.summary.executive_summary}</p>
                  
                  {detail.summary.key_strengths && (
                    <div className="mt-3">
                      <span className="text-xs font-medium text-gray-500">Key Strengths</span>
                      <ul className="mt-1 list-disc list-inside text-sm text-gray-700">
                        {detail.summary.key_strengths.map((s: string, i: number) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {detail.summary.areas_of_concern && (
                    <div className="mt-3">
                      <span className="text-xs font-medium text-gray-500">Areas of Concern</span>
                      <ul className="mt-1 list-disc list-inside text-sm text-gray-700">
                        {detail.summary.areas_of_concern.map((s: string, i: number) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {detail.summary.recommendation_score && (
                    <div className="mt-3 flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-500">Recommendation Score:</span>
                      <span className="text-lg font-bold text-brand">{detail.summary.recommendation_score}/10</span>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Question Responses */}
            {detail.question_responses && detail.question_responses.length > 0 && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Question Responses</h3>
                <div className="space-y-3">
                  {detail.question_responses.map((qr: any, idx: number) => (
                    <div key={idx} className="border rounded-lg p-3">
                      <p className="text-sm font-medium text-gray-900">{qr.question_asked}</p>
                      <p className="text-sm text-gray-700 mt-1">{qr.response_text}</p>
                      {qr.sentiment && (
                        <span className={`mt-2 inline-block px-2 py-1 text-xs rounded-full ${
                          qr.sentiment === 'positive' ? 'bg-green-100 text-green-800' :
                          qr.sentiment === 'negative' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {qr.sentiment}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Transcript */}
            {detail.transcript && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Transcript</h3>
                <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                    {detail.transcript.full_transcript}
                  </pre>
                </div>
              </div>
            )}
            
            {/* Recording */}
            {detail.recording_url && (
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">Recording</h3>
                <audio controls className="w-full">
                  <source src={detail.recording_url} type="audio/mpeg" />
                  Your browser does not support the audio element.
                </audio>
              </div>
            )}
          </div>
        ) : (
          <p className="text-center text-gray-500 py-8">Failed to load call details.</p>
        )}
      </div>
    </div>
  );
}

